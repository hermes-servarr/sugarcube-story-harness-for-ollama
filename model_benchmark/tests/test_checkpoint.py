"""Tests for checkpoint save/load/resume and signal handler (Phase 5 mock).

Covers save_checkpoint/load_checkpoint (atomic writes, resume),
register_signal_handler/unregister_signal_handler, and emergency
checkpoint on SIGINT/SIGTERM (P6 INV-C6).
"""
import json
import signal
import sys
from pathlib import Path

import pytest

from model_benchmark.runner import (
    save_checkpoint,
    load_checkpoint,
    register_signal_handler,
    unregister_signal_handler,
    _emergency_checkpoint_handler,
)
from model_benchmark.schema import CheckpointState


def _make_state(
    *,
    run_id: str = "test-run",
    completed_ids: tuple[str, ...] = ("m:v:d:1",),
    total_cases: int = 1,
    last_saved_at: str = "2026-07-30T00:00:00+00:00",
    provenance: tuple[tuple[str, str], ...] = (("m:v:d:1", "new"),),
) -> CheckpointState:
    """Build a minimal CheckpointState for testing."""
    return CheckpointState(
        run_id=run_id,
        completed_ids=completed_ids,
        total_cases=total_cases,
        last_saved_at=last_saved_at,
        provenance=provenance,  # type: ignore[arg-type]
    )


# ═══════════════════════════════════════════════════════════════════════════
# Class 1: save_checkpoint / load_checkpoint round-trip
# ═══════════════════════════════════════════════════════════════════════════


class TestSaveLoadCheckpoint:
    def test_save_then_load_roundtrips_state(self, tmp_path):
        """save_checkpoint writes JSON that load_checkpoint reads back exactly."""
        state = _make_state()
        path = tmp_path / "checkpoint.json"
        save_checkpoint(state, str(path))
        loaded = load_checkpoint(str(path))
        assert loaded is not None
        assert loaded.run_id == state.run_id
        assert tuple(loaded.completed_ids) == state.completed_ids
        assert loaded.total_cases == state.total_cases
        assert loaded.last_saved_at == state.last_saved_at

    def test_load_returns_none_when_file_absent(self, tmp_path):
        """load_checkpoint returns None (not raises) when file does not exist."""
        assert load_checkpoint(str(tmp_path / "nope.json")) is None

    def test_checkpoint_is_valid_json(self, tmp_path):
        """The checkpoint file is valid JSON with expected keys."""
        state = _make_state()
        path = tmp_path / "checkpoint.json"
        save_checkpoint(state, str(path))
        with open(path) as f:
            data = json.load(f)
        assert "run_id" in data
        assert "completed_ids" in data
        assert "total_cases" in data
        assert "last_saved_at" in data
        assert "provenance" in data


# ═══════════════════════════════════════════════════════════════════════════
# Class 2: register_signal_handler / unregister_signal_handler
# ═══════════════════════════════════════════════════════════════════════════


class TestRegisterUnregister:
    def test_register_installs_custom_handler_for_sigint(self, tmp_path):
        """After register, SIGINT handler is _emergency_checkpoint_handler."""
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        current: object = None
        try:
            current = signal.signal(signal.SIGINT, signal.SIG_DFL)
            assert current is _emergency_checkpoint_handler
        finally:
            signal.signal(signal.SIGINT, current or signal.SIG_DFL)
            unregister_signal_handler()

    def test_register_installs_custom_handler_for_sigterm(self, tmp_path):
        """After register, SIGTERM handler is _emergency_checkpoint_handler."""
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        current: object = None
        try:
            current = signal.signal(signal.SIGTERM, signal.SIG_DFL)
            assert current is _emergency_checkpoint_handler
        finally:
            signal.signal(signal.SIGTERM, current or signal.SIG_DFL)
            unregister_signal_handler()

    def test_unregister_restores_default_sigint(self, tmp_path):
        """After unregister, SIGINT is restored to the pre-register handler."""
        # Set a known default first.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        unregister_signal_handler()
        current = signal.signal(signal.SIGINT, signal.SIG_DFL)
        assert current is signal.SIG_DFL

    def test_unregister_restores_default_sigterm(self, tmp_path):
        """After unregister, SIGTERM is restored to the pre-register handler."""
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        unregister_signal_handler()
        current = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        assert current is signal.SIG_DFL

    def test_unregister_restores_previously_installed_handler(self, tmp_path):
        """If a custom handler was set before register, unregister restores it."""
        def custom_handler(signum, frame):
            pass

        signal.signal(signal.SIGINT, custom_handler)
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        unregister_signal_handler()
        current = signal.signal(signal.SIGINT, signal.SIG_DFL)
        assert current is custom_handler

    def test_register_captures_state_builder_and_path(self, tmp_path):
        """register stores the state_builder closure and checkpoint path."""
        from model_benchmark import runner as rmod

        builder = lambda: _make_state()
        path = str(tmp_path / "cp.json")
        register_signal_handler(builder, path)
        try:
            assert rmod._active_state_builder is builder
            assert rmod._active_checkpoint_path == path
        finally:
            unregister_signal_handler()

    def test_unregister_clears_state_builder_and_path(self, tmp_path):
        """After unregister, module-level state is cleared."""
        from model_benchmark import runner as rmod

        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        unregister_signal_handler()
        assert rmod._active_state_builder is None
        assert rmod._active_checkpoint_path == ""


# ═══════════════════════════════════════════════════════════════════════════
# Class 3: Emergency checkpoint on SIGINT/SIGTERM
# ═══════════════════════════════════════════════════════════════════════════


class TestEmergencyCheckpoint:
    def test_emergency_handler_writes_checkpoint_on_sigint(self, tmp_path):
        """Calling _emergency_checkpoint_handler with SIGINT writes checkpoint.json."""
        path = str(tmp_path / "checkpoint.json")
        register_signal_handler(lambda: _make_state(), path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGINT, None)
            assert exc_info.value.code == 130  # 128 + SIGINT(2)
            assert Path(path).exists()
            loaded = load_checkpoint(path)
            assert loaded is not None
            assert loaded.run_id == "test-run"
        finally:
            unregister_signal_handler()

    def test_emergency_handler_writes_checkpoint_on_sigterm(self, tmp_path):
        """Calling _emergency_checkpoint_handler with SIGTERM writes checkpoint.json."""
        path = str(tmp_path / "checkpoint.json")
        register_signal_handler(lambda: _make_state(), path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGTERM, None)
            assert exc_info.value.code == 143  # 128 + SIGTERM(15)
            assert Path(path).exists()
            loaded = load_checkpoint(path)
            assert loaded is not None
            assert "m:v:d:1" in loaded.completed_ids
        finally:
            unregister_signal_handler()

    def test_emergency_checkpoint_atomic_no_partial_file(self, tmp_path):
        """Emergency checkpoint write is atomic — no .tmp files left behind."""
        path = str(tmp_path / "checkpoint.json")
        register_signal_handler(lambda: _make_state(), path)
        try:
            with pytest.raises(SystemExit):
                _emergency_checkpoint_handler(signal.SIGINT, None)
            # No temp files should remain in the directory.
            tmp_files = list(tmp_path.glob(".tmp_*"))
            assert tmp_files == []
            # The checkpoint file exists and is complete.
            assert Path(path).exists()
        finally:
            unregister_signal_handler()

    def test_emergency_handler_exit_code_sigint(self, tmp_path):
        """Exit code for SIGINT is 130 (128+2)."""
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGINT, None)
            assert exc_info.value.code == 130
        finally:
            unregister_signal_handler()

    def test_emergency_handler_exit_code_sigterm(self, tmp_path):
        """Exit code for SIGTERM is 143 (128+15)."""
        register_signal_handler(lambda: _make_state(), str(tmp_path / "cp.json"))
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGTERM, None)
            assert exc_info.value.code == 143
        finally:
            unregister_signal_handler()

    def test_emergency_handler_safety_on_builder_failure(self, tmp_path):
        """If the state_builder raises, the handler still exits (P1 §4.1 safety)."""
        def bad_builder():
            raise RuntimeError("builder failed")

        path = str(tmp_path / "checkpoint.json")
        register_signal_handler(bad_builder, path)
        try:
            with pytest.raises(SystemExit) as exc_info:
                _emergency_checkpoint_handler(signal.SIGINT, None)
            # Still exits with the signal code, no checkpoint written.
            assert exc_info.value.code == 130
            assert not Path(path).exists()
        finally:
            unregister_signal_handler()
