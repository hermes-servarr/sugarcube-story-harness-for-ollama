# Iteration 23 — Harness-suite: add three architecture-discriminating cases

## Mode

harness-suite

## Baseline (published anonymized result)

The published `results_anonymized.json` summary has:

- `harness_architectures`: 0 cases, empty `by_architecture`, `by_test`, `by_tier`.
  No architecture benchmark has produced a result yet. Prior iterations
  (20-22) stopped at network-unreachable.
- Passage-generation corpus: 128 cases, 51 passed, pass rate 0.3984,
  mean score 0.7698. Failure category: instruction_following (77).
  Thinking variant 6/32 (0.1875). This is the passage benchmark, not the
  architecture suite; recorded for context only.

## Current corpus state

The `refactor_cases.json` corpus has 24 cases. The six test-validity
revisions proposed in earlier iterations are already applied:

- HPROP-0007 (R0-ORDINARY-FANTASY rev 2): task overclaim fix — applied.
- HPROP-0005 (R3-HUB-COPY rev 2): task overclaim fix — applied.
- HPROP-0008 (R4-STYLE-CANT rev 2): task overclaim fix — applied.
- HPROP-0006 (R8-CHOICE-DISTINCTION rev 2): task overclaim fix — applied.
- HPROP-0001 + HPROP-0009 (R2-MULTI-DIALOGUE rev 3): forbidden_terms +
  task-vs-plan slot-kind alignment — applied.

No existing case needs further revision in this experiment.

## Failure pattern / coverage gap

The architecture benchmark has never produced per-architecture results.
The corpus covers passage modes (normal, form, loop, hub, room, random,
ending, dialogue_loop), context sizes (S, M, L, XL), tiers 0-9, and D1
distractors at T7/T9. Three coverage gaps remain that would make the
suite more informative for distinguishing `typed_fill` from `flat_fill`:

1. No S-context structured-passage-mode test. All five T3 structured-mode
   cases (form, loop, hub, room, random) use M context. At S context the
   model has minimal surrounding guidance, so the architecture's
   representation of room structure is the primary signal.
2. No mid-tier (T3-T6) D1 distractor test. D1 appears only at T7 (L, XL)
   and T9 (XL), confounding distractor resistance with large context.
3. No S-context mixed-narrative-kind (paragraph + dialogue + thought) test
   at a high tier. Multi-kind cases exist only at T2 (M, L) and T9 (XL).

## Hypothesis (suite-level)

Adding three architecture-neutral cases that probe S-context structured
modes, mid-tier distractor resistance, and S-context mixed narrative
kinds will yield interpretable per-architecture evidence without
rewarding a higher or lower pass rate. Each case is designed to
distinguish `typed_fill` from `flat_fill` for a specific, stated reason.

## Exact suite change

Add three new cases (no existing case changed):

1. `R3-S-ROOM` (HPROP-0002): T3, S context, horror fixture, D0, room
   passage mode, revision 1. Mirrors R3-ROOM-COPY but at S context.
2. `R4-M-DISTRACTOR` (HPROP-0003): T4, M context, social fixture, D1,
   normal passage mode, revision 1. Mid-tier distractor resistance with
   treaty_name needle.
3. `R6-S-MIXED-KIND` (HPROP-0004): T6, S context, modern fixture, D0,
   normal passage mode with paragraph + dialogue + thought, revision 1.

New corpus total: 27 cases.

## Rollback condition

Revert all three new cases if any fails schema validation, the
loader rejects the corpus, any test in the validation suite fails,
or `git diff --name-only` shows a path outside `refactor_cases.json`,
this iteration note, and `test-proposals.md`.

## Exact suite change

Attempted to add three new cases (R3-S-ROOM, R4-M-DISTRACTOR, R6-S-MIXED-KIND)
to `refactor_cases.json`. The protected test
`test_refactor_corpus_has_fixed_core_and_canary_sizes` in
`model_benchmark/tests/test_refactor_benchmark.py` hardcodes
`len(cases) == 24` and `select_refactor_cases(cases, "refactor-core") == 24`.
Adding cases changes the frozen `refactor-core` corpus size and fails this
protected validation. The contract doc confirms `refactor-core` is the
"frozen 24-case architecture baseline." New cases require an
operator-approved signed code commit to update the frozen-count assertion;
they cannot be added by a data-only harness-suite edit. The corpus change
was reverted.

## Result

Stop condition fired: validation failure (protected test enforces frozen
24-case corpus size). No benchmark was invoked. No corpus change was
committed. The three proposals (HPROP-0002, HPROP-0003, HPROP-0004) remain
`proposed`.

## Decision

Reverted. The three new-case proposals remain valid coverage gaps but
require an operator-approved signed code commit to promote into the
`refactor-core` corpus. No data-only harness-suite experiment can add
cases to the frozen 24-case baseline. Operator action required to either
(a) sign a code commit raising the frozen corpus count, or (b) approve a
separate candidate-test path outside `refactor-core`.
