# Iteration 43 — Harness-suite: re-validate frozen corpus and attempt architecture baseline

## Mode

harness-suite

## Baseline (published anonymized result)

Published `benchmark_anon/results_anonymized.json` summary:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet.
- Passage-generation corpus (context only, not the architecture suite):
  128 cases, 51 passed, pass rate 0.3984, mean score 0.7698. Failure
  category: instruction_following (77). Thinking variant 6/32 (0.1875).
- No `typed_fill` / `flat_fill` baseline exists.

## Pre-flight checks

- `git pull --ff-only origin main`: already up to date.
- HEAD at `a494ff74ec8169b07cc1c1635bf907cc947b8b9a` equals `origin/main`.
- SSH config exists at `/opt/data/home/.ssh/config`: confirmed
  (`sugarcube-benchmark` host entry present; contents not read).
- No active matching managed processes: confirmed (process list empty).

## Current corpus state (frozen at 24)

`model_benchmark/refactor_cases.json` has 24 cases. All six test-validity
revisions from earlier iterations are already applied:

- HPROP-0007 (R0-ORDINARY-FANTASY rev 2): task overclaim fix.
- HPROP-0005 (R3-HUB-COPY rev 2): task overclaim fix.
- HPROP-0008 (R4-STYLE-CANT rev 2): task overclaim fix.
- HPROP-0006 (R8-CHOICE-DISTINCTION rev 2): task overclaim fix.
- HPROP-0001 + HPROP-0009 (R2-MULTI-DIALOGUE rev 3): forbidden_terms
  consistency + task-vs-plan slot-kind alignment.

The protected test `test_refactor_corpus_has_fixed_core_and_canary_sizes`
enforces `len(cases) == 24` and `select_refactor_cases(cases,
"refactor-canary") == 10`. A data-only harness-suite edit therefore cannot
add the three remaining proposed cases (HPROP-0002 S-context room-mode,
HPROP-0003 mid-tier D1 distractor, HPROP-0004 S-context mixed-kind) — doing
so would fail validation. Those require an operator-approved signed code
commit to raise the frozen corpus count.

## Failure pattern / coverage gap

The architecture benchmark has never produced per-architecture results
across iterations 21-42. The connectivity blocker moved through DNS
resolution failure (iterations 21-41) to routing/link-layer unreachability
(iteration 42, exit 255 "no route to host"), then to a stale single-run
lock after WOL + IP correction (iteration 42 post-run recovery, exit 75).
The frozen 24-case corpus is otherwise validated and ready to yield the
first `typed_fill` vs `flat_fill` baseline.

## Hypothesis (suite-level)

No corpus change is needed. The frozen 24-case corpus, with all six
test-validity revisions applied, is validated and ready to produce the
first architecture baseline across `typed_fill` and `flat_fill`. The
remaining blocking condition is the PC-side stale single-run lock; this
iteration uses the scheduled stale-state self-heal to clear it, then runs
the protected benchmark once.

## Exact suite change

No corpus change. Validation commands were run:

- `python -m json.tool model_benchmark/refactor_cases.json` — valid.
- `uv run python -c "from model_benchmark.refactor_benchmark import
  load_refactor_cases; load_refactor_cases()"` — passed (24 cases).
- `uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py
  model_benchmark/tests/test_profiles.py
  model_benchmark/tests/test_cli_subcommands.py
  model_benchmark/tests/test_hermes_benchmark_publish.py` — 134 passed.

## Git diff guard

`git diff --name-only` shows no tracked changes. The only new file is the
untracked `benchmark_optimization/iteration-43.md`. No paths outside the
allowed set.

## Rollback condition

No corpus change to roll back.

## Benchmark attempt

Invoked `/run-sugarcube-benchmark` exactly once on the validated 24-case
corpus (managed process `proc_0092516c5f2e`, PID 35495). The SSH command
exited after 4 seconds with code **75** and message
`A benchmark is already running.`

## Stale-state self-heal investigation (Step 2.4)

Because this job freshly woke the PC, the exit-75 was investigated before
giving up:

- `task-status.json` state: `running`.
- Live `hermes_benchmark_task` process count via `Get-CimInstance`: **2**.

A real benchmark process IS running on the PC (count > 0), so the single-run
lock is legitimate, not stale. Per the self-heal procedure, the stale state
file was NOT deleted and the benchmark was NOT retried. A live run owns the
GPU; a competing benchmark must not be started.

## Result

Stop condition fired: `A benchmark is already running.` (exit 75), and the
investigation confirmed a genuine live run (2 live `hermes_benchmark_task`
processes, state `running`). This is not the stale-lock error predicted for
a fresh WOL wake; the PC is actively running a benchmark. No architecture
result was produced this turn. The `harness_architectures` summary remains
0 cases. No corpus change was made or needed.

## Decision

Stopped without retrying. No corpus change (frozen 24-case corpus, all six
test-validity revisions applied, 134 tests pass). The frozen corpus is
validated and ready to produce the first `typed_fill` vs `flat_fill` baseline
once the PC-side live run completes. The live run is not owned by this turn;
it was already in progress before this job's benchmark start. Operator should
allow the current PC-side run to finish and re-invoke the benchmark on a
later turn, or confirm whether the in-progress run is stale/orphaned and
should be cleared intentionally on the PC.

Three coverage-gap proposals (HPROP-0002: S-context room-mode,
HPROP-0003: mid-tier D1 distractor, HPROP-0004: S-context mixed-kind)
remain valid but require an operator-approved signed code commit to raise
the frozen corpus count from 24 before they can be promoted into
`refactor-core`.
