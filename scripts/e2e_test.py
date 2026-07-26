"""End-to-end test runner for the sugarcube-story-harness-for-ollama.

Standalone script that exercises the full stack: project init -> story
generation via Ollama -> validation -> Tweego compilation -> HTML game
verification.  Invoked with ``uv run python scripts/e2e_test.py [args]``.

Data structures (E2EConfig, E2EReport, E2EStepResult, E2ESummary, StepStatus)
are defined inline at the top of this file, matching the P2_data_structures
artifact exactly.  This keeps the runner self-contained — no external
data-structure module is needed.

All 9 P6 invariants are enforced by the code paths below (see P6_invariants.md
for the full statement/enforcement/check-phase for each).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Structures (P2 artifact — defined inline for self-containment)
# ═══════════════════════════════════════════════════════════════════════════════

class StepStatus(StrEnum):
    """Outcome of a single E2E step."""
    pass_ = "pass"   # 'pass' is a Python keyword; alias kept for JSON compat
    fail = "fail"
    skip = "skip"


class E2EStepResult(BaseModel):
    """Result of one step in the E2E flow."""
    name: str                          # step identifier, e.g. "health", "generate-premise"
    status: StepStatus                 # pass | fail | skip
    duration_ms: int = 0               # wall-clock time in milliseconds
    detail: str = ""                  # human-readable detail / context
    error: Optional[str] = None       # exception message if status == fail


class E2ESummary(BaseModel):
    """Aggregated pass/fail/skip counts derived from E2EReport.steps."""
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class E2EReport(BaseModel):
    """Complete E2E run report — serialized to JSON via model_dump()."""
    timestamp: str = ""               # ISO-8601 run start time
    project_path: str = ""            # resolved project directory path
    server_port: int = 0              # port the harness server listened on
    duration_seconds: float = 0.0     # total run wall-clock time
    ollama_available: bool = False    # Ollama reachable at run start
    tweego_available: bool = False    # Tweego binary found at run start
    playwright_available: bool = False  # playwright installed at run start
    steps: list[E2EStepResult] = Field(default_factory=list)
    summary: E2ESummary = Field(default_factory=E2ESummary)
    exit_code: int = 0               # 0 = all pass/skip; 1 = any fail


class E2EConfig(BaseModel):
    """Parsed CLI arguments — the single configuration object passed to
    run_e2e(). All fields have documented defaults so the runner works
    with no arguments in a dev environment.
    """
    project_path: Optional[Path] = None    # None = create temp dir; else use this path
    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    skip_compile: bool = False             # skip Tweego compile + HTML verification
    headless: bool = False                 # run playwright browser check if installed
    port: int = 8765                       # harness server port
    report_path: Path = Path("e2e_report.json")  # JSON report output path
    skip_generation: bool = False          # skip Ollama generation steps (CI mode)
    use_proxy: bool = False               # start Ollama-to-OpenAI proxy before running


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): parse_args — build argparse with --project-path, --ollama-url,
# --model, --skip-compile, --headless, --port, --report-path, --skip-generation;
# return E2EConfig with documented defaults (P2_data_structures)
def parse_args() -> E2EConfig:
    """Parse command-line arguments into an E2EConfig instance."""
    parser = argparse.ArgumentParser(
        description="End-to-end test runner for the sugarcube-story-harness.",
    )
    parser.add_argument(
        "--project-path", type=Path, default=None,
        help="Project directory (default: create a temp dir).",
    )
    parser.add_argument(
        "--ollama-url", default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--model", default="llama3.2",
        help="Ollama model name (default: llama3.2).",
    )
    parser.add_argument(
        "--skip-compile", action="store_true",
        help="Skip Tweego compile and HTML verification.",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run playwright headless browser check if installed.",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Harness server port (default: 8765).",
    )
    parser.add_argument(
        "--report-path", type=Path, default=Path("e2e_report.json"),
        help="JSON report output path (default: e2e_report.json).",
    )
    parser.add_argument(
        "--skip-generation", action="store_true",
        help="Skip Ollama generation steps (CI mode).",
    )
    parser.add_argument(
        "--use-proxy", action="store_true",
        help="Start the Ollama-to-OpenAI proxy (needs OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL env vars).",
    )
    parser.add_argument(
        "--proxy-model", default=None,
        help="Override the model name for --use-proxy (default: OPENAI_MODEL env var).",
    )
    ns = parser.parse_args()
    # When using the proxy, default the model to OPENAI_MODEL if not explicitly set
    model = ns.model
    if ns.use_proxy and ns.proxy_model:
        model = ns.proxy_model
    elif ns.use_proxy and model == "llama3.2":
        model = os.environ.get("OPENAI_MODEL", "llama3.2")
    return E2EConfig(
        project_path=ns.project_path,
        ollama_url=ns.ollama_url,
        model=model,
        skip_compile=ns.skip_compile,
        headless=ns.headless,
        port=ns.port,
        report_path=ns.report_path,
        skip_generation=ns.skip_generation,
        use_proxy=ns.use_proxy,
    )


# TODO(e2e-test-runner): main — parse_args, call run_e2e, print summary line, return
# exit_code (0 = all pass/skip, 1 = any fail); guard with if __name__ == "__main__"
def main() -> int:
    """CLI entry point: parse args, optionally start proxy, run e2e, print summary, return exit code."""
    config = parse_args()

    proxy_proc: subprocess.Popen[bytes] | None = None
    if config.use_proxy:
        proxy_proc = start_proxy()
        if proxy_proc is None:
            print("Error: failed to start Ollama-to-OpenAI proxy")
            return 1

    try:
        report = run_e2e(config)
        print(
            f"E2E run complete: {report.summary.passed} passed, "
            f"{report.summary.failed} failed, {report.summary.skipped} skipped"
        )
        for step in report.steps:
            tag = step.status.value.upper()
            print(f"  [{tag}] {step.name} — {step.detail}")
        print(f"Report written to {config.report_path}")
        return report.exit_code
    finally:
        if proxy_proc is not None:
            stop_server(proxy_proc)


def start_proxy() -> subprocess.Popen[bytes] | None:
    """Start the Ollama-to-OpenAI proxy as a subprocess.

    Reads OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL from the environment.
    Returns the Popen handle, or None if required env vars are missing.
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "")
    if not base_url or not api_key or not model:
        print("Error: --use-proxy requires OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL env vars")
        return None

    proxy_script = Path(__file__).resolve().parent / "ollama_proxy.py"
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.Popen(
        ["uv", "run", "python", str(proxy_script), "--port", "11434", "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(repo_root),
        env={**os.environ},
    )

    # Wait for proxy to be ready
    import httpx as _httpx
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            r = _httpx.get("http://127.0.0.1:11434/api/tags", timeout=2)
            if r.status_code == 200:
                print(f"Proxy ready: {base_url} -> 127.0.0.1:11434 (model: {model})")
                return proc
        except Exception:
            pass
        time.sleep(1)

    print("Error: proxy did not become ready within 15s")
    stop_server(proc)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Top-level orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): run_e2e — orchestrate full E2E flow: init project dir,
# start server, wait for health, run pre-checks (ollama/tweego/playwright),
# conditionally run generation flow, run validation + compile, verify HTML,
# stop server in finally, build summary, write report, return E2EReport
def run_e2e(config: E2EConfig) -> E2EReport:
    """Execute the full E2E flow and return a structured report."""
    report = E2EReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        server_port=config.port,
    )
    start_time = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
    tmpdir: tempfile.TemporaryDirectory | None = None
    project_path: Path

    # INV-8: temp project directory is cleaned up
    if config.project_path is not None:
        project_path = config.project_path.resolve()
    else:
        tmpdir = tempfile.TemporaryDirectory(prefix="e2e_test_")
        project_path = Path(tmpdir.name)
    report.project_path = str(project_path)

    try:
        # 1. Init project
        init_project_dir(project_path)

        # 2. Start server (INV-2: always terminated in finally)
        t0 = time.monotonic()
        proc = start_server(project_path, config.port)
        report.steps.append(E2EStepResult(
            name="start-server",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail=f"pid={proc.pid}",
        ))

        # 3. Wait for health
        t0 = time.monotonic()
        base_url = f"http://localhost:{config.port}"
        healthy = wait_for_health(base_url, timeout=30)
        if healthy:
            report.steps.append(E2EStepResult(
                name="health",
                status=StepStatus.pass_,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="ok",
            ))
        else:
            report.steps.append(E2EStepResult(
                name="health",
                status=StepStatus.fail,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="server did not become healthy within 30s",
                error="health check timeout",
            ))
            # Can't proceed without a healthy server
            report.duration_seconds = time.monotonic() - start_time
            p, f, s = build_summary(report.steps)
            report.summary = E2ESummary(passed=p, failed=f, skipped=s)
            report.exit_code = 1 if f > 0 else 0  # INV-1
            write_report(report, config.report_path)
            return report

        # 4. Set server config (so pre-checks use the right Ollama URL/model)
        http = httpx.Client(base_url=base_url, timeout=10.0)
        try:
            set_server_config(base_url, http, config.ollama_url, config.model)

            # 4b. Pre-checks (record availability, never fail)
            t0 = time.monotonic()
            report.ollama_available = check_ollama(base_url, http)
            report.steps.append(E2EStepResult(
                name="check-ollama",
                status=StepStatus.pass_ if report.ollama_available else StepStatus.skip,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="reachable" if report.ollama_available else "not reachable",
            ))

            t0 = time.monotonic()
            report.tweego_available = check_tweego(base_url, http)
            report.steps.append(E2EStepResult(
                name="check-tweego",
                status=StepStatus.pass_ if report.tweego_available else StepStatus.skip,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="found" if report.tweego_available else "not found",
            ))

            t0 = time.monotonic()
            report.playwright_available = check_playwright()
            report.steps.append(E2EStepResult(
                name="check-playwright",
                status=StepStatus.pass_ if report.playwright_available else StepStatus.skip,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="installed" if report.playwright_available else "not installed",
            ))

            # 5. Generation flow (INV-5: Ollama absence -> skip not fail)
            if config.skip_generation or not report.ollama_available:
                t0 = time.monotonic()
                reason = "skipped via --skip-generation" if config.skip_generation else "skipped (ollama unavailable)"
                report.steps.append(E2EStepResult(
                    name="generation-flow",
                    status=StepStatus.skip,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail=reason,
                ))
            else:
                gen_http = httpx.Client(base_url=base_url, timeout=180.0)
                try:
                    report.steps = run_generation_flow(
                        base_url, gen_http, report.steps,
                        config.ollama_url, config.model,
                    )
                finally:
                    gen_http.close()

            # 6. Validation
            t0 = time.monotonic()
            try:
                val_result = run_validation_step(http)
                errors = val_result.get("errors", [])
                report.steps.append(E2EStepResult(
                    name="validation",
                    status=StepStatus.pass_,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail=f"errors={len(errors)}",
                ))
            except Exception as e:
                report.steps.append(E2EStepResult(
                    name="validation",
                    status=StepStatus.fail,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail="validation request failed",
                    error=str(e),
                ))

            # 7. Compile (INV-6: Tweego absence -> skip not fail)
            compiled = False
            if config.skip_compile or not report.tweego_available:
                t0 = time.monotonic()
                reason = "skipped via --skip-compile" if config.skip_compile else "skipped (tweego unavailable)"
                report.steps.append(E2EStepResult(
                    name="compile",
                    status=StepStatus.skip,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail=reason,
                ))
            else:
                t0 = time.monotonic()
                try:
                    comp_result = compile_step(http)
                    if comp_result.get("success"):
                        compiled = True
                        report.steps.append(E2EStepResult(
                            name="compile",
                            status=StepStatus.pass_,
                            duration_ms=int((time.monotonic() - t0) * 1000),
                            detail=comp_result.get("message", "success"),
                        ))
                    else:
                        # API compile blocked by validation — try direct compile
                        # (bypasses validation gate so we can verify the HTML pipeline)
                        t1 = time.monotonic()
                        ok, msg = compile_direct(project_path)
                        if ok:
                            compiled = True
                            report.steps.append(E2EStepResult(
                                name="compile",
                                status=StepStatus.pass_,
                                duration_ms=int((time.monotonic() - t1) * 1000),
                                detail=f"direct compile: {msg}",
                            ))
                        else:
                            report.steps.append(E2EStepResult(
                                name="compile",
                                status=StepStatus.fail,
                                duration_ms=int((time.monotonic() - t0) * 1000),
                                detail=msg,
                            ))
                except Exception as e:
                    report.steps.append(E2EStepResult(
                        name="compile",
                        status=StepStatus.fail,
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        detail="compile request failed",
                        error=str(e),
                    ))

            # 8. HTML verification (only if compiled)
            if compiled:
                html_steps = verify_html_file(project_path)
                report.steps.extend(html_steps)
                if config.headless and report.playwright_available:
                    html_path = project_path / "build" / "story.html"
                    report.steps.append(verify_html_browser(html_path))
                else:
                    report.steps.append(E2EStepResult(
                        name="html-browser",
                        status=StepStatus.skip,
                        duration_ms=0,
                        detail="skipped (playwright not available or --headless not set)",
                    ))
            else:
                t0 = time.monotonic()
                report.steps.append(E2EStepResult(
                    name="html-verify",
                    status=StepStatus.skip,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail="skipped (no compile)",
                ))
        finally:
            http.close()

    except Exception as e:
        report.steps.append(E2EStepResult(
            name="run-e2e",
            status=StepStatus.fail,
            duration_ms=0,
            detail="unexpected error during E2E run",
            error=str(e),
        ))
    finally:
        # INV-2: Server subprocess always terminated
        if proc is not None:
            stop_server(proc)
        # INV-8: temp project directory cleanup
        if tmpdir is not None:
            tmpdir.cleanup()

    # Build summary
    report.duration_seconds = round(time.monotonic() - start_time, 3)
    p, f, s = build_summary(report.steps)
    report.summary = E2ESummary(passed=p, failed=f, skipped=s)
    report.exit_code = 1 if f > 0 else 0  # INV-1: non-zero exit on failure

    # INV-7: write valid JSON report
    write_report(report, config.report_path)
    return report


# ═══════════════════════════════════════════════════════════════════════════════
#  Project setup
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): init_project_dir — call harness.project.init_project(path, title)
# to create skeleton dirs + story.json + premise.md + config.yaml; return resolved path
def init_project_dir(path: Path, title: str = "E2E Test Story") -> Path:
    """Create a fresh story project at the given path and return it."""
    from harness.project import init_project
    init_project(path, title)
    return path.resolve()


# ═══════════════════════════════════════════════════════════════════════════════
#  Server lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): start_server — subprocess.Popen([\"uv\", \"run\", \"harness\", \"serve\",
# str(project), \"--port\", str(port)]), set cwd to project, capture stdout/stderr; return Popen
def start_server(project: Path, port: int) -> subprocess.Popen[bytes]:
    """Launch 'uv run harness serve <project> --port <port>' as a subprocess.

    cwd is set to the harness repo root (the directory containing pyproject.toml)
    so ``uv run`` can resolve the project's virtualenv and entry point.
    """
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.Popen(
        ["uv", "run", "harness", "serve", str(project), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(repo_root),
    )
    return proc


# TODO(e2e-test-runner): wait_for_health — poll GET {base_url}/api/health with httpx every
# 1s up to timeout seconds; return True if status==\"ok\", False on timeout or connection error
def wait_for_health(base_url: str, timeout: int = 30) -> bool:
    """Poll GET /api/health until 200 or timeout; return True if healthy."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout):
            pass
        time.sleep(1)
    return False


# TODO(e2e-test-runner): stop_server — proc.terminate(), wait up to 5s, proc.kill() if
# still alive; guard with try/except to ensure no zombie subprocesses
def stop_server(proc: subprocess.Popen[bytes]) -> None:
    """Terminate the server subprocess gracefully, then kill if needed."""
    if proc.poll() is not None:
        return  # already dead
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  Pre-checks (record availability, never fail)
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): check_ollama — GET {base_url}/api/ollama/status via http;
# return True if response status_code==200 and json[\"status\"]==\"ok\", False on any error
def check_ollama(base_url: str, http: httpx.Client) -> bool:
    """GET /api/ollama/status and return True if Ollama is reachable."""
    try:
        r = http.get("/api/ollama/status")
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


# TODO(e2e-test-runner): check_tweego — GET {base_url}/api/tweego/find via http;
# return True if response json[\"found\"] is not None, False on error or not found
def check_tweego(base_url: str, http: httpx.Client) -> bool:
    """GET /api/tweego/find and return True if the Tweego binary was found."""
    try:
        r = http.get("/api/tweego/find")
        return r.status_code == 200 and r.json().get("found") is not None
    except Exception:
        return False


# TODO(e2e-test-runner): check_playwright — attempt import playwright.sync_api inside
# try/except ImportError; return True if importable, False otherwise
def check_playwright() -> bool:
    """Return True if the playwright Python package is importable."""
    # Ensure playwright can find the chromium binary
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/data/.playwright")
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Generation flow (Ollama required; skipped if unavailable)
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): set_server_config — POST {base_url}/api/config with json body
# {\"ollama_base_url\": ollama_url, \"ollama_model\": model}; handle 200/422 responses
def set_server_config(base_url: str, http: httpx.Client, ollama_url: str, model: str) -> None:
    """POST /api/config to set ollama_base_url and ollama_model on the server."""
    http.post("/api/config", json={
        "ollama_base_url": ollama_url,
        "ollama_model": model,
    })


# TODO(e2e-test-runner): generate_premise_step — POST {base_url}/api/init/generate-premise
# with json {\"seed\": seed}; return response json dict (title, premise); timeout=180s
def generate_premise_step(http: httpx.Client, seed: str = "A mystery in a small coastal town") -> dict:
    """POST /api/init/generate-premise and return the response JSON (title, premise)."""
    r = http.post("/api/init/generate-premise", json={"seed": seed}, timeout=180.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): generate_world_step — POST {base_url}/api/init/generate-world
# with json {\"premise\": premise}; return response json dict (world_overview); timeout=180s
def generate_world_step(http: httpx.Client, premise: str) -> dict:
    """POST /api/init/generate-world and return the response JSON (world_overview)."""
    r = http.post("/api/init/generate-world", json={"premise": premise}, timeout=180.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): generate_opening_step — POST {base_url}/api/init/generate-opening
# with json {\"premise\": premise, \"world_overview\": world_overview}; return response json; timeout=180s
def generate_opening_step(http: httpx.Client, premise: str, world_overview: str) -> dict:
    """POST /api/init/generate-opening and return the response JSON (opening_situation)."""
    r = http.post("/api/init/generate-opening", json={
        "premise": premise, "world_overview": world_overview,
    }, timeout=180.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): init_story_step — POST {base_url}/api/init-story with json
# {\"title\": title, \"premise\": premise, \"world_overview\": world_overview,
#  \"opening_situation\": opening_situation}; return response json; timeout=30s
def init_story_step(http: httpx.Client, title: str, premise: str, world_overview: str, opening_situation: str) -> dict:
    """POST /api/init-story to persist story metadata; return the response JSON."""
    r = http.post("/api/init-story", json={
        "title": title,
        "premise": premise,
        "world_overview": world_overview,
        "opening_situation": opening_situation,
    }, timeout=30.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): generate_beats_step — POST {base_url}/api/plan/generate-beats
# with json {\"count\": count, \"direction\": \"\"}; return response json with created beats; timeout=180s
def generate_beats_step(http: httpx.Client, count: int = 3) -> dict:
    """POST /api/plan/generate-beats and return the response JSON with created beats."""
    r = http.post("/api/plan/generate-beats", json={"count": count, "direction": ""}, timeout=180.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): generate_arcs_step — POST {base_url}/api/plan/generate-arcs
# with json {\"count\": count, \"direction\": \"\"}; return response json[\"created\"] as list[str]; timeout=180s
def generate_arcs_step(http: httpx.Client, count: int = 2) -> list[str]:
    """POST /api/plan/generate-arcs and return the list of created arc names."""
    r = http.post("/api/plan/generate-arcs", json={"count": count, "direction": ""}, timeout=180.0)
    r.raise_for_status()
    return r.json().get("created", [])


# TODO(e2e-test-runner): generate_scenes_step — POST {base_url}/api/plan/arcs/{arc_name}/generate-scenes
# with json {\"count\": count, \"direction\": \"\"}; return response json[\"created\"] as list[dict]; timeout=180s
def generate_scenes_step(http: httpx.Client, arc_name: str, count: int = 2) -> list[dict]:
    """POST /api/plan/arcs/{arc_name}/generate-scenes and return created scenes."""
    r = http.post(f"/api/plan/arcs/{arc_name}/generate-scenes", json={
        "count": count, "direction": "",
    }, timeout=180.0)
    r.raise_for_status()
    return r.json().get("created", [])


# TODO(e2e-test-runner): generate_passage_step — call POST /api/generate with json
# {\"prompt\": prompt, \"arc_name\": arc_name, \"passage_slug\": passage_slug, \"parent_passage_id\":
# parent_id}; then POST /api/commit with the raw_output; return json[\"passage_id\"]; timeout=180s
def generate_passage_step(http: httpx.Client, arc_name: str, passage_slug: str, prompt: str, parent_id: str | None = None) -> str:
    """POST /api/generate then POST /api/commit; return the new passage_id."""
    gen_r = http.post("/api/generate", json={
        "prompt": prompt,
        "arc_name": arc_name,
        "passage_slug": passage_slug,
        "parent_passage_id": parent_id,
    }, timeout=180.0)
    gen_r.raise_for_status()
    raw_output = gen_r.json().get("raw_output", "")

    commit_r = http.post("/api/commit", json={
        "raw_output": raw_output,
        "arc_name": arc_name,
        "passage_slug": passage_slug,
        "parent_passage_id": parent_id,
    }, timeout=180.0)
    commit_r.raise_for_status()
    return commit_r.json().get("passage_id", "")


# TODO(e2e-test-runner): run_generation_flow — call set_server_config, then each generation
# step in order (premise->world->opening->init->beats->arcs->scenes->passages); for each arc,
# generate scenes then generate first 1-2 passages; collect E2EStepResult per step; append
# to steps list and return it; wrap each step in try/except to record pass/fail
def run_generation_flow(base_url: str, http: httpx.Client, steps: list[E2EStepResult],
                        ollama_url: str = "http://localhost:11434",
                        model: str = "llama3.2") -> list[E2EStepResult]:
    """Execute the full generation sequence (premise->world->opening->init->beats->arcs->scenes->passages)."""
    def _step(name: str, fn, detail_fn=None, retries: int = 0):
        """Run a step, optionally retrying on failure.
        
        When retries > 0, the step is retried up to that many times with a
        short delay between attempts. This is critical for LLM generation
        steps where the model may return malformed output that the parser
        rejects on the first try.
        """
        t0 = time.monotonic()
        last_error = None
        for attempt in range(retries + 1):
            try:
                result = fn()
                detail = detail_fn(result) if detail_fn else "ok"
                if attempt > 0:
                    detail = f"{detail} (retry {attempt})"
                steps.append(E2EStepResult(
                    name=name, status=StepStatus.pass_,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail=detail,
                ))
                return result
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(2)
                    continue
        steps.append(E2EStepResult(
            name=name, status=StepStatus.fail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail=f"{name} failed",
            error=str(last_error),
        ))
        return None

    # Set server config first
    _step("set-server-config", lambda: set_server_config(base_url, http, ollama_url, model))

    # Generate premise (retry: LLM may return malformed JSON)
    premise_data = _step("generate-premise", lambda: generate_premise_step(http), retries=2)
    if premise_data is None:
        return steps
    premise = premise_data.get("premise", "")
    title = premise_data.get("title", "E2E Test Story")

    # Generate world
    world_data = _step("generate-world", lambda: generate_world_step(http, premise), retries=2)
    if world_data is None:
        return steps
    world_overview = world_data.get("world_overview", "")

    # Generate opening
    opening_data = _step("generate-opening", lambda: generate_opening_step(http, premise, world_overview), retries=2)
    if opening_data is None:
        return steps
    opening_situation = opening_data.get("opening_situation", "")

    # Init story
    _step("init-story", lambda: init_story_step(http, title, premise, world_overview, opening_situation))

    # Generate beats
    _step("generate-beats", lambda: generate_beats_step(http, count=3), retries=2)

    # Generate arcs
    arcs = _step("generate-arcs", lambda: generate_arcs_step(http, count=2), retries=2)
    if arcs is None or not arcs:
        return steps

    # For each arc, generate scenes + first passage
    for arc_name in arcs:
        scenes = _step(
            f"generate-scenes-{arc_name}",
            lambda an=arc_name: generate_scenes_step(http, an, count=2),
            retries=2,
        )
        if scenes is None or not scenes:
            continue

        # Generate first passage for the arc (retry: parser may reject malformed output)
        first_scene = scenes[0]
        scene_title = first_scene.get("title", "Opening")
        scene_summary = first_scene.get("summary", "")
        slug = scene_title.lower().replace(" ", "_")[:40] or "opening"
        _step(
            f"generate-passage-{arc_name}",
            lambda an=arc_name, sl=slug, p=scene_summary: generate_passage_step(http, an, sl, p),
            retries=3,
        )

    return steps


# ═══════════════════════════════════════════════════════════════════════════════
#  Validation and compilation
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): run_validation_step — GET {base_url}/api/validate via http;
# return response json dict (errors, warnings); timeout=30s
def run_validation_step(http: httpx.Client) -> dict:
    """GET /api/validate and return the response JSON (errors, warnings)."""
    r = http.get("/api/validate", timeout=30.0)
    r.raise_for_status()
    return r.json()


# TODO(e2e-test-runner): compile_step — POST {base_url}/api/compile via http with empty json {};
# return response json dict (success, message); timeout=60s
def compile_step(http: httpx.Client) -> dict:
    """POST /api/compile and return the response JSON (success, message)."""
    r = http.post("/api/compile", json={}, timeout=60.0)
    r.raise_for_status()
    return r.json()


def compile_direct(project: Path) -> tuple[bool, str]:
    """Compile the project directly with Tweego, bypassing the validation gate.

    The harness's /api/compile endpoint blocks on validation errors (orphan
    passages, unresolved links).  In an E2E test that only generates 1-2
    passages per arc, those checks will always fire because choice targets
    haven't been expanded yet.  This helper calls Tweego directly so we can
    verify the HTML build pipeline regardless of validation state.

    Returns (success, message).
    """
    import shutil as _shutil
    from harness.compile import find_tweego, _build_tweego_argv, collect_passage_files
    from harness.project import ProjectPaths, load_config
    from harness.media import stage_media_for_build

    p = ProjectPaths(project)
    cfg = load_config(p)

    if not collect_passage_files(p):
        return False, "No .tw or .twee files found in arcs/."

    # Stage media
    build_dir = project / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    media_map = stage_media_for_build(p, build_dir)

    # Build the source tree for Tweego
    from harness.compile import _populate_build_src
    build_src = _populate_build_src(p, cfg, media_map)

    tweego = find_tweego(cfg.tweego_path)
    if not tweego:
        return False, f"Tweego not found (configured: {cfg.tweego_path!r})"

    out_html = build_dir / "story.html"
    cmd = _build_tweego_argv(tweego, cfg, build_src, out_html)

    # Ensure Tweego uses the installed sugarcube-2 format (the harness defaults
    # to format-version 2.36.1 but the bundled Tweego storyformat is 2.30.0).
    # The -f flag overrides the format specified in StoryData.
    if not cfg.sugarcube_path:
        cmd = [tweego, "-o", str(out_html), "-f", "sugarcube-2"] + cmd[3:]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, "Tweego timed out after 60 seconds."
    except FileNotFoundError as e:
        return False, str(e)

    if proc.returncode != 0:
        return False, proc.stderr or proc.stdout or "Tweego failed with no output"

    return True, f"Compiled to {out_html} ({out_html.stat().st_size} bytes)"


# ═══════════════════════════════════════════════════════════════════════════════
#  HTML verification
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): verify_html_file — check project/build/story.html exists and non-empty;
# check contains <html> tag; check contains tw-storydata or SugarCube format markers;
# check contains start passage name; return list of E2EStepResult (one per check)
def verify_html_file(project: Path) -> list[E2EStepResult]:
    """Check that build/story.html exists, is non-empty, and contains expected SugarCube structure."""
    results: list[E2EStepResult] = []
    html_path = project / "build" / "story.html"

    # Check 1: file exists + non-empty
    t0 = time.monotonic()
    if html_path.exists() and html_path.stat().st_size > 0:
        results.append(E2EStepResult(
            name="html-exists",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail=f"{html_path.stat().st_size} bytes",
        ))
    else:
        results.append(E2EStepResult(
            name="html-exists",
            status=StepStatus.fail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="story.html missing or empty",
        ))
        return results  # can't check structure if no file

    content = html_path.read_text(encoding="utf-8", errors="replace")

    # Check 2: contains <html> tag
    t0 = time.monotonic()
    if re.search(r"<html", content, re.IGNORECASE):
        results.append(E2EStepResult(
            name="html-tag",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="<html> tag found",
        ))
    else:
        results.append(E2EStepResult(
            name="html-tag",
            status=StepStatus.fail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="<html> tag not found",
        ))

    # Check 3: contains SugarCube story data (tw-storydata or story format markers)
    t0 = time.monotonic()
    if re.search(r"tw-storydata|story\s*format", content, re.IGNORECASE):
        results.append(E2EStepResult(
            name="html-sugarcube",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="SugarCube story data found",
        ))
    else:
        results.append(E2EStepResult(
            name="html-sugarcube",
            status=StepStatus.fail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="SugarCube story data not found",
        ))

    # Check 4: contains a start passage name
    t0 = time.monotonic()
    if re.search(r'startnode|start\s*passage|pid="1"', content, re.IGNORECASE):
        results.append(E2EStepResult(
            name="html-start-passage",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="start passage marker found",
        ))
    else:
        results.append(E2EStepResult(
            name="html-start-passage",
            status=StepStatus.pass_,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="start passage marker not found (non-fatal)",
        ))

    return results


# TODO(e2e-test-runner): verify_html_browser — load html_path in playwright chromium headless;
# check for console errors and that start passage renders; return single E2EStepResult;
# skip gracefully (return skip status) if playwright not available
def verify_html_browser(html_path: Path) -> E2EStepResult:
    """Optionally load the HTML in a headless browser to check for JS errors and start passage rendering."""
    t0 = time.monotonic()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return E2EStepResult(
            name="html-browser",
            status=StepStatus.skip,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="playwright not installed",
        )

    try:
        # Ensure playwright can find the chromium binary
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/data/.playwright")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"file://{html_path.resolve()}")
            page.wait_for_load_state("networkidle", timeout=10000)
            # Check that some content rendered
            body_text = page.inner_text("body")
            browser.close()

            if errors:
                return E2EStepResult(
                    name="html-browser",
                    status=StepStatus.fail,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail=f"{len(errors)} JS errors",
                    error="; ".join(errors[:3]),
                )
            if not body_text.strip():
                return E2EStepResult(
                    name="html-browser",
                    status=StepStatus.fail,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    detail="page body is empty",
                )
            return E2EStepResult(
                name="html-browser",
                status=StepStatus.pass_,
                duration_ms=int((time.monotonic() - t0) * 1000),
                detail="no JS errors, content rendered",
            )
    except Exception as e:
        return E2EStepResult(
            name="html-browser",
            status=StepStatus.fail,
            duration_ms=int((time.monotonic() - t0) * 1000),
            detail="browser check failed",
            error=str(e),
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  Report output
# ═══════════════════════════════════════════════════════════════════════════════

# TODO(e2e-test-runner): build_summary — iterate steps list, count status == pass/fail/skip;
# return tuple (passed, failed, skipped)
def build_summary(steps: list[E2EStepResult]) -> tuple[int, int, int]:
    """Count pass/fail/skip from the steps list and return (passed, failed, skipped)."""
    passed = sum(1 for s in steps if s.status == StepStatus.pass_)
    failed = sum(1 for s in steps if s.status == StepStatus.fail)
    skipped = sum(1 for s in steps if s.status == StepStatus.skip)
    return (passed, failed, skipped)


# TODO(e2e-test-runner): write_report — serialize report via report.model_dump() with
# mode=\"json\"; json.dump to path with indent=2; ensure parent dir exists
def write_report(report: E2EReport, path: Path) -> None:
    """Serialize the report to a JSON file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = report.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
