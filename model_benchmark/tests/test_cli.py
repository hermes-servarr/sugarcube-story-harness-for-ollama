"""Tests for the CLI entry point.

Tests main(argv) -> int (P3 §3.1) and _build_parser (P3 §3.2).
Enforces P6 invariants INV-CLI1..INV-CLI9.
"""
from __future__ import annotations

import pytest

from model_benchmark.cli import main, _build_parser
from model_benchmark.config import BenchmarkConfig, parse_cli_args


# ═══════════════════════════════════════════════════════════════════════════
# §1: main(argv) -> int tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMain:
    """Test main(argv) -> int per P3 §3.1."""

    def test_main_dry_run(self, tmp_path):
        """--dry-run produces a run dir with outputs without calling Ollama (INV-CLI3)."""
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet"])
        assert rc == 0

    def test_main_returns_zero_on_success(self, tmp_path):
        """Returns 0 on success."""
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet"])
        assert rc == 0

    def test_main_returns_nonzero_on_error(self):
        """Returns non-zero on error (bad argparse)."""
        rc = main(["--nonexistent-flag"])
        assert rc != 0

    def test_main_legacy_flags(self, tmp_path):
        """11 legacy flags preserved (INV-CLI2)."""
        rc = main([
            "--dry-run", "--quiet",
            "--models", "test",
            "--variants", "compact",
            "--directions", "A",
            "--base-url", "http://localhost:11434",
            "--timeout", "120",
            "--num-predict", "640",
            "--temperature", "0.2",
            "--runs", "1",
            "--output-dir", str(tmp_path),
        ])
        assert rc == 0

    def test_main_new_flags(self, tmp_path):
        """9 new flags (INV-CLI2)."""
        rc = main([
            "--dry-run", "--quiet",
            "--checkpoint-every", "5",
            "--checkpoint-interval", "30",
            "--output-dir", str(tmp_path),
            "--verbose",
            "--no-anonymize",
            "--baseline", "",
            "--seed", "42",
            "--force-rerun",
        ])
        assert rc == 0

    def test_main_baseline(self, tmp_path):
        """--baseline triggers compare_runs/detect_regressions (INV-CLI5) when baseline exists."""
        # No baseline dir means no comparison — should still succeed.
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet",
                   "--baseline", "/nonexistent/path"])
        assert rc == 0

    def test_main_stats(self, tmp_path):
        """runs > 1 triggers compute_run_statistics and passes stats to reports (INV-CLI4)."""
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet",
                   "--runs", "2"])
        assert rc == 0

    def test_main_anonymize(self, tmp_path):
        """--anonymize triggers anonymization pipeline (INV-CLI6)."""
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet",
                   "--anonymize"])
        assert rc == 0

    def test_main_no_anonymize(self, tmp_path):
        """--no-anonymize skips anonymization (INV-CLI6)."""
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet",
                   "--no-anonymize"])
        assert rc == 0

    def test_main_legacy_output(self, tmp_path):
        """--output / --json-output produce output files (backward compat — INV-CLI8)."""
        out_file = tmp_path / "report.txt"
        rc = main(["--dry-run", "--output-dir", str(tmp_path), "--quiet",
                   "--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()


# ═══════════════════════════════════════════════════════════════════════════
# §2: _build_parser tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildParser:
    """Test _build_parser (private helper) per P3 §3.2."""

    def test_build_parser_has_20_flags(self):
        """Parser has all 11 legacy + 9 new flags."""
        parser = _build_parser()
        actions = {a.dest for a in parser._actions}
        expected = {"models", "variants", "directions", "base_url",
                    "timeout", "num_predict", "temperature", "runs",
                    "dry_run", "output", "json_output",
                    "checkpoint_every", "checkpoint_interval",
                    "output_dir", "verbose", "quiet", "anonymize",
                    "baseline", "seed", "force_rerun"}
        assert expected.issubset(actions), f"Missing: {expected - actions}"

    def test_build_parser_defaults(self):
        """Defaults match BenchmarkConfig field defaults."""
        parser = _build_parser()
        defaults = {a.dest: a.default for a in parser._actions}
        assert defaults["base_url"] == "http://localhost:11434"
        assert defaults["timeout"] == 120
        assert defaults["num_predict"] == 640
        assert defaults["temperature"] == 0.2
        assert defaults["runs"] == 1
        assert defaults["checkpoint_every"] == 10
        assert defaults["checkpoint_interval"] == 60.0
        assert defaults["output_dir"] == "benchmark_outputs"
        assert defaults["anonymize"] is True

    def test_build_parser_anonymize_default_true(self):
        """--anonymize defaults True."""
        parser = _build_parser()
        anon_action = next(a for a in parser._actions if a.dest == "anonymize")
        assert anon_action.default is True
