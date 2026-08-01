# Iteration 04: Add full-variant suffix with passage section names

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

## Failure Pattern

The full variant has 456 cases (the largest variant) but only 16 passed (3.51%).
This is down from the campaign baseline of 24 passes (5.26%), meaning the
global_suffix markup instructions in Exp02 hurt the full variant (-8 passes).

The full variant's 440 failures include heavy `passage_structure` and
`sections` failures. The global_suffix already includes the ===CHOICES===,
===PROSE===, ===SUMMARY=== section names, but the full variant may need
additional emphasis on passage structure because it has more complex output
requirements than compact.

## Behavior

The full variant likely has a richer prompt structure that includes more
SugarCube macro instructions and story-generation guidance. The global_suffix
markup instructions may be getting diluted or contradicted by the full
variant's longer system prompt. Adding a full-variant-specific suffix that
reinforces the passage section requirement may help without affecting other
variants.

## Hypothesis

Adding a full-variant-specific suffix that reinforces the required passage
sections (===CHOICES===, ===PROSE===, ===SUMMARY===) in their exact order,
without the full markup instructions or conversation layout guidance, will
help the full variant recover and exceed its baseline pass rate by providing
targeted structural guidance that is not diluted by the global suffix position.

This is the smallest instruction change targeting the largest failing variant.
It does not affect compact, json, or thinking, which all use only the
global_suffix.

## Exact Overlay Change

`variants.full` changed from empty string to:

```
Organize your output into these required sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===
```

All other fields remain unchanged (global_suffix retains Exp02 content,
compact/json/thinking remain empty).

## Expected Affected Categories

- full variant passage_structure and sections failures
- full variant pass rate (expected to recover toward 5.26% or higher)
- No expected change to compact, json, thinking, or plain_text

## Rollback Condition

Revert variants.full to empty string if:
- Aggregate objective pass rate declines below 0.2316 (the current best), or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

(Pending benchmark run)

## Conclusion

(Pending)
