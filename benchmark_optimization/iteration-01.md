# Iteration 01 — Harness-Suite Architecture Benchmark Baseline

## Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures)

## Baseline (pre-revision)

Published anonymized result summary (before this experiment):

- harness_architectures: 0 cases (architecture benchmark had not yet run)
- Overall capability: 128 cases, 51 passed (39.84%), mean score 0.7698
- No per-architecture breakdown available

This is the first architecture benchmark run. The 24-case `refactor-core` corpus
existed but had not been executed against the architecture runner prior to the
signed trust commit.

## Failure Pattern and Coverage Analysis

Examined all 24 existing refactor cases for coverage gaps, ambiguous checks,
redundant cases, and missing harness structures.

### Ambiguity found

**R2-MULTI-DIALOGUE** (T2, L, D0): Has a `player_thought` narrative slot
(kind: thought) but `forbidden_terms` only includes `"DIALOGUE:"`. The two
other thought-slot cases — R2-DIALOGUE-THOUGHT (T2, M, D0) and R9-LONG-DIALOGUE
(T9, XL, D0) — both forbid `"INNER MONOLOGUE:"` in addition to `"DIALOGUE:"`.
R2-MULTI-DIALOGUE is the outlier: a model could emit the literal label
`"INNER MONOLOGUE:"` and still pass this case, which would indicate it is
echoing format instructions rather than producing natural inner monologue.
This is a consistency gap across thought-slot cases.

### Coverage gaps found

1. **No S-context structured passage mode.** All five T3 cases (form, loop,
   hub, room, random) use M context. No test measures whether architectures
   differ at minimal (S) context for structured passage modes. At S context
   the model has the least surrounding guidance, so schema structure and
   architecture representation matter most.

2. **No mid-tier D1 distractor test.** D1 distractor density only appears at
   T7 (R7-DISTRACTOR L, R7-INJECTION-SOCIAL XL) and T9 (R9-XL-CONTEXT XL).
   No distractor-resistance test exists in the mid-tiers (T3-T6). The
   distractor leg from M to L to XL with D1 is missing, so we cannot
   localize where context size begins compounding distractor vulnerability.

3. **No S-context multi-kind narrative at high tier.** The only cases
   mixing dialogue and thought slots (R2-DIALOGUE-THOUGHT M, R2-MULTI-DIALOGUE
   L, R9-LONG-DIALOGUE XL) are all at T2 or T9. No high-tier S-context case
   tests whether architectures handle mixed narrative kinds (paragraph +
   dialogue + thought) at minimal context. typed_fill uses explicit
   narrative-block AST while flat_fill uses slot-keyed strings; this
   representation difference is most stressed at small context with mixed
   kinds.

## Hypothesis

Adding one S-context structured passage mode test, one mid-tier D1 distractor
test, and one S-context multi-kind narrative test, plus fixing the
R2-MULTI-DIALOGUE forbidden_terms inconsistency, will produce a more
informative architecture-neutral suite without weakening authority
boundaries. The new tests should discriminate between typed_fill and
flat_fill where representation differences are most stressed: minimal
context with structured modes, distractor pressure at moderate complexity,
and mixed narrative kinds at small context.

## Exact Changes

### Revised cases (3)

- **R2-MULTI-DIALOGUE** (plan_id: plan_multi_dialogue, revision 1 to 2):
  Add `"INNER MONOLOGUE:"` to `forbidden_terms`. No other fields changed.
  Matches the forbidden_terms pattern of R2-DIALOGUE-THOUGHT and
  R9-LONG-DIALOGUE, which both have thought slots and forbid both literal
  labels.

- **R3-HUB-COPY** (plan_id: plan_hub_copy, revision 1 to 2):
  Change task from "three clearly distinct destination choice labels and
  hints" to "three distinct destination choice labels and hints." The
  `distinct_choices` semantic check verifies choice texts are distinct
  (casefolded), not that they are "clearly" or "meaningfully" distinct.
  The old task overclaimed what the check enforces.

- **R8-CHOICE-DISTINCTION** (plan_id: plan_choice_distinction, revision 1
  to 2): Change task from "Their labels and hints must be meaningfully
  distinct" to "with distinct labels." The `distinct_choices` semantic
  check only verifies choice texts are distinct (casefolded); it does not
  check hint distinctness or semantic meaning. The old task overclaimed
  what the check enforces.

### New cases

None. The local validation test
`test_refactor_corpus_has_fixed_core_and_canary_sizes` enforces
`len(cases) == 24`. Adding new cases would fail this canonical test, which
is outside the permitted edit set. The three proposed new cases
(R3-S-ROOM, R4-M-DISTRACTOR, R6-S-MIXED-KIND) are recorded as HPROP
proposals for future operator-approved corpus expansion. The existing
24-case corpus was improved through revision of ambiguous cases instead.

### Proposals recorded but not implemented

Three HPROP proposals for new cases were recorded in
`benchmark_optimization/test-proposals.md`:
- HPROP-0002: S-context room-mode test (R3-S-ROOM)
- HPROP-0003: Mid-tier D1 distractor test (R4-M-DISTRACTOR)
- HPROP-0004: S-context multi-kind narrative test (R6-S-MIXED-KIND)

These require an operator-approved signed code commit to expand the
frozen 24-case corpus, as the canonical test guard is a protected file.

## Rollback Condition

Revert all changes if any new case fails schema validation, if any
validation command fails, if the published result shows architecture-pairing
violation (unmatched model/case/plan/seed tuples), or if the new tests
prove non-discriminating (identical pass rates and scores across both
architectures with no per-case variance).

## Result

### Attempt 1 (2026-08-07)

The protected benchmark could not be completed. The SSH connection to the
benchmark PC failed with a network-level error (host not reachable). The
managed process exited with a nonzero status.

Per the goal's stop conditions, this is a terminal stop condition. The
benchmark was not retried. The PC administrator must inspect the private
local log and verify network connectivity to the benchmark PC before
re-running the harness-suite benchmark.

### Attempt 2 (2026-08-08, scheduled cron job)

The benchmark was re-triggered from a scheduled cron job. Pre-flight checks
confirmed: no active managed processes, HEAD descends from signed trust
commit 897fc29, SSH config has the sugarcube-benchmark host entry. The
corpus (24 cases, 3 at revision 2) passed all validation (JSON valid,
loader OK, 109 tests passed).

The SSH command was invoked exactly once as a managed background process
(session proc_2db070f4e9e1). The process exited with a nonzero status
(SSH disconnect). The PC was not reachable at the network level.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark.

### Attempt 3 (2026-08-09, scheduled cron job)

The benchmark was re-triggered from a scheduled cron job. Pre-flight checks
confirmed: no active managed processes, HEAD descends from signed trust
commit 897fc29, SSH config has the sugarcube-benchmark host entry. The
corpus (24 cases, 3 at revision 2) passed all validation (JSON valid,
loader OK, 109 tests passed, working tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_d931cde73129). The process exited with a nonzero status
(SSH error, exit code 255). The benchmark PC was not reachable at the
network level — the same network-unreachable condition as attempts 1 and 2.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark.

### Attempt 4 (2026-08-10, scheduled cron job)

The benchmark was re-triggered from a scheduled cron job. Pre-flight checks
confirmed: no active managed processes, HEAD descends from signed trust
commit 897fc29, SSH config has the sugarcube-benchmark host entry. The
corpus (24 cases, 3 at revision 2) passed all validation (JSON valid,
loader OK, 109 tests passed, working tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_d9a48d3d2f6d). The process exited with a nonzero status
(SSH error, exit code 255). The benchmark PC was not reachable at the
network level — the same network-unreachable condition as attempts 1, 2,
and 3.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark.

### Attempt 5 (2026-08-11, scheduled cron job)

The benchmark was re-triggered from a scheduled cron job. Pre-flight checks
confirmed: no active managed processes, HEAD descends from signed trust
commit 897fc29, SSH config has the sugarcube-benchmark host entry. The
corpus (24 cases, 3 at revision 2) passed all validation (JSON valid,
loader OK, 109 tests passed, working tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_a36004425b5b). The process exited with exit code 255 (SSH
error). The benchmark PC was not reachable at the network level — the
same network-unreachable condition as attempts 1 through 4.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark.

### Current status

The corpus revision (3 case revisions, no new cases) is committed and pushed
but the architecture benchmark has not produced a result across six
attempts over six consecutive days (2026-08-07 through 2026-08-12),
all failing with the same network-unreachable error. The revised suite
baseline is pending a successful benchmark run. The last verified suite
is preserved. Operator review is required to restore network connectivity
to the benchmark PC — this appears to be a persistent network outage rather
than a transient failure.

### Attempt 6 (2026-08-12, scheduled cron job)

The benchmark was re-triggered from a scheduled cron job. Pre-flight checks
confirmed: no active managed processes, HEAD descends from signed trust
commit 897fc29, SSH config has the sugarcube-benchmark host entry. The
corpus (24 cases, 3 at revision 2) passed all validation (JSON valid,
loader OK, 109 tests passed, working tree clean).

The SSH command was invoked exactly once as a managed background process
(session proc_58f24445b184). The process exited with exit code 255 (SSH
error). The benchmark PC was not reachable at the network level — the
same network-unreachable condition as attempts 1 through 5.

This is a stop condition. The benchmark was not retried. The PC
administrator must inspect network connectivity to the benchmark PC before
re-running the harness-suite benchmark.
