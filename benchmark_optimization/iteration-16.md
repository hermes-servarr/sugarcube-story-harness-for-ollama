# Iteration 16: Compact-variant suffix for SugarCube markup compliance

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 14 after, Exp15 reverted)

- Total cases: 248
- Passed: 53
- Pass rate: 0.2137 (21.37%)
- Mean score: 0.6298
- Failure category: instruction_following (195)

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 60    | 19     | 0.3167    | 0.7292     |
| full     | 96    | 6      | 0.0625    | 0.5432     |
| json     | 40    | 21     | 0.525     | 0.8208     |
| thinking | 52    | 7      | 0.1346    | 0.5282     |

## Observable Failure Behavior

The compact variant has 60 cases with 19 passes (31.67%). It has no
variant-specific suffix and relies entirely on global_suffix. Representative
failures show Markdown emphasis instead of SugarCube markup, the same pattern
that the full-variant suffix (Exp13) successfully addressed.

Exp13 showed that a concise variant-specific markup emphasis suffix helped the
full variant +4 without affecting other variants. The compact variant has
similar markup compliance failures but shorter prompts, so instruction
dilution is less severe. However, the compact variant is the second-largest
case count (60 cases) and has room to improve from 31.67%.

Prior experiments showed global_suffix changes are risky for compact (Exp09
-6, Exp11 -6, Exp15 -2). A variant-specific suffix does not modify
global_suffix and should be safe for other variants.

## Hypothesis

Adding a concise compact-variant suffix emphasizing SugarCube markup syntax
will reduce markup_compliance failures in compact-variant cases and improve
the compact variant pass rate from 19/60 (31.67%) without affecting full,
json, or thinking variants.

This uses the same approach as Exp13 (which helped full +4) but targets the
compact variant. The suffix is kept short to avoid overloading the compact
prompt's shorter context.

## Exact Overlay Change

`variants.compact` changed from empty string to:

```
Use SugarCube ''double single quotes'' for bold and //double slashes// for italic. Never use Markdown for emphasis.
```

All other fields remain unchanged:
- global_suffix retains the Exp14 content (original ordering)
- variants.full retains the Exp13 suffix
- variants.thinking retains the Exp14 suffix
- variants.json remains empty
- directions.H retains the Exp12 suffix

## Expected Affected Categories

- Compact variant markup_compliance failures (expected reduction)
- Compact variant pass rate (expected improvement from 19/60 = 31.67%)
- No expected change to full, json, thinking, or non-compact cases
- No expected change to conversation_layout or writing_style

## Rollback Condition

Revert variants.compact to empty string if:
- Aggregate objective pass rate declines below 0.2137, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
