import io

import pytest
import scripts.hermes_benchmark_publish as publisher

from scripts.hermes_benchmark_publish import (
    _exclusive_lock,
    _redaction_terms,
    leaked_terms,
    prepare_public_results,
    scrub_json,
)


def test_scrubs_model_names_from_values_and_keys():
    terms = _redaction_terms(["family:latest", "other/model:7b"], ["family:latest"])
    original = {
        "test_id": "family:latest:compact:A:1",
        "family:latest": ["OTHER/MODEL:7B", {"model": "family"}],
    }

    scrubbed = scrub_json(original, terms)
    rendered = str(scrubbed)

    assert not leaked_terms(rendered, terms)
    assert "[REDACTED_MODEL]" in rendered


def test_redaction_terms_are_longest_first_and_include_family():
    terms = _redaction_terms(["registry/team/model:latest"], [])

    assert terms[0] == "registry/team/model:latest"
    assert "registry/team/model" in terms


def test_exclusive_lock_rejects_concurrent_run(tmp_path):
    lock_path = tmp_path / "run.lock"

    with _exclusive_lock(lock_path):
        with pytest.raises(BlockingIOError):
            with _exclusive_lock(lock_path):
                pass


def test_public_results_use_alias_in_test_id():
    records = [
        {
            "test_id": "secret/model:latest:compact:A:1",
            "model_alias": "Model_A",
        }
    ]
    terms = _redaction_terms(["secret/model:latest"], [])

    scrubbed = prepare_public_results(records, terms)

    assert scrubbed[0]["test_id"] == "Model_A:compact:A:1"
    assert not leaked_terms(str(scrubbed), terms)


def test_update_checkout_pulls_configured_branch(monkeypatch, tmp_path):
    captured = iter(("", "release"))
    logged_commands = []
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: next(captured),
    )
    monkeypatch.setattr(
        publisher,
        "_run_logged",
        lambda command, **kwargs: logged_commands.append(command),
    )

    publisher._update_checkout(
        {
            "git_remote": "upstream",
            "git_branch": "release",
            "require_signed_commit": False,
        },
        repo=tmp_path,
        git="git",
        log_handle=io.StringIO(),
    )

    assert logged_commands == [
        ["git", "pull", "--ff-only", "upstream", "release"]
    ]


def test_update_checkout_rejects_dirty_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: " M benchmark.py",
    )

    with pytest.raises(publisher.PublishError, match="not clean"):
        publisher._update_checkout(
            {},
            repo=tmp_path,
            git="git",
            log_handle=io.StringIO(),
        )


def test_git_environment_uses_protected_repository_ssh_config(monkeypatch):
    monkeypatch.setenv("GIT_SSH", "untrusted-ssh")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -o StrictHostKeyChecking=no")
    monkeypatch.setenv("GIT_SSH_VARIANT", "plink")

    environment = publisher._git_environment()

    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_SSH" not in environment
    assert "GIT_SSH_COMMAND" not in environment
    assert "GIT_SSH_VARIANT" not in environment


@pytest.mark.parametrize(
    ("runner", "kwargs"),
    [
        (publisher._run_logged, {"log_handle": io.StringIO()}),
        (publisher._run_captured, {}),
    ],
)
def test_git_helpers_fail_closed_on_timeout(monkeypatch, tmp_path, runner, kwargs):
    def timeout(*args, **call_kwargs):
        raise publisher.subprocess.TimeoutExpired(args[0], call_kwargs["timeout"])

    monkeypatch.setattr(publisher.subprocess, "run", timeout)

    with pytest.raises(publisher.PublishError, match="timed out"):
        runner(["git", "status"], cwd=tmp_path, **kwargs)


def test_private_progress_file_excludes_identity_fields(tmp_path):
    log = io.StringIO()

    publisher._write_private_progress(
        tmp_path,
        {
            "phase": "matrix",
            "completed": 7,
            "total": 20,
            "percent": 35.0,
            "model_alias": "private-model",
            "current_test": "private-model:compact:A:1",
            "current_model_alias": "not-an-anonymous-alias",
        },
        log_handle=log,
    )

    progress = publisher.json.loads(
        (tmp_path / "progress.json").read_text(encoding="utf-8")
    )
    rendered = publisher.json.dumps(progress)

    assert progress["phase"] == "matrix"
    assert progress["completed"] == 7
    assert progress["total"] == 20
    assert "model_alias" not in progress
    assert "current_test" not in progress
    assert "private-model" not in rendered
    assert "private-model" not in log.getvalue()


def test_private_progress_file_includes_safe_model_alias_and_runtime(tmp_path):
    log = io.StringIO()

    publisher._write_private_progress(
        tmp_path,
        {
            "phase": "finalizing",
            "completed": 1,
            "total": 1,
            "percent": 100.0,
            "elapsed_seconds": 123.5,
            "eta_seconds": 0.0,
            "current_model_alias": "Model_AA",
            "current_model_number": 27,
            "model_count": 30,
            "total_run_seconds": 123.5,
        },
        log_handle=log,
    )

    progress = publisher.json.loads(
        (tmp_path / "progress.json").read_text(encoding="utf-8")
    )
    assert progress["current_model_alias"] == "Model_AA"
    assert progress["current_model_number"] == 27
    assert progress["model_count"] == 30
    assert progress["total_run_seconds"] == 123.5
    assert "model=Model_AA" in log.getvalue()


def test_private_progress_accepts_context_window_phase(tmp_path):
    publisher._write_private_progress(
        tmp_path,
        {"phase": "context_window", "completed": 2, "total": 5},
        log_handle=io.StringIO(),
    )

    progress = publisher.json.loads(
        (tmp_path / "progress.json").read_text(encoding="utf-8")
    )
    assert progress["phase"] == "context_window"


def test_public_progress_contains_only_aggregate_timing(tmp_path):
    path = tmp_path / "public-progress.json"
    publisher._write_public_progress(
        path,
        {
            "phase": "capability",
            "completed": 4,
            "total": 20,
            "overall_completed": 36,
            "overall_total": 100,
            "overall_percent": 36.0,
            "overall_elapsed_seconds": 900.0,
            "overall_eta_seconds": 1600.0,
            "estimate_basis": "previous_successful_run",
            "current_model": "private-model-name",
            "current_model_alias": "Model_A",
            "current_test": "private-test-id",
        },
    )

    progress = publisher.json.loads(path.read_text(encoding="utf-8"))
    rendered = publisher.json.dumps(progress)
    assert progress["overall_completed"] == 36
    assert progress["overall_total"] == 100
    assert progress["overall_eta_seconds"] == 1600.0
    assert progress["estimate_basis"] == "previous_successful_run"
    assert "private-model-name" not in rendered
    assert "Model_A" not in rendered
    assert "private-test-id" not in rendered


def test_runtime_estimate_uses_matching_previous_workload(tmp_path):
    path = tmp_path / "runtime-history.json"
    workload = {
        "matrix_total": 32,
        "capability_total": 33,
        "context_window_total": 0,
    }
    publisher._record_runtime_sample(path, workload, 1200.0)

    assert publisher._read_runtime_estimate(path, workload) == 1200.0
    assert publisher._read_runtime_estimate(
        path,
        {**workload, "capability_total": 34},
    ) is None


def test_update_checkout_requires_allowlisted_signer(monkeypatch, tmp_path):
    captured = iter(("", "main", "AA BB CC"))
    logged_commands = []
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: next(captured),
    )
    monkeypatch.setattr(
        publisher,
        "_run_logged",
        lambda command, **kwargs: logged_commands.append(command),
    )

    publisher._update_checkout(
        {
            "git_branch": "main",
            "require_signed_commit": True,
            "trusted_commit_signers": ["aabbcc"],
        },
        repo=tmp_path,
        git="git",
        log_handle=io.StringIO(),
    )

    assert ["git", "verify-commit", "HEAD"] in logged_commands


def test_update_checkout_rejects_untrusted_signer(monkeypatch, tmp_path):
    captured = iter(("", "main", "BADFINGERPRINT"))
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: next(captured),
    )
    monkeypatch.setattr(publisher, "_run_logged", lambda command, **kwargs: None)

    with pytest.raises(publisher.PublishError, match="not trusted"):
        publisher._update_checkout(
            {
                "git_branch": "main",
                "require_signed_commit": True,
                "trusted_commit_signers": ["TRUSTEDFINGERPRINT"],
            },
            repo=tmp_path,
            git="git",
            log_handle=io.StringIO(),
        )


def test_candidate_mode_allows_only_data_paths(monkeypatch, tmp_path):
    captured = iter(
        (
            "",
            "main",
            "abc123",
            "AA BB CC",
            "\n".join(
                (
                    "model_benchmark/prompt_overrides.json",
                    "benchmark_optimization/iteration-01.md",
                    "benchmark_anon/results_anonymized.json",
                )
            ),
        )
    )
    logged_commands = []
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: next(captured),
    )
    monkeypatch.setattr(
        publisher,
        "_run_logged",
        lambda command, **kwargs: logged_commands.append(command),
    )

    publisher._update_checkout(
        {
            "git_branch": "main",
            "require_signed_commit": True,
            "trusted_commit_signers": ["aabbcc"],
            "allow_unsigned_candidate_commits": True,
            "trusted_code_commit": "abc123",
        },
        repo=tmp_path,
        git="git",
        log_handle=io.StringIO(),
    )

    assert ["git", "merge-base", "--is-ancestor", "abc123", "HEAD"] in logged_commands


def test_candidate_mode_rejects_python_change(monkeypatch, tmp_path):
    captured = iter(("", "main", "abc123", "AABBCC", "harness/prompts.py"))
    monkeypatch.setattr(
        publisher,
        "_run_captured",
        lambda command, cwd: next(captured),
    )
    monkeypatch.setattr(publisher, "_run_logged", lambda command, **kwargs: None)

    with pytest.raises(publisher.PublishError, match="protected path"):
        publisher._update_checkout(
            {
                "git_branch": "main",
                "require_signed_commit": True,
                "trusted_commit_signers": ["AABBCC"],
                "allow_unsigned_candidate_commits": True,
                "trusted_code_commit": "abc123",
            },
            repo=tmp_path,
            git="git",
            log_handle=io.StringIO(),
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("model_benchmark/prompt_overrides.json", True),
        ("model_benchmark/ingestion_overrides.json", True),
        ("benchmark_optimization/iteration-01.md", True),
        ("benchmark_optimization", True),
        ("model_benchmark/scoring.py", False),
        ("benchmark_optimization-evil/file", False),
    ],
)
def test_candidate_path_matching(path, expected):
    patterns = [
        "model_benchmark/prompt_overrides.json",
        "model_benchmark/ingestion_overrides.json",
        "benchmark_optimization/**",
    ]

    assert publisher._candidate_path_allowed(path, patterns) is expected


def test_candidate_files_reject_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    candidate = tmp_path / "prompt_overrides.json"
    try:
        candidate.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(publisher.PublishError, match="regular file"):
        publisher._validate_candidate_files(
            tmp_path,
            ["prompt_overrides.json"],
        )


def test_candidate_files_reject_oversized_overlay(tmp_path):
    candidate = tmp_path / "model_benchmark" / "prompt_overrides.json"
    candidate.parent.mkdir()
    candidate.write_bytes(b"x" * 40_001)

    with pytest.raises(publisher.PublishError, match="size limit"):
        publisher._validate_candidate_files(
            tmp_path,
            ["model_benchmark/prompt_overrides.json"],
        )


def test_candidate_test_files_must_be_bounded_json(tmp_path):
    candidate = tmp_path / "benchmark_optimization" / "candidate_tests" / "probe.py"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("print('unsafe')", encoding="utf-8")

    with pytest.raises(publisher.PublishError, match="JSON"):
        publisher._validate_candidate_files(
            tmp_path,
            ["benchmark_optimization/candidate_tests/probe.py"],
        )


def test_benchmark_args_enable_capability_ladder(tmp_path):
    args = publisher._benchmark_args(
        {
            "models": ["private-model"],
            "capability_tests": True,
            "candidate_test_dir": "benchmark_optimization/candidate_tests",
        },
        tmp_path,
    )

    assert "--capability-tests" in args
    assert args[-2:] == [
        "--candidate-test-dir",
        "benchmark_optimization/candidate_tests",
    ]


def test_benchmark_args_forward_named_profile(tmp_path):
    args = publisher._benchmark_args(
        {"models": ["private-model"], "benchmark_profile": "canary"},
        tmp_path,
    )

    assert args[args.index("--profile") + 1] == "canary"

    with pytest.raises(ValueError, match="benchmark_profile"):
        publisher._benchmark_args(
            {"models": ["private-model"], "benchmark_profile": "unknown"},
            tmp_path,
        )


def test_benchmark_args_enable_bounded_context_window_ladder(tmp_path):
    args = publisher._benchmark_args(
        {
            "models": ["private-model"],
            "context_window_tests": True,
            "context_window_sizes": [2048, 4096, 8192],
        },
        tmp_path,
    )

    assert "--context-window-tests" in args
    start = args.index("--context-window-sizes")
    assert args[start + 1:start + 4] == ["2048", "4096", "8192"]

    with pytest.raises(ValueError, match="outside the signed ladder"):
        publisher._benchmark_args(
            {
                "models": ["private-model"],
                "context_window_tests": True,
                "context_window_sizes": [262144],
            },
            tmp_path,
        )


def test_benchmark_args_write_private_ingestion_routing(tmp_path):
    args = publisher._benchmark_args(
        {
            "models": ["private-model"],
            "model_profiles": {"private-model": "llama3-neutral"},
        },
        tmp_path,
    )

    routing_path = tmp_path / "ingestion-routing.private.json"
    assert args[-2:] == ["--ingestion-routing", str(routing_path)]
    assert publisher.json.loads(routing_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "model_profiles": {"private-model": "llama3-neutral"},
    }


def test_benchmark_args_forward_sampling_seed(tmp_path):
    args = publisher._benchmark_args(
        {"models": ["private-model"], "seed": 42},
        tmp_path,
    )

    assert args[-2:] == ["--seed", "42"]
