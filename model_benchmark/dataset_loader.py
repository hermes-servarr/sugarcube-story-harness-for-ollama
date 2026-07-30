#!/usr/bin/env python3
"""Dataset loader for declarative test configs (task t_b8e82f29).

Integrates with the ``DatasetReference`` model from ``config_schema.py``.
Tests can reference external datasets (CSV, JSONL, JSON, HuggingFace, or
inline data) by path or identifier. The loader fetches rows, applies
optional filters/sampling, and returns them as a list of dicts — one dict
per row — ready to be injected as parameterized test inputs.

Supported formats (``DatasetReference.format``):
    csv:         Comma-separated, first row is the header.
    jsonl:       JSON Lines — one JSON object per line.
    json:        A single JSON file containing a list of objects.
    huggingface: A HuggingFace ``datasets`` repo (requires the ``datasets``
                 package; if not installed, the loader raises a clear error).
    inline:      Rows provided directly in the config via ``inline_data``.

Path resolution:
    Relative paths are resolved relative to ``base_dir`` (default: the
    ``model_benchmark/tests/`` directory). Absolute paths are used as-is.

Filters:
    The ``filters`` dict from ``DatasetReference`` applies row-level filters.
    Each key is a column name, value is either a scalar (exact match) or a
    list (membership test). Example::

        filters:
          difficulty: ["easy", "medium"]   # keep rows where difficulty ∈ {easy, medium}
          enabled: true                     # keep rows where enabled == true

Sampling:
    If ``sample`` is set, the loader randomly samples N rows from the
    filtered result. ``seed`` controls reproducibility.
"""
from __future__ import annotations

import csv
import io
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from model_benchmark.config_schema import DatasetReference


# ── Result ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LoadedDataset:
    """The result of loading a dataset reference.

    Attributes:
        name:        Stable dataset identifier (from the reference).
        rows:        List of dicts — one per row, keys are column names.
        format:      The source format ("csv", "jsonl", "json", ...).
        source:      Human-readable source description (path or HF id).
        total_rows:  Total rows before filtering/sampling.
        filtered_rows: Rows after filtering (before sampling).
        metadata:    Extra info (split, version, checksum, sampling seed).
    """
    name: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    format: str = ""
    source: str = ""
    total_rows: int = 0
    filtered_rows: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Loader ────────────────────────────────────────────────────────────

class DatasetLoader:
    """Load datasets referenced by ``DatasetReference`` configs.

    Args:
        base_dir: Base directory for resolving relative paths. Defaults to
            ``model_benchmark/tests/`` (so ``datasets/foo.jsonl`` resolves
            to ``model_benchmark/tests/datasets/foo.jsonl``).
        hf_cache_dir: Optional HuggingFace cache directory override.

    Usage::

        loader = DatasetLoader()
        loaded = loader.load(ref)          # ref is a DatasetReference
        for row in loaded.rows:
            run_test(input_variables=row)
    """

    def __init__(
        self,
        base_dir: Optional[Path | str] = None,
        hf_cache_dir: Optional[Path | str] = None,
    ) -> None:
        if base_dir is None:
            # Default: model_benchmark/tests/ (relative to this file).
            base_dir = Path(__file__).parent / "tests"
        self.base_dir = Path(base_dir)
        self.hf_cache_dir = Path(hf_cache_dir) if hf_cache_dir else None

    # ── Public API ─────────────────────────────────────────────────────

    def load(self, ref: DatasetReference) -> LoadedDataset:
        """Load a dataset from a ``DatasetReference``.

        Resolves the path, reads the file, applies filters, and optionally
        samples rows. Returns a ``LoadedDataset`` with the final row list.
        """
        rows = self._load_raw(ref)
        total = len(rows)
        filtered = self._apply_filters(rows, ref.filters)
        if ref.sample is not None and ref.sample < len(filtered):
            filtered = self._sample(filtered, ref.sample, ref.seed)
        return LoadedDataset(
            name=ref.name,
            rows=filtered,
            format=ref.format,
            source=self._source_description(ref),
            total_rows=total,
            filtered_rows=len(filtered),
            metadata={
                "version": ref.version,
                "split": ref.split,
                "checksum": ref.checksum,
                "sample": ref.sample,
                "seed": ref.seed,
            },
        )

    def load_rows(self, ref: DatasetReference) -> list[dict[str, Any]]:
        """Convenience: return just the row list from ``load()``."""
        return self.load(ref).rows

    # ── Format loaders ─────────────────────────────────────────────────

    def _load_raw(self, ref: DatasetReference) -> list[dict[str, Any]]:
        """Dispatch to the format-specific loader."""
        fmt = ref.format
        if fmt == "inline":
            return self._load_inline(ref)
        if fmt == "csv":
            return self._load_csv(ref)
        if fmt == "jsonl":
            return self._load_jsonl(ref)
        if fmt == "json":
            return self._load_json(ref)
        if fmt == "huggingface":
            return self._load_huggingface(ref)
        raise ValueError(f"Unknown dataset format: {fmt!r}")

    def _load_inline(self, ref: DatasetReference) -> list[dict[str, Any]]:
        if ref.inline_data is None:
            raise ValueError("format='inline' requires inline_data to be set")
        return [dict(row) for row in ref.inline_data]

    def _resolve_path(self, ref: DatasetReference) -> Path:
        """Resolve a dataset file path relative to ``base_dir``."""
        if not ref.path:
            raise ValueError(f"format='{ref.format}' requires path to be set")
        p = Path(ref.path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    def _load_csv(self, ref: DatasetReference) -> list[dict[str, Any]]:
        path = self._resolve_path(ref)
        if not path.exists():
            raise FileNotFoundError(f"CSV dataset not found: {path}")
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    def _load_jsonl(self, ref: DatasetReference) -> list[dict[str, Any]]:
        path = self._resolve_path(ref)
        if not path.exists():
            raise FileNotFoundError(f"JSONL dataset not found: {path}")
        rows: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                    else:
                        rows.append({"value": obj})
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON on line {line_num} of {path}: {e}"
                    ) from e
        return rows

    def _load_json(self, ref: DatasetReference) -> list[dict[str, Any]]:
        path = self._resolve_path(ref)
        if not path.exists():
            raise FileNotFoundError(f"JSON dataset not found: {path}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [dict(row) if isinstance(row, dict) else {"value": row} for row in data]
        if isinstance(data, dict):
            # If the dict has a "data" or "rows" key that's a list, use that.
            for key in ("data", "rows", "examples"):
                if key in data and isinstance(data[key], list):
                    return [dict(r) if isinstance(r, dict) else {"value": r} for r in data[key]]
            # Otherwise, treat as a single-row dataset.
            return [data]
        raise ValueError(f"JSON dataset at {path} is not a list or dict")

    def _load_huggingface(self, ref: DatasetReference) -> list[dict[str, Any]]:
        if not ref.huggingface_id:
            raise ValueError("format='huggingface' requires huggingface_id to be set")
        try:
            from datasets import load_dataset  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "The 'datasets' package is required to load HuggingFace datasets. "
                "Install it with: pip install datasets"
            ) from e

        split = ref.split or "test"
        ds = load_dataset(
            ref.huggingface_id,
            split=split,
            cache_dir=str(self.hf_cache_dir) if self.hf_cache_dir else None,
        )
        return [dict(row) for row in ds]

    # ── Filtering ──────────────────────────────────────────────────────

    def _apply_filters(
        self,
        rows: list[dict[str, Any]],
        filters: Optional[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply column-value filters to the rows.

        Each key in ``filters`` is a column name. The value is either a
        scalar (exact match) or a list (membership test). A special key
        ``enabled`` (bool) can be used to filter on a boolean column.
        """
        if not filters:
            return list(rows)
        # Skip meta-keys that aren't real column filters.
        result = []
        column_filters = {k: v for k, v in filters.items() if k != "enabled"}
        for row in rows:
            if self._row_matches(row, column_filters):
                result.append(row)
        return result

    @staticmethod
    def _row_matches(row: dict[str, Any], filters: dict[str, Any]) -> bool:
        for col, expected in filters.items():
            actual = row.get(col)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                # Coerce types for comparison (e.g. "true" vs True).
                if str(actual).lower() != str(expected).lower():
                    return False
        return True

    # ── Sampling ───────────────────────────────────────────────────────

    def _sample(
        self,
        rows: list[dict[str, Any]],
        n: int,
        seed: Optional[int],
    ) -> list[dict[str, Any]]:
        """Randomly sample ``n`` rows from ``rows`` (without replacement)."""
        rng = random.Random(seed)
        return rng.sample(rows, n)

    # ── Helpers ────────────────────────────────────────────────────────

    def _source_description(self, ref: DatasetReference) -> str:
        if ref.format == "inline":
            return f"inline ({len(ref.inline_data or [])} rows)"
        if ref.format == "huggingface":
            return f"huggingface:{ref.huggingface_id}" + (
                f"/{ref.split}" if ref.split else ""
            )
        return str(ref.path or "(no path)")
