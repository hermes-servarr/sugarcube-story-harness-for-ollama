# Iteration 01: Add SugarCube formatting and structure guidance to global_suffix

## Baseline Metrics (before)

- Total cases: 108
- Passed: 6
- Pass rate: 0.0556 (5.56%)
- Mean score: 0.8164
- Failure category: instruction_following (102/102 failures)

### By Variant
| Variant | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|-----------|
| compact | 36    | 3      | 0.0833    | 0.8009    |
| full    | 36    | 0      | 0.0000    | 0.8102    |
| json    | 36    | 3      | 0.0833    | 0.8380    |

### By Direction
| Direction | Cases | Passed | Pass Rate | Mean Score |
|-----------|-------|--------|-----------|-----------|
| A         | 36    | 1      | 0.0278    | 0.8102    |
| B         | 36    | 2      | 0.0556    | 0.8102    |
| C         | 36    | 3      | 0.0833    | 0.8287    |

### By Model Alias (selected)
- Model_E: 3/9 passed (0.3333), best performer
- Model_G: 2/9 passed (0.2222)
- Model_11: 1/9 passed (0.1111)
- All others: 0/9 passed

## Failure Pattern

All 102 failures are instruction_following. Every representative failure shows two co-occurring sub-categories:

1. **markup_compliance**: Models produce Markdown bold (`**text**`) and italic (`*text*`) instead of SugarCube markup. SugarCube bold=0, italic=0, strike=0, highlight=0 in every case. Markdown bold ranges 3-14, italic 2-17 per case.

2. **passage_structure**: Models miss all three required sections: CHOICES, PROSE, SUMMARY. Six warnings per case, zero links_in_choices, zero macros_in_choices.

These failures are universal across all variants (compact, full, json), all directions (A, B, C), and all model aliases. The overlay is currently completely empty.

## Behavior

Models generate well-formed prose content (mean_score 0.8164 is close to passing) but format it with Markdown conventions instead of SugarCube markup, and do not organize output into the required passage sections. This suggests the base prompt does not adequately communicate SugarCube-specific formatting requirements, or models default to Markdown habits without explicit correction.

## Hypothesis

Adding a global_suffix that explicitly specifies:
1. The three required passage sections (===CHOICES===, ===PROSE===, ===SUMMARY===) and their order
2. SugarCube markup conventions: `''double single quotes''` for bold, `//double slashes//` for italic
3. That Markdown formatting must not be used

will reduce both markup_compliance and passage_structure failures across all variants and directions.

## Exact Overlay Change

Changed `global_suffix` from empty string to:

```
Format your output using SugarCube markup, not Markdown.

Use these required passage sections in this order:
===CHOICES===
===PROSE===
===SUMMARY===

For text emphasis, use SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

No variant-specific or direction-specific changes. All other overlay fields remain empty.

## Rollback Condition

Revert global_suffix to empty string if aggregate pass rate declines below 0.0556, or if any per-variant or per-alias regression is observed without offsetting gains elsewhere.

## After Metrics

(pending benchmark run)

## Conclusion

(pending)
