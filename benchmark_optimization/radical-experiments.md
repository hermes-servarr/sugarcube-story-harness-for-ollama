# Twenty Radical Experiments for the SugarCube Harness

## How to run this program

These are experiments, not assumed improvements. Radical ideas are valuable
only when failure is cheap and the result is interpretable.

The benchmark contract changed after iteration 12. The standard capability run
now selects the 30 signed passage cases; the 8 plain-text retrieval/transport
cases and validated candidate probes run only with `--diagnostic-tests`.
Reports use passage generation as the headline, and scorer categories whose
construct is neither required nor emitted are reported as `N/A` and excluded
from score denominators. Configured seeds are now forwarded to Ollama and
stored on result records.

Consequently, iteration 10's 85/280 (30.36%) result is historical evidence,
not a valid control for this program. First create and freeze a clean baseline
with the current code, current overlay, four-variant A–H generation matrix, and
30-case passage capability core. That is 62 calls per model/seed: 32 matrix
calls plus 30 capability calls. Run retrieval/transport, candidate, context-
window, and other stress diagnostics separately; never merge them into the
passage headline.

For every treatment:

- run the same model/case/seed triples for control and treatment;
- use at least 5 seeds for screening and 10 for confirmation;
- keep suite, roster, model digests, chat templates, context limits, sampling,
  and output budgets fixed unless one is the declared treatment;
- store the exact rendered prompt, configuration hashes, token counts, finish
  reason, parser route, repair attempts, latency, and browser/compile results;
- report paired deltas with confidence intervals by variant, capability,
  context profile, and model—not just aggregate pass rate;
- report both pass rate and applicable-check coverage; never interpret an
  increase caused only by more checks becoming `N/A` as an improvement;
- define one primary metric before running and treat all other movement as
  secondary evidence;
- promote an idea only if it reproduces in a second run and does not conceal a
  loss in semantic or playtest quality.

The default success gate below is a statistically credible improvement on the
predeclared passage-generation metric, no reduction in applicable-check
coverage, and no greater than 2 percentage-point regression in semantic
correctness or browser playability. Retrieval/transport diagnostics must not
offset a passage regression. Experiments may override that gate when a
different criterion is stated.

## 1. Measure the noise floor before optimizing anything

**Radical claim:** Some recorded “improvements” are ordinary sampling noise.

Run the frozen current-suite baseline 10 times using fixed seeds, then repeat
once with the same seeds and once with new seeds. Measure exact replay
agreement, per-case flip rate, variance of passage pass rate, applicable-check
coverage, and variance by model/variant/context profile. The treatment is no
prompt change—only repetition. Verify from result records that every planned
seed reached the backend; do not infer seeds from repetition numbers.

**Primary metric:** 95% interval for paired pass-rate variation under no change.

**Decision:** Establish a minimum detectable effect and forbid promotion of
future deltas smaller than that threshold. If same-seed replay is not nearly
identical, first investigate Ollama/model nondeterminism and hidden state.

## 2. Paired crossover instead of sequential campaigns

**Radical claim:** Interleaving control and treatment removes machine-time,
thermal, cache, and service-state bias.

For every model/case/seed, randomly run AB or BA, where A is the baseline and B
is the treatment. Clear only the state known to affect generation, and record
order. Compare each B output directly with its paired A output rather than with
the previous publication.

**Primary metric:** paired win/loss/tie rate on strict and component scores.

**Decision:** Make crossover execution the default if order effects are small;
if they are large, that is itself a harness defect to isolate.

## 3. Make every run cryptographically self-describing

**Radical claim:** A benchmark result without the exact effective configuration
is not reusable evidence.

Extend the current manifest and seeded result records into a run capsule
containing hashes and stored artifacts for the rendered prompt, base templates,
overlay, selected suite and diagnostic flags, applicability/evaluator policy,
parser, source commit, model digest, quantization, chat template, seed, and
Ollama options. Deliberately change one field at a time and verify that the
capsule and comparison tooling detect every mismatch.

**Primary metric:** 100% detection of intentionally introduced provenance
mismatches; zero false “comparable” labels.

**Decision:** Block cross-run comparisons when capsule compatibility fails.

## 4. Canonical chat-template surgery

**Radical claim:** A large fraction of the apparent model gap is provisioning,
not weights.

For model families that currently mix bare `{{ .Prompt }}` and real instruct
templates, run three arms: existing template, one canonical family-appropriate
chat template, and raw completion. Keep weights, quantization, prompt, and seed
fixed. Use the signed passage core for the primary comparison, then run the
“do not emit analysis” probe and conversation candidates as diagnostics.

**Primary metric:** change in format adoption and analysis-leak rate within the
same model artifact.

**Decision:** Canonicalize or explicitly classify templates if they explain
more variance than quantization/model identity. Never rank mixed provisioning
as though it were a clean model comparison.

## 5. Reserve tokens for the final answer

**Radical claim:** Thinking models fail because reasoning can consume the final
passage budget.

Compare: current single budget; larger budget; hard reasoning budget plus a
separate final budget; and “reason briefly, then render” with an explicit phase
boundary. Record actual token counts and finish reasons. Do not inspect or
publish hidden reasoning; evaluate only budget use and the final passage.

**Primary metric:** complete-final-passage rate for `thinking` cases. Report
`thinking_quality` coverage only for the thinking variant; non-thinking `N/A`
entries are not successes.

**Decision:** Adopt phase-separated budgets if they reduce empty/truncated
finals without increasing total latency by more than the chosen operating cap.

## 6. Delete the `full` prompt and reconstruct it from minimal context

**Radical claim:** The full prompt is worse because it contains too much, not
because models need more instruction.

Create a “minimum viable full” prompt by starting from `compact` and adding
context blocks one at a time: current state, lore, arc, style, examples, and
SugarCube reference. Also run a subtractive arm that removes each block from
the existing `full` prompt. Preserve the same task and output contract.

**Primary metric:** strict passage pass rate per input token on full-context
cases, split between the A–H matrix and signed capability core.

**Decision:** Keep only blocks with a reproducible marginal benefit. Treat a
short prompt that retains semantics as a successful replacement for `full`.

## 7. Move from text generation to an intermediate story AST

**Radical claim:** Models should express intent, while deterministic code emits
SugarCube.

Have the model return a typed story AST: prose spans, dialogue turns, inner
monologue, choices, guards, state reads/writes, macros, summary, and continuity
updates. A deterministic compiler converts the AST to SugarCube/Twee. Compare
against direct SugarCube generation on the same signed state, conditional,
switch, loop, form, conversation, retrieval, and consistency tasks. Add AST as
a declared treatment dimension; do not silently replace the direct-generation
cases.

**Primary metric:** compiled-and-playable rate with semantically correct state
transitions.

**Decision:** Promote the AST path if it sharply reduces syntax/structure
failures without flattening prose or losing requested mechanics.

## 8. Skeleton first, constrained slot filling second

**Radical claim:** Models comply better when they cannot forget the envelope.

The harness creates the exact output skeleton itself, including required
sections and immutable markers. The model fills individually delimited slots
for prose, choices, state effects, and summary. Test single-call masked filling
and separate calls per slot against the same passage-core cases. Preserve the
raw-contract score even if deterministic framing guarantees section presence,
so harness help is not misreported as model compliance.

**Primary metric:** section completeness and parser success.

**Decision:** Prefer the lowest-call design that eliminates missing-section
failures while preserving cross-slot consistency.

## 9. Split author, mechanic, and serializer into separate agents

**Radical claim:** One model call should not be novelist, game designer, and
compiler simultaneously.

Use three bounded stages: an author writes scene intent/prose; a mechanic maps
intent to choices and state transitions; a serializer emits the final AST or
SugarCube. Test same-model stages and specialized-model stages. Pass structured
artifacts, not growing conversational transcripts.

**Primary metric:** end-to-end playable-and-semantically-correct rate.

**Decision:** Accept extra latency only if failure localization and final
reliability materially improve over direct generation.

## 10. Compiler-in-the-loop self-repair

**Radical claim:** Deterministic error messages are more useful than longer
prompts.

Generate once, parse and compile it, then return only machine-readable error
codes with narrow repair instructions. Allow at most two patches. Compare no
repair, full regeneration, and minimal diff repair. Track whether repair fixes
one issue while introducing another.

**Primary metric:** recovery rate from initial failure to compiled playable
passage.

**Decision:** Keep repair only where net recovery, latency, and non-regression
rates beat one fresh retry.

## 11. Grammar-constrained decoding versus tolerant parsing

**Radical claim:** Prevention and recovery should be measured separately.

Run four arms: unconstrained direct text; JSON-schema constrained AST;
grammar-constrained sectioned output; and unconstrained output with a tolerant
parser. Score raw compliance before repair and usable output after repair.
Keep parser route and raw/final artifacts in the run capsule, and keep
plain-text diagnostics outside this comparison.

**Primary metric:** raw-valid rate and final-usable rate as two separate axes.

**Decision:** Do not call parser forgiveness a model improvement. Choose the
cheapest approach that yields reliable final artifacts and preserves semantic
quality.

## 12. Replace all-or-nothing scoring with a capability vector

**Radical claim:** The current pass cliff hides progress and misdirects prompt
optimization.

The new suite has already taken the first step: conditional hygiene categories
are `N/A` when neither required nor emitted, and reports exclude them from
denominators. Validate that policy with an evaluator oracle corpus, then score
independent dimensions: envelope validity, SugarCube syntax, requested
mechanic, state-transition correctness, continuity, prose/style quality,
choice quality, compilation, and runtime playability. Publish numerator,
denominator, and coverage for every dimension. Ask blinded human raters to
judge a stratified sample and compare which automated dimensions predict their
ratings and actual browser success.

**Primary metric:** correlation with human preference and runtime success.

**Decision:** Retire or down-weight checks with no discrimination or poor
external validity; retain strict failure only for genuinely fatal defects.
Reject any scoring revision that improves the headline only by shrinking its
applicable denominator.

## 13. Metamorphic testing instead of a larger pile of fixtures

**Radical claim:** Invariance reveals brittle harness behavior better than more
handwritten examples.

Generate controlled transformations of signed passage-core tasks: rename
variables and characters, permute irrelevant lore, swap genre, rephrase the
direction, change whitespace, reorder equivalent context blocks, and add
benign distractors. Expected mechanics and state transitions remain invariant.
Tag these as a research/stress suite so their expansion cannot change the core
headline denominator.

**Primary metric:** metamorphic consistency—the fraction of transformations
that preserve the expected semantic result.

**Decision:** Treat unexplained sensitivity as a harness bug even when the base
case passes.

## 14. Attack the prompt hierarchy on purpose

**Radical claim:** Story/lore content can accidentally or maliciously override
the harness contract.

Insert adversarial but data-shaped text into lore, character sheets, previous
prose, summaries, and style guides: fake section markers, “ignore previous
instructions,” Markdown examples, fake system messages, and enormous repeated
headers. Compare current delimiters, signed blocks, escaping, and structured
transport. Run these with explicit diagnostic/stress selection, not as an
unannounced addition to the passage core.

**Primary metric:** contract-escape rate and contamination of generated state.

**Decision:** Require zero high-severity hierarchy escapes before trusting
unreviewed user content in automated generation.

## 15. Position-sweep every critical instruction

**Radical claim:** Instruction position matters more than repetition or length.

Place the same short output contract at the beginning, before story context,
after story context, at both ends, and in a separate system message where the
backend supports it. Keep wording and token count constant. Run by variant and
chat-template class on a fixed passage-core subset; use the conversation
candidates only as secondary diagnostics.

**Primary metric:** raw contract-adoption rate by position.

**Decision:** Replace folklore about “suffixes” with an evidence-based prompt
layout per template class.

## 16. Retrieval by causal relevance, not document category

**Radical claim:** The model needs facts that can affect this passage, not all
available lore.

Compare full context, embedding retrieval, graph retrieval over entities and
state dependencies, and an oracle minimal set labeled from the fixture. Add a
counterfactual arm that intentionally omits one causally necessary fact. Use
the signed passage retrieval/consistency cases for the headline; report the
eight direct plain-text cases separately as retrieval/transport diagnostics.

**Primary metric:** required-fact recall and correct downstream state use per
input token.

**Decision:** Adopt a retriever only if it approaches the oracle and reliably
fails the counterfactual check for the right reason.

## 17. Learn a router instead of one universal prompt

**Radical claim:** Different models and tasks need different generation paths.

Route each request among direct compact, minimal-full, AST, constrained JSON,
and staged generation using only pre-generation features: model/template class,
context size, requested mechanics, and story-state complexity. Train on earlier
seeds, evaluate on held-out seeds and unseen fixtures.

**Primary metric:** held-out playable success under a fixed latency budget.

**Decision:** Require the router to beat the best single strategy, not merely
the average strategy, and publish its confusion/fallback behavior.

## 18. Generate diverse candidates, select with execution

**Radical claim:** Best-of-N is valuable only when the selector tests the game,
not when another model likes the prose.

Generate 2–4 low-cost candidates with controlled diversity. Compile each,
execute scripted state assertions, reject invalid transitions, then rank the
survivors for continuity and prose quality. Compare with spending the same
token/latency budget on one larger generation.

**Primary metric:** playable semantic success at equal compute budget.

**Decision:** Use ensembles only if execution-based selection adds value beyond
simple retries and does not homogenize narrative output.

## 19. Treat story generation as a state-machine transaction

**Radical claim:** A passage should be proposed and committed like a database
transaction.

Before prose generation, require a typed transaction: preconditions, reads,
writes, reachable choices, invariants, and expected next states. Validate it
against the current snapshot. Generate prose only for a valid transaction,
then verify that rendered links/macros implement the committed transition.

**Primary metric:** invariant-preserving state-transition accuracy over
multi-passage paths.

**Decision:** Reject any architecture that produces attractive prose but can
silently corrupt story state.

## 20. Let browser play—not text matching—be the final judge

**Radical claim:** The harness can pass textual checks and still produce a bad
or broken game.

Compile every passage candidate into a disposable story, open it in a real
browser, traverse choices, exercise inputs, save/reload, backtrack, and verify
DOM, console, state, reachability, and ending behavior. Add property-based
random walks and compare their discoveries with the existing deterministic
evaluator. Plain-text and candidate diagnostics have no browser denominator.

**Primary metric:** failure-free playable paths and invariant coverage per run.

**Decision:** Make browser execution the release gate. Textual scores remain
diagnostics, not the definition of success.

## Recommended order

Before any treatment, freeze the suite selection and create the new
passage-only baseline; do not reuse an iteration 1–12 rate across the changed
denominator and applicability rules. Run experiments 1–4 first because they
determine whether later evidence can be trusted. Experiment 12 begins with an
audit of the newly implemented `N/A` policy. Then run 5–8 to attack the known
`thinking`, `full`, and serialization bottlenecks. Experiments 10–12 establish
a closed validation loop. The remaining experiments explore robustness,
routing, retrieval, transactionality, and real playability.

A particularly high-upside sequence is **new baseline → 1 → 3 → 4 → 12 → 7 →
10 → 20**: establish the passage-only control, noise floor, and provenance;
normalize provisioning; validate applicability-aware scoring; replace raw
SugarCube generation with a typed AST; repair against deterministic compiler
feedback; and judge the result in the browser.

See `benchmark-suite-recommendations.md` for the corresponding core, diagnostic,
stress, and no-model benchmark portfolio.
