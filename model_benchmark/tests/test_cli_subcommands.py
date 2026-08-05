"""Tests for the subcommand CLI (t_3ccd7826).

Covers the six subcommands (init, new, validate, list, run) and the --debug
mode, plus backward compatibility with the legacy flat-flag main(argv).

The tests run the CLI via ``main(argv)`` (the public entry point) and assert
on the process exit code and stdout/stderr content.  They use ``tmp_path``
fixtures so no real config files are touched.
"""
from __future__ import annotations

import json
import io
import sys
from pathlib import Path

import pytest

from model_benchmark.cli import main, cli_main, _build_subcommand_parser


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    """Run main(argv), capturing stdout/stderr.  Returns (rc, out, err)."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        rc = main(list(argv))
    except SystemExit as e:
        rc = int(e.code) if isinstance(e.code, int) else 1
    finally:
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdout, sys.stderr = old_out, old_err
    return rc, out, err


# ═══════════════════════════════════════════════════════════════════════════
# §1: Backward compatibility — legacy flat-flag flow still works
# ═══════════════════════════════════════════════════════════════════════════


class TestLegacyCompat:
    """The subcommand CLI must not break the existing flat-flag main(argv)."""

    def test_legacy_dry_run_still_works(self, tmp_path):
        """--dry-run with no subcommand runs the legacy benchmark flow."""
        rc, out, err = run_cli([
            "--dry-run", "--output-dir", str(tmp_path),
        ])
        assert rc == 0
        assert "Model Benchmark Report" in out

    def test_unknown_flag_returns_nonzero(self):
        """Unknown flags still return non-zero (legacy argparse error)."""
        rc, out, err = run_cli(["--nonexistent-flag"])
        assert rc != 0

    def test_subcommand_prefix_routes_to_cli_main(self, tmp_path):
        """A recognized subcommand routes to the subcommand CLI, not legacy."""
        rc, out, err = run_cli(["init", str(tmp_path / "cfg"), "--force"])
        assert rc == 0
        assert "Initialized" in out

    def test_refactor_profile_routes_only_fixed_plan_cases(
        self, monkeypatch, tmp_path
    ):
        captured = {}

        def fake_execute(
            cfg, cases, *, architectures=None, progress_callback=None
        ):
            captured["profile"] = cfg.benchmark_profile
            captured["case_ids"] = [case.id for case in cases]
            captured["architectures"] = tuple(architectures or ())
            return []

        monkeypatch.setattr(
            "model_benchmark.refactor_benchmark.execute_refactor_cases",
            fake_execute,
        )

        rc, out, err = run_cli([
            "run",
            "--profile", "refactor-canary",
            "--models", "fixture-model",
            "--quiet",
            "--no-anonymize",
            "--output-dir", str(tmp_path),
        ])

        assert rc == 0
        assert captured["profile"] == "refactor-canary"
        assert captured["architectures"] == ("typed_fill", "flat_fill")
        assert len(captured["case_ids"]) == 10
        assert captured["case_ids"][0] == "R0-ORDINARY-FANTASY"


# ═══════════════════════════════════════════════════════════════════════════
# §2: init — scaffold a new test config directory
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    """Test the `init` subcommand."""

    def test_init_creates_defaults_and_sample_test(self, tmp_path):
        rc, out, err = run_cli(["init", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "defaults.yaml").exists()
        assert (tmp_path / "cases" / "sample_test_001.yaml").exists()
        assert (tmp_path / "suites" / "README.md").exists()
        assert "Initialized" in out
        assert "defaults.yaml" in out

    def test_init_defaults_content_has_schema_version(self, tmp_path):
        rc, out, err = run_cli(["init", str(tmp_path)])
        assert rc == 0
        content = (tmp_path / "defaults.yaml").read_text()
        assert 'schema_version: "1.0.0"' in content
        assert "kind: defaults" in content
        assert "model_parameters" in content

    def test_init_sample_test_is_valid_yaml(self, tmp_path):
        """The generated sample test should be valid (loadable by the loader)."""
        rc, out, err = run_cli(["init", str(tmp_path)])
        assert rc == 0
        # Validate it via the validate command.
        rc2, out2, err2 = run_cli([
            "validate", str(tmp_path / "cases" / "sample_test_001.yaml"),
        ])
        assert rc2 == 0
        assert "valid" in out2.lower()

    def test_init_idempotent_skips_existing(self, tmp_path):
        rc1, out1, err1 = run_cli(["init", str(tmp_path)])
        assert rc1 == 0
        rc2, out2, err2 = run_cli(["init", str(tmp_path)])
        assert rc2 == 0
        assert "Skipped" in out2

    def test_init_force_overwrites(self, tmp_path):
        rc1, out1, err1 = run_cli(["init", str(tmp_path)])
        assert rc1 == 0
        original = (tmp_path / "defaults.yaml").read_text()
        rc2, out2, err2 = run_cli(["init", str(tmp_path), "--force"])
        assert rc2 == 0
        assert "Created" in out2

    def test_init_default_path(self, tmp_path, monkeypatch):
        """init with no path arg uses the default 'benchmark_configs'."""
        monkeypatch.chdir(tmp_path)
        rc, out, err = run_cli(["init"])
        assert rc == 0
        assert (tmp_path / "benchmark_configs" / "defaults.yaml").exists()


# ═══════════════════════════════════════════════════════════════════════════
# §3: new — create a new test YAML from a template
# ═══════════════════════════════════════════════════════════════════════════


class TestNew:
    """Test the `new <name>` subcommand."""

    def test_new_creates_file_with_flags(self, tmp_path):
        rc, out, err = run_cli([
            "new", "my_test",
            "--title", "My Test",
            "--capability", "sugarcube_compliance",
            "--category", "macro_usage",
            "--difficulty", "hard",
            "--tags", "smoke", "new",
            "--input", "Test the macro feature",
            "--no-prompt",
            "--dir", str(tmp_path),
        ])
        assert rc == 0
        target = tmp_path / "my_test.yaml"
        assert target.exists()
        content = target.read_text()
        assert "id: my_test" in content
        assert "name: My Test" in content
        assert "capability: sugarcube_compliance" in content
        assert "category: macro_usage" in content
        assert "difficulty: hard" in content
        assert '"smoke"' in content
        assert "Test the macro feature" in content

    def test_new_generated_file_is_valid(self, tmp_path):
        """The generated test file should validate successfully."""
        rc, out, err = run_cli([
            "new", "valid_test",
            "--capability", "sugarcube_compliance",
            "--category", "markup_compliance",
            "--no-prompt",
            "--dir", str(tmp_path),
        ])
        assert rc == 0
        rc2, out2, err2 = run_cli([
            "validate", str(tmp_path / "valid_test.yaml"),
        ])
        assert rc2 == 0, f"validation failed: {out2}{err2}"

    def test_new_default_difficulty_is_medium(self, tmp_path):
        rc, out, err = run_cli([
            "new", "diff_test", "--no-prompt", "--dir", str(tmp_path),
        ])
        assert rc == 0
        content = (tmp_path / "diff_test.yaml").read_text()
        assert "difficulty: medium" in content

    def test_new_default_evaluator_is_exact_match(self, tmp_path):
        rc, out, err = run_cli([
            "new", "eval_test", "--no-prompt", "--dir", str(tmp_path),
        ])
        assert rc == 0
        content = (tmp_path / "eval_test.yaml").read_text()
        assert "name: exact_match" in content

    def test_new_custom_evaluator(self, tmp_path):
        rc, out, err = run_cli([
            "new", "custom_eval_test",
            "--evaluator", "substring_regex",
            "--no-prompt",
            "--dir", str(tmp_path),
        ])
        assert rc == 0
        content = (tmp_path / "custom_eval_test.yaml").read_text()
        assert "name: substring_regex" in content

    def test_new_appends_yaml_extension(self, tmp_path):
        rc, out, err = run_cli([
            "new", "no_ext_test", "--no-prompt", "--dir", str(tmp_path),
        ])
        assert rc == 0
        assert (tmp_path / "no_ext_test.yaml").exists()
        assert not (tmp_path / "no_ext_test").exists()

    def test_new_preserves_explicit_yaml_extension(self, tmp_path):
        rc, out, err = run_cli([
            "new", "explicit.yaml", "--no-prompt", "--dir", str(tmp_path),
        ])
        assert rc == 0
        assert (tmp_path / "explicit.yaml").exists()


# ═══════════════════════════════════════════════════════════════════════════
# §4: validate — load and validate config file(s)
# ═══════════════════════════════════════════════════════════════════════════


class TestValidate:
    """Test the `validate` subcommand."""

    def test_validate_valid_file(self):
        """Validating the example config file succeeds."""
        path = "model_benchmark/tests/examples/full_feature_example.yaml"
        rc, out, err = run_cli(["validate", path])
        assert rc == 0
        assert "valid" in out.lower()

    def test_validate_default_discovery(self):
        """Validating with no path validates all discovered configs."""
        rc, out, err = run_cli(["validate"])
        assert rc == 0
        assert "document(s) valid" in out
        assert "sugarcube_markup_001" in out

    def test_validate_invalid_file_returns_nonzero(self, tmp_path):
        """An invalid config file produces a non-zero exit and error report."""
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            'schema_version: "1.0.0"\n'
            "kind: test\n"
            "id: bad_test\n"
            "difficulty: not-a-valid-difficulty\n"  # enum violation
            "input: test\n",
            encoding="utf-8",
        )
        rc, out, err = run_cli(["validate", str(bad)])
        assert rc == 1
        assert "INVALID" in out
        assert "error" in out.lower()

    def test_validate_directory(self, tmp_path):
        """Validating a directory scans it recursively."""
        # Use the default examples directory via config-dir.
        rc, out, err = run_cli([
            "validate", "model_benchmark/tests/examples",
        ])
        assert rc == 0
        assert "valid" in out.lower()

    def test_validate_reports_all_errors(self, tmp_path):
        """Multiple errors in one file are all reported (not just the first)."""
        bad = tmp_path / "multi_bad.yaml"
        bad.write_text(
            'schema_version: "1.0.0"\n'
            "kind: test\n"
            "id: multi_bad\n"
            "difficulty: bogus\n"   # error 1
            "timeout: -5\n"         # error 2 (must be > 0)
            "input: test\n",
            encoding="utf-8",
        )
        rc, out, err = run_cli(["validate", str(bad)])
        assert rc == 1
        assert "INVALID" in out
        # At least one error line present.
        assert out.count("\n  ") >= 1 or "error" in out.lower()


# ═══════════════════════════════════════════════════════════════════════════
# §5: list — list discovered tests with selection filters
# ═══════════════════════════════════════════════════════════════════════════


class TestList:
    """Test the `list` subcommand."""

    def test_list_table_default(self):
        rc, out, err = run_cli(["list"])
        assert rc == 0
        assert "Discovered:" in out
        assert "Selected:" in out
        assert "ID" in out
        assert "sugarcube_markup_001" in out

    def test_list_ids_format(self):
        rc, out, err = run_cli(["list", "--format", "ids"])
        assert rc == 0
        ids = [line.strip() for line in out.strip().splitlines() if line.strip()]
        assert "sugarcube_markup_001" in ids
        assert "sugarcube_direction_matrix" in ids

    def test_list_json_format(self):
        rc, out, err = run_cli(["list", "--format", "json"])
        assert rc == 0
        import json
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 6
        first = data[0]
        assert "id" in first
        assert "name" in first
        assert "suite" in first
        assert "tags" in first

    def test_list_with_select_filter(self):
        rc, out, err = run_cli(["list", "--select", "tag:smoke", "--format", "ids"])
        assert rc == 0
        ids = [l.strip() for l in out.strip().splitlines() if l.strip()]
        assert "sugarcube_markup_001" in ids
        # Other tests should not match tag:smoke.
        assert "sugarcube_direction_matrix" not in ids

    def test_list_with_exclude_filter(self):
        rc, out, err = run_cli(["list", "--exclude", "tag:core", "--format", "ids"])
        assert rc == 0
        ids = [l.strip() for l in out.strip().splitlines() if l.strip()]
        assert "sugarcube_markup_001" not in ids  # has tag:core
        assert "qa_exact_match_example" in ids  # no tag:core

    def test_list_with_compound_select(self):
        """A compound expression: difficulty:hard and not id:matrix."""
        rc, out, err = run_cli([
            "list", "--select", "difficulty:hard and not id:matrix",
            "--format", "ids",
        ])
        assert rc == 0
        ids = [l.strip() for l in out.strip().splitlines() if l.strip()]
        assert "sugarcube_inline_macro" in ids
        assert "sugarcube_direction_matrix" not in ids

    def test_list_max_selected_truncates(self):
        rc, out, err = run_cli(["list", "--max-selected", "2", "--format", "ids"])
        assert rc == 0
        ids = [l.strip() for l in out.strip().splitlines() if l.strip()]
        assert len(ids) == 2

    def test_list_config_dir_adds_search_path(self, tmp_path):
        """--config-dir adds a directory to the search path."""
        # Create a test file in a custom dir.
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "custom_test.yaml").write_text(
            'schema_version: "1.0.0"\n'
            "kind: test\n"
            "id: custom_discovered_test\n"
            "input: test\n",
            encoding="utf-8",
        )
        rc, out, err = run_cli([
            "list", "--config-dir", str(custom), "--format", "ids",
        ])
        assert rc == 0
        ids = [l.strip() for l in out.strip().splitlines() if l.strip()]
        assert "custom_discovered_test" in ids


# ═══════════════════════════════════════════════════════════════════════════
# §6: run — execute selected tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRun:
    """Test the `run` subcommand."""

    def test_run_plan_only_shows_matrix_expansion(self):
        rc, out, err = run_cli(["run", "--plan-only", "--quiet"])
        assert rc == 0
        assert "DRY RUN" in out
        assert "Matrix Expansion" in out
        assert "Total instances:" in out

    def test_run_plan_only_with_selection(self):
        rc, out, err = run_cli([
            "run", "--plan-only", "--select", "id:sugarcube_markup_001",
        ])
        assert rc == 0
        assert "DRY RUN" in out
        assert "sugarcube_markup_001" in out
        assert "Selected:    1" in out

    def test_run_dry_run_executes_fixtures(self, tmp_path):
        """--dry-run scores fixtures without calling Ollama and produces a report."""
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        assert "Model Benchmark Report" in out
        assert "PASS" in out

    def test_run_dry_run_writes_results(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        # A results jsonl should be written.
        files = list(tmp_path.rglob("results_internal.jsonl"))
        assert files, f"no results file in {tmp_path}"

    def test_run_output_format_json(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-format", "json",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        import json
        # The JSON output is a list of result rows.
        # Find the JSON array in the output (may have debug lines before it).
        lines = out.strip().splitlines()
        json_start = next(i for i, l in enumerate(lines) if l.strip().startswith("["))
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "test_id" in data[0]
        assert "status" in data[0]

    def test_run_executes_selected_declarative_test(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-format", "json",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        data = json.loads(out[out.index("["):])
        assert data
        assert all(
            row["test_id"].startswith("sugarcube_markup_001::")
            for row in data
        )

    def test_declarative_repetitions_are_reported_together(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-format", "markdown",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        assert "Variance & Confidence Intervals" in out
        assert "n=3" in out.lower() or "| 3 |" in out

    def test_declarative_dataset_rows_execute_with_repetitions(self, tmp_path):
        configs = tmp_path / "configs"
        configs.mkdir()
        (configs / "dataset_case.yaml").write_text(
            """
schema_version: "1.0.0"
kind: test
id: dataset_case
input: "Answer: {question}"
category: general_qa
repetitions: 2
expected:
  answer_type: exact
evaluation:
  name: exact_match
dataset:
  name: inline_qa
  format: inline
  inline_data:
    - {question: "Capital of France?", answer: "Paris"}
    - {question: "Two plus two?", answer: "4"}
""".strip(),
            encoding="utf-8",
        )

        rc, out, err = run_cli([
            "run", "--dry-run", "--config-dir", str(configs),
            "--select", "id:dataset_case", "--output-format", "json",
            "--output-dir", str(tmp_path / "out"), "--quiet",
        ])

        assert rc == 0
        data = json.loads(out[out.index("["):])
        assert len(data) == 4
        assert all(row["status"] == "PASS" for row in data)
        assert {row["test_id"].split("::")[1] for row in data} == {
            "row-1", "row-2"
        }

    def test_run_output_format_markdown(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--dry-run", "--select", "id:sugarcube_markup_001",
            "--output-format", "markdown",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        # Markdown report contains heading markers.
        assert "#" in out or "Benchmark" in out


# ═══════════════════════════════════════════════════════════════════════════
# §7: --debug mode
# ═══════════════════════════════════════════════════════════════════════════


class TestDebugMode:
    """Test that --debug shows resolved config, matrix expansion, and model I/O."""

    def test_debug_shows_resolved_config(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--debug", "--dry-run",
            "--select", "id:sugarcube_markup_001",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        assert "DEBUG — Resolved Config After Merge" in out
        assert "sugarcube_markup_001" in out
        # Shows merged values (suite defaults applied: temperature 0.0, num_predict 512).
        assert "temperature=0.0" in out
        assert "num_predict=512" in out
        assert "suite: sugarcube_core" in out

    def test_debug_shows_matrix_expansion(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--debug", "--plan-only",
            "--select", "id:sugarcube_direction_matrix",
        ])
        assert rc == 0
        assert "DEBUG — Resolved Config After Merge" in out
        assert "matrix expansion:" in out
        assert "18 instance(s)" in out
        # Shows dimension names.
        assert "parameters (matrix dims)" in out
        assert "variant" in out

    def test_debug_shows_model_io_capture(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--debug", "--dry-run",
            "--select", "id:sugarcube_markup_001",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        assert "DEBUG — Model I/O Capture" in out
        assert "model output (raw):" in out
        assert "parsed prose:" in out
        assert "category results:" in out
        assert "markup_compliance: PASS" in out

    def test_debug_shows_source_files_provenance(self, tmp_path):
        rc, out, err = run_cli([
            "run", "--debug", "--plan-only",
            "--select", "id:sugarcube_markup_001",
        ])
        assert rc == 0
        assert "source_files:" in out
        assert "sugarcube_markup_001.yaml" in out
        assert "full_feature_example.yaml" in out

    def test_debug_without_debug_no_debug_output(self, tmp_path):
        """Without --debug, no DEBUG sections appear."""
        rc, out, err = run_cli([
            "run", "--dry-run",
            "--select", "id:sugarcube_markup_001",
            "--output-dir", str(tmp_path), "--quiet",
        ])
        assert rc == 0
        assert "DEBUG —" not in out


# ═══════════════════════════════════════════════════════════════════════════
# §8: --help documentation
# ═══════════════════════════════════════════════════════════════════════════


class TestHelp:
    """Test that all commands are documented in --help."""

    def test_top_level_help_lists_all_subcommands(self):
        rc, out, err = run_cli(["--help"])
        assert rc == 0
        for cmd in ("init", "new", "validate", "list", "run"):
            assert cmd in out, f"{cmd} missing from top-level --help"

    def test_top_level_help_mentions_debug(self):
        rc, out, err = run_cli(["--help"])
        assert rc == 0
        assert "--debug" in out
        assert "resolved config" in out.lower() or "matrix" in out.lower()

    def test_init_help(self):
        rc, out, err = run_cli(["init", "--help"])
        assert rc == 0
        assert "Scaffold" in out or "scaffold" in out.lower()
        assert "--force" in out

    def test_new_help(self):
        rc, out, err = run_cli(["new", "--help"])
        assert rc == 0
        assert "--difficulty" in out
        assert "--evaluator" in out
        assert "--no-prompt" in out

    def test_validate_help(self):
        rc, out, err = run_cli(["validate", "--help"])
        assert rc == 0
        assert "validate" in out.lower()
        assert "errors" in out.lower()

    def test_list_help(self):
        rc, out, err = run_cli(["list", "--help"])
        assert rc == 0
        assert "--select" in out
        assert "--exclude" in out
        assert "--format" in out
        assert "table" in out
        assert "json" in out
        assert "ids" in out

    def test_run_help(self):
        rc, out, err = run_cli(["run", "--help"])
        assert rc == 0
        assert "--dry-run" in out
        assert "--debug" in out
        assert "--output-format" in out
        assert "--plan-only" in out
        assert "--select" in out
        assert "--profile" in out


# ═══════════════════════════════════════════════════════════════════════════
# §9: Subcommand parser structure
# ═══════════════════════════════════════════════════════════════════════════


class TestSubcommandParser:
    """Test the _build_subcommand_parser structure."""

    def test_parser_has_six_subcommands(self):
        parser = _build_subcommand_parser()
        # Find the subparsers action.
        sub_action = next(
            a for a in parser._actions
            if hasattr(a, "choices") and isinstance(a.choices, dict)
        )
        assert set(sub_action.choices.keys()) == {"init", "new", "validate", "list", "run", "models"}

    def test_global_debug_flag_present(self):
        parser = _build_subcommand_parser()
        dests = {a.dest for a in parser._actions}
        assert "debug" in dests

    def test_run_subparser_has_debug_flag(self):
        parser = _build_subcommand_parser()
        sub_action = next(
            a for a in parser._actions
            if hasattr(a, "choices") and isinstance(a.choices, dict)
        )
        run_parser = sub_action.choices["run"]
        dests = {a.dest for a in run_parser._actions}
        assert "debug" in dests
        assert "dry_run" in dests
        assert "plan_only" in dests
        assert "output_format" in dests
        assert "select" in dests
        assert "exclude" in dests
        assert "profile" in dests

    def test_list_subparser_has_formats(self):
        parser = _build_subcommand_parser()
        sub_action = next(
            a for a in parser._actions
            if hasattr(a, "choices") and isinstance(a.choices, dict)
        )
        list_parser = sub_action.choices["list"]
        dests = {a.dest for a in list_parser._actions}
        assert "format" in dests
        assert "select" in dests
        assert "max_selected" in dests
        assert "include_disabled" in dests


# ═══════════════════════════════════════════════════════════════════════════
# §10: cli_main dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestCliMainDispatch:
    """Test the cli_main dispatcher directly."""

    def test_cli_main_init(self, tmp_path):
        rc = cli_main(["init", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "defaults.yaml").exists()

    def test_cli_main_unknown_command_returns_nonzero(self):
        rc = cli_main(["bogus"])
        assert rc != 0

    def test_cli_main_empty_returns_nonzero(self):
        rc = cli_main([])
        assert rc != 0
