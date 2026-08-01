# Iteration 03: Move markup/passage instructions to variant suffixes, keep conversation layout in global_suffix

## Baseline Metrics (current best = Experiment 02 after)

- Total cases: 1330
- Passed: 308
- Pass rate: 0.2316 (23.16%)
- Mean score: 0.6874
- Campaign baseline: 0.2150 (21.50%)
- Target: 0.2650 (26.50%)

### By Variant (current best)

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 285   | 89     | 0.3123    | 0.7311     |
| full       | 456   | 16     | 0.0351    | 0.6631     |
| json       | 190   | 93     | 0.4895    | 0.8658     |
| plain_text | 152   | 101    | 0.6645    | 0.6645     |
| thinking   | 247   | 9      | 0.0364    | 0.5589     |

### By Model Alias (current best, selected)

| Alias    | Cases | Passed | Pass Rate | Delta from campaign baseline |
|----------|-------|--------|-----------|-------------------------------|
| Model_A  | 70    | 9      | 0.1286    | -6 (regressed from 15)        |
| Model_B  | 70    | 15     | 0.2143    | -8 (regressed from 23)        |
| Model_C  | 70    | 10     | 0.1429    | -5 (regressed from 15)        |
| Model_D  | 70    | 23     | 0.3286    | +2                            |
| Model_E  | 70    | 28     | 0.4000    | +13                           |
| Model_G  | 70    | 30     | 0.4286    | +6                           |
| Model_S  | 70    | 16     | 0.2286    | -2 (regressed from 18)        |

### Conversation Layout (current best)

- Cases: 209, Passed: 8, Pass rate: 3.83%
- compact: 5/19, full: 0/114, json: 0/19, thinking: 3/57
- mc_inner_monologue: 163, conversation_layout: 90, min_dialogue_turns: 110

### Writing Style (current best)

- Cases: 95, Passed: 2, Pass rate: 2.11%

### Thinking Variant (current best)

- Cases: 247, Passed: 9, Pass rate: 3.64%
- passage_structure: 150, markup_compliance: 167, thinking_quality: 0

## Failure Pattern

Experiment 02 showed that adding SugarCube markup and passage-section instructions
to global_suffix improved compact (+35 passes) and thinking (+6) but caused
regressions in json (-11 passes, 54.74% -> 48.95%) and full (-8 passes, 5.26% ->
3.51%). The json variant likely interprets the ===CHOICES=== etc. section
instructions as conflicting with JSON output structure. The full variant may
be receiving conflicting formatting guidance that disrupts its existing
output patterns.

Per-alias regressions: Model_A (-6), Model_B (-8), Model_C (-5), Model_S (-2)
suggest these aliases are disproportionately affected by the global markup
instructions, possibly because their output formats were closer to passing
and the added instructions shifted them away from their working format.

## Behavior

The global_suffix instructions helped variants that had no strong formatting
constraints (compact, thinking) but hurt variants that already had implicit
format expectations (json needs JSON output, full has its own passage format).
The conversation layout guidance is applicable across all variants and does
not conflict with format-specific expectations.

## Hypothesis

Moving the SugarCube markup and passage-structure instructions from
global_suffix to the compact and thinking variant-specific suffixes will:
1. Recover the json variant regression (back toward 54.74%) by removing
   conflicting section instructions.
2. Recover the full variant regression (back toward 5.26%) by removing
   conflicting markup instructions.
3. Preserve the compact variant gains (toward 31.23%) by keeping the markup
   and passage-structure instructions in the compact suffix.
4. Preserve or improve the thinking variant gains (toward 3.64%) by keeping
   the markup and passage-structure instructions in the thinking suffix.
5. Keep the conversation layout improvement by retaining only the conversation
   layout guidance in global_suffix.

This is the smallest instruction change that addresses the regressions while
preserving the gains. It separates format-specific guidance (markup, sections)
from cross-variant guidance (conversation layout).

## Exact Overlay Change

1. `global_suffix` changed to contain ONLY the conversation layout guidance:

```
When the task requests a conversation scene, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

2. `variants.compact` changed from empty to:

```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

3. `variants.thinking` changed from empty to the same as compact:

```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

4. `variants.full` and `variants.json` remain empty.
5. All direction-specific fields remain empty.

## Expected Affected Categories

- json variant pass rate (expected recovery toward 54.74%)
- full variant pass rate (expected recovery toward 5.26%)
- compact variant pass rate (expected to hold at ~31.23%)
- thinking variant pass rate (expected to hold at ~3.64% or improve)
- conversation_layout and mc_inner_monologue (expected to hold or improve)
- per-alias regressions for Model_A, Model_B, Model_C, Model_S (expected recovery)

## Rollback Condition

Revert to the Experiment 02 overlay (all instructions in global_suffix, all
variant suffixes empty) if:
- Aggregate objective pass rate declines below 0.2316 (the current best), or
- Any per-variant pass rate declines below its Experiment 02 after value without
  offsetting gains elsewhere, or
- Any material per-alias regression beyond what was already observed in
  Experiment 02.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~170 minutes.

### Aggregate

| Metric    | Exp02 (best) | Exp03   | Delta |
|-----------|-------------|---------|-------|
| Cases     | 1330         | 1330    | 0     |
| Passed    | 308          | 301     | -7    |
| Pass rate | 0.2316       | 0.2263  | -0.53pp |
| Mean score| 0.6874       | 0.6859  | -0.0015 |

### By Variant

| Variant    | Exp02 pass | Exp03 pass | Delta |
|------------|------------|------------|-------|
| compact    | 89/285     | 79/285     | -10 (REGRESSION) |
| full       | 16/456     | 10/456     | -6 (REGRESSION) |
| json       | 93/190     | 99/190     | +6    |
| plain_text | 101/152    | 101/152    | 0     |
| thinking   | 9/247      | 12/247     | +3    |

### By Model Alias (deltas from Exp02)

| Alias    | Exp02 | Exp03 | Delta |
|----------|-------|-------|-------|
| Model_A  | 9     | 13    | +4    |
| Model_B  | 15    | 15    | 0     |
| Model_C  | 10    | 11    | +1    |
| Model_D  | 23    | 24    | +1    |
| Model_E  | 28    | 28    | 0     |
| Model_F  | 22    | 22    | 0     |
| Model_G  | 30    | 26    | -4 (REGRESSION) |
| Model_H  | 25    | 25    | 0     |
| Model_I  | 17    | 20    | +3    |
| Model_J  | 26    | 22    | -4 (REGRESSION) |
| Model_K  | 24    | 21    | -3 (REGRESSION) |
| Model_L  | 24    | 23    | -1    |
| Model_M  | 27    | 20    | -7 (REGRESSION) |
| Model_S  | 16    | 18    | +2    |

### Conversation Layout

| Metric           | Exp02 | Exp03 |
|------------------|-------|-------|
| Passed            | 8/209 | 3/209 |
| compact          | 5/19  | 1/19  |
| thinking         | 3/57  | 2/57  |

### Thinking Variant

| Metric           | Exp02 | Exp03 |
|------------------|-------|-------|
| Passed            | 9/247 | 12/247 |
| passage_structure | 150   | 153   |
| thinking_quality  | 0     | 1     |

## Conclusion

Experiment 03 regressed the aggregate from 308 (23.16%) to 301 (22.63%), a
decline of 7 passes (-0.53pp). The variant-split hypothesis was partially
correct for json (+6, recovering toward baseline 104) and thinking (+3), but
the compact variant dropped 10 passes (89->79) and the full variant dropped 6
more (16->10, now well below the baseline of 24). Conversation layout also
dropped from 8 to 3.

The compact regression suggests that moving the markup instructions from
global_suffix to the compact variant suffix changed how the instructions
interact with the variant's prompt framework. The global_suffix position
applies the instructions in a different context than the variant suffix,
and the compact variant may depend on the global context for formatting
guidance more than expected.

Per-alias regressions: Model_G (-4), Model_J (-4), Model_K (-3), Model_M (-7).
Model_M's -7 is material. The overlay is reverted to the Experiment 02
configuration (all instructions in global_suffix, all variant suffixes empty),
which was the verified best at 308/1330 (23.16%).

No additional GPU run is needed for the byte-for-byte restored overlay.

## Rollback

Reverted to Experiment 02 overlay: all formatting instructions in
global_suffix, all variant suffixes empty. Validated with json.tool and
pytest (53 passed). Committed and pushed.

## Next Decision

The campaign has completed 2 experiments (Exp02 improved, Exp03 regressed and
was reverted). The best aggregate is 308/1330 (23.16%). Target is 26.50%.

Next experiment should target the full variant (456 cases, 3.51% pass in Exp02),
which is the largest case count and the worst non-thinking pass rate. The full
variant may need SugarCube-specific markup guidance that does not conflict
with its format expectations. A full-variant-specific suffix that adds only
the passage section names (without the conversation layout) could help full
without hurting compact (which uses global_suffix) or json.
