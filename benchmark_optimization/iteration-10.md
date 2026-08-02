# Iteration 10: Remove JSON-variant suffix to recover JSON variant

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 08 after)

- Total cases: 280
- Passed: 82
- Pass rate: 0.2929 (29.29%)
- Mean score: 0.8180
- Target: 0.3214 (32.14%, +5 absolute pp)
- Failure category: instruction_following (198)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 27     | 0.4500    | 0.8903     |
| full       | 96    | 6      | 0.0625    | 0.7882     |
| json       | 40    | 17     | 0.4250    | 0.8948     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 5      | 0.0962    | 0.7147     |

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 70    | 9      | 0.1286    | 0.7446     |
| Model_B | 70    | 30     | 0.4286    | 0.8732     |
| Model_C | 70    | 27     | 0.3857    | 0.8524     |
| Model_D | 70    | 16     | 0.2286    | 0.8018     |

## Observable Failure Behavior

The JSON variant has been declining since Exp07 added the JSON suffix:
- Pre-Exp07: 19/40 (47.5%)
- Exp07 (suffix added): 18/40 (45.0%), -1
- Exp08 (suffix retained): 17/40 (42.5%), -1 more

The JSON suffix "Your output must be valid JSON. Use SugarCube markup
(not Markdown) inside JSON string values." has caused a monotonic decline
in JSON pass rate. Exp09 (condensed global_suffix, JSON suffix retained)
showed JSON recovering to 19/40 (47.5%), but that was confounded with the
global_suffix change. The current Exp08 overlay still has the JSON suffix.

The JSON variant has the highest mean score (0.8948) but only 42.5% pass
rate, indicating content quality is high but format compliance is the
bottleneck. The JSON suffix may be adding conflicting instructions that
disrupt the JSON variant's already-good output format.

## Hypothesis

Removing the JSON-variant suffix (reverting variants.json to empty string)
will recover the JSON variant pass rate from 17/40 (42.5%) toward its
pre-Exp07 level of 19/40 (47.5%), improving the aggregate objective pass
rate by +2 without affecting compact, full, thinking, or plain_text.

This is the reverse of Exp07's hypothesis. Exp07 hypothesized the JSON
suffix would help; evidence shows it harmed. This experiment tests
removal as the remedy. Only one change is made: variants.json to empty.

## Exact Overlay Change

`variants.json` changed from:

```
Your output must be valid JSON. Use SugarCube markup (not Markdown) inside JSON string values.
```

to empty string:

```
```

All other fields remain unchanged:
- global_suffix retains the Exp08 content (verbose format with broadened
  conversation trigger)
- variants.compact, variants.full, variants.thinking remain empty
- All direction fields remain empty

## Expected Affected Categories

- JSON variant pass rate (expected recovery from 17 to ~19, +2)
- JSON variant markup_compliance (expected reduction)
- No expected change to compact, full, thinking, or plain_text
- Aggregate objective pass rate (expected +2 from JSON recovery)

## Rollback Condition

Re-add the JSON suffix (variants.json to the Exp07 text) if:
- Aggregate objective pass rate declines below 0.2929, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
