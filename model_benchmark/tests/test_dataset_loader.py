#!/usr/bin/env python3
"""Tests for the dataset loader (dataset_loader.py).

Covers: all formats (inline, CSV, JSONL, JSON, HuggingFace), path
resolution, filtering, sampling, reproducibility, error handling, and
LoadedDataset metadata. Uses the sample datasets in tests/datasets/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from model_benchmark.config_schema import DatasetReference
from model_benchmark.dataset_loader import DatasetLoader, LoadedDataset


# ── Helpers ─────────────────────────────────────────────────────────────

DATASETS_DIR = Path(__file__).parent / "datasets"


# ── Inline format ────────────────────────────────────────────────────────

class TestInlineFormat:
    def test_basic_inline(self):
        ref = DatasetReference(
            name="test", format="inline",
            inline_data=[{"q": "a", "answer": "1"}, {"q": "b", "answer": "2"}],
        )
        loader = DatasetLoader()
        loaded = loader.load(ref)
        assert loaded.name == "test"
        assert loaded.format == "inline"
        assert len(loaded.rows) == 2
        assert loaded.rows[0]["q"] == "a"

    def test_empty_inline(self):
        ref = DatasetReference(name="empty", format="inline", inline_data=[])
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 0
        assert loaded.total_rows == 0

    def test_inline_preserves_dicts(self):
        data = [{"key": "val", "nested": {"a": 1}}]
        ref = DatasetReference(name="t", format="inline", inline_data=data)
        loaded = DatasetLoader().load(ref)
        assert loaded.rows[0]["key"] == "val"
        assert loaded.rows[0]["nested"]["a"] == 1


# ── CSV format ──────────────────────────────────────────────────────────

class TestCSVFormat:
    def test_load_csv(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
        )
        loader = DatasetLoader(base_dir=DATASETS_DIR.parent)
        loaded = loader.load(ref)
        assert loaded.format == "csv"
        assert len(loaded.rows) == 10
        assert "question" in loaded.rows[0]
        assert loaded.rows[0]["answer"] == "Paris"

    def test_csv_total_rows(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
        )
        loaded = DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)
        assert loaded.total_rows == 10

    def test_csv_not_found(self):
        ref = DatasetReference(
            name="missing", format="csv", path="nonexistent.csv",
        )
        with pytest.raises(FileNotFoundError):
            DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)


# ── JSONL format ────────────────────────────────────────────────────────

class TestJSONLFormat:
    def test_load_jsonl(self):
        ref = DatasetReference(
            name="dirs", format="jsonl", path="datasets/directions.jsonl",
        )
        loader = DatasetLoader(base_dir=DATASETS_DIR.parent)
        loaded = loader.load(ref)
        assert loaded.format == "jsonl"
        assert len(loaded.rows) == 5
        assert "prompt" in loaded.rows[0]
        assert loaded.rows[0]["variant"] == "compact"

    def test_jsonl_skips_blank_lines(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text('{"a": 1}\n\n{"b": 2}\n')
        ref = DatasetReference(name="t", format="jsonl", path=str(f))
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 2

    def test_jsonl_invalid_line(self, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text('{"a": 1}\nnot json\n')
        ref = DatasetReference(name="t", format="jsonl", path=str(f))
        with pytest.raises(ValueError, match="Invalid JSON"):
            DatasetLoader().load(ref)

    def test_jsonl_not_found(self):
        ref = DatasetReference(
            name="missing", format="jsonl", path="nope.jsonl",
        )
        with pytest.raises(FileNotFoundError):
            DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)


# ── JSON format ──────────────────────────────────────────────────────────

class TestJSONFormat:
    def test_load_json_list(self, tmp_path):
        f = tmp_path / "data.json"
        json.dump([{"x": 1}, {"x": 2}], f.open("w"))
        ref = DatasetReference(name="t", format="json", path=str(f))
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 2

    def test_load_json_dict_with_data_key(self, tmp_path):
        f = tmp_path / "data.json"
        json.dump({"data": [{"x": 1}]}, f.open("w"))
        ref = DatasetReference(name="t", format="json", path=str(f))
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 1
        assert loaded.rows[0]["x"] == 1

    def test_load_json_dict_with_rows_key(self, tmp_path):
        f = tmp_path / "data.json"
        json.dump({"rows": [{"y": 10}]}, f.open("w"))
        ref = DatasetReference(name="t", format="json", path=str(f))
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 1
        assert loaded.rows[0]["y"] == 10

    def test_load_json_single_dict(self, tmp_path):
        f = tmp_path / "data.json"
        json.dump({"single": "row"}, f.open("w"))
        ref = DatasetReference(name="t", format="json", path=str(f))
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 1
        assert loaded.rows[0]["single"] == "row"


# ── HuggingFace format ────────────────────────────────────────────────────

class TestHuggingFaceFormat:
    def test_missing_hf_id_raises(self):
        """DatasetReference validation catches missing huggingface_id at construction."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="huggingface_id"):
            DatasetReference(name="hf", format="huggingface")

    def test_hf_without_datasets_package(self):
        """If datasets package not installed, should raise ImportError."""
        # This test only runs if 'datasets' is not installed.
        try:
            import datasets  # noqa: F401
            pytest.skip("datasets package installed — skipping import error test")
        except ImportError:
            pass
        ref = DatasetReference(
            name="hf", format="huggingface", huggingface_id="squad",
        )
        with pytest.raises(ImportError, match="datasets"):
            DatasetLoader().load(ref)


# ── Filtering ────────────────────────────────────────────────────────────

class TestFiltering:
    def test_filter_single_value(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[
                {"q": "a", "diff": "easy"},
                {"q": "b", "diff": "hard"},
            ],
            filters={"diff": "easy"},
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 1
        assert loaded.rows[0]["q"] == "a"

    def test_filter_list_values(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[
                {"q": "a", "diff": "easy"},
                {"q": "b", "diff": "medium"},
                {"q": "c", "diff": "hard"},
            ],
            filters={"diff": ["easy", "medium"]},
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 2
        assert loaded.rows[0]["diff"] == "easy"
        assert loaded.rows[1]["diff"] == "medium"

    def test_filter_no_match(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[{"q": "a", "diff": "easy"}],
            filters={"diff": "hard"},
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 0

    def test_no_filter_returns_all(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[{"a": 1}, {"b": 2}],
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 2

    def test_filter_on_csv(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
            filters={"difficulty": "easy"},
        )
        loaded = DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)
        assert all(r["difficulty"] == "easy" for r in loaded.rows)
        assert loaded.total_rows == 10  # before filtering
        assert loaded.filtered_rows == len(loaded.rows)  # after filtering, before sampling
        assert loaded.filtered_rows < loaded.total_rows  # filter reduced rows
        assert len(loaded.rows) == 5  # easy rows in qa_simple.csv

    def test_total_vs_filtered_rows(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
            filters={"difficulty": ["easy", "medium"]},
        )
        loaded = DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)
        assert loaded.total_rows == 10
        assert loaded.filtered_rows < 10
        assert len(loaded.rows) == loaded.filtered_rows


# ── Sampling ─────────────────────────────────────────────────────────────

class TestSampling:
    def test_sample_n_rows(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[{"i": i} for i in range(20)],
            sample=5,
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 5

    def test_sample_reproducible(self):
        data = [{"i": i} for i in range(20)]
        ref1 = DatasetReference(name="t", format="inline",
                                inline_data=list(data), sample=5, seed=42)
        ref2 = DatasetReference(name="t", format="inline",
                                inline_data=list(data), sample=5, seed=42)
        loader = DatasetLoader()
        r1 = loader.load(ref1)
        r2 = loader.load(ref2)
        assert [r["i"] for r in r1.rows] == [r["i"] for r in r2.rows]

    def test_sample_different_seeds(self):
        data = [{"i": i} for i in range(20)]
        ref1 = DatasetReference(name="t", format="inline",
                                inline_data=list(data), sample=5, seed=1)
        ref2 = DatasetReference(name="t", format="inline",
                                inline_data=list(data), sample=5, seed=2)
        loader = DatasetLoader()
        r1 = loader.load(ref1)
        r2 = loader.load(ref2)
        assert [r["i"] for r in r1.rows] != [r["i"] for r in r2.rows]

    def test_sample_larger_than_data(self):
        """If sample > available rows, return all rows."""
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[{"a": 1}, {"b": 2}],
            sample=100,
        )
        loaded = DatasetLoader().load(ref)
        assert len(loaded.rows) == 2  # returns all, can't sample more than available

    def test_sample_after_filter(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
            filters={"difficulty": ["easy", "medium"]},
            sample=3, seed=42,
        )
        loaded = DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)
        assert len(loaded.rows) == 3
        assert loaded.total_rows == 10
        assert loaded.filtered_rows >= 3


# ── Path resolution ──────────────────────────────────────────────────────

class TestPathResolution:
    def test_relative_path(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
        )
        loader = DatasetLoader(base_dir=DATASETS_DIR.parent)
        loaded = loader.load(ref)
        assert len(loaded.rows) > 0

    def test_absolute_path(self):
        abs_path = str(DATASETS_DIR / "qa_simple.csv")
        ref = DatasetReference(
            name="qa", format="csv", path=abs_path,
        )
        loader = DatasetLoader()  # base_dir shouldn't matter for abs paths
        loaded = loader.load(ref)
        assert len(loaded.rows) > 0


# ── LoadedDataset metadata ────────────────────────────────────────────────

class TestLoadedDatasetMetadata:
    def test_metadata_fields(self):
        ref = DatasetReference(
            name="test", version="1.0", split="test", format="inline",
            inline_data=[{"a": 1}], sample=None, seed=None,
            checksum="sha256:abc",
        )
        loaded = DatasetLoader().load(ref)
        assert loaded.metadata["version"] == "1.0"
        assert loaded.metadata["split"] == "test"
        assert loaded.metadata["checksum"] == "sha256:abc"

    def test_source_description_inline(self):
        ref = DatasetReference(name="t", format="inline", inline_data=[{"a": 1}])
        loaded = DatasetLoader().load(ref)
        assert "inline" in loaded.source

    def test_source_description_csv(self):
        ref = DatasetReference(
            name="qa", format="csv", path="datasets/qa_simple.csv",
        )
        loaded = DatasetLoader(base_dir=DATASETS_DIR.parent).load(ref)
        assert "qa_simple.csv" in loaded.source

    def test_source_description_hf(self):
        ref = DatasetReference(
            name="hf", format="huggingface", huggingface_id="squad",
            split="train",
        )
        loaded_metadata = ref
        # Can't actually load HF, but can check source description construction
        loader = DatasetLoader()
        # Test the private method directly
        source = loader._source_description(ref)
        assert "huggingface:squad" in source
        assert "train" in source


# ── Error handling ──────────────────────────────────────────────────────

class TestErrorHandling:
    def test_unknown_format(self):
        # DatasetReference won't accept invalid format, but we test the loader
        ref = DatasetReference(name="t", format="inline", inline_data=[{"a": 1}])
        ref.format = "unknown"  # bypass validation
        with pytest.raises(ValueError, match="Unknown dataset format"):
            DatasetLoader().load(ref)

    def test_csv_requires_path(self):
        """DatasetReference validation catches missing path at construction."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="requires path"):
            DatasetReference(name="t", format="csv", path="")


# ── Integration with config_schema ────────────────────────────────────────

class TestConfigSchemaIntegration:
    def test_dataset_reference_from_yaml(self):
        """DatasetReference should parse from a dict (as in YAML config)."""
        data = {
            "name": "test_ds",
            "format": "inline",
            "inline_data": [{"q": "hello", "answer": "world"}],
        }
        ref = DatasetReference(**data)
        loaded = DatasetLoader().load(ref)
        assert loaded.rows[0]["answer"] == "world"

    def test_load_rows_convenience(self):
        ref = DatasetReference(
            name="t", format="inline",
            inline_data=[{"a": 1}, {"b": 2}],
        )
        rows = DatasetLoader().load_rows(ref)
        assert len(rows) == 2
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)
