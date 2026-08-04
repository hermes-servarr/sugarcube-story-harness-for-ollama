# Iteration 17: Thinking-variant concise boundary suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (fresh protected baseline)

- Total cases: 128
- Passed: 46
- Pass rate: 0.3594 (35.94%)
- Mean score: 0.7612
- Failure category: instruction_following (82)

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 32    | 9      | 0.2812    | 0.7604     |
| full     | 32    | 8      | 0.25      | 0.7188     |
| json     | 32    | 22     | 0.6875    | 0.9036     |
| thinking | 32    | 7      | 0.2188    | 0.662      |

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 32    | 3      | 0.0938    | 0.6443     |
| Model_B | 32    | 17     | 0.5312    | 0.8536     |
| Model_C | 32    | 11     | 0.3438    | 0.7865     |
| Model_D | 32    | 15     | 0.4688    | 0.7604     |

### By Direction

| Direction | Cases | Passed | Pass Rate | Mean Score |
|-----------|-------|--------|-----------|------------|
| A         | 16    | 6      | 0.375     | 0.7875     |
| B         | 16    | 7      | 0.4375    | 0.7552     |
| C         | 16    | 4      | 0.25      | 0.7333     |
| D         | 16    | 6      | 0.375     | 0.7417     |
| E         | 16    | 6      | 0.375     | 0.776      |
| F         | 16    | 4      | 0.25      | 0.7312     |
| G         | 16    | 7      | 0.4375    | 0.7771     |
| H         | 16    | 6      | 0.375     | 0.7875     |

### Thinking Variant Detail

- Cases: 32, Passed: 7, Pass rate: 21.88%, Mean score: 0.662
- Failed evaluator categories: thinking_quality (14), markup_compliance (14),
  passage_structure (14), macro_usage (10)
- Thinking quality failures: 14 (models produce no thinking content)
- Final passage structure failures: 14 (no final passage after thinking)

## Observable Failure Behavior

The thinking variant is the weakest variant at 21.88%. Two dominant failure
patterns each affect 14 of 32 cases:

1. thinking_quality: "Thinking variant produced no thinking content." Models
   skip the planning section entirely and go straight to passage output or
   produce only a passage with no visible planning.

2. passage_structure: "No final passage after extracted thinking" or
   "Sections missing=['SUMMARY']" or "Empty text — no markup to evaluate."
   Models either produce only thinking with no final passage, or produce
   an incomplete passage missing required sections.

The current variants.thinking already contains verbose plan-then-render
guidance with full format instructions. Despite this, 14/32 cases produce no
thinking content and 14/32 produce no valid final passage. This suggests the
current instruction may be too long, diluting the critical boundary between
planning and final passage output.

Prior Exp14 (previous campaign) added a thinking suffix that improved +2 but
increased passage_structure failures (28 to 33), with one empty raw response
flagged as suspected output-budget exhaustion. The current baseline already
has planning guidance in variants.thinking, so adding more planning text
risks worsening budget exhaustion.

## Hypothesis

Replacing the current verbose thinking instruction with a concise suffix
that (a) requires a brief planning section, (b) explicitly marks the final
passage boundary with ===PASSAGE===, and (c) requires all three sections in
the final passage will reduce both thinking_quality failures (from 14) and
passage_structure failures (from 14), improving the thinking variant pass
rate from 7/32 (21.88%) without affecting compact, full, or json variants.

This differs from Exp14 by being concise (shorter instruction to reduce
budget pressure) and by using an explicit ===PASSAGE=== boundary marker
to separate planning from final output, rather than adding more planning
content. The concision addresses the suspected budget exhaustion.

## Exact Overlay Change

`variants.thinking` changed from the current verbose content to:

```
Plan briefly: identify relevant variables, SugarCube macros, and direction constraints. Then produce one complete passage after your plan.

===PASSAGE===
PROSE:
CHOICES:
SUMMARY:

Use SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Not Markdown.
```

All other fields remain unchanged:
- global_suffix retains the current content
- variants.compact, variants.full, variants.json remain empty
- All direction fields remain empty

## Expected Affected Categories

- thinking_quality failures (expected reduction from 14)
- thinking variant passage_structure failures (expected reduction from 14)
- thinking variant markup_compliance failures (expected reduction from 14)
- thinking variant pass rate (expected improvement from 7/32 = 21.88%)
- No expected change to compact, full, json, or non-thinking cases

## Rollback Condition

Revert variants.thinking to the baseline content if:
- Aggregate objective pass rate declines below 0.3594, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
