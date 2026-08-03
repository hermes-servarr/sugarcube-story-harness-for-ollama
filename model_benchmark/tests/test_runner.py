"""Tests for BenchmarkRunner signal-handler integration (Phase 5 mock).

Covers execute() registration/unregistration, emergency checkpoint
during execute(), and restoration on exception (P6 INV-C6).
"""
import signal
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from model_benchmark.runner import (
    BenchmarkRunner,
    build_iteration_plan,
    result_record_from_model_run,
    register_signal_handler,
    unregister_signal_handler,
    _emergency_checkpoint_handler,
)
from model_benchmark.scoring import (
    BenchmarkConfig,
    CategoryResult,
    ModelRunResult,
    run_single_model,
)
from model_benchmark.schema import CheckpointState
from harness.models import ModelOutput
from harness.ollama_client import OllamaGenerationResult


def _make_config(dry_run: bool = True) -> BenchmarkConfig:
    """Build a minimal BenchmarkConfig for testing."""
    return BenchmarkConfig(
        models=("test-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://localhost:99999",  # unreachable; dry-run avoids it
        timeout=1,
        num_predict=1,
        temperature=0.0,
        runs=1,
        dry_run=dry_run,
    )


def test_build_iteration_plan_accepts_explicit_covering_cases():
    plan = build_iteration_plan(
        models=("m1", "m2"),
        variants=("compact",),
        directions=("A",),
        repetitions=2,
        matrix_cases=(("compact", "A"), ("json", "G")),
    )

    assert plan.total_cases == 8
    assert plan.variants == ("compact", "json")
    assert plan.directions == ("A", "G")
    assert [item.test_id for item in plan.items[:4]] == [
        "m1:compact:A:1",
        "m1:compact:A:2",
        "m1:json:G:1",
        "m1:json:G:2",
    ]


def test_runner_dry_run_uses_canary_profile_matrix():
    cfg = _make_config(dry_run=True)
    object.__setattr__(cfg, "benchmark_profile", "canary")

    plan = BenchmarkRunner(cfg, quiet=True).dry_run()

    assert plan.total_cases == 8
    assert {(item.variant, item.direction) for item in plan.items} == {
        ("compact", "A"),
        ("full", "B"),
        ("json", "C"),
        ("thinking", "D"),
        ("compact", "E"),
        ("full", "F"),
        ("json", "G"),
        ("thinking", "H"),
    }


def test_result_record_excludes_na_categories_from_denominator():
    run = ModelRunResult(
        model_name="test-model",
        variant="compact",
        direction="A",
        run_index=0,
        raw_response="output",
        parsed_output=ModelOutput(prose="output"),
        category_results=(
            CategoryResult("markup_compliance", True, 1.0, "ok"),
            CategoryResult(
                "link_setter_syntax",
                False,
                0.0,
                "N/A",
                applicable=False,
            ),
        ),
        overall_pass=True,
    )

    record = result_record_from_model_run(run)

    assert record.max_score == 1.0
    assert record.score == 1.0
    assert record.normalized_score == 1.0
    assert record.status == "PASS"


def test_core_run_passes_and_records_configured_seed(monkeypatch):
    captured = {}

    def fake_call(*args, **kwargs):
        captured["seed"] = kwargs["seed"]
        return OllamaGenerationResult(
            response=(
                "PROSE:\n$gold is visible. <<set $seen to true>>\n"
                "CHOICES:\n- Continue | Move on\nSUMMARY:\nThe flag changed."
            ),
            prompt_eval_count=120,
            eval_count=30,
            done_reason="stop",
        )

    monkeypatch.setattr(
        "model_benchmark.scoring.call_ollama_sync_detailed",
        fake_call,
    )
    cfg = _make_config(dry_run=False)
    object.__setattr__(cfg, "random_seed", "42")

    run = run_single_model("test-model", "compact", "A", cfg)

    assert captured["seed"] == 42
    assert run.random_seed == "42"
    record = result_record_from_model_run(run)
    assert record.random_seed == "42"
    assert record.input_tokens == 120
    assert record.output_tokens == 30
    assert record.total_tokens == 150
    assert record.finish_reason == "stop"


# ═══════════════════════════════════════════════════════════════════════════
# Class 1: execute() registers/unregisters signal handler
# ═══════════════════════════════════════════════════════════════════════════


class TestExecuteSignalRegistration:
    def test_execute_registers_handler_before_loop(self, tmp_path):
        """execute() calls register_signal_handler before the generation loop."""
        with patch("model_benchmark.runner.register_signal_handler") as mock_reg, \
             patch("model_benchmark.runner.unregister_signal_handler") as mock_unreg:
            runner = BenchmarkRunner(
                _make_config(dry_run=False),
                output_dir=str(tmp_path),
                quiet=True,
            )
            with patch.object(runner, "_run_one_case", return_value=MagicMock(status="PASS")):
                with patch.object(runner, "_emit_progress"):
                    with patch.object(runner, "_maybe_checkpoint"):
                        runner.execute()
            assert mock_reg.called, "register_signal_handler was not called"
            assert mock_unreg.called, "unregister_signal_handler was not called"

    def test_execute_does_not_register_in_dry_run_fixture_mode(self, tmp_path):
        """When config.dry_run=True, execute delegates to fixture path (no signal handler)."""
        with patch("model_benchmark.runner.register_signal_handler") as mock_reg, \
             patch("model_benchmark.runner.unregister_signal_handler") as mock_unreg:
            runner = BenchmarkRunner(
                _make_config(dry_run=True),
                output_dir=str(tmp_path),
                quiet=True,
            )
            runner.execute()
            # Dry-run mode returns early via _execute_dry_run_fixture — does NOT
            # reach the signal-handler registration block.
            assert not mock_reg.called
            assert not mock_unreg.called

    def test_signal_handlers_restored_after_normal_execute(self, tmp_path):
        """After execute() returns normally, default SIGINT handler is restored."""
        # Set a known default.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        runner = BenchmarkRunner(
            _make_config(dry_run=False),
            output_dir=str(tmp_path),
            quiet=True,
        )
        # Patch _run_one_case so we don't actually call a model.
        with patch.object(runner, "_run_one_case", return_value=MagicMock(status="PASS")):
            with patch.object(runner, "_emit_progress"):
                with patch.object(runner, "_maybe_checkpoint"):
                    runner.execute()
        sigint_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
        sigterm_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        assert sigint_handler is signal.SIG_DFL
        assert sigterm_handler is signal.SIG_DFL


# ═══════════════════════════════════════════════════════════════════════════
# Class 2: Emergency checkpoint during execute()
# ═══════════════════════════════════════════════════════════════════════════


class TestEmergencyCheckpointDuringExecute:
    def test_emergency_handler_invoked_writes_checkpoint(self, tmp_path):
        """If the emergency handler is triggered mid-loop, checkpoint.json is written."""
        cp_path = tmp_path / "checkpoint.json"
        # Simulate: register the handler, call the handler directly (as a
        # real SIGINT would), and verify the checkpoint was written.
        def state_builder():
            return CheckpointState(
                run_id="emergency-test",
                completed_ids=("test-model:compact:A:1",),
                total_cases=1,
                last_saved_at="2026-07-30T00:00:00+00:00",
                provenance=(("test-model:compact:A:1", "new"),),
            )

        register_signal_handler(state_builder, str(cp_path))
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGINT, None)
            assert exc_info.value.code == 130
            assert cp_path.exists()
        finally:
            unregister_signal_handler()

    def test_emergency_checkpoint_contains_completed_ids(self, tmp_path):
        """The emergency checkpoint contains the completed_ids from the run."""
        cp_path = tmp_path / "checkpoint.json"
        register_signal_handler(
            lambda: CheckpointState(
                run_id="r1",
                completed_ids=("m1:v:d:1", "m1:v:d:2"),
                total_cases=2,
                last_saved_at="2026-07-30T00:00:00+00:00",
                provenance=(("m1:v:d:1", "new"), ("m1:v:d:2", "new")),
            ),
            str(cp_path),
        )
        try:
            with pytest.raises(SystemExit):
                _emergency_checkpoint_handler(signal.SIGTERM, None)
            from model_benchmark.runner import load_checkpoint
            loaded = load_checkpoint(str(cp_path))
            assert loaded is not None
            assert "m1:v:d:1" in loaded.completed_ids
            assert "m1:v:d:2" in loaded.completed_ids
        finally:
            unregister_signal_handler()


# ═══════════════════════════════════════════════════════════════════════════
# Class 3: Signal handler restoration on exception
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalRestorationOnException:
    def test_handler_restored_when_loop_raises(self, tmp_path):
        """If the loop body raises, the finally block still restores handlers."""
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        runner = BenchmarkRunner(
            _make_config(dry_run=False),
            output_dir=str(tmp_path),
            quiet=True,
        )

        def boom(item):
            raise RuntimeError("simulated failure")

        with patch.object(runner, "_run_one_case", side_effect=boom):
            with patch.object(runner, "_emit_progress"):
                with patch.object(runner, "_maybe_checkpoint"):
                    with pytest.raises(RuntimeError, match="simulated failure"):
                        runner.execute()

        # Even though the loop raised, the finally block should have
        # restored default handlers.
        sigint_handler = signal.signal(signal.SIGINT, signal.SIG_DFL)
        sigterm_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        assert sigint_handler is signal.SIG_DFL
        assert sigterm_handler is signal.SIG_DFL

    def test_unregister_called_in_finally_on_exception(self, tmp_path):
        """unregister_signal_handler is called even when the loop raises."""
        runner = BenchmarkRunner(
            _make_config(dry_run=False),
            output_dir=str(tmp_path),
            quiet=True,
        )

        def boom(item):
            raise ValueError("boom")

        with patch("model_benchmark.runner.unregister_signal_handler") as mock_unreg:
            with patch.object(runner, "_run_one_case", side_effect=boom):
                with patch.object(runner, "_emit_progress"):
                    with patch.object(runner, "_maybe_checkpoint"):
                        with pytest.raises(ValueError):
                            runner.execute()
            assert mock_unreg.called

    def test_register_and_unregister_called_in_pair(self, tmp_path):
        """Both register and unregister are called exactly once per execute()."""
        runner = BenchmarkRunner(
            _make_config(dry_run=False),
            output_dir=str(tmp_path),
            quiet=True,
        )

        with patch("model_benchmark.runner.register_signal_handler") as mock_reg, \
             patch("model_benchmark.runner.unregister_signal_handler") as mock_unreg:
            with patch.object(runner, "_run_one_case", return_value=MagicMock(status="PASS")):
                with patch.object(runner, "_emit_progress"):
                    with patch.object(runner, "_maybe_checkpoint"):
                        runner.execute()
            assert mock_reg.call_count == 1
            assert mock_unreg.call_count == 1

    def test_register_passes_build_checkpoint_state_and_path(self, tmp_path):
        """register_signal_handler is called with _build_checkpoint_state and checkpoint_path."""
        runner = BenchmarkRunner(
            _make_config(dry_run=False),
            output_dir=str(tmp_path),
            quiet=True,
        )

        with patch("model_benchmark.runner.register_signal_handler") as mock_reg, \
             patch("model_benchmark.runner.unregister_signal_handler"):
            with patch.object(runner, "_run_one_case", return_value=MagicMock(status="PASS")):
                with patch.object(runner, "_emit_progress"):
                    with patch.object(runner, "_maybe_checkpoint"):
                        runner.execute()
            # The first positional arg should be the bound method
            # _build_checkpoint_state, the second the checkpoint path.
            call_args = mock_reg.call_args
            assert call_args is not None
            state_builder = call_args[0][0]
            checkpoint_path = call_args[0][1]
            assert state_builder == runner._build_checkpoint_state
            assert str(checkpoint_path) == str(runner.checkpoint_path)
