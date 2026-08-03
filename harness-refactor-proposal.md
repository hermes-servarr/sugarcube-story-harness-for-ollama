# Harness Refactor Proposal: Structured Intent, Deterministic SugarCube

## Status

- **Proposal date:** 2026-08-03
- **Scope:** Passage generation, normalization, validation, rendering, draft persistence, and benchmark integration
- **Primary evidence:** `benchmark_anon/results_anonymized.json`, `benchmark_optimization/iteration-16.md`, `benchmark_optimization/lessons-learned.md`, and the current harness code
- **Recommendation:** Replace direct sectioned/SugarCube generation as the production default with a typed passage-intent contract and deterministic SugarCube compilation. Keep the existing path as a compatibility adapter during migration.

## Executive Summary

The current harness asks one model response to perform five jobs at once:

1. understand story context;
2. plan a scene and choices;
3. express state and game mechanics;
4. serialize a private section-based transport format; and
5. write valid SugarCube markup.

The benchmark indicates that this coupling is the dominant source of failure. Models often produce useful story material but fail the transport or macro contract. Adding more prompt reminders has repeatedly produced variant-specific regressions rather than a stable improvement.

The harness should instead make the default model call responsible for
**narrative and choice copy inside predefined slots**. Deterministic code owns
**SugarCube syntax, passage structure, state transactions, links, forms, loops,
and compilation**. When creative mechanic help is requested, it uses a separate
bounded proposal that cannot grant itself authority.

The proposed production path is:

```text
GenerationRequest
  -> ContextPack
  -> GenerationStrategy
  -> PassagePlan (trusted harness skeleton)
  -> NarrativeFill (model-owned text boxes)
  -> optional MechanicProposal (separate, untrusted)
  -> PassageDraft (validated assembly)
  -> SugarCubeCompiler
  -> compile/runtime checks
  -> persisted review draft
  -> atomic commit
```

This is an incremental refactor rather than a rewrite. The codebase already has most of the necessary foundations: `ModelOutput`, Pydantic schemas, JSON-schema delivery through Ollama, deterministic choice/state rendering, graph transactions, validation, compilation, and browser playtesting.

## Evidence Boundary

There is no single model run that exactly represents both the current prompt configuration and the current benchmark contract.

- The latest published artifact contains **248 cases with 49 passes (19.8%)**. It measures the Experiment 16 compact suffix.
- Experiment 16 regressed from the documented control of **53/248 (21.4%)** and was rolled back immediately afterward.
- The named `canary`, `core`, and `full` profiles and the architecture-neutral harness-contract cases were committed after that artifact was produced.
- All 248 published cases use one recorded seed (`42`), and token counts are zero, so small model differences and budget-related explanations are not reliable.

Therefore, this proposal uses the artifact to identify **recurring failure modes**, not to claim a current model ranking or a statistically established effect size. Phase 0 must produce a fresh, paired `core` baseline before implementation choices are promoted.

## What the Benchmark Says

### Latest Published Artifact

| Cohort | Passed | Rate | Mean runtime |
|---|---:|---:|---:|
| Direct A-H generation matrix | 42/128 | 32.8% | 13.8 s |
| Capability ladder | 7/120 | 5.8% | 16.3 s |
| Total | 49/248 | 19.8% | 15.0 s |

### Matrix Results by Output Variant

| Variant | Passed | Mean score | Mean runtime | Interpretation |
|---|---:|---:|---:|---|
| `json` | 21/32 (65.6%) | 0.880 | 10.8 s | Best current transport signal; already benefits from schema-constrained output |
| `compact` | 9/32 (28.1%) | 0.737 | 13.0 s | Better than full text, but repeated compact reminders regressed Experiment 16 |
| `full` | 6/32 (18.8%) | 0.717 | 9.9 s | Structurally overloaded despite reasonable partial scores |
| `thinking` | 6/32 (18.8%) | 0.570 | 21.6 s | Slowest path and no more reliable than full text |

The useful conclusion is not that JSON is solved. It is that **one constrained contract outperforms a long mixed transport/markup contract**. JSON should become the handoff format, while the schema itself should be simplified around model-owned intent.

This also argues against the current production defaults in `HarnessConfig` (`model_mode: compact`, `output_format: delimited`) as the long-term universal path. They should remain compatibility defaults until the shadow comparison passes, then migrate through an explicit config version rather than changing silently.

### Dominant Failure Signals

Across the capability cases:

| Observable | Failures | Why it matters |
|---|---:|---|
| Required macro behavior | 60/64 | Models do not reliably translate intent into the requested SugarCube macro |
| Balanced macros | 28/28 | Direct macro emission is not a safe production boundary |
| State variable behavior | 21/32 | State intent and SugarCube implementation are being conflated |
| Minimum dialogue turns | 23/32 | Conversation constraints compete with the envelope and mechanics |
| Conversation layout | 21/44 | Mostly adoption of a private serialization convention |
| Context fact retrieval | 22/60 | Context assembly/retrieval also needs improvement, but is not the only bottleneck |
| Minimum choices | 18/96 | Structured scene handoff remains incomplete in some outputs |
| No Markdown | 16/92 | Markup normalization should be deterministic rather than a model gate |

The parser also recorded:

- 135 missing `SUMMARY` warnings;
- 74 missing `CHOICES` warnings;
- 63 missing `PROSE` warnings;
- 59 raw-output prose fallbacks; and
- 5 JSON-to-delimited fallbacks.

These are transport failures. A missing summary should not invalidate good prose, and a private `DIALOGUE:` label should not determine whether a conversation is usable.

### Model Ranking Is Not Yet Actionable

The four anonymized models passed between 9 and 14 of 62 cases. With one seed, changed prompt treatments, and no token/finish metadata in the artifact, that spread is not enough to hard-code model-specific behavior. Routing should use repeated capability measurements tied to the exact model digest and chat template, not model-name heuristics alone.

## Current Architectural Mismatch

### The Harness Already Owns Rendering

`harness/passage.py` already renders choices, state assignments, forms, conditions, random events, hubs, loops, and passage metadata. This is the right ownership boundary.

However, the prompts still ask the model to reason in SugarCube terms and sometimes emit macros directly. The benchmark then penalizes the model for syntax that the harness can generate more reliably itself.

### `ModelOutput` Is Close to an Intermediate Representation

`ModelOutput` in `harness/models.py` already carries prose, choices, state, inputs, continuity changes, media, summary, and beats. It should evolve into a versioned passage-intent contract rather than remain the result of a permissive section parser.

Its main problems are:

- prose can contain arbitrary SugarCube and Markdown;
- choice guards are raw expression strings;
- state effects are only a loose dictionary;
- conversation structure is embedded in prose conventions;
- passage mechanics are split between model output and commit-request fields; and
- parser warnings are mixed into domain data.

### Draft Generation and Commit Can Disagree

`/api/generate` returns and persists parsed output, but `/api/commit` accepts the raw response again and reparses it with the delimited parser when no override is supplied. A JSON generation can therefore be interpreted through a different route at commit time.

The commit boundary should reference an immutable, validated draft by ID and revision. Raw output should remain provenance, not the source of truth.

### Prompt Selection Uses Heuristics, Not Measured Capabilities

`model_profile()` routes mainly from model names and parameter-size hints. This is useful for initial limits but cannot capture chat-template quality, structured-output reliability, mechanic accuracy, or real context capacity.

### Transport Metadata Is Inconsistent

The synchronous benchmark path can retain Ollama token counts and finish reason, while the asynchronous production path returns only text. Production and benchmark calls should use one result envelope so truncation, retries, latency, and repair decisions are observable everywhere.

## Refactor Goals

1. Make schema-valid model output independent of SugarCube syntax.
2. Compile all supported mechanics deterministically.
3. Preserve prose quality and human editability.
4. Separate raw model compliance from final harness usability.
5. Make generation, validation, review, and commit use the same typed artifact.
6. Localize failures to context, generation, normalization, semantics, compilation, or runtime.
7. Route models and strategies from measured capability profiles.
8. Keep legacy projects and draft records readable throughout migration.
9. Keep trusted passage structure separate from untrusted model-authored text
   and mechanic proposals.

## Non-Goals

- Replacing Ollama or adding a cloud dependency.
- Building a general-purpose SugarCube parser.
- Removing human review before commit.
- Requiring multi-agent generation for every passage.
- Making narrative prose fully grammar-constrained.
- Optimizing benchmark pass rate at the expense of story quality.

## Proposed Domain Contract

Use three trust-layer contracts plus one assembled compiler artifact. The model
does not directly produce the compiler input.

```python
class PassagePlan(BaseModel):
    schema_version: Literal["1"] = "1"
    plan_id: str
    revision: int
    passage_mode: PassageMode
    narrative_slots: list[NarrativeSlot]
    choice_slots: list[ChoiceSlot]
    allowed_state_reads: list[str] = Field(default_factory=list)
    allowed_effects: list[AllowedEffect] = Field(default_factory=list)
    required_components: list[MechanicComponent] = Field(default_factory=list)
    open_mechanic_slots: list[MechanicSlot] = Field(default_factory=list)


class NarrativeFill(BaseModel):
    plan_id: str
    plan_revision: int
    narrative: list[NarrativeBlock]
    choices: list[ChoiceCopy]
    continuity_proposals: ContinuityDelta = Field(default_factory=ContinuityDelta)
    media_proposals: list[MediaProposal] = Field(default_factory=list)
    summary: str = ""
    beats: list[str] = Field(default_factory=list)


class MechanicProposal(BaseModel):
    plan_id: str
    plan_revision: int
    guards: list[GuardProposal] = Field(default_factory=list)
    effects: list[StateEffectProposal] = Field(default_factory=list)
    components: list[MechanicComponentProposal] = Field(default_factory=list)


class PassageDraft(BaseModel):
    plan: PassagePlan
    narrative: NarrativeFill
    resolved_mechanics: list[MechanicComponent]
```

`PassagePlan` is created by deterministic harness logic, explicit human input,
or an approved planning step. `NarrativeFill` is the default model output: it
fills known prose, dialogue, thought, and choice-copy slots. A
`MechanicProposal` is requested separately only when the plan leaves a bounded
mechanic decision open. The harness validates and resolves that proposal before
assembling `PassageDraft`.

Every fill/proposal item carries an existing slot ID. Assembly requires exactly
one value for every required slot, rejects duplicate or unknown slot IDs, and
rejects any reference, target, operation, or component outside the plan's
allowlists. Missing slots remain explicit failures; normalization does not
invent them.

The exact model-facing schema should remain smaller than the current full
prompt. Optional fields and union branches should appear only when the plan
allows them and the compiler supports and tests them.

### Narrative Blocks

Represent conversation and inner thought as data instead of requiring labels
inside a prose string. Ordinary slots remain simple text boxes. Slots that must
display dynamic values use typed inline spans rather than SugarCube syntax.

```json
{
  "narrative": [
    {"kind": "paragraph", "parts": [
      {"kind": "text", "text": "You have "},
      {"kind": "state_ref", "target": "gold"},
      {"kind": "text", "text": " coins as rain silvers the courtyard."}
    ]},
    {"kind": "dialogue", "speaker": "Mara", "parts": [
      {"kind": "text", "text": "You came back."}
    ]},
    {"kind": "thought", "speaker": "player", "parts": [
      {"kind": "text", "text": "She sounds afraid."}
    ]}
  ]
}
```

Supported block kinds for the first version should be `paragraph`, `dialogue`,
and `thought`. Initial inline parts should be `text`, `state_ref`, and
`entity_ref`. A plan that does not allow dynamic references exposes only plain
text parts in its generation schema. The compiler renders presentation and
safe interpolation. This removes both SugarCube variables and the benchmark's
private `DIALOGUE:`/`INNER MONOLOGUE:` convention from the model boundary.

### Typed Conditions and Effects

Replace free-form guards and model-authored setters with a constrained state DSL.

```json
{
  "guard": {"left": "gold", "op": "gte", "right": 5},
  "effects": [
    {"op": "add", "target": "gold", "amount": -5},
    {"op": "set", "target": "bought_lantern", "value": true}
  ]
}
```

Initial operations:

- conditions: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `truthy`, `falsy`, `contains`;
- effects: `set`, `add`, `append`, `remove`;
- composition: bounded `all`, `any`, and `not` nodes;
- targets: stable state IDs declared by the plan only for version 1. The legacy
  adapter/compiler maps those IDs to SugarCube `$` variables.

The compiler escapes literals, verifies target types, and emits the SugarCube expression. Arbitrary expressions remain an expert-mode escape hatch and are never accepted silently from model output.

### Typed Mechanics

Do not encode every passage as one optional `MechanicSpec`. Separate the
primary passage mode from composable mechanic components:

- passage modes: `normal`, `room`, `hub`, `dialogue_loop`, `form`, `loop`,
  `random`, `event`, `random_event`, and `ending`; `widget` and `include` remain
  reviewed expert modes during migration;
- components: `GuardSpec`, `BranchSpec`, `InputSpec`, `IterationSpec`,
  `WeightedChoiceSpec`, and typed effects attached to scene or choice slots.

Compatibility rules define which components may coexist. For example, a form
may have guarded choices and submit effects, while an ending may not expose an
unresolved destination. Dialogue blocks are narrative structure;
`dialogue_loop` is only the passage-navigation mode that keeps non-exit choices
in the same scene.

The trusted plan supplies required components whenever the user or passage type
already determines them. A separate mechanic stage may propose only components
and targets explicitly allowed by the plan. The compiler owns `<<if>>`,
`<<switch>>`, `<<for>>`, `<<capture>>`, input macros, setters, and link bodies.

### Separate Domain Data from Diagnostics

Move `parse_warnings` out of the domain model. Return a generation envelope instead:

```python
class DraftResult(BaseModel):
    plan: PassagePlan
    narrative_fill: NarrativeFill | None
    mechanic_proposal: MechanicProposal | None
    draft: PassageDraft | None
    raw_output: str
    diagnostics: list[GenerationDiagnostic]
    provenance: GenerationProvenance
```

This prevents fallback details from becoming part of committed story state.

## Target Pipeline

### 1. Context Assembly

Create a `ContextPack` with named, provenance-bearing blocks:

- human direction;
- parent scene and snapshot;
- relevant state declarations;
- required character/lore facts;
- current beat/arc goal;
- retrieved inspiration; and
- retrieved earlier-story facts.

Each block records source, priority, character/token estimate, and whether it is required or optional. Budget required facts first, then narrative context, then inspiration. Do not trim an undifferentiated prompt string after assembly.

This makes context failures testable and supports causal-ablation benchmarks.

### 2. Trusted Plan Construction

Construct `PassagePlan` before model generation from the commit request, parent
graph, passage type, declared state schema, and explicit human direction. For an
ordinary continuation, the plan may contain one narrative slot, two choice-copy
slots, no state effects, and a bounded list of allowed entity references. Forms,
loops, branches, and state transactions add programmatic slots and components
before prose is requested.

If the human asks the model to help design mechanics, the plan records explicit
open mechanic slots plus their allowed targets and operations. It does not trust
the narrative response to create new mechanical authority implicitly.

### 3. Strategy Routing

Add three explicit strategies:

| Strategy | Use | Calls |
|---|---|---:|
| `structured_fill` | Default: fill narrative and choice-copy slots in a trusted plan | 1 |
| `structured_staged` | A bounded mechanic decision remains open after planning | 2 |
| `legacy_delimited` | Compatibility and benchmark control only | 1 plus current repair behavior |

`structured_fill` never asks the narrative model to invent state transactions
or passage structure. The plan fixes slot IDs, allowed references, choice count,
and required mechanics before generation.

`structured_staged` should split authoring from mechanic proposal, not create
an open-ended agent conversation:

1. **Author stage:** fill narrative blocks, choice copy, continuity proposals,
   summary, and beats against an immutable `PassagePlan`.
2. **Mechanic stage:** propose only the unresolved guards, effects, or
   components allowed by that same plan and current state schema.

The harness validates the mechanic proposal independently and may require human
approval before assembly. Use staged generation only when the human requested
model assistance with mechanics or prior capability measurements justify its
latency.

### 4. Schema-Constrained Generation

Send the smallest plan-derived JSON schema through Ollama's `format` field.
Avoid describing delimited sections inside the JSON prompt. A plain narrative
slot should expose strings and choice copy only. Dynamic inline spans, form
copy, or mechanic proposals should appear only when the trusted plan permits
them.

Every generated schema receives a stable profile ID and content hash. Store
both in provenance so dynamic schema reduction does not fragment comparisons
or allow two different contracts to share one benchmark label.

The prompt should describe story and semantic requirements. It should not include a SugarCube cheat sheet unless the model is explicitly being benchmarked on direct markup generation.

### 5. Normalization

Normalization must be deterministic and non-creative:

- coerce safe scalar mismatches;
- trim and deduplicate IDs, beats, and facts;
- normalize Markdown emphasis to the supported presentation form;
- generate a deterministic summary fallback from the first complete sentence;
- reject unknown state operations, undeclared targets, and references not
  allowed by the plan; and
- preserve all changes as diagnostics.

Normalization must never invent a missing choice, state effect, or continuity fact.

### 6. Semantic Validation

Validate the draft before rendering:

- required number of choices for the passage type;
- unique and non-empty choice text;
- state targets exist and value types match;
- guards only read allowed state;
- effects stay within the requested mutation scope;
- mechanic-specific invariants hold;
- referenced entities exist or are explicit proposals;
- continuity additions/removals do not contradict the parent snapshot; and
- passage type and mechanic are compatible.

Return stable error codes such as `STATE_UNKNOWN_TARGET`, `FORM_MISSING_SUBMIT`, or `CHOICE_DUPLICATE`, not prose-only warnings.

### 7. Deterministic Compilation

Extract rendering responsibilities from `harness/passage.py` into a pure `SugarCubeCompiler`:

```python
CompileArtifact compile_passage(PassageDraft, CompileContext)
```

`CompileArtifact` should contain:

- generated Twee source;
- state reads and writes;
- unresolved destination slots;
- source-map-like references from diagnostics to draft fields; and
- compiler diagnostics.

For a schema-valid draft, compiler syntax failures are harness defects, not model failures. Unit fixtures should cover every compiler branch.

### 8. Bounded Repair

Repair policy should depend on failure ownership:

| Failure | Action |
|---|---|
| JSON/schema invalid | One constrained schema-repair call with exact validation errors |
| Semantic mechanic invalid | One mechanic-only repair; preserve narrative |
| Missing summary | Deterministic fallback; no model call |
| SugarCube compiler failure | Fail fast as a harness defect |
| Browser/runtime failure | Block commit and report stable diagnostics; optionally repair only the responsible typed field |
| Narrative quality concern | Human review or explicit regenerate; never silent repair |

Do not regenerate the full passage to fix one setter or missing field.

### 9. Draft Persistence and Commit

Persist each `PassageDraft` with:

- generation ID and revision;
- schema version;
- raw output and normalized draft;
- exact prompt/context hashes;
- model digest and chat-template hash;
- sampler settings and seed;
- token counts, finish reason, latency, and repair route;
- validation and compile results; and
- parent snapshot hash.

Change commit to accept `generation_id`, plan revision, draft revision, and
optional typed edits. The server reloads the stored plan and assembled draft,
validates that neither the plan nor parent snapshot has changed, compiles it,
and commits graph/file changes atomically. Raw text is never reparsed at commit
time.

## Model Capability Routing

Add a persisted capability card keyed by model digest, quantization, chat-template hash, Ollama version, and context setting.

```yaml
structured_handoff_rate: 0.94
state_semantic_rate: 0.82
conversation_rate: 0.88
context_band: medium
p95_latency_seconds: 11.4
preferred_strategy: structured_fill
confirmed_seed_count: 10
```

The card informs strategy and budget selection but does not bypass validation.

Initial routing rules:

1. Prefer `structured_fill` for every passage with a complete trusted plan.
2. Use `structured_staged` only when the plan explicitly leaves a bounded
   mechanic decision open and the model's measured mechanic capability exceeds
   the configured threshold.
3. Reduce optional context before increasing instruction length.
4. Do not use the production `thinking` prompt. Reasoning models must return the same typed final contract; reasoning behavior remains a benchmark diagnostic.
5. Keep name/parameter heuristics only as a cold-start profile until a capability card exists.

## Proposed Module Boundaries

```text
harness/
  generation/
    contracts.py      # PassagePlan, fills, proposals, draft, typed submodels
    context.py        # ContextPack assembly and token budgets
    planning.py       # deterministic trusted plan construction
    strategies.py     # fill, staged proposal, legacy adapters
    pipeline.py       # orchestration and bounded repair
    normalization.py  # deterministic coercion/cleanup
    validation.py     # semantic validators and error codes
    provenance.py     # prompt/model/runtime capture
    drafts.py         # immutable draft persistence/revisions
  sugarcube/
    compiler.py       # PassageDraft -> CompileArtifact
    expressions.py    # typed condition/effect rendering
```

Existing modules change as follows:

- `harness/models.py`: retain story graph models; move generation contracts to `generation/contracts.py`.
- `harness/prompts.py`: keep planning prompts, add minimal structured author/mechanic prompts, freeze legacy passage prompts.
- `harness/generators.py`: become a compatibility facade over `generation/pipeline.py`.
- `harness/parsers.py`: retain legacy adapters and JSON salvage; remove it from the normal commit path.
- `harness/passage.py`: retain graph transaction and link resolution; delegate source rendering to `SugarCubeCompiler`.
- `harness/ollama_client.py`: return one detailed result type from async and sync calls.
- `harness/server/app.py`: generate and commit immutable typed drafts.
- `model_benchmark/`: add generation architecture as a treatment dimension and execute compiler/browser adapters after normalization.

## Migration Plan

### Phase 0: Freeze a Trustworthy Baseline

1. Define and freeze a semantic `refactor-core` cohort containing only fixed
   `PassagePlan` cases and architecture-neutral outcomes. Do not use the current
   mixed `core` aggregate, which also contains the direct A-H matrix.
2. Run the legacy adapter on `refactor-core` against the same four model
   artifacts using at least five fixed seeds for screening.
3. Store model digest, quantization, chat-template hash, rendered prompt, tokens, finish reason, and effective config.
4. Separate raw contract, structured handoff, semantic observables, latency, and applicable-check coverage.
5. Do not use the 49/248 Experiment 16 artifact as the control.

**Exit gate:** A reproducible paired baseline with compatible run capsules and a measured same-seed replay rate.

### Phase 1: Introduce Contracts and Compiler Parity

1. Define `PassagePlan`, `NarrativeFill`, `MechanicProposal`, assembled
   `PassageDraft`, typed state operations, and `CompileArtifact`.
2. Extract current rendering into pure compiler functions without changing emitted Twee.
3. Add fixture parity tests for all supported passage types.
4. Add hostile-value escaping tests and exact state read/write tests.

**Exit gate:** Existing tests pass and legacy `ModelOutput` compiles byte-equivalently through an adapter.

### Phase 2: Add Structured Shadow Generation

1. Implement `structured_fill` using the smallest plan-derived JSON schema.
2. Adapt legacy output into fills/proposals, then assemble both legacy and
   structured paths into `PassageDraft` through the same validator.
3. Run legacy and structured paths in benchmark pairs without changing the UI default.
4. Add compile and browser choice-effect evaluation.

**Exit gate:** Structured generation beats legacy on final usable/playable rate without a material narrative-quality regression.

### Phase 3: Make Typed Drafts the Product Boundary

1. Persist immutable drafts and revisions.
2. Change commit to use draft ID rather than raw reparse.
3. Show structured diagnostics and compiler output in review.
4. Make `structured_fill` the default for validated model profiles.

**Exit gate:** Generate-review-edit-commit uses one typed artifact end to end, with legacy fallback available by configuration.

### Phase 4: Add Staged Mechanics and Capability Routing

1. Implement separately persisted author fill/mechanic proposal staging.
2. Add model capability cards and measured routing.
3. Add mechanic-only repair.
4. Add context causal-ablation and multi-passage continuity tests.

**Exit gate:** Staging improves complex-mechanic semantic success enough to justify its added latency.

### Phase 5: Retire Direct SugarCube Generation as Default

1. Freeze delimited/full/thinking prompts as compatibility and research paths.
2. Remove raw-output reparse from commit.
3. Keep historical benchmark cases in `full`, retain the mixed `core` for
   transitional comparisons, and use frozen `refactor-core` results for
   architecture promotion.

**Exit gate:** No supported production feature requires model-authored SugarCube syntax.

## Benchmark Plan for the Refactor

Add an `architecture` axis:

- `legacy_delimited`
- `legacy_json`
- `typed_fill`
- `typed_staged`

Run matching model/case/seed triples against the frozen `refactor-core` plans.
The same plan IDs, revisions, semantic expectations, model artifacts, and seeds
must feed every architecture through adapters. Keep the direct A-H matrix as a
diagnostic cohort rather than mixing it into architecture-promotion aggregates.

### Headline Metrics

Report these independently:

1. raw transport validity;
2. normalized draft validity;
3. requested mechanic correctness;
4. exact state transaction correctness;
5. deterministic compile success;
6. browser playability and choice execution;
7. continuity correctness;
8. narrative and choice quality;
9. latency, calls, and token use; and
10. repair rate and repair-induced regressions.

Every report must include both stage-conditional rates and request-level rates.
The request-level denominator is every original generation request; repaired,
rejected, schema-invalid, or uncompiled attempts remain in that denominator.
Conditional rates such as “browser success among compiled drafts” are diagnostic
and may not serve as the promotion headline by themselves.

### Promotion Gates

After a five-seed screen, confirm on ten seeds. Promote the typed path only when:

- semantically accepted typed drafts compile at 100% as a compiler invariant;
- normalized handoff reaches at least 90% of all `refactor-core` requests;
- final browser-playable output is reported over all original requests and
  exceeds the legacy path by the predeclared margin beyond the noise floor;
- browser playability among compiled drafts remains at least 95% as a
  diagnostic compiler/runtime check;
- exact state transaction reaches at least 90% of all applicable original
  requests, including rejected and failed generations;
- narrative/choice quality does not regress by more than the predeclared margin;
- same-seed control/treatment comparison shows a credible improvement beyond the measured noise floor; and
- fill-stage p95 latency remains within 25% of the current production path,
  while staged mechanic-proposal latency is reported separately.

These are initial engineering gates, not permanent benchmark weights. Revise them from the Phase 0 baseline before implementation promotion.

## Testing Priorities

### Deterministic CI

- Pydantic/schema fixtures for every plan, fill, proposal, and assembled-draft
  variant.
- Plan-authority tests proving a fill cannot add slots, state targets,
  references, effects, or mechanic components that the plan did not allow.
- Typed inline-span rendering for text, state references, entity references,
  escaping, and hostile values.
- Legacy `ModelOutput` plus `PassagePlan` to `PassageDraft` adapter parity.
- Typed condition/effect rendering and escaping.
- Compiler fixtures for normal, conditional, switch, loop, form, dialogue, random, hub, and ending passages.
- State read/write exactness.
- Draft revision and stale-parent rejection.
- Atomic commit rollback on validation or filesystem failure.
- Async/sync Ollama provenance parity.
- Parser/compiler semantic round trips where a reverse adapter exists.

### Model Canary

- ordinary prose and choices against a fixed plan;
- one state update;
- one guarded choice;
- one form;
- one loop or switch;
- one conversation;
- one continuity case;
- one context distractor case; and
- one compile-and-browser choice execution.

### Stress/Research

- XL context and long histories;
- prompt injection in retrieved story data;
- hostile strings and Unicode;
- thinking-budget experiments;
- 16-turn conversations;
- repeated repair attempts; and
- 25-100 passage continuity walks.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Typed output flattens prose | Keep narrative text fields open; constrain structure and mechanics, not vocabulary; retain blinded quality review |
| Some Ollama models handle JSON schema poorly | Preserve a legacy adapter and capability-based routing; test grammar and tolerant-parser alternatives separately |
| Staged generation is too slow | Use one fill call by default; request a mechanic stage only when the plan leaves an approved bounded decision open |
| Compiler bugs affect every model | Make compiler pure, fixture-heavy, and browser-tested; treat compiler failures as release blockers |
| The state DSL is too narrow | Version the schema and add operations only with compiler/tests; provide an explicit reviewed expert escape hatch |
| Migration changes emitted Twee | Require byte parity in Phase 1, then make intentional diffs explicit |
| Benchmark improves while stories worsen | Keep narrative/choice quality and multi-passage continuity as independent gates |
| Capability cards become stale | Key them by exact digest/template/runtime configuration and invalidate on any fingerprint change |

## Decision

Proceed with the refactor, beginning with a fresh frozen `refactor-core`
baseline and compiler extraction.

Do **not** spend another optimization cycle adding global or variant-specific format reminders before testing the typed path. The published experiments already show that prompt-only changes trade failures between variants, while the current codebase is capable of owning the syntax deterministically.

The smallest high-value implementation slice is:

1. define `PassagePlan`, `NarrativeFill`, bounded `MechanicProposal`, and the
   assembled `PassageDraft`;
2. implement deterministic plan construction for ordinary, state, guarded
   choice, and form cases;
3. adapt `ModelOutput` into fills/proposals without granting new plan authority;
4. extract deterministic rendering into `SugarCubeCompiler`;
5. add `typed_fill` JSON-schema generation in shadow mode; and
6. compare it with legacy generation on paired `refactor-core` plans plus
   compile/browser checks.

If this slice improves final playable and semantically correct passages, continue to immutable draft commit and staged mechanics. If it does not, the layered benchmark will identify whether the remaining defect is context, schema adoption, semantic planning, compiler behavior, or runtime execution.

## Repository References

- Current generation domain model: `harness/models.py` (`ParsedChoice`, `ModelOutput`)
- Prompt/context assembly: `harness/generators.py` (`build_prompt`, `generate_story_output`)
- Legacy and JSON normalization: `harness/parsers.py`
- Deterministic rendering and graph commit: `harness/passage.py` (`_render_passage_tw`, `create_passage`)
- Generate/commit API boundary: `harness/server/app.py` (`/api/generate`, `/api/commit`)
- Ollama profiles and payloads: `harness/ollama_client.py`
- Current benchmark contract: `model_benchmark/docs/refactor-contract.md`
- Named architecture-comparison profile: `model_benchmark/README.md` (`core`)
- Experiment synthesis: `benchmark_optimization/lessons-learned.md`
- Latest treatment and rollback: `benchmark_optimization/iteration-16.md`
