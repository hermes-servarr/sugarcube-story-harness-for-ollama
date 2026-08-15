# Refactor/Rebuild Requirement Audit

Updated: 2026-08-14

This matrix audits `refactor-rebuild-plan.md` against production code, tests,
and immutable benchmark evidence. A phase is not marked complete merely because
its implementation exists; its exit gate must also have evidence.

| Plan area | Status | Authoritative evidence or remaining work |
|---|---|---|
| Phase 0 — measurement and reproducibility | Complete for the selected qwen35 9B Q4_K_M artifact | Frozen corpus/configuration hashes, exact artifact/runtime provenance, matched seeds, three byte-identical replay runs, a frozen 5-point margin, and five-/ten-seed manifests exist. Historical canaries without full provenance remain explicitly non-promotional. |
| Phase 1 — contracts and compiler parity | Complete | Production Pydantic contracts, immutable fingerprints, authority rejection tests, all legacy renderer modes, hostile text, exact plan-owned state transactions, deterministic compilation, and documented intentional typed-path additions are covered. Compiler v2 makes conditional fallback and random-event odds explicit plan authority. |
| Phase 2 — typed shadow generation | Mechanically complete; narrative gate open | `legacy_json`, `typed_fill`, and `flat_fill` share plans, normalization, assembly, compiler, and detailed response envelopes. Defaults remain legacy. Independent narrative judgments have not been collected, so the Phase 2 narrative exit condition is not yet met. |
| Phase 3 — browser and multi-passage gates | Complete for the frozen promotion corpus | Tweego/Chromium gates cover the promised passage behaviors. The ten-seed child reports typed `221/221` and flat `240/240` compiled-playable drafts and retains original-request denominators. |
| Phase 4 — immutable draft boundary | Complete | Immutable draft revisions, exact-artifact validation/commit, parent and plan conflicts, journaled recovery, restart persistence, rejection, fact decisions, and raw-output tamper resistance are tested. Typed mode remains opt-in. |
| Phase 5 — staged mechanics and repair | Deliberately deferred | The bounded `MechanicProposal` authority contract exists, but no `typed_staged` production/benchmark strategy has been justified. The one-call flat candidate already clears mechanical and latency gates. This phase must remain separate if future complex-mechanic evidence shows a material gain. |
| Phase 6 — capability routing and promotion | Mechanically complete; narrative/default promotion gated | Exact-evidence capability cards, expiry/invalidation, conservative selection, five-seed screening, and ten-seed confirmation exist. Compiler v2 correctly source-invalidates the frozen v1 card, and a new matched 727-record parent, zero-call browser child, confirmation, and source-valid mechanical-v2 card are registered. Narrative review is unassessed and no config-version default migration is authorized. |
| Phase 7 — legacy retirement | Not started; correctly blocked | The fallback policy is frozen, but no promotion release or following stable-release/30-day observation window exists. Legacy deletion is prohibited at this stage. |
| Phase 8 — Hybrid and Sandbox simulation | Substantially complete; acceptance expansion continues | Typed topology, clock/resources, systems, encounters, character/faction persistence, fixtures, traces, long-run replay/liveness, and UI authoring exist. Explicitly tagged planned scenes now project to ordered Hybrid `authored_anchor` opportunities; completion is an immutable runtime transition and leaves `story.json` unchanged. Human sandbox narrative variation/agency review is still absent. |
| UI Phases A–E | Substantially complete | The reversible React/Vite application, generated contracts, accessible outline, authoring workspaces, exact Write lifecycle, recovery, facts, planning, settings, topology/systems/encounters, World, Media, Tests, and initialization are implemented. Write now has structured controls for the entire current `PassagePlan` surface: narrative kinds/speakers, choice destinations/weights/restarts/guards/effects, reference allowlists, fixed and allowlisted effects, optional proposal authority, all form variants/options, loop bindings, room exits, conditional fallback, random-event odds, and lifecycle timing. Required mechanic proposals remain unavailable with the deliberately deferred `typed_staged` strategy. |
| UI Phase F — cutover | Blocked and incomplete | The new UI is not the default. Independent manual accessibility review, matched old/new compatibility acceptance, the promotion decision, and the fallback observation window remain. |

## Known local implementation gaps

These are code or automated-evidence gaps, not reasons to weaken promotion
rules:

1. The Preview tab renders safe prose/choice text plus compiled-source details,
   provides desktop/tablet/mobile width controls, and can launch an isolated
   playtest for one visible trusted choice. It is not yet an embedded live
   SugarCube passage; execution remains a persisted background browser job.
2. Exact-revision resource-style draft `compile` and `playtest` endpoints now
   exist, and playtests expose persisted queued/running/completed/failed job
   state. Queueing recomputes and verifies the persisted artifact against the
   exact draft before any browser work. The ad hoc isolated scenario currently proves Tweego compilation,
   browser load, and reachable fixture-eligible choices. It deliberately does
   not claim effect transactions, form binding, return continuity, or hostile
   text coverage unless a richer scenario supplies those assertions.
3. Model generation remains synchronous and does not yet expose a job ID or
   status stream as proposed in section 6.11. Isolated browser playtests no
   longer share this gap.
4. Served Playwright coverage exercises the two end-to-end lifecycle stories
   across many workspaces, but additional mode-specific Write workflows and
   visual-regression baselines remain useful before UI cutover.
5. Some legacy-only endpoints retain handwritten response shapes. Generated
   OpenAPI drift enforcement covers the typed contracts consumed by the new
   UI, including generation requests and commit/fact-decision responses;
   migration should continue as remaining legacy consumers move.

## External and time-gated blockers

1. Independent reviewers must complete the blinded narrative/choice bundles.
2. After a compiler-v2 mechanical card exists, it needs a reviewed revision
   only if blinded results satisfy the frozen per-dimension and preference
   tolerances. Assessed strategy claims now require a hashed decoded report;
   the selector independently recomputes those aggregate gates.
3. An independent manual accessibility audit is required; passing axe scans do
   not establish WCAG conformance.
4. After an eventual promotion, legacy must remain available through the
   promotion release and following stable release for at least 30 days before
   retirement can be considered.

Until both the local cutover requirements and external gates clear, production
defaults remain `legacy_delimited` and the legacy authoring UI.
