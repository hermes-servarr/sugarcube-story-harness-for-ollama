# Iteration 03: Move markup/passage instructions to variant suffixes, keep conversation layout in global_suffix

## Baseline Metrics (current best = Experiment 02 after)

- Total cases: 1330
- Passed: 308
- Pass rate: 0.2316 (23.16%)
- Mean score: 0.6874
- Campaign baseline: 0.2150 (21.50%)
- Target: 0.2650 (26.50%)

### By Variant (current best)

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 285   | 89     | 0.3123    | 0.7311     |
| full       | 456   | 16     | 0.0351    | 0.6631     |
| json       | 190   | 93     | 0.4895    | 0.8658     |
| plain_text | 152   | 101    | 0.6645    | 0.6645     |
| thinking   | 247   | 9      | 0.0364    | 0.5589     |

### By Model Alias (current best, selected)

| Alias    | Cases | Passed | Pass Rate | Delta from campaign baseline |
|----------|-------|--------|-----------|-------------------------------|
| Model_A  | 70    | 9      | 0.1286    | -6 (regressed from 15)        |
| Model_B  | 70    | 15     | 0.2143    | -8 (regressed from 23)        |
| Model_C  | 70    | 10     | 0.1429    | -5 (regressed from 15)        |
| Model_D  | 70    | 23     | 0.3286    | +2                            |
| Model_E  | 70    | 28     | 0.4000    | +13                           |
| Model_G  | 70    | 30     | 0.4286    | +6                           |
| Model_S  | 70    | 16     | 0.2286    | -2 (regressed from 18)        |

### Conversation Layout (current best)

- Cases: 209, Passed: 8, Pass rate: 3.83%
- compact: 5/19, full: 0/114, json: 0/19, thinking: 3/57
- mc_inner_monologue: 163, conversation_layout: 90, min_dialogue_turns: 110

### Writing Style (current best)

- Cases: 95, Passed: 2, Pass rate: 2.11%

### Thinking Variant (current best)

- Cases: 247, Passed: 9, Pass rate: 3.64%
- passage_structure: 150, markup_compliance: 167, thinking_quality: 0

## Failure Pattern

Experiment 02 showed that adding SugarCube markup and passage-section instructions
to global_suffix improved compact (+35 passes) and thinking (+6) but caused
regressions in json (-11 passes, 54.74% -> 48.95%) and full (-8 passes, 5.26% ->
3.51%). The json variant likely interprets the ===CHOICES=== etc. section
instructions as conflicting with JSON output structure. The full variant may
be receiving conflicting formatting guidance that disrupts its existing
output patterns.

Per-alias regressions: Model_A (-6), Model_B (-8), Model_C (-5), Model_S (-2)
suggest these aliases are disproportionately affected by the global markup
instructions, possibly because their output formats were closer to passing
and the added instructions shifted them away from their working format.

## Behavior

The global_suffix instructions helped variants that had no strong formatting
constraints (compact, thinking) but hurt variants that already had implicit
format expectations (json needs JSON output, full has its own passage format).
The conversation layout guidance is applicable across all variants and does
not conflict with format-specific expectations.

## Hypothesis

Moving the SugarCube markup and passage-structure instructions from
global_suffix to the compact and thinking variant-specific suffixes will:
1. Recover the json variant regression (back toward 54.74%) by removing
   conflicting section instructions.
2. Recover the full variant regression (back toward 5.26%) by removing
   conflicting markup instructions.
3. Preserve the compact variant gains (toward 31.23%) by keeping the markup
   and passage-structure instructions in the compact suffix.
4. Preserve or improve the thinking variant gains (toward 3.64%) by keeping
   the markup and passage-structure instructions in the thinking suffix.
5. Keep the conversation layout improvement by retaining only the conversation
   layout guidance in global_suffix.

This is the smallest instruction change that addresses the regressions while
preserving the gains. It separates format-specific guidance (markup, sections)
from cross-variant guidance (conversation layout).

## Exact Overlay Change

1. `global_suffix` changed to contain ONLY the conversation layout guidance:

```
When the task requests a conversation scene, use this layout inside the PROSE section:
DIALOGUE:
Speaker: "Spoken words."
Speaker: "Reply words."
INNER MONOLOGUE:
MC: //Private thoughts.//
```

2. `variants.compact` changed from empty to:

```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

3. `variants.thinking` changed from empty to the same as compact:

```
Format your output using SugarCube markup, not Markdown.

Required passage sections in this exact order:
===CHOICES===
===PROSE===
===SUMMARY===

SugarCube markup: ''double single quotes'' for bold, //double slashes// for italic. Do not use Markdown ** or * for emphasis.
```

4. `variants.full` and `variants.json` remain empty.
5. All direction-specific fields remain empty.

## Expected Affected Categories

- json variant pass rate (expected recovery toward 54.74%)
- full variant pass rate (expected recovery toward 5.26%)
- compact variant pass rate (expected to hold at ~31.23%)
- thinking variant pass rate (expected to hold at ~3.64% or improve)
- conversation_layout and mc_inner_monologue (expected to hold or improve)
- per-alias regressions for Model_A, Model_B, Model_C, Model_S (expected recovery)

## Rollback Condition

Revert to the Experiment 02 overlay (all instructions in global_suffix, all
variant suffixes empty) if:
- Aggregate objective pass rate declines below 0.2316 (the current best), or
- Any per-variant pass rate declines below its Experiment 02 after value without
  offsetting gains elsewhere, or
- Any material per-alias regression beyond what was already observed in
  Experiment 02.

## After Metrics

(Pending benchmark run)

## Conclusion

(Pending)
