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
        ("benchmark_optimization/iteration-01.md", True),
        ("benchmark_optimization", True),
        ("model_benchmark/scoring.py", False),
        ("benchmark_optimization-evil/file", False),
    ],
)
def test_candidate_path_matching(path, expected):
    patterns = [
        "model_benchmark/prompt_overrides.json",
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
