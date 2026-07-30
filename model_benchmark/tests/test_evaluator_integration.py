#!/usr/bin/env python3
"""Integration test: config referencing a custom evaluator + dataset loads and runs.

This is the acceptance-criteria test for task t_b8e82f29: "a config
referencing a custom evaluator + dataset loads and runs successfully."

It demonstrates the full pipeline:
1. Parse a YAML test config (using config_schema.parse_config_dict).
2. Resolve the config through the layered hierarchy (resolve_test).
3. Load the referenced dataset (DatasetLoader).
4. Look up the referenced evaluator (evaluators registry).
5. Run the evaluator on each dataset row.
6. Collect and verify results.
"""
from __future__ import annotations

import pytest
import yaml

from model_benchmark.config_schema import (
    BUILTIN_DEFAULTS,
    EvaluatorReference,
    TestConfig,
    TestDocument,
    parse_config_dict,
    resolve_test,
)
from model_benchmark.dataset_loader import DatasetLoader
from model_benchmark.evaluators import evaluate_response, get_evaluator, list_evaluators


# ── Test config (inline YAML) ─────────────────────────────────────────────

INTEGRATION_CONFIG_YAML = """
schema_version: "1.0.0"
kind: test

id: integration_evaluator_dataset_test
name: Integration test — custom evaluator + dataset
description: >
  Acceptance test for t_b8e82f29: a config referencing the section_presence
  custom evaluator and the qa_simple.csv dataset loads and runs successfully.
version: "1.0.0"
enabled: true
difficulty: easy
tags: ["integration", "evaluator", "dataset"]

input: "What is the capital of France?"
expected:
  answer: Paris
  answer_type: exact
  contains:
    - "Paris"

evaluation:
  name: exact_match
  pass_threshold: 1.0
  max_score: 1.0

dataset:
  name: qa_simple
  format: csv
  path: datasets/qa_simple.csv
  filters:
    difficulty: easy
"""

# A second config that uses the custom section_presence evaluator
CUSTOM_EVALUATOR_CONFIG_YAML = """
schema_version: "1.0.0"
kind: test

id: integration_custom_evaluator_test
name: Integration test — custom evaluator plugin
description: >
  Tests that the section_presence plugin (auto-discovered from
  tests/evaluators/) works end-to-end with a dataset.
version: "1.0.0"
enabled: true
difficulty: medium
tags: ["integration", "custom-evaluator"]

input: |
  PROSE: The apprentice opened the book.
  CHOICES:
  - Read it | A bold choice
  - Close it | The safe path
  SUMMARY:
  The apprentice made a decision.
expected:
  contains:
    - "PROSE:"
    - "CHOICES:"
    - "SUMMARY:"
  must_parse_as: sugarcube_passage

evaluation:
  name: section_presence
  type: section_check
  pass_threshold: 1.0
  max_score: 1.0
  deterministic: true

dataset:
  name: directions
  format: jsonl
  path: datasets/directions.jsonl
  filters:
    variant: compact
"""


# ── Integration tests ─────────────────────────────────────────────────────

class TestIntegrationConfigLoadAndRun:
    """Acceptance criterion: config referencing custom evaluator + dataset loads and runs."""

    def test_config_parses_successfully(self):
        """Step 1: Parse the test config YAML into a TestDocument."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        assert isinstance(doc, TestDocument)
        assert doc.id == "integration_evaluator_dataset_test"

    def test_config_references_evaluator(self):
        """The parsed config must reference an evaluator by name."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        assert doc.evaluation is not None
        assert doc.evaluation.name == "exact_match"

    def test_config_references_dataset(self):
        """The parsed config must reference a dataset."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        assert doc.dataset is not None
        assert doc.dataset.name == "qa_simple"
        assert doc.dataset.format == "csv"

    def test_resolved_test_has_evaluator_and_dataset(self):
        """Step 2: Resolve through the layered hierarchy."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())
        assert test_config.evaluation is not None
        assert test_config.evaluation.name == "exact_match"
        assert test_config.dataset is not None
        assert test_config.dataset.name == "qa_simple"

    def test_dataset_loads(self):
        """Step 3: Load the referenced dataset."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)
        assert len(loaded.rows) > 0
        assert "question" in loaded.rows[0]
        assert "answer" in loaded.rows[0]
        # Filter applied: only easy rows
        assert all(r["difficulty"] == "easy" for r in loaded.rows)

    def test_evaluator_resolves(self):
        """Step 4: Look up the evaluator by name from the config."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())
        ev_name = test_config.evaluation.name
        ev = get_evaluator(ev_name)
        assert ev.name == "exact_match"

    def test_full_pipeline_runs(self):
        """Step 5+6: Load dataset, run evaluator on each row, collect results.

        This is the key acceptance test — the full end-to-end pipeline.
        """
        # 1. Parse and resolve config
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        # 2. Load dataset
        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)
        assert len(loaded.rows) > 0

        # 3. Get evaluator params from config
        eval_ref = test_config.evaluation
        ev_params = eval_ref.params or {}
        pass_threshold = eval_ref.pass_threshold

        # 4. Run evaluator on each dataset row
        results = []
        for row in loaded.rows:
            expected = {
                "answer": row["answer"],
                "contains": [row["answer"]],
            }
            # Simulate a model response (in real use, this comes from Ollama)
            simulated_response = row["answer"]  # correct answer
            result = evaluate_response(
                eval_ref.name,
                simulated_response,
                expected=expected,
                params=ev_params,
                pass_threshold=pass_threshold,
            )
            results.append(result)

        # 5. Verify results
        assert len(results) == len(loaded.rows)
        assert all(r.passed for r in results), (
            f"Not all passed: {[(r.passed, r.details) for r in results]}"
        )
        assert all(r.score == 1.0 for r in results)

    def test_full_pipeline_with_failures(self):
        """The pipeline should also correctly report failures."""
        data = yaml.safe_load(INTEGRATION_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)

        eval_ref = test_config.evaluation
        results = []
        for row in loaded.rows:
            # Simulate WRONG response
            simulated_response = "WRONG ANSWER"
            result = evaluate_response(
                eval_ref.name,
                simulated_response,
                expected={"answer": row["answer"]},
                params=eval_ref.params or {},
                pass_threshold=eval_ref.pass_threshold,
            )
            results.append(result)

        assert len(results) == len(loaded.rows)
        assert all(not r.passed for r in results)
        assert all(r.score == 0.0 for r in results)


class TestIntegrationCustomEvaluatorAndDataset:
    """Acceptance test: custom evaluator (plugin) + dataset loads and runs."""

    def test_custom_evaluator_available(self):
        """The section_presence plugin must be auto-discovered."""
        names = list_evaluators()
        assert "section_presence" in names

    def test_custom_evaluator_config_parses(self):
        data = yaml.safe_load(CUSTOM_EVALUATOR_CONFIG_YAML)
        doc = parse_config_dict(data)
        assert doc.evaluation.name == "section_presence"
        assert doc.dataset.name == "directions"

    def test_custom_evaluator_dataset_loads(self):
        data = yaml.safe_load(CUSTOM_EVALUATOR_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)
        assert len(loaded.rows) > 0
        # Filter: only compact variant rows
        assert all(r["variant"] == "compact" for r in loaded.rows)

    def test_custom_evaluator_full_pipeline(self):
        """Custom evaluator + dataset: full end-to-end pipeline."""
        # 1. Parse and resolve
        data = yaml.safe_load(CUSTOM_EVALUATOR_CONFIG_YAML)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        # 2. Load dataset
        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)
        assert len(loaded.rows) > 0

        # 3. Get evaluator
        eval_ref = test_config.evaluation
        assert eval_ref.name == "section_presence"

        # 4. Run evaluator on each row
        # Use the expected sections from the test config
        expected = {
            "contains": test_config.expected.contains or ["PROSE:", "CHOICES:", "SUMMARY:"],
        }
        # Simulate a correct SugarCube response
        correct_response = "PROSE: text\nCHOICES:\n- A | B\nSUMMARY:\ndone"
        results = []
        for row in loaded.rows:
            result = evaluate_response(
                eval_ref.name,
                correct_response,
                expected=expected,
                params=eval_ref.params or {},
                pass_threshold=eval_ref.pass_threshold,
            )
            results.append(result)

        # 5. Verify
        assert len(results) == len(loaded.rows)
        assert all(r.passed for r in results), (
            f"Custom evaluator failed: {[(r.passed, r.details) for r in results]}"
        )


class TestIntegrationSubstringRegexWithDataset:
    """Test substring_regex evaluator with a dataset (combined check)."""

    def test_substring_evaluator_with_directions_dataset(self):
        """Run substring_regex on directions.jsonl, checking expected_sections."""
        config_yaml = """
schema_version: "1.0.0"
kind: test
id: substring_directions_test
name: Substring regex with directions dataset
evaluation:
  name: substring_regex
  pass_threshold: 1.0
dataset:
  name: directions
  format: jsonl
  path: datasets/directions.jsonl
"""
        data = yaml.safe_load(config_yaml)
        doc = parse_config_dict(data)
        test_config = resolve_test(BUILTIN_DEFAULTS, doc.to_test_config())

        loader = DatasetLoader(
            base_dir=__import__("pathlib").Path(__file__).parent
        )
        loaded = loader.load(test_config.dataset)
        assert len(loaded.rows) == 5

        # For each row, check that the expected_sections are present in
        # a simulated correct response.
        results = []
        for row in loaded.rows:
            sections = row.get("expected_sections", [])
            # Simulate a response containing all expected sections
            simulated = "\n".join(sections)
            result = evaluate_response(
                "substring_regex",
                simulated,
                expected={"contains": sections},
                pass_threshold=1.0,
            )
            results.append(result)

        assert all(r.passed for r in results)
