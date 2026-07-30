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
- Capability: syntax | state | branching | loops | forms | retrieval |
  distractor-resistance | consistency | harness-scale | thinking
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

No proposals recorded yet.
