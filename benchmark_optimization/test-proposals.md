# Capability Test Proposals

This is the review backlog for benchmark ideas. Entries here are proposals,
not executable tests, and do not affect benchmark results.

Hermes may append new proposals or update the status and observations of its
own existing proposals. It must not remove prior proposals or rewrite their
original hypothesis. A reviewed proposal may later become one data-only JSON
probe under `benchmark_optimization/candidate_tests/`; promotion into the
signed capability suite requires an operator-approved signed code commit.

Fixed-plan harness architecture proposals use `HPROP-NNNN` IDs and may revise
existing entries or add new entries in `model_benchmark/refactor_cases.json`.
They are governed by
`skills/optimize-sugarcube-prompts/references/harness-tests.md`. A changed
corpus creates a new suite baseline; its aggregate pass rate must not be
compared with the old denominator as an improvement claim.

## Status Values

- `proposed`: idea recorded but not yet implemented.
- `candidate`: implemented as a diagnostic candidate probe.
- `observed`: at least one anonymized candidate result recorded.
- `recommended`: evidence supports operator review for canonical promotion.
- `rejected`: unsafe, redundant, non-deterministic, or not informative.

## Proposal Template

Copy this section for each new proposal. Use the next unused sequential ID.

```markdown
## PROP-0001 — Short descriptive title

- Status: proposed
- Proposed in iteration: iteration-NN
- Capability: syntax | state | branching | loops | forms | conversation-layout
  | conversation-length | retrieval | distractor-resistance | consistency |
  harness-scale | thinking
- Context size: S | M | L | XL
- Task complexity: K1 | K2 | K3 | K4
- Distractor density: D0 | D1
- Variant: compact | full | json | thinking
- Response mode: passage | plain_text
- Output budget: tiny | short | medium | standard
- Paired control: PROP-ID or `needed`
- Hypothesis: One falsifiable capability claim.
- Controlled change: The single axis changed relative to the paired control.
- Required observable behavior: Externally visible behavior only.
- Deterministic checks: Signed check primitives from the candidate-test schema.
- Why existing tests are insufficient: The ambiguity this proposal resolves.
- Resource estimate: Expected extra sequential model calls and context size.
- Safety notes: Privacy, prompt-injection, or output-budget considerations.
- Candidate file: none
- Observations: none
- Operator decision: pending
```

## Proposals

## Harness Proposal Template

```markdown
## HPROP-0001 — Short title

- Status: proposed
- Proposed in iteration: iteration-NN
- Action: revise CASE-ID | add NEW-CASE-ID
- Coverage gap: Missing or ambiguous behavior.
- Competing structures: Harness approaches this test may distinguish.
- Hypothesis: One falsifiable architecture-level claim.
- Controlled inputs: Context, plan authority, seed, budget, and model pairing.
- Observable outcomes: Architecture-neutral request-level behaviors.
- Existing-case changes: Exact fields and revision increment, or `none`.
- New cases: IDs and purpose, or `none`.
- Why current corpus is insufficient: Concrete ambiguity or missing coverage.
- Resource estimate: cases × architectures × models × seeds.
- Rejection conditions: Invalid, redundant, unstable, biased, or non-discriminating.
- First suite baseline: pending
```

## PROP-0001 — K1 conversation-layout baseline (full variant)

- Status: observed
- Proposed in iteration: pre-optimization
- Capability: conversation-layout
- Context size: M
- Task complexity: K1
- Distractor density: D0
- Variant: full
- Response mode: passage
- Output budget: standard
- Paired control: T3-CONVERSATION-FULL (M-K2-D0, full)
- Hypothesis: If conversation-layout checks (mc_inner_monologue, conversation_layout, min_dialogue_turns) fail at K1 complexity, the 0% conversation pass rate is pure format-compliance and prompt-overlay optimization is the correct tool. If they pass at K1, task complexity interacts with conversation formatting and the overlay must address that interaction.
- Controlled change: Task complexity K2 to K1, holding context size M, distractor D0, and variant full constant.
- Required observable behavior: Externally visible SugarCube passage with DIALOGUE/INNER MONOLOGUE blocks and CHOICES.
- Deterministic checks: conversation_layout, min_dialogue_turns (4), mc_inner_monologue, min_choices (2), no_markdown.
- Why existing tests are insufficient: All 80 conversation-layout cases use K2 or higher complexity. No K1 conversation baseline exists to isolate format compliance from task complexity.
- Resource estimate: 8 sequential model calls (one per model alias) at M context.
- Safety notes: Diagnostic-only, excluded from pass-rate. No model identities, raw output, or private data.
- Candidate file: CAND-T3-CONVERSATION-K1-01.json
- Observations: 2026-08-01, first result, 3 model aliases, local capability run.
  Probe (M-K1-D0): 0/3 aliases pass all checks; conversation_layout 2/3,
  min_choices 2/3, no_markdown 3/3, min_dialogue_turns 0/3,
  mc_inner_monologue 0/3. Control (see caveat) : conversation_layout 1/3,
  min_choices 3/3, no_markdown 3/3, sections 3/3, min_dialogue_turns 0/3,
  mc_inner_monologue 0/3. Lowering task complexity recovered no
  conversation-layout check: min_dialogue_turns and mc_inner_monologue are
  0/3 at both complexities. This supports the first branch of the stated
  hypothesis, that the conversation failure is format compliance rather than
  task complexity. Caveat: the paired control T3-CONVERSATION-FULL is
  actually M-K3-D0, not M-K2-D0 as recorded above, so the observed
  controlled change is K3 to K1. See Operator Notes for the provisioning
  caveat that limits how far this reading can be taken.
- Operator decision: pending

## PROP-0002 — L-context conversation-layout (full variant)

- Status: observed
- Proposed in iteration: pre-optimization
- Capability: conversation-layout
- Context size: L
- Task complexity: K3
- Distractor density: D0
- Variant: full
- Response mode: passage
- Output budget: standard
- Paired control: T8-CONVERSATION-XL (XL-K3-D0, full)
- Hypothesis: If L-K3 conversation-layout compliance is significantly better than XL-K3, the XL conversation failure has a context-length component. If equally poor, it is pure format compliance.
- Controlled change: Context size XL to L, holding task complexity K3, distractor D0, and variant full constant.
- Required observable behavior: Externally visible SugarCube passage with DIALOGUE/INNER MONOLOGUE blocks, alternating dialogue, and CHOICES.
- Deterministic checks: conversation_layout, min_dialogue_turns (4), mc_inner_monologue, min_choices (2), alternating_dialogue, no_markdown.
- Why existing tests are insufficient: Conversation tests exist at S, M, and XL context but not L. The S-to-XL slope has a gap at L, preventing localization of where context length begins degrading layout compliance.
- Resource estimate: 8 sequential model calls at L context.
- Safety notes: Diagnostic-only, excluded from pass-rate. No model identities, raw output, or private data.
- Candidate file: CAND-T8-CONVERSATION-L-01.json
- Observations: 2026-08-01, first result, 3 model aliases, local capability run.
  Probe (L-K3-D0): 0/3 aliases pass all checks; min_choices 3/3,
  no_markdown 3/3, conversation_layout 1/3, min_dialogue_turns 0/3,
  mc_inner_monologue 0/3, alternating_dialogue 0/3. Control defect: the
  paired control T8-CONVERSATION-XL is actually XL-K3-D1, not XL-K3-D0 as
  recorded above, so that comparison moves context size and distractor
  density together and cannot attribute a difference to either. No XL-K3-D0
  conversation case exists in the ladder, so the control as specified is
  unavailable. Clean substitute leg used instead: T3-CONVERSATION-FULL is
  M-K3-D0, giving a single-axis M to L context comparison. Result: the
  per-check profile is identical between M and L (conversation_layout 1/3,
  min_dialogue_turns 0/3, mc_inner_monologue 0/3), so no context-length
  effect on conversation layout was detected between M and L. On the
  confounded L to XL leg the conversation checks are likewise unchanged;
  only context_needle (2/3) and no_markdown (2/3) differ. This supports the
  second branch of the stated hypothesis, that the failure is pure format
  compliance rather than context length. See Operator Notes for the
  provisioning caveat.
- Operator decision: pending

## PROP-0003 — K1 thinking+conversation baseline (thinking variant)

- Status: observed
- Proposed in iteration: pre-optimization
- Capability: conversation-layout | thinking
- Context size: S
- Task complexity: K1
- Distractor density: D0
- Variant: thinking
- Response mode: passage
- Output budget: standard
- Paired control: T3-CONVERSATION-THINKING-S (S-K2-D0, thinking)
- Hypothesis: If thinking+conversation still fails mc_inner_monologue at K1, the thinking variant's final-passage formatting is fundamentally broken for conversation layout regardless of task difficulty. If it passes, existing failures are complexity-aggravated and the overlay should add thinking-specific conversation guidance.
- Controlled change: Task complexity K2 to K1, holding context size S, distractor D0, and variant thinking constant.
- Required observable behavior: Externally visible SugarCube passage with DIALOGUE/INNER MONOLOGUE blocks and CHOICES after a thinking section.
- Deterministic checks: conversation_layout, min_dialogue_turns (4), mc_inner_monologue, min_choices (2), no_markdown.
- Why existing tests are insufficient: All three thinking+conversation tests (T3-S, T6-M, T9-XL) use K2 or higher and score 0% pass. No K1 thinking+conversation baseline exists to isolate thinking-mode formatting from task complexity.
- Resource estimate: 8 sequential model calls at S context with thinking mode.
- Safety notes: Diagnostic-only, excluded from pass-rate. Never inspect or reproduce chain-of-thought. Record only category-level failure counts.
- Candidate file: CAND-T3-CONVERSATION-THINKING-K1-01.json
- Observations: 2026-08-01, first result, 3 model aliases, local capability run.
  Probe (S-K1-D0, thinking): 0/3 aliases pass all checks; no_markdown 3/3,
  conversation_layout 1/3, min_choices 1/3, min_dialogue_turns 0/3,
  mc_inner_monologue 0/3. Control T3-CONVERSATION-THINKING-S (S-K2-D0,
  thinking; cell matches as recorded): no_markdown 3/3,
  conversation_layout 1/3, min_choices 3/3, min_dialogue_turns 0/3,
  mc_inner_monologue 0/3. mc_inner_monologue and min_dialogue_turns remain
  0/3 at K1, which supports the first branch of the stated hypothesis, that
  thinking-variant final-passage formatting is not recovered by lowering
  task difficulty. min_choices was lower on the probe (1/3) than the control
  (3/3); at 3 samples this is not separable from noise and is recorded as an
  observation only, not a regression. No chain-of-thought was inspected or
  reproduced; only category-level counts are recorded. See Operator Notes
  for the provisioning caveat.
- Operator decision: pending

## HPROP-0001 — Fix R2-MULTI-DIALOGUE thought-slot forbidden_terms consistency

- Status: proposed
- Proposed in iteration: iteration-01
- Action: revise R2-MULTI-DIALOGUE
- Coverage gap: Inconsistent forbidden_terms across thought-slot cases.
- Competing structures: All architectures — this is a test-validity fix, not architecture-discriminating.
- Hypothesis: Adding "INNER MONOLOGUE:" to R2-MULTI-DIALOGUE forbidden_terms will close the consistency gap with R2-DIALOGUE-THOUGHT and R9-LONG-DIALOGUE, preventing false passes where a model emits the literal thought label.
- Controlled inputs: Same context (L), plan, seed, budget, and model pairing; only forbidden_terms changed.
- Observable outcomes: Architecture-neutral request-level semantic check: the literal string "INNER MONOLOGUE:" must not appear in the fill text.
- Existing-case changes: R2-MULTI-DIALOGUE forbidden_terms: add "INNER MONOLOGUE:"; plan revision 1 to 2.
- New cases: none
- Why current corpus is insufficient: R2-MULTI-DIALOGUE has a player_thought slot but only forbids "DIALOGUE:", while the two other thought-slot cases forbid both "DIALOGUE:" and "INNER MONOLOGUE:". A model emitting the literal label would pass R2-MULTI-DIALOGUE but fail the others, creating an inconsistent signal.
- Resource estimate: no additional model calls (revision of existing case).
- Rejection conditions: If the revision causes a validation failure or breaks plan-adherence pairing.
- First suite baseline: pending

## HPROP-0005 — Fix R3-HUB-COPY task-vs-check overclaim

- Status: proposed
- Proposed in iteration: iteration-01
- Action: revise R3-HUB-COPY
- Coverage gap: Task overclaims what the distinct_choices check enforces.
- Competing structures: All architectures — this is a test-validity fix.
- Hypothesis: Changing the task from "three clearly distinct" to "three distinct" will accurately reflect what the distinct_choices semantic check enforces (casefolded string distinctness of choice texts), preventing suite consumers from over-interpreting the check as enforcing semantic or hint-level distinctness.
- Controlled inputs: Same context, plan, seed, budget, and model pairing; only task text changed.
- Observable outcomes: Same as before — distinct_choices check on choice texts.
- Existing-case changes: R3-HUB-COPY task: "three clearly distinct" to "three distinct"; plan revision 1 to 2.
- New cases: none
- Why current corpus is insufficient: The task said "clearly distinct" which implies a stronger semantic requirement than the check enforces.
- Resource estimate: no additional model calls.
- Rejection conditions: If the revision causes a validation failure.
- First suite baseline: pending

## HPROP-0006 — Fix R8-CHOICE-DISTINCTION task-vs-check overclaim

- Status: proposed
- Proposed in iteration: iteration-01
- Action: revise R8-CHOICE-DISTINCTION
- Coverage gap: Task overclaims what the distinct_choices check enforces.
- Competing structures: All architectures — this is a test-validity fix.
- Hypothesis: Changing the task from "Their labels and hints must be meaningfully distinct" to "with distinct labels" will accurately reflect what the distinct_choices semantic check enforces (casefolded string distinctness of choice texts only), preventing suite consumers from expecting hint-level or semantic-meaning distinctness that is not checked.
- Controlled inputs: Same context, plan, seed, budget, and model pairing; only task text changed.
- Observable outcomes: Same as before — distinct_choices check on choice texts.
- Existing-case changes: R8-CHOICE-DISTINCTION task: remove "Their labels and hints must be meaningfully distinct"; plan revision 1 to 2.
- New cases: none
- Why current corpus is insufficient: The task claimed labels AND hints must be "meaningfully" distinct, but the check only verifies choice texts are distinct (casefolded). Hint distinctness and semantic meaning are not checked.
- Resource estimate: no additional model calls.
- Rejection conditions: If the revision causes a validation failure.
- First suite baseline: pending

## HPROP-0002 — S-context room-mode architecture discrimination test

- Status: proposed
- Proposed in iteration: iteration-01
- Action: add R3-S-ROOM
- Coverage gap: No S-context structured passage mode test exists. All five T3 cases (form, loop, hub, room, random) use M context.
- Competing structures: typed_fill (explicit narrative-block AST) vs flat_fill (slot-keyed JSON strings). At S context the model has minimal surrounding guidance, so the architecture's representation of room structure (fixed exits + local choices) is the primary signal the model receives.
- Hypothesis: At S context with room mode, typed_fill and flat_fill will show different plan-adherence rates because the structured AST representation conveys exit and slot constraints more explicitly than flat slot-keyed strings when context is minimal.
- Controlled inputs: S context, horror fixture, D0 distractors, room passage mode, seed 42 with 5 runs, same model pairing across architectures.
- Observable outcomes: Plan adherence (slot IDs, slot kinds, exit components), fill completeness (narrative + choices + summary + beats), semantic observables (required term "room", forbidden SugarCube link syntax, min_words, distinct_choices).
- Existing-case changes: none
- New cases: R3-S-ROOM (T3, S, horror, D0, room mode, revision 1)
- Why current corpus is insufficient: All structured-passage-mode tests (T3: form, loop, hub, room, random) use M context. No test measures architecture behavior at S context where schema guidance is minimal.
- Resource estimate: 1 case x 2 architectures x 4 models x 5 runs = 40 additional model calls at S context.
- Rejection conditions: If the test produces identical pass rates and scores across both architectures with zero per-case variance, it does not discriminate and should be reverted.
- First suite baseline: pending

## HPROP-0003 — Mid-tier D1 distractor-resistance test

- Status: proposed
- Proposed in iteration: iteration-01
- Action: add R4-M-DISTRACTOR
- Coverage gap: D1 distractor density only appears at T7 (L, XL) and T9 (XL). No mid-tier (T3-T6) distractor test exists.
- Competing structures: typed_fill vs flat_fill under distractor pressure at moderate complexity. Distractor injection attempts to add a slot and emit SugarCube syntax; architecture representation determines how clearly the trusted plan boundary is conveyed.
- Hypothesis: At M context with D1 distractors and moderate task complexity, architecture pass rates will differ because the trusted plan's slot boundary is conveyed differently by the AST (typed_fill) vs slot-keyed strings (flat_fill). This isolates distractor resistance from large-context compounding.
- Controlled inputs: M context, social fixture, D1 distractors, normal passage mode, treaty_name context needle, seed 42 with 5 runs, same model pairing.
- Observable outcomes: Plan adherence (no extra slots from distractor), semantic observables (treaty_name needle present, distractor terms absent, min_words, distinct_choices).
- Existing-case changes: none
- New cases: R4-M-DISTRACTOR (T4, M, social, D1, normal mode, revision 1)
- Why current corpus is insufficient: Distractor tests only exist at T7+ with L/XL context. No test isolates distractor resistance at moderate complexity without the confound of large context.
- Resource estimate: 1 case x 2 architectures x 4 models x 5 runs = 40 additional model calls at M context.
- Rejection conditions: If the test does not distinguish architectures (identical results) or if the distractor injection is trivially rejected by both architectures with zero variance.
- First suite baseline: pending

## HPROP-0004 — S-context multi-kind narrative architecture test

- Status: proposed
- Proposed in iteration: iteration-01
- Action: add R6-S-MIXED-KIND
- Coverage gap: No S-context case tests mixed narrative kinds (paragraph + dialogue + thought) at a high tier. Existing multi-kind cases are at T2 (M, L) and T9 (XL).
- Competing structures: typed_fill (explicit narrative-block AST with kind discrimination) vs flat_fill (slot-keyed JSON strings). Mixed narrative kinds stress the architecture's ability to convey slot kind and speaker assignments. At S context this is the primary structural signal.
- Hypothesis: At S context with mixed narrative kinds (paragraph, dialogue with speaker, thought), typed_fill and flat_fill will show different plan-adherence rates because the AST explicitly encodes kind and speaker per block while flat slot-keyed strings may lose this structure at minimal context.
- Controlled inputs: S context, modern fixture, D0 distractors, normal passage mode with paragraph + dialogue + thought slots, seed 42 with 5 runs, same model pairing.
- Observable outcomes: Plan adherence (slot IDs, slot kinds, speaker assignment), fill completeness (all slots filled + summary + beats), semantic observables (required term, forbidden literal labels, min_words, distinct_choices, no_markup_code).
- Existing-case changes: none
- New cases: R6-S-MIXED-KIND (T6, S, modern, D0, normal mode, revision 1)
- Why current corpus is insufficient: Multi-kind narrative tests (dialogue + thought) only exist at T2 (M, L context) and T9 (XL context). No high-tier S-context test isolates architecture handling of mixed kinds at minimal context.
- Resource estimate: 1 case x 2 architectures x 4 models x 5 runs = 40 additional model calls at S context.
- Rejection conditions: If the test produces identical results across both architectures or if slot-kind or speaker plan-adherence is trivially perfect in both, it does not discriminate.
- First suite baseline: pending

## HPROP-0007 — Fix R0-ORDINARY-FANTASY task-vs-check overclaim

- Status: observed
- Proposed in iteration: iteration-19
- Action: revise R0-ORDINARY-FANTASY
- Coverage gap: Task overclaims what the distinct_choices check enforces.
- Competing structures: All architectures — this is a test-validity fix.
- Hypothesis: Changing the task from "two materially different" to "two distinct" will accurately reflect what the distinct_choices semantic check enforces (casefolded string distinctness of choice texts only), preventing suite consumers from over-interpreting the check as enforcing semantic-content distinctness.
- Controlled inputs: Same context, plan, seed, budget, and model pairing; only task text changed.
- Observable outcomes: Same as before — distinct_choices check on choice texts.
- Existing-case changes: R0-ORDINARY-FANTASY task: "two materially different" to "two distinct"; plan revision 1 to 2.
- New cases: none
- Why current corpus is insufficient: The task said "materially different" which implies a stronger semantic requirement than the check enforces. This is the same class of overclaim fixed in iteration-01 for R3-HUB-COPY and R8-CHOICE-DISTINCTION.
- Resource estimate: no additional model calls (revision of existing case).
- Rejection conditions: If the revision causes a validation failure.
- First suite baseline: pending; the architecture benchmark has not yet produced a result across 10 attempts due to persistent network unreachability.

## HPROP-0009 — Fix R2-MULTI-DIALOGUE task-vs-plan slot-kind mismatch

- Status: proposed
- Proposed in iteration: iteration-21
- Action: revise R2-MULTI-DIALOGUE
- Coverage gap: Task text mislabels the 6th narrative slot as a dialogue slot when the plan defines it as a thought slot (player_thought, kind=thought, no speaker). Task says "six alternating fixed-speaker dialogue slots" but plan has 5 dialogue + 1 thought.
- Competing structures: All architectures — this is a test-validity fix. The task-vs-plan mismatch could cause false plan-adherence failures in both typed_fill and flat_fill since both derive slot expectations from the same trusted plan.
- Hypothesis: Aligning the task text to say "five alternating fixed-speaker dialogue slots and one private thought" will match the plan's actual slot composition (5 dialogue + 1 thought), preventing task-text-induced plan-adherence failures. This mirrors the accurate descriptions in R2-DIALOGUE-THOUGHT ("dialogue turns and private thought") and R9-LONG-DIALOGUE ("eight fixed alternating dialogue slots and one thought slot").
- Controlled inputs: Same context (L), plan, seed, budget, and model pairing; only task text changed.
- Observable outcomes: Architecture-neutral request-level plan adherence: slot IDs, slot kinds, and speaker assignments should match the plan. A model following the revised task text should produce 5 dialogue slots with speakers + 1 thought slot, matching the plan.
- Existing-case changes: R2-MULTI-DIALOGUE task: "six alternating fixed-speaker dialogue slots" to "five alternating fixed-speaker dialogue slots and one private thought"; plan revision 2 to 3.
- New cases: none
- Why current corpus is insufficient: R2-MULTI-DIALOGUE is the only dialogue-plus-thought case that mislabels the thought slot as a dialogue slot in the task text. R2-DIALOGUE-THOUGHT and R9-LONG-DIALOGUE both correctly distinguish dialogue from thought. A model following the task literally would write 6 speaker-tagged dialogue lines and fail plan adherence for the 6th slot.
- Resource estimate: no additional model calls (revision of existing case).
- Rejection conditions: If the revision causes a validation failure or breaks plan-adherence pairing.
- First suite baseline: pending

## HPROP-0008 — Fix R4-STYLE-CANT task-vs-check overclaim

- Status: proposed
- Proposed in iteration: iteration-20
- Action: revise R4-STYLE-CANT
- Coverage gap: Task overclaims what the required_terms check enforces by specifying slot placement ("only in spoken dialogue") that no deterministic check verifies.
- Competing structures: All architectures — this is a test-validity fix.
- Hypothesis: Changing the task from "Use chrome-cold and wired-in only in spoken dialogue" to "Use chrome-cold and wired-in in the spoken dialogue lines" will accurately reflect what the required_terms semantic check enforces (casefolded substring presence anywhere in the fill text), preventing suite consumers from over-interpreting "only" as enforcing slot-placement or register-leakage detection that the check does not perform.
- Controlled inputs: Same context, plan, seed, budget, and model pairing; only task text changed.
- Observable outcomes: Same as before — required_terms check for substring presence of "chrome-cold" and "wired-in".
- Existing-case changes: R4-STYLE-CANT task: "Use chrome-cold and wired-in only in spoken dialogue" to "Use chrome-cold and wired-in in the spoken dialogue lines"; plan revision 1 to 2.
- New cases: none
- Why current corpus is insufficient: The task said "only in spoken dialogue" which implies the check enforces that the required terms appear exclusively in dialogue slots and not in the narration slot. The required_terms check only verifies casefolded substring presence anywhere in the fill text; it does not check which slot the terms appear in. The word "only" overclaims slot-placement enforcement. This is the same class of task-vs-check overclaim fixed in iteration-01 (R3-HUB-COPY, R8-CHOICE-DISTINCTION) and iteration-19 (R0-ORDINARY-FANTASY), applied to the register-placement axis.
- Resource estimate: no additional model calls (revision of existing case).
- Rejection conditions: If the revision causes a validation failure.
- First suite baseline: pending

## Operator Notes

Added by the operator, not by Hermes. These notes record run provenance and
caveats that apply to all three observations above. They do not alter any
proposal's original hypothesis.

### Run provenance

- Date: 2026-08-01. Output: `benchmark_outputs/20260731_234130_84f20528`.
- 3 model aliases, 1 repetition, 41 capability cases plus 1 generation case
  per alias (126 records). Overall pass rate 5.6%, unchanged from the
  pre-optimization baseline of 5.56%.
- The prompt overlay was empty for this run, so these are baseline
  observations, not the result of an overlay experiment.

### Probe validity was checked before the run

Each of the three probes was scored against a hand-written ideal response and
passed every check (5/5, 5/5, 6/6). Observed failures are therefore
attributable to model output, not to an over-strict check.

### Why the conversation checks fail

Across the 30 non-thinking conversation cases in this run, the dominant
failure is upstream of dialogue formatting: 24 of 30 emitted no `DIALOGUE:`
block at all. Breakdown by kind:

| Kind | Cases |
|------|-------|
| Narrative prose with quoted speech, but no `DIALOGUE:`/`INNER MONOLOGUE:` labels | 10 |
| Prompt analysis or meta-commentary emitted as PROSE | 10 |
| Narrative prose with no quoted speech | 4 |
| `DIALOGUE:` block present but no speaker-quote lines | 4 |
| 4+ turns present but comma delimiter instead of the signed colon | 1 |
| Too few turns | 1 |

The mismatch is convention adoption, not a near-miss on punctuation: the
comma-delimiter case that a small sample first suggested is a 1-of-30 tail.
This pattern is invariant across K1 and K3 and across S, M, L, and XL, which
is the shared basis for all three observations above.

### Provisioning caveat: chat templates are inconsistent

Model provisioning is not uniform across the local Ollama roster, and the
benchmark does not currently record it. The roster contains both models with
a bare `{{ .Prompt }}` passthrough template and models with a real chat
template. Two consequences:

1. One of the three aliases in this run was a bare-template model. Its
   signature (narrative prose with unlabeled quoted speech) is what
   raw-completion behavior looks like when no instruct formatting is applied,
   so part of the conversation-layout failure for that alias is a
   provisioning artifact rather than a capability result. The other two
   aliases carry full chat templates, so their failures, including the
   analysis-leaked-into-PROSE mode, are not explained by a missing template.
2. Provisioning differs *within* one model family: two quantizations of one
   family are bare while four others share an identical template. A
   quantization comparison across that family would conflate quantization
   with template presence.

Until template provenance is recorded per model in the run manifest, treat
cross-model conversation-layout comparisons as provisional. None of the three
proposals should move to `recommended` on this run alone.
