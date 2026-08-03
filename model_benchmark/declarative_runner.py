"""Execution support for declarative benchmark test instances."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from harness.models import HarnessConfig, ModelOutput
from harness.ollama_client import call_ollama_sync_detailed
from harness.parsers import parse_model_output, parse_model_output_json
from model_benchmark.config import BenchmarkConfig
from model_benchmark.evaluators import evaluate_response
from model_benchmark.fixtures import _DRY_RUN_RESPONSE, build_fixture_prompt
from model_benchmark.schema import ResultRecord
from model_benchmark.scoring import PROMPT_VERSION, score_response
from model_benchmark.test_selection import ExpandedTestInstance


EVALUATOR_VERSION = "declarative-v1"


@dataclass(frozen=True)
class DeclarativeScoredResult:
    model_name: str
    raw_response: str
    parsed_output: ModelOutput
    category_results: tuple[Any, ...] = ()
    error: str = ""


def _dataset_rows(instance: ExpandedTestInstance) -> list[dict[str, Any] | None]:
    cfg = instance.config or instance.spec.config
    if cfg.dataset is None:
        return [None]
    from model_benchmark.dataset_loader import DatasetLoader

    source = (
        Path(instance.spec.source_files[-1])
        if instance.spec.source_files
        else Path.cwd()
    )
    candidate_bases = [source.parent, source.parent.parent]
    base_dir = next(
        (
            base
            for base in candidate_bases
            if cfg.dataset.path and (base / cfg.dataset.path).exists()
        ),
        None,
    )
    return DatasetLoader(base_dir=base_dir).load_rows(cfg.dataset)


def declarative_case_count(
    instances: Sequence[ExpandedTestInstance],
    config: BenchmarkConfig,
) -> int:
    """Count per-model declarative work units, including datasets/repetitions."""
    return sum(
        len(_dataset_rows(instance))
        * max(
            1,
            int(
                (instance.config or instance.spec.config).repetitions
                or config.runs
                or 1
            ),
        )
        for instance in instances
    )


def _format_text(text: str, variables: dict[str, Any]) -> str:
    """Format known ``{name}`` fields while leaving unknown fields intact."""

    class SafeValues(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    try:
        return text.format_map(SafeValues(variables))
    except (ValueError, TypeError):
        return text


def _direction(instance: ExpandedTestInstance) -> str:
    cfg = instance.config or instance.spec.config
    candidates = [
        instance.parameters.get("direction"),
        instance.parameters.get("dir"),
        (cfg.input_variables or {}).get("direction"),
        (
            cfg.prompt_template.input_variables.get("direction")
            if cfg.prompt_template is not None
            else None
        ),
    ]
    for value in candidates:
        key = str(value or "").strip().upper()
        if key in set("ABCDEFGH"):
            return key
    return "A"


def _variant(instance: ExpandedTestInstance) -> str:
    cfg = instance.config or instance.spec.config
    value = (
        cfg.prompt_template.variant
        if cfg.prompt_template is not None and cfg.prompt_template.variant
        else instance.parameters.get("variant", "compact")
    )
    return str(value or "compact")


def build_declarative_prompt(
    instance: ExpandedTestInstance,
    dataset_row: dict[str, Any] | None = None,
) -> str:
    """Build the concrete prompt represented by one expanded test instance."""
    cfg = instance.config or instance.spec.config
    variables: dict[str, Any] = {}
    if cfg.prompt_template is not None:
        variables.update(cfg.prompt_template.input_variables)
    variables.update(cfg.input_variables or {})
    variables.update(instance.parameters)
    variables.update(dataset_row or {})
    input_text = _format_text(cfg.input or "", variables).strip()

    template = cfg.prompt_template
    if template is not None and template.text:
        rendered = _format_text(template.text, variables).strip()
        return "\n\n".join(part for part in (rendered, input_text) if part)

    if template is not None and template.ref:
        source = Path(instance.spec.source_files[-1]) if instance.spec.source_files else Path.cwd()
        path = Path(template.ref)
        if not path.is_absolute():
            path = source.parent / path
        rendered = _format_text(path.read_text(encoding="utf-8"), variables).strip()
        return "\n\n".join(part for part in (rendered, input_text) if part)

    if template is not None and template.variant:
        base = build_fixture_prompt(_variant(instance), _direction(instance))
        if input_text:
            return f"{base.rstrip()}\n\nCASE-SPECIFIC REQUIREMENT:\n{input_text}\n"
        return base
    return input_text


def _evaluate(
    instance: ExpandedTestInstance,
    response: str,
    dataset_row: dict[str, Any] | None = None,
) -> tuple[float, float, bool, str, Any, tuple[Any, ...]]:
    cfg = instance.config or instance.spec.config
    variant = _variant(instance)
    parsed = parse_model_output_json(response) if variant == "json" else parse_model_output(response)

    sugarcube_case = bool(
        (cfg.expected is not None and cfg.expected.must_parse_as == "sugarcube_passage")
        or cfg.scoring_categories
        or (cfg.category or "").startswith(("markup", "macro", "passage", "variable", "link", "naked", "thinking"))
    )
    if sugarcube_case:
        required = frozenset(cfg.scoring_categories or ()) or None
        categories = score_response(
            response,
            parsed,
            variant,  # type: ignore[arg-type]
            _direction(instance),  # type: ignore[arg-type]
            required_categories=required,
        )
        if required is not None:
            categories = [c for c in categories if c.name in required]
        applicable = [c for c in categories if c.applicable]
        score = float(sum(c.score for c in applicable))
        maximum = float(len(applicable)) or 1.0
        passed = bool(applicable) and all(c.passed for c in applicable)
        reasoning = "; ".join(f"{c.name}: {c.details}" for c in applicable)
        return score, maximum, passed, reasoning, parsed, tuple(categories)

    evaluation = cfg.evaluation
    if evaluation is None:
        raise ValueError(f"declarative test {instance.instance_id!r} has no evaluator")
    expected: Any = cfg.expected
    if dataset_row:
        expected = cfg.expected.model_dump(exclude_none=True) if cfg.expected else {}
        if "answer" in dataset_row:
            expected["answer"] = dataset_row["answer"]
    result = evaluate_response(
        evaluation.name,
        response,
        expected=expected,
        context={
            "test_id": instance.instance_id,
            "test_name": cfg.name or instance.instance_id,
            "input_variables": {**(cfg.input_variables or {}), **instance.parameters},
            "dataset_row": dataset_row,
            "variant": variant,
        },
        params=evaluation.params,
        pass_threshold=evaluation.pass_threshold,
    )
    return result.score, result.max_score, result.passed, result.details, ModelOutput(), ()


def _record(
    instance: ExpandedTestInstance,
    *,
    model: str,
    repetition: int,
    response: str,
    elapsed: float,
    run_id: str,
    error: str = "",
    retry_count: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    finish_reason: str = "",
    dataset_row: dict[str, Any] | None = None,
    dataset_index: int | None = None,
) -> ResultRecord:
    cfg = instance.config or instance.spec.config
    now = datetime.now(timezone.utc).isoformat()
    if error and not response:
        score, maximum, parsed, categories = 0.0, 1.0, ModelOutput(), ()
        status, failure = "ERROR", "network_error"
        reasoning = "model generation failed"
    else:
        try:
            score, maximum, passed, reasoning, parsed, categories = _evaluate(
                instance, response, dataset_row
            )
            status = "PASS" if passed else "FAIL"
            failure = "none" if passed else "instruction_following"
        except Exception as exc:
            score, maximum, parsed, categories = 0.0, 1.0, ModelOutput(), ()
            status, failure = "ERROR", "evaluator_error"
            reasoning = "declarative evaluator failed"
            error = error or str(exc)
    seed = cfg.random_seed
    if seed is None and cfg.model_parameters is not None:
        seed = cfg.model_parameters.seed
    return ResultRecord(
        schema_version="1.0.0",
        test_id=(
            f"{instance.instance_id}"
            f"{'::row-' + str(dataset_index) if dataset_index is not None else ''}"
            f"::{model}::{repetition}"
        ),
        test_version=cfg.version or "1.0.0",
        capability=cfg.capability or "declarative",
        category=(cfg.category or "markup_compliance"),  # type: ignore[arg-type]
        subcategory=cfg.subcategory or _variant(instance),
        difficulty=cfg.difficulty or "medium",
        dataset=cfg.dataset.name if cfg.dataset is not None else "declarative",
        split=(cfg.dataset.split or "default") if cfg.dataset is not None else "default",
        repetition=repetition,
        input_summary=(
            f"{cfg.input or ''}\nDataset row: {dataset_row}"
            if dataset_row is not None
            else (cfg.input or "")
        )[:500],
        expected_behavior=str(cfg.expected.model_dump(exclude_none=True) if cfg.expected else ""),
        reference_rubric=str(cfg.evaluation.model_dump(exclude_none=True) if cfg.evaluation else "SugarCube scorers"),
        actual_output_raw=response,
        parsed_output=parsed,
        score=score,
        max_score=maximum,
        normalized_score=(score / maximum if maximum else 0.0),
        pass_threshold=(cfg.evaluation.pass_threshold if cfg.evaluation else 1.0),
        status=status,  # type: ignore[arg-type]
        failure_category=failure,  # type: ignore[arg-type]
        evaluator_reasoning=reasoning,
        evaluator_confidence=1.0,
        runtime_seconds=elapsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost=0.0,
        retry_count=retry_count,
        error_details=error,
        model_alias=model,
        config_alias=instance.source_id,
        prompt_version=PROMPT_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        random_seed="" if seed is None else str(seed),
        timestamp_start=now,
        timestamp_end=now,
        parent_result_id=run_id,
        provenance="new",
        scored_result=DeclarativeScoredResult(
            model_name=model,
            raw_response=response,
            parsed_output=parsed,
            category_results=categories,
            error=error,
        ),
        finish_reason=finish_reason,
    )


def execute_declarative_tests(
    instances: Sequence[ExpandedTestInstance],
    config: BenchmarkConfig,
    *,
    run_id: str,
    dry_run: bool = False,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[ResultRecord]:
    """Execute selected declarative instances and return enriched records."""
    from model_benchmark.scoring import discover_models

    models = list(config.models)
    if dry_run:
        models = ["(dry-run)"]
    elif not models:
        models = discover_models(config.base_url)

    work: list[
        tuple[str, ExpandedTestInstance, int, dict[str, Any] | None, int | None]
    ] = []
    for model in models:
        for instance in instances:
            cfg = instance.config or instance.spec.config
            repetitions = max(1, int(cfg.repetitions or config.runs or 1))
            dataset_rows = _dataset_rows(instance)
            for dataset_index, dataset_row in enumerate(dataset_rows, 1):
                row_number = dataset_index if dataset_row is not None else None
                for repetition in range(1, repetitions + 1):
                    work.append(
                        (model, instance, repetition, dataset_row, row_number)
                    )

    records: list[ResultRecord] = []
    for index, (
        model,
        instance,
        repetition,
        dataset_row,
        dataset_index,
    ) in enumerate(work, 1):
        cfg = instance.config or instance.spec.config
        response = _DRY_RUN_RESPONSE
        elapsed = 0.0
        error = ""
        retry_count = 0
        input_tokens = 0
        output_tokens = 0
        finish_reason = ""
        if dry_run and dataset_row is not None and "answer" in dataset_row:
            response = str(dataset_row["answer"])
        elif dry_run and cfg.expected is not None and cfg.expected.answer:
            response = cfg.expected.answer
        elif not dry_run:
            params = cfg.model_parameters
            harness_cfg = HarnessConfig(
                ollama_model=model,
                ollama_base_url=(params.base_url if params else config.base_url),
                temperature=(params.temperature if params else config.temperature),
                num_predict=(params.num_predict if params else config.num_predict),
            )
            seed = cfg.random_seed if cfg.random_seed is not None else (params.seed if params else None)
            timeout = cfg.timeout or (params.timeout if params else config.timeout)
            max_retries = cfg.retry_policy.max_retries if cfg.retry_policy else 0
            started = time.monotonic()
            while True:
                try:
                    generated = call_ollama_sync_detailed(
                        harness_cfg,
                        build_declarative_prompt(instance, dataset_row),
                        timeout=timeout,
                        temperature=harness_cfg.temperature,
                        num_predict=harness_cfg.num_predict,
                        format_spec="json" if _variant(instance) == "json" else None,
                        seed=seed,
                        label=f"declarative-{instance.instance_id}",
                    )
                    response = generated.response
                    input_tokens = generated.prompt_eval_count
                    output_tokens = generated.eval_count
                    finish_reason = generated.done_reason
                    break
                except Exception as exc:
                    error = str(exc)
                    if retry_count >= max_retries:
                        response = ""
                        break
                    retry_count += 1
            elapsed = time.monotonic() - started
        records.append(
            _record(
                instance,
                model=model,
                repetition=repetition,
                response=response,
                elapsed=elapsed,
                run_id=run_id,
                error=error,
                retry_count=retry_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                dataset_row=dataset_row,
                dataset_index=dataset_index,
            )
        )
        if progress_callback is not None:
            progress_callback(index, len(work), model)
    return records
