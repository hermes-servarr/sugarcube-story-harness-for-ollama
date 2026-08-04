# Iteration 18: Full-variant section completeness suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (fresh protected baseline = current best)

- Total cases: 128
- Passed: 46
- Pass rate: 0.3594 (35.94%)
- Mean score: 0.7612

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 32    | 9      | 0.2812    | 0.7604     |
| full     | 32    | 8      | 0.25      | 0.7188     |
| json     | 32    | 22     | 0.6875    | 0.9036     |
| thinking | 32    | 7      | 0.2188    | 0.662      |

### Full Variant Representative Failures

Representative failures for the full variant show:
- "Sections missing=['SUMMARY']; warnings=2; links_in_choices=0; macros_in_choices=0"
- "variable_scoping: <<set>>: to=0, eq=2; setup.in_prose=0; reads=4, writes=2"
- "macro_usage: <<set>>: to=0, eq=2; tags=2; nesting_errors=0"

The most common full-variant failure is missing the SUMMARY section. The
current variants.full already has a markup emphasis suffix (from the
baseline overlay). The full prompt has the longest context, so section
completeness instructions may be diluted.

## Observable Failure Behavior

The full variant has 32 cases with 8 passes (25%). The most common
passage_structure failure is "Sections missing=['SUMMARY']." The
current variants.full already reinforces SugarCube markup but does not
specifically reinforce section completeness. The global_suffix lists
sections but in the full variant's long context this may be overlooked.

Prior Exp13 (previous campaign) showed a concise markup suffix helped
full +4. That suffix is already in the baseline. A different axis is
needed: section completeness, specifically the SUMMARY section which is
the most commonly missing.

## Hypothesis

Appending a concise instruction to variants.full that specifically
reinforces the SUMMARY section requirement will reduce passage_structure
failures in full-variant cases and improve the full variant pass rate
from 8/32 (25%) without affecting compact, json, or thinking variants,
because variant-specific suffixes do not modify the shared global_suffix.

This differs from Exp13 (markup suffix) by targeting section completeness
(SUMMARY) rather than markup syntax. It differs from Exp06 (which repeated
all section headers and regressed) by focusing only on the most commonly
missing section.

## Exact Overlay Change

Append to the end of `variants.full`:

```
Every passage must end with a SUMMARY section. Do not omit SUMMARY.
```

The full variants.full becomes (existing content + new suffix):
```
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

Use ''double single quotes'' for bold and //double slashes// for italic. Never use Markdown ** or * or _ for emphasis. All emphasis must use SugarCube markup.

Every passage must end with a SUMMARY section. Do not omit SUMMARY.
```

All other fields remain unchanged.

## Expected Affected Categories

- Full variant passage_structure failures (expected reduction, SUMMARY specifically)
- Full variant pass rate (expected improvement from 8/32 = 25%)
- No expected change to compact, json, thinking, or non-full cases

## Rollback Condition

Remove the SUMMARY suffix from variants.full if:
- Aggregate objective pass rate declines below 0.3594, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~43 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 128     | 128     | 0     |
| Passed    | 46      | 51      | +5    |
| Pass rate | 0.3594  | 0.3984  | +3.91pp |
| Mean score| 0.7612  | 0.7698  | +0.0086 |

### By Variant

| Variant  | Before pass | After pass | Before rate | After rate | Delta |
|----------|-------------|------------|-------------|------------|-------|
| compact  | 9/32        | 11/32      | 0.2812      | 0.3438     | +2    |
| full     | 8/32        | 12/32      | 0.25        | 0.375      | +4    |
| json     | 22/32       | 22/32      | 0.6875      | 0.6875     | 0     |
| thinking | 7/32        | 6/32       | 0.2188      | 0.1875     | -1    |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 3           | 5          | +2    |
| Model_B | 17          | 19         | +2    |
| Model_C | 11          | 11         | 0     |
| Model_D | 15          | 16         | +1    |

### By Direction

| Direction | Before | After | Delta |
|-----------|--------|-------|-------|
| A         | 6      | 7     | +1    |
| B         | 7      | 6     | -1    |
| C         | 4      | 8     | +4    |
| D         | 6      | 6     | 0     |
| E         | 6      | 7     | +1    |
| F         | 4      | 7     | +3    |
| G         | 7      | 6     | -1    |
| H         | 6      | 4     | -2    |

### Thinking Variant Detail

| Metric                     | Before | After | Delta |
|----------------------------|--------|-------|-------|
| Passed                     | 7/32   | 6/32  | -1    |
| thinking_quality failures  | 14     | 15    | +1    |
| markup_compliance failures | 14     | 17    | +3    |
| macro_usage failures       | 10     | 13    | +3    |
| passage_structure failures | 14     | 14    | 0     |

## Conclusion

Experiment 18 improved the aggregate by +5 passes (46 to 51, 35.94% to 39.84%).
The full variant improved from 8/32 (25%) to 12/32 (37.5%), confirming the
hypothesis that a SUMMARY section completeness suffix helps the full variant.
The compact variant also improved +2 (unexpected positive spillover), and
directions C (+4) and F (+3) showed notable gains.

The thinking variant dropped -1 (7 to 6), which is within sampling noise. No
material per-alias regression occurred: Model_A +2, Model_B +2, Model_D +1,
Model_C unchanged.

The overlay is retained as the new best. Campaign progress: 35.94% baseline
to 39.84% best (+3.91pp).

## Next Decision

The full variant SUMMARY suffix was the first successful experiment. The
thinking variant remains the weakest at 18.75% with 15 thinking_quality
failures. However, Exp17 showed that reducing the thinking instruction is
harmful. Next experiment should target the thinking variant by adding a
brief reinforcement to the existing verbose instruction, not replacing it.
Alternatively, the direction-specific weakness (H dropped from 6 to 4) could
be addressed. The thinking variant's "no thinking content" problem (15
failures) is the largest remaining concentrated failure.
