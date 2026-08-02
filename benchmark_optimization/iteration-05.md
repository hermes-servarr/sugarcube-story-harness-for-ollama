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

Benchmark completed and anonymized results were pushed. Run duration ~50 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 78      | 78      | 0     |
| Pass rate | 0.2786  | 0.2786  | 0     |
| Mean score| 0.8061  | 0.7996  | -0.0065 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 24/60       | 24/60      | 0.4000      | 0.4000     | 0     |
| full       | 4/96        | 4/96       | 0.0417      | 0.0417     | 0     |
| json       | 19/40       | 19/40      | 0.4750      | 0.4750     | 0     |
| plain_text | 27/32       | 27/32      | 0.8438      | 0.8438     | 0     |
| thinking   | 4/52        | 4/52       | 0.0769      | 0.0769     | 0     |

### Thinking Variant Detail

| Metric                    | Before | After | Delta |
|---------------------------|--------|-------|-------|
| passage_structure failures| 23     | 36    | +13   |
| markup_compliance         | 29     | 28    | -1    |
| macro_usage               | 28     | 27    | -1    |
| thinking_quality          | 0      | 0     | 0     |
| mean_score                | 0.7019 | 0.6667| -0.035|

### Per-Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 10          | 10         | 0     |
| Model_B | 25          | 27         | +2    |
| Model_C | 27          | 25         | -2    |
| Model_D | 16          | 16         | 0     |

### Representative Failures (thinking)

Three thinking cases now show "Empty raw response" with all categories
reporting "Empty text" (was 1 in the baseline). This is an increase in
empty-response thinking cases, suggesting output-budget exhaustion is
aggravated by the additional thinking suffix instructions.

## Conclusion

The experiment is non-improving. Aggregate pass rate is unchanged (78/280 =
27.86%). The thinking variant pass rate is unchanged (4/52 = 7.69%). However,
thinking passage_structure failures increased from 23 to 36 and the thinking
variant mean score declined from 0.7019 to 0.6667. Three thinking cases now
show "Empty raw response" (up from one in baseline).

**Suspected output-budget exhaustion:** The additional thinking suffix
instructions may be consuming output token budget during the reasoning phase,
leaving insufficient budget for the final passage. The increase in
passage_structure failures (23 to 36) and empty-response cases (1 to 3)
supports this. Per skill rules, the anonymized summary cannot prove the cause,
and output budgets are operator-owned settings that cannot be changed in this
campaign.

The overlay is reverted to the baseline (all variant suffixes empty,
global_suffix retaining the Exp02 content from the previous campaign).

## Rollback

Reverted variants.thinking to empty string. Validated with json.tool and
pytest (53 passed). Committed and pushed. No additional GPU run needed for
the byte-for-byte restored overlay.

## Next Decision

Experiment 05 is the first non-improving experiment in this campaign. The
best aggregate remains 78/280 (27.86%), equal to the campaign baseline.
Target is 32.86%.

Next experiment should target the full variant (96 cases, 4.17% pass), the
largest case count with the worst non-thinking pass rate. A full-variant
suffix adding only SugarCube markup guidance (without conversation layout,
which is already in global_suffix) may help the full variant without
affecting other variants.
