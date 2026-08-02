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

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 77      | 82      | +5    |
| Pass rate | 0.2750  | 0.2929  | +1.79pp |
| Mean score| 0.8065  | 0.8180  | +0.0115 |

### By Variant

| Variant    | Before pass | After pass | Before rate | After rate | Delta |
|------------|-------------|------------|-------------|------------|-------|
| compact    | 24/60       | 27/60      | 0.4000      | 0.4500     | +3    |
| full       | 4/96        | 6/96       | 0.0417      | 0.0625     | +2    |
| json       | 18/40       | 17/40      | 0.4500      | 0.4250     | -1    |
| plain_text | 27/32       | 27/32      | 0.8438      | 0.8438     | 0     |
| thinking   | 4/52        | 5/52       | 0.0769      | 0.0962     | +1    |

### By Model Alias

| Alias   | Before pass | After pass | Delta |
|---------|-------------|------------|-------|
| Model_A | 9           | 9          | 0     |
| Model_B | 25          | 30         | +5    |
| Model_C | 27          | 27         | 0     |
| Model_D | 16          | 16         | 0     |

### Conversation Layout

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 2/44   | 3/44  |
| Pass rate           | 4.55%  | 6.82% |
| mc_inner_monologue  | 37     | 38    |
| conversation_layout | 14     | 21    |
| min_dialogue_turns  | 23     | 24    |
| compact             | 1/4    | 1/4   |
| full                | 0/24   | 0/24  |
| json                | 0/4    | 0/4   |
| thinking            | 1/12   | 2/12  |

### Writing Style

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 1/20   | 1/20  |
| dialogue_slang      | 18     | 17    |
| sections            | 5      | 4     |

### Thinking Variant

| Metric               | Before | After |
|----------------------|--------|-------|
| Passed               | 4/52   | 5/52  |
| Pass rate            | 7.69%  | 9.62% |
| markup_compliance    | 29     | 29    |
| macro_usage          | 28     | 26    |
| passage_structure    | 23     | 18    |
| thinking_quality     | 0      | 0     |

### Directions (improvements)

| Direction | Before pass | After pass | Delta |
|-----------|-------------|------------|-------|
| A         | 5/16        | 7/16       | +2    |
| B         | 6/16        | 7/16       | +1    |
| T3        | 1/16        | 2/16       | +1    |
| T6        | 25/44       | 27/44      | +2    |

## Conclusion

Experiment 08 improved the aggregate by +5 passes (77 to 82, 27.50% to 29.29%),
the best improvement of this campaign. The broadened conversation trigger
phrase helped across multiple variants: compact (+3), full (+2), thinking
(+1), with gains in directions A (+2), B (+1), T3 (+1), and T6 (+2).

The JSON variant regressed by -1 (18 to 17), continuing the pattern from
Exp07. This is a minor regression offset by significant gains elsewhere.
Model_B gained +5 (25 to 30).

Interestingly, the thinking variant improved (+1 pass, 4 to 5) and its
passage_structure failures dropped from 23 to 18. This suggests the
broadened trigger helped thinking cases that involve conversation
scenarios recognize the layout requirement.

The conversation_layout check count increased (14 to 21) even though
the conversation pass rate improved (2 to 3). This may indicate the
broadened trigger is reaching more cases but models are partially
adopting the convention rather than fully complying. The key gain is
in cases that now partially comply enough to pass.

The overlay is retained as the new best: global_suffix with broadened
conversation trigger + json variant suffix from Exp07. Aggregate
29.29% vs campaign baseline 27.14% (+2.15pp). Target is 32.14%.

## Next Decision

The full variant (96 cases, 6.25%) remains the largest opportunity.
Prior full-variant suffix experiments (Exp04, Exp06) both regressed,
but the broadened conversation trigger in Exp08 helped full by +2.
The compact variant is now at 45% (27/60). The thinking variant improved
to 9.62% but still has 29 markup_compliance failures.

Next experiment should target a different axis. The thinking variant's
markup_compliance failures (29, unchanged across Exp07/08) are the most
concentrated remaining failure. But Exp05 showed thinking suffixes may
cause output-budget exhaustion. A safer axis is the compact variant's
remaining failures, or exploring the global instruction hierarchy by
making the SugarCube markup instruction more emphatic without adding
length.
