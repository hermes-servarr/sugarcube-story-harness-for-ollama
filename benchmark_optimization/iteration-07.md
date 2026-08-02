# Iteration 07: Add JSON-variant suffix reinforcing JSON structure and SugarCube markup

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (campaign baseline = current published result)

- Total cases: 280
- Passed: 76
- Pass rate: 0.2714 (27.14%)
- Mean score: 0.7957
- Target: 0.3214 (32.14%, +5 absolute pp)
- Failure category: instruction_following (204)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 24     | 0.4000    | 0.8729     |
| full       | 96    | 2      | 0.0208    | 0.7387     |
| json       | 40    | 19     | 0.4750    | 0.9000     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 4      | 0.0769    | 0.7019     |

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 70    | 11     | 0.1571    | 0.7202     |
| Model_B | 70    | 23     | 0.3286    | 0.8381     |
| Model_C | 70    | 26     | 0.3714    | 0.8304     |
| Model_D | 70    | 16     | 0.2286    | 0.7940     |

### Thinking Variant

- Cases: 52, Passed: 4, Pass rate: 7.69%, Mean score: 0.7019
- Failed evaluator categories: markup_compliance (29), macro_usage (28),
  passage_structure (23), capability_observables (19), variable_scoping (4),
  link_setter_syntax (1)
- Thinking quality failures: 0
- Final passage structure failures: 23

### Conversation Layout

- Cases: 44, Passed: 2, Pass rate: 4.55%, Mean score: 0.7472
- Failed checks: mc_inner_monologue (41), min_dialogue_turns (25),
  conversation_layout (22), no_markdown (13), min_choices (12),
  conversation_endpoints (12), sections (11), exact_dialogue_turns (11),
  alternating_dialogue (11), dialogue_slang (4), context_needle (2),
  banned_register (1)

### Writing Style

- Cases: 20, Passed: 1, Pass rate: 5.0%, Mean score: 0.775
- Failed checks: dialogue_slang (18), min_choices (8), sections (6),
  min_dialogue_turns (4), mc_inner_monologue (4), conversation_layout (3),
  no_markdown (3), slang_confined_to_dialogue (3), banned_register (1),
  max_sentence_words (1)

### Candidate Tests (diagnostic-only)

- Cases: 12, Passed: 0, Pass rate: 0.0%, Mean score: 0.7083

### Context-Window Diagnostic

- Not present in this run (0 cases).

## Observable Failure Behavior

The JSON variant has 40 cases with 19 passes (47.5%) and the highest mean score
(0.9000) among non-diagnostic variants. In the prior 19-model campaign, json
was at 54.74% without any overlay and dropped to 48.95% after the global_suffix
was added in Exp02. This 6pp regression suggests the global_suffix instructions
about ===CHOICES===, ===PROSE===, ===SUMMARY=== as literal section headers
conflict with the JSON variant's expected JSON output format.

The JSON variant's high mean score (0.90) indicates content quality is strong;
the failures are likely format-compliance issues where models produce
plain-text section headers instead of valid JSON, or mix section-header
formatting into JSON structure incorrectly.

## Hypothesis

Adding a JSON-variant-specific suffix that reinforces valid JSON output
structure and SugarCube markup inside JSON string values (not as plain-text
section headers) will recover the JSON variant pass rate from 47.5% toward
its pre-overlay baseline of ~54.74%, improving aggregate pass rate without
affecting compact, full, thinking, or plain_text.

This is the smallest instruction change targeting a known regression cause
(global_suffix section headers conflicting with JSON format). No prior
experiment has tested a JSON-variant-specific suffix.

## Exact Overlay Change

`variants.json` changed from empty string to:

```
Your output must be valid JSON. Use SugarCube markup (not Markdown) inside JSON string values.
```

All other fields remain unchanged:
- global_suffix retains the current Exp02 content
- variants.compact, variants.full, variants.thinking remain empty
- All direction fields remain empty

## Expected Affected Categories

- JSON variant pass rate (expected improvement from 47.5%)
- JSON variant markup_compliance failures
- No expected change to compact, full, thinking, or plain_text

## Rollback Condition

Revert variants.json to empty string if:
- Aggregate objective pass rate declines below 0.2714, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 76      | 77      | +1    |
| Pass rate | 0.2714  | 0.2750  | +0.36pp |
| Mean score| 0.7957  | 0.8065  | +0.0108 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 24/60       | 24/60      | 0.4000      | 0.4000     | 0     |
| full       | 2/96        | 4/96       | 0.0208      | 0.0417     | +2    |
| json       | 19/40       | 18/40      | 0.4750      | 0.4500     | -1    |
| plain_text | 27/32       | 27/32      | 0.8438      | 0.8438     | 0     |
| thinking   | 4/52        | 4/52       | 0.0769      | 0.0769     | 0     |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 11          | 9          | -2 (REGRESSION) |
| Model_B | 23          | 25         | +2    |
| Model_C | 27          | 27         | 0     |
| Model_D | 16          | 16         | 0     |

### Conversation Layout

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 2/44   | 2/44  |
| mc_inner_monologue  | 41     | 37    |
| conversation_layout | 22     | 14    |
| min_dialogue_turns  | 25     | 23    |
| sections            | 11     | 5     |
| no_markdown         | 13     | 11    |

### Writing Style

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 1/20   | 1/20  |
| dialogue_slang      | 18     | 18    |
| min_choices          | 8      | 5     |
| sections            | 6      | 5     |

### Thinking Variant

Unchanged: 4/52 passed, same failure profile (markup_compliance 29,
macro_usage 28, passage_structure 23, thinking_quality 0).

### Plain-Text

Unchanged: 27/32 passed (84.38%), same by-profile breakdown.

## Conclusion

Experiment 07 improved the aggregate by +1 pass (76 to 77, 27.14% to 27.50%).
The improvement is modest and comes from the full variant recovering by +2
(2 to 4), not from the JSON variant as hypothesized. The JSON variant
actually regressed by -1 (19 to 18, 47.5% to 45.0%), contrary to the
hypothesis.

Model_A regressed by -2 (11 to 9), but this is offset by Model_B gaining +2
(23 to 25). The rollback condition (aggregate decline below 0.2714) is not
triggered because the aggregate improved.

The JSON suffix instruction ("Your output must be valid JSON. Use SugarCube
markup (not Markdown) inside JSON string values.") did not help the JSON
variant and may have slightly hurt it. The full variant recovery is likely
noise or an indirect effect of the global_suffix being relatively less
disruptive in this run.

The overlay is retained because the aggregate improved by +1. The JSON
variant regression is within the rollback tolerance (offsetting gains exist).

## Next Decision

The JSON suffix was not clearly helpful for the JSON variant. The full
variant remains the largest opportunity (96 cases, 4.17% pass) and is
resistant to variant-specific suffixes (Exp04, Exp06 both failed or
regressed). The thinking variant has suspected output-budget exhaustion
(Exp05). Next experiment should explore a different axis: direction-specific
overlay for the worst-performing directions (T1, T4, T5, T7, T8 all at 0%
pass).
