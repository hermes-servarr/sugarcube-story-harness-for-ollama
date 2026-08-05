# Fixed-Plan Harness Architecture Tests

Edit `model_benchmark/refactor_cases.json` only in `harness-suite` mode. The
file is one JSON array; `refactor-core` runs every validated item against every
configured architecture.

## Change Rules

- Preserve every existing case ID and plan ID.
- Increment `plan.revision` whenever an existing case's task, plan, or expected
  behavior changes.
- Add no more than four new cases per experiment. Use a unique `R<tier>-...` ID,
  unique lowercase `plan_id`, and revision `1`.
- Do not delete, rename, disable, or reorder a case merely to alter aggregate
  results.
- Hold context, plan, seed, evaluator, model artifact, and request budget fixed
  across architecture treatments.
- Specify observable intent, not one architecture's JSON layout, SugarCube
  syntax, prose wording, or parser convention.

## Case Shape

```json
{
  "schema_version": 1,
  "id": "R2-EXAMPLE",
  "tier": 2,
  "context_ref": "fantasy",
  "context_size": "M",
  "distractor_density": "D0",
  "task": "Fill the trusted scene and choice-copy slots.",
  "plan": {
    "plan_id": "plan_example",
    "revision": 1,
    "passage_mode": "normal",
    "narrative_slots": [{"id": "scene", "kind": "paragraph"}],
    "choice_slots": ["choice_continue", "choice_leave"],
    "allowed_state_refs": [],
    "allowed_entity_refs": [],
    "required_components": []
  },
  "expected": {
    "context_needles": [],
    "required_state_refs": [],
    "required_entity_refs": [],
    "required_terms": [],
    "forbidden_terms": [],
    "min_words": 20
  }
}
```

Allowed values:

- tier: integer 0-9;
- context: an existing signed fixture ID;
- context size: `S`, `M`, `L`, or `XL`;
- distractors: `D0` or `D1`;
- passage mode: `normal`, `dialogue_loop`, `ending`, `form`, `hub`, `loop`,
  `random`, or `room`;
- narrative kind: `paragraph`, `dialogue`, or `thought`;
- context needles: `archive_code`, `treaty_name`, or `witness_name`.

IDs use lowercase letters, digits, and underscores; case IDs use the existing
uppercase `R<tier>-...` convention. Every required reference must also appear
in its plan allowlist. Use required components only as trusted plan facts; the
model must not author or reproduce their implementation syntax.

## Proposal Record

Before editing the corpus, append a harness-test proposal to
`benchmark_optimization/test-proposals.md`:

```markdown
## HPROP-0001 — Short title

- Status: proposed
- Proposed in iteration: iteration-NN
- Action: revise CASE-ID | add NEW-CASE-ID
- Coverage gap: Missing or ambiguous behavior.
- Competing structures: The harness approaches this test may distinguish.
- Hypothesis: One falsifiable architecture-level claim.
- Controlled inputs: Context, plan authority, seed, budget, and model pairing.
- Observable outcomes: Architecture-neutral request-level behaviors.
- Existing-case changes: Exact fields and revision increment, or `none`.
- New cases: IDs and purpose, or `none`.
- Why current corpus is insufficient: Concrete ambiguity or missing coverage.
- Resource estimate: cases × architectures × models × seeds.
- Rejection conditions: Invalid, redundant, unstable, biased, or non-discriminating.
- First suite baseline: pending
```

Never call a changed suite better because its aggregate pass rate changed. A
suite is better when it closes a declared coverage gap, remains deterministic,
preserves authority boundaries, and yields interpretable architecture-level
evidence.

## Validation

Run all commands before committing:

```bash
python -m json.tool model_benchmark/refactor_cases.json >/dev/null
uv run python -c "from model_benchmark.refactor_benchmark import load_refactor_cases; load_refactor_cases()"
uv run pytest -q -s model_benchmark/tests/test_refactor_benchmark.py model_benchmark/tests/test_profiles.py model_benchmark/tests/test_cli_subcommands.py model_benchmark/tests/test_hermes_benchmark_publish.py
```

Then confirm changed paths are limited to the case corpus, one iteration note,
and the proposal backlog. The protected publisher performs another bounded JSON
check before starting Ollama; the signed benchmark loader performs full schema
validation.
