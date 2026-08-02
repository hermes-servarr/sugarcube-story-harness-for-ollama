# Iteration 11: Add writing-style dialogue register trigger to global_suffix

## Campaign Mode

Prompt overlays only (operator has not stated envelope mode).

## Baseline Metrics (current best = Experiment 10 after)

- Total cases: 280
- Passed: 85
- Pass rate: 0.3036 (30.36%)
- Mean score: 0.8202
- Target: 0.3214 (32.14%, +5 absolute pp)
- Failure category: instruction_following (195)

### By Variant

| Variant    | Cases | Passed | Pass Rate | Mean Score |
|------------|-------|--------|-----------|------------|
| compact    | 60    | 27     | 0.4500    | 0.8903     |
| full       | 96    | 6      | 0.0625    | 0.7882     |
| json       | 40    | 20     | 0.5000    | 0.9104     |
| plain_text | 32    | 27     | 0.8438    | 0.8438     |
| thinking   | 52    | 5      | 0.0962    | 0.7147     |

### Writing Style

- Cases: 20, Passed: 1, Pass rate: 5.0%, Mean score: 0.7812
- Failed checks: dialogue_slang (17), min_dialogue_turns (4),
  mc_inner_monologue (4), min_choices (4), max_sentence_words (3),
  sections (3), no_markdown (3), conversation_layout (1),
  slang_confined_to_dialogue (1)
- By variant: compact 1/4, full 0/8, json 0/4, thinking 0/4

### Conversation Layout

- Cases: 44, Passed: 3, Pass rate: 6.82%
- Failed checks: mc_inner_monologue (38), min_dialogue_turns (24),
  conversation_layout (21), alternating_dialogue (11),
  conversation_endpoints (11), exact_dialogue_turns (11), no_markdown (8),
  min_choices (6), sections (5), context_needle (4), dialogue_slang (4)

## Observable Failure Behavior

The writing-style test has 20 cases with only 1 pass (5.0%). The dominant
failure is dialogue_slang (17/20 = 85% failure rate). This check counts
distinct guide phrases inside quoted speech. Models are not using the
required dialogue register specified by the signed writing-style guide.

The current global_suffix mentions conversation layout (DIALOGUE/INNER
MONOLOGUE format) but says nothing about dialogue register or writing
style. When a writing-style guide is active, models may not realize they
need to adopt a specific speech register in dialogue. The guide phrases
are injected by signed code into the context, but without an overlay
instruction to follow them, models default to standard dialogue.

This is analogous to the conversation layout problem in Exp08: the
overlay had format guidance but a narrow trigger that models didn't
recognize. Adding a writing-style trigger could help models notice the
guide and adopt the required register.

## Hypothesis

Adding a global_suffix instruction that when a writing style or dialogue
register is specified in the context, models should follow that register
in all dialogue lines, will reduce dialogue_slang failures in
writing-style cases and improve the writing-style pass rate from 1/20
(5%) without affecting non-writing-style cases.

This is the smallest instruction change targeting the most concentrated
writing-style failure (dialogue_slang 17/20). It adds a trigger, not a
format specification, and does not copy or weaken any signed guide
phrases. No prior experiment has addressed writing-style compliance.

## Exact Overlay Change

In `model_benchmark/prompt_overrides.json`, the following sentence is
appended to the end of `global_suffix`:

```
When a writing style or dialogue register is specified in the context, follow that register in all dialogue lines.
```

All other parts of the global_suffix remain unchanged (SugarCube markup
instructions, passage section names, conversation layout with broadened
trigger). All variant and direction fields remain empty.

## Expected Affected Categories

- writing_style dialogue_slang failures (expected reduction from 17)
- writing_style pass rate (expected improvement from 1/20 = 5%)
- Possible spillover to conversation_layout dialogue_slang (4 failures)
- No expected change to non-writing-style cases

## Rollback Condition

Remove the writing-style trigger sentence from global_suffix if:
- Aggregate objective pass rate declines below 0.3036, or
- Any per-variant pass rate declines without offsetting gains, or
- Any material per-alias regression.

## After Metrics

Benchmark completed and anonymized results were pushed. Run duration ~55 minutes.

### Aggregate

| Metric    | Before  | After   | Delta |
|-----------|---------|---------|-------|
| Cases     | 280     | 280     | 0     |
| Passed    | 85      | 78      | -7    |
| Pass rate | 0.3036  | 0.2786  | -2.50pp |
| Mean score| 0.8202  | 0.8092  | -0.0110 |

### By Variant

| Variant    | Before pass | After pass | Delta |
|------------|-------------|------------|-------|
| compact    | 27/60       | 21/60      | -6 (REGRESSION) |
| full       | 6/96        | 7/96       | +1    |
| json       | 20/40       | 19/40      | -1    |
| plain_text | 27/32       | 27/32      | 0     |
| thinking   | 5/52        | 4/52       | -1    |

### By Model Alias

| Alias   | Before | After | Delta |
|---------|--------|-------|-------|
| Model_A | 13     | 13    | 0     |
| Model_B | 30     | 25    | -5 (REGRESSION) |
| Model_C | 26     | 24    | -2    |
| Model_D | 16     | 16    | 0     |

### Writing Style

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 1/20   | 3/20  |
| dialogue_slang      | 17     | 16    |

### Conversation Layout

| Metric              | Before | After |
|---------------------|--------|-------|
| Passed              | 3/44   | 1/44  |

## Conclusion

Experiment 11 regressed severely. Aggregate declined from 85/280 (30.36%)
to 78/280 (27.86%), a loss of 7 passes. The writing-style trigger helped
writing_style (+2, 1 to 3) and dialogue_slang (-1, 17 to 16), but the
additional global_suffix sentence harmed compact (-6), conversation (-2),
thinking (-1), and json (-1). Model_B dropped -5.

The writing-style trigger sentence added 99 characters to global_suffix.
This is similar to Exp09's finding: longer global_suffix text hurts compact.
The compact variant is sensitive to global_suffix length. Even a single
additional sentence causes significant regression.

The rollback condition fired (aggregate declined below 0.3036). The overlay
is reverted to the Exp10 best (global_suffix without the writing-style
trigger, all variant suffixes empty).

## Rollback

Reverted global_suffix to the Exp10 version (removed the writing-style
trigger sentence). Validated with json.tool and pytest (53 passed).
Committed and pushed. No additional GPU run needed for the restored overlay.

## Next Decision

Experiments 09 and 11 both show that adding text to global_suffix harms
compact (-6 each). The compact variant is at its ceiling with the current
global_suffix length. Future experiments should avoid modifying
global_suffix and instead use direction-specific or variant-specific
suffixes that don't affect compact.

The writing-style improvement (+2) from the trigger is real but cannot
be retained without harming compact. A direction-specific overlay for
writing-style directions (e.g., directions that contain writing-style
tests) could isolate the benefit without affecting compact. However,
writing-style is a diagnostic category, not a direction. The directions
A-H are SugarCube story directions, and T-tests are capability tiers.

Next experiment should target the full variant (96 cases, 6.25%) with
a full-variant suffix, but prior experiments (Exp04 aborted, Exp06
regressed) showed full-variant suffixes are risky. A different approach:
add a direction-specific suffix for direction H (currently at 25%, 4/16)
or direction D (25%, 4/16), which are the worst A-H directions.
