# Iteration 12: Add direction-specific suffix for direction H

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 10 after)

- Total cases: 280
- Passed: 85
- Pass rate: 0.3036 (30.36%)
- Mean score: 0.8202
- Target: 0.3214 (32.14%, +5 absolute pp)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 27     | 0.4500    | 0.8903     |
| full       | 96    | 6      | 0.0625    | 0.7882     |
| json       | 40    | 20     | 0.5000    | 0.9104     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 5      | 0.0962    | 0.7147     |

### By Direction (A-H only, from Exp10)

| Direction | Cases | Passed | Pass Rate | Mean Score |
|-----------|-------|--------|-----------|------------|
| A         | 16    | 7      | 0.4375    | 0.8646     |
| B         | 16    | 8      | 0.5000    | 0.8646     |
| C         | 16    | 6      | 0.3750    | 0.8542     |
| D         | 16    | 4      | 0.2500    | 0.8542     |
| E         | 16    | 4      | 0.2500    | 0.8229     |
| F         | 16    | 5      | 0.3125    | 0.8750     |
| G         | 16    | 7      | 0.4375    | 0.8438     |
| H         | 16    | 5      | 0.3125    | 0.8438     |

## Observable Failure Behavior

Directions D and E are the weakest A-H directions at 25% (4/16 each).
Direction D has a mean score of 0.8542 and direction E has 0.8229,
indicating good content quality but format compliance failures.

Direction-specific suffixes do not affect the compact variant's global_suffix
processing because they are only applied to cases with that direction key.
This avoids the compact regression pattern seen in Exp09 and Exp11 where
global_suffix modifications hurt compact by -6.

Prior experiments showed:
- Exp06: full-variant suffix regressed full by -2 (section headers disrupted format)
- Exp09/Exp11: global_suffix additions hurt compact by -6

A direction-specific suffix targets only 16 cases (one direction) and does
not modify global_suffix, so it should not affect compact, json, thinking,
or other directions.

## Hypothesis

Adding a direction-specific suffix for direction H that reinforces the
passage section requirement will improve direction H's pass rate from
5/16 (31.25%) by helping H-direction cases organize output into the required
sections, without affecting any other direction, variant, or the compact
variant.

Direction H was chosen over D and E because H has slightly higher pass rate
(5 vs 4) suggesting it is closer to passing more cases, and the direction-
specific suffix may tip more H cases over the passing threshold.

This is the smallest instruction change targeting a single direction. It
uses the direction-specific overlay field, a new axis not previously tested.

## Exact Overlay Change

`directions.H` changed from empty string to:

```
Organize your output into the required passage sections: ===CHOICES===, ===PROSE===, ===SUMMARY===.
```

All other fields remain unchanged:
- global_suffix retains the Exp10 content (verbose format with broadened
  conversation trigger)
- All variant suffixes remain empty
- All other direction fields remain empty

## Expected Affected Categories

- Direction H pass rate (expected improvement from 5/16 = 31.25%)
- Direction H passage_structure failures
- No expected change to other directions, compact, full, json, thinking,
  or plain_text

## Rollback Condition

Revert directions.H to empty string if:
- Aggregate objective pass rate declines below 0.3036, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 85      | 85      | 0     |
| Pass rate | 0.3036  | 0.3036  | 0     |
| Mean score| 0.8202  | 0.8196  | -0.0006 |

### By Variant

All variants identical to Exp10. compact 27/60, full 6/96, json 20/40,
plain_text 27/32, thinking 5/52.

### By Direction

All directions identical to Exp10. Direction H: 5/16 (unchanged).

### By Model Alias

All aliases identical to Exp10. Model_A 13, Model_B 30, Model_C 26, Model_D 16.

## Conclusion

Experiment 12 is non-improving. The aggregate pass rate is unchanged
(85/280 = 30.36%). Direction H pass rate is unchanged (5/16 = 31.25%).
No variant, alias, or direction changed. The direction-H suffix had
zero observable effect.

The direction-specific suffix may not be reaching the model's attention
in the context of the full prompt, or direction H's failures are not
passage_structure related (the suffix only reinforced section names that
are already in global_suffix). The global_suffix already names the
required sections; repeating them in a direction-specific suffix adds
no new information.

The overlay is retained because it did not regress. The direction-H
suffix is harmless but ineffective. It may be removed in a future cleanup
but is left in place to avoid spending a GPU run on a byte-for-byte
restoration.

## Next Decision

Direction-specific suffixes that repeat global_suffix content are
ineffective. The next experiment should try a direction-specific suffix
with different content, or explore another axis entirely. The full
variant (96 cases, 6.25%) remains the largest opportunity. Exp09 showed
the condensed global_suffix helped full (+4) but hurt compact (-6). A
full-variant-specific suffix with concise markup guidance (not section
names, which failed in Exp06) could help full without affecting compact.
