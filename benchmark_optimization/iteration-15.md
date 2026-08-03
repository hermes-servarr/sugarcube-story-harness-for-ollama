# Iteration 15: Global suffix restructure — lead with SugarCube syntax

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 14 after)

- Total cases: 248
- Passed: 53
- Pass rate: 0.2137 (21.37%)
- Mean score: 0.6298
- Failure category: instruction_following (195)

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 60    | 19     | 0.3167    | 0.7292     |
| full     | 96    | 6      | 0.0625    | 0.5432     |
| json     | 40    | 21     | 0.525     | 0.8208     |
| thinking | 52    | 7      | 0.1346    | 0.5282     |

### By Model Alias

| Alias   | Cases | Passed | Pass Rate | Mean Score |
|---------|-------|--------|-----------|------------|
| Model_A | 62    | 11     | 0.1774    | 0.5737     |
| Model_B | 62    | 19     | 0.3065    | 0.7083     |
| Model_C | 62    | 12     | 0.1935    | 0.6393     |
| Model_D | 62    | 11     | 0.1774    | 0.598      |

## Observable Failure Behavior

Representative failures across all variants show Markdown emphasis (**bold**
and *italic*) instead of SugarCube markup (''bold'' and //italic//). The
current global_suffix mentions SugarCube syntax in its third paragraph, after
the section list. Instruction position experiments (radical-experiments #15)
suggest that instruction position matters more than repetition.

The full variant already has a markup emphasis suffix (Exp13), which helped
+4. The compact variant does not have a variant suffix and relies on
global_suffix alone. The compact variant is at 31.67% with markup compliance
failures in its cases.

The current global_suffix ordering is:
1. "Format your output using SugarCube markup, not Markdown."
2. Required passage sections
3. SugarCube markup syntax details
4. Conversation layout

The SugarCube syntax tokens (''bold'' and //italic//) are in paragraph 3,
after the section list. If position matters, leading with the syntax tokens
should improve markup compliance in variants that rely on global_suffix
(compact, json, thinking).

## Hypothesis

Restructuring global_suffix to lead with the SugarCube syntax tokens (placing
the most critical markup instruction first) while keeping the same content
and approximate length will improve markup compliance across compact, json,
and thinking variants without regressing any variant, because the first
instruction in a suffix has the highest attention weight.

This is a position-sweep experiment (radical experiment #15). It keeps all
existing content but reorders paragraphs. It does not add or remove text.
This differs from Exp09 (which condensed/shortened global_suffix and hurt
compact -6) and Exp11 (which added text and hurt compact -6) by preserving
the exact same content in a different order.

## Exact Overlay Change

In `model_benchmark/prompt_overrides.json`, the `global_suffix` is changed
from the current ordering (format intro → sections → syntax → conversation)
to a reordered version (syntax first → format intro → sections → conversation):

Before:
```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.

When the task involves dialogue or conversation between characters, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

After:
```
SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.

Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

When the task involves dialogue or conversation between characters, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

All other fields remain unchanged. The variants.full, variants.thinking, and
directions.H suffixes from prior experiments are retained.

## Expected Affected Categories

- Compact variant markup_compliance (expected improvement, syntax first)
- JSON variant markup_compliance (expected improvement)
- Thinking variant markup_compliance (expected improvement or neutral,
  since thinking already has its own markup guidance in variants.thinking)
- Full variant (expected neutral, since it has its own variants.full suffix)
- No expected change to conversation_layout or writing_style

## Rollback Condition

Revert global_suffix to the Exp14 ordering if:
- Aggregate objective pass rate declines below 0.2137, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~62 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 248     | 248     | 0     |
| Passed    | 53      | 48      | -5    |
| Pass rate | 0.2137  | 0.1935  | -2.02pp |
| Mean score| 0.6298  | 0.6167  | -0.0131 |

### By Variant

| Variant  | Before pass | After pass | Before rate | After rate | Delta |
|----------|-------------|------------|-------------|------------|-------|
| compact  | 19/60       | 17/60      | 0.3167      | 0.2833     | -2    |
| full     | 6/96        | 3/96       | 0.0625      | 0.0312     | -3    |
| json     | 21/40       | 20/40      | 0.525       | 0.5        | -1    |
| thinking | 7/52        | 8/52       | 0.1346      | 0.1538     | +1    |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 11          | 8          | -3    |
| Model_B | 19          | 14         | -5    |
| Model_C | 12          | 17         | +5    |
| Model_D | 11          | 9          | -2    |

### Conversation, Writing Style, Thinking

- Conversation layout: 2/44 → 0/44 (-2, all conversation passes lost)
- Writing style: 1/20 (unchanged)
- Thinking: 7/52 → 8/52 (+1), thinking_quality 26→23, markup_compliance 20→19

## Conclusion

Experiment 15 regressed. Aggregate declined from 53/248 (21.37%) to 48/248
(19.35%), a loss of 5 passes. The global_suffix reposition hurt compact (-2),
full (-3), and json (-1). Only thinking improved (+1). Model_B dropped -5
(19→14) and Model_A -3 (11→8), while Model_C gained +5 (12→17).

The rollback condition fired (aggregate declined below 0.2137). The overlay
is reverted to the Exp14 global_suffix ordering (format intro → sections →
syntax → conversation). The variant suffixes (full, thinking) and direction H
suffix are retained.

This confirms that global_suffix ordering matters and that the current
ordering (format intro first, syntax third) is better than leading with the
syntax tokens. The compact variant may depend on seeing the high-level format
instruction ("Format your output using SugarCube markup, not Markdown") before
the detailed syntax. Leading with syntax tokens may have caused models to
skip the broader format directive.

## Rollback

Reverted global_suffix to the Exp14 version (original ordering). Validated
with json.tool and pytest (53 passed). Committed and pushed. No additional
GPU run needed for the restored overlay.

## Next Decision

Global_suffix reordering is harmful. The compact variant is sensitive to
global_suffix structure, not just length (Exp09, Exp11, Exp15). Future
experiments should continue using variant-specific suffixes that do not
modify global_suffix. The full variant remains the largest opportunity
(96 cases, 6.25% after Exp13). Next experiment: a compact-variant suffix
targeting markup compliance, since compact is at 31.67% and has no
variant-specific suffix.
