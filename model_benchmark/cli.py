"""CLI entry point for the model benchmark.

This module is the **home** of the :func:`main` function (P1 §4.1 module
``cli.py``, P3 §3.1).  It wires the modular benchmark together: parse args,
configure the runner (dry-run, resume, checkpoint interval), execute or
resume the benchmark (runner.py), generate text/Markdown/HTML reports to
the output dir (reports.py, html_report.py), and optionally compare against
a baseline (comparisons.py).

The signature is preserved from the legacy ``scoring.main`` so the
``benchmark.main`` compatibility shim and the existing test suite keep
working.  The body extends the legacy flow to wire the new modules
(checkpoint, anonymization, persistence, stats, comparisons).

In addition to the legacy flat-flag run flow, this module now provides a
**subcommand CLI** (t_3ccd7826) for test-config authoring and management:

    python -m model_benchmark.cli init
    python -m model_benchmark.cli new <name>
    python -m model_benchmark.cli validate [path]
    python -m model_benchmark.cli list [filters...]
    python -m model_benchmark.cli run [flags...]
    python -m model_benchmark.cli run --debug ...

When the first argument is a recognized subcommand, ``cli_main`` dispatches
to the corresponding handler.  Otherwise ``main`` falls through to the
legacy flat-flag benchmark-run flow (so ``python -m model_benchmark.cli
--dry-run`` still works exactly as before).

Phase 7 — production implementation conforming to P3 (the ``main`` and
``_build_parser`` signatures) and P6 invariants (INV-CLI1..INV-CLI9).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from model_benchmark.config import BenchmarkConfig, parse_cli_args

logger = logging.getLogger("model_benchmark.cli")

# ── Subcommand names (recognized as the first positional argument) ──────────
_SUBCOMMANDS = {"init", "new", "validate", "list", "run", "models"}


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser with all 11 legacy + 9 new flags (returns the parser, does not parse)."""
    # Reuse config._build_parser to avoid duplication; it defines all 20 flags.
    from model_benchmark.config import _build_parser as _bp
    return _bp()


# ════════════════════════════════════════════════════════════════════════════
# Legacy run flow (preserved verbatim for backward compatibility)
# ════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args, run the benchmark, write reports, optionally compare baseline; return process exit code.

    Dispatch logic:
      * If the first arg is a recognized subcommand (init/new/validate/list/run),
        dispatch to :func:`cli_main` (the subcommand CLI).
      * If the first arg is ``-h``/``--help`` with no subcommand, show the
        subcommand CLI help (so ``python -m model_benchmark.cli --help`` documents
        the new commands).
      * Otherwise run the legacy flat-flag benchmark flow so existing callers
        (``benchmark.main([...])``, ``python -m model_benchmark.cli --dry-run``)
        keep working unchanged.
    """
    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] in _SUBCOMMANDS:
        return cli_main(raw)
    if raw and raw[0] in ("-h", "--help") and not any(a in _SUBCOMMANDS for a in raw):
        # Top-level --help with no subcommand → show the subcommand CLI help.
        try:
            _build_subcommand_parser().parse_args(["--help"])
        except SystemExit as e:
            return int(e.code) if isinstance(e.code, int) else 0
        return 0
    return _legacy_main(raw)


def _legacy_main(argv: list[str]) -> int:
    """The original flat-flag benchmark run flow (preserved from the prior implementation)."""
    try:
        cfg = parse_cli_args(argv)
    except SystemExit as e:
        # argparse calls sys.exit on --help or error; return the code.
        return int(e.code) if isinstance(e.code, int) else 1

    # ── 2. Execute via BenchmarkRunner (runner.py §8.1) ────────────────────
    from model_benchmark.runner import BenchmarkRunner

    runner = BenchmarkRunner(
        cfg,
        checkpoint_every=cfg.checkpoint_every,
        checkpoint_interval_seconds=cfg.checkpoint_interval_seconds,
        output_dir=cfg.output_dir,
        verbose=cfg.verbose,
        quiet=cfg.quiet,
        force_rerun=cfg.force_rerun,
    )

    if cfg.dry_run:
        # Dry-run: produce the iteration plan without calling Ollama.
        runner.dry_run()
        # In dry-run mode, execute to get fixture-scored records.
        results = runner.execute()
    else:
        # Full run (or resume if checkpoint exists).
        resume = "--resume" in (argv or [])
        results = runner.execute(resume=resume)

    # ── 3. Stats (stats.py §8.2) — when runs > 1 ────────────────────────────
    stats_map: dict[str, Any] = {}
    if cfg.runs > 1:
        from model_benchmark.stats import compute_run_statistics
        from collections import defaultdict
        grouped: dict[str, list[float]] = defaultdict(list)
        grouped_passed: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            tid = getattr(r, "test_id", "") or ""
            score = getattr(r, "normalized_score", getattr(r, "score", 0.0))
            passed = getattr(r, "status", "FAIL") == "PASS"
            grouped[tid].append(float(score))
            grouped_passed[tid].append(bool(passed))
        for tid, scores in grouped.items():
            stats_map[tid] = compute_run_statistics(
                tid, scores, grouped_passed[tid]
            )

    # ── 4. Baseline comparison (comparisons.py §2) — when baseline_dir ─────
    comparison = None
    regressions = None
    if cfg.baseline_dir:
        from model_benchmark.comparisons import (
            load_baseline, compare_runs, detect_regressions,
        )
        baseline = load_baseline(cfg.baseline_dir)
        if baseline:
            comparison = compare_runs(results, baseline)
            regressions = detect_regressions(comparison, results, baseline)

    # ── 5. Manifest (metadata.py §8.3) ─────────────────────────────────────
    from model_benchmark.metadata import collect_reproducibility_metadata
    manifest = collect_reproducibility_metadata(
        cfg,
        run_id=getattr(runner, "run_id", None),
        repeated_runs_count=cfg.runs,
        random_seed=cfg.random_seed,
        argv=argv,
    )

    # ── 6. Anonymization (anonymization.py §8.4) — when anonymize ──────────
    anon_results = results
    anon_manifest = manifest
    if cfg.anonymize:
        from model_benchmark.anonymization import (
            build_anonymization_mapping,
            anonymize_results,
            anonymize_metadata,
        )
        mapping = build_anonymization_mapping(results, manifest=manifest, config=cfg)
        anon_results = anonymize_results(results, mapping)
        anon_manifest = anonymize_metadata(manifest, mapping)

    # ── 7. Reports (reports.py §4, html_report.py §5) ──────────────────────
    from model_benchmark.reports import (
        generate_text_report, generate_markdown_report,
    )
    from model_benchmark.html_report import generate_html_report

    # Pass stats as a list (first stat or None for the report header).
    stats_list = list(stats_map.values()) if stats_map else None

    text_report = generate_text_report(
        anon_results,
        manifest=anon_manifest,
        stats=stats_list[0] if stats_list else None,
        comparison=comparison,
        regressions=regressions,
    )
    md_report = generate_markdown_report(
        anon_results,
        manifest=anon_manifest,
        stats=stats_list[0] if stats_list else None,
        comparison=comparison,
        regressions=regressions,
    )
    html_report = generate_html_report(
        anon_results,
        anon_manifest,
        anonymized=cfg.anonymize,
        stats=stats_list[0] if stats_list else None,
        comparison=comparison,
        regressions=regressions,
    )

    # ── 8. Persistence (persistence.py §8.5) ──────────────────────────────
    from model_benchmark.persistence import (
        create_run_dir, write_json, write_jsonl, write_manifest,
    )

    run_dir = create_run_dir(cfg.output_dir, run_id=getattr(runner, "run_id", None))
    write_jsonl(run_dir / "results_internal.jsonl", results)
    if cfg.anonymize:
        write_json(run_dir / "results_anonymized.json", anon_results)
    write_manifest(run_dir / "run_manifest.json", anon_manifest)
    (run_dir / "summary_internal.md").write_text(md_report, encoding="utf-8")
    (run_dir / "report_internal.html").write_text(html_report, encoding="utf-8")

    # ── 9. Legacy output (scoring.py §8.6) — --output / --json-output ──────
    if cfg.output_path or cfg.json_output_path:
        if cfg.output_path:
            with open(cfg.output_path, "w") as f:
                f.write(text_report)
        if cfg.json_output_path:
            with open(cfg.json_output_path, "w") as f:
                f.write(text_report)

    if not cfg.quiet:
        print(text_report)

    return 0


# ════════════════════════════════════════════════════════════════════════════
# Subcommand CLI (t_3ccd7826)
# ════════════════════════════════════════════════════════════════════════════


def _build_subcommand_parser() -> argparse.ArgumentParser:
    """Build the top-level subcommand parser.

    The parser has a single positional ``command`` plus a global ``--debug``
    flag.  Each subcommand has its own sub-parser with its own flags.
    """
    parser = argparse.ArgumentParser(
        prog="model_benchmark",
        description=(
            "SugarCube model-benchmark CLI.  Manage test configs, validate "
            "them, list discovered tests, and run the benchmark.  When no "
            "subcommand is given, falls back to the legacy flat-flag run flow."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Enable verbose debug output: show resolved config after merge, "
            "matrix expansion, and capture full model I/O for each test."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── init ──────────────────────────────────────────────────────────────
    p_init = sub.add_parser(
        "init",
        help="Scaffold a new test config directory with defaults + a sample test.",
        description=(
            "Create a benchmark config skeleton in the target directory: a "
            "defaults.yaml (global defaults with sensible values and "
            "comments), a cases/ directory with one sample test, and a "
            "suites/ directory.  Idempotent — skips files that already exist."
        ),
    )
    p_init.add_argument(
        "path",
        nargs="?",
        default="benchmark_configs",
        help="Target directory to scaffold (default: benchmark_configs).",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files instead of skipping them.",
    )

    # ── new ───────────────────────────────────────────────────────────────
    p_new = sub.add_parser(
        "new",
        help="Create a new test YAML from a template.",
        description=(
            "Create a new test config file from a template.  Key fields can "
            "be supplied via flags or, when omitted and stdin is a TTY, "
            "prompted interactively.  The generated file is a valid "
            "standalone test document (kind: test)."
        ),
    )
    p_new.add_argument("name", help="Test ID / file name (e.g. my_feature_test).")
    p_new.add_argument(
        "--dir",
        default="model_benchmark/tests/cases",
        help="Directory to write the test file (default: model_benchmark/tests/cases).",
    )
    p_new.add_argument("--title", default="", help="Human-readable test name.")
    p_new.add_argument("--capability", default="", help="Capability tag.")
    p_new.add_argument("--category", default="", help="Scoring category.")
    p_new.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard", "expert"],
        default="medium",
        help="Difficulty (default: medium).",
    )
    p_new.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Tags for the test (space-separated).",
    )
    p_new.add_argument(
        "--input",
        default="",
        help="Prompt input text (default: a placeholder).",
    )
    p_new.add_argument(
        "--evaluator",
        default="exact_match",
        help="Evaluator name (default: exact_match).",
    )
    p_new.add_argument(
        "--no-prompt",
        action="store_true",
        help="Never prompt interactively; use flag/placeholder values only.",
    )

    # ── validate ──────────────────────────────────────────────────────────
    p_val = sub.add_parser(
        "validate",
        help="Load and validate config file(s), reporting all errors.",
        description=(
            "Load and validate one config file or a directory of configs.  "
            "Reports ALL validation errors (with file path + line number "
            "context) before failing — does not stop at the first error.  "
            "Exit code 0 if all valid, 1 if any errors."
        ),
    )
    p_val.add_argument(
        "path",
        nargs="?",
        help=(
            "File or directory to validate.  If omitted, validates all "
            "discovered configs in the default search dirs."
        ),
    )

    # ── list ──────────────────────────────────────────────────────────────
    p_list = sub.add_parser(
        "list",
        help="List discovered tests with selection filters.",
        description=(
            "List all discovered test configs after resolving the layered "
            "merge.  Supports the same selection filters as `run` (--select, "
            "--exclude, --tags, --max-selected, --include-disabled) to "
            "narrow the listing.  Output formats: table (default), json, "
            "ids."
        ),
    )
    p_list.add_argument(
        "--select",
        action="append",
        default=[],
        help=(
            "Include expression (can repeat).  Tests must match ALL.  "
            "Fields: tag, name, id, capability, category, difficulty, "
            "suite.  e.g. tag:smoke and not difficulty:expert"
        ),
    )
    p_list.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude expression (can repeat).  Tests matching ANY are removed.",
    )
    p_list.add_argument(
        "--max-selected",
        type=int,
        default=None,
        help="Truncate to N tests (highest priority first).",
    )
    p_list.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include tests with enabled: false (excluded by default).",
    )
    p_list.add_argument(
        "--format",
        choices=["table", "json", "ids"],
        default="table",
        help="Output format (default: table).",
    )
    p_list.add_argument(
        "--config-dir",
        action="append",
        default=[],
        help="Additional config search directory (can repeat).",
    )

    # ── run ───────────────────────────────────────────────────────────────
    p_run = sub.add_parser(
        "run",
        help="Execute selected tests with dry-run, debug, and output-format flags.",
        description=(
            "Run the benchmark.  Selects tests via the config loader + "
            "selection filters, expands matrices, and executes.  Supports "
            "dry-run (plan only), debug mode (verbose config + matrix + I/O), "
            "and output-format selection (text/json/markdown)."
        ),
    )
    p_run.add_argument(
        "--select",
        action="append",
        default=[],
        help="Include expression (can repeat).  Tests must match ALL.",
    )
    p_run.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude expression (can repeat).  Tests matching ANY are removed.",
    )
    p_run.add_argument(
        "--max-selected",
        type=int,
        default=None,
        help="Truncate to N tests (highest priority first).",
    )
    p_run.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include tests with enabled: false.",
    )
    p_run.add_argument(
        "--config-dir",
        action="append",
        default=[],
        help="Additional config search directory (can repeat).",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Score fixtures without calling Ollama (CI).  Use --plan-only for just the plan.",
    )
    p_run.add_argument(
        "--plan-only",
        action="store_true",
        help="Show selection + matrix expansion plan without executing anything.",
    )
    p_run.add_argument(
        "--output-format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Report output format (default: text).",
    )
    p_run.add_argument(
        "--output-dir",
        default="benchmark_outputs",
        help="Directory for run outputs (default: benchmark_outputs).",
    )
    p_run.add_argument(
        "--models",
        nargs="*",
        default=[],
        help="Model tags to test (empty=auto-discover).",
    )
    p_run.add_argument(
        "--variants",
        nargs="*",
        choices=["compact", "full", "json"],
        default=["compact", "full", "json"],
        help="Prompt variants.",
    )
    p_run.add_argument(
        "--directions",
        nargs="*",
        choices=["A", "B", "C"],
        default=["A", "B", "C"],
        help="Directions.",
    )
    p_run.add_argument(
        "--runs",
        type=int,
        default=1,
        help="N runs per model×variant×direction.",
    )
    p_run.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Enable verbose debug output: show resolved config after merge, "
            "matrix expansion, and capture full model I/O for each test."
        ),
    )
    p_run.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    p_run.add_argument(
        "--verbose",
        action="store_true",
        help="Emit detailed per-case progress to stderr.",
    )
    p_run.add_argument(
        "--anonymize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Anonymize model/provider/config names in reports (default True).",
    )
    p_run.add_argument(
        "--baseline",
        default="",
        help="Path to a previous run dir for baseline comparison.",
    )
    p_run.add_argument(
        "--seed",
        default="",
        help="Explicit random seed for reproducibility.",
    )
    p_run.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore existing checkpoint and recompute every case.",
    )
    p_run.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434).",
    )
    p_run.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds per model call (default 120).",
    )
    p_run.add_argument(
        "--num-predict",
        type=int,
        default=640,
        help="Max tokens to generate (default 640).",
    )
    p_run.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature (default 0.2).",
    )

    # ── models ────────────────────────────────────────────────────────────
    p_models = sub.add_parser(
        "models",
        help="List models discovered from Ollama (no benchmark run).",
        description=(
            "Query the Ollama server at --base-url for installed models "
            "and print them one per line.  No benchmark is executed.  "
            "Useful to verify Ollama is reachable and see what would be tested."
        ),
    )
    p_models.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434).",
    )

    return parser


def cli_main(argv: list[str]) -> int:
    """Dispatch to a subcommand handler.  ``argv[0]`` must be a subcommand name."""
    if not argv or argv[0] not in _SUBCOMMANDS:
        # Should not happen — main() guards this — but be defensive.
        print(f"error: unknown command {argv[0] if argv else '(none)'}", file=sys.stderr)
        return 2

    command = argv[0]
    parser = _build_subcommand_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1

    if getattr(args, "debug", False):
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(levelname)s] %(name)s: %(message)s",
        )
        logger.debug("Debug mode enabled.")

    handlers = {
        "init": _cmd_init,
        "new": _cmd_new,
        "validate": _cmd_validate,
        "list": _cmd_list,
        "run": _cmd_run,
        "models": _cmd_models,
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"error: unknown command {command}", file=sys.stderr)
        return 2
    return handler(args)


# ── init ────────────────────────────────────────────────────────────────────

_DEFAULTS_TEMPLATE = """\
# =============================================================================
# Global defaults for the SugarCube model benchmark (schema v1.0.0)
# =============================================================================
# Applied to ALL tests in ALL suites unless overridden by a higher layer.
# See model_benchmark/tests/examples/full_feature_example.yaml for the
# complete reference example demonstrating every field.
# =============================================================================

schema_version: "1.0.0"
kind: defaults

defaults:
  # Sensible defaults so a minimal test needs only `id` + `input` + `expected`.
  enabled: true
  difficulty: medium
  repetitions: 1
  tags: ["sugarcube"]          # inherited by all tests; tags always union

  model_parameters:
    base_url: "http://localhost:11434"
    timeout: 120
    num_predict: 640
    temperature: 0.2

  evaluation:
    name: exact_match
    pass_threshold: 1.0
    max_score: 1.0

  retry_policy:
    max_retries: 2
    backoff: exponential
    initial_delay: 1.0
    max_delay: 60.0
    retry_on: ["timeout", "network_error", "rate_limit"]

  metadata:
    owner: benchmark-team
    source: model_benchmark/tests

# Merge policy: `tags` is overridden to `append` so inherited tags accumulate
# rather than clobber child tags.
merge:
  list_strategy: replace
  field_overrides:
    tags: append
"""

_SAMPLE_TEST_TEMPLATE = """\
# Sample test config — generated by `model_benchmark.cli init`.
# A minimal test only needs `id` + `input` + `expected`.  All other fields
# fall back to the global defaults.  See the full reference example at
# model_benchmark/tests/examples/full_feature_example.yaml.

schema_version: "1.0.0"
kind: test

id: sample_test_001
name: Sample SugarCube markup test
description: >
  A minimal test that checks the model produces SugarCube-formatted markup
  with the PROSE, CHOICES, and SUMMARY sections.

capability: sugarcube_compliance
category: markup_compliance
difficulty: easy
tags: ["sample", "smoke"]

input: |
  Generate a short SugarCube passage where the player examines an object.
  Output the PROSE, CHOICES, and SUMMARY sections.

prompt_template:
  variant: full
  input_variables:
    direction: "Examine object"

expected:
  answer_type: structured
  behavior:
    - "Response contains PROSE, CHOICES, and SUMMARY sections"
    - "Uses SugarCube markup, not Markdown"
  contains:
    - "PROSE:"
    - "CHOICES:"
    - "SUMMARY:"
  not_contains:
    - "**"
    - "*italic*"
  must_parse_as: sugarcube_passage

evaluation:
  name: exact_match
  pass_threshold: 1.0
  max_score: 1.0

metadata:
  owner: benchmark-team
  created: "2026-07-30T00:00:00Z"
"""


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a new test config directory with defaults + a sample test."""
    target = Path(args.path)
    cases_dir = target / "cases"
    suites_dir = target / "suites"
    created: list[str] = []
    skipped: list[str] = []

    def _write(path: Path, content: str) -> None:
        if path.exists() and not args.force:
            skipped.append(str(path))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(str(path))

    _write(target / "defaults.yaml", _DEFAULTS_TEMPLATE)
    _write(cases_dir / "sample_test_001.yaml", _SAMPLE_TEST_TEMPLATE)
    # Empty suites dir with a README.
    suites_dir.mkdir(parents=True, exist_ok=True)
    readme = suites_dir / "README.md"
    if not readme.exists() or args.force:
        readme.write_text(
            "# Test suites\n\nPlace suite YAML files here (kind: suite).\n",
            encoding="utf-8",
        )

    print(f"Initialized benchmark config directory: {target}")
    if created:
        print("  Created:")
        for p in created:
            print(f"    {p}")
    if skipped:
        print("  Skipped (already exist; use --force to overwrite):")
        for p in skipped:
            print(f"    {p}")
    print()
    print("Next steps:")
    print(f"  1. Edit {target}/defaults.yaml to set global defaults.")
    print(f"  2. Add tests to {cases_dir}/")
    print(f"  3. Validate:   python -m model_benchmark.cli validate {target}")
    print(f"  4. List tests: python -m model_benchmark.cli list --config-dir {target}")
    return 0


# ── new ────────────────────────────────────────────────────────────────────


def _test_template(
    name: str,
    title: str,
    capability: str,
    category: str,
    difficulty: str,
    tags: list[str],
    input_text: str,
    evaluator: str,
) -> str:
    """Render a standalone test YAML from the given fields."""
    tags_yaml = ", ".join(f'"{t}"' for t in tags) if tags else ""
    tags_line = f"tags: [{tags_yaml}]" if tags else ""
    cap_line = f"capability: {capability}" if capability else ""
    cat_line = f"category: {category}" if category else ""
    input_block = input_text if input_text else (
        "TODO: describe the prompt input for this test."
    )
    lines = [
        f'# Test config — generated by `model_benchmark.cli new {name}`.',
        "# Fill in the TODOs and validate with: "
        "python -m model_benchmark.cli validate <this file>",
        "",
        'schema_version: "1.0.0"',
        "kind: test",
        "",
        f"id: {name}",
        f"name: {title or name}",
        'description: >',
        "  TODO: describe what this test verifies.",
        "",
    ]
    if cap_line:
        lines.append(cap_line)
    if cat_line:
        lines.append(cat_line)
    lines.append(f"difficulty: {difficulty}")
    if tags_line:
        lines.append(tags_line)
    lines.extend([
        "",
        "input: |",
    ])
    for ln in input_block.splitlines():
        lines.append(f"  {ln}" if ln else "")
    lines.extend([
        "",
        "expected:",
        "  answer_type: structured",
        "  behavior:",
        "    - \"TODO: describe expected behavior\"",
        "  contains:",
        '    - "PROSE:"',
        '    - "CHOICES:"',
        '    - "SUMMARY:"',
        "  must_parse_as: sugarcube_passage",
        "",
        "evaluation:",
        f"  name: {evaluator}",
        "  pass_threshold: 1.0",
        "  max_score: 1.0",
        "",
        "metadata:",
        "  owner: benchmark-team",
    ])
    return "\n".join(lines) + "\n"


def _prompt(msg: str, default: str = "") -> str:
    """Interactive prompt with a default; returns the trimmed input or default."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val or default


def _cmd_new(args: argparse.Namespace) -> int:
    """Create a new test YAML from a template, prompting for key fields."""
    name = args.name
    title = args.title
    capability = args.capability
    category = args.category
    difficulty = args.difficulty
    tags = list(args.tags)
    input_text = args.input
    evaluator = args.evaluator

    # Interactive prompting (only when stdin is a TTY and not --no-prompt).
    if not args.no_prompt and sys.stdin.isatty():
        if not title:
            title = _prompt("Test title", name.replace("_", " "))
        if not capability:
            capability = _prompt("Capability", "sugarcube_compliance")
        if not category:
            category = _prompt("Scoring category", "markup_compliance")
        if not input_text:
            input_text = _prompt("Prompt input (one line)", "")

    target_dir = Path(args.dir)
    # Normalize the filename: use the test name, ensure .yaml extension.
    safe = name.replace(" ", "_")
    if not safe.endswith((".yaml", ".yml")):
        safe = safe + ".yaml"
    target = target_dir / safe

    content = _test_template(
        name=name,
        title=title or name,
        capability=capability,
        category=category,
        difficulty=difficulty,
        tags=tags,
        input_text=input_text,
        evaluator=evaluator,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"Created test config: {target}")
    print(f"  Validate: python -m model_benchmark.cli validate {target}")
    return 0


# ── validate ────────────────────────────────────────────────────────────────


def _make_loader(config_dirs: Optional[Sequence[str]] = None) -> Any:
    """Build a ConfigLoader, optionally with extra search dirs."""
    from model_benchmark.config_loader import ConfigLoader
    loader = ConfigLoader()
    if config_dirs:
        for d in config_dirs:
            loader.add_directory(d)
    return loader


def _cmd_validate(args: argparse.Namespace) -> int:
    """Load and validate config file(s), reporting all errors."""
    from model_benchmark.config_loader import (
        ConfigLoader, load_file, ConfigError, ConfigErrorCollection,
    )

    path = getattr(args, "path", None)
    config_dirs = getattr(args, "config_dir", []) or []

    # Case 1: a specific file path is given.
    if path:
        p = Path(path)
        if p.is_file():
            errors: list = []
            try:
                load_file(p, errors)
            except ConfigErrorCollection as exc:
                errors.extend(exc.errors)
            if errors:
                print(f"INVALID — {len(errors)} error(s) in {p}:")
                for e in errors:
                    print(f"  {e}")
                return 1
            print(f"OK — {p} is valid.")
            return 0
        # It's a directory (or the default-search case below).
        config_dirs = list(config_dirs) + [path]

    # Case 2: directory / default discovery.
    loader = ConfigLoader()
    for d in config_dirs:
        loader.add_directory(d)
    loader.reload()
    errs = loader.errors()
    docs = loader.documents()

    if errs:
        print(f"INVALID — {len(errs)} error(s) across {len(config_dirs) or len(loader.search_dirs)} dir(s):")
        for e in errs:
            print(f"  {e}")
        return 1

    print(f"OK — {len(docs)} document(s) valid across "
          f"{len(config_dirs) or len(loader.search_dirs)} dir(s).")
    for d in docs:
        print(f"  {d.kind}: {d.id}  ({d.source_path})")
    return 0


# ── list ────────────────────────────────────────────────────────────────────


def _build_filters(args: argparse.Namespace):
    """Build a SelectionFilters from argparse args."""
    from model_benchmark.test_selection import SelectionFilters
    filters = SelectionFilters()
    for expr in getattr(args, "select", []) or []:
        filters.add_include(expr)
    for expr in getattr(args, "exclude", []) or []:
        filters.add_exclude(expr)
    if getattr(args, "max_selected", None) is not None:
        filters.max_selected = int(args.max_selected)
    if getattr(args, "include_disabled", False):
        filters.include_disabled = True
    return filters


def _resolved_specs(config_dirs: Sequence[str]) -> list:
    """Load + resolve all test specs from the config dirs (or defaults)."""
    from model_benchmark.config_loader import ConfigLoader
    loader = ConfigLoader()
    for d in config_dirs:
        loader.add_directory(d)
    loader.reload()
    return loader.resolve_all()


def _cmd_list(args: argparse.Namespace) -> int:
    """List discovered tests with selection filters."""
    from model_benchmark.test_selection import select_tests, dry_run

    config_dirs = getattr(args, "config_dir", []) or []
    fmt = getattr(args, "format", "table")

    all_specs = _resolved_specs(config_dirs)
    filters = _build_filters(args)
    selected = select_tests(all_specs, filters)

    if fmt == "ids":
        for s in selected:
            print(s.id)
        return 0

    if fmt == "json":
        rows = []
        for s in selected:
            rows.append({
                "id": s.id,
                "name": s.config.name or s.id,
                "suite": s.suite_name,
                "capability": s.config.capability or "",
                "category": s.config.category or "",
                "difficulty": s.config.difficulty or "",
                "tags": list(s.config.tags),
                "enabled": s.config.enabled if s.config.enabled is not None else True,
                "source_files": list(s.source_files),
            })
        print(json.dumps(rows, indent=2, default=str))
        return 0

    # table (default)
    print(f"Discovered: {len(all_specs)}  Selected: {len(selected)}")
    if not selected:
        print("  (no tests match the current filters)")
        return 0
    # Column widths.
    id_w = max(len(s.id) for s in selected)
    id_w = max(id_w, len("ID"))
    cat_w = max(len(s.config.category or "-") for s in selected)
    cat_w = max(cat_w, len("CATEGORY"))
    diff_w = max(len(s.config.difficulty or "-") for s in selected)
    diff_w = max(diff_w, len("DIFF"))
    hdr = f"  {'ID':<{id_w}}  {'CATEGORY':<{cat_w}}  {'DIFF':<{diff_w}}  ENABLED  SUITE"
    print(hdr)
    print(f"  {'-' * id_w}  {'-' * cat_w}  {'-' * diff_w}  -------  -----")
    for s in selected:
        enabled = "yes" if (s.config.enabled if s.config.enabled is not None else True) else "no"
        suite = s.suite_name or "-"
        cat = s.config.category or "-"
        diff = s.config.difficulty or "-"
        print(f"  {s.id:<{id_w}}  {cat:<{cat_w}}  {diff:<{diff_w}}  {enabled:<7}  {suite}")
    return 0


# ── run ────────────────────────────────────────────────────────────────────


def _cmd_run(args: argparse.Namespace) -> int:
    """Execute selected tests with dry-run, debug, and output-format flags."""
    from model_benchmark.test_selection import dry_run as ts_dry_run

    config_dirs = getattr(args, "config_dir", []) or []
    debug = getattr(args, "debug", False)
    quiet = getattr(args, "quiet", False)
    verbose = getattr(args, "verbose", False) or debug

    all_specs = _resolved_specs(config_dirs)
    filters = _build_filters(args)

    # ── Debug: show resolved config after merge + matrix expansion. ───────
    if debug:
        _debug_resolved_configs(all_specs, filters)

    # ── Plan-only: show selection + matrix expansion, no execution. ───────
    if getattr(args, "plan_only", False):
        result = ts_dry_run(all_specs, filters)
        print(result.format())
        return 0

    # ── Build a BenchmarkConfig and execute via the runner. ────────────────
    from model_benchmark.config import _build_parser as _bp
    # Reuse the legacy parser to coerce the model/run flags into BenchmarkConfig.
    legacy_parser = _bp()
    # Construct argv for parse_cli_args from the run subcommand's flags.
    legacy_argv = _run_args_to_legacy_argv(args)
    try:
        cfg = parse_cli_args(legacy_argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1

    from model_benchmark.runner import BenchmarkRunner
    runner = BenchmarkRunner(
        cfg,
        checkpoint_every=cfg.checkpoint_every,
        checkpoint_interval_seconds=cfg.checkpoint_interval_seconds,
        output_dir=cfg.output_dir,
        verbose=verbose,
        quiet=quiet,
        force_rerun=cfg.force_rerun,
    )

    if cfg.dry_run:
        # Fixture dry-run: produces scored records without calling Ollama.
        runner.dry_run()
        results = runner.execute()
    else:
        results = runner.execute()

    if debug:
        _debug_model_io(results)

    # ── Stats (when runs > 1) ────────────────────────────────────────────
    from collections import defaultdict
    stats_map: dict[str, Any] = {}
    if cfg.runs > 1:
        from model_benchmark.stats import compute_run_statistics
        grouped: dict[str, list[float]] = defaultdict(list)
        grouped_passed: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            tid = getattr(r, "test_id", "") or ""
            score = getattr(r, "normalized_score", getattr(r, "score", 0.0))
            passed = getattr(r, "status", "FAIL") == "PASS"
            grouped[tid].append(float(score))
            grouped_passed[tid].append(bool(passed))
        for tid, scores in grouped.items():
            stats_map[tid] = compute_run_statistics(tid, scores, grouped_passed[tid])

    # ── Baseline comparison ─────────────────────────────────────────────
    comparison = None
    regressions = None
    if cfg.baseline_dir:
        from model_benchmark.comparisons import (
            load_baseline, compare_runs, detect_regressions,
        )
        baseline = load_baseline(cfg.baseline_dir)
        if baseline:
            comparison = compare_runs(results, baseline)
            regressions = detect_regressions(comparison, results, baseline)

    # ── Manifest ─────────────────────────────────────────────────────────
    from model_benchmark.metadata import collect_reproducibility_metadata
    manifest = collect_reproducibility_metadata(
        cfg,
        run_id=getattr(runner, "run_id", None),
        repeated_runs_count=cfg.runs,
        random_seed=cfg.random_seed,
        argv=sys.argv[1:],
    )

    # ── Anonymization ───────────────────────────────────────────────────
    anon_results = results
    anon_manifest = manifest
    if cfg.anonymize:
        from model_benchmark.anonymization import (
            build_anonymization_mapping,
            anonymize_results,
            anonymize_metadata,
        )
        mapping = build_anonymization_mapping(results, manifest=manifest, config=cfg)
        anon_results = anonymize_results(results, mapping)
        anon_manifest = anonymize_metadata(manifest, mapping)

    # ── Reports ─────────────────────────────────────────────────────────
    from model_benchmark.reports import (
        generate_text_report, generate_markdown_report,
    )
    from model_benchmark.html_report import generate_html_report

    stats_list = list(stats_map.values()) if stats_map else None

    md_report = generate_markdown_report(
        anon_results,
        manifest=anon_manifest,
        stats=stats_list[0] if stats_list else None,
        comparison=comparison,
        regressions=regressions,
    )
    html_report = generate_html_report(
        anon_results,
        anon_manifest,
        anonymized=cfg.anonymize,
        stats=stats_list[0] if stats_list else None,
        comparison=comparison,
        regressions=regressions,
    )

    # ── Output to stdout (respects --output-format) ─────────────────────
    fmt = getattr(args, "output_format", "text")
    if fmt == "json":
        rows = []
        for r in anon_results:
            rows.append({
                "test_id": getattr(r, "test_id", ""),
                "status": getattr(r, "status", ""),
                "score": getattr(r, "normalized_score", getattr(r, "score", 0.0)),
                "category": getattr(r, "category", ""),
                "error_details": getattr(r, "error_details", ""),
            })
        print(json.dumps(rows, indent=2, default=str))
    elif fmt == "markdown":
        print(md_report)
    else:
        text_report = generate_text_report(
            anon_results,
            manifest=anon_manifest,
            stats=stats_list[0] if stats_list else None,
            comparison=comparison,
            regressions=regressions,
        )
        print(text_report)

    # ── Persist outputs (full pipeline, same as legacy mode) ─────────────
    try:
        from model_benchmark.persistence import (
            create_run_dir, write_json, write_jsonl, write_manifest,
        )
        run_dir = create_run_dir(cfg.output_dir, run_id=getattr(runner, "run_id", None))
        write_jsonl(run_dir / "results_internal.jsonl", results)
        if cfg.anonymize:
            write_json(run_dir / "results_anonymized.json", anon_results)
        write_manifest(run_dir / "run_manifest.json", anon_manifest)
        (run_dir / "summary_internal.md").write_text(md_report, encoding="utf-8")
        (run_dir / "report_internal.html").write_text(html_report, encoding="utf-8")
        if not quiet:
            sys.stderr.write(f"[output] results written to {run_dir}\n")
    except Exception as exc:  # pragma: no cover — persistence is best-effort.
        if not quiet:
            sys.stderr.write(f"[warn] could not persist results: {exc}\n")

    return 0


def _run_args_to_legacy_argv(args: argparse.Namespace) -> list[str]:
    """Translate the `run` subcommand flags into the legacy flat-flag argv format."""
    out: list[str] = []
    if getattr(args, "dry_run", False):
        out.append("--dry-run")
    if getattr(args, "quiet", False):
        out.append("--quiet")
    if getattr(args, "verbose", False) or getattr(args, "debug", False):
        out.append("--verbose")
    if not getattr(args, "anonymize", True):
        out.append("--no-anonymize")
    if getattr(args, "force_rerun", False):
        out.append("--force-rerun")
    baseline = getattr(args, "baseline", "") or ""
    if baseline:
        out += ["--baseline", baseline]
    seed = getattr(args, "seed", "") or ""
    if seed:
        out += ["--seed", seed]
    models = getattr(args, "models", []) or []
    if models:
        out += ["--models", *models]
    variants = getattr(args, "variants", []) or []
    if variants:
        out += ["--variants", *variants]
    directions = getattr(args, "directions", []) or []
    if directions:
        out += ["--directions", *directions]
    runs = getattr(args, "runs", 1)
    if runs != 1:
        out += ["--runs", str(runs)]
    base_url = getattr(args, "base_url", "") or ""
    if base_url:
        out += ["--base-url", base_url]
    timeout = getattr(args, "timeout", None)
    if timeout is not None:
        out += ["--timeout", str(timeout)]
    num_predict = getattr(args, "num_predict", None)
    if num_predict is not None:
        out += ["--num-predict", str(num_predict)]
    temperature = getattr(args, "temperature", None)
    if temperature is not None:
        out += ["--temperature", str(temperature)]
    out += ["--output-dir", getattr(args, "output_dir", "benchmark_outputs")]
    return out


def _debug_resolved_configs(all_specs: list, filters: Any) -> None:
    """Print resolved config after merge + matrix expansion (debug mode)."""
    from model_benchmark.test_selection import select_tests, expand_matrix

    print("=" * 72)
    print("DEBUG — Resolved Config After Merge")
    print("=" * 72)
    selected = select_tests(all_specs, filters)
    for s in selected:
        print(f"\n── {s.id} ──")
        print(f"  suite: {s.suite_name or '(standalone)'}")
        print(f"  source_files: {list(s.source_files)}")
        cfg = s.config
        print(f"  name: {cfg.name or '(none)'}")
        print(f"  capability: {cfg.capability or '(none)'}")
        print(f"  category: {cfg.category or '(none)'}")
        print(f"  difficulty: {cfg.difficulty or '(none)'}")
        print(f"  tags: {list(cfg.tags)}")
        print(f"  enabled: {cfg.enabled if cfg.enabled is not None else True}")
        print(f"  repetitions: {cfg.repetitions or 1}")
        if cfg.model_parameters:
            mp = cfg.model_parameters
            print(
                f"  model_parameters: base_url={mp.base_url} "
                f"timeout={mp.timeout} num_predict={mp.num_predict} "
                f"temperature={mp.temperature}"
            )
        if cfg.evaluation:
            print(
                f"  evaluation: name={cfg.evaluation.name} "
                f"pass_threshold={cfg.evaluation.pass_threshold}"
            )
        if cfg.parameters:
            print(f"  parameters (matrix dims): {list(cfg.parameters.keys())}")
        if cfg.matrix:
            print(
                f"  matrix: strategy={cfg.matrix.strategy} "
                f"max_cases={cfg.matrix.max_cases}"
            )
        # Matrix expansion.
        exp = expand_matrix(s)
        if exp.strategy != "none":
            print(f"  matrix expansion: {exp.num_instances} instance(s) "
                  f"(full product={exp.full_product_size}, "
                  f"truncated={exp.truncated})")
            for inst in exp.instances[:8]:
                params = ", ".join(f"{k}={v}" for k, v in inst.parameters.items())
                print(f"    → {inst.instance_id}  ({params})")
            if len(exp.instances) > 8:
                print(f"    ... and {len(exp.instances) - 8} more")
        else:
            print(f"  matrix expansion: (no matrix — 1 instance: {s.id})")
    print()
    print(f"Total: {len(selected)} test(s) selected of {len(all_specs)} discovered.")
    print("=" * 72)


def _debug_model_io(results: list) -> None:
    """Print full model I/O for each test (debug mode)."""
    print("\n" + "=" * 72)
    print("DEBUG — Model I/O Capture")
    print("=" * 72)
    for r in results:
        tid = getattr(r, "test_id", "")
        status = getattr(r, "status", "")
        score = getattr(r, "normalized_score", getattr(r, "score", 0.0))
        print(f"\n── {tid} ──")
        print(f"  status: {status}  score: {score:.4f}")
        raw = getattr(r, "actual_output_raw", "")
        if raw:
            preview = raw if len(raw) <= 500 else raw[:500] + f"\n... ({len(raw) - 500} more chars)"
            print("  model output (raw):")
            for line in preview.splitlines():
                print(f"    {line}")
        scored = getattr(r, "scored_result", None)
        if scored is not None:
            parsed = getattr(scored, "parsed_output", None)
            if parsed is not None:
                prose = getattr(parsed, "prose", "")
                if prose:
                    preview = prose if len(prose) <= 300 else prose[:300] + "..."
                    print("  parsed prose:")
                    for line in preview.splitlines():
                        print(f"    {line}")
                cats = getattr(scored, "category_results", ())
                if cats:
                    print("  category results:")
                    for c in cats:
                        name = getattr(c, "name", str(c))
                        passed = getattr(c, "passed", "?")
                        print(f"    {name}: {'PASS' if passed else 'FAIL'}")
        err = getattr(r, "error_details", "")
        if err:
            print(f"  error: {err}")
    print("=" * 72)


# ── models ──────────────────────────────────────────────────────────────────

def _cmd_models(args: argparse.Namespace) -> int:
    """List models discovered from the Ollama server.  No benchmark run."""
    from model_benchmark.benchmark import discover_models

    base_url = getattr(args, "base_url", "http://localhost:11434")
    models = discover_models(base_url)

    if not models:
        print(f"No models found at {base_url}.  Is Ollama running?", file=sys.stderr)
        return 1

    print(f"Discovered {len(models)} model(s) from {base_url}:")
    for m in models:
        print(f"  {m}")
    return 0


# ── `python -m model_benchmark.cli` entry ──────────────────────────────────


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
