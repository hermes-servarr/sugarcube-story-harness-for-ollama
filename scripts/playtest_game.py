"""CLI entry point for the HTML game playtester.

Importable so other scripts/tests can call parse_args() and main() directly.
"""
from __future__ import annotations

import argparse
import sys

from harness.playtest.models import PlaytestConfig
from harness.playtest.runner import run_playtest


def parse_args(argv: list[str] | None = None) -> PlaytestConfig:
    """Parse command-line arguments into a PlaytestConfig."""
    parser = argparse.ArgumentParser(
        prog="playtest_game",
        description="Automated playtester for compiled SugarCube HTML games.",
    )
    parser.add_argument(
        "project_path",
        help="Path to the story project root",
    )
    parser.add_argument(
        "--html",
        default="",
        help="Explicit path to story.html (default: <project>/build/story.html)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Max BFS exploration depth (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Seconds to wait for page load per step (default: 30)",
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        default=False,
        help="Skip taking screenshots",
    )
    parser.add_argument(
        "--no-kanban",
        action="store_true",
        default=False,
        help="Skip creating kanban tasks for issues",
    )
    parser.add_argument(
        "--output-dir",
        default="playtest_results",
        help="Where to write results (default: playtest_results/)",
    )
    args = parser.parse_args(argv)
    return PlaytestConfig(
        project_path=args.project_path,
        html_path=args.html,
        max_depth=args.max_depth,
        timeout=args.timeout,
        no_screenshots=args.no_screenshots,
        no_kanban=args.no_kanban,
        output_dir=args.output_dir,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, run playtest, print summary, return exit code."""
    try:
        config = parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1

    try:
        report = run_playtest(config)
    except Exception as e:
        print(f"Playtest failed: {e}", file=sys.stderr)
        return 1

    if not report.sugarcube_loaded:
        print(
            "Error: SugarCube engine not detected. The HTML file may not be a "
            "compiled SugarCube game, or it failed to load.",
            file=sys.stderr,
        )
        return 1

    print(f"Playtest complete:")
    print(f"  Story HTML: {report.story_html_path}")
    print(f"  Steps: {report.total_steps}")
    print(f"  Passages visited: {report.total_passages_visited}")
    print(f"  Issues found: {len(report.issues)}")
    blockers = [i for i in report.issues if i.severity.value == "blocker"]
    majors = [i for i in report.issues if i.severity.value == "major"]
    minors = [i for i in report.issues if i.severity.value == "minor"]
    if blockers:
        print(f"    Blockers: {len(blockers)}")
    if majors:
        print(f"    Major: {len(majors)}")
    if minors:
        print(f"    Minor: {len(minors)}")
    print(f"  Output: {config.output_dir}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
