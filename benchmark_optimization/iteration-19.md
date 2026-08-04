# Iteration 19: Thinking-variant planning emphasis suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 18 after)

- Total cases: 128
- Passed: 51
- Pass rate: 0.3984 (39.84%)
- Mean score: 0.7698

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 32    | 11     | 0.3438    | 0.7734     |
| full     | 32    | 12     | 0.375     | 0.7875     |
| json     | 32    | 22     | 0.6875    | 0.9036     |
| thinking | 32    | 6      | 0.1875    | 0.6146     |

### Thinking Variant Detail

- Cases: 32, Passed: 6, Pass rate: 18.75%, Mean score: 0.6146
- Failed evaluator categories: markup_compliance (17), thinking_quality (15),
  passage_structure (14), macro_usage (13)
- Thinking quality failures: 15 (models produce no thinking content)
- Final passage structure failures: 14

## Observable Failure Behavior

The thinking variant is the weakest at 18.75% with 15 thinking_quality
failures ("Thinking variant produced no thinking content"). Models skip
the planning section entirely.

The current variants.thinking already contains verbose plan-then-render
guidance: "Plan briefly: identify relevant variables, SugarCube macros,
and direction constraints, but reserve most of the response for the final
passage. Then produce the complete passage." Despite this, 15/32 cases
produce no thinking content.

Exp17 showed that replacing the verbose instruction with a concise one
was harmful (-4, thinking_quality failures 14 to 26). The verbose format
guidance is load-bearing. The approach here is to ADD a brief reinforcement
to the end of the existing instruction, not replace it.

The problem may be that "Plan briefly" is too weak a directive. Models
interpret "briefly" as "optionally" or "in one sentence." A stronger
directive that explicitly requires a visible planning section before the
passage may help.

## Hypothesis

Appending a concise sentence to the end of the existing thinking instruction
that explicitly requires a visible planning section before the passage will
reduce thinking_quality failures (from 15) and improve the thinking variant
pass rate from 6/32 (18.75%) without affecting compact, full, or json
variants.

This differs from Exp17 by ADDING to the existing verbose instruction rather
than replacing it. The existing format guidance is preserved. The added
text reinforces only the planning requirement.

## Exact Overlay Change

Append to the end of `variants.thinking`:

```
You must write your plan before the passage. Start with your plan, then write the passage.
```

The full variants.thinking becomes (existing content + new suffix):
```
Plan briefly: identify relevant variables, SugarCube macros, and direction constraints, but reserve most of the response for the final passage. Then produce the complete passage.

Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
PROSE:
CHOICES:
SUMMARY:

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.

When the task involves dialogue or conversation between characters, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//

You must write your plan before the passage. Start with your plan, then write the passage.
```

All other fields remain unchanged (including the Exp18 full-variant SUMMARY suffix).

## Expected Affected Categories

- thinking_quality failures (expected reduction from 15)
- thinking variant pass rate (expected improvement from 6/32 = 18.75%)
- No expected change to compact, full, json, or non-thinking cases

## Rollback Condition

Remove the planning emphasis suffix from variants.thinking if:
- Aggregate objective pass rate declines below 0.3984, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
