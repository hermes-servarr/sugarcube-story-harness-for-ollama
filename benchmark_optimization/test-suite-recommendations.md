# Test-Suite Recommendations

## Scope

This review covers three different things that currently share the word
“test”:

1. Python unit and integration tests under `tests/` and
   `model_benchmark/tests/`;
2. model capability cases in `model_benchmark/capability_cases.json`, fixed-plan
   cases in `model_benchmark/refactor_cases.json`, and the declarative YAML
   cases;
3. manual browser scripts under `scripts/` and `test_stories/`.

A static scan finds about 1,295 Python test functions across roughly 19,400
lines, but only 13 declarative YAML benchmark cases and one principal playable
story fixture. The framework has much more test coverage than the behavior of
the generated games.

Test collection could not be executed in the current shell because neither
`uv` nor `pytest` is installed there. Recommendations below are therefore based
on source inspection and the recorded benchmark evidence. Run collection,
coverage, and mutation testing before deleting non-trivial coverage.

## Executive recommendation

The refactor benchmark should make mechanics programmatic and model text
bounded. Use `refactor-canary` (10 requests/model) during implementation and
`refactor-core` (24 requests/model) for matched architecture baselines. Each
case supplies a trusted plan with fixed slots, state/entity reference allowlists,
and required components; the model fills only narrative and choice-copy fields.
Keep the direct-SugarCube suites as historical diagnostics, not as promotion
gates for the new harness.

Add tests that answer these questions:

- Is the benchmark result reproducible and comparable?
- Did the model implement the requested mechanic, not merely spell its name?
- Does the generated passage compile and execute correctly?
- Does it preserve state and continuity across several passages?
- Can untrusted story context escape the prompt or corrupt generated code?
- Does a test fail when the production behavior is deliberately broken?

Remove or consolidate tests that:

- contain no test functions;
- merely scan source text for TODOs;
- catch every exception and therefore cannot fail;
- reproduce production logic inside the test instead of invoking it;
- duplicate a second test suite without protecting a distinct boundary;
- are confounded model cases whose prompt and expected result disagree;
- measure a behavior that passes vacuously in nearly every case.

## Tests to add first

### P0 — Experimental validity

These tests should be added before another optimization campaign. Their main
benefit is preventing false conclusions.

| Test | What it should prove | Benefit |
|---|---|---|
| Same-seed replay | Identical model/case/config/seed produces the same output or a documented bounded difference | Establishes whether small deltas can be trusted |
| Paired comparison guard | Comparison rejects runs whose model, case, seed, suite, prompt, or provisioning hashes differ | Stops accidental multi-variable experiments |
| Effective-config capsule | Every result stores prompt/overlay/suite hashes, model digest, quantization, chat-template hash, sampler settings, and seed | Makes old results reproducible and auditable |
| Token/finish provenance | Input/output tokens, output cap, finish reason, truncation, retries, and repair route are non-empty and internally consistent | Turns “suspected budget exhaustion” into a testable diagnosis |
| Immutable summary regeneration | Rebuilding a summary from an immutable result directory produces byte-equivalent metrics | Prevents the iteration-01/analysis disagreement from recurring |
| Rollback equivalence | A rolled-back overlay hashes exactly to the named baseline before it can be used in another comparison | Prevents stale-result baselines such as the iteration-06→07 boundary |
| Resume equivalence | Interrupted+resumed execution yields the same result set and provenance as uninterrupted execution | Verifies checkpointing does not bias a campaign |
| Run isolation | Two concurrent or sequential runs cannot reuse another run’s checkpoint, cache, result, or prompt artifact | Eliminates hidden cross-run contamination |

### P0 — Canonical implementation parity

There are currently two substantial benchmark implementations:
`model_benchmark/benchmark.py` contains the older three-variant/A–C behavior,
while `model_benchmark/scoring.py` contains thinking and A–H support. Imports
are split between them, despite `scoring.py` describing `benchmark.py` as a
compatibility shim.

Add a temporary parity test that runs a corpus of known responses through both
public import paths and compares types, category order, scores, prompt variants,
directions, and CLI options. The test should fail today wherever the two
implementations diverge. Then make `benchmark.py` a real re-export shim and
delete the parity test once only one implementation remains.

**Benefit:** prevents silent differences between the code being tested, the
code used by the runner, and the code used by reports.

### P0 — Evaluator oracle corpus

For every deterministic check, add at least:

- one minimal passing response;
- one failure for each independent rule;
- one near miss;
- one irrelevant but confusing example;
- one empty/truncated example;
- one JSON and one delimited representation where applicable.

The oracle corpus must include the known parser/scorer contradiction: a JSON
key exists but contains `null`, an array, or an empty string. Expected section
presence should come from usable parsed content, not substring presence.

**Benefit:** makes false positives and false negatives visible before model
runs spend GPU time.

### P0 — Test-the-tests mutation check

Automate a small mutation suite that deliberately:

- accepts Markdown;
- ignores a missing `SUMMARY`;
- treats `<<set $x = ...>>` as valid;
- disables macro-balance checking;
- accepts a link to a nonexistent passage;
- drops one state write;
- disables identity redaction.

At least one test must fail for every mutation.

**Benefit:** proves that the large suite detects real defects rather than only
confirming current implementation details.

## Model capability tests to add

### 1. Executed state-transition cases

Give an initial state, request a passage, compile it, select each choice, and
assert the exact resulting state. Include guarded choices, increment/decrement,
inventory mutation, and mutually exclusive branches.

**Benefit:** distinguishes mentioning a variable or macro from implementing the
mechanic correctly.

### 2. Link target and reachability cases

Require every generated choice to point to an existing or explicitly planned
passage. Compile and traverse the links. Include missing targets, self-loops,
unreachable passages, intentional endings, and conditional-only routes.

**Benefit:** catches games that format correctly but cannot be played.

### 3. Multi-passage continuity cases

Generate a sequence of 3–5 passages. Assert that named characters, injuries,
inventory, promises, location, open threads, and completed threads remain
consistent after branching and rejoining.

**Benefit:** tests the harness’s core value—maintaining a story—not isolated
single-response formatting.

### 4. Save, reload, undo, and backtrack cases

Perform state-changing choices, save/reload the compiled game, use history or
back navigation where supported, and verify state plus rendered content.

**Benefit:** finds serialization/history defects invisible to static Twee
validation.

### 5. Output-boundary cases

Run the same task with output limits just below, at, and above the observed
completion length. Record finish reason and require a complete final envelope
or an explicit recoverable truncation status.

**Benefit:** isolates budget failures from instruction-following failures.

### 6. Prompt-hierarchy attack cases

Put fake instructions, section headers, Markdown examples, fake system text,
and “ignore previous instructions” inside lore, character data, retrieved
context, previous prose, and style guides.

**Benefit:** validates that untrusted story content remains data and cannot
override the generation contract.

### 7. Escaping and hostile-value cases

Use names and values containing quotes, backslashes, `]]`, `>>`, newlines,
Unicode combining characters, emoji, HTML, script-like text, and SugarCube
markers. Compile and execute the result.

**Benefit:** protects generated Twee, JavaScript strings, links, JSON, and the
browser from corruption or injection.

### 8. Metamorphic equivalence cases

Rename characters/variables, rephrase the direction, reorder irrelevant
context, change genre, and add benign distractors while preserving the required
mechanic. Assert equivalent semantic outcomes.

**Benefit:** exposes prompt brittleness and fixture memorization.

### 9. Real prose conversation cases

The current conversation suite mostly tests adoption of a custom signed
`DIALOGUE:`/`INNER MONOLOGUE:` convention. Add a separate product-level test
where ordinary SugarCube prose with dialogue is compiled and rendered, then
score speaker clarity, ordering, inner-thought placement, and choice relevance
without requiring the transport labels.

**Benefit:** separates “can write and render a conversation” from “can imitate
this benchmark’s serialization convention.”

### 10. Choice-quality and consequence cases

Require choices to be distinct, actionable, consistent with the prose, and to
lead to observably different state or narrative outcomes. Include cosmetic
choices as explicit negative examples.

**Benefit:** prevents structurally valid but meaningless interactivity.

### 11. Genre and register matrix

Repeat a small, fixed mechanic set across fantasy, contemporary, horror,
science fiction, romance, comedy, and non-English or mixed-language prose.

**Benefit:** reveals whether the single fantasy-tome fixture overstates general
performance or biases prompt tuning.

### 12. Repair-loop cases

Seed one defect at a time—missing header, unclosed macro, bad link, invalid
JSON, undeclared state, or compile failure—then test whether a bounded repair
step fixes only that defect without changing valid prose/state.

**Benefit:** measures recovery behavior and guards against destructive full
regeneration.

### 13. Cross-serialization equivalence

Generate the same passage through delimited text, JSON, skeleton filling, and a
future AST path. Normalize them and compare prose, choices, and state effects.

**Benefit:** reveals whether a transport changes semantics and supports safely
replacing direct SugarCube generation.

### 14. Context causal-ablation cases

Run with the full context, the minimal required facts, one required fact
removed, and irrelevant facts added. The output should change only when a
causally relevant fact changes.

**Benefit:** directly evaluates retrieval quality and context dilution.

### 15. Browser random-walk invariants

On generated and fixture stories, perform seeded random walks while asserting:
no console errors, no raw macros, no blank non-ending passages, valid state
types, at least one way out of non-endings, and stable save/reload.

**Benefit:** finds path interactions that fixed happy-path scripts miss while
remaining reproducible.

## Python tests to add

| Area | Missing or under-tested behavior | Benefit |
|---|---|---|
| JSON parsing | `prose` as array/null, nested `response`/`result` wrappers, duplicate keys, trailing text, valid JSON with empty required content | Covers failures repeatedly seen in raw benchmark output |
| Prompt overlay | exact placement/order in the fully rendered prompt for every variant and chat-template class—not only fragment concatenation | Tests what the model actually receives |
| Ollama transport | seed forwarding, token accounting, finish reasons, retry classification, timeout cancellation, malformed streaming chunks | Completes reproducibility and failure provenance |
| Persistence | crash between temp write and replace, disk-full/permission failure, concurrent writers, fsync expectations, resume after partial JSONL | Protects long GPU campaigns |
| Comparison logic | paired confidence intervals, missing pairs, changed cohorts, duplicate cases, multiple-testing correction, minimum detectable effect | Prevents invalid experiment promotion |
| Anonymization | hostile identities in nested keys, filenames, HTML attributes, compressed artifacts, exception chains, overlapping aliases | Preserves privacy under adversarial output |
| Browser explorer | cycles, conditional links, dynamically inserted choices, delayed navigation, save dialogs, reload, history divergence | Expands beyond static detector unit tests |
| Compile pipeline | generated asset paths, hostile titles/IFIDs, duplicate passage names, Unicode filenames, template collision behavior | Protects end-to-end build integrity |
| Story transaction | precondition validation, atomic commit, invariant failure rollback, rendered macro equivalence | Enables the state-machine architecture safely |
| Cache isolation | prompt/config/model hash in cache key, no reuse across seed or template changes | Prevents contaminated benchmark comparisons |

## Tests and cases that can be removed now

These removals do not discard meaningful behavioral coverage.

### Empty placeholder modules

- `tests/pw_smoke_test.py`
- `tests/pw_e2e_playtest.py`
- `model_benchmark/tests/test_metadata.py`
- `model_benchmark/tests/test_persistence.py`

The first two contain only “intentionally left empty” comments. The latter two
contain imports and TODO comments but no tests. Track unfinished work in an
issue or roadmap rather than in collected test modules.

**Benefit:** honest collection counts and less confusion about what CI covers.

### Source-text policy tests

Remove `test_no_todo_markers_in_playtest` and
`test_no_not_implemented_in_playtest` from `tests/test_playtest_e2e.py`.
They invoke `grep` with a hard-coded `/opt/data/...` working directory and test
source wording rather than behavior. TODOs are not runtime defects.

**Replacement:** targeted import, protocol, and behavior tests—or a repository
lint job if TODO policy is genuinely required.

**Benefit:** eliminates environment-specific failures and incentives to hide
useful TODOs.

### Non-assertive Playwright test

Remove or immediately replace `test_launch_browser_missing_playwright`. It
catches any `Exception` and passes, so browser-launch regressions cannot make
it fail.

**Replacement:** monkeypatch import resolution so `playwright.sync_api` raises
`ModuleNotFoundError`, then assert the exact public exception and message.

**Benefit:** converts an always-green test into real optional-dependency
coverage.

### Locally reimplemented deduplication test

Remove or replace `test_issue_dedup_by_category_passage`. The test manually
implements a `seen` set after calling detectors twice; it proves that the local
test code deduplicates, not that the production runner does.

**Replacement:** send duplicate issues through the production aggregation path
and assert one stored/reported issue.

**Benefit:** detects regressions in actual deduplication.

### Scripts from pytest discovery

Remove `scripts/` from pytest `testpaths`, or rename
`scripts/test_player_flow.py` and `scripts/test_endings.py` to names that make
their manual nature clear. They import optional Playwright at module import
time and implement standalone report-producing flows rather than pytest tests.
Keep and run them as an explicitly marked browser job until their useful paths
are migrated to pytest.

**Benefit:** unit-test collection no longer depends on an optional browser
package or accidentally collects manual tools.

## Tests to consolidate, then remove

These contain useful coverage, so deletion must follow migration and mutation
verification.

### Standalone underscore smoke scripts

- `model_benchmark/tests/_checkpoint_smoke.py`
- `model_benchmark/tests/_failures_smoke.py`
- `model_benchmark/tests/_metadata_smoke.py`

They are standalone scripts, are excluded by normal pytest naming, and overlap
the pytest suite. Port any unique assertions into `test_checkpoint.py`, a real
`test_failures.py`, and a real `test_metadata.py`; then delete the smoke files.

**Benefit:** one runner, one fixture system, and coverage that CI actually
collects.

### Duplicated core/template tests

`tests/test_core.py` and `tests/test_template_aware.py` share at least 15 exact
test method names, including deprecated macro warnings, prompt-version checks,
template guidance, asset handling, include rendering, and container macros.
Move each behavior to the file matching its production module and keep only a
small integration test for cross-module wiring.

**Benefit:** less maintenance and fewer synchronized edits without losing a
distinct boundary.

### CLI parser duplication

`model_benchmark/tests/test_config.py` and `test_cli.py` both test parser
defaults, anonymization defaults, and flag count; `test_cli_subcommands.py`
covers the newer command surface. Define one contract test per public CLI and
move lower-level configuration parsing to `test_config.py`.

**Benefit:** prevents old and new CLI expectations from silently diverging.

### Repeated live E2E generation

`tests/test_e2e.py` independently regenerates premise/world/opening for several
tests, then runs the entire flow again in `test_full_e2e_flow` and again for
the report test. Consolidate this into:

- fast endpoint contract tests with mocked Ollama;
- one fixture-driven live generation journey;
- one report serialization unit test using a constructed report.

Also make compiled-HTML tests consume the same project fixture; the current
function-scoped `e2e_config` project is separate from the session server’s
project, so HTML checks can skip without testing the artifact produced earlier.

**Benefit:** much lower runtime/cost, fewer stochastic failures, and a real
end-to-end artifact chain.

## Benchmark checks to remove from the universal objective

Do not delete their implementations. Stop applying them to cases where the
requested behavior cannot exercise them.

### `variable_scoping`

It historically passed 100% and passes when a response contains no `<<set>>`
at all because its strict verdict only rejects `=` setters and `setup.` in
prose. Make it required only for tests that demand state reads/writes, and add a
positive requirement that the requested write occurred.

### `naked_interpolation`

It historically passed 100% and its strict verdict only rejects simple
`<<print $var>>`; it can pass without any interpolation. Use it only when the
task requires interpolation and assert the named variable appears in the
correct rendered location.

### `link_setter_syntax`

It historically passed 100% and often passes because there are no links to
inspect. Apply it to dedicated link/setter cases and replace universal use with
compiled reachability and state-transition tests.

**Benefit:** removes vacuous green checks from the aggregate while preserving
targeted regression protection.

## Model cases to remove or rewrite

### Remove `edge_empty_response_001` from model execution

It has an empty input, uses `exact_match`, and sets `pass_threshold: 0.0` while
describing scorer robustness. This is a unit test of the scoring system, not a
model capability test, and a zero threshold is non-discriminating.

Move its assertions into the evaluator oracle corpus.

### Rewrite `edge_markdown_mixed_001`

The prompt explicitly permits Markdown while the expected behavior prefers
SugarCube and the benchmark penalizes Markdown. This tests conflict resolution,
not markup compliance, and its result is ambiguous.

Keep two single-axis cases instead: one clean SugarCube-only instruction and
one explicitly labeled adversarial-context case where Markdown appears only in
untrusted data.

### Rewrite the thinking puzzle and social-deduction cases

Both currently inject the unrelated direction “use `<<switch>>` and
`<<case>>` on the player’s current location,” even though one requests rune
logic and the other reputation/social logic. Their metadata category is also
`markup_compliance`, which does not represent the claimed reasoning capability.

Align prompt, expected state transition, and deterministic checks before using
them for model ranking.

### Consolidate duplicate macro cases

The YAML corpus and `capability_cases.json` both cover markup, conditionals,
loops/capture, forms, include, switch/case, and thinking. Choose one canonical
executable corpus. Preserve a minimal YAML example for configuration-loader
tests, but do not pay for semantically duplicate GPU cases unless they vary one
declared axis such as context size or serialization.

**Benefit:** more GPU budget for repeated seeds, genres, state execution, and
browser validation—the additions that provide genuinely new information.

## Tests that may look redundant but should stay

- Anonymization across JSON, HTML, CSV, Markdown, filenames, keys, and values:
  each output channel is a separate privacy boundary.
- Signal and emergency-checkpoint tests: long remote GPU runs make interruption
  behavior operationally important.
- Parser golden tests for malformed and legacy formats: tolerant parsing is a
  compatibility boundary, though the canonical success path should remain
  strict and separately measured.
- Compiled HTML JavaScript, CSS, passage-data, entity, and raw-macro checks:
  these catch different classes of broken build artifact.
- Snapshot-delta invariants and cycle guards: history/state reconstruction is
  foundational and difficult to validate only through happy-path E2E tests.
- Candidate-test security restrictions and publish allowlists: they protect the
  remote benchmark machine and private model identities.

## Suggested execution order

1. Delete empty placeholders and remove `scripts/` from pytest discovery.
2. Replace the three non-assertive/source-scanning playtest tests.
3. Resolve `benchmark.py` versus `scoring.py` and add experimental-validity
   guards.
4. Add the evaluator oracle and mutation checks.
5. Fix or remove confounded declarative model cases.
6. Add executed state-transition, multi-passage continuity, adversarial
   context, output-boundary, and browser random-walk tests.
7. Measure coverage and mutation score, then consolidate duplicate unit/E2E
   tests.

This order improves trust first, reduces obvious noise second, and only then
spends more GPU/browser time on broader behavioral coverage.
