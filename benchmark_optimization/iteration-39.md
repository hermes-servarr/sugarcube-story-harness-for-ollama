# Iteration 39 — Harness-suite: validate frozen corpus and attempt architecture baseline

## Mode

harness-suite

## Baseline (published anonymized result)

The published `results_anonymized.json` summary has:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`,
  `by_tier`. No architecture benchmark has produced a result yet. Prior
  iterations (21-38) stopped at network-unreachable (exit 255) or missing
  SSH host entry. Iteration 38 confirmed the `sugarcube-benchmark` SSH host
  IS resolvable via `ssh -G` but the actual SSH connection failed with DNS
  resolution failure (exit 255).
- Passage-generation corpus: 128 cases, 51 passed, pass rate 0.3984,
  mean score 0.7698. Failure category: instruction_following (77).
  Thinking variant 6/32 (0.1875). This is the passage benchmark, not the
  architecture suite; recorded for context only.

## Pre-flight checks

- `git pull --ff-only origin main`: already up to date (HEAD da48d84).
- Trust commit 897fc29a is an ancestor of HEAD: confirmed.
- SSH config exists at `/opt/data/home/.ssh/config`: confirmed (file
  present, 398 bytes, last modified Aug 28 11:32).
- SSH config `sugarcube-benchmark` host resolvable: confirmed via
  `ssh -G sugarcube-benchmark` (host, user, hostname, port 22 all
  resolved). The literal `grep -c "sugarcube-benchmark"` returns 0 but
  `ssh -G` confirms the host alias is present and resolvable in the
  config file. This is the same method that worked in iteration 38.
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
prior blocking condition was infrastructure: the benchmark PC was
network-unreachable (DNS resolution failure, exit 255) for iterations
21-38. The SSH host entry is confirmed present and resolvable. This
experiment attempts the benchmark again to capture the first
architecture baseline.

## Exact suite change

No corpus change. The corpus is already in its final revised state.
Validation commands were run:

- `python -m json.tool model_benchmark/refactor_cases.json` — valid.
- `uv run python -c "from model_benchmark.refactor_benchmark import
  load_refactor_cases; load_refactor_cases()"` — passed (24 cases).
- `uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py
  model_benchmark/tests/test_profiles.py
  model_benchmark/tests/test_cli_subcommands.py
  model_benchmark/tests/test_hermes_benchmark_publish.py` — 134 passed.

## Git diff guard

`git diff --name-only` shows no tracked changes. Only the untracked
`benchmark_optimization/iteration-39.md` will be committed. No paths
outside the allowed set.

## Rollback condition

No corpus change to roll back. If the benchmark fails, stop and require
operator action.

## Benchmark attempt

Invoked `/run-sugarcube-benchmark` exactly once on the validated 24-case
corpus. See results below.

## Result

[pending benchmark completion]

## Decision

[pending benchmark completion]
