# Iteration 45 — Harness-suite: re-validate frozen corpus, attempt first architecture baseline with reattachment semantics

## Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures,
seed 42 with five repetitions)

## Baseline (published anonymized result)

Published `benchmark_anon/results_anonymized.json` summary:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet.
- Passage-generation corpus (context only, not the architecture suite):
  128 cases, 51 passed, pass rate 0.3984, mean score 0.7698. Failure
  category: instruction_following (77).
- Thinking variant 6/32 (0.1875); failed categories markdown? no —
  markup_compliance 17, thinking_quality 15, passage_structure 14,
  macro_usage 13.
- Plain-text diagnostic: 48 cases, 12 passed (0.25).
- No `typed_fill` / `flat_fill` baseline exists.

## Pre-flight checks (Steps 1-2)

- `git pull --ff-only origin main`: up to date (HEAD 66b0502).
- HEAD `66b05024502e4cb11a6488ab6ffa4f171b15447a` equals `origin/main`.
- SSH config exists at `/opt/data/home/.ssh/config`: confirmed
  (`sugarcube-benchmark` host entry present; contents not read).
- No active matching managed processes: confirmed (process list empty, no
  `sugarcube-benchmark` command).

## WOL pre-flight (Step 2.5)

- `/opt/data/bin/wake-windows-pc` exited 0 (magic packet sent via SSH relay).
- Waited 300 s, then probed the PC SSH port through the servarr relay
  (192.168.0.111:22): **OPEN** on the first probe. PC freshly woken by this
  pre-flight and reachable.

## Reattachment semantics in HEAD (Step 2.4)

Commit `dce51d5` ("fix(benchmark): recover and reattach scheduled runs") is an
ancestor of HEAD and is therefore in effect this turn. Under these semantics:

1. A fresh invocation REATTACHES to an active benchmark request and normally
   waits for the existing run's completion, then returns its published result.
   This is expected behavior when a prior SSH connection was lost, not a
   conflict.
2. Exit 75 ("A benchmark is already running.") now means a CONCURRENTLY
   CONNECTED trigger owns monitoring of an active run.
3. PC-side state files (task-status.json, run.lock) must never be deleted; the
   publisher replaces stale requests itself.

This differs from iterations 43/44, which ran under the older semantics and
treated exit 75 as a genuine-live-run stop condition after investigating live
`hermes_benchmark_task` processes. This turn relies on the reattachment path.

## Current corpus state (frozen at 24)

`model_benchmark/refactor_cases.json` has 24 cases (JSON valid, loader
returns 24). All six test-validity revisions from earlier iterations are
already applied:

- HPROP-0007 (R0-ORDINARY-FANTASY rev 2): task overclaim fix.
- HPROP-0005 (R3-HUB-COPY rev 2): task overclaim fix.
- HPROP-0008 (R4-STYLE-CANT rev 2): task overclaim fix.
- HPROP-0006 (R8-CHOICE-DISTINCTION rev 2): task overclaim fix.
- HPROP-0001 + HPROP-0009 (R2-MULTI-DIALOGUE rev 3): forbidden_terms
  consistency + task-vs-plan slot-kind alignment.

The protected test `test_refactor_corpus_has_fixed_core_and_canary_sizes`
(verified in `model_benchmark/tests/test_refactor_benchmark.py`) asserts
`len(cases) == 24`, `select_refactor_cases(cases, "refactor-core") == 24`, and
`select_refactor_cases(cases, "refactor-canary") == 10`. A data-only
harness-suite edit therefore cannot promote the three remaining proposed new
cases (HPROP-0002 S-context room-mode, HPROP-0003 mid-tier D1 distractor,
HPROP-0004 S-context mixed-kind) into `refactor-core`: doing so would raise the
count past 24 and fail validation. Those require an operator-approved signed
code commit to update the test and raise the frozen corpus count, which is
outside the allowed boundary for an active benchmark goal (Python code and the
protected test may not be edited; no signing key is available).

## Failure pattern / coverage gap

The architecture benchmark has never produced per-architecture results across
iterations 21-44. The connectivity blocker progressed from DNS resolution
failure, to routing/link-layer unreachability (exit 255), to a stale/active
single-run lock (exit 75). Iterations 43/44 investigated exit 75 and found 2
live `hermes_benchmark_task` processes with state `running`, concluding a
genuine live run. This turn, after a fresh WOL wake, the port is OPEN and the
HEAD carries the reattachment fix, so a fresh invocation should either start a
fresh run or reattach to the prior run and eventually publish.

The frozen 24-case corpus is otherwise validated and ready to yield the first
`typed_fill` vs `flat_fill` baseline.

## Hypothesis (suite-level)

No corpus change is needed this turn. The frozen 24-case corpus, with all six
test-validity revisions applied, is validated and remains the best data-only
state. The remaining productive step is to invoke the protected benchmark once
under reattachment semantics to finally produce the first `typed_fill` vs
`flat_fill` baseline. The result — whether it reattaches to a completed prior
run or runs fresh — is the first baseline for the current 24-case suite
revision, not a pass-rate improvement over the old denominator.

## Exact suite change

No change to `model_benchmark/refactor_cases.json`. Validation commands were
run and passed:

- `python -m json.tool model_benchmark/refactor_cases.json` — valid (24 cases).
- `uv run python -c "from model_benchmark.refactor_benchmark import
  load_refactor_cases; load_refactor_cases()"` — 24 cases.
- `uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py
  model_benchmark/tests/test_profiles.py
  model_benchmark/tests/test_cli_subcommands.py
  model_benchmark/tests/test_hermes_benchmark_publish.py` — 134 passed.

## Git diff guard

`git diff --name-only` at start of this turn shows no tracked changes. The only
new file is the untracked `benchmark_optimization/iteration-45.md`. No paths
outside the allowed set (case corpus, iteration note, proposal backlog).

## Rollback condition

No corpus change was made, so there is nothing to roll back.

## Benchmark attempt

Invoked `/run-sugarcube-benchmark` exactly once on the validated 24-case
corpus (managed process `proc_7401878fa9cd`, PID 44041). The SSH command
exited after ~2 seconds with code **75** and message
`A benchmark is already running.`

## Stop condition: concurrent trigger owns monitoring (exit 75)

Per Step 2.4 reattachment semantics (commit `dce51d5` is in HEAD), exit 75 now
means a **concurrently connected trigger currently owns monitoring of an
active run**, not a stale lock. A fresh invocation that finds the prior SSH
connection lost would instead reattach on the PC and wait; because we received
exit 75, another trigger connection reached the PC first and is actively
monitoring the in-progress run.

Permitted diagnostic only (Step 2.4), read via the `windows-pc` alias:

- `task-status.json` state: `running`.
- `request_id`: `88cb2ec6ffdef2a025c5a738f0381a35`.
- `updated_at`: `2026-09-10T23:18:00.859433+00:00`.

The state file reports `running` and another connection owns monitoring. No
PC-side state file was read for anything beyond this diagnostic, and none was
deleted. The publisher replaces stale requests itself; deleting state while a
live owner monitors it would interfere with the run.

## Result

Stop condition fired: `A benchmark is already running.` (exit 75), meaning a
concurrently connected trigger owns monitoring of an active run. No
architecture result was produced this turn. The `harness_architectures` summary
remains 0 cases. No corpus change was made or needed.

## Decision

Stopped without retrying, without starting a second benchmark, and without
deleting any PC-side state file. No corpus change (frozen 24-case corpus, all
six test-validity revisions applied, 134 tests pass). This turn's benchmark
start was intercepted by a concurrent trigger already monitoring an active run
(state `running`, task-status up-to-date from 2026-09-10), not by a stale lock.

The operator should allow the concurrent run to complete and re-invoke the
benchmark on a later turn, or — if the run is verified to be orphaned/intended
— clear it intentionally on the PC. The frozen corpus remains validated and
ready to produce the first `typed_fill` vs `flat_fill` baseline once the PC-side
monitor is free. Three coverage-gap proposals (HPROP-0002: S-context room-mode,
HPROP-0003: mid-tier D1 distractor, HPROP-0004: S-context mixed-kind) remain
valid but require an operator-approved signed code commit to raise the frozen
corpus count from 24 before they can be promoted into `refactor-core`.

## Consequence of no data-only change

Because no corpus change is possible and no existing-case revision is justified
by evidence this turn, the suite is unchanged. The first architecture baseline
for the validated 24-case corpus is the deliverable; it will serve as the
comparison point for any future suite revision that requires operator approval
to raise the frozen corpus count.
