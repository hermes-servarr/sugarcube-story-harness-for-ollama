# Iteration 21: Harness-Suite R2-MULTI-DIALOGUE task-vs-plan slot-kind alignment

## Campaign Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures)

## Baseline Metrics (pre-revision)

Published anonymized result summary (before this experiment):

- harness_architectures: 0 cases (architecture benchmark has not yet produced a result)
- Overall capability benchmark: 128 cases, 51 passed (39.84%), mean score 0.7698
- No per-architecture breakdown available

The architecture benchmark has not produced a result across prior attempts
(iteration-01 through iteration-20, attempts 1-11, all failed with
network-unreachable errors). The corpus revisions from iteration-01
(R2-MULTI-DIALOGUE rev 2, R3-HUB-COPY rev 2, R8-CHOICE-DISTINCTION rev 2),
iteration-19 (R0-ORDINARY-FANTASY rev 2), and iteration-20 (R4-STYLE-CANT
rev 2) are committed and visible in the current working tree.

## Failure Pattern and Coverage Analysis

### Ambiguity found

**R2-MULTI-DIALOGUE** (T2, L, D0, revision 2): The task says "Fill six
alternating fixed-speaker dialogue slots for a tense treaty negotiation,
followed by two choice-copy slots." However, the plan's narrative_slots
contain 5 dialogue slots and 1 thought slot:

- mira_1 (dialogue, speaker: Mira Vale)
- player_1 (dialogue, speaker: Player)
- mira_2 (dialogue, speaker: Mira Vale)
- player_2 (dialogue, speaker: Player)
- mira_3 (dialogue, speaker: Mira Vale)
- player_thought (thought, no speaker)

The task describes all six narrative slots as "fixed-speaker dialogue
slots," but the 6th slot (player_thought) is a thought slot with no
speaker. A model following the task literally would attempt to write 6
dialogue lines with speakers, then fail plan adherence because the plan
expects 5 dialogue + 1 thought. This creates a false plan-adherence
failure attributable to task-text confusion rather than genuine
architecture discrimination.

### Comparison with correctly-described peers

Two other cases in the corpus have the same dialogue-plus-thought pattern
and describe it accurately:

- **R2-DIALOGUE-THOUGHT** (T2, M): task says "Fill the fixed interrogation
  dialogue turns and private thought, then two follow-up choice-copy
  slots." This correctly distinguishes dialogue from thought.
- **R9-LONG-DIALOGUE** (T9, XL): task says "Fill eight fixed alternating
  dialogue slots and one thought slot while preserving the treaty
  negotiation across the long context." This correctly counts 8 dialogue
  + 1 thought.

R2-MULTI-DIALOGUE is the only case that mislabels a thought slot as a
dialogue slot in its task text.

### Coverage gaps

No new coverage gaps identified beyond those already recorded as HPROP
proposals 0002-0004 in iteration-01. Those proposals (R3-S-ROOM,
R4-M-DISTRACTOR, R6-S-MIXED-KIND) require an operator-approved signed code
commit to expand the frozen 24-case corpus (the canonical test guard
`test_refactor_corpus_has_fixed_core_and_canary_sizes` enforces
`len(cases) == 24`).

### Prior revisions preserved

The five case revisions from prior iterations remain in the corpus:
- R0-ORDINARY-FANTASY: plan_ordinary_fantasy, revision 2 (task: "two
  distinct" not "two materially different")
- R2-MULTI-DIALOGUE: plan_multi_dialogue, revision 2 (forbidden_terms now
  includes "INNER MONOLOGUE:") -- this iteration further revises to 3
- R3-HUB-COPY: plan_hub_copy, revision 2 (task: "three distinct" not
  "three clearly distinct")
- R4-STYLE-CANT: plan_style_cant, revision 2 (task: "in the spoken
  dialogue lines" not "only in spoken dialogue")
- R8-CHOICE-DISTINCTION: plan_choice_distinction, revision 2 (task: "with
  distinct labels" not "meaningfully distinct")

## Hypothesis

Changing the R2-MULTI-DIALOGUE task from "Fill six alternating
fixed-speaker dialogue slots for a tense treaty negotiation, followed by
two choice-copy slots." to "Fill five alternating fixed-speaker dialogue
slots and one private thought for a tense treaty negotiation, followed
by two choice-copy slots." will align the task text with the plan's
actual slot composition (5 dialogue + 1 thought), matching the pattern
used by R2-DIALOGUE-THOUGHT and R9-LONG-DIALOGUE. This prevents
task-text-induced plan-adherence failures where a model writes 6 dialogue
lines for a plan that expects 5 dialogue + 1 thought.

## Exact Changes

### Revised cases (1)

- **R2-MULTI-DIALOGUE** (plan_id: plan_multi_dialogue, revision 2 to 3):
  Change task from "Fill six alternating fixed-speaker dialogue slots for
  a tense treaty negotiation, followed by two choice-copy slots." to "Fill
  five alternating fixed-speaker dialogue slots and one private thought
  for a tense treaty negotiation, followed by two choice-copy slots." No
  other fields changed.

### New cases

None. The canonical test guard enforces a frozen 24-case corpus. Adding
new cases would require an operator-approved signed code commit outside
the permitted edit set.

## Rollback Condition

Revert this change if any validation command fails, if the published
result shows architecture-pairing violation, or if the revision proves
non-discriminating.

## Suite Baseline Status

This is the first suite baseline for the revised corpus (6 cases at
revision 2+: R0-ORDINARY-FANTASY rev 2, R2-MULTI-DIALOGUE rev 3,
R3-HUB-COPY rev 2, R4-STYLE-CANT rev 2, R8-CHOICE-DISTINCTION rev 2, and
R0-ORDINARY-SCIFI/R1-STATE-REFERENCE/etc. at rev 1). The architecture
benchmark has not yet produced a result. A successful benchmark run will
establish the first baseline.

## Benchmark Attempt

### Attempt 1 (2026-08-17, scheduled cron job)

Pre-flight checks confirmed: no active managed processes, HEAD
(6593bc1) descends from signed trust commit 897fc29a, SSH config has the
sugarcube-benchmark host entry. The corpus (24 cases, 5 at revision 2
and R2-MULTI-DIALOGUE at revision 3) passed all validation (JSON valid,
loader OK, 134 tests passed, working tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_c90e72c1019e). The process exited with exit code 255 (SSH
error). The benchmark PC was not reachable at the network level — the same
network-unreachable condition as iteration-01 attempts 1 through 8,
iteration-19 attempt 1, and iteration-20 attempt 1.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark. This appears to be a persistent
network outage (now spanning 12 attempts over 11 consecutive days,
2026-08-07 through 2026-08-17).

## Conclusion

The corpus revision (R2-MULTI-DIALOGUE rev 2 to 3, task-vs-plan slot-kind
alignment) is committed and pushed. The architecture benchmark could not
be completed due to network unreachability. The revised suite baseline
remains pending a successful benchmark run. The last verified suite is
preserved. Operator review is required to restore network connectivity
to the benchmark PC.
