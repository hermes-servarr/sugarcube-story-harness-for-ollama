"""Create a deterministic, architecture-blinded narrative review bundle.

The public bundle contains only matched story context and randomly ordered
outputs named A/B. The private key retains model, architecture, case, and
source-record identities. Compiler scores are deliberately excluded from the
review items and response template so quality remains a separate result layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from model_benchmark.refactor_benchmark import REFACTOR_CASES_PATH, _context_for_case, load_refactor_cases


SCHEMA_VERSION = "narrative-review-v1"
RUBRIC = (
    "coherence_with_immediate_context",
    "continuity_accuracy",
    "specificity_over_generic_filler",
    "distinct_meaningful_choices",
    "dialogue_voice",
    "pacing_readability",
    "tone_style_compliance",
)


class NarrativeReviewError(ValueError):
    """Raised when a source run cannot produce a valid matched review set."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if private and hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if private and os.name != "nt":
            os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_records(run_dir: Path) -> tuple[list[dict[str, Any]], str]:
    source = run_dir / "results_internal.jsonl"
    if not source.is_file():
        raise NarrativeReviewError(f"missing source results: {source}")
    raw = source.read_bytes()
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise NarrativeReviewError(f"invalid JSON on source line {line_number}") from error
        if not isinstance(value, dict):
            raise NarrativeReviewError(f"source line {line_number} is not an object")
        records.append(value)
    return records, hashlib.sha256(raw).hexdigest()


def _case_id(record: dict[str, Any]) -> str:
    case_id = str(record.get("input_summary", "")).split(":", 1)[0]
    if not case_id:
        raise NarrativeReviewError("source record has no case identity")
    return case_id


def _reviewable_output(record: dict[str, Any]) -> dict[str, Any] | None:
    scored = record.get("scored_result")
    parsed = scored.get("parsed_output") if isinstance(scored, dict) else None
    if not isinstance(parsed, dict):
        return None
    prose = parsed.get("prose")
    choices = parsed.get("choices")
    if not isinstance(prose, str) or not prose.strip() or not isinstance(choices, list) or not choices:
        return None
    clean_choices = []
    for choice in choices:
        if not isinstance(choice, dict) or not isinstance(choice.get("text"), str):
            return None
        clean_choices.append({"text": choice["text"], "hint": str(choice.get("hint", ""))})
    return {"prose": prose, "choices": clean_choices}


def _pair_identity(record: dict[str, Any]) -> tuple[str, str, int]:
    return str(record.get("model_alias", "")), _case_id(record), int(record.get("repetition", 0))


def _digest_order(seed: str, *parts: object) -> str:
    material = "\0".join((seed, *(str(part) for part in parts)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_review_bundle(
    run_dir: Path,
    *,
    architecture_a: str,
    architecture_b: str,
    sample_size: int,
    seed: str,
    required_architectures: Iterable[str] = (),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build public bundle, private answer key, and blank score template."""
    if not architecture_a or not architecture_b or architecture_a == architecture_b:
        raise NarrativeReviewError("two distinct architecture names are required")
    if sample_size < 1:
        raise NarrativeReviewError("sample_size must be positive")

    records, source_sha256 = _read_records(run_dir)
    case_corpus_sha256 = hashlib.sha256(REFACTOR_CASES_PATH.read_bytes()).hexdigest()
    cases = {case.id: case for case in load_refactor_cases()}
    selected_architectures = {architecture_a, architecture_b}
    eligibility_architectures = selected_architectures | {str(value) for value in required_architectures}
    if "" in eligibility_architectures:
        raise NarrativeReviewError("required architecture names cannot be empty")
    matched: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = {}
    for record in records:
        architecture = str(record.get("subcategory", ""))
        if architecture in eligibility_architectures:
            matched.setdefault(_pair_identity(record), {})[architecture] = record

    complete = [(identity, pair) for identity, pair in matched.items() if eligibility_architectures <= pair.keys()]
    eligible = []
    for identity, pair in complete:
        outputs = {architecture: _reviewable_output(pair[architecture]) for architecture in eligibility_architectures}
        if all(output is not None for output in outputs.values()):
            eligible.append((identity, pair, outputs))

    if not eligible:
        raise NarrativeReviewError("no matched reviewable output pairs found")
    by_case: dict[str, list[Any]] = {}
    for item in eligible:
        by_case.setdefault(item[0][1], []).append(item)
    for items in by_case.values():
        items.sort(key=lambda item: _digest_order(seed, *item[0]))
    case_order = sorted(by_case, key=lambda case_id: _digest_order(seed, "case", case_id))
    chosen = []
    while len(chosen) < min(sample_size, len(eligible)):
        added = False
        for case_id in case_order:
            if by_case[case_id] and len(chosen) < min(sample_size, len(eligible)):
                chosen.append(by_case[case_id].pop(0))
                added = True
        if not added:
            break

    public_items: list[dict[str, Any]] = []
    private_items: list[dict[str, Any]] = []
    response_items: list[dict[str, Any]] = []
    for index, (identity, pair, outputs) in enumerate(chosen, 1):
        model, case_id, repetition = identity
        case = cases.get(case_id)
        if case is None:
            raise NarrativeReviewError(f"unknown case in source results: {case_id}")
        item_id = f"Review_{index:03d}"
        architectures = [architecture_a, architecture_b]
        label_offset = int(_digest_order(seed, "label-balance"), 16) % 2
        if (index + label_offset) % 2:
            architectures.reverse()
        labels = {"A": architectures[0], "B": architectures[1]}
        public_items.append({
            "item_id": item_id,
            "task": case.task,
            "immediate_context": _context_for_case(case),
            "outputs": {label: outputs[architecture] for label, architecture in labels.items()},
        })
        private_items.append({
            "item_id": item_id,
            "model": model,
            "case_id": case_id,
            "repetition": repetition,
            "labels": labels,
            "source_test_ids": {label: pair[architecture].get("test_id", "") for label, architecture in labels.items()},
        })
        response_items.append({
            "item_id": item_id,
            "ratings": {label: {dimension: None for dimension in RUBRIC} for label in ("A", "B")},
            "preference": None,
            "notes": "",
        })

    common = {
        "schema_version": SCHEMA_VERSION,
        "source_results_sha256": source_sha256,
        "case_corpus_sha256": case_corpus_sha256,
        "selection_seed": seed,
        "eligible_pairs": len(eligible),
        "eligible_case_count": len({identity[1] for identity, _, _ in eligible}),
        "excluded_unreviewable_pairs": len(complete) - len(eligible),
        "sample_size": len(public_items),
        "sampled_case_count": len({item[0][1] for item in chosen}),
    }
    bundle = {
        **common,
        "instructions": "Score each dimension from 1 (poor) to 5 (excellent). Judge story quality only; do not infer compiler correctness. Preference is A, B, or tie.",
        "rubric": list(RUBRIC),
        "items": public_items,
    }
    private_key = {
        **common,
        "private": True,
        "architectures": [architecture_a, architecture_b],
        "eligibility_architectures": sorted(eligibility_architectures),
        "output_a_counts": {
            architecture: sum(item["labels"]["A"] == architecture for item in private_items)
            for architecture in (architecture_a, architecture_b)
        },
        "items": private_items,
    }
    response_template = {
        "schema_version": SCHEMA_VERSION,
        "source_results_sha256": source_sha256,
        "rating_scale": {"minimum": 1, "maximum": 5},
        "preference_values": ["A", "B", "tie"],
        "items": response_items,
    }
    return bundle, private_key, response_template


def write_review_bundle(output_dir: Path, bundle: dict[str, Any], private_key: dict[str, Any], template: dict[str, Any]) -> None:
    _atomic_json(output_dir / "review_bundle.json", bundle)
    _atomic_json(output_dir / "review_scores.template.json", template)
    _atomic_json(output_dir / "review_key.private.json", private_key, private=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--architectures", nargs=2, default=("typed_fill", "legacy_json"), metavar=("CANDIDATE", "CONTROL"))
    parser.add_argument("--require-architectures", nargs="*", default=())
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", default="narrative-review-v1")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        bundle, private_key, template = build_review_bundle(
            args.run_dir,
            architecture_a=args.architectures[0],
            architecture_b=args.architectures[1],
            sample_size=args.sample_size,
            seed=args.seed,
            required_architectures=args.require_architectures,
        )
        write_review_bundle(args.output_dir, bundle, private_key, template)
    except (NarrativeReviewError, OSError) as error:
        print(f"error: {error}", file=os.sys.stderr)
        return 2
    print(args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
