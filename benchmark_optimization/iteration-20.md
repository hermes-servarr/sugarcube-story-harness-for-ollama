# Iteration 20: Harness-Suite R4-STYLE-CANT task-vs-check alignment

## Campaign Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures)

## Baseline Metrics (pre-revision)

Published anonymized result summary (before this experiment):

- harness_architectures: 0 cases (architecture benchmark has not yet produced a result)
- Overall capability benchmark: 128 cases, 51 passed (39.84%), mean score 0.7698
- No per-architecture breakdown available

The architecture benchmark has not produced a result across prior attempts
(iteration-01 through iteration-19, attempts 1-10, all failed with
network-unreachable errors). The corpus revisions from iteration-01
(R2-MULTI-DIALOGUE rev 2, R3-HUB-COPY rev 2, R8-CHOICE-DISTINCTION rev 2)
and iteration-19 (R0-ORDINARY-FANTASY rev 2) are committed and visible in
the current working tree.

## Failure Pattern and Coverage Analysis

### Ambiguity found

**R4-STYLE-CANT** (T4, L, D0): The task says "Fill one neutral narration
slot and two fixed-speaker lines. Use chrome-cold and wired-in only in
spoken dialogue." The word "only" implies the `required_terms` check
enforces slot placement: that the terms "chrome-cold" and "wired-in" must
appear exclusively in the dialogue slots and not in the narration
paragraph slot. However, the `required_terms` semantic check
(`score_refactor_fill` in `refactor_benchmark.py`) only verifies
casefolded substring presence anywhere in the assembled fill text. It does
not check which narrative slot the terms appear in. A model placing
"chrome-cold" in the narration paragraph would pass `required_terms` but
violate the task's "only in spoken dialogue" constraint.

This is the same class of task-vs-check overclaim fixed in:
- iteration-01: R3-HUB-COPY ("clearly distinct" to "distinct")
- iteration-01: R8-CHOICE-DISTINCTION ("meaningfully distinct" to "distinct labels")
- iteration-19: R0-ORDINARY-FANTASY ("materially different" to "distinct")

R4-STYLE-CANT is the remaining outlier where a qualifying word ("only")
overclaims what the deterministic check enforces. The overclaim is on the
register-placement axis rather than the distinctness axis, but the
principle is the same: the task implies a stronger constraint than the
check verifies.

### Coverage gaps

No new coverage gaps identified beyond those already recorded as HPROP
proposals 0002-0004 in iteration-01. Those proposals (R3-S-ROOM,
R4-M-DISTRACTOR, R6-S-MIXED-KIND) require an operator-approved signed code
commit to expand the frozen 24-case corpus (the canonical test guard
`test_refactor_corpus_has_fixed_core_and_canary_sizes` enforces
`len(cases) == 24`).

### Prior revisions preserved

The four case revisions from prior iterations remain in the corpus:
- R0-ORDINARY-FANTASY: plan_ordinary_fantasy, revision 2 (task: "two
  distinct" not "two materially different")
- R2-MULTI-DIALOGUE: plan_multi_dialogue, revision 2 (forbidden_terms now
  includes "INNER MONOLOGUE:")
- R3-HUB-COPY: plan_hub_copy, revision 2 (task: "three distinct" not
  "three clearly distinct")
- R8-CHOICE-DISTINCTION: plan_choice_distinction, revision 2 (task: "with
  distinct labels" not "meaningfully distinct")

## Hypothesis

Changing the R4-STYLE-CANT task from "Use chrome-cold and wired-in only in
spoken dialogue" to "Use chrome-cold and wired-in in the spoken dialogue
lines" will align the task text with the `required_terms` check
(casefolded substring presence), closing the last task-vs-check overclaim
in the corpus. Removing "only" prevents suite consumers from
over-interpreting the task as enforcing slot-placement or register-leakage
detection that the check does not perform. The phrasing "in the spoken
dialogue lines" guides the model toward the intended slots without
claiming the check enforces exclusivity.

## Exact Changes

### Revised cases (1)

- **R4-STYLE-CANT** (plan_id: plan_style_cant, revision 1 to 2):
  Change task from "Fill one neutral narration slot and two fixed-speaker
  lines. Use chrome-cold and wired-in only in spoken dialogue." to "Fill
  one neutral narration slot and two fixed-speaker lines. Use chrome-cold
  and wired-in in the spoken dialogue lines." No other fields changed.

### New cases

None. The canonical test guard enforces a frozen 24-case corpus. Adding
new cases would require an operator-approved signed code commit outside
the permitted edit set.

## Rollback Condition

Revert this change if any validation command fails, if the published
result shows architecture-pairing violation, or if the revision proves
non-discriminating.

## Suite Baseline Status

This is the first suite baseline for the revised corpus (5 cases at
revision 2: R0-ORDINARY-FANTASY, R2-MULTI-DIALOGUE, R3-HUB-COPY,
R4-STYLE-CANT, R8-CHOICE-DISTINCTION). The architecture benchmark has not
yet produced a result. A successful benchmark run will establish the
first baseline.

## Benchmark Attempt

### Attempt 1 (2026-08-16, scheduled cron job)

Pre-flight checks confirmed: no active managed processes, HEAD (0a60af5)
descends from signed trust commit 897fc29a, SSH config has the
sugarcube-benchmark host entry. The corpus (24 cases, 5 at revision 2)
passed all validation (JSON valid, loader OK, 134 tests passed, working
tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_b8a9a6a42141). The process exited with exit code 255 (SSH
error). The benchmark PC was not reachable at the network level — the same
network-unreachable condition as iteration-01 attempts 1 through 8 and
iteration-19 attempt 1.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark. This appears to be a persistent
network outage (now spanning 11 attempts over 10 consecutive days,
2026-08-07 through 2026-08-16).

## Conclusion

The corpus revision (R4-STYLE-CANT rev 1 to 2, task-vs-check alignment on
the register-placement axis) is committed and pushed. The architecture
benchmark could not be completed due to network unreachability. The
revised suite baseline remains pending a successful benchmark run. The
last verified suite is preserved. Operator review is required to restore
network connectivity to the benchmark PC.
