"""Self-contained functional tests for model_benchmark/runner.py.

Exercises: import, dry-run plan, checkpoint write, checkpoint load on resume,
and resumed runs skipping completed items. No model calls (all dry-run or
fixture-based). Run with: uv run python test_runner_selfcheck.py
"""
import os
import shutil
import sys

# Ensure model_benchmark is importable from the repo root.
REPO = "/opt/data/sugarcube-story-harness-for-ollama-p5-input-macros"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from model_benchmark.runner import (
    BenchmarkRunner,
    build_iteration_plan,
    make_test_id,
    save_checkpoint,
    load_checkpoint,
    atomic_write_text,
    result_record_from_model_run,
)
from model_benchmark.benchmark import BenchmarkConfig, ModelRunResult
from model_benchmark.schema import (
    CheckpointState,
    ProgressEvent,
    ResultRecord,
)
from model_benchmark.runner import IterationPlan, PlanItem
from harness.models import ModelOutput
from harness.parsers import parse_model_output
from model_benchmark.fixtures import _DRY_RUN_RESPONSE

OUT = "/tmp/runner_selfcheck"
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)

ok = 0
fail = 0


def check(cond, msg):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS: {msg}")
    else:
        fail += 1
        print(f"  FAIL: {msg}")


# ── TEST 1: import ───────────────────────────────────────────────────
print("TEST 1: module imports cleanly")
check(True, "from model_benchmark.runner import BenchmarkRunner succeeded")

# ── TEST 2: dry-run produces iteration plan without model calls ──────
print("TEST 2: dry-run produces iteration plan")
cfg = BenchmarkConfig(
    models=("llama3", "mistral"),
    variants=("compact", "full"),
    directions=("A", "B"),
    base_url="http://localhost:11434",
    timeout=120, num_predict=640, temperature=0.2, runs=2,
    dry_run=True,
)
runner = BenchmarkRunner(cfg, output_dir=OUT, quiet=True)
plan = runner.dry_run()
check(plan.total_cases == 2 * 2 * 2 * 2, f"total_cases == 8 (got {plan.total_cases})")
check(plan.dry_run is True, "plan.dry_run is True")
check(len(plan.models) == 2, f"2 models in plan (got {len(plan.models)})")
check(plan.repetitions == 2, f"repetitions == 2 (got {plan.repetitions})")
first = plan.items[0]
check(first.model == "llama3", f"first item model == llama3 (got {first.model})")
check(first.repetition == 1, f"first rep == 1 (got {first.repetition})")
last = plan.items[-1]
check(last.model == "mistral", f"last item model == mistral (got {last.model})")
check(last.repetition == 2, f"last rep == 2 (got {last.repetition})")
# No model calls: test_id deterministic and matches helper
check(
    first.test_id == make_test_id("llama3", "compact", "A", 1),
    f"test_id deterministic: {first.test_id}",
)

# ── TEST 3: checkpoint files are written to disk ─────────────────────
print("TEST 3: checkpoint write")
state = CheckpointState(
    run_id="r123",
    completed_ids=("a", "b", "c"),
    total_cases=3,
    last_saved_at="2026-07-30T00:00:00+00:00",
    provenance=(("a", "new"), ("b", "new"), ("c", "resumed")),
)
ckpt_path = os.path.join(OUT, "checkpoint.json")
save_checkpoint(state, ckpt_path)
check(os.path.exists(ckpt_path), f"checkpoint.json exists at {ckpt_path}")
import json
with open(ckpt_path) as f:
    data = json.load(f)
check(data["run_id"] == "r123", f"checkpoint run_id == r123 (got {data['run_id']})")
check(list(data["completed_ids"]) == ["a", "b", "c"], "completed_ids round-trip")
check(data["total_cases"] == 3, "total_cases round-trip")

# ── TEST 4: checkpoint loads on resume ───────────────────────────────
print("TEST 4: checkpoint load")
loaded = load_checkpoint(ckpt_path)
check(loaded is not None, "load_checkpoint returns state (not None)")
check(loaded.run_id == "r123", f"loaded run_id == r123 (got {loaded.run_id})")
check(tuple(loaded.completed_ids) == ("a", "b", "c"), "loaded completed_ids match")
check(loaded.total_cases == 3, "loaded total_cases == 3")
check(
    tuple(loaded.provenance) == (("a", "new"), ("b", "new"), ("c", "resumed")),
    "loaded provenance matches",
)
# load_checkpoint on missing path returns None
missing = load_checkpoint(os.path.join(OUT, "nope.json"))
check(missing is None, "load_checkpoint on missing file returns None")

# ── TEST 5: resumed run skips already-completed items ────────────────
print("TEST 5: resumed run skips completed items")
# Build a checkpoint with 2 of 4 cases completed, then run with resume=True.
# Use dry_run config so execute() uses the fixture path... but we want to
# test resume-skip on the loop. We'll simulate by pre-writing a checkpoint
# for the iteration plan and calling execute(resume=True) with a dry-run
# config so no real model calls happen — but dry_run config takes the
# fixture path. Instead, test the skip logic directly via a non-dry-run
# config pointing at unreachable models: each "new" case will ERROR (no
# ollama) but resumed cases will be SKIPPED.

cfg2 = BenchmarkConfig(
    models=("model-x",),
    variants=("compact",),
    directions=("A", "B"),
    base_url="http://localhost:1",  # unreachable -> errors, not hangs
    timeout=2, num_predict=64, temperature=0.2, runs=2,
    dry_run=False,
)
runner2 = BenchmarkRunner(cfg2, output_dir=OUT, quiet=True, checkpoint_every=1)
plan2 = build_iteration_plan(("model-x",), ("compact",), ("A", "B"), 2)
# Pre-write a checkpoint marking the first 2 cases complete.
pre_ids = {plan2.items[0].test_id, plan2.items[1].test_id}
pre_state = CheckpointState(
    run_id="r456",
    completed_ids=tuple(sorted(pre_ids)),
    total_cases=len(pre_ids),
    last_saved_at="2026-07-30T00:00:00+00:00",
    provenance=((plan2.items[0].test_id, "new"), (plan2.items[1].test_id, "new")),
)
save_checkpoint(pre_state, runner2.checkpoint_path)
# Resume: the 2 pre-completed cases should be SKIPPED, the other 2 should
# be recomputed (they'll ERROR since ollama is unreachable, but that's fine —
# the point is they are NOT skipped).
results = runner2.execute(resume=True)
n_skipped = sum(1 for r in results if r.status == "SKIPPED")
n_error = sum(1 for r in results if r.status == "ERROR")
print(f"  results statuses: {[r.status for r in results]}")
print(f"  skipped={n_skipped} error={n_error} total={len(results)}")
check(len(results) == 4, f"4 total results (got {len(results)})")
check(n_skipped == 2, f"2 resumed/skipped (got {n_skipped})")
# The 2 non-skipped cases should be ERROR (ollama unreachable) — proving they
# were actually recomputed rather than skipped.
check(n_error == 2, f"2 recomputed (error) cases (got {n_error})")
# The skipped cases should be the ones in the checkpoint, in order.
skipped_ids = {r.test_id for r in results if r.status == "SKIPPED"}
check(skipped_ids == pre_ids, f"skipped ids match checkpoint: {skipped_ids}")
# The skipped records should have provenance="resumed"
resumed_provs = [r.provenance for r in results if r.status == "SKIPPED"]
check(
    all(p == "resumed" for p in resumed_provs),
    f"all skipped records provenance=resumed: {resumed_provs}",
)

# ── TEST 6: force_rerun ignores checkpoint ───────────────────────────
print("TEST 6: force_rerun ignores checkpoint")
runner3 = BenchmarkRunner(
    cfg2, output_dir=OUT, quiet=True, checkpoint_every=1, force_rerun=True
)
# Re-use the checkpoint from test 5 (still on disk).
check(runner3.checkpoint_path.exists(), "checkpoint still present for force_rerun test")
results3 = runner3.execute(resume=True)
n_skipped3 = sum(1 for r in results3 if r.status == "SKIPPED")
n_error3 = sum(1 for r in results3 if r.status == "ERROR")
check(n_skipped3 == 0, f"force_rerun: 0 skipped (got {n_skipped3})")
check(n_error3 == 4, f"force_rerun: 4 recomputed (got {n_error3})")

# ── TEST 7: execute with dry_run config uses fixture (no model calls) ─
print("TEST 7: dry_run config executes fixture")
cfg_dry = BenchmarkConfig(
    models=(),
    variants=("compact",),
    directions=("A",),
    base_url="http://localhost:1",
    timeout=2, num_predict=64, temperature=0.2, runs=1,
    dry_run=True,
)
runner4 = BenchmarkRunner(cfg_dry, output_dir=os.path.join(OUT, "dry"), quiet=True)
results4 = runner4.execute()
check(len(results4) == 1, f"dry-run fixture: 1 record (got {len(results4)})")
check(results4[0].status == "PASS", f"dry-run fixture passes (got {results4[0].status})")
check(
    results4[0].actual_output_raw == _DRY_RUN_RESPONSE,
    "dry-run record raw is the fixture",
)
check(results4[0].scored_result is not None, "dry-run record embeds scored_result")

# ── TEST 8: atomic_write_text is atomic ──────────────────────────────
print("TEST 8: atomic_write_text")
target = os.path.join(OUT, "atomic.txt")
atomic_write_text(target, "hello\n")
with open(target) as f:
    check(f.read() == "hello\n", "atomic_write_text content correct")
# No leftover temp files
leftovers = [n for n in os.listdir(OUT) if n.startswith(".tmp_")]
check(len(leftovers) == 0, f"no leftover temp files (got {leftovers})")

# ── TEST 9: result_record_from_model_run bridge ──────────────────────
print("TEST 9: result_record_from_model_run")
parsed = parse_model_output(_DRY_RUN_RESPONSE)
from model_benchmark.benchmark import score_response
results_sc = score_response(_DRY_RUN_RESPONSE, parsed, "compact")
run = ModelRunResult(
    model_name="m", variant="compact", direction="A", run_index=0,
    raw_response=_DRY_RUN_RESPONSE, parsed_output=parsed,
    category_results=tuple(results_sc), overall_pass=True, elapsed_seconds=0.1,
)
rec = result_record_from_model_run(run)
check(rec.status == "PASS", f"bridge status PASS (got {rec.status})")
check(rec.score == 6.0, f"bridge score == 6.0 (got {rec.score})")
check(rec.max_score == 6.0, f"bridge max_score == 6.0 (got {rec.max_score})")
check(rec.normalized_score == 1.0, f"normalized_score == 1.0 (got {rec.normalized_score})")
check(rec.schema_version == "1.0.0", f"schema_version (got {rec.schema_version})")
check(rec.provenance == "new", "default provenance == new")
check(rec.scored_result is run, "scored_result embedded")

# ── TEST 10: progress callback fires ─────────────────────────────────
print("TEST 10: progress callback")
events = []
def cb(ev):
    events.append(ev)
runner5 = BenchmarkRunner(
    cfg_dry, output_dir=os.path.join(OUT, "cb"), quiet=True, progress_callback=cb,
)
runner5.execute()  # dry-run fixture path
# dry-run fixture path doesn't emit per-case progress (single fixture), but
# the callback should still be a valid ProgressEvent consumer. Test with a
# real (erroring) run instead.
cfg_cb = BenchmarkConfig(
    models=("m1",), variants=("compact",), directions=("A",),
    base_url="http://localhost:1", timeout=2, num_predict=64, temperature=0.2,
    runs=1, dry_run=False,
)
runner6 = BenchmarkRunner(
    cfg_cb, output_dir=os.path.join(OUT, "cb2"), quiet=True, progress_callback=cb,
)
events.clear()
runner6.execute()
check(len(events) == 1, f"1 progress event for 1 case (got {len(events)})")
check(isinstance(events[0], ProgressEvent), "event is ProgressEvent")
check(events[0].total == 1, f"event total == 1 (got {events[0].total})")
check(events[0].completed == 1, f"event completed == 1 (got {events[0].completed})")

print()
print(f"RESULTS: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
