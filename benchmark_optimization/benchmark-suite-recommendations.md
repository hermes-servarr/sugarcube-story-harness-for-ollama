# Benchmark Suite Recommendations

## Recommendation in one sentence

Keep the existing cases as historical evidence, but stop treating all of them
as one equally weighted benchmark. Build a smaller passage-generation core,
move transport/retrieval/style stress tests into separate diagnostic suites,
and add execution-level benchmarks that test whether the generated story
actually works.

## What the current suite contains

The protected later campaign runs, per model:

- 32 generation-matrix cases: 4 variants × directions A–H;
- 30 passage-mode capability cases;
- 8 plain-text capability cases;
- 70 total calls per model, or 280 calls for the four-model campaign.

The suite is broad, but its headline pass rate mixes different questions:

- Can the model retrieve a short fact?
- Can it obey an artificial dialogue layout?
- Can it repeat required style-guide phrases?
- Can it serialize the harness envelope?
- Can it write correct SugarCube?
- Can it create a playable and narratively useful passage?

Those are all worth measuring, but combining them into one pass rate makes the
number hard to interpret.

In iteration 10, plain-text cases contributed 27 passes out of 32. The full
headline was 85/280 (30.36%); passage-generating cases alone were 58/248
(23.39%). The plain-text diagnostic therefore raised the headline by almost
seven percentage points without improving passage generation.

## Benchmarks to add

### Priority 0 — necessary for trustworthy benchmark results

| Benchmark | Minimal design | Benefit |
|---|---|---|
| Seeded replay stability | Run the same case twice with the same seed and 5–10 different seeds | Establishes the noise floor and prevents promotion of random ±1-pass changes |
| Prompt/provisioning fingerprint | Assert and report prompt hash, model digest, quantization, chat-template hash, context size, sampler settings, and finish reason | Makes results reproducible and separates model capability from provisioning defects |
| Evaluator calibration set | Hand-author positive, near-miss, malformed, and semantically wrong outputs for every check | Detects false positives, false negatives, vacuous passes, and parser/scorer disagreement before spending GPU time |
| Paired baseline/treatment | Run both configurations on identical model/case/seed triples in randomized AB/BA order | Produces causal evidence and removes stale-baseline and run-order bias |

These do not primarily rank models. They benchmark the benchmark itself, which
is the most urgent gap exposed by the previous experiments.

### Priority 1 — benchmarks closest to real harness value

| Benchmark | What it should verify | Benefit |
|---|---|---|
| SugarCube compile test | Generated Twee compiles with the exact supported TweeGo/SugarCube version | Replaces regex confidence with proof that syntax is accepted |
| Browser runtime smoke | Load the compiled passage and require no console/page errors | Finds failures that parsing and compilation miss |
| Choice execution | Click every generated choice and verify the expected destination and setter effects | Tests the central interactive-fiction behavior rather than the appearance of a link or macro |
| State transaction | Given an initial snapshot, assert exact allowed reads/writes and forbid unintended mutations | Detects silent story-state corruption and hallucinated variables |
| Branch coverage | Execute both sides of `if`, every `switch` case, and representative loop cardinalities 0/1/many | Proves generated mechanics work under boundary conditions |
| Save/reload continuity | Generate, play, save, reload, and compare state plus visible passage | Protects a core SugarCube feature and catches non-serializable state |
| Multi-passage continuity | Generate 3–5 linked passages and check facts, inventory, relationships, open threads, and reachable exits across the path | Measures the harness as a story system rather than as isolated text completion |
| Reachability and dead ends | Build the passage graph and execute paths to ensure every offered choice resolves and intended endings remain reachable | Prevents attractive but unplayable stories |
| Parser/compiler round trip | Model output → parsed AST → SugarCube → parsed representation, with semantic equivalence checks | Validates the proposed structured-generation architecture and detects lossy transformations |

These should become release-gating benchmarks. A passage that has perfect
headers but fails in the browser is not a harness success.

### Priority 2 — quality, resilience, and system behavior

| Benchmark | Minimal design | Benefit |
|---|---|---|
| Requirement-negation pairs | Pair “set `$flag`” with “do not change `$flag`,” and required with forbidden macros | Detects keyword copying and proves the evaluator recognizes intent, not mere token presence |
| Counterfactual state | Change one input fact while keeping everything else fixed; require only the causally dependent output to change | Tests genuine state grounding and exposes memorized fixture responses |
| Metamorphic robustness | Rename variables/entities, rephrase directions, reorder irrelevant context, and change genre | Reveals brittle dependence on wording without needing subjective gold prose |
| Prompt-injection resistance | Put fake instructions and section markers in lore, prior prose, character sheets, and retrieved context | Tests whether untrusted story data can seize the output contract or corrupt state |
| Truncation and finish-reason ladder | Sweep output budgets while recording tokens and finish reasons | Identifies the real minimum budget and distinguishes instruction failure from truncation |
| Recovery benchmark | Inject one known syntax, structure, state, or compile error and allow one bounded repair | Measures whether compiler feedback and repair are cheaper and safer than regeneration |
| Latency/resource reliability | Record warm/cold latency, timeouts, memory, tokens, and throughput at fixed success targets | Supports practical model selection and catches improvements that merely spend more compute |
| Long-story accumulation | Run 25–100 passage transitions with compaction/snapshots enabled | Exposes context drift, summary corruption, state bloat, and late-story degradation |
| Choice quality | Check that choices are distinct, feasible, consequential, and not cosmetic; calibrate against blinded human ratings | Prevents mechanically valid but meaningless interactivity |
| Narrative quality | Blindly rate coherence, specificity, character voice, pacing, and continuity on a stratified sample | Ensures format optimization does not make the actual story worse |
| Safety/content-boundary preservation | Give explicit content constraints and adversarial context that conflicts with them | Verifies that story generation respects the operator’s boundaries across long contexts |
| Template/media integration | Generate passages using each supported UI template and media-slot contract, then validate DOM/assets in-browser | Covers real harness features absent from the model-only suite |

### Missing controlled ladders

The suite has many difficult compound cases but too few clean isolation ladders.
Add paired cases where exactly one axis changes:

- context S/M/L/XL with identical task and distractor density;
- task complexity K1/K2/K3/K4 with identical context;
- distractor D0/D1/D2 with identical context length;
- output budget tiny/short/medium/large with identical prompt;
- direct/AST/skeleton/staged serialization with identical story intent;
- bare/canonical/native chat template with identical weights;
- one, two, and four choices with the same state model;
- state size and passage-history length with identical requested mechanic.

The benefit is attribution. Current compound tier changes often alter context,
complexity, distractors, and variant simultaneously, so a failure cannot be
localized.

## Benchmarks to remove, demote, or redesign

“Remove” here normally means remove from the repeated GPU-heavy core or from the
headline metric. Preserve the historical definitions and run specialized
diagnostics when their question is relevant.

### Remove from the headline score now

| Current benchmark/check | Action | Reason and benefit |
|---|---|---|
| Eight plain-text cases (`T0-PLAIN-EXACT`, the T6 plain-text ladder, and `T9-PLAIN-FALLBACK-XL`) | Report as a separate retrieval/transport suite | They contributed 27/32 passes in iteration 10 and materially inflated a headline intended to describe SugarCube generation |
| `thinking_quality` on non-thinking variants | Mark not-applicable; exclude from denominator | It currently auto-passes when there is no thinking content, adding no information |
| Generic `variable_scoping` when no state operation is required | Mark not-applicable | Absence of invalid `<<set>>` is not evidence that the model can perform a correct state update |
| Generic `macro_usage` when no macro is required | Mark not-applicable | A response with no macros can pass; capability cases should test required macro presence and behavior |
| Generic `naked_interpolation` when no interpolation is required | Mark not-applicable | Its Boolean pass can be true with no valid interpolation, so it is a hygiene check rather than capability evidence |
| Generic `link_setter_syntax` when no link/setter is emitted or required | Mark not-applicable | “No invalid links because there are no links” is a vacuous pass |

Do not delete these scorers. Make them conditional checks and show coverage—the
number of applicable cases—beside pass rate.

### Demote from every optimization run

| Current case family | Action | Reason and benefit |
|---|---|---|
| `T0-PLAIN-EXACT` (`READY`) | Run once per model/provisioning change as a transport smoke test | It verifies the endpoint, not SugarCube ability; removing repetition saves calls without losing signal |
| S/M/L/XL exact-needle retrieval ladder | Keep S and XL in the core; run M/L only in context-focused campaigns or when endpoints diverge | The previous M→L probe showed identical behavior; adaptive testing preserves localization at lower cost |
| Conversation candidate probes already marked `observed` | Archive after one seeded confirmation; do not append them forever | Their K1/M/L questions have been answered provisionally; perpetual reruns spend GPU time without changing the core result |
| Exact 16-turn endpoint conversation | Move to stress/nightly suite | It combines long dialogue, exact endpoints, alternation, XL context, and distractors; useful stress coverage but poor everyday diagnostic isolation |
| XL/K4/D1 compound cases | Run as a stress tier after lower tiers pass | Always-failing compound tests cannot show which subsystem improved and consume the most resources |

### Redesign rather than merely remove

| Current case family | Problem | Replacement |
|---|---|---|
| Artificial `DIALOGUE:` / `INNER MONOLOGUE:` convention tests | Mostly measure adoption of a private serialization convention | Generate typed dialogue turns and thoughts in an AST, then let the renderer own labels; retain one compatibility test for direct text mode |
| Style tests based on required phrase counts | Easy to game by repeating phrases; weak proxy for voice quality | Use forbidden-token checks only as guardrails, plus contrastive/blinded style classification and narrative-quality sampling |
| Fixed A–H matrix on one story fixture | Repeats related mechanics across every variant but has poor content diversity | Use a covering array across variant × mechanic × context, then rotate several genres/state shapes |
| Raw section-header presence | Dominates results even when content is usable | Separate raw contract compliance from post-parse usability; if the harness supplies the skeleton/AST, move header correctness to deterministic unit tests |
| Keyword-only macro observables | A macro token can be present but semantically wrong or unreachable | Compile and execute the branch/state effect against assertions |
| One global all-or-nothing pass | Hides near-misses and lets easy diagnostics mask hard failures | Publish a capability vector plus three top-level gates: syntactically usable, semantically correct, and browser playable |

### Do not count these as model benchmarks

The YAML fixtures under `model_benchmark/tests/cases/` are valuable evaluator
and configuration tests. Empty-response handling, mixed-markup detection, and
known macro examples should stay in fast deterministic CI. They should not be
expanded into model calls unless the question is specifically whether a model
can repair or avoid that defect. This keeps model benchmarking focused and CI
coverage cheap.

## Proposed lean portfolio

### Suite A — CI, no model calls

- parser/evaluator calibration corpus;
- valid and invalid SugarCube/Twee compile fixtures;
- AST/render/parse round trips;
- browser fixtures for choices, state, save/reload, media, and templates;
- provenance and comparison-integrity tests.

Run on every commit. This catches harness regressions without sampling noise.

### Suite B — model canary

About 12 calls per model/seed:

- compact and structured/AST serialization;
- one state update, conditional, loop, form, and switch;
- one retrieval/counterfactual pair;
- one conversation and one style case;
- one adversarial-context case;
- one multi-passage transition;
- one compile-and-browser execution case.

Run before a full campaign. Stop early if transport, provenance, or basic
compilation fails.

### Suite C — core comparison

Use a covering array rather than every Cartesian combination. Include multiple
story fixtures and ensure every variant, mechanic, context band, and model
template class receives coverage. Run control/treatment pairs on at least five
seeds. Headline results should be:

1. raw contract compliance;
2. parsed/compiled usability;
3. semantic state correctness;
4. browser playability;
5. narrative/choice quality on a calibrated sample;
6. latency and token cost.

### Suite D — stress and research

- XL context and 25–100 passage histories;
- 16-turn conversations;
- dense distractors and prompt injection;
- output-budget and context-window ladders;
- thinking-budget experiments;
- candidate probes and experimental architectures.

Run nightly or for the relevant experiment. Never let this suite silently
change the core headline denominator.

## Highest-value changes

If only five suite changes are made, choose these:

1. Separate the eight plain-text cases from the passage-generation headline.
2. Add applicability so vacuous checks become `N/A`, not passes.
3. Add compile, browser, choice-effect, and state-transaction benchmarks.
4. Replace the full Cartesian matrix with a multi-fixture covering array.
5. Require paired seeded repetitions and complete provisioning fingerprints.

These changes make the benchmark smaller, harder to game, more statistically
credible, and much closer to the real question: **does the harness reliably
produce a playable SugarCube story with correct state and worthwhile choices?**
