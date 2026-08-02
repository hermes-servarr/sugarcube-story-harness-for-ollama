# Iteration 05: Add thinking-variant suffix reinforcing final-passage structure and SugarCube markup

## Campaign Mode

This campaign uses **prompt overlays only**. The operator has not stated the
envelope mode (optimized or story), so per skill rules, no ingestion-envelope
experiments are performed.

## Baseline Metrics (campaign baseline)

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

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 70    | 10     | 0.1429    | 0.7321     |
| Model_B | 70    | 25     | 0.3571    | 0.8482     |
| Model_C | 70    | 27     | 0.3857    | 0.8452     |
| Model_D | 70    | 16     | 0.2286    | 0.7988     |

### Thinking Variant

- Cases: 52, Passed: 4, Pass rate: 7.69%, Mean score: 0.7019
- Failed evaluator categories: markup_compliance (29), macro_usage (28),
  passage_structure (23), capability_observables (19), variable_scoping (4),
  link_setter_syntax (1)
- Thinking quality failures: 0
- Final passage structure failures: 23

### Conversation Layout

- Cases: 44, Passed: 2, Pass rate: 4.55%, Mean score: 0.7585
- Failed checks: mc_inner_monologue (37), min_dialogue_turns (23),
  no_markdown (12), conversation_layout (12), exact_dialogue_turns (11),
  conversation_endpoints (11), alternating_dialogue (10), min_choices (4),
  dialogue_slang (4), context_needle (4), sections (3),
  slang_confined_to_dialogue (1)

### Writing Style

- Cases: 20, Passed: 1, Pass rate: 5.0%, Mean score: 0.7812
- Failed checks: dialogue_slang (18), sections (5), min_choices (5),
  slang_confined_to_dialogue (4), max_sentence_words (3),
  mc_inner_monologue (3), min_dialogue_turns (3), no_markdown (2),
  conversation_layout (1)

### Candidate Tests (diagnostic-only)

- Cases: 12, Passed: 0, Pass rate: 0.0%, Mean score: 0.7188

### Context-Window Diagnostic

- Not present in this run (0 cases).

## Observable Failure Behavior

The thinking variant has 52 cases with only 4 passes (7.69%).
thinking_quality_failures = 0, so reasoning quality is not the issue. The
failures are concentrated in final-passage formatting:

- 23 passage_structure failures: models either emit empty/truncated final
  passages or miss required sections (e.g., SUMMARY).
- 29 markup_compliance failures: models produce Markdown bold/italic instead
  of SugarCube markup in the final passage.
- 28 macro_usage failures: models produce incorrect or missing SugarCube
  macros.

One representative failure shows "Empty raw response" for a thinking case
(Model_A:T9-THINKING-XL), which could indicate output-budget exhaustion for
that case. However, 29 markup_compliance failures indicate that at least 29
thinking cases produced non-empty output with wrong formatting. The
passage_structure and markup_compliance failures are the dominant pattern.

The current global_suffix already includes SugarCube markup instructions and
passage section names, but the thinking variant may lose these instructions
during the reasoning process. A thinking-specific suffix placed closer to
the output instruction can reinforce the final-passage requirement.

## Hypothesis

Adding a thinking-variant-specific suffix that reinforces the requirement to
output one complete final passage after reasoning, with all required sections
in order and SugarCube markup (not Markdown), will reduce passage_structure,
markup_compliance, and macro_usage failures in the thinking variant without
affecting compact, full, json, or plain_text variants.

This is the smallest instruction change targeting the most concentrated
failure pattern (thinking final-passage formatting) per the skill's thinking
variant rules.

## Exact Overlay Change

`variants.thinking` changed from empty string to:

```
After your reasoning, output one complete final passage with all required sections in this exact order: ===CHOICES===, ===PROSE===, ===SUMMARY===. Use SugarCube markup only: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

All other fields remain unchanged:
- global_suffix retains the current Exp02 content (SugarCube markup, passage
  sections, conversation layout)
- variants.compact, variants.full, variants.json remain empty
- All direction fields remain empty

## Expected Affected Categories

- thinking variant passage_structure failures (23)
- thinking variant markup_compliance failures (29)
- thinking variant macro_usage failures (28)
- thinking variant pass rate (expected improvement from 7.69%)
- No expected change to compact, full, json, or plain_text

## Rollback Condition

Revert variants.thinking to empty string if:
- Aggregate objective pass rate declines below 0.2786 (the campaign baseline), or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

(Pending benchmark run)

## Conclusion

(Pending benchmark run)
