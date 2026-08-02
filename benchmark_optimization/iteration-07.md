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
