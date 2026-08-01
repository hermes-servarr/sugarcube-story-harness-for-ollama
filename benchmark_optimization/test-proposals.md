# Capability Test Proposals

This is the review backlog for benchmark ideas. Entries here are proposals,
not executable tests, and do not affect benchmark results.

Hermes may append new proposals or update the status and observations of its
own existing proposals. It must not remove prior proposals or rewrite their
original hypothesis. A reviewed proposal may later become one data-only JSON
probe under `benchmark_optimization/candidate_tests/`; promotion into the
signed capability suite requires an operator-approved signed code commit.

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
