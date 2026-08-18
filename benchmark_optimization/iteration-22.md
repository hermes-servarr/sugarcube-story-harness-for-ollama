# Iteration 22: Harness-Suite benchmark attempt on revised corpus

## Campaign Mode

harness-suite (refactor-core profile, typed_fill + flat_fill architectures)

## Baseline Metrics (pre-revision)

Published anonymized result summary (before this experiment):

- harness_architectures: 0 cases (architecture benchmark has not yet produced a result)
- Overall capability benchmark: 128 cases, 51 passed (39.84%), mean score 0.7698
- No per-architecture breakdown available

The architecture benchmark has not produced a result across prior attempts
(iteration-01 through iteration-21, attempts 1-12, all failed with
network-unreachable errors). The corpus revisions from iteration-01
(R2-MULTI-DIALOGUE rev 2, R3-HUB-COPY rev 2, R8-CHOICE-DISTINCTION rev 2),
iteration-19 (R0-ORDINARY-FANTASY rev 2), iteration-20 (R4-STYLE-CANT rev 2),
and iteration-21 (R2-MULTI-DIALOGUE rev 3) are committed and visible in the
current working tree.

## Failure Pattern and Coverage Analysis

### Corpus audit

Systematic audit of all 24 cases in model_benchmark/refactor_cases.json
against the scoring logic in score_refactor_fill (refactor_benchmark.py)
and each case's plan composition:

**Already revised (5 cases at revision 2+):**
- R0-ORDINARY-FANTASY: rev 2 (task: "two distinct" not "two materially different")
- R2-MULTI-DIALOGUE: rev 3 (task: "five...and one private thought"; forbidden_terms
  includes "INNER MONOLOGUE:")
- R3-HUB-COPY: rev 2 (task: "three distinct" not "three clearly distinct")
- R4-STYLE-CANT: rev 2 (task: "in the spoken dialogue lines" not "only in spoken
  dialogue")
- R8-CHOICE-DISTINCTION: rev 2 (task: "with distinct labels" not "meaningfully
  distinct")

**Remaining revision-1 cases (19 cases):** All checked for task-vs-check
overclaims (task implying a stronger check than score_refactor_fill enforces)
and task-vs-plan mismatches (task mislabeling plan slot composition, kinds, or
speakers). No remaining issues found. Each task accurately reflects its plan's
slot composition and does not overclaim what the deterministic checks enforce.

The deterministic semantic checks in score_refactor_fill are:
- context: context_needles appear as casefolded substrings in the fill text
- state_refs: required_state_refs appear as used state_ref parts
- entity_refs: required_entity_refs appear as used entity_ref parts
- required_terms: required_terms appear as casefolded substrings anywhere in text
- forbidden_terms: forbidden_terms do not appear as casefolded substrings
- min_words: word count >= min_words
- no_markup_code: no SugarCube/Markdown syntax in assembled text
- distinct_choices: choice texts are casefolded-distinct

### New-case proposals blocked

HPROP-0002 (R3-S-ROOM), HPROP-0003 (R4-M-DISTRACTOR), and HPROP-0004
(R6-S-MIXED-KIND) remain proposed but unexecutable. The canonical test guard
test_refactor_corpus_has_fixed_core_and_canary_sizes enforces
len(cases) == 24. Adding new cases requires an operator-approved signed code
commit outside the permitted data-only edit set.

### No new HPROP proposals this iteration

The corpus is at its best revised state. No additional test-validity fixes
or data-only revisions are warranted.

## Hypothesis

No corpus change is needed this iteration. The 5 test-validity fixes from
iterations 01, 19, 20, and 21 are already committed. The corpus is validated
(134 tests pass). Proceed directly to the benchmark attempt with the current
revised corpus to establish the first architecture-suite baseline.

## Exact Changes

### Revised cases

None. No corpus edits this iteration.

### New cases

None. The frozen 24-case corpus guard blocks new cases without an
operator-approved signed code commit.

## Validation

All validation commands passed:

- python -m json.tool model_benchmark/refactor_cases.json: valid
- uv run python -c "from model_benchmark.refactor_benchmark import
  load_refactor_cases; load_refactor_cases()": OK
- uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py
  model_benchmark/tests/test_profiles.py
  model_benchmark/tests/test_cli_subcommands.py
  model_benchmark/tests/test_hermes_benchmark_publish.py: 134 passed

## Rollback Condition

No corpus changes made, so no rollback needed. If the benchmark fails, the
last verified suite is preserved.

## Suite Baseline Status

This is the first suite baseline for the revised corpus (5 cases at revision
2+: R0-ORDINARY-FANTASY rev 2, R2-MULTI-DIALOGUE rev 3, R3-HUB-COPY rev 2,
R4-STYLE-CANT rev 2, R8-CHOICE-DISTINCTION rev 2, and 19 cases at rev 1). The
architecture benchmark has not yet produced a result. A successful benchmark
run will establish the first baseline.

## Benchmark Attempt

### Attempt 1 (2026-08-18, scheduled cron job)

Pre-flight checks confirmed: no active managed processes, HEAD
(49702e22) descends from signed trust commit 897fc29a, SSH config has the
sugarcube-benchmark host entry. The corpus (24 cases, 5 at revision 2+,
R2-MULTI-DIALOGUE at revision 3) passed all validation (JSON valid, loader
OK, 134 tests passed, working tree clean).

[benchmark result pending]
