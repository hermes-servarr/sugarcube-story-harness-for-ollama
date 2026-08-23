# Iteration 27 — Harness-suite: validate frozen corpus and attempt architecture baseline

## Mode

harness-suite

## Baseline (published anonymized result)

The published `results_anonymized.json` summary has:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet. Prior
  iterations (21-26) stopped at network-unreachable (exit 255).
- Passage-generation corpus: 128 cases, 51 passed, pass rate 0.3984,
  mean score 0.7698. Failure category: instruction_following (77).
  Thinking variant 6/32 (0.1875). This is the passage benchmark, not the
  architecture suite; recorded for context only.

## Current corpus state

The `refactor_cases.json` corpus has 24 cases. All six test-validity
revisions from earlier iterations are already applied:

- HPROP-0007 (R0-ORDINARY-FANTASY rev 2): task overclaim fix — applied.
- HPROP-0005 (R3-HUB-COPY rev 2): task overclaim fix — applied.
- HPROP-0008 (R4-STYLE-CANT rev 2): task overclaim fix — applied.
- HPROP-0006 (R8-CHOICE-DISTINCTION rev 2): task overclaim fix — applied.
- HPROP-0001 + HPROP-0009 (R2-MULTI-DIALOGUE rev 3): forbidden_terms +
  task-vs-plan slot-kind alignment — applied.

A systematic review of all 24 cases found no remaining task-vs-check
overclaims, slot-kind mismatches, or forbidden_terms inconsistencies.
No existing case needs further revision in this experiment.

The protected test `test_refactor_corpus_has_fixed_core_and_canary_sizes`
enforces `len(cases) == 24` and `select_refactor_cases(cases,
"refactor-core") == 24`. New cases (HPROP-0002, 0003, 0004) remain
proposed but cannot be added by a data-only harness-suite edit; they
require an operator-approved signed code commit to raise the frozen
corpus count.

## Failure pattern / coverage gap

The architecture benchmark has never produced per-architecture results.
The corpus covers passage modes (normal, form, loop, hub, room, random,
ending, dialogue_loop), context sizes (S, M, L, XL), tiers 0-9, and D1
distractors at T7/T9. Three coverage gaps (HPROP-0002, 0003, 0004) remain
proposed but blocked by the frozen-count assertion. No further data-only
corpus change is possible this experiment.

## Hypothesis (suite-level)

The frozen 24-case corpus, with all six test-validity revisions applied,
is validated and ready to produce the first architecture baseline across
`typed_fill` and `flat_fill`. This experiment attempts the benchmark to
capture that baseline.

## Exact suite change

No corpus change. The corpus is already in its final revised state.
Validation commands were run:

- `python -m json.tool model_benchmark/refactor_cases.json` — valid.
- `uv run python -c "from model_benchmark.refactor_benchmark import
  load_refactor_cases; load_refactor_cases()"` — passed.
- `uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py
  model_benchmark/tests/test_profiles.py
  model_benchmark/tests/test_cli_subcommands.py
  model_benchmark/tests/test_hermes_benchmark_publish.py` — 134 passed.

## Rollback condition

No corpus change to roll back. If the benchmark fails, stop and require
operator action.

## Benchmark attempt

Invoked `/run-sugarcube-benchmark` exactly once on the validated 24-case
corpus. The SSH command exited with code 255: the benchmark PC was
unreachable (connection timed out). This matches the network-unreachable
pattern from iterations 21-26. Per the goal's stop conditions, this is
a disconnect stop condition and must not be retried. Operator action
required to restore benchmark PC network connectivity.

## Result

Stop condition fired: SSH disconnect (exit 255, benchmark PC
unreachable — connection timed out). No architecture benchmark result
was produced. The `harness_architectures` summary remains 0 cases. No
corpus change was made or needed. Operator action required to restore
PC connectivity before the next benchmark attempt.

## Decision

Stopped. The frozen 24-case corpus is validated and ready for the
first architecture baseline run. The benchmark PC has been unreachable
for seven consecutive iterations (21-27). Operator action required to
restore PC network connectivity before the next scheduled benchmark
attempt.

Three coverage-gap proposals (HPROP-0002: S-context room-mode,
HPROP-0003: mid-tier D1 distractor, HPROP-0004: S-context mixed-kind)
remain valid but require an operator-approved signed code commit to
raise the frozen corpus count from 24 before they can be promoted into
`refactor-core`.
