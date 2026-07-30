"""Smoke test for model_benchmark/checkpoint.py (Phase 7).

Verifies the acceptance criteria:
  1. CheckpointManager.save() writes atomically (no .tmp debris, valid JSON).
  2. CheckpointManager.load() / load_checkpoint() restores state.
  3. save -> load round-trips correctly (run_id, completed_ids, total_cases,
     provenance).
  4. Signal handlers are registered via context manager and explicit
     start/stop (idempotent, restored on exit).
  5. resume() loads an existing checkpoint and skips completed IDs.
  6. Reuses persistence.write_json (atomic via tmpfile + os.replace).

Run:  uv run python model_benchmark/_checkpoint_smoke.py
"""
from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
from pathlib import Path

# Ensure the repo root is on sys.path (run from anywhere).
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from model_benchmark.checkpoint import (
    CheckpointManager,
    CheckpointState,
    ResultProvenance,
    load_checkpoint,
    save_checkpoint,
)
from model_benchmark.schema import CheckpointState as SchemaCheckpointState

PASS = 0
FAIL = 0


def check(cond: bool, msg: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def main() -> int:
    global PASS, FAIL

    # Re-export identity: checkpoint.CheckpointState is schema.CheckpointState.
    print("TEST 0: re-export identity")
    check(
        CheckpointState is SchemaCheckpointState,
        "checkpoint.CheckpointState is schema.CheckpointState",
    )

    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        ckpt = out / "checkpoint.json"

        # ── TEST 1: save() writes a valid, atomic file ──────────────────
        print("TEST 1: save() writes atomically")
        mgr = CheckpointManager(run_id="run-001", path=ckpt, total_cases=4)
        mgr.mark_completed("modelA:compact:A:1", result={"score": 0.9})
        mgr.mark_completed("modelA:compact:A:2", provenance="retried")
        mgr.save()
        check(ckpt.exists(), f"checkpoint.json exists at {ckpt}")
        # No leftover .tmp files (atomic write cleans up).
        tmps = list(out.glob("*.tmp"))
        check(len(tmps) == 0, f"no leftover .tmp files (found {len(tmps)})")
        # Valid JSON with the expected keys.
        data = json.loads(ckpt.read_text())
        check(
            set(data.keys()) >= {"run_id", "completed_ids", "total_cases",
                                "last_saved_at", "provenance"},
            f"JSON has all 5 CheckpointState keys (got {sorted(data.keys())})",
        )
        check(data["run_id"] == "run-001", "run_id == run-001")
        check(data["total_cases"] == 4, "total_cases == 4")
        check(
            data["completed_ids"]
            == ["modelA:compact:A:1", "modelA:compact:A:2"],
            f"completed_ids sorted list (got {data['completed_ids']})",
        )
        check(
            data["provenance"]
            == [["modelA:compact:A:1", "new"], ["modelA:compact:A:2", "retried"]],
            f"provenance list of pairs (got {data['provenance']})",
        )
        check(data["last_saved_at"] != "", "last_saved_at is non-empty")

        # ── TEST 2: load() restores state ───────────────────────────────
        print("TEST 2: load() restores state")
        mgr2 = CheckpointManager(run_id="run-001", path=ckpt)
        loaded = mgr2.load()
        check(loaded is not None, "load() returns a CheckpointState (not None)")
        check(isinstance(loaded, CheckpointState), "loaded is a CheckpointState")
        check(loaded.run_id == "run-001", "loaded.run_id == run-001")
        check(loaded.total_cases == 4, "loaded.total_cases == 4")
        check(
            set(loaded.completed_ids) == {"modelA:compact:A:1", "modelA:compact:A:2"},
            f"loaded.completed_ids restored (got {loaded.completed_ids})",
        )
        check(
            isinstance(loaded.completed_ids, tuple),
            "loaded.completed_ids is a tuple (frozen dataclass field type)",
        )
        check(
            loaded.provenance
            == (("modelA:compact:A:1", "new"), ("modelA:compact:A:2", "retried")),
            f"loaded.provenance restored as tuple of pairs (got {loaded.provenance})",
        )
        check(loaded.last_saved_at != "", "loaded.last_saved_at restored")
        # Manager's mutable state was also restored.
        check(mgr2.is_completed("modelA:compact:A:1"), "mgr2.is_completed restored")
        check(mgr2.remaining() == 2, f"mgr2.remaining() == 2 (got {mgr2.remaining()})")

        # ── TEST 3: save -> load round-trips a second time ──────────────
        print("TEST 3: save -> load round-trip (second pass)")
        mgr2.mark_completed("modelA:full:B:1")
        mgr2.update_progress(iteration=1, step=0)
        mgr2.save()
        mgr3 = CheckpointManager(run_id="run-001", path=ckpt)
        loaded3 = mgr3.load()
        check(loaded3 is not None, "second load() returns state")
        check(
            len(loaded3.completed_ids) == 3,
            f"3 completed IDs after second save (got {len(loaded3.completed_ids)})",
        )
        check(
            "modelA:full:B:1" in loaded3.completed_ids,
            "newly completed ID present after round-trip",
        )

        # ── TEST 4: load_checkpoint on missing path returns None ────────
        print("TEST 4: load_checkpoint on missing/empty path")
        check(load_checkpoint(out / "nope.json") is None, "missing path -> None")
        empty = out / "empty.json"
        empty.write_text("")
        check(load_checkpoint(empty) is None, "empty file -> None")
        bad = out / "bad.json"
        bad.write_text("{not json")
        check(load_checkpoint(bad) is None, "invalid JSON -> None")

        # ── TEST 5: module-level save_checkpoint / load_checkpoint ──────
        print("TEST 5: module-level save_checkpoint / load_checkpoint")
        st = CheckpointState(
            run_id="r2",
            completed_ids=("x", "y"),
            total_cases=2,
            last_saved_at="2026-01-01T00:00:00+00:00",
            provenance=(("x", "new"), ("y", "resumed")),
        )
        p = out / "mod.json"
        save_checkpoint(st, p)
        check(p.exists(), "save_checkpoint wrote the file")
        loaded_st = load_checkpoint(p)
        check(loaded_st is not None, "load_checkpoint returns state")
        check(loaded_st.run_id == "r2", "module-level round-trip run_id")
        check(loaded_st.completed_ids == ("x", "y"), "round-trip completed_ids")
        check(
            loaded_st.provenance == (("x", "new"), ("y", "resumed")),
            "round-trip provenance",
        )

        # ── TEST 6: signal handlers via context manager ────────────────
        print("TEST 6: signal handlers via context manager")
        sig_before_int = signal.getsignal(signal.SIGINT)
        sig_before_term = signal.getsignal(signal.SIGTERM)
        with CheckpointManager(run_id="cm", path=ckpt) as m:
            # Inside the with-block, SIGINT/SIGTERM handlers are installed.
            h_int = signal.getsignal(signal.SIGINT)
            h_term = signal.getsignal(signal.SIGTERM)
            # Bound methods create a new object on each attribute access, so
            # ``is`` identity never holds; compare by value (==) which checks
            # __func__ and __self__.
            check(
                h_int == m._handle_signal,
                "SIGINT handler installed inside with-block",
            )
            check(
                h_term == m._handle_signal,
                "SIGTERM handler installed inside with-block",
            )
            m.total_cases = 10
            m.mark_completed("t1")
        # After the with-block, handlers are restored and a final save ran.
        check(
            signal.getsignal(signal.SIGINT) is sig_before_int,
            "SIGINT handler restored after with-block",
        )
        check(
            signal.getsignal(signal.SIGTERM) is sig_before_term,
            "SIGTERM handler restored after with-block",
        )
        # Final save on normal exit wrote the checkpoint.
        final = load_checkpoint(ckpt)
        check(final is not None, "final save on context-manager exit wrote file")
        check(
            final is not None and final.run_id == "cm",
            "context-manager checkpoint has correct run_id",
        )

        # ── TEST 7: explicit start/stop ─────────────────────────────────
        print("TEST 7: explicit start/stop")
        m2 = CheckpointManager(run_id="ss", path=ckpt)
        check(not m2._active, "manager not active before start()")
        m2.start()
        check(m2._active, "manager active after start()")
        check(
            signal.getsignal(signal.SIGINT) == m2._handle_signal,
            "SIGINT installed after explicit start()",
        )
        m2.stop()
        check(not m2._active, "manager not active after stop()")
        check(
            signal.getsignal(signal.SIGINT) is sig_before_int,
            "SIGINT restored after explicit stop()",
        )
        # start() is idempotent; stop() is idempotent.
        m2.start(); m2.start()
        check(m2._active, "double start() stays active")
        m2.stop(); m2.stop()
        check(not m2._active, "double stop() stays inactive")

        # ── TEST 8: resume() loads + installs handlers ───────────────────
        print("TEST 8: resume() loads existing checkpoint + installs handlers")
        # Pre-write a checkpoint via save_checkpoint.
        pre = CheckpointState(
            run_id="res",
            completed_ids=("done1", "done2"),
            total_cases=5,
            last_saved_at="2026-01-01T00:00:00+00:00",
            provenance=(("done1", "new"), ("done2", "new")),
        )
        save_checkpoint(pre, ckpt)
        rmgr = CheckpointManager(run_id="res", path=ckpt)
        rstate = rmgr.resume()
        check(rstate is not None, "resume() returns loaded state")
        check(rmgr._active, "resume() installed signal handlers")
        check(rmgr.is_completed("done1"), "resume() restored completed IDs")
        check(
            rmgr.remaining() == 3,
            f"resume() remaining == 3 (got {rmgr.remaining()})",
        )
        rmgr.stop()
        check(not rmgr._active, "stopped after resume()")

        # ── TEST 9: force_rerun ignores existing checkpoint ──────────────
        print("TEST 9: force_rerun ignores existing checkpoint")
        fr = CheckpointManager(run_id="res", path=ckpt, force_rerun=True)
        fstate = fr.resume()
        check(fstate is None, "force_rerun resume() returns None (no load)")
        check(fr._active, "force_rerun still installs handlers")
        check(
            not fr.is_completed("done1"),
            "force_rerun did not restore completed IDs",
        )
        fr.stop()

        # ── TEST 10: model_config tracking + round-trip ─────────────────
        print("TEST 10: model_config + partial results tracking")
        mc = CheckpointManager(
            run_id="mc",
            path=ckpt,
            model_config={"temperature": 0.7, "base_url": "http://localhost:11434"},
            total_cases=2,
        )
        check(
            mc.partial_results.get("__model_config__")
            == {"temperature": 0.7, "base_url": "http://localhost:11434"},
            "model_config stored under __model_config__",
        )
        mc.mark_completed("case-1", result={"score": 1.0})
        mc.save()
        mc2 = CheckpointManager(run_id="mc", path=ckpt)
        mc2.load()
        check(mc2.is_completed("case-1"), "partial result tracked + restored")

    print(f"\n{'=' * 48}")
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
