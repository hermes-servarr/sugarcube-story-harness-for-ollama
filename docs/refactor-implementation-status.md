# Refactor/Rebuild Implementation Status

Updated: 2026-08-14

The refactor goal remains active. Legacy generation and the legacy UI remain
the defaults until matched live-model promotion evidence clears the gates in
`refactor-rebuild-plan.md`.

## Completed production slices

- Versioned, immutable planning/fill/draft/compiler/diagnostic contracts.
- Pure deterministic compiler plus legacy renderer compatibility boundary.
- `typed_fill`, `flat_fill`, and comparable `legacy_json` benchmark paths.
- Typed shadow generation with one detailed Ollama response envelope.
- Immutable `DraftStore` revisions and exact-artifact validate/commit APIs.
- Journaled multi-file commit with rollback/failure-injection coverage.
- Layered benchmark categories through draft assembly, component resolution,
  state transactions, compilation, Tweego, Playwright, and continuity.
- Browser fixtures for guards/effects, hostile text, hub revisits, rooms,
  weighted random routes, ending restart, forms, loops, and benchmark wiring.
- Reversible React/TypeScript/Vite UI at `/next`; legacy remains at `/legacy`.
- Story and Tests inspection workspaces plus fingerprint-guarded World, Media,
  planning, topology, Settings, and initialization authoring workflows.
- Typed Write generate/edit/revision/validate/exact-commit workflow.
- Read-only persisted benchmark run/detail/comparison APIs.
- Complete typed `ExperienceProfile` semantics with named Story-driven,
  Hybrid, and Sandbox defaults plus explicit scoped overrides.
- Immutable project profile revisions with graph-bound, stale-safe migration
  previews that never rewrite topology or passage files.
- React Settings profile editor with preset/custom controls, preview-before-save,
  structured impacts, and typed conflict handling.
- Effective profile fingerprints stamped at the typed planning boundary and
  rejected when a submitted plan targets a stale profile.
- Typed systemic topology/runtime contracts for locations, routes, local
  actions, eligibility, costs, clocks, opportunities, visits, and traces.
- Pure deterministic local-action/travel transitions with resource authority,
  optimistic revision checks, topology binding, cycles, and revisit history.
- Immutable authored topology and runtime-session stores plus profile-gated
  topology/simulation APIs; disposable simulations never touch `story.json`.
- Sandbox/Hybrid Story workspace variant for location/route authoring and
  interactive deterministic simulation traces.
- Explicitly tagged planned scenes now project into ordered Hybrid authored-
  anchor opportunities. Completing an anchor is an immutable runtime-only
  transition, preserves free exploration, and never rewrites `story.json`.
- Typed system-rule and reusable-encounter contracts with deterministic
  priority, eligibility, cooldown, occurrence-limit, and seeded-weighted
  selection behavior; authored system rules run inside API action transitions.
- Schema-defined persistent-character contracts and pure bounded mutations for
  stats, inventory, facts, location, conditions, agendas, activities, needs,
  decay, deadlines, cooldowns, and visibility-safe narrative context.
- Frozen long-run cyclic simulation fixtures proving deterministic replay,
  revisit liveness, authored-topology immutability, and resource underflow
  prevention.
- Browser initialization that bootstraps a completely bare project directory,
  then persists explicit author intent without generating or committing prose.
- Character and lore creation/editing plus media metadata/resolution guarded by
  content fingerprints, with dirty-navigation and reload protection.
- Story planning beat/arc creation guarded by a canonical story fingerprint.
- Story planning beat/arc edits, beat deletion, and planned-scene create/edit/
  deletion guarded by the same serialized story fingerprint, with React stale-
  edit reload handling.
- Media import plus slot-scoped image/audio/video preview in the React Media
  workspace; arbitrary preview paths are not accepted.
- Runtime model management for Ollama endpoint/model selection, inference
  controls, health discovery, and separately cached per-model smoke tests.
- Frozen `sandbox-canary` and `sandbox-core` profiles that combine the matched
  bounded-fill architectures with content-hashed deterministic runtime cases
  for eligibility precision, action authority, state deltas, replay,
  resources, and cyclic liveness.
- Frozen faction, reusable-encounter, and persistent-character domain cases;
  pure faction transitions clamp influence/disposition/relationships and reject
  resource underflow.
- Serialized compare-and-swap for UI planning creates, including a two-writer
  race test and stable validation/conflict error codes.
- Typed Write dirty guards, latest-revision conflict recovery, fingerprint-bound
  validation, unsaved-edit validation/commit blocking, parent-conflict commit
  lockout, and explicit exact-revision rejection.
- Runtime sessions persist typed character stat definitions, character state,
  and faction state separately from authored canon. Elapsed actions/travel/ticks
  advance character decay, needs, conditions, deadlines, and cooldowns; system
  rules can apply bounded character and faction effects.
- Fingerprint-guarded, atomic system-rule and reusable-encounter catalog
  revisions, with structured React creation forms.
- Immutable topology update/delete revisions for locations and routes, with a
  serialized two-writer compare-and-swap store, React conflict reload, and an
  empty-topology guard on ad-hoc simulation startup.
- Bounded typed continuity proposals with plan-owned evidence-slot validation;
  post-commit accept/reject decisions are bound to the exact immutable proposal,
  recorded independently, reload-recoverable in React, and cannot overwrite a
  conflicting authored continuity fact.
- Immutable, fingerprinted PassagePlan revisions with explicit author approval;
  typed generation consumes an exact approved revision and rejects stale,
  unapproved, or superseded references. The React Write workflow now covers
  save, structured review, approval, revision, generation, validation, and
  exact commit.
- Fingerprint-guarded named simulation fixtures with persisted start location,
  seed, world/resources, character stats/state, and faction state. React
  supports structured fixture create/edit/delete/run workflows.
- React diagnostics navigate to and focus the exact invalid prose/choice slot;
  served-browser coverage includes reload recovery, parent conflicts, draft
  rejection, independent fact decisions, ARIA tab/arrow-key navigation, narrow
  layout, and 200% zoom.
- The Write inspector exposes the Plan/Narrative/Mechanics/Compile/Playtest
  stage pipeline, structured plan-owned mechanic details, all contract passage
  modes, an advanced exact compiled-Twee/source-map view, and structured state
  fixture values for allowed references. Preview width can be switched among
  desktop, tablet, and mobile, and each visible trusted choice can launch a
  slot-scoped isolated playtest. Compile-artifact drift is retained as a failed
  review stage and blocks playtest/commit. Exact immutable draft compilation is
  available as a read-only fingerprint-guarded resource operation; commit also
  reproduces the artifact before writing. Isolated playtests
  re-prove the persisted artifact from the exact draft before queueing, persist
  a job ID and queued/running/completed/failed status, recover abandoned active
  jobs as explicit stale failures, and report only the runtime layers actually
  assessed.
- The plan editor exposes structured, non-JSON controls for every current
  `PassagePlan` field: narrative slot kind/speaker, choices and ordering,
  random weights, ending restarts, guards, effects, allowlists, proposal-slot
  authority, every form input/option variant, loop bindings, room exits,
  eligibility, conditional fallback, random-event odds, and lifecycle timing.
  Required proposal slots remain disabled while `typed_staged` is deliberately
  deferred.
- The deterministic compiler renders choice labels through safe SugarCube
  link string literals, prevents model-authored `$`/`_` text from becoming
  runtime variable interpolation, and uses plan-owned dialogue-exit markers
  instead of guessing destinations from model wording.
- The React client consumes generated OpenAPI types for typed-generation
  requests and exact commit/fact-decision responses; validation no longer
  sends an undocumented empty request body.
- Deterministic narrative-review packaging creates score-free, architecture-
  blinded A/B bundles, a separate private decoding key, and a blank seven-
  dimension rubric. Strict decoding reports per-dimension paired means and
  preferences without collapsing them into an opaque combined score. The
  frozen five-seed child now has balanced 30-pair typed-
  versus-legacy and flat-versus-legacy bundles over the same exact sample
  identities, each stratified across all 22 cases with three-way-matched
  reviewable outputs.
- Promotion protocol v1 freezes the same-seed replay method, strict margin
  formula, ten-seed cohort, and narrative tolerance before new evidence is
  observed. A replay analyzer rejects mismatched seeds, runtimes, evaluators,
  corpora, models, or request identities and reports original-request
  playability noise separately from compiled-draft diagnostics.

## Current verification

- Python non-E2E suite: `1611 passed, 27 deselected` (the Node-dependent file
  was run separately and combined with the remaining suite). The run used native
  `/tmp` for pytest capture and a temporary WSL path-conversion wrapper around
  the installed Windows Node executable; this avoids DrvFS capture failures
  and gives `node --check` Windows-readable temporary paths without changing
  repository behavior.
- Production Tweego/Chromium passage browser fixtures: `8 passed`.
- Served React lifecycle/browser workflows: `2 passed`, covering bare-project
  authoring/simulation and the full approved-plan/draft/conflict/recovery/fact
  lifecycle with no unexpected page or console errors. Both workflows now run
  pinned axe-core 4.10.3 WCAG 2 A/AA, 2.1 AA, and 2.2 AA scans across
  initialization, settings/capability evidence, sandbox simulation,
  world/media, narrow 200%-zoom tests, plan review, draft diagnostics, and fact
  review. The combined served run is `2 passed`; the Write workflow now also
  asserts structured plan controls across form/room/loop/random/random-event/
  conditional/ending modes, guard/effect persistence, compiled-source
  provenance, exact compilation, asynchronous isolated playtest completion,
  and the review stage list.
  Earlier axe coverage found and fixed transient toast contrast during the
  former opacity animation.
- Focused simulation engine/API regression: `19 passed`, including ordered
  Hybrid anchor progression, authored-canon immutability, and compatibility
  loading for pre-anchor runtime-session fingerprints.
- React unit tests: `6 passed`; TypeScript type-check and Vite production
  build: successful.
- Blinded narrative-review packaging/decoding, replay-variance, and promotion-
  confirmation tests: `11 passed`; the current focused refactor/browser/
  review/promotion slice is `47 passed`.
- Final plan/simulation/UI focused verification: `14 passed`.
- Benchmark-to-production browser integration: `1 passed`.
- Current Sandbox benchmark/profile/CLI regression suite: `88 passed` before
  the domain extension; the final domain-focused slice is `17 passed`.
- Diagnostic one-seed live `sandbox-canary` on `orinth:latest` (seed 8341):
  typed fill `9/10`, flat fill `8/10`, legacy JSON `3/10`, deterministic
  runtime/domain `3/3`. This run is not promotion-grade because its original
  manifest predated exact digest/quantization capture.
- Formal five-seed `sandbox-canary` run `20260814_000552_c4ce7c70`:
  typed fill `43/50` (86%), flat fill `41/50` (82%), legacy JSON `17/50`
  (34%), and deterministic Sandbox runtime/domain `3/3`. Typed versus legacy
  had 26 paired wins and zero losses. This was a canary without the matched
  browser gate and is not promotion evidence by itself.
- Formal five-seed `sandbox-core` run `20260814_010329_a82d8571` contains all
  367 expected records with exact model digest/quantization/runtime provenance.
  Before browser scoring: typed fill `64/120`, flat fill `70/120`, legacy JSON
  `33/120`; compile/assembly/state was `109/120`, `120/120`, and `78/120`
  respectively. Typed p95 latency was 18.3% above legacy; flat was 17.6% below.
- Provenance-complete intermediate child `20260814_021507_509a2df8` established
  that safe choice-label compilation raised typed browser load/playability to
  `105/109` and flat to `112/120`; its remaining failures exposed evaluator
  redirect assumptions, model-text variable interpolation, and dialogue-exit
  destination guessing.
- Final zero-model-call child `20260814_024100_fdae858a`, linked to the same
  parent/results hash and recording all evaluator/tool/source hashes, rescored
  all 367 records after those deterministic fixes. Request passes are typed
  `64/120`, flat `70/120`, and legacy `32/120`. Typed is `109/109` and flat is
  `120/120` for both browser load and fully playable compiled drafts; legacy is
  `76/78`. Typed-versus-legacy is 34 wins/2 losses/84 ties (exact two-sided
  p=`1.94e-8`); flat-versus-legacy is 42/4/74 (p=`5.10e-9`). Typed normalized
  plan handoff and exact state/compile each reach `109/120`; flat reaches
  `119/120` plan handoff and `120/120` state/compile. This child made zero model
  calls and preserves the parent model digest, Q4_K_M quantization, five seeds,
  Ollama version, and original-request denominators.
- Promotion manifests now query and persist exact Ollama digest, quantization,
  family, parameter size, context length, and runtime version; failures are
  explicitly recorded as `unknown` rather than silently omitted.
- The final child leaves two browser-load failures in the legacy control only;
  typed and flat have no compiler-originated runtime failures in the frozen
  five-seed corpus.
- Same-seed replay browser children `20260814_030727_f0844428`,
  `20260814_031914_d8f9f7b9`, and `20260814_033054_8c56fee4` are exactly stable:
  flat request/pass-playable is `15/24` and `24/24`, typed is `13/24` and
  `22/24`, and legacy is `7/24` and `17/24` in every run. All 72 raw responses
  are byte-identical across executions. The measured playability noise floor
  is 0 percentage points, freezing the protocol-defined promotion margin at
  5 percentage points before confirmation.
- Compiler-v2 ten-seed parent `20260814_090812_93244233` contains all 727 expected
  records: 240 matched requests per architecture over seeds 42--51 plus seven
  deterministic Sandbox records. Its zero-call browser child
  `20260814_092621_759ed6cf` preserves every request identity and generation
  field and records the parent, evaluator, Tweego, and story-format hashes.
  Request pass/playable is legacy `61/240` and `145/240`, typed `133/240` and
  `221/240`, and flat `142/240` and `240/240`. Typed-versus-legacy playability
  is 83 wins/7 losses/150 ties (p=`1.32e-17`); flat-versus-legacy is 95/0/145
  (p=`5.05e-29`). Typed and flat compiled playability are both 100%; legacy is
  `145/149`. Typed handoff/state is `221/240`; flat is `239/240` handoff and
  `240/240` state. Typed p95 is 17.7% above legacy and flat is 15.5% below.
  Both candidates clear the frozen automated mechanical/latency gates for
  this exact model artifact, with flat the stronger mechanical candidate.
- `model_benchmark/promotion_confirmation.py` now strictly verifies the
  parent/child hash, zero-call provenance, unchanged generation fields,
  compatibility metadata, exact seed/repetition coverage, and matched request
  identities before reporting independent layers, paired exact tests,
  per-seed counts, regressions, latency, and promotion gates. Its focused
  tests are `3 passed`; the hash-linked report is
  `benchmark_outputs/promotion_confirmation_ten_seed_v2.json`.
- Phase 1 renderer parity now exercises all 11 promised legacy passage modes
  plus widget/include and branch-specific fixtures for plain, gated, and skill
  links; plain hub gating; weighted random routing; dialogue exits; loop
  capture/index syntax; room fallbacks; raw widgets; and every supported form
  input kind. The focused compiler suite is `36 passed`. Typed compiler v2
  additionally makes conditional fallback and random-event odds explicit
  trusted plan fields. The other permitted typed-path additions remain
  explicit: `state_effect_lines` emits trusted plan transactions only when
  supplied, and `HARNESS_EXIT` marks trusted dialogue destinations (the legacy
  default path remains byte-identical). Hostile model
  copy now has direct tests for quotes, backslashes, link delimiters,
  `</script>`, HTML, Unicode, and newlines.
- Backend/UI schema drift is now detected by committed deterministic OpenAPI
  and generated TypeScript artifacts. `npm run contracts:check` verifies both
  and is mandatory inside the production UI build; frontend experience-profile
  and passage-plan types consume the generated Pydantic-derived declarations.
  Four Python guard tests and the production TypeScript/Vite build pass.
- Exact-evidence capability routing now has a frozen Pydantic card contract,
  repository-confined evidence/source hash verification, result-file bindings,
  confirmation-gate validation, expiry and identity invalidation, and a
  conservative selector that returns `legacy_delimited` unless every gate is
  satisfied. Any narrative pass/fail claim must bind a hashed decoded 30-item
  review report; a pass is recomputed against all seven frozen dimension
  tolerances and the preference tolerance. A deterministic card issuer
  reproduces confirmation analysis, rejects source files modified after their
  parent/browser run began, and refuses to relabel v1 evidence with compiler
  v2. The qwen35 9B Q4_K_M artifact now has two committed cards: historical
  compiler-v1 card `qwen35-9b-q4_k_m-mechanical-v1` remains intentionally
  source-invalid, while compiler-v2 card `qwen35-9b-q4_k_m-mechanical-v2`
  binds the new parent, zero-call child, confirmation report, and all twelve
  generation/evaluation/issuance sources. Flat and typed are mechanically
  qualified on the v2 card, but narrative review remains `not_assessed` and
  both are deliberately ineligible as defaults. The historical fingerprint is
  `4b4c04be6a7c46109068713190df9c117964718e4aa03f1c9b95af6739598c5f`;
  the v2 fingerprint is
  `77ebcd62bd94eba183c0c66c19eea65f82692f470757972344be1c27dbcf0768`.
  Twenty-two focused card/API tests pass.

The one pytest warning is a pre-existing collection warning for the helper
class `TestResult` in `scripts/test_player_flow.py`.

## Reversible controls

- Generation default: `generation_strategy: legacy_delimited`.
- Typed comparison default: `typed_shadow_generation: false`; operators may
  explicitly set it to `true` for isolated, non-committing shadow comparison.
- UI default: `authoring_ui: legacy`.
- UI operator override: `HARNESS_AUTHORING_UI=legacy|next`.
- Explicit routes: `/legacy` and `/next` remain available regardless of the
  configured default.

## Remaining promotion blockers

1. Have independent reviewers score the generated blinded narrative/choice
   bundles and decode the completed results against the private keys. The
   reproducible packaging and blank human-review samples exist; reviewer
   judgments do not, and must remain separate from compiler correctness.
2. Complete the narrative gate for the exact registered compiler-v2 card, then
   issue a reviewed card revision if it passes. The current card scopes the
   ten-seed result to the exact Q4_K_M qwen35 9B digest/runtime/profile/settings
   and deliberately routes no typed default; untested or changed artifacts
   invalidate rather than inherit that evidence.
3. Observe the stable-release fallback window before legacy retirement. The
   exact plan/draft/commit/benchmark response contracts used by the new UI are
   now generated from FastAPI and consumed by TypeScript; broader legacy-only
   endpoints can migrate as their UI consumers move. The frozen policy retains
   both legacy switches through the promotion release and following stable
   release, for at least 30 days. No window is active because no default has
   been promoted.
4. Complete the independent manual accessibility audit. Automated axe scans,
   keyboard/diagnostic focus, 200%-zoom, and narrow-layout checks now pass over
   the two served lifecycle workflows, but automated checks alone are not a
   WCAG conformance claim.
5. Capability-card default routing, typed-staged mechanics, promotion, and
   legacy cleanup remain gated follow-on phases; they should not be enabled
   merely because the corrected compiler/browser diagnostics are now green.

No production-default promotion is justified yet.

The phase-by-phase audit, including local UI/API gaps that are not promotion
blockers, is maintained in `docs/refactor-requirement-audit.md`.
