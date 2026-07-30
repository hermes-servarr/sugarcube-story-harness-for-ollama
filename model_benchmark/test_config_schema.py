#!/usr/bin/env python3
"""Tests for the declarative test configuration schema (config_schema.py).

Verifies: schema parsing, layered merge semantics, validation rules (required
fields, type constraints, enums, cross-field constraints), JSON Schema export,
and matrix expansion config. These tests are additive — they do not modify
the existing 63 tests in test_benchmark.py.
"""
from __future__ import annotations

import pytest
import yaml

from model_benchmark.config_schema import (
    BUILTIN_DEFAULTS,
    DefaultsDocument,
    DatasetReference,
    EvaluatorReference,
    MatrixConfig,
    MergePolicy,
    ModelEligibility,
    ModelParameters,
    PromptTemplate,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    SuiteDocument,
    TestConfig,
    TestDocument,
    TestMetadata,
    deep_merge,
    export_json_schema,
    parse_config_dict,
    resolve_test,
)


# ── Schema version ──────────────────────────────────────────────────────

class TestSchemaVersion:
    def test_schema_version_is_semver(self):
        assert SCHEMA_VERSION == "1.0.0"
        assert SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS

    def test_unsupported_version_rejected(self):
        with pytest.raises(Exception, match="Unsupported schema_version"):
            TestDocument(schema_version="0.0.1", kind="test", id="x")

    def test_unsupported_version_rejected_defaults(self):
        with pytest.raises(Exception, match="Unsupported schema_version"):
            DefaultsDocument(schema_version="9.9.9", kind="defaults",
                             defaults=TestConfig())


# ── Document parsing ─────────────────────────────────────────────────────

class TestParseConfigDict:
    def test_parse_defaults(self):
        doc = parse_config_dict({"kind": "defaults", "defaults": {"timeout": 60}})
        assert isinstance(doc, DefaultsDocument)
        assert doc.defaults.timeout == 60

    def test_parse_suite(self):
        doc = parse_config_dict({
            "kind": "suite", "name": "s1", "tests": ["t1", "t2"],
        })
        assert isinstance(doc, SuiteDocument)
        assert doc.name == "s1"
        assert doc.tests == ["t1", "t2"]

    def test_parse_test(self):
        doc = parse_config_dict({"kind": "test", "id": "t1", "name": "Test 1"})
        assert isinstance(doc, TestDocument)
        assert doc.id == "t1"

    def test_auto_detect_defaults_by_defaults_key(self):
        doc = parse_config_dict({"defaults": {"timeout": 30}})
        assert isinstance(doc, DefaultsDocument)

    def test_auto_detect_suite_by_tests_key(self):
        doc = parse_config_dict({"name": "s1", "tests": ["t1"]})
        assert isinstance(doc, SuiteDocument)

    def test_auto_detect_test_by_id_key(self):
        doc = parse_config_dict({"id": "t1"})
        assert isinstance(doc, TestDocument)

    def test_ambiguous_raises(self):
        with pytest.raises(ValueError, match="Cannot determine document kind"):
            parse_config_dict({"description": "no kind, no id, no defaults, no tests"})


# ── Merge semantics ──────────────────────────────────────────────────────

class TestDeepMerge:
    def test_scalar_replace(self):
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_scalar_none_inherits_parent(self):
        assert deep_merge({"a": 1}, {"a": None}) == {"a": 1}

    def test_dict_deep_merge(self):
        result = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3, "d": 4}})
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_list_replace_default(self):
        policy = MergePolicy(list_strategy="replace")
        assert deep_merge({"x": [1, 2]}, {"x": [3]}, policy) == {"x": [3]}

    def test_list_append(self):
        policy = MergePolicy(list_strategy="append")
        assert deep_merge({"x": [1, 2]}, {"x": [3]}, policy) == {"x": [1, 2, 3]}

    def test_field_override_append(self):
        policy = MergePolicy(list_strategy="replace", field_overrides={"tags": "append"})
        assert deep_merge({"tags": ["a"]}, {"tags": ["b"]}, policy) == {"tags": ["a", "b"]}

    def test_tags_always_union_dedup(self):
        # tags union regardless of policy
        policy = MergePolicy(list_strategy="replace")
        result = deep_merge({"tags": ["a", "b"]}, {"tags": ["b", "c"]}, policy)
        assert result == {"tags": ["a", "b", "c"]}

    def test_no_mutation(self):
        parent = {"a": {"b": 1}}
        child = {"a": {"c": 2}}
        deep_merge(parent, child)
        assert parent == {"a": {"b": 1}}
        assert child == {"a": {"c": 2}}


class TestResolveTest:
    def test_builtin_defaults_applied(self):
        resolved = resolve_test(BUILTIN_DEFAULTS, TestConfig(id="t1"))
        assert resolved.id == "t1"
        assert resolved.enabled is True
        assert resolved.evaluation.name == "exact_match"

    def test_child_overrides_parent(self):
        resolved = resolve_test(
            BUILTIN_DEFAULTS,
            TestConfig(id="t1", timeout=999),
        )
        assert resolved.timeout == 999

    def test_tags_union_across_layers(self):
        resolved = resolve_test(
            BUILTIN_DEFAULTS,
            TestConfig(tags=["layer1"]),
            TestConfig(tags=["layer2", "layer3"]),
        )
        assert "layer1" in resolved.tags
        assert "layer2" in resolved.tags
        assert "layer3" in resolved.tags


# ── Validation rules: cross-field constraints ────────────────────────────

class TestPromptTemplateValidation:
    def test_ref_and_text_mutually_exclusive(self):
        with pytest.raises(Exception, match="mutually exclusive"):
            PromptTemplate(ref="p.txt", text="inline")

    def test_requires_one_of(self):
        with pytest.raises(Exception, match="requires one of"):
            PromptTemplate()

    def test_variant_only_ok(self):
        pt = PromptTemplate(variant="compact")
        assert pt.variant == "compact"


class TestDatasetReferenceValidation:
    def test_huggingface_requires_id(self):
        with pytest.raises(Exception, match="huggingface_id"):
            DatasetReference(name="d", format="huggingface")

    def test_inline_requires_data(self):
        with pytest.raises(Exception, match="inline_data"):
            DatasetReference(name="d", format="inline")

    def test_csv_requires_path(self):
        with pytest.raises(Exception, match="path"):
            DatasetReference(name="d", format="csv")

    def test_valid_huggingface(self):
        ds = DatasetReference(name="squad", format="huggingface", huggingface_id="squad")
        assert ds.huggingface_id == "squad"

    def test_valid_inline(self):
        ds = DatasetReference(name="d", format="inline", inline_data=[{"a": 1}])
        assert ds.inline_data == [{"a": 1}]


class TestMatrixConfigValidation:
    def test_explicit_requires_combinations(self):
        with pytest.raises(Exception, match="explicit_combinations"):
            MatrixConfig(strategy="explicit")

    def test_sample_requires_size(self):
        with pytest.raises(Exception, match="sample_size"):
            MatrixConfig(strategy="sample")

    def test_full_ok(self):
        m = MatrixConfig(strategy="full", max_cases=50)
        assert m.max_cases == 50


class TestModelEligibilityValidation:
    def test_required_excluded_overlap(self):
        with pytest.raises(Exception, match="overlap"):
            ModelEligibility(required=["m1"], excluded=["m1"])

    def test_no_overlap_ok(self):
        me = ModelEligibility(required=["m1"], excluded=["m2"])
        assert me.required == ["m1"]


class TestTestDocumentValidation:
    def test_matrix_requires_parameters(self):
        with pytest.raises(Exception, match="parameters"):
            TestDocument(
                id="t1", kind="test", schema_version="1.0.0",
                matrix=MatrixConfig(strategy="full"),
            )

    def test_valid_with_parameters(self):
        doc = TestDocument(
            id="t1", kind="test", schema_version="1.0.0",
            parameters={"x": [1, 2]},
            matrix=MatrixConfig(strategy="full"),
        )
        assert doc.parameters == {"x": [1, 2]}


# ── Type constraints ─────────────────────────────────────────────────────

class TestTypeConstraints:
    def test_temperature_range(self):
        with pytest.raises(Exception):
            ModelParameters(temperature=3.0)

    def test_timeout_positive(self):
        with pytest.raises(Exception):
            TestDocument(id="t1", timeout=-1)

    def test_pass_threshold_range(self):
        with pytest.raises(Exception):
            EvaluatorReference(name="x", pass_threshold=1.5)

    def test_repetitions_min(self):
        with pytest.raises(Exception):
            TestDocument(id="t1", repetitions=0)

    def test_valid_temperature_zero(self):
        mp = ModelParameters(temperature=0.0)
        assert mp.temperature == 0.0


# ── Enum values ──────────────────────────────────────────────────────────

class TestEnumValues:
    def test_invalid_difficulty(self):
        with pytest.raises(Exception):
            TestDocument(id="t1", difficulty="impossible")

    def test_invalid_kind(self):
        with pytest.raises(Exception):
            parse_config_dict({"kind": "unknown", "id": "x"})

    def test_invalid_scoring_category(self):
        with pytest.raises(Exception):
            TestConfig(scoring_categories=["nonexistent"])


# ── JSON Schema export ──────────────────────────────────────────────────

class TestJsonSchemaExport:
    def test_export_returns_dict(self):
        schema = export_json_schema()
        assert isinstance(schema, dict)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "title" in schema
        assert "$defs" in schema

    def test_schema_has_defs_for_document_types(self):
        schema = export_json_schema()
        defs = schema["$defs"]
        # Should contain definitions for the document and sub-models.
        assert any("Defaults" in k for k in defs)
        assert any("Suite" in k for k in defs)
        assert any("Test" in k for k in defs)


# ── Reference example integration ───────────────────────────────────────

class TestReferenceExample:
    """End-to-end: parse and resolve the reference example file."""

    @pytest.fixture(scope="class")
    def example_docs(self):
        import pathlib
        path = pathlib.Path(__file__).parent / "tests" / "examples" / "full_feature_example.yaml"
        with open(path) as f:
            return list(yaml.safe_load_all(f))

    def test_three_documents(self, example_docs):
        assert len(example_docs) == 3

    def test_defaults_doc_valid(self, example_docs):
        doc = parse_config_dict(example_docs[0])
        assert isinstance(doc, DefaultsDocument)
        assert doc.defaults.enabled is True

    def test_suite_doc_valid(self, example_docs):
        doc = parse_config_dict(example_docs[1])
        assert isinstance(doc, SuiteDocument)
        assert doc.name == "sugarcube_core"
        assert len(doc.tests) == 3

    def test_test_doc_valid(self, example_docs):
        doc = parse_config_dict(example_docs[2])
        assert isinstance(doc, TestDocument)
        assert doc.id == "sugarcube_direction_matrix"

    def test_full_layered_resolution(self, example_docs):
        """Resolve the matrix test across all 4 layers."""
        defaults_doc = parse_config_dict(example_docs[0])
        suite_doc = parse_config_dict(example_docs[1])
        test_doc = parse_config_dict(example_docs[2])

        resolved = resolve_test(
            BUILTIN_DEFAULTS,
            defaults_doc.defaults,
            suite_doc.defaults,
            test_doc.to_test_config(),
        )
        assert resolved.id == "sugarcube_direction_matrix"
        # tags unioned across layers
        assert "sugarcube" in resolved.tags
        assert "core" in resolved.tags
        assert "matrix" in resolved.tags
        # suite override (temperature 0.0) preserved (test didn't override)
        assert resolved.model_parameters.temperature == 0.0
        # suite override (num_predict 512) preserved
        assert resolved.model_parameters.num_predict == 512
        # test override (repetitions 5)
        assert resolved.repetitions == 5
        # evaluator overridden from exact_match to sugarcube_rubric
        assert resolved.evaluation.name == "sugarcube_rubric"
        # test subset of scoring categories
        assert resolved.scoring_categories == [
            "markup_compliance", "passage_structure", "macro_usage"
        ]
