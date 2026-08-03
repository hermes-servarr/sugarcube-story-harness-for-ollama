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
