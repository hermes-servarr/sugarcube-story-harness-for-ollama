# Iteration 09: Condense global_suffix to reduce prompt dilution

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

### Conversation Layout

- Cases: 44, Passed: 3, Pass rate: 6.82%
- Failed checks: mc_inner_monologue (38), min_dialogue_turns (24),
  conversation_layout (21), alternating_dialogue (11),
  conversation_endpoints (11), exact_dialogue_turns (11), no_markdown (8),
  sections (7), min_choices (7), context_needle (4), dialogue_slang (4)

### Writing Style

- Cases: 20, Passed: 1, Pass rate: 5.0%
- Failed checks: dialogue_slang (17), min_dialogue_turns (4),
  mc_inner_monologue (4), sections (4), min_choices (4),
  max_sentence_words (3), slang_confined_to_dialogue (2), no_markdown (2),
  conversation_layout (1)

### Thinking Variant

- Cases: 52, Passed: 5, Pass rate: 9.62%, Mean score: 0.7147
- Failed evaluator categories: markup_compliance (29), macro_usage (26),
  passage_structure (18), capability_observables (17), variable_scoping (8),
  link_setter_syntax (4)
- Thinking quality failures: 0
- Final passage structure failures: 18

### Directions at 0%

T1 (4 cases), T4 (8), T5 (12), T7 (12), T8 (8) = 44 cases all failing

## Observable Failure Behavior

The global_suffix is currently 377 characters of instruction text covering
SugarCube markup, passage sections, and conversation layout. Models with
longer prompt contexts (full variant, thinking variant) may dilute these
instructions. The compact variant at 45% and json at 42.5% are the best
performers, suggesting that when the instruction-to-content ratio is higher,
compliance improves.

The full variant (96 cases, 6.25%) has a mean score of 0.7882, indicating
good content quality but poor format compliance. The instructions are present
but may be getting lost in the longer full-variant prompt context.

## Hypothesis

Condensing the global_suffix to a more concise version with the same
directives but fewer words will improve instruction compliance across all
variants by reducing prompt dilution. The condensed version preserves all
required information (markup conventions, section names, conversation layout)
but uses more compact phrasing.

This is a global instruction hierarchy experiment. It tests whether
instruction length (not content) affects compliance. No prior experiment
has modified the conciseness of the global_suffix.

## Exact Overlay Change

In `model_benchmark/prompt_overrides.json`, the `global_suffix` is changed
from the current version (377 chars) to a condensed version (~240 chars):

```
Use SugarCube markup, not Markdown: ''double single quotes'' for bold, //double slashes// for italic.

Required sections in order: ===CHOICES===, ===PROSE===, ===SUMMARY===

For dialogue or conversation between characters, use inside PROSE:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

The variants.json suffix from Exp07 is retained. All other variant and
direction fields remain empty.

The condensed version preserves:
1. SugarCube markup convention (bold and italic syntax)
2. "not Markdown" directive
3. All three required sections in order
4. Conversation layout with the broadened trigger from Exp08
5. DIALOGUE/INNER MONOLOGUE format specification

It removes:
- Redundant "Format your output" preamble
- Repetitive "Do not use Markdown ** or * for emphasis" (already said "not Markdown")
- "Required passage sections in this exact order:" → "Required sections in order:"
- "When the task involves dialogue or conversation between characters,
  use this layout inside the PROSE section:" → "For dialogue or conversation
  between characters, use inside PROSE:"

## Expected Affected Categories

- All variants (expected improvement from better instruction compliance)
- Full variant passage_structure failures (expected reduction)
- Thinking variant markup_compliance failures (expected reduction)
- Compact variant pass rate (expected improvement or hold)
- JSON variant (uncertain: shorter global_suffix may reduce conflict)
- No expected change to plain_text (diagnostic only)

## Rollback Condition

Revert global_suffix to the Exp08 version if:
- Aggregate objective pass rate declines below 0.2929, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
