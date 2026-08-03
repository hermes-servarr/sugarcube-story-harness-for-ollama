"""CLI configuration for the model benchmark.

This module is the home of the extended :class:`BenchmarkConfig` and the
:func:`parse_cli_args` interface.

The extended ``BenchmarkConfig`` is the
canonical run configuration type.  The original 11-field ``BenchmarkConfig``
that lives in ``scoring.py`` is replaced by a re-export from this module, and
the ``benchmark.py`` compatibility shim re-exports from here (P2 §5 migration
plan).  All 9 new fields are defaulted so existing code constructing the
config with only the original 11 fields continues to work.

Phase 7 — production implementation conforming to P2, P3 (the
``parse_cli_args`` signature), and P6 invariants (INV-CFG1..INV-CFG7).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields, MISSING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These are Literal["compact","full","json"] / Literal["A","B","C"] in
    # scoring.py / benchmark.py. We keep annotations as strings (PEP 563).
    from model_benchmark.scoring import PromptVariant, DirectionKey


@dataclass(frozen=True)
class BenchmarkConfig:
    """Run configuration — one CLI invocation's parameters.

    Extends the original BenchmarkConfig with operational fields for
    checkpoint cadence, output directory, verbosity, anonymization,
    baseline comparison, random seed, and force-rerun control. All new fields
    are defaulted for backward compatibility.
    """

    # ── Original fields (preserved verbatim from scoring.py L201) ───────────
    models: tuple[str, ...]
    variants: tuple[PromptVariant, ...]
    directions: tuple[DirectionKey, ...]
    base_url: str
    timeout: int
    num_predict: int
    temperature: float
    runs: int
    dry_run: bool = False
    output_path: str = ""
    json_output_path: str = ""

    # ── Operational fields, all defaulted for backward compatibility ───────
    checkpoint_every: int = 10
    """Persist a checkpoint after this many completed cases (default 10)."""

    checkpoint_interval_seconds: float = 60.0
    """Also persist a checkpoint after this many seconds since the last (default 60.0)."""

    output_dir: str = "benchmark_outputs"
    """Directory for checkpoint files and run outputs (default "benchmark_outputs")."""

    verbose: bool = False
    """Emit detailed per-case progress lines to stderr."""

    quiet: bool = False
    """Suppress all progress output (errors still print to stderr)."""

    anonymize: bool = True
    """Anonymize model/provider/config names in output reports (default True)."""

    baseline_dir: str = ""
    """Path to a previous run's output directory for baseline comparison (empty = no comparison)."""

    random_seed: str = ""
    """Explicit random seed for reproducibility (empty = random)."""

    force_rerun: bool = False
    """Ignore any existing checkpoint and recompute every case."""

    ingestion_routing_path: str = ""
    """PC-private model-to-profile routing JSON (empty = legacy behavior)."""

    benchmark_profile: str = ""
    """Named built-in workload profile; empty keeps custom matrix flags."""


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for legacy and operational run flags."""
    parser = argparse.ArgumentParser(
        description="SugarCube Direction-Following Benchmark",
    )
    # ── Legacy flags (11, preserved from scoring.py main() L873) ────────────
    parser.add_argument("--models", nargs="*", default=[],
                        help="Model tags to test (empty=auto-discover)")
    parser.add_argument("--variants", nargs="*", choices=["compact", "full", "json", "thinking"],
                        default=["compact", "full", "json"], help="Prompt variants")
    parser.add_argument("--directions", nargs="*", choices=["A", "B", "C", "D", "E", "F", "G", "H"],
 default=["A", "B", "C"], help="Directions")
    parser.add_argument("--base-url", default="http://localhost:11434",
                        help="Ollama base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per call")
    parser.add_argument("--num-predict", type=int, default=640, help="Max tokens")
    parser.add_argument("--temperature", type=float, default=0.2,
                        help="Sampling temperature")
    parser.add_argument("--runs", type=int, default=1,
                        help="N runs per model×variant×direction")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score a fixture, skip Ollama (CI)")
    parser.add_argument("--output", default="", help="Text report file (empty=stdout)")
    parser.add_argument("--json-output", default="", help="JSON report file (empty=none)")

    # ── New flags (9, per P3 §1.2) ──────────────────────────────────────────
    parser.add_argument("--checkpoint-every", type=int, default=10,
                        help="Checkpoint after N completed cases")
    parser.add_argument("--checkpoint-interval", type=float, default=60.0,
                        help="Also checkpoint after N seconds since last")
    parser.add_argument("--output-dir", default="benchmark_outputs",
                        help="Directory for checkpoint files and run outputs")
    parser.add_argument("--verbose", action="store_true",
                        help="Emit detailed per-case progress to stderr")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress all progress output")
    parser.add_argument("--anonymize", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Anonymize model/provider/config names (default True)")
    parser.add_argument("--baseline", default="",
                        help="Path to a previous run dir for baseline comparison")
    parser.add_argument("--seed", default="",
                        help="Explicit random seed for reproducibility")
    parser.add_argument("--force-rerun", action="store_true",
                        help="Ignore existing checkpoint and recompute every case")
    parser.add_argument("--ingestion-routing", default="",
                        help=argparse.SUPPRESS)
    parser.add_argument("--profile", choices=["canary", "core", "full"], default="",
                        help="Named workload profile (default: custom flags)")

    return parser


def parse_cli_args(argv: list[str] | None = None) -> BenchmarkConfig:
    """Parse CLI arguments into an extended BenchmarkConfig."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.profile:
        from model_benchmark.profiles import ALL_DIRECTIONS, ALL_VARIANTS

        variants = ALL_VARIANTS
        directions = ALL_DIRECTIONS
    else:
        variants = tuple(args.variants)
        directions = tuple(args.directions)

    return BenchmarkConfig(
        models=tuple(args.models),
        variants=variants,
        directions=directions,
        base_url=args.base_url,
        timeout=args.timeout,
        num_predict=args.num_predict,
        temperature=args.temperature,
        runs=args.runs,
        dry_run=args.dry_run,
        output_path=args.output,
        json_output_path=args.json_output,
        checkpoint_every=args.checkpoint_every,
        checkpoint_interval_seconds=args.checkpoint_interval,
        output_dir=args.output_dir,
        verbose=args.verbose,
        quiet=args.quiet,
        anonymize=args.anonymize,
        baseline_dir=args.baseline,
        random_seed=args.seed,
        force_rerun=args.force_rerun,
        ingestion_routing_path=args.ingestion_routing,
        benchmark_profile=args.profile,
    )
