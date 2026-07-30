#!/usr/bin/env python3
"""Scoring logic for the SugarCube Direction-Following benchmark.

This module contains all scoring-related logic extracted from the original
monolithic ``benchmark.py`` (Phase 7 refactor): the 3 type aliases, 6 frozen
dataclasses, ``_CATEGORY_ORDER`` constant, 6 scoring functions, the
``score_response`` orchestrator, model interaction (``run_single_model``,
``discover_models``), report assembly (``build_model_report``,
``build_benchmark_report``), report formatting (``format_report_text``,
``format_report_json``), and the CLI entry point (``main``).

Test fixtures (``build_fixture_prompt``, ``_DRY_RUN_RESPONSE``) live in
``model_benchmark/fixtures.py`` and are imported here at runtime.  The
``benchmark.py`` shim re-exports the public API from this module, fixtures.py,
and schema.py so existing ``from model_benchmark.benchmark import ...``
imports continue to work.

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
- INV-3 (real prompt templates): build_fixture_prompt (in fixtures.py) imports
  and calls the real build_*_passage_prompt functions from harness.prompts; no
  inline prompt text.
- INV-4 (PROMPT_VERSION traceability): build_benchmark_report populates
  BenchmarkReport.prompt_version from the live harness.prompts.PROMPT_VERSION.
- INV-5 (no harness modification): this file only imports from harness.*; the
  final git diff lists only model_benchmark/ files.
- INV-6 (graceful failure): every scorer has an empty-input early-return guard;
  run_single_model wraps call+parse+score in try/except returning failing results.
- INV-7 (choice text+hint scanning): score_passage_structure and
  score_link_setter_syntax scan combined "{text} | {hint}" per ParsedChoice.
- INV-8 (dry-run self-consistency): _DRY_RUN_RESPONSE (in fixtures.py) is a
  known-good SugarCube passage; main(["--dry-run"]) scores it and all 6
  categories pass.
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
from typing import TYPE_CHECKING, Literal

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
from model_benchmark.fixtures import build_fixture_prompt, _DRY_RUN_RESPONSE

# Bridge to the Phase 2 schema module (created by the parent task
# t_45b88e53).  The types below are *defined* in ``model_benchmark.schema``
# and are the outcome/record types this scoring layer's output feeds into
# downstream: each scorer returns a ``CategoryResult`` (defined here) and
# ``score_response`` returns the 6-element ``list[CategoryResult]`` that the
# future P3 converter wraps into a schema ``ResultRecord`` (whose
# ``category`` field is the ``CategoryName`` defined here and whose
# ``scored_result`` field embeds the ``ModelRunResult`` defined here).  The
# ``ResultStatus`` literal is the PASS/FAIL/ERROR/... classification that a
# ``CategoryResult.passed`` verdict maps onto once a result is classified.
#
# Imported under ``TYPE_CHECKING`` only: scoring.py has no *runtime*
# dependency on the schema types today (it does not construct
# ``ResultRecord``), and keeping the import type-checker-only preserves
# INV-2 (scoring purity — no heavyweight/I/O imports in the scoring layer)
# and avoids any import cycle (schema.py imports ``CategoryName`` /
# ``ModelRunResult`` back from this module, also under ``TYPE_CHECKING``
# only, so neither module imports the other at runtime).
if TYPE_CHECKING:
    from model_benchmark.schema import (
        FailureCategory,
        ResultRecord,
        ResultStatus,
    )


# ── P2 Data Structures ───────────────────────────────────────────────────

PromptVariant = Literal["compact", "full", "json", "thinking"]

DirectionKey = Literal["A", "B", "C", "D", "E", "F", "G", "H"]

CategoryName = Literal[
    "markup_compliance",
    "variable_scoping",
    "passage_structure",
    "macro_usage",
    "naked_interpolation",
    "link_setter_syntax",
    "thinking_quality",
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
    "thinking_quality",
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


# TODO(benchmark-upgrade): scoring.py — move BenchmarkConfig to
# model_benchmark.config (P2 §1 home map, P3 §3.2).  The EXTENDED
# BenchmarkConfig with 9 new fields (checkpoint_every, checkpoint_interval_seconds,
# output_dir, verbose, quiet, anonymize, baseline_dir, random_seed,
# force_rerun — all defaulted per P2 §3.1) is defined in config.py.  Keep the
# current 12-field version here only until config.py is created; then delete
# and re-export.  P3 §3.2 defines parse_cli_args(argv) -> BenchmarkConfig in
# config.py.
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


# TODO(benchmark-upgrade): scoring.py — BenchmarkReport stays here (P2 §1 home
# map).  No changes needed; the definition is correct.
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

def score_thinking_quality(thinking_text: str, direction: DirectionKey) -> CategoryResult:
    """Score Category 7: thinking/reasoning quality for thinking models.

    Evaluates the chain-of-thought reasoning that thinking models produce
    before their formatted output. Checks whether the reasoning:
    - References state variables ($var)
    - Mentions SugarCube macros (<<set>>, <<if>>, etc.)
    - Plans the direction-specific feature
    - Shows structured analysis (multiple reasoning steps)
    - References the story context (premise, entities, etc.)

    For non-thinking responses (empty thinking_text), returns a passing
    result with score 1.0 so it doesn't penalize non-thinking models.
    The category is only meaningful for the "thinking" prompt variant.
    """
    if not thinking_text or not thinking_text.strip():
        # Non-thinking response: neutral pass, no penalty
        return CategoryResult(
            name="thinking_quality",
            passed=True,
            score=1.0,
            details="No thinking content (non-thinking variant or model).",
        )

    # Sub-checks (INV-10): 5 checks
    sub_checks = 5
    passed_checks = 0
    evidence: list[str] = []

    # 1. References state variables ($var)
    var_mentions = re.findall(r'\$\w+', thinking_text)
    if var_mentions:
        passed_checks += 1
        evidence.extend(var_mentions[:3])

    # 2. Mentions SugarCube macros
    macro_mentions = re.findall(r'<<\w+>>', thinking_text)
    if macro_mentions:
        passed_checks += 1
        evidence.extend(macro_mentions[:3])

    # 3. Direction-specific planning
    direction_features = {
        "A": [r'<<set', r'inventory', r'flag'],
        "B": [r'<<if', r'conditional', r'king'],
        "C": [r'gold', r'stat', r'<<print'],
        "D": [r'<<include', r'shared', r'passage'],
        "E": [r'<<capture', r'<<for', r'loop'],
        "F": [r'<<textbox', r'<<radiobutton', r'input'],
        "G": [r'<<for', r'<<print', r'inventory'],
        "H": [r'<<switch', r'<<case', r'location'],
    }
    direction_patterns = direction_features.get(direction, [])
    direction_hits = 0
    for pat in direction_patterns:
        if re.search(pat, thinking_text, re.IGNORECASE):
            direction_hits += 1
    if direction_hits >= 1:
        passed_checks += 1
        evidence.append(f"direction_{direction}_planning")

    # 4. Structured analysis (multiple reasoning steps)
    # Count numbered items, bullet points, or section headers in thinking
    structured_markers = len(re.findall(r'^\s*\d+\.\s', thinking_text, re.MULTILINE))
    structured_markers += len(re.findall(r'^\s*[-*]\s', thinking_text, re.MULTILINE))
    structured_markers += len(re.findall(r'^\s*#{1,3}\s', thinking_text, re.MULTILINE))
    if structured_markers >= 3:
        passed_checks += 1
        evidence.append(f"structured_markers={structured_markers}")

    # 5. References story context (premise, entities, character names)
    context_keywords = ['apprentice', 'mentor', 'pilot', 'journalist', 'detective',
                        'netrunner', 'character', 'protagonist', 'scene', 'passage',
                        'story', 'narrative']
    context_hits = sum(1 for kw in context_keywords if kw in thinking_text.lower())
    if context_hits >= 2:
        passed_checks += 1
        evidence.append(f"context_refs={context_hits}")

    score = passed_checks / sub_checks
    # thinking_quality passes if at least 3/5 checks pass (quality threshold)
    passed = passed_checks >= 3

    details = (
        f"vars={len(var_mentions)}, macros={len(macro_mentions)}, "
        f"direction_hits={direction_hits}, structured={structured_markers}, "
        f"context_refs={context_hits}"
    )

    return CategoryResult(
        name="thinking_quality",
        passed=passed,
        score=score,
        details=details,
        evidence=tuple(evidence),
    )


def score_response(raw: str, parsed: ModelOutput, variant: PromptVariant,
                   direction: DirectionKey = "A") -> list[CategoryResult]:
    """Run all scorers on one response; returns exactly 7 CategoryResult (one per category).

    For thinking variants, extracts thinking content and scores it separately.
    The existing 6 scorers run on the stripped output (without thinking preamble).
    """
    # Extract thinking content for thinking_quality scoring
    from model_benchmark.thinking import extract_thinking
    extraction = extract_thinking(raw)
    thinking_text = extraction.thinking_text if extraction.has_thinking else ""

    # For the 6 format scorers, use the stripped output if thinking was detected
    format_raw = extraction.output_text if extraction.has_thinking else raw

    # INV-9: exactly 7 results in canonical category order.
    results = [
        score_markup_compliance(format_raw),
        score_variable_scoping(format_raw),
        score_passage_structure(format_raw, parsed),
        score_macro_usage(format_raw),
        score_naked_interpolation(parsed.prose or format_raw),
        score_link_setter_syntax(format_raw, parsed),
        score_thinking_quality(thinking_text, direction),
    ]
    return results


# ── P3 Model Interaction ────────────────────────────────────────────────

# TODO(benchmark-upgrade): scoring.py — run_single_model and discover_models
# move to model_benchmark.runner per P3 §2.3.  They are preserved signatures
# (verified against benchmark.py L670-757).  Delete from scoring.py and
# re-export from runner.py in the benchmark.py shim.  P3 §3.1 adds
# execute_benchmark, resume_from_checkpoint, render_progress to runner.py
# (NEW interfaces).

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

        results = score_response(raw, parsed, variant, direction)
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

# TODO(benchmark-upgrade): scoring.py — build_model_report and
# build_benchmark_report stay in scoring.py per P3 §2.4 (preserved
# signatures, home = scoring.py).  No TODO needed — the definitions are
# correct and in the right module.

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

# TODO(benchmark-upgrade): scoring.py — format_report_text and
# format_report_json move to model_benchmark.reports per P3 §2.5.  They are
# preserved signatures (verified against benchmark.py L818-856).  Delete
# from scoring.py and add `from model_benchmark.reports import
# format_report_text, format_report_json` to the benchmark.py shim.
# P3 §3.8 adds format_summary_text and format_summary_markdown (NEW) to
# reports.py.

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

# TODO(benchmark-upgrade): scoring.py — main moves to model_benchmark.cli
# per P3 §2.6.  Signature preserved (argv: list[str] | None = None -> int);
# body extended to wire new modules (checkpoint, anonymization, persistence,
# stats, comparisons).  Delete from scoring.py and add
# `from model_benchmark.cli import main` to the benchmark.py shim.
# P3 §3.2 defines parse_cli_args in config.py which main() calls.

def main(argv: list[str] | None = None) -> int:
    """Parse CLI args, run the benchmark, write reports; return process exit code."""
    parser = argparse.ArgumentParser(
        description="SugarCube Direction-Following Benchmark",
    )
    parser.add_argument("--models", nargs="*", default=[], help="Model tags to test (empty=auto-discover)")
    parser.add_argument("--variants", nargs="*", choices=["compact", "full", "json", "thinking"],
                        default=["compact", "full", "json"], help="Prompt variants")
    parser.add_argument("--directions", nargs="*", choices=["A", "B", "C", "D", "E", "F", "G", "H"],
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
        results = score_response(_DRY_RUN_RESPONSE, parsed, "compact", "A")
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
