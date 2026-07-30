#!/usr/bin/env python3
"""Tests for the config loader (config_loader.py).

Verifies:
* file discovery across configurable directories (YAML/JSON, recursive)
* loading single and multi-doc YAML, and JSON
* validation collecting all errors with file + line context before failing
* layered merge resolution (built-in → global → suite → test)
* registry for adding custom directories programmatically
* ResolvedTestSpec provenance (source_files, suite_name, suite_tags)
* acceptance: example configs load, invalid configs rejected, merges match

These tests are additive — they do not modify the existing tests in
test_benchmark.py or test_config_schema.py.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from model_benchmark.config_loader import (
    CONFIG_GLOBS,
    ConfigError,
    ConfigErrorCollection,
    ConfigLoader,
    LoadedDocument,
    ResolvedTestSpec,
    default_search_dirs,
    load_directory,
    load_file,
)
from model_benchmark.config_schema import (
    BUILTIN_DEFAULTS,
    DefaultsDocument,
    SuiteDocument,
    TestConfig,
    TestDocument,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """A temp tests/ dir with defaults/, suites/, cases/ subdirectories."""
    for sub in ("defaults", "suites", "cases"):
        (tmp_path / sub).mkdir()
    return tmp_path


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path


# ── Discovery ──────────────────────────────────────────────────────────


class TestDiscovery:
    def test_default_search_dirs_exist_or_empty(self):
        dirs = default_search_dirs()
        assert isinstance(dirs, list)
        # Each returned dir either exists or is skipped — list has no None.
        for d in dirs:
            assert isinstance(d, Path)

    def test_default_search_dirs_with_project_root(self, tmp_path: Path):
        (tmp_path / "model_benchmark" / "tests").mkdir(parents=True)
        dirs = default_search_dirs(tmp_path)
        base = tmp_path / "model_benchmark" / "tests"
        assert base in dirs

    def test_config_globs_include_yaml_and_json(self):
        assert "*.yaml" in CONFIG_GLOBS
        assert "*.yml" in CONFIG_GLOBS
        assert "*.json" in CONFIG_GLOBS

    def test_load_directory_discovers_yaml_and_json(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "a.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: a
        """)
        _write(tmp_config_dir / "cases" / "b.json", json.dumps({
            "schema_version": "1.0.0", "kind": "test", "id": "b",
        }))
        docs, errs = load_directory(tmp_config_dir)
        assert not errs
        ids = sorted(d.id for d in docs)
        assert ids == ["a", "b"]

    def test_recursive_discovery(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "sub" / "deep.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: deep
        """)
        docs, errs = load_directory(tmp_config_dir)
        assert not errs
        assert any(d.id == "deep" for d in docs)

    def test_excludes_non_config_subdirs(self, tmp_config_dir: Path):
        # A JSON file in schemas/ should NOT be loaded as a config.
        _write(tmp_config_dir / "schemas" / "schema.json", json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Not a config",
        }))
        docs, errs = load_directory(tmp_config_dir)
        # schemas/ is excluded; the JSON file should not appear as a doc or error.
        assert not any("schema" in str(d.source_path) and d.source_path.suffix == ".json"
                       for d in docs)
        assert not any("schema" in str(e.file_path) for e in errs)

    def test_empty_directory(self, tmp_path: Path):
        docs, errs = load_directory(tmp_path)
        assert docs == []
        assert errs == []

    def test_nonexistent_dir_skipped(self, tmp_path: Path):
        docs, errs = load_directory([tmp_path / "nonexistent"])
        assert docs == []
        assert errs == []


# ── Loading ────────────────────────────────────────────────────────────


class TestLoadFile:
    def test_load_single_yaml(self, tmp_path: Path):
        f = _write(tmp_path / "t.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        docs = load_file(f)
        assert len(docs) == 1
        assert isinstance(docs[0].document, TestDocument)
        assert docs[0].id == "t1"
        assert docs[0].doc_index is None  # single doc

    def test_load_multi_doc_yaml(self, tmp_path: Path):
        f = _write(tmp_path / "multi.yaml", """
            schema_version: "1.0.0"
            kind: defaults
            defaults:
              enabled: true
            ---
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        docs = load_file(f)
        assert len(docs) == 2
        assert docs[0].kind == "defaults"
        assert docs[1].kind == "test"
        assert docs[0].doc_index == 0
        assert docs[1].doc_index == 1

    def test_load_json(self, tmp_path: Path):
        f = tmp_path / "t.json"
        f.write_text(json.dumps({
            "schema_version": "1.0.0", "kind": "test", "id": "jt1",
        }))
        docs = load_file(f)
        assert len(docs) == 1
        assert docs[0].id == "jt1"

    def test_load_json_array_of_docs(self, tmp_path: Path):
        f = tmp_path / "arr.json"
        f.write_text(json.dumps([
            {"schema_version": "1.0.0", "kind": "test", "id": "x1"},
            {"schema_version": "1.0.0", "kind": "test", "id": "x2"},
        ]))
        docs = load_file(f)
        assert len(docs) == 2
        assert {d.id for d in docs} == {"x1", "x2"}

    def test_nonexistent_file_collects_error(self, tmp_path: Path):
        errs: list[ConfigError] = []
        docs = load_file(tmp_path / "missing.yaml", errors=errs)
        assert docs == []
        assert len(errs) == 1
        assert "not found" in errs[0].message.lower()

    def test_nonexistent_file_raises_without_collector(self, tmp_path: Path):
        with pytest.raises(ConfigErrorCollection) as exc_info:
            load_file(tmp_path / "missing.yaml", errors=None)
        assert "not found" in str(exc_info.value).lower()

    def test_yaml_parse_error_collected(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("foo: [unclosed\n")
        errs: list[ConfigError] = []
        docs = load_file(f, errors=errs)
        assert docs == []
        assert len(errs) == 1
        assert "parse error" in errs[0].message.lower()

    def test_json_parse_error_collected(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        errs: list[ConfigError] = []
        docs = load_file(f, errors=errs)
        assert docs == []
        assert len(errs) == 1

    def test_empty_yaml_doc_skipped(self, tmp_path: Path):
        f = _write(tmp_path / "empty.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            ---
            ---
        """)
        docs = load_file(f)
        assert len(docs) == 1  # empty docs skipped
        assert docs[0].id == "t1"

    def test_doc_index_none_for_single_doc(self, tmp_path: Path):
        f = _write(tmp_path / "single.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: only
        """)
        docs = load_file(f)
        assert docs[0].doc_index is None


# ── Validation & error collection ──────────────────────────────────────


class TestValidationErrors:
    def test_validation_error_has_file_path(self, tmp_path: Path):
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: -5
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        assert errs[0].file_path == f
        assert "timeout" in str(errs[0].loc).lower() or "gt" in errs[0].message.lower()

    def test_all_errors_collected_before_failing(self, tmp_path: Path):
        # Two files each with an error → both errors returned.
        _write(tmp_path / "a.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: a
            timeout: -1
        """)
        _write(tmp_path / "b.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: b
            repetitions: 0
        """)
        docs, errs = load_directory(tmp_path)
        assert len(errs) == 2
        messages = " ".join(e.message for e in errs)
        # Both errors present (timeout and repetitions)
        assert errs[0].file_path != errs[1].file_path  # different files

    def test_multiple_errors_in_one_file(self, tmp_path: Path):
        f = _write(tmp_path / "multi_err.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: -1
            repetitions: 0
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        # Pydantic collects all field errors in one ValidationError.
        assert len(errs) >= 2

    def test_error_includes_line_number_when_found(self, tmp_path: Path):
        f = _write(tmp_path / "lined.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: -1
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        # Line number should be found (heuristic) and point at the timeout line.
        assert errs[0].line is not None
        assert errs[0].line >= 1

    def test_unsupported_schema_version_error(self, tmp_path: Path):
        f = _write(tmp_path / "bad_ver.yaml", """
            schema_version: "0.0.1"
            kind: test
            id: t1
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        assert "schema_version" in errs[0].message.lower() or "unsupported" in errs[0].message.lower()

    def test_ambiguous_kind_error(self, tmp_path: Path):
        f = _write(tmp_path / "ambiguous.yaml", """
            description: "no kind, id, defaults, or tests"
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        assert "kind" in errs[0].message.lower()

    def test_config_error_collection_str(self):
        errs = [
            ConfigError(file_path=Path("a.yaml"), message="bad"),
            ConfigError(file_path=Path("b.yaml"), message="worse"),
        ]
        coll = ConfigErrorCollection(errors=errs)
        s = str(coll)
        assert "2 config validation error(s)" in s
        assert "bad" in s
        assert "worse" in s

    def test_config_error_location_property(self):
        e = ConfigError(file_path=Path("x.yaml"), message="m", line=42)
        assert "line 42" in e.location
        e2 = ConfigError(file_path=Path("x.yaml"), message="m", doc_index=2, line=10)
        assert "doc#2" in e2.location
        assert "line 10" in e2.location


# ── ConfigLoader registry ──────────────────────────────────────────────


class TestConfigLoaderRegistry:
    def test_add_directory(self, tmp_config_dir: Path):
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        extra = tmp_config_dir / "extra"
        extra.mkdir()
        _write(extra / "e.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: extra_test
        """)
        loader.add_directory(extra)
        loader.reload()
        ids = [d.id for d in loader.documents()]
        assert "extra_test" in ids

    def test_remove_directory(self, tmp_config_dir: Path):
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        # Use a sibling directory (not a subdir) so recursive scan of
        # tmp_config_dir doesn't pick it up after removal.
        extra = tmp_config_dir.parent / "extra_dir"
        extra.mkdir(exist_ok=True)
        try:
            _write(extra / "e.yaml", """
                schema_version: "1.0.0"
                kind: test
                id: extra_test
            """)
            loader.add_directory(extra)
            loader.reload()
            assert "extra_test" in [d.id for d in loader.documents()]
            loader.remove_directory(extra)
            loader.reload()
            assert "extra_test" not in [d.id for d in loader.documents()]
        finally:
            import shutil
            shutil.rmtree(extra, ignore_errors=True)

    def test_add_directory_chaining(self, tmp_config_dir: Path):
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        ret = loader.add_directory(tmp_config_dir / "x")
        assert ret is loader  # returns self

    def test_search_dirs_property(self, tmp_config_dir: Path):
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        assert tmp_config_dir in loader.search_dirs

    def test_reload_invalidates_cache(self, tmp_config_dir: Path):
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        loader.reload()
        assert len(loader.documents()) == 0
        _write(tmp_config_dir / "cases" / "new.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: new
        """)
        # Cache is stale — reload picks up the new file.
        loader.reload()
        assert any(d.id == "new" for d in loader.documents())

    def test_custom_search_dirs_override_defaults(self, tmp_path: Path):
        custom = tmp_path / "custom"
        custom.mkdir()
        _write(custom / "c.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: custom_test
        """)
        loader = ConfigLoader(search_dirs=[custom])
        loader.reload()
        ids = [d.id for d in loader.documents()]
        assert ids == ["custom_test"]

    def test_validate_returns_errors(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: bad
            timeout: -1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        errs = loader.validate()
        assert len(errs) >= 1

    def test_validate_returns_empty_when_valid(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "good.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: good
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        errs = loader.validate()
        assert errs == []


# ── Resolution ─────────────────────────────────────────────────────────


class TestResolution:
    def test_resolve_standalone_test(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            name: Test One
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert len(specs) == 1
        assert specs[0].id == "t1"
        assert specs[0].suite_name is None
        assert specs[0].suite_tags == ()
        # Built-in defaults applied
        assert specs[0].config.enabled is True
        assert specs[0].config.evaluation.name == "exact_match"

    def test_resolve_with_global_defaults(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "defaults.yaml", """
            schema_version: "1.0.0"
            kind: defaults
            defaults:
              timeout: 60
              tags: ["global"]
        """)
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert len(specs) == 1
        assert specs[0].config.timeout == 60
        assert "global" in specs[0].config.tags

    def test_resolve_suite_applies_suite_defaults(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            defaults:
              timeout: 90
              tags: ["suite-tag"]
            tests:
              - t1
        """)
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert len(specs) == 1
        assert specs[0].suite_name == "s1"
        assert specs[0].config.timeout == 90
        assert "suite-tag" in specs[0].config.tags

    def test_resolve_inline_test_in_suite(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests:
              - id: inline_t
                name: Inline Test
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert len(specs) == 1
        assert specs[0].id == "inline_t"
        assert specs[0].suite_name == "s1"

    def test_resolve_test_overrides_suite(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            defaults:
              timeout: 100
            tests:
              - t1
        """)
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: 200
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert specs[0].config.timeout == 200  # test overrides suite

    def test_resolve_unknown_suite_reference(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests:
              - nonexistent_test
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert specs == []  # reference couldn't be resolved
        assert loader.has_errors()
        errs = loader.errors()
        assert any("nonexistent_test" in e.message for e in errs)

    def test_resolve_by_id(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        _write(tmp_config_dir / "cases" / "t2.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t2
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        spec = loader.resolve_by_id("t2")
        assert spec is not None
        assert spec.id == "t2"
        assert loader.resolve_by_id("nonexistent") is None

    def test_resolve_suite_by_name(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests:
              - id: inline_a
              - id: inline_b
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_suite("s1")
        assert len(specs) == 2
        assert all(s.suite_name == "s1" for s in specs)
        assert loader.resolve_suite("nonexistent") == []

    def test_source_files_provenance(self, tmp_config_dir: Path):
        case_file = _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        suite_file = _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests:
              - t1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        assert len(specs) == 1
        # Source files include both the test case file and the suite file.
        assert str(case_file) in specs[0].source_files
        assert str(suite_file) in specs[0].source_files

    def test_standalone_not_referenced_by_suite(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests:
              - ref_test
        """)
        _write(tmp_config_dir / "cases" / "ref_test.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: ref_test
        """)
        _write(tmp_config_dir / "cases" / "standalone.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: standalone
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        ids = [s.id for s in specs]
        # ref_test resolved within suite; standalone resolved separately.
        assert "ref_test" in ids
        assert "standalone" in ids
        # ref_test has suite_name; standalone does not.
        ref = [s for s in specs if s.id == "ref_test"][0]
        standalone = [s for s in specs if s.id == "standalone"][0]
        assert ref.suite_name == "s1"
        assert standalone.suite_name is None

    def test_same_test_in_multiple_suits(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "shared.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: shared
        """)
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            defaults:
              timeout: 100
            tests:
              - shared
        """)
        _write(tmp_config_dir / "suites" / "s2.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s2
            defaults:
              timeout: 200
            tests:
              - shared
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = loader.resolve_all()
        shared_specs = [s for s in specs if s.id == "shared"]
        assert len(shared_specs) == 2  # one per suite
        timeouts = sorted(s.config.timeout for s in shared_specs)
        assert timeouts == [100, 200]

    def test_resolved_spec_enabled_property(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        _write(tmp_config_dir / "cases" / "t2.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t2
            enabled: false
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        specs = {s.id: s for s in loader.resolve_all()}
        assert specs["t1"].enabled is True  # built-in default
        assert specs["t2"].enabled is False

    def test_resolved_spec_repr(self):
        spec = ResolvedTestSpec(config=TestConfig(id="x"))
        r = repr(spec)
        assert "x" in r


# ── Example configs integration (acceptance) ────────────────────────────


class TestExampleConfigs:
    """End-to-end: load and resolve the reference example from the schema task."""

    @pytest.fixture(scope="class")
    def example_path(self) -> Path:
        return (
            Path(__file__).parent
            / "examples"
            / "full_feature_example.yaml"
        )

    @pytest.fixture(scope="class")
    def example_docs(self, example_path: Path) -> list[LoadedDocument]:
        docs = load_file(example_path)
        assert len(docs) == 3
        return docs

    def test_three_documents_discovered(self, example_docs):
        kinds = [d.kind for d in example_docs]
        assert kinds == ["defaults", "suite", "test"]

    def test_defaults_doc(self, example_docs):
        d = example_docs[0]
        assert isinstance(d.document, DefaultsDocument)
        assert d.document.defaults.enabled is True
        assert d.document.defaults.tags == ["sugarcube"]

    def test_suite_doc(self, example_docs):
        d = example_docs[1]
        assert isinstance(d.document, SuiteDocument)
        assert d.document.name == "sugarcube_core"
        assert len(d.document.tests) == 3

    def test_test_doc(self, example_docs):
        d = example_docs[2]
        assert isinstance(d.document, TestDocument)
        assert d.document.id == "sugarcube_direction_matrix"

    def test_full_resolution_matches_design_note(self, example_path: Path):
        """Resolve the matrix test and verify it matches DESIGN_NOTE.md expectations."""
        # The example file lives in tests/examples/.  Use a loader pointed at
        # the tests/ root so both the example and the standalone case file
        # (sugarcube_markup_001.yaml) are discovered.
        tests_root = example_path.parent.parent
        loader = ConfigLoader(search_dirs=[tests_root])
        specs = loader.resolve_all()
        assert not loader.errors()

        matrix_spec = [s for s in specs if s.id == "sugarcube_direction_matrix"]
        assert len(matrix_spec) == 1
        spec = matrix_spec[0]

        # These match DESIGN_NOTE.md section 2 "Proof":
        assert spec.config.id == "sugarcube_direction_matrix"
        assert spec.config.tags == [
            "sugarcube", "core", "regression", "matrix", "parametrized",
        ]
        assert spec.config.model_parameters.temperature == 0.0
        assert spec.config.model_parameters.num_predict == 512
        assert spec.config.repetitions == 5
        assert spec.config.evaluation.name == "sugarcube_rubric"
        assert spec.config.scoring_categories == [
            "markup_compliance", "passage_structure", "macro_usage",
        ]

    def test_suite_resolves_all_tests(self, example_path: Path):
        tests_root = example_path.parent.parent
        loader = ConfigLoader(search_dirs=[tests_root])
        suite_specs = loader.resolve_suite("sugarcube_core")
        ids = sorted(s.id for s in suite_specs)
        # Suite references: sugarcube_markup_001, sugarcube_direction_matrix,
        # and inline sugarcube_inline_macro.
        assert "sugarcube_markup_001" in ids
        assert "sugarcube_direction_matrix" in ids
        assert "sugarcube_inline_macro" in ids

    def test_inline_test_tags_unioned(self, example_path: Path):
        tests_root = example_path.parent.parent
        loader = ConfigLoader(search_dirs=[tests_root])
        inline = [s for s in loader.resolve_all() if s.id == "sugarcube_inline_macro"][0]
        # tags: global [sugarcube] + suite [core, regression] + test [inline, nesting]
        assert "sugarcube" in inline.config.tags
        assert "core" in inline.config.tags
        assert "regression" in inline.config.tags
        assert "inline" in inline.config.tags
        assert "nesting" in inline.config.tags

    def test_inline_test_uses_llm_judge(self, example_path: Path):
        tests_root = example_path.parent.parent
        loader = ConfigLoader(search_dirs=[tests_root])
        inline = [s for s in loader.resolve_all() if s.id == "sugarcube_inline_macro"][0]
        assert inline.config.evaluation.name == "llm_judge"
        assert inline.config.evaluation.pass_threshold == 0.8


# ── Rejection of invalid configs (acceptance) ──────────────────────────


class TestInvalidConfigsRejected:
    def test_invalid_config_rejected_with_clear_message(self, tmp_path: Path):
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: -10
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        # Clear message includes the field and the constraint.
        msg = errs[0].message.lower()
        assert "timeout" in msg or "gt" in msg or "greater" in msg

    def test_invalid_kind_rejected(self, tmp_path: Path):
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: unknown
            id: t1
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) == 1
        assert "unknown" in errs[0].message.lower() or "kind" in errs[0].message.lower()

    def test_missing_required_field_rejected(self, tmp_path: Path):
        # Test document requires `id`.
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            name: no id
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) >= 1
        assert any("id" in str(e.loc).lower() for e in errs)

    def test_cross_field_constraint_rejected(self, tmp_path: Path):
        # model_eligibility required and excluded overlap.
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            model_eligibility:
              required: ["m1"]
              excluded: ["m1"]
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) >= 1
        assert any("overlap" in e.message.lower() for e in errs)

    def test_invalid_enum_rejected(self, tmp_path: Path):
        f = _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            difficulty: impossible
        """)
        errs: list[ConfigError] = []
        load_file(f, errors=errs)
        assert len(errs) >= 1

    def test_loader_has_errors_after_invalid_load(self, tmp_path: Path):
        _write(tmp_path / "bad.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
            timeout: -1
        """)
        loader = ConfigLoader(search_dirs=[tmp_path])
        loader.reload()
        assert loader.has_errors()
        assert len(loader.errors()) >= 1


# ── Document kind accessors ────────────────────────────────────────────


class TestDocumentAccessors:
    def test_defaults_documents(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "defaults.yaml", """
            schema_version: "1.0.0"
            kind: defaults
            defaults:
              timeout: 60
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        loader.reload()
        defs = loader.defaults_documents()
        assert len(defs) == 1
        assert defs[0].kind == "defaults"

    def test_suite_documents(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "suites" / "s1.yaml", """
            schema_version: "1.0.0"
            kind: suite
            name: s1
            tests: [t1]
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        loader.reload()
        suites = loader.suite_documents()
        assert len(suites) == 1
        assert suites[0].id == "s1"

    def test_test_documents(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        loader.reload()
        tests = loader.test_documents()
        assert len(tests) == 1
        assert tests[0].id == "t1"

    def test_loaded_document_repr(self, tmp_config_dir: Path):
        _write(tmp_config_dir / "cases" / "t1.yaml", """
            schema_version: "1.0.0"
            kind: test
            id: t1
        """)
        loader = ConfigLoader(search_dirs=[tmp_config_dir])
        loader.reload()
        d = loader.test_documents()[0]
        r = repr(d)
        assert "test" in r
        assert "t1" in r
