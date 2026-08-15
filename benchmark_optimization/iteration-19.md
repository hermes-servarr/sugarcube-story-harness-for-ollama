# Iteration 19: Harness-Suite R0-ORDINARY-FANTASY task-vs-check alignment

## Campaign Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures)

## Baseline Metrics (pre-revision)

Published anonymized result summary (before this experiment):

- harness_architectures: 0 cases (architecture benchmark has not yet produced a result)
- Overall capability benchmark: 128 cases, 51 passed (39.84%), mean score 0.7698
- No per-architecture breakdown available

The architecture benchmark has not produced a result across prior attempts
(iteration-01, attempts 1-8, all failed with network-unreachable errors).
The corpus revision from iteration-01 (R2-MULTI-DIALOGUE rev 2, R3-HUB-COPY
rev 2, R8-CHOICE-DISTINCTION rev 2) is committed and visible in the current
working tree.

## Failure Pattern and Coverage Analysis

### Ambiguity found

**R0-ORDINARY-FANTASY** (T0, S, D0): The task says "Fill the opening paragraph
and two materially different choice-copy slots." The word "materially"
implies a semantic-content distinctness requirement, but the
`distinct_choices` semantic check only verifies that choice texts are
casefolded-string distinct. This is the same class of task-vs-check
overclaim that iteration-01 fixed for R3-HUB-COPY ("clearly distinct" to
"distinct") and R8-CHOICE-DISTINCTION ("meaningfully distinct" to "distinct
labels"). R0-ORDINARY-FANTASY is the remaining outlier with a qualifying
adverb ("materially") that overclaims what the deterministic check enforces.

### Coverage gaps

No new coverage gaps identified beyond those already recorded as HPROP
proposals 0002-0004 in iteration-01. Those proposals require an
operator-approved signed code commit to expand the frozen 24-case corpus
(the canonical test guard `test_refactor_corpus_has_fixed_core_and_canary_sizes`
enforces `len(cases) == 24`).

### Prior revisions preserved

The three case revisions from iteration-01 remain in the corpus:
- R2-MULTI-DIALOGUE: plan_multi_dialogue, revision 2 (forbidden_terms now
  includes "INNER MONOLOGUE:")
- R3-HUB-COPY: plan_hub_copy, revision 2 (task: "three distinct" not "three
  clearly distinct")
- R8-CHOICE-DISTINCTION: plan_choice_distinction, revision 2 (task: "with
  distinct labels" not "meaningfully distinct")

## Hypothesis

Changing the R0-ORDINARY-FANTASY task from "two materially different
choice-copy slots" to "two distinct choice-copy slots" will align the task
text with the `distinct_choices` check (casefolded string distinctness),
closing the last task-vs-check overclaim in the corpus. This prevents suite
consumers from over-interpreting "materially" as enforcing semantic-content
distinctness that the check does not verify.

## Exact Changes

### Revised cases (1)

- **R0-ORDINARY-FANTASY** (plan_id: plan_ordinary_fantasy, revision 1 to 2):
  Change task from "Fill the opening paragraph and two materially different
  choice-copy slots. Keep the scene focused on the discovered tome." to
  "Fill the opening paragraph and two distinct choice-copy slots. Keep the
  scene focused on the discovered tome." No other fields changed.

### New cases

None. The canonical test guard enforces a frozen 24-case corpus. Adding new
cases would require an operator-approved signed code commit outside the
permitted edit set.

## Rollback Condition

Revert this change if any validation command fails, if the published result
shows architecture-pairing violation, or if the revision proves
non-discriminating.

## Suite Baseline Status

This is the first suite baseline for the revised corpus (4 cases at
revision 2: R0-ORDINARY-FANTASY, R2-MULTI-DIALOGUE, R3-HUB-COPY,
R8-CHOICE-DISTINCTION). The architecture benchmark has not yet produced
a result. A successful benchmark run will establish the first baseline.

## Benchmark Attempt

### Attempt 1 (2026-08-15, scheduled cron job)

Pre-flight checks confirmed: no active managed processes, HEAD (083c307)
descends from signed trust commit 897fc29a, SSH config has the
sugarcube-benchmark host entry. The corpus (24 cases, 4 at revision 2)
passed all validation (JSON valid, loader OK, 109 tests passed, working
tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_a1aca4efb48d). The process exited with exit code 255 (SSH
error). The benchmark PC was not reachable at the network level - the same
network-unreachable condition as iteration-01 attempts 1 through 8.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark. This appears to be a persistent
network outage (now spanning 9 attempts over 9 consecutive days,
2026-08-07 through 2026-08-15).

## Conclusion

The corpus revision (R0-ORDINARY-FANTASY rev 1 to 2, task-vs-check
alignment) is committed and pushed. The architecture benchmark could not
be completed due to network unreachability. The revised suite baseline
remains pending a successful benchmark run. The last verified suite is
preserved. Operator review is required to restore network connectivity
to the benchmark PC.
