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
