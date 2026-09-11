# Iteration 44 — Harness-suite: re-validate frozen corpus and attempt architecture baseline

## Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures,
seed 42 with five repetitions)

## Baseline (published anonymized result)

Published `benchmark_anon/results_anonymized.json` summary:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet.
- Passage-generation corpus (context only, not the architecture suite):
  128 cases, 51 passed, pass rate 0.3984, mean score 0.7698. Failure
  category: instruction_following (77). Thinking variant 6/32 (0.1875).
- No `typed_fill` / `flat_fill` baseline exists.

## Pre-flight checks (Steps 1-2)

- `git pull --ff-only origin main`: fast-forward 77093b5..dce51d5.
- HEAD `dce51d5e895b40d9b7349f81e0a95d552249f190` equals `origin/main`.
- SSH config exists at `/opt/data/home/.ssh/config`: confirmed
  (`sugarcube-benchmark` host entry present; contents not read).
- No active matching managed processes: confirmed (process list had no
  `sugarcube-benchmark` command; the WOL probe had exited).

## WOL pre-flight (Step 2.5)

- `/opt/data/bin/wake-windows-pc` exited 0 (magic packet sent via SSH relay).
- Waited 300 s, then probed the PC SSH port through the servarr relay
  (192.168.0.111:22): **OPEN** on the first probe. The PC is reachable.

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
enforces `len(cases) == 24` and `select_refactor_cases(cases,
"refactor-canary") == 10`. A data-only harness-suite edit therefore cannot
add the three remaining proposed cases (HPROP-0002 S-context room-mode,
HPROP-0003 mid-tier D1 distractor, HPROP-0004 S-context mixed-kind) — doing
so would fail validation. Those require an operator-approved signed code
commit to raise the frozen corpus count.

## Failure pattern / coverage gap

The architecture benchmark has never produced per-architecture results
across iterations 21-43. The connectivity blocker progressed from DNS
resolution failure, to routing/link-layer unreachability, to a stale
single-run lock (iteration 42/43, exit 75). iteration-43 investigated and
found 2 live `hermes_benchmark_task` processes and state `running`, so the
lock was genuine at that time. This turn freshly woke the PC via WOL and the
port is OPEN; the previous live run may now be complete or the state file may
be stale from a mid-run shutdown (the Step 2.4 self-heal scenario).

The frozen 24-case corpus is otherwise validated and ready to yield the first
`typed_fill` vs `flat_fill` baseline.

## Hypothesis (suite-level)

No corpus change is needed. The frozen 24-case corpus, with all six
test-validity revisions applied, is validated and ready to produce the first
architecture baseline across `typed_fill` and `flat_fill`. The remaining
blocking condition is the PC-side single-run lock; this iteration invokes the
protected benchmark once and, only if it returns exit 75, runs the scheduled
stale-state self-heal (Step 2.4) to confirm whether the lock is stale or
backed by a live run.

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

`git diff --name-only` at start of this turn showed no tracked changes
(the prior pull was clean). The only new file is the untracked
`benchmark_optimization/iteration-44.md`. No paths outside the allowed set.

## Benchmark attempt

Invoked `/run-sugarcube-benchmark` exactly once on the validated 24-case
corpus (managed process `proc_acd17f626596`, PID 37277). The SSH command
exited after a few seconds with code **75** and message
`A benchmark is already running.`

## Stale-state self-heal investigation (Step 2.4)

Because the benchmark start returned exit 75 after a fresh WOL wake, the
Step 2.4 stale-state self-heal was run before giving up:

- `task-status.json` state (via `windows-pc` alias): `running`.
- Live `hermes_benchmark_task` process count via `Get-CimInstance
  Win32_Process` (property-based `Where-Object CommandLine -match` filter):
  **2**.

A real benchmark process IS running on the PC (count > 0), so the single-run
lock is legitimate, not stale. Per the self-heal procedure, the stale state
file was NOT deleted and the benchmark was NOT retried. A live run owns the
GPU; a competing benchmark must not be started.

## Result

Stop condition fired: `A benchmark is already running.` (exit 75), and the
Step 2.4 investigation confirmed a **genuine live run** (2 live
`hermes_benchmark_task` processes, state `running`). This is the same
condition observed in iteration-43; the PC continues to hold the single-run
lock with an active benchmark. No architecture result was produced this turn.
The `harness_architectures` summary remains 0 cases. No corpus change was
made or needed.

Note on the exit-75-after-fresh-WOL interpretation: the job cautions that a
fresh WOL wake implies nothing else should own the GPU, suggesting a stale
lock. However, the Step 2.4 self-heal is the authoritative check, and it
found 2 live `hermes_benchmark_task` processes plus state `running`, so this
is a **legitimate active run**, not a stale-lock artifact. The stale state
file must not be deleted while the live processes exist.

## Decision

Stopped without retrying. No corpus change (frozen 24-case corpus, all six
test-validity revisions applied, 134 tests pass). This turn's benchmark start
was blocked by a genuine PC-side live run, not by a stale lock, so no
self-heal deletion or retry was undertaken.

The PC is currently running a benchmark (2 live `hermes_benchmark_task`
processes). Operator should either allow it to complete and re-invoke the
benchmark on a later turn, or — if the run is verified to be stuck/orphaned
PC-side — clear it intentionally on the PC before the next invocation. The
frozen corpus remains validated and ready to produce the first
`typed_fill` vs `flat_fill` baseline once the PC is available.

Three coverage-gap proposals (HPROP-0002: S-context room-mode,
HPROP-0003: mid-tier D1 distractor, HPROP-0004: S-context mixed-kind)
remain valid but require an operator-approved signed code commit to raise
the frozen corpus count from 24 before they can be promoted into
`refactor-core`.
