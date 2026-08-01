#!/usr/bin/env python3
"""Run and publish an Ollama benchmark through a restricted SSH command.

This program is intended to be installed as a root-owned OpenSSH forced
command.  It deliberately accepts no command-line options.  All sensitive
settings, including Ollama model tags, come from a root-readable JSON file.
Only a fail-closed, scrubbed JSON result is copied into the Git repository.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    DEFAULT_CONFIG = Path("C:/ProgramData/HermesBenchmark/config.json")
    DEFAULT_STATE_DIR = Path("C:/ProgramData/HermesBenchmark/state")
else:
    DEFAULT_CONFIG = Path("/etc/hermes-benchmark/config.json")
    DEFAULT_STATE_DIR = Path("/var/lib/hermes-benchmark")


class PublishError(RuntimeError):
    """A safe-to-log failure that must not reveal details to the SSH caller."""


COMMAND_TIMEOUT_SECONDS = 120


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise PublishError("configuration root must be an object")
    required = ("repo_path", "models")
    missing = [key for key in required if key not in config]
    if missing:
        raise PublishError(f"missing configuration keys: {', '.join(missing)}")
    models = config["models"]
    if not isinstance(models, list) or not models or not all(
        isinstance(model, str) and model.strip() for model in models
    ):
        raise PublishError("models must be a non-empty array of strings")
    return config


def _reexec_if_needed(config: dict[str, Any]) -> None:
    """Switch to the configured project interpreter without exposing models."""
    configured = config.get("python_executable")
    if not configured:
        return
    interpreter = Path(str(configured)).resolve()
    if Path(sys.executable).resolve() == interpreter:
        return
    if not interpreter.is_file():
        raise PublishError("configured Python interpreter does not exist")
    clean_env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONINSPECT", "PYTHONSTARTUP"):
        clean_env.pop(key, None)
    os.execve(
        interpreter,
        [str(interpreter), str(Path(__file__).resolve())],
        clean_env,
    )


@contextlib.contextmanager
def _exclusive_lock(path: Path):
    """Hold a non-blocking one-byte lock on Linux/macOS or Windows."""
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BlockingIOError from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _ollama_model_names(base_url: str, timeout: int) -> list[str]:
    """Return installed model tags without writing them to stdout or stderr."""
    endpoint = f"{base_url.rstrip('/')}/api/tags"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except Exception as exc:
        raise PublishError("could not obtain the private Ollama model inventory") from exc

    rows = payload.get("models", []) if isinstance(payload, dict) else []
    names = [
        row.get("name", "")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    ]
    if not names:
        raise PublishError("Ollama returned an empty model inventory")
    return names


def _redaction_terms(installed: list[str], selected: list[str]) -> list[str]:
    """Build a conservative, longest-first list of model-identifying terms."""
    terms: set[str] = set()
    for name in [*installed, *selected]:
        value = name.strip()
        if not value:
            continue
        terms.add(value)
        # Also hide the repository portion of tags such as "family:latest".
        family = value.rsplit(":", 1)[0]
        if len(family) >= 3:
            terms.add(family)
    return sorted(terms, key=lambda item: (-len(item), item.casefold()))


def _scrub_string(value: str, terms: list[str]) -> str:
    for term in terms:
        value = re.sub(re.escape(term), "[REDACTED_MODEL]", value, flags=re.IGNORECASE)
    return value


def scrub_json(value: Any, terms: list[str]) -> Any:
    """Recursively redact model terms from JSON values and object keys."""
    if isinstance(value, str):
        return _scrub_string(value, terms)
    if isinstance(value, list):
        return [scrub_json(item, terms) for item in value]
    if isinstance(value, dict):
        return {
            _scrub_string(str(key), terms): scrub_json(item, terms)
            for key, item in value.items()
        }
    return value


def prepare_public_results(value: Any, terms: list[str]) -> Any:
    """Preserve anonymous test identity, then recursively scrub all tags."""
    if isinstance(value, list):
        for record in value:
            if not isinstance(record, dict):
                continue
            alias = record.get("model_alias")
            test_id = record.get("test_id")
            if (
                isinstance(alias, str)
                and alias.startswith("Model_")
                and isinstance(test_id, str)
            ):
                components = test_id.rsplit(":", 3)
                if len(components) == 4:
                    record["test_id"] = ":".join((alias, *components[-3:]))
    return scrub_json(value, terms)


def leaked_terms(text: str, terms: list[str]) -> list[str]:
    folded = text.casefold()
    return [term for term in terms if term.casefold() in folded]


def _run_logged(
    command: list[str],
    *,
    cwd: Path,
    log_handle: Any,
    env: dict[str, str] | None = None,
) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PublishError("command timed out") from exc
    if completed.returncode:
        raise PublishError(f"command failed with exit status {completed.returncode}")


def _run_captured(command: list[str], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PublishError("command timed out") from exc
    if completed.returncode:
        raise PublishError(f"command failed with exit status {completed.returncode}")
    return completed.stdout.strip()


def _update_checkout(
    config: dict[str, Any],
    *,
    repo: Path,
    git: str,
    log_handle: Any,
) -> None:
    """Fast-forward the clean, configured branch before importing repo code."""
    dirty = _run_captured([git, "status", "--porcelain"], cwd=repo)
    if dirty:
        raise PublishError("benchmark checkout is not clean")

    branch = str(config.get("git_branch", "main"))
    current_branch = _run_captured(
        [git, "branch", "--show-current"],
        cwd=repo,
    )
    if current_branch != branch:
        raise PublishError("benchmark checkout is on the wrong branch")

    remote = str(config.get("git_remote", "origin"))
    _run_logged(
        [git, "pull", "--ff-only", remote, branch],
        cwd=repo,
        log_handle=log_handle,
        env=_git_environment(),
    )
    if not bool(config.get("require_signed_commit", True)):
        return

    trusted_signers = config.get("trusted_commit_signers", [])
    if not isinstance(trusted_signers, list) or not trusted_signers:
        raise PublishError("no trusted commit signers are configured")

    if bool(config.get("allow_unsigned_candidate_commits", False)):
        trusted_ref = str(config.get("trusted_code_commit", "")).strip()
        if not trusted_ref:
            raise PublishError("trusted_code_commit is required")
        trusted_commit = _run_captured(
            [git, "rev-parse", "--verify", f"{trusted_ref}^{{commit}}"],
            cwd=repo,
        )
        _verify_trusted_commit(
            trusted_commit,
            trusted_signers=trusted_signers,
            repo=repo,
            git=git,
            log_handle=log_handle,
        )
        _run_logged(
            [git, "merge-base", "--is-ancestor", trusted_commit, "HEAD"],
            cwd=repo,
            log_handle=log_handle,
        )
        changed_paths = _run_captured(
            [git, "diff", "--name-only", trusted_commit, "HEAD"],
            cwd=repo,
        ).splitlines()
        allowed_paths = config.get(
            "candidate_paths",
            [
                "model_benchmark/prompt_overrides.json",
                "model_benchmark/ingestion_overrides.json",
                "benchmark_anon/results_anonymized.json",
                "benchmark_optimization/**",
            ],
        )
        if not isinstance(allowed_paths, list) or not allowed_paths:
            raise PublishError("candidate_paths must be a non-empty array")
        rejected = [
            path
            for path in changed_paths
            if not _candidate_path_allowed(path, allowed_paths)
        ]
        if rejected:
            raise PublishError("candidate commits changed a protected path")
        _validate_candidate_files(repo, changed_paths)
        return

    _verify_trusted_commit(
        "HEAD",
        trusted_signers=trusted_signers,
        repo=repo,
        git=git,
        log_handle=log_handle,
    )


def _candidate_path_allowed(path: str, patterns: list[Any]) -> bool:
    normalized = path.replace("\\", "/")
    for raw_pattern in patterns:
        pattern = str(raw_pattern).replace("\\", "/")
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return True
        elif normalized == pattern:
            return True
    return False


def _validate_candidate_files(repo: Path, changed_paths: list[str]) -> None:
    if len(changed_paths) > 100:
        raise PublishError("candidate commit changed too many files")
    candidate_tests = [
        name for name in changed_paths
        if name.replace("\\", "/").startswith(
            "benchmark_optimization/candidate_tests/"
        )
    ]
    if len(candidate_tests) > 20:
        raise PublishError("candidate commit contains too many test files")
    for relative_name in changed_paths:
        path = repo / relative_name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise PublishError("candidate path is not a regular file")
        normalized = relative_name.replace("\\", "/")
        limit = 20_000_000 if normalized == (
            "benchmark_anon/results_anonymized.json"
        ) else 262_144
        if normalized == "model_benchmark/prompt_overrides.json":
            limit = 40_000
        if normalized == "model_benchmark/ingestion_overrides.json":
            limit = 40_000
        if normalized.startswith("benchmark_optimization/candidate_tests/"):
            if path.suffix.casefold() != ".json":
                raise PublishError("candidate tests must be JSON files")
            limit = 32_768
        if path.stat().st_size > limit:
            raise PublishError("candidate file exceeds its size limit")


def _verify_trusted_commit(
    commit: str,
    *,
    trusted_signers: list[Any],
    repo: Path,
    git: str,
    log_handle: Any,
) -> None:
    _run_logged(
        [git, "verify-commit", commit],
        cwd=repo,
        log_handle=log_handle,
        env=_git_environment(),
    )
    signer = _run_captured(
        [git, "log", "-1", "--format=%GF", commit],
        cwd=repo,
    )
    allowed = {
        str(fingerprint).replace(" ", "").casefold()
        for fingerprint in trusted_signers
    }
    if not signer or signer.replace(" ", "").casefold() not in allowed:
        raise PublishError("commit signer is not trusted")


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    # The protected checkout owns its repository-scoped core.sshCommand,
    # including the deploy key and pinned known_hosts file. Environment
    # overrides take precedence over that setting, so remove them instead of
    # replacing the configured command with a generic SSH invocation.
    for variable in ("GIT_SSH", "GIT_SSH_COMMAND", "GIT_SSH_VARIANT"):
        environment.pop(variable, None)
    return environment


def _latest_anonymized_result(output_dir: Path) -> Path:
    candidates = list(output_dir.glob("*/results_anonymized.json"))
    if not candidates:
        raise PublishError("benchmark produced no anonymized result")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _safe_repo_target(repo: Path, relative_name: str) -> Path:
    if Path(relative_name).is_absolute():
        raise PublishError("publish_path must be relative to the repository")
    target = (repo / relative_name).resolve()
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise PublishError("publish_path escapes the repository") from exc
    return target


def _benchmark_args(config: dict[str, Any], output_dir: Path) -> list[str]:
    args = [
        "run",
        "--quiet",
        "--anonymize",
        "--force-rerun",
        "--output-dir",
        str(output_dir),
        "--base-url",
        str(config.get("ollama_base_url", "http://127.0.0.1:11434")),
        "--models",
        *config["models"],
    ]
    for flag, key in (
        ("--variants", "variants"),
        ("--directions", "directions"),
    ):
        values = config.get(key)
        if values:
            args.extend([flag, *map(str, values)])
    for flag, key in (
        ("--runs", "runs"),
        ("--timeout", "timeout"),
        ("--num-predict", "num_predict"),
        ("--temperature", "temperature"),
        ("--seed", "seed"),
    ):
        if key in config:
            args.extend([flag, str(config[key])])
    for config_dir in config.get("config_dirs", []):
        args.extend(["--config-dir", str(config_dir)])
    if bool(config.get("capability_tests", False)):
        args.append("--capability-tests")
        candidate_dir = config.get("candidate_test_dir")
        if candidate_dir:
            args.extend(["--candidate-test-dir", str(candidate_dir)])
    if bool(config.get("context_window_tests", False)):
        from model_benchmark.context_window_tests import validate_context_sizes
        context_sizes = validate_context_sizes(
            config.get(
                "context_window_sizes",
                [2048, 4096, 8192, 16384, 32768, 65536, 131072],
            )
        )
        args.append("--context-window-tests")
        args.extend(["--context-window-sizes", *map(str, context_sizes)])
    model_profiles = config.get("model_profiles")
    if model_profiles is not None:
        routing_path = output_dir / "ingestion-routing.private.json"
        with routing_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {"schema_version": 1, "model_profiles": model_profiles},
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
        os.chmod(routing_path, 0o600)
        args.extend(["--ingestion-routing", str(routing_path)])
    return args


def _write_private_progress(
    run_dir: Path,
    payload: dict[str, Any],
    *,
    log_handle: Any,
) -> None:
    """Atomically persist identity-free progress for PC-side inspection."""
    phase = str(payload.get("phase", "unknown"))
    if phase not in {
        "starting", "matrix", "capability", "context_window", "finalizing"
    }:
        phase = "unknown"
    progress: dict[str, Any] = {
        "schema_version": 1,
        "phase": phase,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for key in (
        "completed",
        "total",
        "pass_count",
        "fail_count",
        "error_count",
        "timeout_count",
    ):
        if key in payload:
            progress[key] = max(0, int(payload[key]))
    for key in ("percent", "elapsed_seconds", "eta_seconds"):
        if key in payload:
            progress[key] = float(payload[key])
    current_model_alias = payload.get("current_model_alias")
    if (
        isinstance(current_model_alias, str)
        and re.fullmatch(r"Model_[A-Z]+", current_model_alias)
    ):
        progress["current_model_alias"] = current_model_alias
        progress["current_model_number"] = max(
            1,
            int(payload.get("current_model_number", 1)),
        )
        progress["model_count"] = max(
            progress["current_model_number"],
            int(payload.get("model_count", 1)),
        )
    if "total_run_seconds" in payload:
        progress["total_run_seconds"] = max(
            0.0,
            float(payload["total_run_seconds"]),
        )

    target = run_dir / "progress.json"
    fd, temporary_name = tempfile.mkstemp(
        prefix=".progress-",
        suffix=".json",
        dir=run_dir,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(progress, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    log_handle.write(
        "progress "
        f"phase={progress['phase']} "
        f"completed={progress.get('completed', 0)} "
        f"total={progress.get('total', 0)} "
        f"model={progress.get('current_model_alias', '-')} "
        f"model_number={progress.get('current_model_number', 0)}/"
        f"{progress.get('model_count', 0)} "
        f"elapsed_seconds={progress.get('elapsed_seconds', 0.0):.3f} "
        f"updated_at={progress['updated_at']}\n"
    )
    log_handle.flush()


def _publish(config: dict[str, Any], log_handle: Any) -> bool:
    repo = Path(config["repo_path"]).resolve()
    if not (repo / ".git").exists():
        raise PublishError("repo_path is not a Git working tree")
    git = str(config.get("git_executable", "git"))
    _update_checkout(config, repo=repo, git=git, log_handle=log_handle)
    # Resolve benchmark modules from the verified checkout, not from an older
    # editable-install path or the publisher's installation directory.
    sys.path.insert(0, str(repo))
    from harness.ingestion_profiles import (
        IngestionEnvelopeError,
        load_ingestion_envelopes,
    )
    try:
        load_ingestion_envelopes()
    except IngestionEnvelopeError as exc:
        raise PublishError("invalid ingestion envelope configuration") from exc

    base_url = str(config.get("ollama_base_url", "http://127.0.0.1:11434"))
    inventory_timeout = int(config.get("inventory_timeout", 10))
    installed = _ollama_model_names(base_url, inventory_timeout)
    selected = [str(model) for model in config["models"]]
    missing = [model for model in selected if model not in installed]
    if missing:
        raise PublishError("one or more configured models are not installed")
    model_profiles = config.get("model_profiles")
    if model_profiles is not None:
        if not isinstance(model_profiles, dict) or set(model_profiles) != set(selected):
            raise PublishError("model_profiles must exactly match configured models")
        from harness.ingestion_profiles import PROFILE_IDS
        if not all(
            isinstance(profile, str) and profile in PROFILE_IDS
            for profile in model_profiles.values()
        ):
            raise PublishError("model_profiles contains an unknown profile")
    terms = _redaction_terms(installed, selected)
    from model_benchmark.anonymization import _model_alias
    sorted_models = sorted(set(selected))
    progress_aliases = {
        model: (_model_alias(index), index + 1)
        for index, model in enumerate(sorted_models)
    }

    state_dir = Path(config.get("state_dir", DEFAULT_STATE_DIR)).resolve()
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=state_dir))
    os.chmod(run_dir, 0o700)

    try:
        _write_private_progress(
            run_dir,
            {"phase": "starting", "completed": 0, "total": 0},
            log_handle=log_handle,
        )

        def record_progress(payload: dict[str, Any]) -> None:
            safe_payload = dict(payload)
            current_model = safe_payload.pop("current_model", None)
            model_progress = progress_aliases.get(current_model)
            if model_progress is not None:
                alias, number = model_progress
                safe_payload["current_model_alias"] = alias
                safe_payload["current_model_number"] = number
                safe_payload["model_count"] = len(sorted_models)
            _write_private_progress(
                run_dir,
                safe_payload,
                log_handle=log_handle,
            )

        # Import and invoke in this process: model tags never enter argv or the
        # environment, where another unprivileged process might inspect them.
        from model_benchmark.cli import main as benchmark_main

        previous_cwd = Path.cwd()
        benchmark_started_clock = time.monotonic()
        try:
            os.chdir(repo)
            with contextlib.redirect_stdout(log_handle), contextlib.redirect_stderr(log_handle):
                exit_code = benchmark_main(
                    _benchmark_args(config, run_dir),
                    progress_callback=record_progress,
                )
        finally:
            os.chdir(previous_cwd)
        if exit_code:
            raise PublishError(f"benchmark failed with exit status {exit_code}")

        benchmark_total_seconds = time.monotonic() - benchmark_started_clock
        log_handle.write(
            f"benchmark_total_runtime_seconds={benchmark_total_seconds:.3f}\n"
        )
        log_handle.flush()

        _write_private_progress(
            run_dir,
            {
                "phase": "finalizing",
                "completed": 1,
                "total": 1,
                "percent": 100.0,
                "elapsed_seconds": benchmark_total_seconds,
                "eta_seconds": 0.0,
                "total_run_seconds": benchmark_total_seconds,
            },
            log_handle=log_handle,
        )
        source = _latest_anonymized_result(run_dir)
        with source.open("r", encoding="utf-8") as handle:
            public_data = prepare_public_results(json.load(handle), terms)
        rendered = json.dumps(public_data, indent=2, ensure_ascii=False) + "\n"
        if leaked_terms(rendered, terms):
            raise PublishError("model identity remained after output scrubbing")

        target = _safe_repo_target(
            repo,
            str(config.get("publish_path", "benchmark_anon/results_anonymized.json")),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

        relative_target = str(target.relative_to(repo))
        status = _run_captured(
            [git, "status", "--porcelain", "--", relative_target],
            cwd=repo,
        )
        changed = bool(status.strip())
        if changed:
            _run_logged(
                [git, "add", "--force", "--", relative_target],
                cwd=repo,
                log_handle=log_handle,
            )
            message = str(
                config.get("commit_message", "Publish anonymized benchmark results")
            )
            _run_logged(
                [git, "commit", "--only", "-m", message, "--", relative_target],
                cwd=repo,
                log_handle=log_handle,
            )
        remote = str(config.get("git_remote", "origin"))
        branch = str(config.get("git_branch", "main"))
        _run_logged(
            [git, "push", remote, f"HEAD:{branch}"],
            cwd=repo,
            log_handle=log_handle,
            env=_git_environment(),
        )
        return changed
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def main() -> int:
    if os.name != "nt" and os.geteuid() != 0:
        print("Benchmark request failed; the publisher must run as root.")
        return 1
    # An SSH client must not be able to redirect this privileged process to an
    # attacker-controlled configuration through a supplied environment value.
    config_path = DEFAULT_CONFIG
    state_dir = DEFAULT_STATE_DIR
    try:
        config = _load_config(config_path)
        _reexec_if_needed(config)
        state_dir = Path(config.get("state_dir", DEFAULT_STATE_DIR)).resolve()
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(state_dir, 0o700)
    except Exception:
        print("Benchmark request failed; ask the PC administrator to check the private log.")
        return 1

    lock_path = state_dir / "run.lock"
    log_path = state_dir / "last-run.log"
    try:
        with _exclusive_lock(lock_path):
            with log_path.open("w", encoding="utf-8") as log_handle:
                os.chmod(log_path, 0o600)
                log_handle.write(f"started={datetime.now(timezone.utc).isoformat()}\n")
                log_handle.flush()
                try:
                    pushed = _publish(config, log_handle)
                except Exception:
                    traceback.print_exc(file=log_handle)
                    print(
                        "Benchmark request failed; ask the PC administrator "
                        "to check the private log."
                    )
                    return 1
    except BlockingIOError:
        print("A benchmark is already running.")
        return 75
    except Exception:
        print("Benchmark request failed; ask the PC administrator to check the private log.")
        return 1

    print("Benchmark completed and anonymized results were pushed." if pushed else
          "Benchmark completed; anonymized results were unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
