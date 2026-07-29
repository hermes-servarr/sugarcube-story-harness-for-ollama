#!/usr/bin/env python3
"""LLM Model Benchmark for SugarCube Direction-Following.

Production implementation (Phase 7) of a benchmark suite that sends controlled
prompts (built from the real ``harness/prompts.py`` templates with fixed context)
to one or more Ollama models via the existing client, scores each response across
6 SugarCube compliance categories, and emits a per-model scored report.

Conforms to:
- P1 Research (t_c57b62b3c1) — problem statement, approach, file research.
- P2 Data Structures (t_025345d6ba) — 3 Literal aliases + 6 frozen dataclasses.
- P3 Interfaces (t_7e69519738) — 15 function signatures (name, params, return).
- P4 Code TODOs (t_c4e0b9f51f) — TODO(benchmark) markers at all modification sites.
- P5 Mock & Validate (t_b9a51a7238) — provisional implementation validated with
  43 unit tests; deviation report documents 2 logic adaptations carried here.
- P6 Invariants (t_a1fabd0986) — 10 declarative invariants, enforced below.

Invariant conformance (INV-1..INV-10 from p6_invariants.md):
- INV-1 (raw response, no auto-repair): run_single_model calls call_ollama_sync +
  parse_model_output[_json] directly; generate_story_output is never imported.
- INV-2 (scoring purity): the 6 scorers take only (str)/(str, ModelOutput) and
  return CategoryResult; no I/O imports appear in their bodies.
- INV-3 (real prompt templates): build_fixture_prompt imports and calls the real
  build_*_passage_prompt functions from harness.prompts; no inline prompt text.
- INV-4 (PROMPT_VERSION traceability): build_benchmark_report populates
  BenchmarkReport.prompt_version from the live harness.prompts.PROMPT_VERSION.
- INV-5 (no harness modification): this file only imports from harness.*; the
  final git diff lists only scripts/benchmark.py and tests/test_benchmark.py.
- INV-6 (graceful failure): every scorer has an empty-input early-return guard;
  run_single_model wraps call+parse+score in try/except returning failing results.
- INV-7 (choice text+hint scanning): score_passage_structure and
  score_link_setter_syntax scan combined "{text} | {hint}" per ParsedChoice.
- INV-8 (dry-run self-consistency): _DRY_RUN_RESPONSE is a known-good SugarCube
  passage; main(["--dry-run"]) scores it and all 6 categories pass.
- INV-9 (category count + order): score_response returns exactly 6 CategoryResult
  in the canonical order: markup_compliance, variable_scoping, passage_structure,
  macro_usage, naked_interpolation, link_setter_syntax.
- INV-10 (score range): each scorer computes score = passed_checks / sub_checks
  with 0 <= passed_checks <= sub_checks and sub_checks > 0, guaranteeing [0.0, 1.0].

P5 deviation report adaptations carried into production (no P2/P3 changes):
- DEV-P3-1 / DEV-P3-2: choice link/macro scanning uses combined text+hint fields
  (parser splits [[Text|Target]] across choice.text and choice.hint).
- DEV-P3-3: setup. in-prose detection strips macro blocks first (Python's re lacks
  variable-width lookbehind), then scans non-macro text.
- DEV-P5-1: _SET_EQ_RE matches "<<set $var = value>>" (not only bare "<<set $x=>>").
- DEV-P5-2 (P5 rework): naked-interpolation positive check passes if naked vars
  OR complex prints exist (both are valid SugarCube interpolation patterns).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

# P4 import sites — activated from TODO comments (P5/P7 implementation)
from harness.models import HarnessConfig, ModelOutput
from harness.ollama_client import call_ollama_sync, model_profile
from harness.parsers import (
    REQUIRED_SECTIONS,
    needs_repair,
    parse_model_output,
    parse_model_output_json,
    structured_score,
)
from harness.passage import extract_links, scan_state_reads, scan_state_writes
from harness.validation import MACRO_CONTAINERS, _iter_macro_tags
from harness.prompts import (
    PROMPT_VERSION,
    build_compact_passage_prompt,
    build_full_passage_prompt,
    build_json_passage_prompt,
)


# ── P2 Data Structures ───────────────────────────────────────────────────

PromptVariant = Literal["compact", "full", "json"]

DirectionKey = Literal["A", "B", "C"]

CategoryName = Literal[
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
]

# Canonical category order (INV-9). Used by score_response, build_model_report,
# and run_single_model's failing-result construction.
_CATEGORY_ORDER: tuple[CategoryName, ...] = (
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
)


@dataclass(frozen=True)
class CategoryResult:
    """One scoring category's verdict for a single model response — 6 per run."""
    name: CategoryName
    passed: bool
    score: float
    details: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelRunResult:
    """One model × one variant × one direction × one run index — a single Ollama call."""
    model_name: str
    variant: PromptVariant
    direction: DirectionKey
    run_index: int
    raw_response: str
    parsed_output: ModelOutput
    category_results: tuple[CategoryResult, ...]
    overall_pass: bool
    elapsed_seconds: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class CategorySummaryEntry:
    """Per-category aggregate for one model — one row of the report's category table."""
    name: CategoryName
    pass_rate: float
    total: int
    passed: int


@dataclass(frozen=True)
class ModelReport:
    """Aggregated results for one model across all variants/directions/runs."""
    model_name: str
    runs: tuple[ModelRunResult, ...]
    category_summary: tuple[CategorySummaryEntry, ...]
    overall_score: float
    runs_total: int
    runs_passed: int


@dataclass(frozen=True)
class BenchmarkConfig:
    """Run configuration — one CLI invocation's parameters."""
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


@dataclass(frozen=True)
class BenchmarkReport:
    """Top-level benchmark report — the full deliverable of one benchmark run."""
    models: tuple[ModelReport, ...]
    prompt_version: int
    config: BenchmarkConfig
    generated_at: str
    ollama_reachable: bool = True


# ── P3 Scoring Functions ────────────────────────────────────────────────

# Regex patterns for Category 1: Markup compliance
_MARKDOWN_BOLD_RE = re.compile(r'\*\*[^*]+\*\*')
_MARKDOWN_ITALIC_RE = re.compile(r'(?<!\*)\*[^*]+\*(?!\*)')
_SUGARCUBE_BOLD_RE = re.compile(r"''[^']{1,}''")
_SUGARCUBE_ITALIC_RE = re.compile(r'//[^/]{1,}//')
_SUGARCUBE_STRIKE_RE = re.compile(r'~~[^~]{1,}~~')
_SUGARCUBE_HIGHLIGHT_RE = re.compile(r'""[^"]{1,}""')

# Regex patterns for Category 2 + 4: Variable scoping / Macro usage
# DEV-P5-1: matches "<<set $var = value>>" (equals sign followed by whitespace).
_SET_EQ_RE = re.compile(r'<<set\s+\$\w+\s*=\s')
_SET_TO_RE = re.compile(r'<<set\s+\$\w+\s+to\s+')
_SETUP_PROSE_RE = re.compile(r'setup\.\w+')


def score_markup_compliance(text: str) -> CategoryResult:
    """Score Category 1: SugarCube markup ('' // ~~ \"\") present, markdown ** * absent."""
    # INV-6: graceful failure on empty/malformed input.
    if not text or not text.strip():
        return CategoryResult(
            name="markup_compliance",
            passed=False,
            score=0.0,
            details="Empty text — no markup to evaluate.",
        )

    md_bold = _MARKDOWN_BOLD_RE.findall(text)
    md_italic = _MARKDOWN_ITALIC_RE.findall(text)
    sc_bold = _SUGARCUBE_BOLD_RE.findall(text)
    sc_italic = _SUGARCUBE_ITALIC_RE.findall(text)
    sc_strike = _SUGARCUBE_STRIKE_RE.findall(text)
    sc_highlight = _SUGARCUBE_HIGHLIGHT_RE.findall(text)

    markdown_count = len(md_bold) + len(md_italic)
    sugarcube_count = len(sc_bold) + len(sc_italic) + len(sc_strike) + len(sc_highlight)

    # Sub-checks (INV-10): 2 checks, each binary.
    # 0 = no markdown found; 1 = at least one SugarCube markup found.
    sub_checks = 2
    passed_checks = 0
    if markdown_count == 0:
        passed_checks += 1
    if sugarcube_count > 0:
        passed_checks += 1

    passed = markdown_count == 0  # pass if no markdown present
    score = passed_checks / sub_checks  # INV-10: 0.0 <= score <= 1.0

    evidence: list[str] = []
    if md_bold:
        evidence.extend(md_bold[:3])
    if md_italic:
        evidence.extend(md_italic[:3])
    if sc_bold:
        evidence.extend(sc_bold[:3])

    details = (
        f"Markdown: bold={len(md_bold)}, italic={len(md_italic)}; "
        f"SugarCube: bold={len(sc_bold)}, italic={len(sc_italic)}, "
        f"strike={len(sc_strike)}, highlight={len(sc_highlight)}"
    )

    return CategoryResult(
        name="markup_compliance",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_variable_scoping(text: str) -> CategoryResult:
    """Score Category 2: $ persistent vs _ temp vs setup.x, <<set>> uses 'to' operator."""
    # INV-6: graceful failure on empty/malformed input.
    if not text or not text.strip():
        return CategoryResult(
            name="variable_scoping",
            passed=False,
            score=0.0,
            details="Empty text — no variables to evaluate.",
        )

    set_eq = _SET_EQ_RE.findall(text)
    set_to = _SET_TO_RE.findall(text)

    # DEV-P3-3: strip macro blocks first, then scan non-macro text for setup.
    # (Python's re lacks variable-width lookbehind; strip-then-scan is equivalent.)
    non_macro_text = re.split(r'<<[^>]+>>', text)
    setup_in_prose: list[str] = []
    for chunk in non_macro_text:
        found = _SETUP_PROSE_RE.findall(chunk)
        setup_in_prose.extend(found)

    reads = scan_state_reads(text)
    writes = scan_state_writes(text)

    # Sub-checks (INV-10): 3 checks.
    # 0 = uses 'to' operator; 1 = no '=' in set; 2 = no setup. in prose.
    sub_checks = 3
    passed_checks = 0
    if set_to:
        passed_checks += 1
    if not set_eq:
        passed_checks += 1
    if not setup_in_prose:
        passed_checks += 1

    passed = len(set_eq) == 0 and len(setup_in_prose) == 0
    score = passed_checks / sub_checks

    evidence: list[str] = []
    if set_eq:
        evidence.extend(set_eq[:3])
    if setup_in_prose:
        evidence.extend(setup_in_prose[:3])

    details = (
        f"<<set>>: to={len(set_to)}, eq={len(set_eq)}; "
        f"setup.in_prose={len(setup_in_prose)}; "
        f"reads={len(reads)}, writes={len(writes)}"
    )

    return CategoryResult(
        name="variable_scoping",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_passage_structure(raw: str, parsed: ModelOutput) -> CategoryResult:
    """Score Category 3: PROSE/CHOICES/SUMMARY present, no raw links/macros in choices, parse_warnings clean."""
    # INV-6: graceful failure on empty/malformed input.
    if not raw or not raw.strip():
        return CategoryResult(
            name="passage_structure",
            passed=False,
            score=0.0,
            details="Empty raw response.",
        )

    # Check REQUIRED_SECTIONS present (handles both delimited and JSON modes).
    sections_found: set[str] = set()
    for section in REQUIRED_SECTIONS:
        if re.search(rf'^{section}\s*:', raw, re.MULTILINE) or f'"{section.lower()}"' in raw.lower():
            sections_found.add(section)
    missing_sections = REQUIRED_SECTIONS - sections_found

    # Check parse_warnings.
    warnings = parsed.parse_warnings if hasattr(parsed, 'parse_warnings') else []

    # INV-7 / DEV-P3-1: scan combined text+hint for [[link]] and <<macro>> in choices.
    link_in_choices: list[str] = []
    macro_in_choices: list[str] = []
    for ch in parsed.choices:
        combined = f"{ch.text} | {ch.hint}" if ch.hint else ch.text
        links = re.findall(r'\[\[[^\]]*\]\]', combined)
        macros = re.findall(r'<<[^>]*>>', combined)
        link_in_choices.extend(links)
        macro_in_choices.extend(macros)

    # Sub-checks (INV-10): 4 checks.
    # 0 = all sections present; 1 = no parse_warnings; 2 = no links in choices;
    # 3 = no macros in choices.
    sub_checks = 4
    passed_checks = 0
    if not missing_sections:
        passed_checks += 1
    if not warnings:
        passed_checks += 1
    if not link_in_choices:
        passed_checks += 1
    if not macro_in_choices:
        passed_checks += 1

    passed = (
        not missing_sections
        and not warnings
        and not link_in_choices
        and not macro_in_choices
    )
    score = passed_checks / sub_checks

    evidence: list[str] = []
    if missing_sections:
        evidence.extend(list(missing_sections))
    if link_in_choices:
        evidence.extend(link_in_choices[:3])
    if macro_in_choices:
        evidence.extend(macro_in_choices[:3])

    details = (
        f"Sections missing={sorted(missing_sections) if missing_sections else 'none'}; "
        f"warnings={len(warnings)}; "
        f"links_in_choices={len(link_in_choices)}; "
        f"macros_in_choices={len(macro_in_choices)}"
    )

    return CategoryResult(
        name="passage_structure",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_macro_usage(text: str) -> CategoryResult:
    """Score Category 4: <<set>>/<<if>>/<<print>> correct, container macro nesting balanced."""
    # INV-6: graceful failure on empty/malformed input.
    if not text or not text.strip():
        return CategoryResult(
            name="macro_usage",
            passed=False,
            score=0.0,
            details="Empty text — no macros to evaluate.",
        )

    # Use _iter_macro_tags to scan macros (text-based, directly reusable per P1 §3.5).
    tags = list(_iter_macro_tags(text))

    # Check <<set>> uses 'to' operator (not '='). DEV-P5-1 regex.
    set_eq = _SET_EQ_RE.findall(text)
    set_to = _SET_TO_RE.findall(text)

    # Check container macro nesting balance (text-only adaptation of
    # check_macro_pairing logic per P1 §3.5 — operates on raw text, not
    # ProjectPaths+StoryGraph).
    stack: list[str] = []
    nesting_errors: list[str] = []
    for is_close, name, line in tags:
        if is_close:
            if not stack:
                nesting_errors.append(f"stray <</{name}>> at line {line}")
            elif stack[-1] != name:
                nesting_errors.append(
                    f"wrong nesting: <</{name}>> closes <{stack[-1]}>> at line {line}"
                )
                stack.pop()
            else:
                stack.pop()
        else:
            if name in MACRO_CONTAINERS:
                stack.append(name)

    if stack:
        nesting_errors.append(f"unclosed: {', '.join(stack)}")

    # Sub-checks (INV-10): 3 checks.
    # 0 = uses 'to' operator; 1 = no '=' in set; 2 = balanced nesting.
    sub_checks = 3
    passed_checks = 0
    if set_to:
        passed_checks += 1
    if not set_eq:
        passed_checks += 1
    if not nesting_errors:
        passed_checks += 1

    passed = not set_eq and not nesting_errors
    score = passed_checks / sub_checks

    evidence: list[str] = []
    if set_eq:
        evidence.extend(set_eq[:3])
    if nesting_errors:
        evidence.extend(nesting_errors[:3])

    details = (
        f"<<set>>: to={len(set_to)}, eq={len(set_eq)}; "
        f"tags={len(tags)}; nesting_errors={len(nesting_errors)}"
    )

    return CategoryResult(
        name="macro_usage",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_naked_interpolation(prose: str) -> CategoryResult:
    """Score Category 5: simple $var naked in prose, <<print>> only for complex expressions."""
    # INV-6: graceful failure on empty/malformed input.
    if not prose or not prose.strip():
        return CategoryResult(
            name="naked_interpolation",
            passed=False,
            score=0.0,
            details="Empty prose — no interpolation to evaluate.",
        )

    # Find naked $var in non-macro text (split out <<...>> blocks first).
    non_macro_text = re.split(r'<<[^>]*>>', prose)
    non_macro_joined = ' '.join(non_macro_text)
    naked_vars = re.findall(r'\$([a-zA-Z_]\w*)', non_macro_joined)

    # Find <<print>> expressions.
    print_exprs = re.findall(r'<<print\s+([^>]+)>>', prose)

    # Classify <<print>> expressions: simple ($var only) vs complex (dot/bracket/method).
    simple_prints: list[str] = []
    complex_prints: list[str] = []
    for expr in print_exprs:
        expr_stripped = expr.strip()
        # Simple if it's just $var with no dot/bracket/method.
        if re.match(r'^\$\w+$', expr_stripped):
            simple_prints.append(expr_stripped)
        else:
            complex_prints.append(expr_stripped)

    # Sub-checks (INV-10): 2 checks. DEV-P5-2 (P5 rework):
    # 0 = no simple vars wasted in <<print>> (bad practice);
    # 1 = naked vars present OR complex prints present (correct usage — either
    #    form of valid variable access satisfies the positive check).
    sub_checks = 2
    passed_checks = 0
    if not simple_prints:
        passed_checks += 1
    if naked_vars or complex_prints:
        passed_checks += 1

    passed = not simple_prints  # pass if no simple vars wasted in <<print>>
    score = passed_checks / sub_checks

    evidence: list[str] = []
    if simple_prints:
        evidence.extend(simple_prints[:3])
    if naked_vars:
        evidence.extend([f"${v}" for v in naked_vars[:3]])

    details = (
        f"naked_vars={len(naked_vars)}; "
        f"<<print>>: simple={len(simple_prints)}, complex={len(complex_prints)}"
    )

    return CategoryResult(
        name="naked_interpolation",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_link_setter_syntax(raw: str, parsed: ModelOutput) -> CategoryResult:
    """Score Category 6: [[Text|Target]] / [[Target][Setter]] valid, no [[link]] in choices."""
    # INV-6: graceful failure on empty/malformed input.
    if not raw or not raw.strip():
        return CategoryResult(
            name="link_setter_syntax",
            passed=False,
            score=0.0,
            details="Empty raw response.",
        )

    # Extract all links from raw text using the reusable harness function.
    all_links = extract_links(raw)

    # Validate link syntax: [[Text|Target]], [[Target]], or [[Target][Setter]].
    valid_link_re = re.compile(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]')
    valid_links = valid_link_re.findall(raw)
    invalid_links = [l for l in all_links if l not in valid_links]

    # INV-7 / DEV-P3-2: scan combined text+hint for [[link]] in choices (negative).
    # Per SUGARCUBE_GUIDANCE L33-35, the model should NOT emit [[link]] in CHOICES
    # — the harness renders them.
    links_in_choices: list[str] = []
    for ch in parsed.choices:
        combined = f"{ch.text} | {ch.hint}" if ch.hint else ch.text
        choice_links = re.findall(r'\[\[[^\]]*\]\]', combined)
        links_in_choices.extend(choice_links)

    # Sub-checks (INV-10): 2 checks.
    # 0 = valid link syntax; 1 = no links in choices.
    sub_checks = 2
    passed_checks = 0
    if not invalid_links:
        passed_checks += 1
    if not links_in_choices:
        passed_checks += 1

    passed = not invalid_links and not links_in_choices
    score = passed_checks / sub_checks

    evidence: list[str] = []
    if invalid_links:
        evidence.extend(invalid_links[:3])
    if links_in_choices:
        evidence.extend(links_in_choices[:3])

    details = (
        f"links={len(all_links)}, invalid={len(invalid_links)}; "
        f"links_in_choices={len(links_in_choices)}"
    )

    return CategoryResult(
        name="link_setter_syntax",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


# ── P3 Scoring Orchestrator ─────────────────────────────────────────────

def score_response(raw: str, parsed: ModelOutput, variant: PromptVariant) -> list[CategoryResult]:
    """Run all 6 scorers on one response; returns exactly 6 CategoryResult (one per category)."""
    # INV-9: exactly 6 results in canonical category order.
    results = [
        score_markup_compliance(raw),
        score_variable_scoping(raw),
        score_passage_structure(raw, parsed),
        score_macro_usage(raw),
        score_naked_interpolation(parsed.prose or raw),
        score_link_setter_syntax(raw, parsed),
    ]
    return results


# ── P3 Prompt Fixture Factory ───────────────────────────────────────────

# Fixed fixture context for controlled prompts (P1 §3.3).
# These are controlled INPUTS, not prompt template text (INV-3). The real
# prompt templates come from build_*_passage_prompt in harness.prompts.
_FIXTURE_PREMISE = "A young apprentice discovers a magical tome in the dusty attic of their mentor's tower."
_FIXTURE_STORY_POINTS = "The apprentice must decide whether to read the forbidden book or return it."
_FIXTURE_ARC_MD = "## Chapter 1: The Discovery\nThe apprentice finds a mysterious artifact."
_FIXTURE_SNAPSHOT = "Location: Mentor's tower attic. Time: Late evening. $gold = 15, $hasMetKing = false."
_FIXTURE_ENTITIES = "Characters: apprentice (protagonist), mentor (wise old wizard)"
_FIXTURE_PARENT_PROSE = "The apprentice climbed the creaking stairs to the attic, dust motes dancing in the moonlight."
_FIXTURE_INSPIRATION = "Classic fantasy discovery trope with moral choices."
_FIXTURE_MODE = "standard"

_DIRECTION_PROMPTS = {
    "A": "The protagonist checks their inventory and sets a flag",
    "B": "Include a conditional: if the player has met the king, reference it",
    "C": "Show the player's gold count and a complex stat",
}


def build_fixture_prompt(variant: PromptVariant, direction: DirectionKey) -> str:
    """Build a fixed-context prompt for the given variant using the real build_*_passage_prompt builder."""
    # INV-3: delegates to the real harness.prompts builders — no inline prompt text.
    human_prompt = _DIRECTION_PROMPTS[direction]
    if variant == "compact":
        return build_compact_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_notes=_FIXTURE_ARC_MD,
            entities_text=_FIXTURE_ENTITIES,
            parent_prose=_FIXTURE_PARENT_PROSE,
            snapshot_text=_FIXTURE_SNAPSHOT,
            human_prompt=human_prompt,
        )
    elif variant == "full":
        return build_full_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_md=_FIXTURE_ARC_MD,
            snapshot_text=_FIXTURE_SNAPSHOT,
            entities_text=_FIXTURE_ENTITIES,
            inspiration=_FIXTURE_INSPIRATION,
            parent_prose=_FIXTURE_PARENT_PROSE,
            human_prompt=human_prompt,
            mode=_FIXTURE_MODE,
        )
    elif variant == "json":
        return build_json_passage_prompt(
            premise=_FIXTURE_PREMISE,
            story_points=_FIXTURE_STORY_POINTS,
            arc_md=_FIXTURE_ARC_MD,
            snapshot_text=_FIXTURE_SNAPSHOT,
            entities_text=_FIXTURE_ENTITIES,
            inspiration=_FIXTURE_INSPIRATION,
            parent_prose=_FIXTURE_PARENT_PROSE,
            human_prompt=human_prompt,
            mode=_FIXTURE_MODE,
        )
    raise ValueError(f"Unknown variant: {variant}")


# ── P3 Model Interaction ────────────────────────────────────────────────

def run_single_model(
    model: str,
    variant: PromptVariant,
    direction: DirectionKey,
    cfg: BenchmarkConfig,
    run_index: int = 0,
) -> ModelRunResult:
    """Call one model on one fixture prompt, parse, score, and return one ModelRunResult."""
    # INV-1: build_fixture_prompt uses the real prompt builders; we call
    # call_ollama_sync + parse_model_output[_json] directly — never
    # generate_story_output (no auto-repair).
    prompt = build_fixture_prompt(variant, direction)
    harness_cfg = HarnessConfig(
        ollama_model=model,
        ollama_base_url=cfg.base_url,
        temperature=cfg.temperature,
        num_predict=cfg.num_predict,
    )

    t0 = time.monotonic()
    try:
        if variant == "json":
            raw = call_ollama_sync(
                harness_cfg, prompt, timeout=cfg.timeout,
                temperature=cfg.temperature, num_predict=cfg.num_predict,
                format_spec="json", label=f"benchmark-{model}-{variant}-{direction}",
            )
            parsed = parse_model_output_json(raw)
        else:
            raw = call_ollama_sync(
                harness_cfg, prompt, timeout=cfg.timeout,
                temperature=cfg.temperature, num_predict=cfg.num_predict,
                label=f"benchmark-{model}-{variant}-{direction}",
            )
            parsed = parse_model_output(raw)
        elapsed = time.monotonic() - t0

        results = score_response(raw, parsed, variant)
        overall = all(r.passed for r in results)

        return ModelRunResult(
            model_name=model,
            variant=variant,
            direction=direction,
            run_index=run_index,
            raw_response=raw,
            parsed_output=parsed,
            category_results=tuple(results),
            overall_pass=overall,
            elapsed_seconds=elapsed,
        )
    except Exception as e:
        elapsed = time.monotonic() - t0
        # INV-6: graceful failure — return failing results, do not raise.
        empty_output = ModelOutput()
        failing_results = tuple(
            CategoryResult(
                name=name,
                passed=False,
                score=0.0,
                details=f"Error: {e}",
            )
            for name in _CATEGORY_ORDER  # INV-9: canonical order
        )
        return ModelRunResult(
            model_name=model,
            variant=variant,
            direction=direction,
            run_index=run_index,
            raw_response="",
            parsed_output=empty_output,
            category_results=failing_results,
            overall_pass=False,
            elapsed_seconds=elapsed,
            error=str(e),
        )


def discover_models(base_url: str) -> list[str]:
    """GET /api/tags from the Ollama server and return installed model tags."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ── P3 Report Assembly ──────────────────────────────────────────────────

def build_model_report(model: str, runs: list[ModelRunResult]) -> ModelReport:
    """Aggregate one model's runs into a ModelReport with per-category pass rates."""
    # INV-9: iterate categories in canonical order.
    summary_entries: list[CategorySummaryEntry] = []
    for cat_name in _CATEGORY_ORDER:
        total = 0
        passed = 0
        for run in runs:
            for cr in run.category_results:
                if cr.name == cat_name:
                    total += 1
                    if cr.passed:
                        passed += 1
        rate = passed / total if total > 0 else 0.0  # INV-10: 0.0 <= rate <= 1.0
        summary_entries.append(CategorySummaryEntry(
            name=cat_name,
            pass_rate=rate,
            total=total,
            passed=passed,
        ))

    # P1 §4.1 Q1 default: unweighted pass-count average across the 6 categories.
    overall_score = (
        sum(e.pass_rate for e in summary_entries) / len(summary_entries)
        if summary_entries else 0.0
    )
    runs_passed = sum(1 for r in runs if r.overall_pass)

    return ModelReport(
        model_name=model,
        runs=tuple(runs),
        category_summary=tuple(summary_entries),
        overall_score=overall_score,
        runs_total=len(runs),
        runs_passed=runs_passed,
    )


def build_benchmark_report(
    reports: list[ModelReport],
    cfg: BenchmarkConfig,
) -> BenchmarkReport:
    """Assemble the top-level BenchmarkReport from per-model reports and run config."""
    # INV-4: prompt_version populated from the live harness.prompts.PROMPT_VERSION,
    # not a hardcoded literal.
    return BenchmarkReport(
        models=tuple(reports),
        prompt_version=PROMPT_VERSION,
        config=cfg,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ollama_reachable=True,
    )


# ── P3 Report Formatting ────────────────────────────────────────────────

def format_report_text(report: BenchmarkReport) -> str:
    """Render the benchmark report as human-readable text for stdout / --output."""
    lines = [
        "=" * 70,
        "SugarCube Direction-Following Benchmark Report",
        "=" * 70,
        f"Generated: {report.generated_at}",
        f"Prompt Version: {report.prompt_version}",
        f"Ollama Reachable: {report.ollama_reachable}",
        "",
    ]
    for mr in report.models:
        lines.append(f"Model: {mr.model_name}")
        lines.append(f"  Runs: {mr.runs_passed}/{mr.runs_total} passed")
        lines.append(f"  Overall Score: {mr.overall_score:.1%}")
        lines.append("  Category Summary:")
        for entry in mr.category_summary:
            lines.append(f"    {entry.name}: {entry.passed}/{entry.total} ({entry.pass_rate:.1%})")
        lines.append("")
    return "\n".join(lines)


def format_report_json(report: BenchmarkReport) -> str:
    """Render the benchmark report as a JSON string for --json-output."""
    def serialize(obj):
        if dataclasses.is_dataclass(obj):
            d = dataclasses.asdict(obj)
            # Convert tuples to lists for JSON (P5 §3.4 discovery).
            for k, v in d.items():
                if isinstance(v, tuple):
                    d[k] = list(v)
            return d
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        return str(obj)

    data = serialize(report)
    # default=str handles any non-serializable edge cases (P5 §3.4).
    return json.dumps(data, indent=2, default=str)


# ── P3 CLI Entry Point ──────────────────────────────────────────────────

# INV-8: dry-run fixture — a deliberately correct SugarCube response that passes
# all 6 categories, confirming the scoring logic is self-consistent.
_DRY_RUN_RESPONSE = """PROSE:
The apprentice examined the tome carefully. ''This is remarkable!'' they whispered.
$gold glinted in their pouch as they weighed the decision.

<<set $hasReadBook to true>>

CHOICES:
- Open the book and read | A dangerous choice
- Return it to the mentor | The safe path

SUMMARY:
The apprentice discovered a magical tome and faced a moral choice.
"""


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args, run the benchmark, write reports; return process exit code."""
    parser = argparse.ArgumentParser(
        description="SugarCube Direction-Following Benchmark",
    )
    parser.add_argument("--models", nargs="*", default=[], help="Model tags to test (empty=auto-discover)")
    parser.add_argument("--variants", nargs="*", choices=["compact", "full", "json"],
                        default=["compact", "full", "json"], help="Prompt variants")
    parser.add_argument("--directions", nargs="*", choices=["A", "B", "C"],
                        default=["A", "B", "C"], help="Directions")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per call")
    parser.add_argument("--num-predict", type=int, default=640, help="Max tokens")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument("--runs", type=int, default=1, help="N runs per model×variant×direction")
    parser.add_argument("--dry-run", action="store_true", help="Score a fixture, skip Ollama (CI)")
    parser.add_argument("--output", default="", help="Text report file (empty=stdout)")
    parser.add_argument("--json-output", default="", help="JSON report file (empty=none)")

    args = parser.parse_args(argv)

    cfg = BenchmarkConfig(
        models=tuple(args.models),
        variants=tuple(args.variants),
        directions=tuple(args.directions),
        base_url=args.base_url,
        timeout=args.timeout,
        num_predict=args.num_predict,
        temperature=args.temperature,
        runs=args.runs,
        dry_run=args.dry_run,
        output_path=args.output,
        json_output_path=args.json_output,
    )

    if cfg.dry_run:
        # INV-8: score the fixture response without calling Ollama.
        parsed = parse_model_output(_DRY_RUN_RESPONSE)
        results = score_response(_DRY_RUN_RESPONSE, parsed, "compact")
        run = ModelRunResult(
            model_name="(dry-run)",
            variant="compact",
            direction="A",
            run_index=0,
            raw_response=_DRY_RUN_RESPONSE,
            parsed_output=parsed,
            category_results=tuple(results),
            overall_pass=all(r.passed for r in results),
            elapsed_seconds=0.0,
        )
        report = build_benchmark_report(
            [build_model_report("(dry-run)", [run])],
            cfg,
        )
    else:
        # Discover or use specified models.
        models = list(cfg.models)
        if not models:
            models = discover_models(cfg.base_url)
            if not models:
                print("No models found. Is Ollama running?", file=sys.stderr)
                return 1

        all_reports: list[ModelReport] = []
        for model in models:
            runs: list[ModelRunResult] = []
            for variant in cfg.variants:
                for direction in cfg.directions:
                    for run_idx in range(cfg.runs):
                        run = run_single_model(model, variant, direction, cfg, run_idx)
                        runs.append(run)
            all_reports.append(build_model_report(model, runs))

        report = build_benchmark_report(all_reports, cfg)

    # Output
    text_output = format_report_text(report)
    if cfg.output_path:
        with open(cfg.output_path, "w") as f:
            f.write(text_output)
    else:
        print(text_output)

    if cfg.json_output_path:
        json_output = format_report_json(report)
        with open(cfg.json_output_path, "w") as f:
            f.write(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
