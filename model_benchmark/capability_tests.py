"""Signed execution and validation for declarative capability probes."""
from __future__ import annotations

import dataclasses
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from harness.models import HarnessConfig
from harness.ollama_client import call_ollama_sync
from harness.parsers import parse_model_output, parse_model_output_json
from harness.prompts import (
    build_compact_passage_prompt,
    build_full_passage_prompt,
    build_json_passage_prompt,
    build_thinking_passage_prompt,
)
from model_benchmark.fixtures import FIXTURE_CONTEXTS, FixtureContext
from model_benchmark.prompt_overlay import apply_prompt_overlay
from model_benchmark.scoring import (
    BenchmarkConfig,
    CategoryResult,
    ModelRunResult,
    score_response,
)
from model_benchmark.runner import result_record_from_model_run
from model_benchmark.thinking import extract_thinking


CORE_CASES_PATH = Path(__file__).with_name("capability_cases.json")
CANDIDATE_CASES_DIR = Path("benchmark_optimization/candidate_tests")
_ID_RE = re.compile(r"^(?:T\d|CAND-T\d)-[A-Z0-9-]+$")
_VARIABLE_RE = re.compile(r"^\$[A-Za-z_]\w*$")
_ALLOWED_VARIANTS = {"compact", "full", "json", "thinking"}
_ALLOWED_CONTEXTS = set(FIXTURE_CONTEXTS)
_ALLOWED_SIZES = {"S", "M", "L", "XL"}
_ALLOWED_COMPLEXITIES = {"K1", "K2", "K3", "K4"}
_ALLOWED_DISTRACTORS = {"D0", "D1"}
_ALLOWED_RESPONSE_MODES = {"passage", "plain_text"}
_OUTPUT_BUDGETS = {
    "tiny": 32,
    "short": 96,
    "medium": 256,
    "standard": None,
}
_ALLOWED_CHECKS = {
    "sections",
    "contains",
    "absent",
    "macro",
    "variable",
    "context_needle",
    "min_choices",
    "balanced_macro",
    "no_markdown",
    "plain_text",
    "max_words",
    "min_words",
    "conversation_layout",
    "min_dialogue_turns",
    "mc_inner_monologue",
}
_NEEDLES = {
    "archive_code": "7319",
    "treaty_name": "Accord of Glass",
    "witness_name": "Mira Vale",
}


@dataclass(frozen=True)
class CapabilityCase:
    id: str
    tier: int
    context_ref: str
    context_size: str
    task_complexity: str
    distractor_density: str
    variant: str
    direction_key: str
    task: str
    checks: tuple[dict[str, Any], ...]
    response_mode: str
    output_budget: str
    source: str


class CapabilityCaseError(ValueError):
    """Raised when declarative capability data is unsafe or invalid."""


def _bounded_string(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CapabilityCaseError(f"{field} must be a non-empty string <= {limit}")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise CapabilityCaseError(f"{field} contains control characters")
    return value


def validate_case(data: Any, *, candidate: bool, source: str) -> CapabilityCase:
    if not isinstance(data, dict):
        raise CapabilityCaseError("case must be an object")
    allowed = {
        "schema_version", "id", "tier", "context_ref", "context_size",
        "task_complexity", "distractor_density", "variant", "direction_key",
        "task", "checks", "response_mode", "output_budget",
    }
    if set(data) - allowed:
        raise CapabilityCaseError("case contains unknown fields")
    if data.get("schema_version") != 1:
        raise CapabilityCaseError("unsupported schema_version")
    case_id = _bounded_string(data.get("id"), "id", 80)
    if not _ID_RE.fullmatch(case_id):
        raise CapabilityCaseError("invalid case id")
    if candidate != case_id.startswith("CAND-"):
        raise CapabilityCaseError("candidate id prefix does not match source")
    tier = data.get("tier")
    if not isinstance(tier, int) or not 0 <= tier <= 9:
        raise CapabilityCaseError("tier must be an integer from 0 to 9")
    context_ref = data.get("context_ref")
    context_size = data.get("context_size")
    complexity = data.get("task_complexity")
    distractors = data.get("distractor_density")
    variant = data.get("variant")
    direction_key = data.get("direction_key")
    response_mode = data.get("response_mode", "passage")
    output_budget = data.get("output_budget", "standard")
    if context_ref not in _ALLOWED_CONTEXTS:
        raise CapabilityCaseError("unknown context_ref")
    if context_size not in _ALLOWED_SIZES:
        raise CapabilityCaseError("unknown context_size")
    if complexity not in _ALLOWED_COMPLEXITIES:
        raise CapabilityCaseError("unknown task_complexity")
    if distractors not in _ALLOWED_DISTRACTORS:
        raise CapabilityCaseError("unknown distractor_density")
    if variant not in _ALLOWED_VARIANTS:
        raise CapabilityCaseError("unknown variant")
    if direction_key not in set("ABCDEFGH"):
        raise CapabilityCaseError("direction_key must be A-H")
    if response_mode not in _ALLOWED_RESPONSE_MODES:
        raise CapabilityCaseError("unknown response_mode")
    if output_budget not in _OUTPUT_BUDGETS:
        raise CapabilityCaseError("unknown output_budget")
    task = _bounded_string(data.get("task"), "task", 1_500)
    if re.search(r"https?://", task, re.IGNORECASE):
        raise CapabilityCaseError("task must not contain URLs")
    checks = data.get("checks")
    if not isinstance(checks, list) or not 3 <= len(checks) <= 12:
        raise CapabilityCaseError("checks must contain 3 to 12 entries")
    checked: list[dict[str, Any]] = []
    nontrivial = False
    for raw_check in checks:
        if not isinstance(raw_check, dict) or "check" not in raw_check:
            raise CapabilityCaseError("each check must be an object with check")
        kind = raw_check.get("check")
        if kind not in _ALLOWED_CHECKS:
            raise CapabilityCaseError("unknown check primitive")
        permitted = {
            "sections": {"check"},
            "contains": {"check", "value"},
            "absent": {"check", "value"},
            "macro": {"check", "name"},
            "variable": {"check", "name"},
            "context_needle": {"check", "name"},
            "min_choices": {"check", "count"},
            "balanced_macro": {"check", "name"},
            "no_markdown": {"check"},
            "plain_text": {"check"},
            "max_words": {"check", "count"},
            "min_words": {"check", "count"},
            "conversation_layout": {"check"},
            "min_dialogue_turns": {"check", "count"},
            "mc_inner_monologue": {"check"},
        }[kind]
        if set(raw_check) - permitted:
            raise CapabilityCaseError("check contains unknown fields")
        check = dict(raw_check)
        if kind in {"contains", "absent"}:
            check["value"] = _bounded_string(check.get("value"), "check value", 120)
        elif kind in {"macro", "balanced_macro"}:
            name = _bounded_string(check.get("name"), "macro name", 24)
            if not re.fullmatch(r"[a-z][a-z0-9]*", name):
                raise CapabilityCaseError("invalid macro name")
            check["name"] = name
            nontrivial = True
        elif kind == "variable":
            name = _bounded_string(check.get("name"), "variable name", 64)
            if not _VARIABLE_RE.fullmatch(name):
                raise CapabilityCaseError("invalid variable name")
            check["name"] = name
            nontrivial = True
        elif kind == "context_needle":
            if check.get("name") not in _NEEDLES:
                raise CapabilityCaseError("unknown context needle")
            nontrivial = True
        elif kind in {
            "min_choices", "max_words", "min_words", "min_dialogue_turns"
        }:
            count = check.get("count")
            upper = (
                6 if kind == "min_choices"
                else 12 if kind == "min_dialogue_turns"
                else 500
            )
            if not isinstance(count, int) or not 1 <= count <= upper:
                raise CapabilityCaseError(f"{kind} count must be 1 to {upper}")
            nontrivial = True
        checked.append(check)
    if candidate and not nontrivial:
        raise CapabilityCaseError("candidate needs at least one non-trivial check")
    return CapabilityCase(
        id=case_id,
        tier=tier,
        context_ref=context_ref,
        context_size=context_size,
        task_complexity=complexity,
        distractor_density=distractors,
        variant=variant,
        direction_key=direction_key,
        task=task,
        checks=tuple(checked),
        response_mode=response_mode,
        output_budget=output_budget,
        source=source,
    )


def load_cases(
    *,
    core_path: Path = CORE_CASES_PATH,
    candidate_dir: Path | None = CANDIDATE_CASES_DIR,
) -> list[CapabilityCase]:
    core_data = json.loads(core_path.read_text(encoding="utf-8"))
    if not isinstance(core_data, list):
        raise CapabilityCaseError("core capability file must contain an array")
    cases = [
        validate_case(item, candidate=False, source="core") for item in core_data
    ]
    if candidate_dir and candidate_dir.is_dir():
        paths = sorted(candidate_dir.glob("*.json"))
        if len(paths) > 20:
            raise CapabilityCaseError("too many candidate test files")
        for path in paths:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 32_768:
                raise CapabilityCaseError("invalid candidate test file")
            data = json.loads(path.read_text(encoding="utf-8"))
            cases.append(validate_case(data, candidate=True, source="candidate"))
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise CapabilityCaseError("duplicate capability case id")
    return cases


def _sized_context(case: CapabilityCase) -> FixtureContext:
    base = FIXTURE_CONTEXTS[case.context_ref]
    if case.context_size == "S":
        return dataclasses.replace(
            base,
            story_points="Keep the scene focused.",
            arc_md="## Current scene",
            snapshot="$archiveCode = 7319, $hasKey = false, $gold = 15.",
            entities="Witness: Mira Vale. Treaty: Accord of Glass.",
            parent_prose="The protagonist pauses.",
            inspiration="",
        )
    repetitions = {"M": 0, "L": 18, "XL": 70}[case.context_size]
    padding = "\n".join(
        f"Background note {index}: district {index % 7} remains unchanged; "
        f"ledger entry {1000 + index} is unrelated to the current decision."
        for index in range(1, repetitions + 1)
    )
    distractor = ""
    if case.distractor_density == "D1":
        distractor = (
            "\nArchived invalid examples to ignore: **markdown**, "
            "<<set $legacy = 1>>, and setup.legacy."
        )
    return dataclasses.replace(
        base,
        arc_md=f"{base.arc_md}\n{padding}{distractor}",
        snapshot=(
            f"{base.snapshot} $archiveCode = 7319, $hasKey = false, "
            "$treatySigned = false."
        ),
        entities=(
            f"{base.entities}; witness Mira Vale; treaty Accord of Glass."
        ),
    )


def _build_prompt(case: CapabilityCase) -> str:
    ctx = _sized_context(case)
    if case.response_mode == "plain_text":
        return (
            "CONTEXT\n"
            f"Premise: {ctx.premise}\n"
            f"Story points: {ctx.story_points}\n"
            f"Arc notes:\n{ctx.arc_md}\n"
            f"Snapshot: {ctx.snapshot}\n"
            f"Entities: {ctx.entities}\n"
            f"Prior prose: {ctx.parent_prose}\n\n"
            f"TASK\n{case.task}\n\n"
            "Answer directly in plain text. Do not use SugarCube macros, "
            "JSON, or PROSE/CHOICES/SUMMARY section labels."
        )
    kwargs = dict(
        premise=ctx.premise,
        story_points=ctx.story_points,
        snapshot_text=ctx.snapshot,
        entities_text=ctx.entities,
        parent_prose=ctx.parent_prose,
        human_prompt=case.task,
    )
    if case.variant == "compact":
        prompt = build_compact_passage_prompt(arc_notes=ctx.arc_md, **kwargs)
        return apply_prompt_overlay(
            prompt, variant=case.variant, direction=case.direction_key
        )
    common = dict(
        arc_md=ctx.arc_md,
        inspiration=ctx.inspiration,
        mode=ctx.mode,
        **kwargs,
    )
    if case.variant == "full":
        prompt = build_full_passage_prompt(**common)
    elif case.variant == "json":
        prompt = build_json_passage_prompt(**common)
    else:
        prompt = build_thinking_passage_prompt(**common)
    return apply_prompt_overlay(
        prompt, variant=case.variant, direction=case.direction_key
    )


def _score_checks(case: CapabilityCase, raw: str, parsed: Any) -> CategoryResult:
    extraction = extract_thinking(raw)
    text = extraction.output_text if extraction.has_thinking else raw
    passed = 0
    evidence: list[str] = []
    for check in case.checks:
        kind = check["check"]
        ok = False
        if kind == "sections":
            ok = all(getattr(parsed, name, "") for name in ("prose", "choices", "summary"))
        elif kind == "contains":
            ok = check["value"].casefold() in text.casefold()
        elif kind == "absent":
            ok = check["value"].casefold() not in text.casefold()
        elif kind == "macro":
            ok = re.search(rf"<<\s*{re.escape(check['name'])}\b", text) is not None
        elif kind == "variable":
            ok = check["name"] in text
        elif kind == "context_needle":
            ok = _NEEDLES[check["name"]].casefold() in text.casefold()
        elif kind == "min_choices":
            ok = len(getattr(parsed, "choices", ()) or ()) >= check["count"]
        elif kind == "balanced_macro":
            name = re.escape(check["name"])
            ok = len(re.findall(rf"<<\s*{name}\b", text)) == len(
                re.findall(rf"<<\s*/{name}\s*>>", text)
            ) > 0
        elif kind == "no_markdown":
            ok = not re.search(r"\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)", text)
        elif kind == "plain_text":
            ok = not re.search(
                r"<<|^PROSE:|^CHOICES:|^SUMMARY:|^\s*[\{\[]",
                text,
                re.MULTILINE,
            )
        elif kind == "max_words":
            ok = len(re.findall(r"\b[\w'-]+\b", text)) <= check["count"]
        elif kind == "min_words":
            ok = len(re.findall(r"\b[\w'-]+\b", text)) >= check["count"]
        elif kind == "conversation_layout":
            prose = getattr(parsed, "prose", "") or ""
            dialogue_at = prose.find("DIALOGUE:")
            inner_at = prose.find("INNER MONOLOGUE:")
            ok = 0 <= dialogue_at < inner_at
        elif kind == "min_dialogue_turns":
            prose = getattr(parsed, "prose", "") or ""
            dialogue = prose.partition("DIALOGUE:")[2].partition(
                "INNER MONOLOGUE:"
            )[0]
            turns = re.findall(
                r'(?m)^\s*[A-Za-z][A-Za-z0-9 _-]*:\s*["“][^"”\n]+["”]\s*$',
                dialogue,
            )
            ok = len(turns) >= check["count"]
        elif kind == "mc_inner_monologue":
            prose = getattr(parsed, "prose", "") or ""
            inner = prose.partition("INNER MONOLOGUE:")[2]
            ok = re.search(r"(?m)^\s*MC:\s*//[^/\n]+//\s*$", inner) is not None
        passed += int(ok)
        evidence.append(f"{kind}={'pass' if ok else 'fail'}")
    score = passed / len(case.checks)
    failed = [
        item.split("=", 1)[0]
        for item in evidence
        if item.endswith("=fail")
    ]
    return CategoryResult(
        name="capability_observables",
        passed=passed == len(case.checks),
        score=score,
        details=(
            f"checks={passed}/{len(case.checks)}; "
            f"failed={','.join(failed) if failed else 'none'}"
        ),
        evidence=tuple(evidence),
    )


def execute_capability_cases(
    cfg: BenchmarkConfig,
    cases: Iterable[CapabilityCase],
) -> list[Any]:
    records = []
    for model in cfg.models:
        for case in cases:
            prompt = _build_prompt(case)
            configured_cap = _OUTPUT_BUDGETS[case.output_budget]
            case_num_predict = (
                cfg.num_predict
                if configured_cap is None
                else min(cfg.num_predict, configured_cap)
            )
            harness_cfg = HarnessConfig(
                ollama_model=model,
                ollama_base_url=cfg.base_url,
                temperature=cfg.temperature,
                num_predict=case_num_predict,
            )
            started = time.monotonic()
            error = ""
            try:
                kwargs: dict[str, Any] = {}
                if case.variant == "json" and case.response_mode == "passage":
                    kwargs["format_spec"] = "json"
                raw = call_ollama_sync(
                    harness_cfg,
                    prompt,
                    timeout=cfg.timeout,
                    temperature=cfg.temperature,
                    num_predict=case_num_predict,
                    label=f"capability-{case.id}",
                    **kwargs,
                )
                parsed = (
                    parse_model_output_json(raw)
                    if case.variant == "json" and case.response_mode == "passage"
                    else parse_model_output(raw)
                )
                categories = (
                    score_response(raw, parsed, case.variant, case.direction_key)
                    if case.response_mode == "passage"
                    else []
                )
                categories.append(_score_checks(case, raw, parsed))
            except Exception as exc:
                raw = ""
                parsed = parse_model_output("")
                error = str(exc)
                categories = [
                    CategoryResult(
                        name="capability_observables",
                        passed=False,
                        score=0.0,
                        details="capability case execution failed",
                    )
                ]
            run = ModelRunResult(
                model_name=model,
                variant=case.variant,
                direction=case.direction_key,
                run_index=0,
                raw_response=raw,
                parsed_output=parsed,
                category_results=tuple(categories),
                overall_pass=not error and all(item.passed for item in categories),
                elapsed_seconds=time.monotonic() - started,
                error=error,
            )
            record = result_record_from_model_run(run)
            records.append(
                dataclasses.replace(
                    record,
                    test_id=f"{model}:{case.id}:{case.variant}:1",
                    test_version="capability-v1",
                    capability="sugarcube_capability_ladder",
                    category="capability_observables",
                    subcategory=(
                        case.variant
                        if case.response_mode == "passage"
                        else "plain_text"
                    ),
                    difficulty=f"T{case.tier}",
                    dataset=f"capability_{case.source}",
                    split=(
                        f"{case.context_size}-{case.task_complexity}-"
                        f"{case.distractor_density}"
                    ),
                    input_summary=case.id,
                    expected_behavior="all signed declarative checks pass",
                    reference_rubric="signed capability check vocabulary v1",
                )
            )
    return records
