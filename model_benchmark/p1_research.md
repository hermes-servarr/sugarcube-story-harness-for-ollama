# Phase 1: Research and Planning

**Task:** Benchmark reliability, reporting, anonymization, and review upgrade
**Repo:** /opt/data/sugarcube-story-harness-for-ollama-p5-input-macros
**Branch:** main (commit a6c7a16)
**Scope:** model_benchmark/ directory only — do not touch harness/ or scripts/
**Triage:** complexity=simple, risk=medium

---

## 1. Problem Statement

The existing `model_benchmark/benchmark.py` (970 lines) is a single-file, in-process benchmark that sends controlled prompts (built from real `harness.prompts` templates) to one or more Ollama models, scores each response across 6 SugarCube compliance categories, and prints a text/JSON report. It works — 63 tests pass, dry-run mode exists for CI — but it lacks the reliability, reproducibility, fault-tolerance, and anonymization features required for trustworthy, shareable model evaluation:

1. **No checkpointing / resume.** A crash or timeout mid-run loses everything. Results are only persisted if the user explicitly passes `--output`/`--json-output`, and only at the very end of the run.
2. **No progress reporting.** Long runs (many models × variants × directions × repetitions) print nothing until completion. No per-case status (PASS/FAIL/ERROR/TIMEOUT/SKIPPED), no ETA, no counts.
3. **No reproducibility metadata.** The report records prompt_version and config, but not the source commit, OS/Python/package versions, generation params, dataset checksums, seeds, or CLI args. Two runs cannot be reliably compared.
4. **No anonymization.** Internal reports contain model names, provider info, file paths. There is no anonymized variant for sharing with reviewers/the public, and no private alias mapping.
5. **No structured result schema.** Results are dataclasses serialized ad-hoc via `dataclasses.asdict` + `default=str`. No schema version, no per-result fields for tokens/cost/retry/status/failure-category/timestamps/artifact-refs.
6. **No failure analysis.** Failures are buried inside `ModelRunResult.category_results[].details`. No grouping by failure category, no CSV export, no distinction between benchmark failures and infrastructure failures.
7. **No HTML reports.** Only text + JSON. No self-contained interactive HTML for rapid inspection.
8. **No repeated-run statistics.** `--runs N` repeats but only records pass-counts; no mean/median/stddev/CI, no variance flags.
9. **No baselines / comparisons / regressions.** No way to compare against a previous run or a baseline model.
10. **No deterministic output organization.** No timestamped run dirs; outputs go wherever the user points `--output`.
11. **Tight coupling.** Scoring, execution, formatting, and CLI are all in one 970-line file. Adding an exporter or metric requires editing the monolith.

The upgrade must transform this into a reliable, reproducible, fault-tolerant evaluation system **in-place** (not a separate repo), preserving existing functionality, the 6 scoring categories, dry-run mode, and all 63 existing tests.

---

## 2. Relevant Files and Modules

### 2.1 model_benchmark/ (the upgrade target — all new code goes here)

| File | Lines | Role | Disposition |
|------|-------|------|-------------|
| `benchmark.py` | 970 | Monolith: 6 dataclasses, 6 scoring fns, orchestrator, prompt fixture, model interaction, report assembly, text/JSON formatters, CLI | **Refactor** into modules; preserve scoring + fixture + dry-run |
| `test_benchmark.py` | 657 | 63 tests: scoring, orchestrator, fixture, report, dry-run, graceful failure, 10 invariants | **Preserve** all 63; add new tests for new features |
| `__init__.py` | — | Package marker | Keep (update exports if needed) |
| `README.md` | 228 | User docs | **Update** to reflect new architecture + commands |

### 2.2 harness/ (imported, NOT modified — INV-5 still applies)

| Module | What benchmark imports | Notes |
|--------|----------------------|-------|
| `harness/prompts.py` | `PROMPT_VERSION` (=7), `build_compact_passage_prompt`, `build_full_passage_prompt`, `build_json_passage_prompt` | INV-3: must keep using real builders. INV-4: prompt_version from live import. |
| `harness/parsers.py` | `REQUIRED_SECTIONS` (={"PROSE","CHOICES","SUMMARY"}), `needs_repair`, `parse_model_output`, `parse_model_output_json`, `structured_score` | Parsers produce `ModelOutput` from raw text/JSON. |
| `harness/models.py` | `HarnessConfig` (pydantic BaseModel), `ModelOutput` (pydantic), `ParsedChoice` (pydantic) | `ModelOutput.prose`, `.choices`, `.state`, `.summary`, `.parse_warnings`. `HarnessConfig.ollama_model`, `.ollama_base_url`, `.temperature`, `.num_predict`. |
| `harness/ollama_client.py` | `call_ollama_sync`, `model_profile` | `call_ollama_sync(cfg, prompt, timeout, *, temperature, num_predict, format_spec, label) -> str`. Raises on error. |
| `harness/passage.py` | `extract_links`, `scan_state_reads`, `scan_state_writes` | Used by scorers. |
| `harness/validation.py` | `MACRO_CONTAINERS`, `_iter_macro_tags` | Used by `score_macro_usage`. |

### 2.3 pyproject.toml

- Python >=3.11, hatchling build, uv for deps.
- Existing deps: fastapi, uvicorn, httpx, pyyaml, pydantic>=2.7, jinja2, networkx, pytest.
- **Constraint:** No new dependencies unless absolutely necessary. Self-contained HTML (no CDN/JS) — can be done with stdlib + inline CSS/JS. CSV with stdlib `csv`. JSON/JSONL with stdlib `json`. No need for jinja2 in benchmark (harness already has it but we avoid touching harness). Atomic writes with stdlib `tempfile`+`os.replace`.

### 2.4 Existing data structures in benchmark.py (to preserve/refactor)

```
PromptVariant = Literal["compact", "full", "json"]
DirectionKey = Literal["A", "B", "C"]
CategoryName = Literal[6 names]
_CATEGORY_ORDER: tuple (canonical order — INV-9)

@dataclass(frozen=True) CategoryResult   — name, passed, score, details, evidence
@dataclass(frozen=True) ModelRunResult    — model_name, variant, direction, run_index, raw_response, parsed_output, category_results, overall_pass, elapsed_seconds, error
@dataclass(frozen=True) CategorySummaryEntry — name, pass_rate, total, passed
@dataclass(frozen=True) ModelReport       — model_name, runs, category_summary, overall_score, runs_total, runs_passed
@dataclass(frozen=True) BenchmarkConfig   — models, variants, directions, base_url, timeout, num_predict, temperature, runs, dry_run, output_path, json_output_path
@dataclass(frozen=True) BenchmarkReport   — models, prompt_version, config, generated_at, ollama_reachable
```

### 2.5 Existing functions in benchmark.py

- 6 scorers: `score_markup_compliance`, `score_variable_scoping`, `score_passage_structure`, `score_macro_usage`, `score_naked_interpolation`, `score_link_setter_syntax` (all pure, INV-2)
- `score_response(raw, parsed, variant) -> list[CategoryResult]` (orchestrator, INV-9)
- `build_fixture_prompt(variant, direction) -> str` (INV-3)
- `run_single_model(model, variant, direction, cfg, run_index) -> ModelRunResult` (INV-1, INV-6)
- `discover_models(base_url) -> list[str]`
- `build_model_report(model, runs) -> ModelReport`
- `build_benchmark_report(reports, cfg) -> BenchmarkReport` (INV-4)
- `format_report_text(report) -> str`, `format_report_json(report) -> str`
- `main(argv) -> int` (CLI, INV-8 dry-run)

### 2.6 Existing invariants (INV-1..INV-10) — must be preserved

These 10 invariants are enforced by tests in `test_benchmark.py::TestInvariants`. The upgrade must keep them valid or explicitly document deviations in P5.

---

## 3. Current Execution Flow

```
main(argv)
  -> parse args -> BenchmarkConfig
  -> if dry_run:
       parse _DRY_RUN_RESPONSE -> score_response -> build report (1 model "(dry-run)")
  -> else:
       discover_models (or use --models)
       for each model:
         for each variant:
           for each direction:
             for run_idx in range(runs):
               run_single_model -> ModelRunResult   [Ollama call + parse + score]
         build_model_report
       build_benchmark_report(all model reports)
  -> format_report_text -> print / --output
  -> format_report_json -> --json-output (optional)
```

**Weaknesses mapped to spec sections:**
- No progress events during the nested loop (§2)
- No checkpoint after each `run_single_model` (§3)
- No run dir — outputs are user-specified paths (§4)
- No reproducibility metadata beyond prompt_version+config (§5)
- No anonymization (§6, §7)
- Result schema is the dataclass — no version, tokens, cost, status, etc. (§8)
- No failure grouping, no CSV (§9, §10)
- No HTML (§11)
- Only JSON + text; no JSONL/CSV/Markdown (§12)
- No exec summary, quality review, repeated-run stats, baselines (§13-16)
- Single file — not modular (§12, §17)

---

## 4. Proposed Approach

### 4.1 Architecture: Modular layers in model_benchmark/

Refactor `benchmark.py` into a package of focused modules. The SugarCube-specific scoring stays isolated from generic benchmark framework code so future extraction is straightforward.

**Proposed module layout:**

```
model_benchmark/
  __init__.py            # re-exports public API (preserve compat)
  scoring.py             # 6 scorers + score_response + _CATEGORY_ORDER (MOVED from benchmark.py, unchanged)
  fixtures.py            # build_fixture_prompt + fixture constants (MOVED)
  runner.py              # run_single_model, discover_models, execution loop, progress, checkpoint, resume
  schema.py              # Versioned result schema (new dataclasses/pydantic models)
  config.py              # BenchmarkConfig (extended) + CLI config parsing
  checkpoint.py          # Checkpoint state, atomic persistence, resume logic
  metadata.py            # Reproducibility metadata collection (commit hash, env, versions)
  anonymization.py       # Alias generation, internal->anonymized transform, private mapping
  persistence.py        # Output dir creation, atomic writes, results JSON/JSONL, run_manifest
  reports.py             # Text + Markdown report formatters
  html_report.py         # Self-contained HTML report generator (inline CSS/JS, no CDN)
  failures.py            # Failure grouping, CSV export, benchmark-vs-infrastructure classification
  comparisons.py         # Baseline loading, regression detection, diff computation
  stats.py               # Repeated-run statistics: mean/median/stddev/CI, variance flags
  cli.py                 # main() — argparse, wires modules together
  benchmark.py           # THIN compatibility shim re-exporting from scoring/fixtures/runner for old imports
  test_benchmark.py      # EXISTING 63 tests (preserve; may update imports)
  test_<new>.py          # NEW tests for checkpoint, anonymization, persistence, stats, etc.
```

**Key design decisions:**
- `benchmark.py` becomes a thin shim so `from benchmark import score_markup_compliance` still works (preserves existing tests' import style and INV tests that `import benchmark`).
- The 6 scoring functions move to `scoring.py` **unchanged** — INV-1/2/3/6/7/9/10 stay valid.
- `build_fixture_prompt` moves to `fixtures.py` unchanged — INV-3 stays valid.
- `run_single_model` moves to `runner.py` — INV-1 (no generate_story_output) preserved by not importing it.

### 4.2 Result schema (§8) — versioned, richer

Extend the result model with the fields the spec requires while keeping the existing `ModelRunResult`/`CategoryResult` as the scoring core. The new `schema.py` defines a versioned `ResultRecord` wrapping the scored result with metadata:

- `schema_version: str`
- `test_id, test_version, capability, category, subcategory, difficulty`
- `dataset, split, repetition`
- `input_summary, expected_behavior, reference_rubric`
- `actual_output (raw), parsed_output`
- `score, max_score, normalized_score, pass_threshold`
- `status` (PASS/FAIL/ERROR/SKIPPED/INVALID/TIMEOUT/CANCELLED)
- `failure_category` (benchmark vs infrastructure)
- `evaluator_reasoning, evaluator_confidence`
- `runtime_seconds, input_tokens, output_tokens, total_tokens, cost`
- `retry_count, error_details`
- `model_alias, config_alias, prompt_version, evaluator_version`
- `random_seed`
- `timestamps` (start, end)
- `artifact_refs`
- `parent_result_id, comparison_result_id`

The existing `ModelRunResult` maps to a `ResultRecord` with capability="sugarcube_direction_following", category from the 6 scorers, etc. A converter bridges old->new so existing tests still pass.

### 4.3 Output organization (§4) — deterministic run dirs

```
benchmark_outputs/
  2026-07-30T004100Z_sugarcube-bench_<run-id>/
    run_manifest.json
    checkpoint.json
    results_internal.json
    results_internal.jsonl
    results_anonymized.json
    results_anonymized.jsonl
    anonymization_mapping.private.json
    summary_internal.md
    summary_anonymized.md
    report_internal.html
    report_anonymized.html
    failures_internal.csv
    failures_anonymized.csv
    logs/
    artifacts/
```

- Run dir name: `<ISO-timestamp>Z_<benchmark-id>_<short-run-id>` — collision-resistant, no identity in anonymized filenames (anonymized files use the same dir name; identity is only inside the internal files).
- Atomic writes: write to `tmp` then `os.replace`.

### 4.4 Checkpointing (§3) — atomic, resumable

- `checkpoint.py` maintains a `CheckpointState` tracking completed result IDs.
- Auto-persist after every N completed cases (configurable `--checkpoint-every`, default 10), after configurable time interval (`--checkpoint-interval`, default 60s), after critical sections, on completion.
- Emergency checkpoint via signal handler (SIGINT/SIGTERM) on interruption.
- Atomic write: `checkpoint.json` written via tmpfile+rename.
- Resume: load `checkpoint.json`, skip completed result IDs, record `new/resumed/retried/recovered` provenance per result.
- Distinguish file roles: run_manifest (run state), checkpoint (resumable state), results_* (finalized), summary/report (human), anonymization_mapping (private).

### 4.5 Progress reporting (§2)

- `runner.py` emits structured progress events: current test/stage, completed/total, %, elapsed, ETA, model alias, config, variant/direction/repetition, status counts (pass/fail/error/skipped).
- Terminal output: aligned columns, section headings, stable labels.
- `--quiet` (errors only) and `--verbose` (full detail) modes.
- Optional machine-readable events to a log file.
- Status classifications: PASS, FAIL, ERROR, SKIPPED, INVALID, TIMEOUT, CANCELLED.
- Single failure does not stop unrelated tests (already partially true via INV-6 graceful failure; extend to the loop level).

### 4.6 Anonymization (§6, §7)

- `anonymization.py` generates deterministic aliases: `Model_A`, `Model_B`, `Provider_A`, `Config_01`, `Run_01` from a stable sort of internal names.
- Transforms results, metadata, errors, file paths, finish reasons, prompts — replacing identity fields.
- `anonymization_mapping.private.json`: separate file, never referenced in anonymized report, marked private, not in reviewer artifacts.
- Both internal and anonymized versions use the same schema, metrics, ordering, precision, layout, grouping.
- No identity leak via filenames, HTML metadata, JS vars, embedded JSON, CSS classes, chart colors, tooltips, sort order, raw errors.
- Tests scan anonymized outputs (JSON values+keys, HTML source, embedded scripts, Markdown, CSV, filenames, paths, logs, error messages, metadata) for identity strings.

### 4.7 Reports (§9-12) — text, markdown, HTML, CSV, JSON, JSONL

- All exports derive from the same canonical `ResultRecord` objects — no recomputation.
- `reports.py`: text + markdown summary (tables for overall score, by-category, pass/fail/error counts, runtime, tokens, variance, CIs, baseline comparisons, regressions).
- `html_report.py`: self-contained HTML (inline CSS/JS, no CDN), full-text search, filter, sort, expandable details, summary charts, regression/confidence indicators, responsive, offline, color-blind safe (text/icons/labels not color-only). Internal + anonymized variants.
- `failures.py`: group failures by category, per-group counts/%/severity/examples/suggested-investigation; per-case detail; CSV export; benchmark-vs-infrastructure classification.
- JSON + JSONL for machine consumption.

### 4.8 Statistics (§15), baselines (§16), exec summary (§13), quality review (§14)

- `stats.py`: repeated-run mean/median/stddev/min/max/CI, per-test consistency, variance flags, insufficient-sample-size flags.
- `comparisons.py`: load a previous run's results, compute absolute/relative diff, changed pass/fail outcomes, newly failing/passing, category regressions, runtime/token changes; configurable thresholds.
- Exec summary (in reports): strongest/weakest capabilities, common failure modes, largest regressions, anomalies, low-confidence, critical infra failures, prioritized improvements.
- Quality review (documented in a `benchmark_quality.md` or summary section): coverage, scoring quality, leakage/contamination, bias, statistical reliability, comparability, controls.

### 4.9 Compatibility & test preservation

- `benchmark.py` shim re-exports the 6 scorers, `score_response`, `build_fixture_prompt`, `run_single_model`, `discover_models`, `build_model_report`, `build_benchmark_report`, `format_report_text`, `format_report_json`, `main`, `PROMPT_VERSION`, dataclasses, type aliases, `_CATEGORY_ORDER`, `_DRY_RUN_RESPONSE`. This keeps `test_benchmark.py`'s `from benchmark import ...` working.
- The 63 existing tests must pass unmodified (or with only import-path adjustments if the shim is insufficient — but the shim approach is preferred).
- INV-1..INV-10 remain enforced. INV-5 (no harness modification) is unchanged.

---

## 5. Open Questions

**OQ-1 (Scoring layer — preserve exactly?):** The 6 scoring functions and their sub-check structure are covered by INV-1/2/6/7/9/10 and 63 tests. I propose moving them to `scoring.py` byte-for-byte. *Decision needed: is a pure move acceptable, or does the reviewer want them to stay in benchmark.py with the rest split out?* My recommendation: move to `scoring.py` and keep `benchmark.py` as a re-export shim — cleaner, and the shim preserves all imports.

**OQ-2 (Result schema — extend ModelRunResult or wrap it?):** The spec (§8) wants ~30 fields per result. The existing `ModelRunResult` has 12. Two options: (a) add fields to `ModelRunResult` (breaks frozen=True but tests use keyword construction so it's compatible if new fields have defaults), or (b) create a new `ResultRecord` in `schema.py` that wraps/embeds the scored `ModelRunResult` + adds metadata fields. *My recommendation: (b) — a separate `ResultRecord` keeps the scoring core stable and the schema concerns separate.* Needs reviewer agreement in P2.

**OQ-3 (Anonymization scope — what counts as identity for this benchmark?):** Model name, Ollama base URL (may contain hostname), file paths in errors, the `label` arg to `call_ollama_sync` (contains model name). The fixture prompts contain "apprentice"/"mentor's tower" — these are fixture content, not identity, so they appear identically in both versions. *Confirm: only model/provider/path/hostnames are anonymized, not fixture story content.*

**OQ-4 (Baselines — where stored?):** Comparisons need a previous run to compare against. Options: (a) pass `--baseline <path-to-previous-run-dir>`, (b) auto-find the most recent prior run dir. *My recommendation: explicit `--baseline` flag; auto-find is fragile.*

**OQ-5 (HTML report complexity vs. "self-contained, no CDN"):** A full-featured interactive HTML (search, filter, sort, charts) in pure inline JS is substantial. *Confirm: acceptable to implement a solid subset (search, filter by status/category, sortable tables, expandable rows, summary stats) without chart libraries? Charts can be simple inline SVG/CSS bars.*

**OQ-6 (New dependencies):** The constraint says no new deps unless absolutely necessary. Statistics (mean/stddev/CI) can use stdlib `statistics` + `math`. Percentiles/quartiles via `statistics.quantiles`. No scipy/numpy needed. *Confirm: stdlib statistics is sufficient?* Yes — this benchmark's sample sizes are small (runs×models×variants×directions).

**OQ-7 (Concurrency):** The spec mentions concurrency in reproducibility metadata (§5). The current `run_single_model` is sequential. Should the upgrade add parallel model calls? *My recommendation: keep sequential for v1 (reproducibility + simplicity), record concurrency=1 in metadata. Note parallelism as a future improvement. The modular architecture makes adding it later straightforward.*

---

## 6. Phase-by-Phase Plan (P2-P7)

### Phase 2: Data Structures
Define all new types in `model_benchmark/schema.py`:
- `ResultStatus` Literal (PASS/FAIL/ERROR/SKIPPED/INVALID/TIMEOUT/CANCELLED)
- `FailureCategory` Literal (benchmark vs infrastructure subtypes)
- `ResultRecord` (versioned, ~30 fields per §8)
- `CheckpointState` (completed IDs, provenance, counts)
- `RunManifest` (run metadata, reproducibility fields per §5)
- `AnonymizationMapping` (alias->original dict)
- `ProgressEvent` (stage, completed, total, pct, elapsed, eta, counts)
- `Alias` types (ModelAlias, ProviderAlias, ConfigAlias)
- `FailureGroup` (category, count, pct, severity, examples)
- `ComparisonResult` / `Regression` (for baselines)
- `RunStatistics` (mean, median, stddev, min, max, ci, n)
- Extend `BenchmarkConfig` with new CLI fields (checkpoint-every, checkpoint-interval, output-dir, verbose, quiet, baseline, anonymize, etc.)
- Preserve existing 6 dataclasses + 3 type aliases + `_CATEGORY_ORDER` (moved to scoring.py but re-exported).
- **No methods, no functions, no logic.** Field names, types, docstrings only.

### Phase 3: Interfaces and API Stubs
Signatures for all new module functions:
- `runner.py`: `execute_benchmark(config, progress_callback, checkpoint_callback) -> list[ResultRecord]`, `resume_from_checkpoint(path) -> CheckpointState`, extended `run_single_model(...)`
- `checkpoint.py`: `save_checkpoint(state, path)`, `load_checkpoint(path) -> CheckpointState`, `atomic_write(path, data)`, `should_checkpoint(state, config) -> bool`
- `metadata.py`: `collect_reproducibility_metadata(config, commit_hash) -> RunManifest`, `redact_secrets(env_dict) -> dict`
- `anonymization.py`: `build_anonymization_mapping(results) -> AnonymizationMapping`, `anonymize_result(record, mapping) -> ResultRecord`, `anonymize_manifest(manifest, mapping) -> RunManifest`
- `persistence.py`: `create_run_dir(config, timestamp) -> Path`, `write_results(records, path, format)`, `write_manifest(manifest, path)`, `write_report(content, path)`
- `reports.py`: `format_summary_text(records, manifest) -> str`, `format_summary_markdown(records, manifest) -> str`
- `html_report.py`: `generate_html_report(records, manifest, anonymized) -> str`
- `failures.py`: `group_failures(records) -> list[FailureGroup]`, `classify_failure(record) -> FailureCategory`, `write_failures_csv(records, path, anonymized)`
- `comparisons.py`: `load_baseline(path) -> list[ResultRecord]`, `compare_runs(current, baseline) -> ComparisonResult`, `detect_regressions(comparison, thresholds) -> list[Regression]`
- `stats.py`: `compute_run_statistics(records) -> RunStatistics`, `flag_high_variance(stats) -> list[str]`
- `cli.py`: new `main(argv) -> int` wiring everything
- Preserve signatures of the 6 scorers, `score_response`, `build_fixture_prompt`, `build_model_report`, `build_benchmark_report`, `format_report_text`, `format_report_json` (moved but same signature).
- **No bodies.** Name, params, return type, one-line docstring only.

### Phase 4: Code TODOs
Place `TODO(benchmark-upgrade): <intent>` markers at every modification site:
- In `benchmark.py`: mark it as the shim, TODO to re-export from new modules.
- Create stub files for each new module with TODO markers for each function/class site.
- In `test_benchmark.py`: TODO markers for import adjustments if needed.
- New test files: `test_checkpoint.py`, `test_anonymization.py`, `test_persistence.py`, `test_stats.py`, etc. with TODO markers.
- Summary list of all TODO sites with location + intent.

### Phase 5: Mock Implementation, Test, Revert
- Implement a provisional version on a scratch branch.
- Wire up the modular architecture, checkpoint, anonymization, persistence, at least one report format, basic stats.
- Run the existing 63 tests (must pass) + new tests for checkpoint resume, anonymization (identity leak scan), metric consistency (internal==anonymized), atomic writes.
- Test dry-run still works and produces a run dir.
- Revert the scratch branch. Produce a deviation report listing all divergences from P2-P4.
- Key validation: confirm `benchmark.py` shim keeps all 63 tests green.

### Phase 6: Invariants
Declare invariants for the new system (preserving INV-1..10 where they still apply):
- INV-A1: Internal and anonymized metrics are identical (same scores, same ordering, same precision).
- INV-A2: No identity string appears in any anonymized artifact (scanned across JSON/HTML/CSV/MD/filenames/paths/logs).
- INV-A3: Checkpoint writes are atomic (tmpfile + os.replace; no partial files on crash).
- INV-A4: Resume skips completed result IDs (no duplicate recomputation unless `--force-rerun`).
- INV-A5: All exports derive from the same canonical ResultRecord list (no recomputation, no divergence).
- INV-A6: Result schema is versioned (schema_version field present on every record).
- INV-A7: No secrets/credentials/API keys in any output file.
- INV-A8: Run dir names contain no model/provider identity.
- INV-A9: Repeated-run statistics flag high-variance and insufficient-sample-size.
- INV-A10: A single failure does not terminate unrelated evaluations.
- (Plus carry-forward of INV-1..10 from the existing system, re-validated against the new module layout.)
- Each invariant: declarative statement + enforcement mechanism + check phase.

### Phase 7: Final Implementation
- Production code at approved TODO sites only.
- Conform to P2 data structures, P3 interfaces, P6 invariants.
- Full modular implementation: scoring.py, fixtures.py, runner.py, schema.py, config.py, checkpoint.py, metadata.py, anonymization.py, persistence.py, reports.py, html_report.py, failures.py, comparisons.py, stats.py, cli.py.
- `benchmark.py` thin shim.
- All 63 existing tests pass + new tests pass.
- `--dry-run` produces a run dir with internal + anonymized outputs.
- Run the full test suite, produce the final diff.

---

## 7. Constraints (from spec)

- Use `uv run python ...` for all commands.
- Preserve existing 6 scoring categories and dry-run mode.
- Preserve existing 63 tests — add new, don't break old.
- Keep `harness.*` imports working.
- INV-3 (real prompt builders) still applies.
- INV-5 (no harness modification) still applies.
- All new code in `model_benchmark/`.
- Python 3.11+.
- Self-contained HTML (no external CDN/JS deps).
- Atomic file writes (tmpfile + rename).
- No new dependencies unless absolutely necessary — add to pyproject.toml if needed.

---

## 8. Evidence Summary

- Repo at `/opt/data/sugarcube-story-harness-for-ollama-p5-input-macros`, branch `main`, commit `a6c7a16`.
- `model_benchmark/benchmark.py`: 970 lines, 6 frozen dataclasses, 3 type aliases, 6 scoring fns, orchestrator, fixture factory, model interaction, report assembly, 2 formatters, CLI.
- `model_benchmark/test_benchmark.py`: 657 lines, 63 tests (verified passing: `63 passed in 1.20s`).
- `model_benchmark/README.md`: 228 lines documenting CLI, categories, invariants.
- `harness/prompts.py`: `PROMPT_VERSION = 7`, 3 build_*_passage_prompt functions.
- `harness/parsers.py`: `REQUIRED_SECTIONS`, `parse_model_output`, `parse_model_output_json`.
- `harness/models.py`: `HarnessConfig`, `ModelOutput` (prose/choices/state/summary/parse_warnings), `ParsedChoice` (text/hint).
- `harness/ollama_client.py`: `call_ollama_sync(cfg, prompt, timeout, *, temperature, num_predict, format_spec, label) -> str`.
- `harness/passage.py`: `extract_links`, `scan_state_reads`, `scan_state_writes`.
- `harness/validation.py`: `MACRO_CONTAINERS`, `_iter_macro_tags`.
- `pyproject.toml`: Python >=3.11, deps include pydantic>=2.7, httpx, pytest. No benchmark-specific deps.
- 10 invariants (INV-1..10) enforced by `TestInvariants` class in test_benchmark.py.
- Full 19-section upgrade spec read from task comments (§1-20 + acceptance + constraints + scope).
