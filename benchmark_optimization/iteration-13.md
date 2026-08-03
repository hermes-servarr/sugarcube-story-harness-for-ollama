# Iteration 13: Full-variant suffix emphasizing SugarCube markup over Markdown

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (fresh protected baseline)

- Total cases: 248
- Passed: 47
- Pass rate: 0.1895 (18.95%)
- Mean score: 0.6279
- Failure category: instruction_following (201)

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 60    | 19     | 0.3167    | 0.7292     |
| full     | 96    | 2      | 0.0208    | 0.546      |
| json     | 40    | 21     | 0.525     | 0.8208     |
| thinking | 52    | 5      | 0.0962    | 0.5138     |

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 62    | 7      | 0.1129    | 0.553      |
| Model_B | 62    | 18     | 0.2903    | 0.7242     |
| Model_C | 62    | 12     | 0.1935    | 0.647      |
| Model_D | 62    | 10     | 0.1613    | 0.5874     |

### Conversation Layout

- Cases: 44, Passed: 3, Pass rate: 6.82%, Mean score: 0.4424
- Failed checks: mc_inner_monologue (38), min_dialogue_turns (24),
  conversation_layout (21), alternating_dialogue (11),
  conversation_endpoints (11), exact_dialogue_turns (11), no_markdown (8),
  min_choices (6), sections (5), context_needle (4), dialogue_slang (4)

### Writing Style

- Cases: 20, Passed: 1, Pass rate: 5.0%, Mean score: 0.4658
- Failed checks: dialogue_slang (17), min_dialogue_turns (4),
  mc_inner_monologue (4), min_choices (4), max_sentence_words (3),
  sections (3), no_markdown (3), conversation_layout (1),
  slang_confined_to_dialogue (1)

### Thinking Variant

- Cases: 52, Passed: 5, Pass rate: 9.62%, Mean score: 0.5138
- Failed evaluator categories: markup_compliance (28), passage_structure (28),
  thinking_quality (27), macro_usage (20), capability_observables (17),
  variable_scoping (1)

## Observable Failure Behavior

The full variant has 96 cases (39% of all objective cases) with only 2 passes
(2.08%) and the lowest mean score (0.546). This is the largest single
opportunity in the benchmark.

Representative failures show models emitting Markdown bold/italic instead of
SugarCube markup (e.g., "Markdown: bold=12, italic=4; SugarCube: bold=0,
italic=0"). The global_suffix already says to use SugarCube markup, not
Markdown, but the full variant has the longest prompt context and these
instructions may be diluted.

Prior experiments show:
- Exp09: condensed global_suffix helped full +4 but hurt compact -6
- Exp06: full-variant suffix with section headers regressed -2
- Exp08: broadened conversation trigger helped full +2

The full variant benefits from concise format guidance but not from repeating
section names already in global_suffix. The markup compliance failure is the
most pervasive: models default to Markdown habits when the instruction is
diluted in long context.

## Hypothesis

Adding a concise full-variant suffix that strongly emphasizes SugarCube markup
syntax (not repeating section names or conversation layout from global_suffix)
will reduce markup_compliance failures in full-variant cases and improve the
full variant pass rate from 2/96 (2.08%) without affecting compact, json, or
thinking variants, because variant-specific suffixes do not modify the
global_suffix that compact depends on.

This differs from Exp06 (which repeated section headers and regressed) by
focusing solely on the markup-vs-Markdown distinction, which is the most
pervasive full-variant failure and not already reinforced in a variant-specific
field.

## Exact Overlay Change

`variants.full` changed from empty string to:

```
Use ''double single quotes'' for bold and //double slashes// for italic. Never use Markdown ** or * or _ for emphasis. All emphasis must use SugarCube markup.
```

All other fields remain unchanged:
- global_suffix retains the current content (verbose format with broadened
  conversation trigger)
- variants.compact, variants.json, variants.thinking remain empty
- All direction fields remain as-is (direction H has the Exp12 suffix)

## Expected Affected Categories

- Full variant markup_compliance failures (expected reduction)
- Full variant pass rate (expected improvement from 2/96 = 2.08%)
- No expected change to compact, json, thinking, or non-full directions
- No expected change to conversation_layout or writing_style

## Rollback Condition

Revert variants.full to empty string if:
- Aggregate objective pass rate declines below 0.1895, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
