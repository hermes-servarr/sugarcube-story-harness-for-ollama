# Iteration 06: Add full-variant suffix reinforcing required passage section headers

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (campaign baseline = current best)

- Total cases: 280
- Passed: 78
- Pass rate: 0.2786 (27.86%)
- Mean score: 0.8061
- Target: 0.3286 (32.86%, +5 absolute pp)
- Failure category: instruction_following (202)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 24     | 0.4000    | 0.8729     |
| full       | 96    | 4      | 0.0417    | 0.7691     |
| json       | 40    | 19     | 0.4750    | 0.9000     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 4      | 0.0769    | 0.7019     |

### Full Variant Failure Analysis

- 96 cases, 92 failed (4.17% pass)
- Failed evaluator categories: passage_structure (84), capability_observables
  (64), markup_compliance (11), macro_usage (6), link_setter_syntax (1),
  variable_scoping (1)
- Missing sections: SUMMARY (80), CHOICES (32), PROSE (28)
- Many full-variant cases score 0.8333 (high quality content) but fail because
  they do not include the required ===SUMMARY===, ===CHOICES===, or ===PROSE===
  section headers

## Observable Failure Behavior

The full variant produces good content (mean score 0.7691, many cases at
0.8333) but does not organize output into the required passage sections. 80
of 92 failures are missing the SUMMARY section, 32 are missing CHOICES, and
28 are missing PROSE. The global_suffix already names these sections, but the
full variant's longer prompt structure may dilute or override the global
formatting instruction.

The full variant differs from compact (40% pass) primarily in having a richer
prompt structure with more SugarCube macro and story-generation guidance. The
global_suffix instruction may be getting buried in the full variant's longer
context. A full-variant-specific suffix that places the section requirement
closer to the output may help.

## Hypothesis

Adding a full-variant-specific suffix that explicitly requires the three
section headers as literal output markers will reduce passage_structure
failures in the full variant, improving its pass rate from 4.17% without
affecting compact, json, thinking, or plain_text.

This is the smallest instruction change targeting the largest failing variant
(96 cases) with the most concentrated failure pattern (84/92 passage_structure
failures, 80 missing SUMMARY).

## Exact Overlay Change

`variants.full` changed from empty string to:

```
Your output must include these three section headers as literal text: ===CHOICES===, ===PROSE===, ===SUMMARY===
```

All other fields remain unchanged:
- global_suffix retains the current Exp02 content
- variants.compact, variants.json, variants.thinking remain empty
- All direction fields remain empty

## Expected Affected Categories

- full variant passage_structure failures (84)
- full variant pass rate (expected improvement from 4.17%)
- No expected change to compact, json, thinking, or plain_text

## Rollback Condition

Revert variants.full to empty string if:
- Aggregate objective pass rate declines below 0.2786, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 78      | 76      | -2    |
| Pass rate | 0.2786  | 0.2714  | -0.72pp |
| Mean score| 0.8061  | 0.7957  | -0.0104 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 24/60       | 24/60      | 0.4000      | 0.4000     | 0     |
| full       | 4/96        | 2/96       | 0.0417      | 0.0208     | -2 (REGRESSION) |
| json       | 19/40       | 19/40      | 0.4750      | 0.4750     | 0     |
| plain_text | 27/32       | 27/32      | 0.8438      | 0.8438     | 0     |
| thinking   | 4/52        | 4/52       | 0.0769      | 0.0769     | 0     |

### Full Variant Detail

| Metric                    | Before | After | Delta |
|---------------------------|--------|-------|-------|
| passage_structure failures| 84     | 92    | +8    |
| SUMMARY missing           | 80     | 91    | +11   |
| CHOICES missing           | 32     | 84    | +52   |
| PROSE missing             | 28     | 82    | +54   |
| markup_compliance         | 11     | 17    | +6    |
| Empty responses           | 0      | 1     | +1    |
| mean_score               | 0.7691 | 0.7387| -0.0304|

### Per-Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 10          | 11         | +1    |
| Model_B | 25          | 23         | -2    |
| Model_C | 27          | 26         | -1    |
| Model_D | 16          | 16         | 0     |

## Conclusion

Experiment 06 regressed. Aggregate pass rate declined from 78/280 (27.86%)
to 76/280 (27.14%), a loss of 2 passes. The full variant pass rate declined
from 4/96 (4.17%) to 2/96 (2.08%). The full-variant suffix increased
passage_structure failures from 84 to 92, with dramatically more cases now
missing CHOICES (32 to 84) and PROSE (28 to 82) sections.

The full-variant suffix instruction appears to have disrupted the full
variant's output structure rather than reinforcing it. The models may be
interpreting the additional instruction as conflicting with the global_suffix
guidance, or the instruction is being placed in a position that interferes
with the full variant's existing prompt framework.

The overlay is reverted to the baseline (all variant suffixes empty,
global_suffix retaining Exp02 content). No additional GPU run is needed for
the byte-for-byte restored overlay.

## Rollback

Reverted variants.full to empty string. Validated with json.tool and pytest
(53 passed). Committed and pushed. No additional GPU run needed for the
byte-for-byte restored overlay.

## Next Decision

Experiments 05 and 06 are two consecutive completed experiments that failed
to improve the best aggregate objective pass rate. Exp05 was non-improving
(unchanged 27.86%) and Exp06 regressed (27.14%, reverted). Per stop condition
#3: "Two consecutive completed experiments fail to improve the best aggregate
objective pass rate."

However, the campaign baseline is the current best (no experiment has
exceeded 27.86%). The target is 32.86% (+5pp). The dominant failures are
concentrated in the full variant (96 cases, 4.17%) and thinking variant
(52 cases, 7.69%), which together account for 148 of 280 cases but only 8
passes. The compact (40%) and json (47.5%) variants are already performing
well.

The previous campaign (Exp02-Exp04) also struggled to improve the full
variant with variant-specific suffixes. The full variant's failure pattern
(passage_structure, missing sections) appears resistant to overlay-level
prompt changes. This may require operator review of the full variant's
prompt structure, provisioning, or output budget.

The thinking variant's failures involve suspected output-budget exhaustion
(Exp05 showed increased empty responses when the thinking suffix was added).
This is also an operator-owned setting.

**Stop condition #3 has fired: two consecutive completed experiments (05 and
06) failed to improve the best aggregate objective pass rate.** The campaign
should report to the operator.
