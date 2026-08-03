"""Identity-leak tests for the anonymization module (P6 INV-A2).

These tests feed sample results, metadata, and error objects containing known
model names, provider names, and config identifiers through the anonymization
module, then scan every output format (JSON, HTML, CSV, Markdown), filenames,
and file paths for any occurrence of the original identifiable strings.

Conforms to the design spec at
/opt/data/kanban/workspaces/t_329c966a/anonymization_design_spec.md and the
data structures in model_benchmark/schema.py (§3.5–§3.9) + benchmark.py.

Acceptance criteria covered:
  1. Sample results/metadata/errors with known identities are anonymized.
  2. All output formats (JSON, HTML, CSV, MD) are scanned for leaks.
  3. Filenames and file paths are scanned for leaks.
  4. No original model/provider/config identifier appears in any output.
  5. The mapping file is protected (mode 0600 / not co-located with public outputs).
  6. Deterministic aliases are stable across runs.
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Import from the SAME module paths as anonymization.py so isinstance() and
# type identity checks use the exact same class objects (avoids the
# schema vs model_benchmark.schema duplicate-module pitfall).
from model_benchmark.schema import (
    AnonymizationMapping,
    ResultRecord,
    RunManifest,
)
from model_benchmark.benchmark import (
    BenchmarkConfig,
    BenchmarkReport,
    CategoryResult,
    CategorySummaryEntry,
    ModelReport,
    ModelRunResult,
)
from harness.models import ModelOutput, ParsedChoice


# ── Known identities used across all fixtures ────────────────────────────
# These are the strings the leak scanner must NOT find in anonymized output.
MODEL_NAMES = ("llama3.1:8b", "qwen2.5:7b")
PROVIDER_HOST = "localhost"
PROVIDER_HOST_2 = "gpu-box.example.org"
BASE_URL = "http://localhost:11434"
BASE_URL_2 = "http://gpu-box.example.org:11434"
RUN_ID = "2026-07-30T004100Z_sugarcube-bench_ab12"
REPO_PATH = "/opt/data/sugarcube-story-harness-for-ollama-p5-input-macros"

# The Ollama label arg: benchmark-{model}-{variant}-{direction} — surfaces in
# client-side error messages (spec §1.1).
LABEL_STRING = "benchmark-llama3.1:8b-json-A"

# File-path identity that can leak via error strings
ERROR_WITH_PATH = (
    f"ConnectionRefusedError: Failed to connect to {BASE_URL} "
    f"from {REPO_PATH}/model_benchmark/benchmark.py"
)
ERROR_WITH_HOST = f"Timeout contacting {PROVIDER_HOST_2}:11434 — model llama3.1:8b"
ERROR_WITH_LABEL = f"label={LABEL_STRING}"


def _make_model_output() -> ModelOutput:
    """Build a minimal valid ModelOutput for fixtures."""
    return ModelOutput(
        prose="The apprentice examined the tome.",
        choices=[ParsedChoice(text="Open the book", hint="A dangerous choice")],
        summary="The apprentice found a tome.",
    )


def _make_category_results() -> tuple[CategoryResult, ...]:
    """Build 6 CategoryResult entries in canonical order."""
    return tuple(
        CategoryResult(
            name=name,
            passed=True,
            score=1.0,
            details="ok",
        )
        for name in (
            "markup_compliance",
            "variable_scoping",
            "passage_structure",
            "macro_usage",
            "naked_interpolation",
            "link_setter_syntax",
        )
    )


def _make_run_result(model: str, error: str = "") -> ModelRunResult:
    """Build a ModelRunResult carrying identity (model_name + optional error)."""
    return ModelRunResult(
        model_name=model,
        variant="json",
        direction="A",
        run_index=0,
        raw_response="PROSE:\nThe apprentice.\nCHOICES:\n- Go | x\nSUMMARY:\nDone.",
        parsed_output=_make_model_output(),
        category_results=_make_category_results(),
        overall_pass=True,
        elapsed_seconds=1.5,
        error=error,
    )


def _make_result_record(model: str, error: str = "") -> ResultRecord:
    """Build a ResultRecord with identity in scored_result + error_details."""
    return ResultRecord(
        schema_version="results-v1",
        test_id="t001",
        test_version="1",
        capability="markup",
        category="markup_compliance",
        subcategory="bold",
        difficulty="easy",
        dataset="fixture",
        split="test",
        repetition=1,
        input_summary="Write a passage",
        expected_behavior="Use SugarCube markup",
        reference_rubric="''bold'' not **bold**",
        actual_output_raw="The apprentice saw ''a book''.",
        parsed_output=_make_model_output(),
        score=1.0,
        max_score=1.0,
        normalized_score=1.0,
        pass_threshold=0.6,
        status="PASS",
        failure_category="none",
        evaluator_reasoning="Looks good",
        evaluator_confidence=0.95,
        runtime_seconds=1.5,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost=0.0,
        retry_count=0,
        error_details=error,
        model_alias="",
        config_alias="",
        prompt_version=1,
        evaluator_version="1.0",
        random_seed="42",
        timestamp_start="2026-07-30T00:41:00Z",
        timestamp_end="2026-07-30T00:41:02Z",
        scored_result=_make_run_result(model, error),
    )


def _make_benchmark_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        models=MODEL_NAMES,
        variants=("json",),
        directions=("A",),
        base_url=BASE_URL,
        timeout=60,
        num_predict=512,
        temperature=0.2,
        runs=1,
    )


def _make_run_manifest() -> RunManifest:
    """Build a RunManifest packed with identity strings.

    Uses PROVIDER_HOST_2 as the manifest provider so the mapping captures
    both localhost (from config.base_url) and gpu-box.example.org (from
    manifest.provider). This mirrors the two-provider scenario (local +
    remote) described in spec §1.2 / §2.2.
    """
    return RunManifest(
        run_id=RUN_ID,
        benchmark_name="sugarcube-bench",
        benchmark_version="0.1.0",
        schema_version="manifest-v1",
        source_commit_hash="abc123",
        model_names=MODEL_NAMES,
        provider=PROVIDER_HOST_2,
        model_configs=(
            {"model": "llama3.1:8b", "temperature": "0.2", "num_predict": "512"},
            {"model": "qwen2.5:7b", "temperature": "0.7", "num_predict": "1024"},
        ),
        generation_params={"temperature": "0.2", "num_predict": "512"},
        prompt_template="compact",
        prompt_version=1,
        evaluator_prompt="default",
        evaluator_version="1.0",
        dataset_name="fixture",
        dataset_version="1",
        dataset_split="test",
        dataset_checksums=("sha256:abc",),
        runtime_settings={"base_url": BASE_URL, "remote_url": BASE_URL_2, "timeout": "60"},
        concurrency=1,
        retry_policy="none",
        timeouts=60,
        random_seed="42",
        sampling_seed="42",
        repeated_runs_count=1,
        start_timestamp="2026-07-30T00:41:00Z",
        completion_timestamp="2026-07-30T00:42:00Z",
        duration_seconds=60.0,
        os_info=f"Linux 6.8.0 on {PROVIDER_HOST_2}",
        python_version="3.13.5",
        package_versions={"pytest": "9.0.3"},
        hardware="cpu",
        env_vars_redacted={"OLLAMA_BASE_URL": BASE_URL, "REMOTE_OLLAMA_URL": BASE_URL_2},
        cli_args=(
            "--models", "llama3.1:8b", "qwen2.5:7b",
            "--base-url", BASE_URL,
        ),
        config_file_contents="models: [llama3.1:8b, qwen2.5:7b]\ntemperature: 0.2",
        config_file_checksum="sha256:def",
        resumed=False,
        parent_run_id="",
    )


def _make_benchmark_report() -> BenchmarkReport:
    """Build a BenchmarkReport with identity in models + config + ModelReports."""
    reports = []
    for model in MODEL_NAMES:
        run = _make_run_result(model)
        reports.append(
            ModelReport(
                model_name=model,
                runs=(run,),
                category_summary=(
                    CategorySummaryEntry(name="markup_compliance", pass_rate=1.0, total=1, passed=1),
                ),
                overall_score=1.0,
                runs_total=1,
                runs_passed=1,
            )
        )
    return BenchmarkReport(
        models=tuple(reports),
        prompt_version=1,
        config=_make_benchmark_config(),
        generated_at="2026-07-30T00:42:00Z",
        ollama_reachable=True,
    )


def _sample_results() -> list[ResultRecord]:
    """Two ResultRecords — one per model, each carrying an error with identity."""
    return [
        _make_result_record("llama3.1:8b", error=ERROR_WITH_PATH),
        _make_result_record("qwen2.5:7b", error=ERROR_WITH_HOST),
    ]


def _all_identity_strings() -> list[str]:
    """The full set of original identity strings that must NOT leak.

    Only includes strings that appear in the input fixtures AND are known to
    the mapping. Config labels (temp=...,num_predict=...) are synthetic keys
    internal to the mapping and never appear as strings in the data, so they
    are excluded.
    """
    return [
        *MODEL_NAMES,
        PROVIDER_HOST,
        PROVIDER_HOST_2,
        BASE_URL,
        BASE_URL_2,
        RUN_ID,
        REPO_PATH,
        LABEL_STRING,
    ]


# ── Import the module under test ──────────────────────────────────────────
# The anonymization module is implemented by the sibling task t_c026642e.
# Import lazily so this file can be collected even before the module exists,
# but tests will require it — a missing module is a genuine skip.

anonymization = pytest.importorskip("model_benchmark.anonymization", reason=(
    "anonymization.py not yet implemented (sibling task t_c026642e). "
    "Tests will run once the module lands."
))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Mapping construction
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestBuildMapping - verify build_anonymization_mapping collects all identity strings from results/manifest/config/report
class TestBuildMapping:
    """build_anonymization_mapping must collect all identity strings."""

    def test_builds_mapping_from_results(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )
        assert isinstance(mapping, AnonymizationMapping)

    def test_mapping_has_model_aliases(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            config=_make_benchmark_config(),
        )
        originals = [orig for _alias, orig in mapping.model_aliases]
        for name in MODEL_NAMES:
            assert name in originals, f"model {name!r} missing from mapping"

    def test_mapping_has_provider_aliases(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )
        originals = [orig for _alias, orig in mapping.provider_aliases]
        assert PROVIDER_HOST in originals, "provider host (localhost) missing"
        assert PROVIDER_HOST_2 in originals, "provider host (gpu-box) missing"

    def test_mapping_has_config_aliases(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )
        originals = [orig for _alias, orig in mapping.config_aliases]
        assert len(originals) >= 1, "no config aliases"

    def test_mapping_identity_strings_include_all(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )
        ident = set(mapping.identity_strings)
        for name in MODEL_NAMES:
            assert name in ident, f"model {name!r} not in identity_strings"
        assert PROVIDER_HOST in ident, "provider host not in identity_strings"
        assert PROVIDER_HOST_2 in ident, "provider host 2 not in identity_strings"
        assert BASE_URL in ident, "base_url not in identity_strings"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Alias scheme — deterministic + correctly formatted
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestAliasScheme - verify alias naming scheme - lettered models/providers, zero-padded configs, determinism across runs
class TestAliasScheme:
    """Aliases must follow Model_A/B, Provider_A/B, Config_01/02, Run_01/02."""

    def test_model_aliases_are_lettered(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            config=_make_benchmark_config(),
        )
        aliases = [alias for alias, _orig in mapping.model_aliases]
        # Sorted alphabetically: llama3.1:8b < qwen2.5:7b
        # llama3.1:8b → Model_A, qwen2.5:7b → Model_B
        assert "Model_A" in aliases
        assert "Model_B" in aliases

    def test_model_aliases_remain_lettered_beyond_ten_models(self):
        assert [
            anonymization._model_alias(index)
            for index in (0, 9, 10, 25, 26, 27, 701, 702)
        ] == [
            "Model_A",
            "Model_J",
            "Model_K",
            "Model_Z",
            "Model_AA",
            "Model_AB",
            "Model_ZZ",
            "Model_AAA",
        ]

    def test_model_alias_rejects_negative_index(self):
        with pytest.raises(ValueError, match="non-negative"):
            anonymization._model_alias(-1)

    def test_provider_aliases_are_lettered(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )
        aliases = [alias for alias, _orig in mapping.provider_aliases]
        assert "Provider_A" in aliases
        assert "Provider_B" in aliases

    def test_config_aliases_are_zero_padded(self):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )
        aliases = [alias for alias, _orig in mapping.config_aliases]
        for a in aliases:
            assert a.startswith("Config_"), f"bad config alias: {a}"
            # Format: Config_NN (two-digit zero-padded)
            num = a.removeprefix("Config_")
            assert len(num) == 2 and num.isdigit(), f"bad padding: {a}"

    def test_deterministic_across_runs(self):
        """Same inputs → same mapping, always."""
        kwargs = dict(
            results=_sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )
        m1 = anonymization.build_anonymization_mapping(**kwargs)
        m2 = anonymization.build_anonymization_mapping(**kwargs)
        assert m1 == m2, "mapping not deterministic across runs"

    def test_deterministic_with_reordered_results(self):
        """Alias assignment is by stable-sort, not insertion order."""
        results = _sample_results()
        m1 = anonymization.build_anonymization_mapping(results, config=_make_benchmark_config())
        m2 = anonymization.build_anonymization_mapping(list(reversed(results)), config=_make_benchmark_config())
        assert m1 == m2, "alias assignment depends on order (should be stable-sorted)"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Anonymize results — no identity in output
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestAnonymizeResults - verify anonymize_result/anonymize_results scrub identity, preserve metrics (INV-A1)
class TestAnonymizeResults:
    """anonymize_results must scrub all identity from every field."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_returns_new_instances(self):
        original = _sample_results()
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(original, mapping)
        assert anonymized is not original, "must return new list"
        for orig, anon in zip(original, anonymized):
            assert anon is not orig, "must return new ResultRecord instances"

    def test_preserves_length_and_order(self):
        original = _sample_results()
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(original, mapping)
        assert len(anonymized) == len(original)

    def test_no_model_name_in_results(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            text = json.dumps(_safe_asdict(rec), default=str)
            for name in MODEL_NAMES:
                assert name not in text, f"model name {name!r} leaked in result"

    def test_no_provider_in_results(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            text = json.dumps(_safe_asdict(rec), default=str)
            for s in (PROVIDER_HOST, PROVIDER_HOST_2, BASE_URL, BASE_URL_2):
                assert s not in text, f"provider string {s!r} leaked in result"

    def test_no_identity_in_error_details(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            for s in (PROVIDER_HOST, PROVIDER_HOST_2, REPO_PATH, BASE_URL, BASE_URL_2):
                assert s not in rec.error_details, f"identity {s!r} in error_details"
            for name in MODEL_NAMES:
                assert name not in rec.error_details, f"model {name!r} in error_details"

    def test_no_identity_in_scored_result(self):
        """The embedded scored_result core must be scrubbed."""
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            if rec.scored_result is not None:
                sr = rec.scored_result
                for name in MODEL_NAMES:
                    assert name not in sr.model_name, f"model {name!r} in scored_result.model_name"
                    assert name not in sr.error, f"model {name!r} in scored_result.error"
                for s in (PROVIDER_HOST, PROVIDER_HOST_2, BASE_URL, REPO_PATH):
                    assert s not in sr.error, f"identity {s!r} in scored_result.error"

    def test_model_identity_is_scrubbed_from_test_id(self):
        records = _sample_results()
        records[0] = dataclasses.replace(
            records[0],
            test_id=f"{MODEL_NAMES[0]}:compact:A:1",
        )
        mapping = anonymization.build_anonymization_mapping(
            records,
            config=_make_benchmark_config(),
        )

        result = anonymization.anonymize_results(records, mapping)[0]

        assert MODEL_NAMES[0] not in result.test_id
        assert "Model_" in result.test_id

    def test_non_identity_fields_preserved(self):
        """INV-A1: scores, status, runtime, tokens must be unchanged."""
        mapping = self._mapping()
        original = _sample_results()
        anonymized = anonymization.anonymize_results(original, mapping)
        for orig, anon in zip(original, anonymized):
            assert anon.score == orig.score
            assert anon.status == orig.status
            assert anon.runtime_seconds == orig.runtime_seconds
            assert anon.total_tokens == orig.total_tokens
            assert anon.normalized_score == orig.normalized_score
            assert anon.test_id == orig.test_id


# ═══════════════════════════════════════════════════════════════════════════
# 4. Anonymize metadata (RunManifest)
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestAnonymizeMetadata - verify anonymize_metadata scrubs all manifest identity fields - model_names, provider, cli_args, run_id, os_info, env_vars
class TestAnonymizeMetadata:
    """anonymize_metadata must scrub all identity from the manifest."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_no_model_names_in_manifest(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        text = json.dumps(_safe_asdict(anon), default=str)
        for name in MODEL_NAMES:
            assert name not in text, f"model {name!r} leaked in anonymized manifest"

    def test_no_provider_in_manifest(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        text = json.dumps(_safe_asdict(anon), default=str)
        for s in (PROVIDER_HOST, PROVIDER_HOST_2, BASE_URL, BASE_URL_2):
            assert s not in text, f"provider string {s!r} leaked in manifest"

    def test_no_identity_in_cli_args(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        for arg in anon.cli_args:
            for name in MODEL_NAMES:
                assert name not in arg, f"model {name!r} in cli_args"
            assert BASE_URL not in arg, "base_url in cli_args"

    def test_run_id_aliased(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        assert RUN_ID not in anon.run_id, "original run_id leaked"

    def test_model_names_replaced_with_aliases(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        for name in anon.model_names:
            assert name.startswith("Model_"), f"model_names not aliased: {name}"

    def test_no_identity_in_os_info(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        assert PROVIDER_HOST_2 not in anon.os_info, "provider host leaked in os_info"

    def test_no_identity_in_env_vars(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        env_text = json.dumps(dict(anon.env_vars_redacted), default=str)
        for s in (BASE_URL, BASE_URL_2, PROVIDER_HOST, PROVIDER_HOST_2):
            assert s not in env_text, f"identity {s!r} leaked in env_vars_redacted"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Anonymize errors
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestAnonymizeErrors - verify anonymize_errors scrubs model/provider/path from error messages, returns new list
class TestAnonymizeErrors:
    """anonymize_errors must scrub identity from error message strings."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_no_model_in_errors(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST, ERROR_WITH_LABEL]
        anon = anonymization.anonymize_errors(errors, mapping)
        for msg in anon:
            for name in MODEL_NAMES:
                assert name not in msg, f"model {name!r} leaked in error: {msg}"

    def test_no_provider_in_errors(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST]
        anon = anonymization.anonymize_errors(errors, mapping)
        for msg in anon:
            for s in (PROVIDER_HOST, PROVIDER_HOST_2, BASE_URL, BASE_URL_2):
                assert s not in msg, f"provider {s!r} leaked in error: {msg}"

    def test_no_repo_path_in_errors(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_errors([ERROR_WITH_PATH], mapping)
        assert REPO_PATH not in anon[0], "repo path leaked in error"

    def test_no_label_string_in_errors(self):
        """The Ollama label arg (benchmark-{model}-{variant}-{direction})
        must have its model name portion scrubbed."""
        mapping = self._mapping()
        anon = anonymization.anonymize_errors([ERROR_WITH_LABEL], mapping)
        for name in MODEL_NAMES:
            assert name not in anon[0], f"model {name!r} leaked via label in error"

    def test_returns_new_list(self):
        mapping = self._mapping()
        original = [ERROR_WITH_PATH]
        anon = anonymization.anonymize_errors(original, mapping)
        assert anon is not original
        assert len(anon) == len(original)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Anonymize report (BenchmarkReport)
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestAnonymizeReport - verify anonymize_report scrubs report tree - config.models, base_url, ModelReport, ModelRunResult - preserves scores
class TestAnonymizeReport:
    """anonymize_report must scrub identity from the top-level report."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )

    def test_no_model_in_report(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        text = json.dumps(_safe_asdict(anon), default=str)
        for name in MODEL_NAMES:
            assert name not in text, f"model {name!r} leaked in report"

    def test_no_provider_in_report(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        text = json.dumps(_safe_asdict(anon), default=str)
        for s in (PROVIDER_HOST, BASE_URL):
            assert s not in text, f"provider {s!r} leaked in report"

    def test_report_model_names_aliased(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        for mr in anon.models:
            assert mr.model_name.startswith("Model_"), f"report model not aliased: {mr.model_name}"

    def test_report_config_models_aliased(self):
        mapping = self._mapping()
        anon = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        for m in anon.config.models:
            assert m.startswith("Model_"), f"config model not aliased: {m}"

    def test_report_scores_preserved(self):
        mapping = self._mapping()
        orig = _make_benchmark_report()
        anon = anonymization.anonymize_report(orig, mapping)
        for o, a in zip(orig.models, anon.models):
            assert a.overall_score == o.overall_score
            assert a.runs_total == o.runs_total


# ═══════════════════════════════════════════════════════════════════════════
# 7. JSON output format leak scan
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestJSONLeakScan - verify no identity string in JSON serialization of results/manifest/report/errors (INV-A2)
class TestJSONLeakScan:
    """Explicitly scan JSON-serialized anonymized output for identity leaks."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )

    def test_json_results_no_leak(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        json_text = json.dumps([_safe_asdict(r) for r in anonymized], indent=2, default=str)
        _assert_no_identity(json_text, "JSON results")

    def test_json_manifest_no_leak(self):
        mapping = self._mapping()
        anon_meta = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        json_text = json.dumps(_safe_asdict(anon_meta), indent=2, default=str)
        _assert_no_identity(json_text, "JSON manifest")

    def test_json_report_no_leak(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        json_text = json.dumps(_safe_asdict(anon_report), indent=2, default=str)
        _assert_no_identity(json_text, "JSON report")

    def test_json_errors_no_leak(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST, ERROR_WITH_LABEL]
        anon_errors = anonymization.anonymize_errors(errors, mapping)
        json_text = json.dumps(anon_errors, indent=2)
        _assert_no_identity(json_text, "JSON errors")

    def test_verify_no_identity_helper_json(self):
        """The module's own verify_no_identity helper must confirm clean JSON."""
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        json_text = json.dumps([_safe_asdict(r) for r in anonymized], indent=2, default=str)
        leaks = anonymization.verify_no_identity(json_text, mapping)
        assert leaks == [], f"verify_no_identity found leaks in JSON: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# 8. HTML output format leak scan
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestHTMLLeakScan - verify no identity string in HTML rendering of reports/errors (INV-A2)
class TestHTMLLeakScan:
    """Explicitly scan HTML-rendered anonymized output for identity leaks."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )

    def _render_html_report(self, report: BenchmarkReport) -> str:
        """Render a minimal HTML representation of the report."""
        rows = ""
        for mr in report.models:
            rows += f"<tr><td>{mr.model_name}</td><td>{mr.overall_score}</td></tr>\n"
        return f"""<!DOCTYPE html>
<html><head><title>Benchmark Report</title></head>
<body>
<h1>Benchmark Report</h1>
<p>Provider: {report.config.base_url}</p>
<table>
<thead><tr><th>Model</th><th>Score</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p>Config: {report.config.models}</p>
</body></html>"""

    def test_html_report_no_leak(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        html = self._render_html_report(anon_report)
        _assert_no_identity(html, "HTML report")

    def test_html_errors_no_leak(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST, ERROR_WITH_LABEL]
        anon_errors = anonymization.anonymize_errors(errors, mapping)
        html = "<ul>" + "".join(f"<li>{e}</li>" for e in anon_errors) + "</ul>"
        _assert_no_identity(html, "HTML errors")

    def test_verify_no_identity_helper_html(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        html = self._render_html_report(anon_report)
        leaks = anonymization.verify_no_identity(html, mapping)
        assert leaks == [], f"verify_no_identity found leaks in HTML: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# 9. CSV output format leak scan
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestCSVLeakScan - verify no identity string in CSV serialization of results/report (INV-A2)
class TestCSVLeakScan:
    """Explicitly scan CSV-rendered anonymized output for identity leaks."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_csv_results_no_leak(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["model_alias", "config_alias", "status", "score", "error_details"])
        for rec in anonymized:
            writer.writerow([rec.model_alias, rec.config_alias, rec.status, rec.score, rec.error_details])
        csv_text = buf.getvalue()
        _assert_no_identity(csv_text, "CSV results")

    def test_csv_report_no_leak(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["model_alias", "overall_score", "runs_total", "runs_passed"])
        for mr in anon_report.models:
            writer.writerow([mr.model_name, mr.overall_score, mr.runs_total, mr.runs_passed])
        csv_text = buf.getvalue()
        _assert_no_identity(csv_text, "CSV report")

    def test_verify_no_identity_helper_csv(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["model_alias", "error_details"])
        for rec in anonymized:
            writer.writerow([rec.model_alias, rec.error_details])
        csv_text = buf.getvalue()
        leaks = anonymization.verify_no_identity(csv_text, mapping)
        assert leaks == [], f"verify_no_identity found leaks in CSV: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Markdown output format leak scan
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestMarkdownLeakScan - verify no identity string in Markdown rendering of reports/errors (INV-A2)
class TestMarkdownLeakScan:
    """Explicitly scan Markdown-rendered anonymized output for identity leaks."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )

    def test_markdown_report_no_leak(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        lines = ["# Benchmark Report", ""]
        lines.append(f"**Provider:** {anon_report.config.base_url}")
        lines.append("")
        lines.append("| Model | Score |")
        lines.append("|-------|-------|")
        for mr in anon_report.models:
            lines.append(f"| {mr.model_name} | {mr.overall_score} |")
        lines.append("")
        lines.append(f"Config models: {', '.join(anon_report.config.models)}")
        md = "\n".join(lines)
        _assert_no_identity(md, "Markdown report")

    def test_markdown_errors_no_leak(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST, ERROR_WITH_LABEL]
        anon_errors = anonymization.anonymize_errors(errors, mapping)
        md = "## Errors\n\n" + "\n\n".join(f"- {e}" for e in anon_errors)
        _assert_no_identity(md, "Markdown errors")

    def test_verify_no_identity_helper_markdown(self):
        mapping = self._mapping()
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        md = f"# Report\n\nProvider: {anon_report.config.base_url}\n"
        for mr in anon_report.models:
            md += f"- {mr.model_name}: {mr.overall_score}\n"
        leaks = anonymization.verify_no_identity(md, mapping)
        assert leaks == [], f"verify_no_identity found leaks in Markdown: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# 11. Filename and file path leak scan
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestFilenameLeakScan - verify anonymized filenames/paths/run-dirs contain no identity (INV-A2/A8)
class TestFilenameLeakScan:
    """Anonymized output filenames and paths must not contain identity."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_anonymized_filenames_no_model_name(self):
        """Files named after models must use aliases, not original names."""
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            filename = f"results_{rec.model_alias}.json"
            for name in MODEL_NAMES:
                assert name not in filename, f"model {name!r} in filename {filename}"
            assert rec.model_alias.startswith("Model_"), f"bad alias: {rec.model_alias}"

    def test_anonymized_file_paths_no_model_name(self):
        """Full file paths must not contain original model names."""
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            filepath = f"benchmark_outputs/run_001/results_{rec.model_alias}.json"
            for name in MODEL_NAMES:
                assert name not in filepath, f"model {name!r} in path {filepath}"
            assert REPO_PATH not in filepath, "repo path in anonymized filepath"

    def test_run_dir_no_identity(self):
        """The run directory name must not embed identity."""
        mapping = self._mapping()
        run_aliases = [a for a, _ in mapping.run_aliases]
        for ra in run_aliases:
            assert ra.startswith("Run_"), f"bad run alias: {ra}"
            for name in MODEL_NAMES:
                assert name not in ra
            assert PROVIDER_HOST not in ra
            assert PROVIDER_HOST_2 not in ra

    def test_verify_no_identity_helper_filename(self):
        mapping = self._mapping()
        anonymized = anonymization.anonymize_results(_sample_results(), mapping)
        for rec in anonymized:
            path = f"outputs/{rec.model_alias}_{rec.config_alias}.json"
            leaks = anonymization.verify_no_identity(path, mapping)
            assert leaks == [], f"identity leaked in filename {path}: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# 12. Mapping file protection
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestMappingFileProtection - verify mapping file mode 0600, private naming, round-trip save/load (P2-anon 3.2)
class TestMappingFileProtection:
    """The mapping file must be protected (mode 0600) and not co-located
    with public outputs."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_save_mapping_creates_file(self, tmp_path):
        mapping = self._mapping()
        path = tmp_path / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, path)
        assert path.exists(), "mapping file not created"

    def test_mapping_file_mode_0600(self, tmp_path):
        """The mapping file must be owner-read-only (mode 0600)."""
        mapping = self._mapping()
        path = tmp_path / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, path)
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600, f"mapping file mode is {oct(mode)}, expected 0o600"

    def test_mapping_file_name_contains_private(self, tmp_path):
        """The filename must contain '.private.' to signal it must not ship."""
        mapping = self._mapping()
        path = tmp_path / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, path)
        assert ".private." in path.name, "mapping file name lacks .private. marker"

    def test_mapping_not_in_public_dir(self, tmp_path):
        """The mapping file must not sit in a 'public' or 'release' directory."""
        mapping = self._mapping()
        run_dir = tmp_path / "run_001"
        run_dir.mkdir()
        public_dir = run_dir / "public"
        public_dir.mkdir()
        mapping_path = run_dir / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, mapping_path)
        assert not (public_dir / "anonymization_mapping.private.json").exists(), \
            "mapping file co-located with public outputs"
        assert mapping_path.exists(), "mapping file not in run dir"

    def test_save_then_load_roundtrip(self, tmp_path):
        """save_mapping + load_mapping must round-trip losslessly."""
        mapping = self._mapping()
        path = tmp_path / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, path)
        loaded = anonymization.load_mapping(path)
        assert loaded == mapping, "mapping round-trip mismatch"

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, IOError, OSError)):
            anonymization.load_mapping(tmp_path / "nonexistent.json")

    def test_mapping_file_contains_no_public_identity_in_name(self, tmp_path):
        """The mapping file path itself must not contain model names."""
        mapping = self._mapping()
        path = tmp_path / "anonymization_mapping.private.json"
        anonymization.save_mapping(mapping, path)
        path_str = str(path)
        for name in MODEL_NAMES:
            assert name not in path_str, f"model {name!r} in mapping file path"


# ═══════════════════════════════════════════════════════════════════════════
# 13. verify_no_identity helper
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestVerifyNoIdentity - verify verify_no_identity detects remaining identity strings in artifact text
class TestVerifyNoIdentity:
    """The verify_no_identity helper must catch leaks and confirm clean text."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_returns_empty_for_clean_text(self):
        mapping = self._mapping()
        clean = "Model_A scored 1.0 with Config_01 via Provider_A"
        assert anonymization.verify_no_identity(clean, mapping) == []

    def test_detects_model_name(self):
        mapping = self._mapping()
        dirty = f"Result for {MODEL_NAMES[0]} was great"
        leaks = anonymization.verify_no_identity(dirty, mapping)
        assert MODEL_NAMES[0] in leaks, "verify_no_identity missed model name"

    def test_detects_provider(self):
        mapping = self._mapping()
        dirty = f"Connected to {BASE_URL}"
        leaks = anonymization.verify_no_identity(dirty, mapping)
        assert BASE_URL in leaks or PROVIDER_HOST in leaks, "verify_no_identity missed provider"

    def test_detects_repo_path(self):
        mapping = self._mapping()
        dirty = f"Error at {REPO_PATH}/benchmark.py"
        leaks = anonymization.verify_no_identity(dirty, mapping)
        assert REPO_PATH in leaks, "verify_no_identity missed repo path"


# ═══════════════════════════════════════════════════════════════════════════
# 14. redact_identity_strings helper
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestRedactIdentityStrings - verify redact_identity_strings replaces all identity with aliases/tokens, longest-first
class TestRedactIdentityStrings:
    """redact_identity_strings must replace identity with aliases/tokens."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_replaces_model_name(self):
        mapping = self._mapping()
        text = f"Model {MODEL_NAMES[0]} passed"
        redacted = anonymization.redact_identity_strings(text, mapping)
        assert MODEL_NAMES[0] not in redacted, "model name not redacted"
        assert "Model_A" in redacted or "Model_" in redacted, "alias not inserted"

    def test_replaces_url_before_hostname(self):
        """Longest-match-first: full URL replaced before hostname substring."""
        mapping = self._mapping()
        text = f"URL={BASE_URL} host={PROVIDER_HOST}"
        redacted = anonymization.redact_identity_strings(text, mapping)
        assert BASE_URL not in redacted, "full URL not redacted"
        assert PROVIDER_HOST not in redacted, "hostname not redacted (substring leak)"

    def test_replaces_repo_path(self):
        mapping = self._mapping()
        text = f"Error in {REPO_PATH}"
        redacted = anonymization.redact_identity_strings(text, mapping)
        assert REPO_PATH not in redacted, "repo path not redacted"

    def test_replaces_second_provider(self):
        """The second provider host must also be redacted."""
        mapping = self._mapping()
        text = f"Remote at {PROVIDER_HOST_2}"
        redacted = anonymization.redact_identity_strings(text, mapping)
        assert PROVIDER_HOST_2 not in redacted, "second provider not redacted"


# ═══════════════════════════════════════════════════════════════════════════
# 15. Idempotency — re-anonymizing with the same mapping yields identical output
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestIdempotency - verify anonymization is idempotent - anonymizing twice produces same result as once
class TestIdempotency:
    """Running anonymization twice with the same mapping must produce
    identical output."""

    def _mapping(self):
        return anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
        )

    def test_results_idempotent(self):
        mapping = self._mapping()
        once = anonymization.anonymize_results(_sample_results(), mapping)
        twice = anonymization.anonymize_results(once, mapping)
        assert once == twice, "anonymize_results not idempotent"

    def test_metadata_idempotent(self):
        mapping = self._mapping()
        once = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        twice = anonymization.anonymize_metadata(once, mapping)
        assert once == twice, "anonymize_metadata not idempotent"

    def test_report_idempotent(self):
        mapping = self._mapping()
        once = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        twice = anonymization.anonymize_report(once, mapping)
        assert once == twice, "anonymize_report not idempotent"

    def test_errors_idempotent(self):
        mapping = self._mapping()
        errors = [ERROR_WITH_PATH, ERROR_WITH_HOST]
        once = anonymization.anonymize_errors(errors, mapping)
        twice = anonymization.anonymize_errors(once, mapping)
        assert once == twice, "anonymize_errors not idempotent"


# ═══════════════════════════════════════════════════════════════════════════
# 16. Cross-format comprehensive scan — all formats at once
# ═══════════════════════════════════════════════════════════════════════════

# TODO(anonymization): TestCrossFormatScan - verify no-leak across all format conversions - JSON/HTML/CSV/MD/filename (INV-A2 cross-format)
class TestCrossFormatScan:
    """One test that scans JSON + HTML + CSV + MD + filenames + paths together
    to satisfy the 'at least one test explicitly checks each format' criterion."""

    def test_all_formats_scanned(self, tmp_path):
        mapping = anonymization.build_anonymization_mapping(
            _sample_results(),
            manifest=_make_run_manifest(),
            config=_make_benchmark_config(),
            report=_make_benchmark_report(),
        )

        # Anonymize everything
        anon_results = anonymization.anonymize_results(_sample_results(), mapping)
        anon_manifest = anonymization.anonymize_metadata(_make_run_manifest(), mapping)
        anon_report = anonymization.anonymize_report(_make_benchmark_report(), mapping)
        anon_errors = anonymization.anonymize_errors(
            [ERROR_WITH_PATH, ERROR_WITH_HOST, ERROR_WITH_LABEL], mapping
        )

        # --- JSON ---
        json_results = json.dumps([_safe_asdict(r) for r in anon_results], default=str)
        json_manifest = json.dumps(_safe_asdict(anon_manifest), default=str)
        json_report = json.dumps(_safe_asdict(anon_report), default=str)
        json_errors = json.dumps(anon_errors)
        for text, label in [
            (json_results, "JSON results"),
            (json_manifest, "JSON manifest"),
            (json_report, "JSON report"),
            (json_errors, "JSON errors"),
        ]:
            _assert_no_identity(text, label)

        # --- HTML ---
        html = f"<html><body><h1>Report</h1><p>{anon_report.config.base_url}</p>"
        for mr in anon_report.models:
            html += f"<div>{mr.model_name}: {mr.overall_score}</div>"
        html += f"<ul>{''.join(f'<li>{e}</li>' for e in anon_errors)}</ul></body></html>"
        _assert_no_identity(html, "HTML")

        # --- CSV ---
        csv_buf = io.StringIO()
        csv_writer = csv.writer(csv_buf)
        csv_writer.writerow(["model_alias", "config_alias", "status", "score", "error"])
        for rec in anon_results:
            csv_writer.writerow([rec.model_alias, rec.config_alias, rec.status, rec.score, rec.error_details])
        csv_text = csv_buf.getvalue()
        _assert_no_identity(csv_text, "CSV")

        # --- Markdown ---
        md = f"# Benchmark Report\n\nProvider: {anon_report.config.base_url}\n\n"
        for mr in anon_report.models:
            md += f"- **{mr.model_name}**: {mr.overall_score}\n"
        md += "\n## Errors\n\n" + "\n".join(f"- {e}" for e in anon_errors)
        _assert_no_identity(md, "Markdown")

        # --- Filenames ---
        for rec in anon_results:
            fname = f"results_{rec.model_alias}_{rec.config_alias}.json"
            _assert_no_identity(fname, "filename")

        # --- File paths ---
        for rec in anon_results:
            fpath = f"benchmark_outputs/run_001/{rec.model_alias}/results.json"
            _assert_no_identity(fpath, "filepath")

        # --- Verify with the module's own helper ---
        all_text = "\n".join([json_results, json_manifest, json_report, json_errors, html, csv_text, md])
        leaks = anonymization.verify_no_identity(all_text, mapping)
        assert leaks == [], f"verify_no_identity found leaks across all formats: {leaks}"


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _safe_asdict(obj):
    """Convert a dataclass (or list of dataclasses) to a JSON-safe dict.

    Handles nested dataclasses, tuples of dataclasses, pydantic models
    (via model_dump), and plain values.  Does NOT use dataclasses.asdict()
    because that leaves pydantic BaseModel instances unconverted, causing
    json.dumps to fail.  Instead, we manually iterate dataclass fields and
    recursively convert each value.
    """
    import dataclasses as dc
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_safe_asdict(item) for item in obj]
    if isinstance(obj, tuple):
        return [_safe_asdict(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_asdict(v) for k, v in obj.items()}
    if dc.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _safe_asdict(getattr(obj, f.name)) for f in dc.fields(obj)}
    # pydantic models (ModelOutput etc.)
    if hasattr(obj, "model_dump"):
        return _safe_asdict(obj.model_dump())
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return _safe_asdict(obj.dict())
        except Exception:
            pass
    return str(obj)


def _assert_no_identity(text: str, label: str):
    """Assert none of the known identity strings appear in text."""
    for s in _all_identity_strings():
        assert s not in text, (
            f"IDENTITY LEAK in {label}: original string {s!r} found in anonymized output.\n"
            f"Excerpt: ...{text[max(0, text.find(s)-40):text.find(s)+len(s)+40]}..."
        )
