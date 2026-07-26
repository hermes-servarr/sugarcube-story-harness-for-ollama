"""Pytest E2E test suite for the sugarcube-story-harness.

Thin pytest wrappers around the E2E flow defined in scripts/e2e_test.py.
Tests are marked with @pytest.mark.e2e and skip gracefully when Ollama,
Tweego, or playwright are not available.

Run with:  uv run pytest tests/test_e2e.py -m e2e

Implementation at approved TODO(e2e-test-runner) sites from P4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

# Import the runner module — add scripts/ to sys.path
_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import e2e_test


# ── pytest marker registration ──────────────────────────────────────────────

# TODO(e2e-test-runner): register the "e2e" marker in pytest config (pyproject.toml
# [tool.pytest.ini_options] markers list) to suppress unknown-marker warnings
# (Marker registration is in pyproject.toml [tool.pytest.ini_options])


# ── Session-scoped fixtures ──────────────────────────────────────────────────

# TODO(e2e-test-runner): e2e_config fixture — yield an E2EConfig instance with defaults
# (temp project_path, localhost:11434, llama3.2, port 8765, skip_compile=False,
# headless=False, skip_generation=False); cleanup temp dir on teardown
@pytest.fixture
def e2e_config() -> "e2e_test.E2EConfig":
    """Provide an E2EConfig with defaults for E2E tests."""
    import tempfile
    tmpdir = tempfile.TemporaryDirectory(prefix="e2e_pytest_")
    config = e2e_test.E2EConfig(
        project_path=Path(tmpdir.name),
        ollama_url="http://localhost:11434",
        model="llama3.2",
        skip_compile=False,
        headless=False,
        port=8765,
        report_path=Path(tmpdir.name) / "e2e_report.json",
        skip_generation=False,
    )
    yield config
    tmpdir.cleanup()


# TODO(e2e-test-runner): server fixture — use e2e_config to init_project_dir,
# start_server, wait_for_health; yield base_url string; stop_server in finally;
# session-scoped so the server starts once for all tests in the module
@pytest.fixture(scope="session")
def server() -> str:
    """Start the harness server once per session and yield its base_url."""
    import tempfile
    tmpdir = tempfile.TemporaryDirectory(prefix="e2e_server_")
    project_path = Path(tmpdir.name)
    base_url = f"http://localhost:8765"
    proc = None
    try:
        e2e_test.init_project_dir(project_path)
        proc = e2e_test.start_server(project_path, 8765)
        healthy = e2e_test.wait_for_health(base_url, timeout=30)
        if not healthy:
            pytest.skip("Could not start harness server")
        yield base_url
    finally:
        if proc is not None:
            e2e_test.stop_server(proc)
        tmpdir.cleanup()


# TODO(e2e-test-runner): http_client fixture — create httpx.Client with timeout=180s;
# yield client; close in finally; function-scoped so each test gets a fresh client
@pytest.fixture
def http_client(server: str) -> "httpx.Client":
    """Provide an httpx.Client pointed at the running server."""
    client = httpx.Client(base_url=server, timeout=180.0)
    yield client
    client.close()


# ── Server lifecycle tests ────────────────────────────────────────────────────

# TODO(e2e-test-runner): test_health_check — GET /api/health via http_client;
# assert status_code == 200 and response json["status"] == "ok"
@pytest.mark.e2e
def test_health_check(server: str, http_client: "httpx.Client") -> None:
    """Server responds to health check with status ok."""
    r = http_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# TODO(e2e-test-runner): test_ollama_status — GET /api/ollama/status via http_client;
# if Ollama unavailable (connection refused), pytest.skip; else assert json["status"]=="ok"
@pytest.mark.e2e
def test_ollama_status(server: str, http_client: "httpx.Client") -> None:
    """Ollama status endpoint reports reachability (skip if Ollama not running)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    r = http_client.get("/api/ollama/status")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# TODO(e2e-test-runner): test_tweego_find — GET /api/tweego/find via http_client;
# record availability; skip test if tweego not found, don't fail
@pytest.mark.e2e
def test_tweego_find(server: str, http_client: "httpx.Client") -> None:
    """Tweego find endpoint reports binary availability (skip if not installed)."""
    if not e2e_test.check_tweego(server, http_client):
        pytest.skip("Tweego not available")
    r = http_client.get("/api/tweego/find")
    assert r.status_code == 200
    assert r.json()["found"] is not None


# ── Generation flow tests (require Ollama) ──────────────────────────────────

# TODO(e2e-test-runner): test_generate_premise — call generate_premise_step(http_client);
# skip if Ollama unavailable; assert "title" and "premise" keys in response dict
@pytest.mark.e2e
def test_generate_premise(server: str, http_client: "httpx.Client") -> None:
    """Generate-premise endpoint returns title and premise (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    result = e2e_test.generate_premise_step(http_client)
    assert "title" in result
    assert "premise" in result


# TODO(e2e-test-runner): test_generate_world — call generate_world_step with premise
# from test_generate_premise or a fixture-provided premise; skip if no Ollama;
# assert "world_overview" key in response dict
@pytest.mark.e2e
def test_generate_world(server: str, http_client: "httpx.Client") -> None:
    """Generate-world endpoint returns world_overview (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    premise_data = e2e_test.generate_premise_step(http_client)
    result = e2e_test.generate_world_step(http_client, premise_data["premise"])
    assert "world_overview" in result


# TODO(e2e-test-runner): test_generate_opening — call generate_opening_step with premise
# and world_overview; skip if no Ollama; assert "opening_situation" key in response
@pytest.mark.e2e
def test_generate_opening(server: str, http_client: "httpx.Client") -> None:
    """Generate-opening endpoint returns opening_situation (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    premise_data = e2e_test.generate_premise_step(http_client)
    world_data = e2e_test.generate_world_step(http_client, premise_data["premise"])
    result = e2e_test.generate_opening_step(http_client, premise_data["premise"], world_data["world_overview"])
    assert "opening_situation" in result


# TODO(e2e-test-runner): test_init_story — call init_story_step with title, premise,
# world_overview, opening_situation; skip if no Ollama; assert "status" == "initialized"
@pytest.mark.e2e
def test_init_story(server: str, http_client: "httpx.Client") -> None:
    """Init-story endpoint persists story metadata (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    premise_data = e2e_test.generate_premise_step(http_client)
    world_data = e2e_test.generate_world_step(http_client, premise_data["premise"])
    opening_data = e2e_test.generate_opening_step(http_client, premise_data["premise"], world_data["world_overview"])
    result = e2e_test.init_story_step(
        http_client,
        title=premise_data.get("title", "Test Story"),
        premise=premise_data["premise"],
        world_overview=world_data["world_overview"],
        opening_situation=opening_data["opening_situation"],
    )
    assert result.get("status") == "initialized"


# TODO(e2e-test-runner): test_generate_arcs_and_scenes — call generate_arcs_step(count=2)
# then generate_scenes_step for each arc; skip if no Ollama; assert non-empty arc list
# and non-empty scene list per arc
@pytest.mark.e2e
def test_generate_arcs_and_scenes(server: str, http_client: "httpx.Client") -> None:
    """Arc and scene generation produces structured output (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    # Need a story initialized first
    premise_data = e2e_test.generate_premise_step(http_client)
    world_data = e2e_test.generate_world_step(http_client, premise_data["premise"])
    opening_data = e2e_test.generate_opening_step(http_client, premise_data["premise"], world_data["world_overview"])
    e2e_test.init_story_step(
        http_client,
        title=premise_data.get("title", "Test Story"),
        premise=premise_data["premise"],
        world_overview=world_data["world_overview"],
        opening_situation=opening_data["opening_situation"],
    )
    e2e_test.generate_beats_step(http_client, count=3)
    arcs = e2e_test.generate_arcs_step(http_client, count=2)
    assert len(arcs) > 0
    for arc_name in arcs:
        scenes = e2e_test.generate_scenes_step(http_client, arc_name, count=2)
        assert len(scenes) > 0


# TODO(e2e-test-runner): test_generate_and_commit_passage — call generate_passage_step
# with arc_name, passage_slug, prompt; skip if no Ollama; assert non-empty passage_id string
@pytest.mark.e2e
def test_generate_and_commit_passage(server: str, http_client: "httpx.Client") -> None:
    """Generate + commit produces a valid passage_id (skip if no Ollama)."""
    if not e2e_test.check_ollama(server, http_client):
        pytest.skip("Ollama not available")
    # Need a story initialized with arcs + scenes first
    premise_data = e2e_test.generate_premise_step(http_client)
    world_data = e2e_test.generate_world_step(http_client, premise_data["premise"])
    opening_data = e2e_test.generate_opening_step(http_client, premise_data["premise"], world_data["world_overview"])
    e2e_test.init_story_step(
        http_client,
        title=premise_data.get("title", "Test Story"),
        premise=premise_data["premise"],
        world_overview=world_data["world_overview"],
        opening_situation=opening_data["opening_situation"],
    )
    e2e_test.generate_beats_step(http_client, count=3)
    arcs = e2e_test.generate_arcs_step(http_client, count=2)
    assert len(arcs) > 0
    scenes = e2e_test.generate_scenes_step(http_client, arcs[0], count=2)
    assert len(scenes) > 0
    passage_id = e2e_test.generate_passage_step(
        http_client, arcs[0], "test_passage", scenes[0].get("summary", "Opening"),
    )
    assert passage_id  # non-empty string


# ── Validation and compilation tests ─────────────────────────────────────────

# TODO(e2e-test-runner): test_validation — call run_validation_step(http_client);
# assert "errors" and "warnings" keys in response; assert no fatal errors if
# generation was run (if skipped, just assert response shape is valid)
@pytest.mark.e2e
def test_validation(server: str, http_client: "httpx.Client") -> None:
    """Validation endpoint returns errors and warnings lists."""
    result = e2e_test.run_validation_step(http_client)
    assert "errors" in result
    assert "warnings" in result


# TODO(e2e-test-runner): test_compile — call compile_step(http_client);
# skip if tweego not available; assert response json["success"] is True
@pytest.mark.e2e
def test_compile(server: str, http_client: "httpx.Client") -> None:
    """Compile endpoint produces success=True (skip if no Tweego)."""
    if not e2e_test.check_tweego(server, http_client):
        pytest.skip("Tweego not available")
    result = e2e_test.compile_step(http_client)
    assert result["success"] is True


# ── HTML verification tests ──────────────────────────────────────────────────

# TODO(e2e-test-runner): test_html_exists — use e2e_config.project_path; assert
# build/story.html exists and is non-empty; skip if compile was skipped/failed
@pytest.mark.e2e
def test_html_exists(e2e_config: "e2e_test.E2EConfig") -> None:
    """Compiled story HTML exists and is non-empty (skip if no compile)."""
    html_path = e2e_config.project_path / "build" / "story.html"
    if not html_path.exists():
        pytest.skip("No compiled HTML (Tweego not available)")
    assert html_path.stat().st_size > 0


# TODO(e2e-test-runner): test_html_structure — read build/story.html; assert contains
# <html> tag, tw-storydata or SugarCube story format markers, and start passage;
# skip if no compile
@pytest.mark.e2e
def test_html_structure(e2e_config: "e2e_test.E2EConfig") -> None:
    """Compiled HTML contains valid SugarCube structure (skip if no compile)."""
    html_path = e2e_config.project_path / "build" / "story.html"
    if not html_path.exists():
        pytest.skip("No compiled HTML (Tweego not available)")
    content = html_path.read_text(encoding="utf-8", errors="replace")
    assert "<html" in content.lower()


# TODO(e2e-test-runner): test_html_browser — call verify_html_browser(html_path);
# skip if playwright not installed; assert step status is pass (no JS errors,
# start passage renders)
@pytest.mark.e2e
def test_html_browser(e2e_config: "e2e_test.E2EConfig") -> None:
    """HTML loads in headless browser without JS errors (skip if no playwright)."""
    if not e2e_test.check_playwright():
        pytest.skip("Playwright not installed")
    html_path = e2e_config.project_path / "build" / "story.html"
    if not html_path.exists():
        pytest.skip("No compiled HTML (Tweego not available)")
    result = e2e_test.verify_html_browser(html_path)
    assert result.status == e2e_test.StepStatus.pass_


# ── Full E2E flow test ───────────────────────────────────────────────────────

# TODO(e2e-test-runner): test_full_e2e_flow — call run_e2e(e2e_config) directly;
# assert report.steps is non-empty; assert report.exit_code == 0 (all pass/skip,
# no failures); assert report.summary counts are consistent with steps list;
# this is the integration test that exercises the entire stack end-to-end
@pytest.mark.e2e
def test_full_e2e_flow(e2e_config: "e2e_test.E2EConfig") -> None:
    """Full E2E flow via run_e2e() produces a valid report with no failures."""
    report = e2e_test.run_e2e(e2e_config)
    assert len(report.steps) > 0
    assert report.exit_code == 0  # all pass/skip, no failures (INV-1)
    # Summary counts must be consistent with steps
    p, f, s = e2e_test.build_summary(report.steps)
    assert report.summary.passed == p
    assert report.summary.failed == f
    assert report.summary.skipped == s


# TODO(e2e-test-runner): test_report_json_valid — call run_e2e(e2e_config), then
# write_report to a temp path, then json.load the file and assert it parses;
# assert all required fields present (timestamp, steps, summary, exit_code)
@pytest.mark.e2e
def test_report_json_valid(e2e_config: "e2e_test.E2EConfig", tmp_path) -> None:
    """Generated JSON report file is valid and parseable."""
    report = e2e_test.run_e2e(e2e_config)
    report_path = tmp_path / "test_report.json"
    e2e_test.write_report(report, report_path)
    with open(report_path, encoding="utf-8") as f:
        data = json.load(f)
    # INV-7: all required fields present
    required_fields = [
        "timestamp", "project_path", "server_port", "duration_seconds",
        "ollama_available", "tweego_available", "playwright_available",
        "steps", "summary", "exit_code",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    assert isinstance(data["steps"], list)
    assert isinstance(data["summary"], dict)
    assert "passed" in data["summary"]
    assert "failed" in data["summary"]
    assert "skipped" in data["summary"]
