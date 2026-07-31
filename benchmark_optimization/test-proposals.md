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

- Status: proposed
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
- Observations: none
- Operator decision: pending

## PROP-0002 — L-context conversation-layout (full variant)

- Status: proposed
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
- Observations: none
- Operator decision: pending

## PROP-0003 — K1 thinking+conversation baseline (thinking variant)

- Status: proposed
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
- Observations: none
- Operator decision: pending
