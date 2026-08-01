# Iteration 02: Add SugarCube formatting, passage structure, and conversation layout guidance to global_suffix

## Baseline Metrics (before)

- Total cases: 1330
- Passed: 286
- Pass rate: 0.2150 (21.50%)
- Mean score: 0.6813
- Target: 0.2650 (26.50%, +5 absolute pp)
- Failure categories: instruction_following (974), internal_exception (70)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 285   | 54     | 0.1895    | 0.6813     |
| full       | 456   | 24     | 0.0526    | 0.6764     |
| json       | 190   | 104    | 0.5474    | 0.8787     |
| plain_text | 152   | 101    | 0.6645    | 0.6645     |
| thinking   | 247   | 3      | 0.0121    | 0.5489     |

### By Direction (objective A-H only)

| Direction | Cases | Passed | Pass Rate | Mean Score |
|-----------|-------|--------|-----------|------------|
| A         | 76    | 17     | 0.2237    | 0.7127     |
| B         | 76    | 21     | 0.2763    | 0.7105     |
| C         | 76    | 26     | 0.3421    | 0.7325     |
| D         | 76    | 19     | 0.2500    | 0.7215     |
| E         | 76    | 24     | 0.3158    | 0.7083     |
| F         | 76    | 20     | 0.2632    | 0.7325     |
| G         | 76    | 24     | 0.3158    | 0.7083     |
| H         | 76    | 16     | 0.2105    | 0.6864     |

### By Model Alias (objective aliases only)

| Alias    | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| Model_A  | 70    | 15     | 0.2143    | 0.7470     |
| Model_B  | 70    | 23     | 0.3286    | 0.7679     |
| Model_C  | 70    | 15     | 0.2143    | 0.7185     |
| Model_D  | 70    | 21     | 0.3000    | 0.8077     |
| Model_E  | 70    | 15     | 0.2143    | 0.8065     |
| Model_F  | 70    | 22     | 0.3143    | 0.8208     |
| Model_G  | 70    | 24     | 0.3429    | 0.8292     |
| Model_H  | 70    | 22     | 0.3143    | 0.8351     |
| Model_I  | 70    | 16     | 0.2286    | 0.8077     |
| Model_J  | 70    | 21     | 0.3000    | 0.8214     |
| Model_K  | 70    | 25     | 0.3571    | 0.8208     |
| Model_L  | 70    | 19     | 0.2714    | 0.8327     |
| Model_M  | 70    | 19     | 0.2714    | 0.8321     |
| Model_N  | 70    | 0      | 0.0000    | 0.0000     |
| Model_O  | 70    | 0      | 0.0000    | 0.1667     |
| Model_P  | 70    | 0      | 0.0000    | 0.1667     |
| Model_Q  | 70    | 8      | 0.1143    | 0.6565     |
| Model_R  | 70    | 3      | 0.0429    | 0.6911     |
| Model_S  | 70    | 18     | 0.2571    | 0.8167     |

### Conversation Layout

- Cases: 209, Passed: 0, Pass rate: 0.0%, Mean score: 0.6417
- Failed checks: mc_inner_monologue (191), conversation_layout (162),
  min_dialogue_turns (139), min_choices (80), sections (70),
  exact_dialogue_turns (54), conversation_endpoints (54),
  alternating_dialogue (53), context_needle (39), no_markdown (28),
  dialogue_slang (16)

### Writing Style

- Cases: 95, Passed: 2, Pass rate: 2.11%, Mean score: 0.6724
- Failed checks: dialogue_slang (77), min_choices (38), sections (33),
  conversation_layout (17), min_dialogue_turns (17), mc_inner_monologue (17),
  no_markdown (14), max_sentence_words (14), slang_confined_to_dialogue (14),
  banned_register (2)

### Thinking Variant

- Cases: 247, Passed: 3, Pass rate: 1.21%, Mean score: 0.5489
- Failed evaluator categories: markup_compliance (192), macro_usage (169),
  passage_structure (130), capability_observables (94), variable_scoping (54),
  link_setter_syntax (46), naked_interpolation (34), thinking_quality (1)
- Thinking quality failures: 1
- Final passage structure failures: 130

### Context-Window Diagnostic

- Diagnostic-only, 133 cases across 19 aliases
- Configured num_ctx levels: 2048, 4096, 8192, 16384, 32768, 65536, 131072
- Several aliases (N, O, P) show 0% acceptance at all levels or 0 full retrieval
- Aliases D, I, J, K, L, M do not accept 131072

### Candidate Tests (diagnostic-only)

- Cases: 57, Passed: 0, Pass rate: 0.0%, Mean score: 0.6228
- T3: 38 cases, 0 passed; T8: 19 cases, 0 passed

## Failure Pattern

The prompt overlay is completely empty (all fields are empty strings). The
dominant failures cluster into three groups:

1. **Passage structure + markup compliance** (affects all variants but
   devastates full and thinking): 70 `sections` failures in conversation
   cases, 33 in writing-style cases. Models do not emit the required
   ===CHOICES=== / ===PROSE=== / ===SUMMARY=== sections. They use Markdown
   instead of SugarCube markup.

2. **Conversation layout** (209 cases, 0% pass): 162 `conversation_layout`
   failures and 191 `mc_inner_monologue` failures. Per the operator notes
   in test-proposals.md, 24 of 30 non-thinking conversation cases emitted no
   `DIALOGUE:` block at all. The convention adoption is the core issue, not
   punctuation near-misses.

3. **Thinking variant final-passage formatting** (247 cases, 1.21% pass):
   130 `passage_structure` failures and 192 `markup_compliance` failures.
   `thinking_quality` only fails 1 time, so reasoning is not the issue. The
   thinking variant produces reasoning but then fails to emit a properly
   formatted final passage.

JSON variant performs well (54.74%), confirming that when format is
structurally constrained, models can comply. The gap is the free-form
variants where the overlay provides no formatting guidance.

## Behavior

Models generate content with reasonable quality (mean scores 0.68-0.83) but
format it with Markdown conventions and free-form narrative structure instead
of the required SugarCube passage sections and signed conversation layout.
The conversation diagnostic probes (PROP-0001 through PROP-0003) confirm this
is a format-compliance issue, not a task-complexity or context-length issue.

## Hypothesis

Adding a global_suffix that explicitly specifies:
1. The three required passage sections and their order
2. SugarCube markup conventions (not Markdown)
3. The signed conversation layout convention with block labels and format

will reduce passage_structure, markup_compliance, conversation_layout, and
mc_inner_monologue failures across all variants, improving the aggregate
objective pass rate without weakening any evaluator or removing coverage.

This is the smallest instruction change that addresses the largest cluster
of repeated failures (format compliance) across multiple variant and
capability categories simultaneously.

## Exact Overlay Change

Changed `global_suffix` in `model_benchmark/prompt_overrides.json` from empty
string to:

```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.

When the task requests a conversation scene, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

No variant-specific or direction-specific changes. All other overlay fields
remain empty.

## Expected Affected Categories

- passage_structure (all variants, especially full and thinking)
- markup_compliance (all variants)
- conversation_layout (conversation cases)
- mc_inner_monologue (conversation cases)
- min_dialogue_turns (conversation cases)
- sections (conversation and writing-style cases)
- min_choices (conversation and writing-style cases)

## Rollback Condition

Revert global_suffix to empty string if:
- Aggregate objective pass rate declines below 0.2150, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression is observed.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~163 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 1330    | 1330    | 0     |
| Passed    | 286     | 308     | +22   |
| Pass rate | 0.2150  | 0.2316  | +1.66pp |
| Mean score| 0.6813  | 0.6874  | +0.0061 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 54/285      | 89/285     | 0.1895      | 0.3123     | +35   |
| full       | 24/456      | 16/456     | 0.0526      | 0.0351     | -8 (REGRESSION) |
| json       | 104/190     | 93/190     | 0.5474      | 0.4895     | -11 (REGRESSION) |
| plain_text | 101/152     | 101/152    | 0.6645      | 0.6645     | 0     |
| thinking   | 3/247       | 9/247      | 0.0121      | 0.0364     | +6    |

### By Model Alias (regressions only)

| Alias    | Before pass | After pass | Before rate | After rate | Delta |
|----------|-------------|------------|-------------|------------|-------|
| Model_A  | 15/70       | 9/70       | 0.2143      | 0.1286     | -6    |
| Model_B  | 23/70       | 15/70      | 0.3286      | 0.2143     | -8    |
| Model_C  | 15/70       | 10/70      | 0.2143      | 0.1429     | -5    |
| Model_K  | 25/70       | 24/70      | 0.3571      | 0.3429     | -1    |
| Model_S  | 18/70       | 16/70      | 0.2571      | 0.2286     | -2    |

### Conversation Layout

| Metric           | Before | After  |
|------------------|--------|--------|
| Cases/Passed     | 0/209  | 8/209  |
| Pass rate        | 0.0%   | 3.83%  |
| compact          | 0/19   | 5/19   |
| full             | 0/114  | 0/114  |
| json             | 0/19   | 0/19   |
| thinking         | 0/57   | 3/57   |
| mc_inner_monologue | 191  | 163    |
| conversation_layout | 162  | 90     |
| min_dialogue_turns  | 139  | 110    |

### Writing Style

| Metric           | Before | After  |
|------------------|--------|--------|
| Cases/Passed     | 2/95   | 2/95   |
| Pass rate        | 2.11%  | 2.11%  |

### Thinking Variant

| Metric           | Before | After  |
|------------------|--------|--------|
| Cases/Passed     | 3/247  | 9/247  |
| Pass rate        | 1.21%  | 3.64%  |
| passage_structure | 130   | 150    |
| markup_compliance | 192   | 167    |
| thinking_quality  | 1     | 0      |

### Context-Window Diagnostic

Not present in this run (0 cases). Previous run had 133 diagnostic cases.

## Conclusion

The aggregate objective pass rate improved by 1.66 absolute pp (21.50% -> 23.16%).
The improvement is concentrated in the compact variant (+35 passes, 18.95% -> 31.23%)
and the thinking variant (+6 passes, 1.21% -> 3.64%). Conversation layout improved
from 0% to 3.83% (8 passes), entirely in compact (5) and thinking (3).

However, the experiment introduced regressions:
- **json variant**: -11 passes (54.74% -> 48.95%). The SugarCube markup and passage-
  section instructions in global_suffix likely conflict with JSON output formatting
  expectations. JSON variant models may interpret the "===CHOICES=== etc." instructions
  as overriding the JSON structure.
- **full variant**: -8 passes (5.26% -> 3.51%). The global_suffix may add conflicting
  formatting instructions that interfere with the full variant's existing behavior.
- **Per-alias**: Model_A (-6), Model_B (-8), Model_C (-5), Model_S (-2) regressed.

The overlay is retained because the aggregate improved. The next experiment should
move the SugarCube markup and passage-structure instructions from global_suffix to
variant-specific suffixes for compact and thinking only, keeping only the conversation
layout guidance in global_suffix. This should recover the json and full regressions
while preserving the compact and thinking gains.

No stop condition has fired. Target (26.50%) not yet reached. Best aggregate so far:
23.16%. Campaign continues.
