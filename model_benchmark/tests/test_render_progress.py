"""Tests for the rich terminal progress renderer (Phase 7 production).

Targets the production functions in model_benchmark/runner.py:
  - render_progress (public, pure)
  - _render_progress_stderr (private wrapper)
  - _supports_color (private helper)
  - _format_eta (private helper)

These tests re-validate the 5 P6 invariants (INV-RP1..INV-RP5) against the
production implementation, and exercise the P3 interfaces at their boundaries.
Originally authored in the P5 mock; re-targeted at production code for P7.
"""
import inspect
import os
import shutil
import sys
from unittest.mock import patch

import pytest

from model_benchmark.runner import (
    render_progress,
    _render_progress_stderr,
    _supports_color,
    _format_eta,
    BenchmarkRunner,
)
from model_benchmark.schema import ProgressEvent
from model_benchmark.scoring import BenchmarkConfig


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════════


def ev(**overrides) -> ProgressEvent:
    """Build a representative ProgressEvent with sensible defaults."""
    base = dict(
        stage="generation",
        current_test="t_001",
        completed=3,
        total=10,
        percent=30.0,
        elapsed_seconds=12.0,
        eta_seconds=28.0,
        model_alias="m1",
        config_alias="c1",
        variant="compact",
        direction="A",
        repetition=1,
        pass_count=2,
        fail_count=1,
        error_count=0,
        skipped_count=0,
        invalid_count=0,
        timeout_count=0,
        cancelled_count=0,
    )
    base.update(overrides)
    return ProgressEvent(**base)


def _make_config(dry_run: bool = True) -> BenchmarkConfig:
    return BenchmarkConfig(
        models=("test-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://localhost:99999",
        timeout=1,
        num_predict=1,
        temperature=0.0,
        runs=1,
        dry_run=dry_run,
    )


# ═══════════════════════════════════════════════════════════════════════════
# _format_eta boundary tests (P3 §2.4)
# ═══════════════════════════════════════════════════════════════════════════


class TestFormatEta:
    def test_unknown_negative(self):
        assert _format_eta(-1.0) == "--:--"

    def test_unknown_zero_negative(self):
        assert _format_eta(-0.5) == "--:--"

    def test_zero(self):
        assert _format_eta(0) == "0:00"

    def test_30s(self):
        assert _format_eta(30) == "0:30"

    def test_90s(self):
        assert _format_eta(90) == "1:30"

    def test_just_under_one_hour(self):
        assert _format_eta(3599) == "59:59"

    def test_exactly_one_hour(self):
        assert _format_eta(3600) == "1:00:00"

    def test_over_one_hour(self):
        assert _format_eta(3700) == "1:01:40"

    def test_ten_hours(self):
        assert _format_eta(36000) == "10:00:00"

    def test_rounding(self):
        # 59.6 rounds to 60 -> 1:00
        assert _format_eta(59.6) == "1:00"


# ═══════════════════════════════════════════════════════════════════════════
# INV-RP1: quiet suppression
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderQuiet:
    def test_quiet_returns_empty(self):
        assert render_progress(ev(), quiet=True) == ""

    def test_quiet_overrides_all_params(self):
        result = render_progress(ev(), quiet=True, verbose=True, color=True, width=40)
        assert result == ""


# ═══════════════════════════════════════════════════════════════════════════
# INV-RP2: ANSI color gating
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderColor:
    def test_no_color_by_default(self):
        out = render_progress(ev())
        assert "\033[" not in out

    def test_color_false_no_ansi(self):
        out = render_progress(ev(), color=False)
        assert "\033[" not in out

    def test_color_true_has_ansi(self):
        out = render_progress(ev(), color=True)
        assert "\033[" in out

    def test_color_codes_match_counts(self):
        out = render_progress(ev(pass_count=5, fail_count=3, error_count=2, skipped_count=1), color=True)
        assert "\033[32m5\033[0m" in out  # green pass
        assert "\033[31m3\033[0m" in out  # red fail
        assert "\033[33m2\033[0m" in out  # yellow err
        assert "\033[2m1\033[0m" in out   # dim skip

    def test_zero_counts_still_shown(self):
        out = render_progress(ev(pass_count=0, fail_count=0, error_count=0, skipped_count=0), color=True)
        assert "\033[32m0\033[0m" in out


class TestSupportsColor:
    def test_no_tty_returns_false(self):
        with patch("os.isatty", return_value=False):
            assert _supports_color() is False

    def test_no_color_env_returns_false(self):
        with patch("os.isatty", return_value=True), \
             patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            assert _supports_color() is False

    def test_term_dumb_returns_false(self):
        with patch("os.isatty", return_value=True), \
             patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
            # remove NO_COLOR if present so it doesn't short-circuit
            env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
            with patch.dict(os.environ, env, clear=True):
                assert _supports_color() is False

    def test_all_conditions_met_returns_true(self):
        env = {"TERM": "xterm-256color"}
        with patch("os.isatty", return_value=True), \
             patch.dict(os.environ, env, clear=True):
            assert _supports_color() is True


# ═══════════════════════════════════════════════════════════════════════════
# INV-RP3: render_progress purity
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderPurity:
    def test_call_twice_identical(self):
        a = render_progress(ev())
        b = render_progress(ev())
        assert a == b

    def test_no_io_or_env_in_source(self):
        src = inspect.getsource(render_progress)
        assert "os.isatty" not in src
        assert "os.environ" not in src

    def test_deterministic_with_explicit_args(self):
        a = render_progress(ev(), width=60, color=False)
        b = render_progress(ev(), width=60, color=False)
        assert a == b


# ═══════════════════════════════════════════════════════════════════════════
# verbose label
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderVerbose:
    def test_verbose_adds_case_label(self):
        out = render_progress(ev(), verbose=True)
        assert "v=compact" in out
        assert "dir=A" in out
        assert "rep=1" in out

    def test_non_verbose_omits_label(self):
        out = render_progress(ev(), verbose=False)
        assert "v=compact" not in out

    def test_empty_current_test_omits_label(self):
        out = render_progress(ev(current_test=""), verbose=True)
        assert "v=compact" not in out


# ═══════════════════════════════════════════════════════════════════════════
# bar rendering
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderBar:
    def test_bar_present(self):
        out = render_progress(ev())
        assert "[" in out and "]" in out
        assert "=" in out or ">" in out

    def test_half_filled(self):
        out = render_progress(ev(completed=5, total=10, percent=50.0))
        assert "[" in out

    def test_zero_filled(self):
        out = render_progress(ev(completed=0, total=10, percent=0.0))
        assert "[" in out
        # The bar (text between the brackets) should contain no "=" fill.
        bar = out[out.index("[") + 1 : out.index("]")]
        assert "=" not in bar

    def test_full_filled(self):
        out = render_progress(ev(completed=10, total=10, percent=100.0))
        assert "=" in out

    def test_width_clamping_min(self):
        out = render_progress(ev(), width=5)
        # width clamped to min 20; bar should still render
        assert "[" in out and "]" in out

    def test_width_clamping_max(self):
        out = render_progress(ev(), width=500)
        # width clamped to max 120; output should not be absurdly long
        assert len(out) < 500

    def test_total_zero_no_crash(self):
        out = render_progress(ev(total=0, completed=0, percent=0.0))
        assert "[" in out


# ═══════════════════════════════════════════════════════════════════════════
# content rendering
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderContent:
    def test_percent_shown(self):
        out = render_progress(ev(percent=30.0))
        assert "30.0%" in out

    def test_completed_total_shown(self):
        out = render_progress(ev(completed=3, total=10))
        assert "3/10" in out

    def test_eta_shown(self):
        out = render_progress(ev(eta_seconds=28.0))
        assert "0:28" in out

    def test_eta_unknown(self):
        out = render_progress(ev(eta_seconds=-1.0))
        assert "--:--" in out

    def test_status_counts_shown(self):
        out = render_progress(ev(pass_count=2, fail_count=1, error_count=0, skipped_count=0))
        assert "pass=2" in out
        assert "fail=1" in out


# ═══════════════════════════════════════════════════════════════════════════
# _render_progress_stderr wrapper
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderProgressStderr:
    def test_quiet_no_output(self, capfd):
        _render_progress_stderr(ev(), verbose=False, quiet=True)
        captured = capfd.readouterr()
        assert captured.err == ""

    def test_non_tty_writes_newline(self, capfd):
        with patch("os.isatty", return_value=False):
            _render_progress_stderr(ev(), verbose=False, quiet=False)
        captured = capfd.readouterr()
        assert captured.err.endswith("\n")
        assert "\r" not in captured.err

    def test_tty_writes_carriage_return(self, capfd):
        with patch("os.isatty", return_value=True), \
             patch("shutil.get_terminal_size") as mock_ts, \
             patch("model_benchmark.runner._supports_color", return_value=False):
            mock_ts.return_value = type("TS", (), {"columns": 80})
            _render_progress_stderr(ev(), verbose=False, quiet=False)
        captured = capfd.readouterr()
        assert captured.err.startswith("\r")


# ═══════════════════════════════════════════════════════════════════════════
# INV-RP4: progress_callback contract preserved
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressCallbackPreserved:
    def _make_item(self):
        from model_benchmark.runner import PlanItem
        return PlanItem(
            test_id="m1:compact:A:1",
            model="m1",
            variant="compact",
            direction="A",
            repetition=1,
        )

    def test_callback_fires_once(self, tmp_path):
        count = {"n": 0}

        def cb(event):
            count["n"] += 1

        runner = BenchmarkRunner(
            _make_config(dry_run=True),
            output_dir=str(tmp_path),
            quiet=True,
            progress_callback=cb,
        )
        runner._completed = 1
        runner._pass_count = 1
        runner._start_time = 0.0
        runner._emit_progress("generation", self._make_item(), 5)
        assert count["n"] == 1

    def test_callback_exceptions_swallowed(self, tmp_path):
        def cb(event):
            raise RuntimeError("boom")

        runner = BenchmarkRunner(
            _make_config(dry_run=True),
            output_dir=str(tmp_path),
            quiet=True,
            progress_callback=cb,
        )
        runner._completed = 1
        runner._pass_count = 1
        runner._start_time = 0.0
        # Should not raise even though callback throws.
        runner._emit_progress("generation", self._make_item(), 5)


# ═══════════════════════════════════════════════════════════════════════════
# INV-RP5: stdlib only — no forbidden imports
# ═══════════════════════════════════════════════════════════════════════════


class TestStdlibOnly:
    def test_no_forbidden_imports(self):
        import model_benchmark.runner as runner_mod
        src = inspect.getsource(runner_mod)
        # check import lines only
        forbidden = ["tqdm", "rich", "colorama", "termcolor", "blessed"]
        for name in forbidden:
            # look for actual import statements, not just mentions in comments
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    assert name not in stripped, f"forbidden import: {name}"

    def test_shutil_imported(self):
        import model_benchmark.runner as runner_mod
        assert hasattr(runner_mod, "shutil") or "import shutil" in inspect.getsource(runner_mod)
