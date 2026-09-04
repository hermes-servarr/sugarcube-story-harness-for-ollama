# Iteration 36 — Harness-suite: SSH host entry absent, stop condition fired

## Mode

harness-suite

## Baseline (published anonymized result)

The published `results_anonymized.json` summary has:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet. Prior
  iterations (21-35) stopped at network-unreachable (exit 255) or missing
  SSH host entry; iterations 32, 34, and 35 explicitly identified the
  missing `sugarcube-benchmark` host entry; iteration 33 reported a
  restoration that did not persist.
- Passage-generation corpus: 128 cases, 51 passed, pass rate 0.3984,
  mean score 0.7698. Failure category: instruction_following (77).
  Thinking variant 6/32 (0.1875). This is the passage benchmark, not the
  architecture suite; recorded for context only.

## Pre-flight checks

- `git pull --ff-only origin main`: already up to date (HEAD bdaca79).
- Trust commit 897fc29a is an ancestor of HEAD: confirmed.
- SSH config exists at `/opt/data/home/.ssh/config`: confirmed (file
  present, 398 bytes, last modified Aug 28 11:32).
- SSH config contains a `sugarcube-benchmark` host entry: **not
  confirmed**. `grep -c "sugarcube-benchmark"` returns 0. The host entry
  is absent. This is the same condition that stopped iterations 32, 34,
  and 35.
- No active matching managed processes: confirmed (process list empty).

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

No corpus change is needed. The frozen 24-case corpus, with all six
test-validity revisions applied, is validated and ready to produce the
first architecture baseline across `typed_fill` and `flat_fill`. The
blocking condition is infrastructure: the `sugarcube-benchmark` SSH host
entry is absent from the SSH config file, preventing the benchmark
trigger command from resolving the host.

## Exact suite change

No corpus change. The corpus is already in its final revised state.

## Benchmark attempt

Not attempted. Per the cron job's Step 1 verification, the SSH config
must contain a `sugarcube-benchmark` host entry before any benchmark
trigger is issued. The host entry is absent. Starting the SSH command
would result in hostname resolution failure (exit 255), matching the
pattern from iterations 21-35. Per the goal's stop conditions and the
run-sugarcube-benchmark skill's safety rules (never retry after a
disconnect; never alter the SSH hostname), no benchmark trigger was
issued.

## Result

Stop condition fired: SSH config missing `sugarcube-benchmark` host entry
(pre-flight verification failure). No architecture benchmark result was
produced. The `harness_architectures` summary remains 0 cases. No corpus
change was made or needed.

## Decision

Stopped. The frozen 24-case corpus is validated and ready for the first
architecture baseline run. The `sugarcube-benchmark` SSH host entry has
been absent from the SSH config for sixteen consecutive iterations
(21-36, with iterations 32, 34, 35, and 36 explicitly identifying the
missing entry and iteration 33 reporting a restoration that did not
persist). The SSH config file has not been modified since Aug 28 11:32.
Operator action required to add the `sugarcube-benchmark` host entry to
`/opt/data/home/.ssh/config` before the next scheduled benchmark
attempt.

Three coverage-gap proposals (HPROP-0002: S-context room-mode,
HPROP-0003: mid-tier D1 distractor, HPROP-0004: S-context mixed-kind)
remain valid but require an operator-approved signed code commit to
raise the frozen corpus count from 24 before they can be promoted into
`refactor-core`.
