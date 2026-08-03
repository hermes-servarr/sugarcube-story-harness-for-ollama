# Iteration 14: Thinking-variant suffix for plan-then-render boundary

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 13 after)

- Total cases: 248
- Passed: 51
- Pass rate: 0.2056 (20.56%)
- Mean score: 0.6268
- Failure category: instruction_following (197)

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 60    | 19     | 0.3167    | 0.7292     |
| full     | 96    | 6      | 0.0625    | 0.5432     |
| json     | 40    | 21     | 0.525     | 0.8208     |
| thinking | 52    | 5      | 0.0962    | 0.5138     |

### Thinking Variant Detail

- Cases: 52, Passed: 5, Pass rate: 9.62%, Mean score: 0.5138
- Failed evaluator categories: markup_compliance (28), passage_structure (28),
  thinking_quality (27), macro_usage (20), capability_observables (17),
  variable_scoping (1)
- Thinking quality failures: 27 (models produce no thinking content)
- Final passage structure failures: 28

## Observable Failure Behavior

The thinking variant has 52 cases with only 5 passes (9.62%). Two dominant
failures:

1. thinking_quality (27/52 = 52% failure): "Thinking variant produced no
   thinking content." Models skip the planning section entirely and go
   straight to passage output.

2. passage_structure (28/52 = 54% failure): Missing sections, especially
   SUMMARY and CHOICES. Even when models produce content, the final passage
   lacks required section markers.

3. markup_compliance (28/52 = 54% failure): Markdown instead of SugarCube
   markup, same pattern as the full variant.

Representative failures show models emitting Markdown bold/italic with no
thinking section and missing passage sections. The thinking variant's mean
score (0.5138) is the lowest of all variants.

Prior Exp05 (thinking suffix reinforcing final format) did not improve pass
count and coincided with more empty responses. But that experiment reinforced
final format, not the planning step. The core problem is that models are not
producing thinking content at all - they skip the planning phase.

## Hypothesis

Adding a thinking-variant suffix that explicitly requires a brief planning
section before the final passage, and reinforces the ===PASSAGE=== output
boundary, will reduce thinking_quality failures (from 27) and improve the
thinking variant pass rate from 5/52 (9.62%) without affecting compact, full,
or json variants.

This differs from Exp05 by focusing on the planning phase itself (the missing
behavior) rather than the final format. It reinforces relevant variables,
SugarCube macros, and direction constraints as the content of planning,
addressing the thinking_quality check directly. Per the thinking variant
rules, this adjusts only variants.thinking.

## Exact Overlay Change

`variants.thinking` changed from empty string to:

```
First plan your approach: identify relevant variables, SugarCube macros, and direction constraints. Then produce a complete passage with all required sections: ===CHOICES===, ===PROSE===, ===SUMMARY===. Use SugarCube markup, not Markdown.
```

All other fields remain unchanged:
- global_suffix retains the current content (verbose format with broadened
  conversation trigger)
- variants.compact remains empty, variants.full retains the Exp13 suffix
- variants.json remains empty
- All direction fields remain as-is

## Expected Affected Categories

- thinking_quality failures (expected reduction from 27)
- thinking variant passage_structure failures (expected reduction from 28)
- thinking variant markup_compliance failures (expected reduction from 28)
- thinking variant pass rate (expected improvement from 5/52 = 9.62%)
- No expected change to compact, full, json, or non-thinking cases

## Rollback Condition

Revert variants.thinking to empty string if:
- Aggregate objective pass rate declines below 0.2056, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~61 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 248     | 248     | 0     |
| Passed    | 51      | 53      | +2    |
| Pass rate | 0.2056  | 0.2137  | +0.81pp |
| Mean score| 0.6268  | 0.6298  | +0.003 |

### By Variant

| Variant  | Before pass | After pass | Before rate | After rate | Delta |
|----------|-------------|------------|-------------|------------|-------|
| compact  | 19/60       | 19/60      | 0.3167      | 0.3167     | 0     |
| full     | 6/96        | 6/96       | 0.0625      | 0.0625     | 0     |
| json     | 21/40       | 21/40      | 0.525       | 0.525      | 0     |
| thinking | 5/52        | 7/52       | 0.0962      | 0.1346     | +2    |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 10          | 11         | +1    |
| Model_B | 18          | 19         | +1    |
| Model_C | 13          | 12         | -1    |
| Model_D | 10          | 11         | +1    |

### Thinking Variant Detail

| Metric                     | Before | After | Delta |
|----------------------------|--------|-------|-------|
| Passed                     | 5/52   | 7/52  | +2    |
| thinking_quality failures  | 27     | 26    | -1    |
| passage_structure failures | 28     | 33    | +5    |
| markup_compliance failures | 28     | 20    | -8    |
| macro_usage failures       | 20     | 22    | +2    |
| capability_observables      | 17     | 19    | +2    |

### Conversation, Writing Style

- Conversation layout: 3/44 → 2/44 (-1, within noise)
- Writing style: 1/20 (unchanged), dialogue_slang 15→17

### Suspected Output-Budget Exhaustion

One representative failure (Model_A:thinking:G) shows "Empty raw response" -
the model produced no output at all. This is a thinking case omitting the final
passage entirely. Per the thinking variant rules, this is recorded as suspected
output-budget exhaustion. The anonymized summary cannot prove the cause; token
counters and finish reasons are not available in the summary.

The passage_structure failures increased from 28 to 33 despite the thinking
pass rate improving, which is consistent with models spending budget on
planning content but running out before completing the final passage. The
markup_compliance failures dropped sharply (28→20), suggesting the suffix did
help models that produce content use SugarCube markup.

The overlay is retained because the aggregate improved (+2) and no variant
regressed. However, the empty-response observation and increased
passage_structure failures in the thinking variant warrant operator review
of the private run and GPU-safe token budget before further thinking-variant
experiments.

## Conclusion

Experiment 14 improved the aggregate by +2 passes (51 to 53, 20.56% to 21.37%).
The thinking variant improved from 5/52 (9.62%) to 7/52 (13.46%), with
markup_compliance dropping sharply (28→20). No variant regressed.

However, one thinking case produced an empty raw response (suspected
output-budget exhaustion), and thinking passage_structure failures increased
(28→33). Per the thinking variant rules and campaign stop condition 7, this
requires operator review before further thinking-variant experiments.

Campaign progress: 18.95% baseline to 21.37% best (+2.42pp).

## Stop Condition

Campaign stop condition 7: A thinking result suggests output-budget
exhaustion or truncation requiring operator review. The empty raw response
in Model_A:thinking:G and the increase in passage_structure failures (28→33)
in the thinking variant indicate that the thinking suffix may be causing
models to exhaust their output budget during the planning phase, leaving
insufficient tokens for the final passage.

Operator action required: review the private run for thinking-variant token
counts, finish reasons, and the GPU-safe token budget before continuing
thinking-variant optimization.
