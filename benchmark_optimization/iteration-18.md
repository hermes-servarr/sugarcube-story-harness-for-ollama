# Iteration 18: Full-variant section completeness suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (fresh protected baseline = current best)

- Total cases: 128
- Passed: 46
- Pass rate: 0.3594 (35.94%)
- Mean score: 0.7612

### By Variant

| Variant  | Cases | Passed | Pass Rate | Mean Score |
|----------|-------|--------|-----------|------------|
| compact  | 32    | 9      | 0.2812    | 0.7604     |
| full     | 32    | 8      | 0.25      | 0.7188     |
| json     | 32    | 22     | 0.6875    | 0.9036     |
| thinking | 32    | 7      | 0.2188    | 0.662      |

### Full Variant Representative Failures

Representative failures for the full variant show:
- "Sections missing=['SUMMARY']; warnings=2; links_in_choices=0; macros_in_choices=0"
- "variable_scoping: <<set>>: to=0, eq=2; setup.in_prose=0; reads=4, writes=2"
- "macro_usage: <<set>>: to=0, eq=2; tags=2; nesting_errors=0"

The most common full-variant failure is missing the SUMMARY section. The
current variants.full already has a markup emphasis suffix (from the
baseline overlay). The full prompt has the longest context, so section
completeness instructions may be diluted.

## Observable Failure Behavior

The full variant has 32 cases with 8 passes (25%). The most common
passage_structure failure is "Sections missing=['SUMMARY']." The
current variants.full already reinforces SugarCube markup but does not
specifically reinforce section completeness. The global_suffix lists
sections but in the full variant's long context this may be overlooked.

Prior Exp13 (previous campaign) showed a concise markup suffix helped
full +4. That suffix is already in the baseline. A different axis is
needed: section completeness, specifically the SUMMARY section which is
the most commonly missing.

## Hypothesis

Appending a concise instruction to variants.full that specifically
reinforces the SUMMARY section requirement will reduce passage_structure
failures in full-variant cases and improve the full variant pass rate
from 8/32 (25%) without affecting compact, json, or thinking variants,
because variant-specific suffixes do not modify the shared global_suffix.

This differs from Exp13 (markup suffix) by targeting section completeness
(SUMMARY) rather than markup syntax. It differs from Exp06 (which repeated
all section headers and regressed) by focusing only on the most commonly
missing section.

## Exact Overlay Change

Append to the end of `variants.full`:

```
Every passage must end with a SUMMARY section. Do not omit SUMMARY.
```

The full variants.full becomes (existing content + new suffix):
```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
PROSE:
CHOICES:
SUMMARY:

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.

When the task involves dialogue or conversation between characters, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//

Use ''double single quotes'' for bold and //double slashes// for italic. Never use Markdown ** or * or _ for emphasis. All emphasis must use SugarCube markup.

Every passage must end with a SUMMARY section. Do not omit SUMMARY.
```

All other fields remain unchanged.

## Expected Affected Categories

- Full variant passage_structure failures (expected reduction, SUMMARY specifically)
- Full variant pass rate (expected improvement from 8/32 = 25%)
- No expected change to compact, json, thinking, or non-full cases

## Rollback Condition

Remove the SUMMARY suffix from variants.full if:
- Aggregate objective pass rate declines below 0.3594, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
