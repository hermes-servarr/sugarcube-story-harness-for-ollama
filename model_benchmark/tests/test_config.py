"""Tests for the CLI configuration module.

Tests the EXTENDED BenchmarkConfig dataclass (P2 §2) and parse_cli_args (P3 §1.2).
Enforces P6 invariants INV-CFG1..INV-CFG7.
"""
from __future__ import annotations

import pytest

from model_benchmark.config import BenchmarkConfig, parse_cli_args, _build_parser


# ═══════════════════════════════════════════════════════════════════════════
# §1: Extended BenchmarkConfig dataclass tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBenchmarkConfigFields:
    """Test the EXTENDED BenchmarkConfig dataclass per P2 §2 and P3 §1.1."""

    def test_benchmark_config_22_fields(self):
        """22 fields total (8 required + 14 optional)."""
        fields = list(BenchmarkConfig.__dataclass_fields__)
        assert len(fields) == 22, f"Expected 22 fields, got {len(fields)}"

    def test_benchmark_config_required_fields(self):
        """8 required fields have no defaults."""
        required = ["models", "variants", "directions", "base_url",
                    "timeout", "num_predict", "temperature", "runs"]
        for name in required:
            assert name in BenchmarkConfig.__dataclass_fields__

    def test_benchmark_config_optional_fields(self):
        """12 optional fields have defaults (3 original + 9 new)."""
        optional = ["dry_run", "output_path", "json_output_path",
                    "checkpoint_every", "checkpoint_interval_seconds",
                    "output_dir", "verbose", "quiet", "anonymize",
                    "baseline_dir", "random_seed", "force_rerun",
                    "ingestion_routing_path", "benchmark_profile"]
        for name in optional:
            assert name in BenchmarkConfig.__dataclass_fields__

    def test_benchmark_config_new_field_defaults(self):
        """New field defaults match P2 §2.2."""
        cfg = BenchmarkConfig(
            models=(), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        assert cfg.checkpoint_every == 10
        assert cfg.checkpoint_interval_seconds == 60.0
        assert cfg.output_dir == "benchmark_outputs"
        assert cfg.verbose is False
        assert cfg.quiet is False
        assert cfg.anonymize is True
        assert cfg.baseline_dir == ""
        assert cfg.random_seed == ""
        assert cfg.force_rerun is False
        assert cfg.ingestion_routing_path == ""
        assert cfg.benchmark_profile == ""

    def test_benchmark_config_frozen(self):
        """Dataclass is frozen (immutable)."""
        cfg = BenchmarkConfig(
            models=(), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        with pytest.raises((AttributeError, Exception)):
            cfg.models = ("other",)

    def test_benchmark_config_backward_compat(self):
        """Constructing with only the 11 original fields works."""
        cfg = BenchmarkConfig(
            models=("test",), variants=("compact",), directions=("A",),
            base_url="http://localhost:11434", timeout=120, num_predict=640,
            temperature=0.2, runs=1,
        )
        # All 9 new fields have their defaults.
        assert cfg.checkpoint_every == 10
        assert cfg.anonymize is True
        assert cfg.force_rerun is False


# ═══════════════════════════════════════════════════════════════════════════
# §2: parse_cli_args tests
# ═══════════════════════════════════════════════════════════════════════════


class TestParseCliArgs:
    """Test parse_cli_args per P3 §1.2."""

    def test_parse_cli_args_default(self):
        """No argv returns BenchmarkConfig with defaults."""
        cfg = parse_cli_args([])
        assert isinstance(cfg, BenchmarkConfig)
        assert cfg.models == ()
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.anonymize is True

    def test_parse_cli_args_legacy_flags(self):
        """11 legacy flags map to the 11 original fields."""
        cfg = parse_cli_args([
            "--models", "a", "b",
            "--variants", "compact",
            "--directions", "A", "B",
            "--base-url", "http://x:1234",
            "--timeout", "60",
            "--num-predict", "100",
            "--temperature", "0.5",
            "--runs", "3",
            "--dry-run",
            "--output", "out.txt",
            "--json-output", "out.json",
        ])
        assert cfg.models == ("a", "b")
        assert cfg.variants == ("compact",)
        assert cfg.directions == ("A", "B")
        assert cfg.base_url == "http://x:1234"
        assert cfg.timeout == 60
        assert cfg.num_predict == 100
        assert cfg.temperature == 0.5
        assert cfg.runs == 3
        assert cfg.dry_run is True
        assert cfg.output_path == "out.txt"
        assert cfg.json_output_path == "out.json"

    def test_parse_cli_args_new_flags(self):
        """9 new flags map to the 9 new fields."""
        cfg = parse_cli_args([
            "--checkpoint-every", "5",
            "--checkpoint-interval", "30.0",
            "--output-dir", "/tmp/out",
            "--verbose",
            "--quiet",
            "--no-anonymize",
            "--baseline", "/tmp/prev",
            "--seed", "42",
            "--force-rerun",
        ])
        assert cfg.checkpoint_every == 5
        assert cfg.checkpoint_interval_seconds == 30.0
        assert cfg.output_dir == "/tmp/out"
        assert cfg.verbose is True
        assert cfg.quiet is True
        assert cfg.anonymize is False
        assert cfg.baseline_dir == "/tmp/prev"
        assert cfg.random_seed == "42"
        assert cfg.force_rerun is True

    def test_parse_cli_args_named_profile(self):
        cfg = parse_cli_args(["--profile", "canary"])

        assert cfg.benchmark_profile == "canary"

    def test_parse_cli_args_refactor_profile(self):
        cfg = parse_cli_args(["--profile", "refactor-core"])

        assert cfg.benchmark_profile == "refactor-core"
        assert cfg.variants == ("compact", "full", "json", "thinking")
        assert cfg.directions == tuple("ABCDEFGH")

    def test_parse_cli_args_anonymize_boolean_optional_action(self):
        """--anonymize / --no-anonymize toggle the anonymize field (default True)."""
        cfg_default = parse_cli_args([])
        assert cfg_default.anonymize is True

        cfg_anon = parse_cli_args(["--anonymize"])
        assert cfg_anon.anonymize is True

        cfg_no_anon = parse_cli_args(["--no-anonymize"])
        assert cfg_no_anon.anonymize is False

    def test_parse_cli_args_returns_benchmark_config(self):
        """Returns a BenchmarkConfig instance (not a Namespace)."""
        from argparse import Namespace
        cfg = parse_cli_args([])
        assert isinstance(cfg, BenchmarkConfig)
        assert not isinstance(cfg, Namespace)

    def test_parse_cli_args_all_21_fields_populated(self):
        """All 21 fields populated after parsing."""
        cfg = parse_cli_args([])
        field_names = list(BenchmarkConfig.__dataclass_fields__)
        for name in field_names:
            value = getattr(cfg, name)
            # All fields should have a value (either provided or default)
            assert value is not None or name in ("random_seed", "baseline_dir",
                                                   "output_path", "json_output_path")


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
        expected.add("ingestion_routing")
        expected.add("profile")
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
