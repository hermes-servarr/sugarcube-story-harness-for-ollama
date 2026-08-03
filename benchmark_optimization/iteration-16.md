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

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~62 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 248     | 248     | 0     |
| Passed    | 53      | 49      | -4    |
| Pass rate | 0.2137  | 0.1976  | -1.61pp |
| Mean score| 0.6298  | 0.6156  | -0.0142 |

### By Variant

| Variant  | Before pass | After pass | Before rate | After rate | Delta |
|----------|-------------|------------|-------------|------------|-------|
| compact  | 19/60       | 15/60      | 0.3167      | 0.25       | -4    |
| full     | 6/96        | 6/96       | 0.0625      | 0.0625     | 0     |
| json     | 21/40       | 21/40      | 0.525       | 0.525      | 0     |
| thinking | 7/52        | 7/52       | 0.1346      | 0.1346     | 0     |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 11          | 12         | +1    |
| Model_B | 19          | 14         | -5    |
| Model_C | 12          | 14         | +2    |
| Model_D | 11          | 9          | -2    |

## Conclusion

Experiment 16 regressed. Aggregate declined from 53/248 (21.37%) to 49/248
(19.76%), a loss of 4 passes. The compact suffix hurt the compact variant
itself (-4, 19→15, 31.67%→25%), with mean score dropping 0.7292→0.6703.
Model_B dropped -5 (19→14).

The rollback condition fired (aggregate declined below 0.2137). The compact
suffix is reverted to empty string.

Unlike the full-variant suffix (Exp13, which helped +4), the compact-variant
markup suffix harmed the compact variant. The compact variant has shorter
prompts where the global_suffix already provides sufficient markup guidance.
Adding a variant-specific suffix creates redundancy that disrupts compact's
instruction-to-content ratio. The compact variant is at its ceiling with
global_suffix alone and does not benefit from variant-specific reinforcement.

## Rollback

Reverted variants.compact to empty string. Validated with json.tool and pytest
(53 passed). Committed and pushed. No additional GPU run needed.

## Next Decision

Both compact (Exp16) and global_suffix (Exp09, Exp11, Exp15) changes harm
compact. The compact variant is maxed out with the current global_suffix.
Future experiments should avoid compact entirely. The full variant (96 cases,
6.25%) remains the largest opportunity. Next experiment: a full-variant
suffix targeting section completeness (missing SUMMARY is the most common
passage_structure failure).
