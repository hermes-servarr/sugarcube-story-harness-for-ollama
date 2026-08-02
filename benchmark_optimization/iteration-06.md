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

(Pending benchmark run)

## Conclusion

(Pending benchmark run)
