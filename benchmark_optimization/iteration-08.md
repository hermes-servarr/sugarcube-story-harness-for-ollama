# Iteration 08: Broaden conversation layout trigger in global_suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 07 after)

- Total cases: 280
- Passed: 77
- Pass rate: 0.2750 (27.50%)
- Mean score: 0.8065
- Target: 0.3214 (32.14%, +5 absolute pp)
- Failure category: instruction_following (203)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 24     | 0.4000    | 0.8729     |
| full       | 96    | 4      | 0.0417    | 0.7691     |
| json       | 40    | 18     | 0.4500    | 0.9031     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 4      | 0.0769    | 0.7019     |

### Conversation Layout (current best)

- Cases: 44, Passed: 2, Pass rate: 4.55%, Mean score: 0.7614
- Failed checks: mc_inner_monologue (37), min_dialogue_turns (23),
  conversation_layout (14), no_markdown (11), exact_dialogue_turns (11),
  conversation_endpoints (11), alternating_dialogue (10), sections (5),
  min_choices (5), dialogue_slang (4), context_needle (4),
  slang_confined_to_dialogue (1)
- By variant: compact 1/4, full 0/24, json 0/4, thinking 1/12

### Writing Style (current best)

- Cases: 20, Passed: 1, Pass rate: 5.0%, Mean score: 0.7812
- Failed checks: dialogue_slang (18), sections (5), min_choices (5),
  slang_confined_to_dialogue (4), max_sentence_words (3),
  mc_inner_monologue (3), min_dialogue_turns (3), no_markdown (2),
  conversation_layout (1)

## Observable Failure Behavior

The conversation layout has 44 cases with only 2 passes (4.55%). The
dominant failure is mc_inner_monologue (37/44 = 84% failure rate), followed
by min_dialogue_turns (23/44) and conversation_layout (14/44).

The operator notes in test-proposals.md record that 24 of 30 non-thinking
conversation cases emitted no DIALOGUE: block at all. The failure is
convention adoption: models produce narrative prose with quoted speech but
do not use the required DIALOGUE:/INNER MONOLOGUE: labels.

The current global_suffix says "When the task requests a conversation scene,
use this layout inside the PROSE section:" followed by the DIALOGUE/INNER
MONOLOGUE format. The trigger phrase "requests a conversation scene" is
narrow. Conversation test cases may describe dialogue scenarios without
using the exact phrase "conversation scene," causing models to not
recognize the layout requirement.

## Hypothesis

Broadening the conversation layout trigger in the global_suffix from "When
the task requests a conversation scene" to "When the task involves dialogue
or conversation between characters" will increase the rate at which models
adopt the DIALOGUE:/INNER MONOLOGUE: convention, reducing
mc_inner_monologue, conversation_layout, and min_dialogue_turns failures
across conversation cases in all variants, improving the aggregate
objective pass rate.

This is the smallest instruction change targeting the conversation layout
convention adoption failure. It changes only the trigger condition, not the
format specification. No prior experiment has modified the conversation
layout trigger.

## Exact Overlay Change

In `model_benchmark/prompt_overrides.json`, the `global_suffix` conversation
layout trigger phrase is changed from:

```
When the task requests a conversation scene, use this layout inside the PROSE section:
```

to:

```
When the task involves dialogue or conversation between characters, use this layout inside the PROSE section:
```

All other parts of the global_suffix remain unchanged (SugarCube markup
instructions, passage section names, and the DIALOGUE/INNER MONOLOGUE format
specification). The variants.json suffix from Exp07 is retained. All other
variant and direction fields remain empty.

## Expected Affected Categories

- conversation_layout failures (expected reduction from 14)
- mc_inner_monologue failures (expected reduction from 37)
- min_dialogue_turns failures (expected reduction from 23)
- Conversation case pass rate (expected improvement from 2/44 = 4.55%)
- No expected change to non-conversation cases, plain_text, or
  non-conversation directions

## Rollback Condition

Revert the global_suffix conversation layout trigger phrase to the original
"When the task requests a conversation scene" text if:
- Aggregate objective pass rate declines below 0.2750, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.
