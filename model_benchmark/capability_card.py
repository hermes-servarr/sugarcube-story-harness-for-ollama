"""Issue a source-bound mechanical capability card from frozen confirmation evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from harness.generation.capabilities import (
    CapabilityCard,
    CapabilityEvidence,
    CapabilityIdentity,
    MECHANICAL_GATE_NAMES,
    StrategyCapability,
    evidence_hashes_match,
    source_hashes_match,
)
from harness.generation.compiler import COMPILER_VERSION
from model_benchmark.narrative_review import NarrativeReviewError, _atomic_json
from model_benchmark.promotion_confirmation import analyze_confirmation


SOURCE_PATHS = (
    "harness/generation/compiler.py",
    "harness/generation/contracts.py",
    "harness/generation/browser_evaluator.py",
    "harness/generation/capabilities.py",
    "harness/models.py",
    "harness/parsers.py",
    "model_benchmark/refactor_benchmark.py",
    "model_benchmark/refactor_cases.json",
    "model_benchmark/scoring.py",
    "model_benchmark/browser_rescore.py",
    "model_benchmark/promotion_confirmation.py",
    "model_benchmark/capability_card.py",
)
PARENT_RUN_SOURCE_PATHS = (
    "harness/generation/compiler.py",
    "harness/generation/contracts.py",
    "harness/models.py",
    "harness/parsers.py",
    "model_benchmark/refactor_benchmark.py",
    "model_benchmark/refactor_cases.json",
    "model_benchmark/scoring.py",
)
BROWSER_RUN_SOURCE_PATHS = (
    "harness/generation/browser_evaluator.py",
    "model_benchmark/browser_rescore.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NarrativeReviewError(f"invalid JSON object: {path}") from error
    if not isinstance(value, dict):
        raise NarrativeReviewError(f"expected JSON object: {path}")
    return value


def _relative_file(repository_root: Path, path: Path) -> str:
    root = repository_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as error:
        raise NarrativeReviewError(f"evidence must remain inside repository: {path}") from error


def _timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise NarrativeReviewError(f"invalid {label} timestamp") from error
    if parsed.tzinfo is None:
        raise NarrativeReviewError(f"{label} timestamp must include a timezone")
    return parsed


def _require_sources_frozen_before(root: Path, relatives: tuple[str, ...], started_at: datetime) -> None:
    for relative in relatives:
        path = root / relative
        if not path.is_file():
            raise NarrativeReviewError(f"capability source file is missing: {relative}")
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=started_at.tzinfo)
        if modified_at > started_at:
            raise NarrativeReviewError(
                f"source changed after evidence run started; rerun required: {relative}"
            )


def issue_mechanical_card(
    repository_root: Path,
    confirmation_path: Path,
    *,
    card_id: str,
    valid_days: int = 90,
) -> CapabilityCard:
    root = repository_root.resolve()
    confirmation_path = confirmation_path.resolve()
    report = _load_object(confirmation_path)
    parent_argument = Path(str(report.get("parent_path", "")))
    child_argument = Path(str(report.get("child_path", "")))
    parent_dir = (root / parent_argument).resolve()
    child_dir = (root / child_argument).resolve()
    _relative_file(root, parent_dir)
    _relative_file(root, child_dir)
    reproduced = analyze_confirmation(
        parent_dir,
        child_dir,
        legacy_architecture=str(report.get("legacy_architecture", "legacy_json")),
        required_margin_percentage_points=float(report.get("required_margin_percentage_points", 5)),
    )
    reproduced["parent_path"] = parent_argument.as_posix()
    reproduced["child_path"] = child_argument.as_posix()
    if reproduced != report:
        raise NarrativeReviewError("confirmation report does not reproduce with the current analyzer")
    margin = report.get("required_margin_percentage_points")
    repeat_count = report.get("repeat_count")
    if report.get("schema_version") != "promotion-confirmation-v1":
        raise NarrativeReviewError("unsupported confirmation report schema")
    if report.get("legacy_architecture") != "legacy_json":
        raise NarrativeReviewError("mechanical capability requires the legacy_json control")
    if not isinstance(repeat_count, int) or isinstance(repeat_count, bool) or repeat_count < 10:
        raise NarrativeReviewError("mechanical capability requires at least ten matched seeds")
    if (
        not isinstance(margin, (int, float))
        or isinstance(margin, bool)
        or margin < 5.0
    ):
        raise NarrativeReviewError("mechanical capability requires a five-point margin")

    parent_manifest_path = parent_dir / "run_manifest.json"
    child_manifest_path = child_dir / "run_manifest.json"
    parent_manifest = _load_object(parent_manifest_path)
    child_manifest = _load_object(child_manifest_path)
    parent_started_at = _timestamp(parent_manifest.get("start_timestamp"), "parent start")
    child_started_at = _timestamp(child_manifest.get("start_timestamp"), "browser start")
    _require_sources_frozen_before(root, PARENT_RUN_SOURCE_PATHS, parent_started_at)
    _require_sources_frozen_before(root, BROWSER_RUN_SOURCE_PATHS, child_started_at)
    configs = parent_manifest.get("model_configs")
    if not isinstance(configs, list) or len(configs) != 1 or not isinstance(configs[0], dict):
        raise NarrativeReviewError("capability issuance requires exactly one model artifact")
    model = configs[0]
    runtime = parent_manifest.get("runtime_settings")
    if not isinstance(runtime, dict):
        raise NarrativeReviewError("parent manifest lacks runtime settings")
    digest = str(model.get("digest", ""))
    quantization = str(model.get("quantization", ""))
    ollama_version = str(runtime.get("ollama_version", ""))
    if not digest or not quantization or not ollama_version:
        raise NarrativeReviewError("parent manifest lacks exact model/runtime identity")

    prompt_identity = {
        "prompt_template": parent_manifest.get("prompt_template"),
        "prompt_version": parent_manifest.get("prompt_version"),
        "dataset_checksums": parent_manifest.get("dataset_checksums"),
        "config_file_checksum": parent_manifest.get("config_file_checksum"),
        "evaluator_prompt": parent_manifest.get("evaluator_prompt"),
        "evaluator_version": parent_manifest.get("evaluator_version"),
    }
    generation_settings = {
        "generation_params": parent_manifest.get("generation_params"),
        "runtime_settings": runtime,
        "random_seed": parent_manifest.get("random_seed"),
        "repeated_runs_count": parent_manifest.get("repeated_runs_count"),
        "timeouts": parent_manifest.get("timeouts"),
    }
    gates = report.get("automated_promotion_gates")
    if not isinstance(gates, dict):
        raise NarrativeReviewError("confirmation report lacks automated gates")
    strategies = []
    for strategy in ("flat_fill", "typed_fill"):
        values = gates.get(strategy)
        if (
            not isinstance(values, dict)
            or values.get("mechanical_and_latency_gates_pass") is not True
            or any(values.get(name) is not True for name in MECHANICAL_GATE_NAMES)
        ):
            raise NarrativeReviewError(f"strategy did not clear mechanical gates: {strategy}")
        strategies.append(StrategyCapability(
            strategy=strategy,
            mechanically_qualified=True,
            narrative_review="not_assessed",
            default_eligible=False,
            notes="Ten-seed automated gates pass; independent blinded narrative review is pending.",
        ))

    observed_at = _timestamp(child_manifest.get("completion_timestamp"), "browser completion")
    source_hashes = {}
    for relative in SOURCE_PATHS:
        source = root / relative
        if not source.is_file():
            raise NarrativeReviewError(f"capability source file is missing: {relative}")
        source_hashes[relative] = _sha256(source)

    card = CapabilityCard(
        card_id=card_id,
        observed_at=observed_at,
        valid_until=observed_at + timedelta(days=valid_days),
        identity=CapabilityIdentity(
            model_digest=digest,
            quantization=quantization,
            prompt_profile_sha256=_canonical_sha256(prompt_identity),
            ollama_version=ollama_version,
            contract_schema_version=1,
            compiler_version=COMPILER_VERSION,
            generation_settings_sha256=_canonical_sha256(generation_settings),
        ),
        evidence=CapabilityEvidence(
            confirmation_report=_relative_file(root, confirmation_path),
            confirmation_report_sha256=_sha256(confirmation_path),
            parent_manifest=_relative_file(root, parent_manifest_path),
            parent_manifest_sha256=_sha256(parent_manifest_path),
            browser_manifest=_relative_file(root, child_manifest_path),
            browser_manifest_sha256=_sha256(child_manifest_path),
        ),
        source_sha256=source_hashes,
        strategies=tuple(strategies),
    )
    if not evidence_hashes_match(card, root) or not source_hashes_match(card, root):
        raise NarrativeReviewError("issued capability card failed its own evidence/source validation")
    return card


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("confirmation_report", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--card-id", required=True)
    parser.add_argument("--valid-days", type=int, default=90)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.valid_days < 1:
            raise NarrativeReviewError("valid-days must be positive")
        card = issue_mechanical_card(
            args.repository_root,
            args.confirmation_report,
            card_id=args.card_id,
            valid_days=args.valid_days,
        )
        _atomic_json(args.output, card.model_dump(mode="json"))
    except (NarrativeReviewError, OSError, ValueError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print(f"{args.output.resolve()} {card.fingerprint()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
