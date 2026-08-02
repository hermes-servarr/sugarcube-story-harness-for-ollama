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

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 82      | 85      | +3    |
| Pass rate | 0.2929  | 0.3036  | +1.07pp |
| Mean score| 0.8180  | 0.8202  | +0.0022 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 27/60       | 27/60      | 0.4500      | 0.4500     | 0     |
| full       | 6/96        | 6/96       | 0.0625      | 0.0625     | 0     |
| json       | 17/40       | 20/40      | 0.4250      | 0.5000     | +3    |
| plain_text | 27/32       | 27/32      | 0.8438      | 0.8438     | 0     |
| thinking   | 5/52        | 5/52       | 0.0962      | 0.0962     | 0     |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 9           | 13         | +4    |
| Model_B | 30          | 30         | 0     |
| Model_C | 27          | 26         | -1    |
| Model_D | 16          | 16         | 0     |

### Conversation, Writing Style, Thinking

All unchanged from Exp08 values. Conversation 3/44, writing_style 1/20,
thinking 5/52 with identical failure profiles.

### Direction Deltas (nonzero)

| Direction | Before | After | Delta |
|-----------|--------|-------|-------|
| A         | 5      | 7     | +2    |
| B         | 6      | 8     | +2    |
| E         | 6      | 4     | -2    |
| G         | 6      | 7     | +1    |
| H         | 4      | 5     | +1    |

## Conclusion

Experiment 10 improved the aggregate by +3 passes (82 to 85, 29.29% to 30.36%).
The JSON variant fully recovered to 20/40 (50.0%), exceeding the pre-Exp07
level of 19/40 (47.5%). The hypothesis was confirmed: the JSON suffix from
Exp07 was harmful and removing it recovered +3 JSON passes.

No variant regressed. Model_C dropped by -1 (27 to 26) which is minor and
within noise. Model_A gained +4 (9 to 13). Directions A (+2), B (+2), G (+1),
H (+1) improved; E (-2) declined but is within noise.

The overlay is retained as the new best: global_suffix with verbose format
and broadened conversation trigger, all variant suffixes empty.

Campaign progress: 27.14% baseline -> 30.36% best (+3.22pp). Target: 32.14%.
Gap: 1.78pp (~5 more passes needed).

## Next Decision

The overlay now has all variant suffixes empty and only the global_suffix
with the Exp02 content + Exp08 broadened conversation trigger. Remaining
opportunities:
- Full variant: 96 cases, 6.25% pass (largest case count)
- Thinking variant: 52 cases, 9.62% pass (markup_compliance 29)
- Directions at 0%: T1(4), T4(8), T5(12), T7(12), T8(8) = 44 cases
- Writing style: 20 cases, 5% pass (dialogue_slang 17)

Next experiment should explore a new axis. The writing-style dialogue_slang
failure (17/20) is the most concentrated failure. Adding a global_suffix
instruction about dialogue register could help, similar to how broadening
the conversation trigger helped conversation cases.
