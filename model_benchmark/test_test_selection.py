#!/usr/bin/env python3
"""Tests for the test selection and matrix expansion module (test_selection.py).

Verifies (per task t_503bdee2):
1. Selection by name, tag, id, capability, category, difficulty, suite + globs
2. Compound boolean expressions (AND, OR, NOT, parentheses)
3. Include/exclude filters and priority-based selection/truncation
4. Parameterized matrix expansion (full, pairwise, explicit, sample)
5. Deterministic instance ID generation
6. Deduplication when matrix combinations overlap
7. max_cases truncation
8. Dry-run mode produces human-readable output

These tests are additive — they do not modify existing tests in
test_benchmark.py, test_config_schema.py, or test_config_loader.py.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from model_benchmark.config_loader import (
    ConfigLoader,
    ResolvedTestSpec,
    default_search_dirs,
)
from model_benchmark.config_schema import (
    BUILTIN_DEFAULTS,
    DefaultsDocument,
    MatrixConfig,
    SuiteDocument,
    TestConfig,
    TestDocument,
    resolve_test,
)
from model_benchmark.test_selection import (
    AndExpr,
    DryRunResult,
    ExpandedTestInstance,
    Expr,
    MatrixExpansionResult,
    NotExpr,
    OrExpr,
    ParseError,
    Predicate,
    SelectionFilters,
    SelectionParser,
    _apply_parameters,
    _generate_instance_id,
    _pairwise_product,
    _sanitize_value,
    dry_run,
    eval_expr,
    expand_all,
    expand_matrix,
    parse_selection,
    select_and_expand,
    select_tests,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_spec(
    test_id: str = "t1",
    name: str | None = None,
    tags: list[str] | None = None,
    capability: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    difficulty: str | None = None,
    enabled: bool | None = True,
    suite_name: str | None = None,
    suite_tags: tuple[str, ...] = (),
    priority: int | None = None,
    parameters: dict | None = None,
    matrix: MatrixConfig | None = None,
    **kwargs,
) -> ResolvedTestSpec:
    """Build a ResolvedTestSpec for testing without loading files."""
    config = TestConfig(
        id=test_id,
        name=name,
        tags=tags or [],
        capability=capability,
        category=category,
        subcategory=subcategory,
        difficulty=difficulty,
        enabled=enabled,
        priority=priority,
        parameters=parameters,
        matrix=matrix,
        **{k: v for k, v in kwargs.items() if k in TestConfig.model_fields},
    )
    return ResolvedTestSpec(
        config=config,
        source_files=(f"<test>/{test_id}.yaml",),
        suite_name=suite_name,
        suite_tags=suite_tags,
    )


def _make_specs(*ids_tags, **common) -> list[ResolvedTestSpec]:
    """Build multiple specs from (id, tags) tuples."""
    specs = []
    for item in ids_tags:
        if isinstance(item, str):
            specs.append(_make_spec(test_id=item, **common))
        elif isinstance(item, tuple):
            tid, tags = item[0], item[1]
            extra = {k: v for k, v in zip(["name", "capability", "category", "difficulty"], item[2:])} if len(item) > 2 else {}
            specs.append(_make_spec(test_id=tid, tags=tags, **{**common, **extra}))
    return specs


# ══════════════════════════════════════════════════════════════════════════
# 1. EXPRESSION PARSER
# ══════════════════════════════════════════════════════════════════════════


class TestParser:
    """Test the selection expression parser."""

    def test_parse_simple_tag(self):
        expr = parse_selection("tag:smoke")
        assert isinstance(expr, Predicate)
        assert expr.field == "tag"
        assert expr.value == "smoke"
        assert expr.negate is False

    def test_parse_simple_id(self):
        expr = parse_selection("id:arithmetic_001")
        assert isinstance(expr, Predicate)
        assert expr.field == "id"
        assert expr.value == "arithmetic_001"

    def test_parse_glob_in_value(self):
        expr = parse_selection("name:story_*")
        assert isinstance(expr, Predicate)
        assert expr.field == "name"
        assert expr.value == "story_*"

    def test_parse_quoted_value(self):
        expr = parse_selection('tag:"smoke test"')
        assert isinstance(expr, Predicate)
        assert expr.field == "tag"
        assert expr.value == "smoke test"

    def test_parse_capability(self):
        expr = parse_selection("capability:reasoning")
        assert expr.field == "capability"
        assert expr.value == "reasoning"

    def test_parse_category(self):
        expr = parse_selection("category:arithmetic")
        assert expr.field == "category"

    def test_parse_difficulty(self):
        expr = parse_selection("difficulty:hard")
        assert expr.field == "difficulty"
        assert expr.value == "hard"

    def test_parse_suite(self):
        expr = parse_selection("suite:core")
        assert expr.field == "suite"
        assert expr.value == "core"

    def test_parse_enabled_true(self):
        expr = parse_selection("enabled:true")
        assert expr.field == "enabled"
        assert expr.value == "true"

    def test_parse_and(self):
        expr = parse_selection("tag:smoke AND tag:fast")
        assert isinstance(expr, AndExpr)
        assert len(expr.children) == 2

    def test_parse_or(self):
        expr = parse_selection("tag:smoke OR tag:fast")
        assert isinstance(expr, OrExpr)
        assert len(expr.children) == 2

    def test_parse_not(self):
        expr = parse_selection("NOT tag:slow")
        assert isinstance(expr, NotExpr)
        assert isinstance(expr.child, Predicate)

    def test_parse_compound_and_not(self):
        expr = parse_selection("tag:regression AND NOT tag:slow")
        assert isinstance(expr, AndExpr)
        assert len(expr.children) == 2
        assert isinstance(expr.children[1], NotExpr)

    def test_parse_parentheses(self):
        expr = parse_selection("(tag:smoke OR tag:fast) AND NOT difficulty:expert")
        assert isinstance(expr, AndExpr)
        assert isinstance(expr.children[0], OrExpr)
        assert isinstance(expr.children[1], NotExpr)

    def test_parse_implicit_and(self):
        # Adjacent atoms without AND are implicitly ANDed.
        expr = parse_selection("tag:smoke tag:fast")
        assert isinstance(expr, AndExpr)
        assert len(expr.children) == 2

    def test_parse_nested_parentheses(self):
        expr = parse_selection("((tag:smoke OR tag:fast) AND (tag:core OR tag:math))")
        assert isinstance(expr, AndExpr)
        assert isinstance(expr.children[0], OrExpr)
        assert isinstance(expr.children[1], OrExpr)

    def test_parse_case_insensitive_keywords(self):
        expr = parse_selection("tag:smoke and tag:fast")
        assert isinstance(expr, AndExpr)
        expr2 = parse_selection("tag:smoke or tag:fast")
        assert isinstance(expr2, OrExpr)
        expr3 = parse_selection("not tag:slow")
        assert isinstance(expr3, NotExpr)

    def test_parse_unknown_field_raises(self):
        with pytest.raises(ParseError, match="Unknown selection field"):
            parse_selection("bogus:value")

    def test_parse_empty_raises(self):
        with pytest.raises(ParseError, match="Empty"):
            parse_selection("")

    def test_parse_unclosed_paren_raises(self):
        with pytest.raises(ParseError, match="Missing closing"):
            parse_selection("(tag:smoke AND tag:fast")

    def test_parse_str_predicate(self):
        expr = parse_selection("tag:smoke")
        assert str(expr) == "tag:smoke"

    def test_parse_str_and_expr(self):
        expr = parse_selection("tag:smoke AND tag:fast")
        assert "AND" in str(expr)

    def test_parse_str_not_expr(self):
        expr = parse_selection("NOT tag:slow")
        assert str(expr).startswith("NOT")


# ══════════════════════════════════════════════════════════════════════════
# 2. EXPRESSION EVALUATION
# ══════════════════════════════════════════════════════════════════════════


class TestEvaluation:
    """Test expression evaluation against test specs."""

    def test_eval_tag_match(self):
        spec = _make_spec(tags=["smoke", "fast"])
        assert eval_expr(parse_selection("tag:smoke"), spec) is True
        assert eval_expr(parse_selection("tag:fast"), spec) is True
        assert eval_expr(parse_selection("tag:slow"), spec) is False

    def test_eval_tag_glob(self):
        spec = _make_spec(tags=["story_arithmetic", "story_logic"])
        assert eval_expr(parse_selection("tag:story_*"), spec) is True
        assert eval_expr(parse_selection("tag:story_?rithmetic"), spec) is True

    def test_eval_tag_matches_suite_tags(self):
        spec = _make_spec(tags=["own"], suite_tags=["inherited", "suite-tag"])
        assert eval_expr(parse_selection("tag:inherited"), spec) is True
        assert eval_expr(parse_selection("tag:suite-tag"), spec) is True

    def test_eval_name_glob(self):
        spec = _make_spec(name="Story generation test")
        assert eval_expr(parse_selection("name:Story*"), spec) is True
        assert eval_expr(parse_selection("name:*generation*"), spec) is True
        assert eval_expr(parse_selection("name:arithmetic"), spec) is False

    def test_eval_id_glob(self):
        spec = _make_spec(test_id="arithmetic_001")
        assert eval_expr(parse_selection("id:arithmetic_*"), spec) is True
        assert eval_expr(parse_selection("id:arithmetic_001"), spec) is True

    def test_eval_capability(self):
        spec = _make_spec(capability="reasoning")
        assert eval_expr(parse_selection("capability:reasoning"), spec) is True
        assert eval_expr(parse_selection("capability:*reason*"), spec) is True

    def test_eval_category(self):
        spec = _make_spec(category="arithmetic")
        assert eval_expr(parse_selection("category:arithmetic"), spec) is True

    def test_eval_subcategory(self):
        spec = _make_spec(subcategory="percentages")
        assert eval_expr(parse_selection("subcategory:percentages"), spec) is True

    def test_eval_difficulty_exact(self):
        spec = _make_spec(difficulty="hard")
        assert eval_expr(parse_selection("difficulty:hard"), spec) is True
        assert eval_expr(parse_selection("difficulty:easy"), spec) is False

    def test_eval_suite(self):
        spec = _make_spec(suite_name="core")
        assert eval_expr(parse_selection("suite:core"), spec) is True
        assert eval_expr(parse_selection("suite:*or*"), spec) is True
        assert eval_expr(parse_selection("suite:math"), spec) is False

    def test_eval_enabled_true(self):
        spec = _make_spec(enabled=True)
        assert eval_expr(parse_selection("enabled:true"), spec) is True
        assert eval_expr(parse_selection("enabled:false"), spec) is False

    def test_eval_enabled_false(self):
        spec = _make_spec(enabled=False)
        assert eval_expr(parse_selection("enabled:false"), spec) is True
        assert eval_expr(parse_selection("enabled:true"), spec) is False

    def test_eval_enabled_none_defaults_true(self):
        spec = _make_spec(enabled=None)
        assert eval_expr(parse_selection("enabled:true"), spec) is True

    def test_eval_and(self):
        spec = _make_spec(tags=["smoke", "fast"])
        expr = parse_selection("tag:smoke AND tag:fast")
        assert eval_expr(expr, spec) is True
        expr = parse_selection("tag:smoke AND tag:slow")
        assert eval_expr(expr, spec) is False

    def test_eval_or(self):
        spec = _make_spec(tags=["smoke"])
        expr = parse_selection("tag:smoke OR tag:fast")
        assert eval_expr(expr, spec) is True

    def test_eval_not(self):
        spec = _make_spec(tags=["smoke"])
        expr = parse_selection("NOT tag:slow")
        assert eval_expr(expr, spec) is True
        expr = parse_selection("NOT tag:smoke")
        assert eval_expr(expr, spec) is False

    def test_eval_compound(self):
        spec = _make_spec(tags=["regression", "fast"], difficulty="hard")
        expr = parse_selection("tag:regression AND NOT tag:slow")
        assert eval_expr(expr, spec) is True
        expr = parse_selection("(tag:smoke OR tag:fast) AND NOT difficulty:expert")
        assert eval_expr(expr, spec) is True

    def test_eval_none_value_never_matches(self):
        spec = _make_spec(name=None)
        assert eval_expr(parse_selection("name:*"), spec) is False

    def test_eval_difficulty_is_exact_not_glob(self):
        """Difficulty is an enum; it should be exact match, not glob."""
        spec = _make_spec(difficulty="hard")
        # 'hard' should match; 'har*' should NOT (difficulty is exact).
        assert eval_expr(parse_selection("difficulty:hard"), spec) is True
        # Actually, for enum fields we use exact match. Verify 'har*' fails.
        assert eval_expr(parse_selection("difficulty:har*"), spec) is False


# ══════════════════════════════════════════════════════════════════════════
# 3. SELECTION FILTERS
# ══════════════════════════════════════════════════════════════════════════


class TestSelectionFilters:
    """Test the SelectionFilters dataclass and select_tests function."""

    def test_select_no_filters_returns_all(self):
        specs = _make_specs(("t1", ["a"]), ("t2", ["b"]), ("t3", ["c"]))
        selected = select_tests(specs)
        assert len(selected) == 3

    def test_select_include_single(self):
        specs = _make_specs(("t1", ["smoke"]), ("t2", ["fast"]), ("t3", ["slow"]))
        filters = SelectionFilters().add_include("tag:smoke")
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_include_multiple_all_must_match(self):
        specs = _make_specs(
            ("t1", ["smoke", "fast"]),
            ("t2", ["smoke", "slow"]),
            ("t3", ["fast"]),
        )
        filters = SelectionFilters().add_include("tag:smoke").add_include("tag:fast")
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_exclude_removes_matching(self):
        specs = _make_specs(
            ("t1", ["smoke", "fast"]),
            ("t2", ["smoke", "slow"]),
            ("t3", ["fast"]),
        )
        filters = SelectionFilters().add_exclude("tag:slow")
        selected = select_tests(specs, filters)
        ids = {s.id for s in selected}
        assert ids == {"t1", "t3"}

    def test_select_include_and_exclude_combined(self):
        specs = _make_specs(
            ("t1", ["smoke", "fast"]),
            ("t2", ["smoke", "slow"]),
            ("t3", ["fast", "regression"]),
        )
        filters = (
            SelectionFilters()
            .add_include("tag:smoke")
            .add_exclude("tag:slow")
        )
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_filters_disabled_by_default(self):
        specs = [
            _make_spec(test_id="t1", enabled=True),
            _make_spec(test_id="t2", enabled=False),
        ]
        selected = select_tests(specs)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_include_disabled_keeps_disabled(self):
        specs = [
            _make_spec(test_id="t1", enabled=True),
            _make_spec(test_id="t2", enabled=False),
        ]
        filters = SelectionFilters(include_disabled=True)
        selected = select_tests(specs, filters)
        assert len(selected) == 2

    def test_select_disabled_none_treated_as_enabled(self):
        specs = [_make_spec(test_id="t1", enabled=None)]
        selected = select_tests(specs)
        assert len(selected) == 1

    def test_select_exclude_multiple_any_match_removes(self):
        specs = _make_specs(
            ("t1", ["a"]),
            ("t2", ["b"]),
            ("t3", ["c"]),
        )
        filters = SelectionFilters().add_exclude("tag:a").add_exclude("tag:b")
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t3"

    def test_select_complex_expression(self):
        specs = _make_specs(
            ("t1", ["regression", "fast"], "T1", None, None, "hard"),
            ("t2", ["regression", "slow"], "T2", None, None, "easy"),
            ("t3", ["smoke", "fast"], "T3", None, None, "expert"),
        )
        filters = SelectionFilters().add_include(
            "tag:regression AND NOT tag:slow"
        )
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_glob_pattern(self):
        specs = _make_specs(
            ("story_arithmetic", []),
            ("story_logic", []),
            ("math_basic", []),
        )
        filters = SelectionFilters().add_include("id:story_*")
        selected = select_tests(specs, filters)
        assert len(selected) == 2
        assert all(s.id.startswith("story_") for s in selected)

    def test_select_by_suite(self):
        specs = [
            _make_spec(test_id="t1", suite_name="core"),
            _make_spec(test_id="t2", suite_name="math"),
            _make_spec(test_id="t3", suite_name=None),
        ]
        filters = SelectionFilters().add_include("suite:core")
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t1"

    def test_select_by_capability(self):
        specs = [
            _make_spec(test_id="t1", capability="reasoning"),
            _make_spec(test_id="t2", capability="arithmetic"),
        ]
        filters = SelectionFilters().add_include("capability:reasoning")
        selected = select_tests(specs, filters)
        assert len(selected) == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. PRIORITY-BASED SELECTION
# ══════════════════════════════════════════════════════════════════════════


class TestPrioritySelection:
    """Test priority-based ordering and truncation."""

    def test_priority_ordering_lower_first(self):
        specs = [
            _make_spec(test_id="t1", priority=5),
            _make_spec(test_id="t2", priority=1),
            _make_spec(test_id="t3", priority=3),
        ]
        selected = select_tests(specs)
        ids = [s.id for s in selected]
        assert ids == ["t2", "t3", "t1"]

    def test_priority_none_sorts_last(self):
        specs = [
            _make_spec(test_id="t1", priority=None),
            _make_spec(test_id="t2", priority=1),
            _make_spec(test_id="t3", priority=None),
        ]
        selected = select_tests(specs)
        ids = [s.id for s in selected]
        # t2 (priority=1) first; t1, t3 (None) in input order after.
        assert ids == ["t2", "t1", "t3"]

    def test_priority_truncation_keeps_highest_priority(self):
        specs = [
            _make_spec(test_id="t1", priority=5),
            _make_spec(test_id="t2", priority=1),
            _make_spec(test_id="t3", priority=3),
            _make_spec(test_id="t4", priority=10),
        ]
        filters = SelectionFilters(max_selected=2)
        selected = select_tests(specs, filters)
        ids = [s.id for s in selected]
        assert ids == ["t2", "t3"]

    def test_priority_truncation_none_keeps_all(self):
        specs = _make_specs(("t1", ["a"]), ("t2", ["b"]))
        filters = SelectionFilters(max_selected=None)
        selected = select_tests(specs, filters)
        assert len(selected) == 2

    def test_priority_truncation_larger_than_set(self):
        specs = _make_specs(("t1", ["a"]), ("t2", ["b"]))
        filters = SelectionFilters(max_selected=10)
        selected = select_tests(specs, filters)
        assert len(selected) == 2

    def test_priority_stable_for_equal_priorities(self):
        specs = [
            _make_spec(test_id="t1", priority=1),
            _make_spec(test_id="t2", priority=1),
            _make_spec(test_id="t3", priority=1),
        ]
        selected = select_tests(specs)
        ids = [s.id for s in selected]
        # Equal priorities preserve input order (stable sort).
        assert ids == ["t1", "t2", "t3"]

    def test_priority_truncation_applied_after_filters(self):
        specs = [
            _make_spec(test_id="t1", priority=5, tags=["a"]),
            _make_spec(test_id="t2", priority=1, tags=["a"]),
            _make_spec(test_id="t3", priority=3, tags=["b"]),
        ]
        # First filter to tag:a, then truncate to 1.
        filters = SelectionFilters(max_selected=1).add_include("tag:a")
        selected = select_tests(specs, filters)
        assert len(selected) == 1
        assert selected[0].id == "t2"  # highest priority among tag:a


# ══════════════════════════════════════════════════════════════════════════
# 5. MATRIX EXPANSION
# ══════════════════════════════════════════════════════════════════════════


class TestMatrixExpansion:
    """Test parameterized matrix expansion."""

    def test_no_parameters_single_instance(self):
        spec = _make_spec(test_id="simple_test")
        result = expand_matrix(spec)
        assert result.num_instances == 1
        assert result.strategy == "none"
        assert result.instances[0].instance_id == "simple_test"
        assert result.instances[0].parameters == {}
        assert not result.instances[0].is_matrix_expansion

    def test_full_product_2x3(self):
        spec = _make_spec(
            test_id="matrix_test",
            parameters={"dim1": ["a", "b"], "dim2": ["x", "y", "z"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 6  # 2 * 3
        assert result.strategy == "full"
        assert result.full_product_size == 6

    def test_full_product_3x3x2(self):
        """The example from the DESIGN_NOTE: variant[3] x direction[3] x difficulty[2] = 18."""
        spec = _make_spec(
            test_id="sugarcube_direction_matrix",
            parameters={
                "variant": ["compact", "full", "json"],
                "direction": ["A", "B", "C"],
                "difficulty": ["easy", "medium"],
            },
            matrix=MatrixConfig(strategy="full", max_cases=100),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 18
        assert result.full_product_size == 18
        assert not result.truncated

    def test_deterministic_instance_ids(self):
        """Instance IDs must be deterministic and sorted alphabetically by dimension name."""
        spec = _make_spec(
            test_id="mt",
            parameters={"variant": ["compact", "full"], "direction": ["A", "B"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        ids = [i.instance_id for i in result.instances]
        # IDs are deterministic: dimension names sorted alphabetically (direction, variant).
        # Instance order follows itertools.product (insertion order of the dict).
        expected = [
            "mt__direction-A__variant-compact",
            "mt__direction-B__variant-compact",
            "mt__direction-A__variant-full",
            "mt__direction-B__variant-full",
        ]
        assert ids == expected

    def test_instance_ids_stable_across_runs(self):
        """Generating IDs twice must produce identical results."""
        spec = _make_spec(
            test_id="mt",
            parameters={"b": ["1", "2"], "a": ["x", "y"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result1 = expand_matrix(spec)
        result2 = expand_matrix(spec)
        assert [i.instance_id for i in result1.instances] == [
            i.instance_id for i in result2.instances
        ]

    def test_id_generation_format(self):
        """Verify the <test_id>__<dim1>-<val1>__<dim2>-<val2> format."""
        iid = _generate_instance_id("base", {"variant": "compact", "direction": "A"})
        # Dimensions are sorted alphabetically.
        assert iid == "base__direction-A__variant-compact"

    def test_id_generation_no_params(self):
        assert _generate_instance_id("base", {}) == "base"

    def test_sanitize_value_bool(self):
        assert _sanitize_value(True) == "true"
        assert _sanitize_value(False) == "false"

    def test_sanitize_value_none(self):
        assert _sanitize_value(None) == "none"

    def test_sanitize_value_float(self):
        assert _sanitize_value(0.0) == "0.0"
        assert _sanitize_value(0.7) == "0.7"

    def test_sanitize_value_unsafe_chars(self):
        # Slashes and spaces become underscores.
        assert _sanitize_value("a/b c") == "a_b_c"

    def test_max_cases_truncation(self):
        spec = _make_spec(
            test_id="mt",
            parameters={"d1": ["a", "b", "c", "d"], "d2": ["1", "2", "3"]},
            matrix=MatrixConfig(strategy="full", max_cases=5),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 5
        assert result.truncated is True
        assert result.max_cases == 5

    def test_max_cases_not_exceeded_when_smaller(self):
        spec = _make_spec(
            test_id="mt",
            parameters={"d1": ["a", "b"]},
            matrix=MatrixConfig(strategy="full", max_cases=10),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 2
        assert not result.truncated

    def test_pairwise_reduces_case_count(self):
        """Pairwise produces fewer cases than full for 3+ dimensions."""
        spec = _make_spec(
            test_id="pw",
            parameters={
                "a": ["a1", "a2", "a3"],
                "b": ["b1", "b2", "b3"],
                "c": ["c1", "c2", "c3"],
            },
            matrix=MatrixConfig(strategy="pairwise"),
        )
        result = expand_matrix(spec)
        # Full would be 27. Pairwise must be less.
        assert result.num_instances < 27
        assert result.num_instances >= 9  # at least covers each pair once

    def test_pairwise_covers_all_pairs(self):
        """Every pair of values from any two dimensions appears in at least one case."""
        dimensions = {
            "a": ["a1", "a2", "a3"],
            "b": ["b1", "b2"],
            "c": ["c1", "c2"],
        }
        combos = _pairwise_product(dimensions)
        # Check all pairs between a-b, a-c, b-c are covered.
        for dim1, dim2 in [("a", "b"), ("a", "c"), ("b", "c")]:
            for v1 in dimensions[dim1]:
                for v2 in dimensions[dim2]:
                    found = any(
                        c[dim1] == v1 and c[dim2] == v2 for c in combos
                    )
                    assert found, f"Pair {dim1}={v1},{dim2}={v2} not covered"

    def test_explicit_strategy(self):
        spec = _make_spec(
            test_id="ex",
            parameters={"variant": ["compact", "full"], "direction": ["A", "B"]},
            matrix=MatrixConfig(
                strategy="explicit",
                explicit_combinations=[
                    {"variant": "compact", "direction": "A"},
                    {"variant": "full", "direction": "B"},
                ],
            ),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 2
        ids = [i.instance_id for i in result.instances]
        assert "ex__direction-A__variant-compact" in ids
        assert "ex__direction-B__variant-full" in ids

    def test_sample_strategy_deterministic(self):
        """Sample with the same seed produces the same results."""
        spec = _make_spec(
            test_id="sm",
            parameters={"a": ["1", "2", "3", "4", "5"], "b": ["x", "y"]},
            matrix=MatrixConfig(strategy="sample", sample_size=3, seed=42),
        )
        result1 = expand_matrix(spec)
        result2 = expand_matrix(spec)
        assert result1.num_instances == 3
        assert [i.instance_id for i in result1.instances] == [
            i.instance_id for i in result2.instances
        ]

    def test_sample_size_exceeds_full_returns_all(self):
        spec = _make_spec(
            test_id="sm",
            parameters={"a": ["1", "2"], "b": ["x"]},
            matrix=MatrixConfig(strategy="sample", sample_size=10, seed=42),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 2  # full product is 2

    def test_dedup_overlapping_combinations(self):
        """If the full product has duplicate combos (shouldn't normally), dedup removes them."""
        # With identical values in a dimension, the full product could have dupes.
        spec = _make_spec(
            test_id="dd",
            parameters={"a": ["x", "x"], "b": ["1", "2"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        # Without dedup, 2*2=4; with dedup, a=x appears twice → 3 unique.
        ids = [i.instance_id for i in result.instances]
        assert len(ids) == len(set(ids)), "Instance IDs must be unique"

    def test_expand_all_multiple_specs(self):
        specs = [
            _make_spec(test_id="simple"),
            _make_spec(
                test_id="matrix",
                parameters={"d": ["1", "2"]},
                matrix=MatrixConfig(strategy="full"),
            ),
        ]
        instances = expand_all(specs)
        assert len(instances) == 3  # 1 + 2

    def test_parameter_application_difficulty(self):
        """Matrix 'difficulty' dimension overrides the config difficulty."""
        cfg = TestConfig(id="t", difficulty="medium")
        spec = ResolvedTestSpec(config=cfg, source_files=())
        applied = _apply_parameters(cfg, {"difficulty": "hard"})
        assert applied.difficulty == "hard"

    def test_parameter_application_temperature(self):
        """Matrix 'temperature' overrides model_parameters.temperature."""
        cfg = TestConfig(id="t")
        spec = ResolvedTestSpec(config=cfg, source_files=())
        applied = _apply_parameters(cfg, {"temperature": 0.5})
        assert applied.model_parameters is not None
        assert applied.model_parameters.temperature == 0.5

    def test_parameter_application_variant(self):
        """Matrix 'variant' overrides prompt_template.variant."""
        cfg = TestConfig(id="t")
        applied = _apply_parameters(cfg, {"variant": "compact"})
        assert applied.prompt_template is not None
        assert applied.prompt_template.variant == "compact"

    def test_parameter_application_unknown_field_to_input_variables(self):
        """Unknown dimension names go into input_variables."""
        cfg = TestConfig(id="t")
        applied = _apply_parameters(cfg, {"custom_dim": "val"})
        assert applied.input_variables.get("custom_dim") == "val"

    def test_expanded_instance_has_applied_config(self):
        spec = _make_spec(
            test_id="mt",
            difficulty="medium",
            parameters={"difficulty": ["easy", "hard"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        easy_inst = [i for i in result.instances if i.parameters.get("difficulty") == "easy"][0]
        assert easy_inst.config is not None
        assert easy_inst.config.difficulty == "easy"

    def test_expand_matrix_no_matrix_config_defaults_to_full(self):
        """If parameters exist but matrix config is None, default to full strategy."""
        spec = _make_spec(
            test_id="nm",
            parameters={"a": ["1", "2"], "b": ["x", "y"]},
            matrix=None,
        )
        result = expand_matrix(spec)
        assert result.num_instances == 4  # full product
        assert result.strategy == "full"

    def test_single_dimension(self):
        spec = _make_spec(
            test_id="sd",
            parameters={"mode": ["fast", "slow"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 2


# ══════════════════════════════════════════════════════════════════════════
# 6. DRY-RUN MODE
# ══════════════════════════════════════════════════════════════════════════


class TestDryRun:
    """Test dry-run mode."""

    def test_dry_run_no_filters(self):
        specs = _make_specs(("t1", ["a"]), ("t2", ["b"]))
        result = dry_run(specs)
        assert result.total_discovered == 2
        assert result.num_selected == 2
        assert result.num_excluded == 0
        assert result.num_disabled == 0
        assert result.total_instances == 2

    def test_dry_run_with_filters(self):
        specs = _make_specs(("t1", ["smoke"]), ("t2", ["slow"]))
        filters = SelectionFilters().add_include("tag:smoke")
        result = dry_run(specs, filters)
        assert result.num_selected == 1
        assert result.num_excluded == 0

    def test_dry_run_with_exclude(self):
        specs = _make_specs(("t1", ["smoke"]), ("t2", ["slow"]))
        filters = SelectionFilters().add_exclude("tag:slow")
        result = dry_run(specs, filters)
        assert result.num_selected == 1
        assert result.num_excluded == 1
        assert result.excluded_specs[0].id == "t2"

    def test_dry_run_disabled_separate_from_excluded(self):
        specs = [
            _make_spec(test_id="t1", enabled=True, tags=["a"]),
            _make_spec(test_id="t2", enabled=False, tags=["a"]),
            _make_spec(test_id="t3", enabled=True, tags=["b"]),
        ]
        filters = SelectionFilters().add_exclude("tag:b")
        result = dry_run(specs, filters)
        assert result.num_disabled == 1  # t2
        assert result.num_excluded == 1  # t3 (excluded by tag:b)
        assert result.num_selected == 1  # t1

    def test_dry_run_with_matrix(self):
        specs = [
            _make_spec(test_id="simple"),
            _make_spec(
                test_id="matrix",
                parameters={"d": ["1", "2", "3"]},
                matrix=MatrixConfig(strategy="full"),
            ),
        ]
        result = dry_run(specs)
        assert result.total_instances == 4  # 1 + 3
        assert len(result.expansion_results) == 2

    def test_dry_run_format_is_string(self):
        specs = _make_specs(("t1", ["a"]))
        result = dry_run(specs)
        formatted = result.format()
        assert isinstance(formatted, str)
        assert "DRY RUN" in formatted
        assert "Selection:" in formatted
        assert "Matrix Expansion:" in formatted

    def test_dry_run_format_shows_filters(self):
        specs = _make_specs(("t1", ["a"]))
        filters = SelectionFilters().add_include("tag:a").add_exclude("tag:b")
        result = dry_run(specs, filters)
        formatted = result.format()
        assert "tag:a" in formatted
        assert "tag:b" in formatted

    def test_dry_run_format_shows_matrix_details(self):
        specs = [
            _make_spec(
                test_id="mt",
                parameters={"a": ["1", "2"], "b": ["x", "y"]},
                matrix=MatrixConfig(strategy="full"),
            )
        ]
        result = dry_run(specs)
        formatted = result.format()
        assert "mt" in formatted
        assert "Strategy:" in formatted
        assert "Instances:" in formatted

    def test_dry_run_format_shows_truncation(self):
        specs = [
            _make_spec(
                test_id="mt",
                parameters={"a": ["1", "2", "3", "4", "5"]},
                matrix=MatrixConfig(strategy="full", max_cases=2),
            )
        ]
        result = dry_run(specs)
        formatted = result.format()
        assert "Truncated:" in formatted

    def test_dry_run_max_selected_truncation(self):
        specs = [
            _make_spec(test_id="t1", priority=1),
            _make_spec(test_id="t2", priority=2),
            _make_spec(test_id="t3", priority=3),
        ]
        filters = SelectionFilters(max_selected=2)
        result = dry_run(specs, filters)
        assert result.num_selected == 2
        assert [s.id for s in result.selected_specs] == ["t1", "t2"]


# ══════════════════════════════════════════════════════════════════════════
# 7. INTEGRATION WITH REAL CONFIGS
# ══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests using the real example configs from the schema task."""

    @pytest.fixture
    def loader(self) -> ConfigLoader:
        """Load the real example configs from model_benchmark/tests/."""
        loader = ConfigLoader()
        loader.reload()
        return loader

    def test_real_configs_resolve(self, loader):
        specs = loader.resolve_all()
        assert len(specs) >= 3
        ids = {s.id for s in specs}
        assert "sugarcube_markup_001" in ids
        assert "sugarcube_direction_matrix" in ids

    def test_real_matrix_expansion(self, loader):
        specs = loader.resolve_all()
        matrix_spec = loader.resolve_by_id("sugarcube_direction_matrix")
        assert matrix_spec is not None
        result = expand_matrix(matrix_spec)
        # DESIGN_NOTE example: variant[3] x direction[3] x difficulty[2] = 18.
        assert result.num_instances == 18
        assert result.strategy == "full"
        assert result.full_product_size == 18

    def test_real_matrix_ids_deterministic(self, loader):
        matrix_spec = loader.resolve_by_id("sugarcube_direction_matrix")
        result = expand_matrix(matrix_spec)
        ids = [i.instance_id for i in result.instances]
        # All IDs must be unique.
        assert len(ids) == len(set(ids))
        # All IDs must start with the source ID.
        assert all(iid.startswith("sugarcube_direction_matrix__") for iid in ids)
        # Check one specific ID format (sorted dims: difficulty, direction, variant).
        assert "sugarcube_direction_matrix__difficulty-easy__direction-A__variant-compact" in ids

    def test_real_select_by_tag_smoke(self, loader):
        specs = loader.resolve_all()
        filters = SelectionFilters().add_include("tag:smoke")
        selected = select_tests(specs, filters)
        ids = {s.id for s in selected}
        assert "sugarcube_markup_001" in ids

    def test_real_select_compound_expression(self, loader):
        specs = loader.resolve_all()
        filters = SelectionFilters().add_include("tag:regression AND NOT tag:slow")
        selected = select_tests(specs, filters)
        # All selected must have 'regression' tag and NOT 'slow'.
        for s in selected:
            assert "regression" in s.config.tags or "regression" in s.suite_tags
            assert "slow" not in s.config.tags

    def test_real_select_and_expand(self, loader):
        instances = select_and_expand(loader)
        # 5 non-matrix tests (1 each) + 1 matrix test (18) = 23.
        assert len(instances) == 23

    def test_real_dry_run(self, loader):
        specs = loader.resolve_all()
        result = dry_run(specs)
        formatted = result.format()
        assert isinstance(formatted, str)
        assert "DRY RUN" in formatted
        assert "23" in formatted  # total instances

    def test_real_select_by_suite(self, loader):
        specs = loader.resolve_all()
        filters = SelectionFilters().add_include("suite:sugarcube_core")
        selected = select_tests(specs, filters)
        assert len(selected) >= 1
        for s in selected:
            assert s.suite_name == "sugarcube_core"

    def test_real_select_by_capability(self, loader):
        specs = loader.resolve_all()
        filters = SelectionFilters().add_include("capability:sugarcube_compliance")
        selected = select_tests(specs, filters)
        assert len(selected) >= 1


# ══════════════════════════════════════════════════════════════════════════
# 8. EDGE CASES
# ══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_specs_list(self):
        selected = select_tests([])
        assert selected == []

    def test_empty_specs_dry_run(self):
        result = dry_run([])
        assert result.total_discovered == 0
        assert result.num_selected == 0
        assert result.total_instances == 0

    def test_empty_specs_expand_all(self):
        instances = expand_all([])
        assert instances == []

    def test_explicit_combinations_with_unknown_dimension(self):
        """Unknown dimension names in explicit_combinations are silently skipped."""
        spec = _make_spec(
            test_id="ex",
            parameters={"a": ["1", "2"]},
            matrix=MatrixConfig(
                strategy="explicit",
                explicit_combinations=[
                    {"a": "1"},
                    {"unknown_dim": "val"},  # should be skipped
                ],
            ),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 1  # only the known combo

    def test_single_value_dimension(self):
        spec = _make_spec(
            test_id="sv",
            parameters={"mode": ["only"]},
            matrix=MatrixConfig(strategy="full"),
        )
        result = expand_matrix(spec)
        assert result.num_instances == 1
        assert result.instances[0].parameters == {"mode": "only"}

    def test_negate_predicate_in_complex_expr(self):
        spec = _make_spec(tags=["fast"])
        # NOT (tag:slow OR tag:expert) should be True for a fast test.
        expr = parse_selection("NOT (tag:slow OR tag:expert)")
        assert eval_expr(expr, spec) is True

    def test_or_with_negation(self):
        spec = _make_spec(tags=["smoke"])
        expr = parse_selection("tag:smoke OR NOT tag:slow")
        assert eval_expr(expr, spec) is True

    def test_double_negation(self):
        spec = _make_spec(tags=["slow"])
        expr = parse_selection("NOT NOT tag:slow")
        assert eval_expr(expr, spec) is True

    def test_deeply_nested(self):
        spec = _make_spec(tags=["a", "b"], difficulty="hard")
        expr = parse_selection("((tag:a AND tag:b) OR tag:c) AND NOT (difficulty:easy OR difficulty:medium)")
        assert eval_expr(expr, spec) is True

    def test_filters_empty_include_list(self):
        """Empty include list matches everything."""
        specs = _make_specs(("t1", ["a"]))
        filters = SelectionFilters(include=[])
        selected = select_tests(specs, filters)
        assert len(selected) == 1

    def test_filters_empty_exclude_list(self):
        specs = _make_specs(("t1", ["a"]))
        filters = SelectionFilters(exclude=[])
        selected = select_tests(specs, filters)
        assert len(selected) == 1

    def test_matrix_result_repr(self):
        spec = _make_spec(test_id="t1")
        result = expand_matrix(spec)
        assert "t1" in repr(result)

    def test_expanded_instance_repr(self):
        inst = ExpandedTestInstance(
            instance_id="t1__a-1", source_id="t1", spec=_make_spec(),
            parameters={"a": "1"},
        )
        r = repr(inst)
        assert "t1__a-1" in r
        assert "a=1" in r

    def test_predicate_repr(self):
        p = Predicate(field="tag", value="smoke")
        assert str(p) == "tag:smoke"

    def test_select_and_expand_with_spec_list(self):
        specs = _make_specs(("t1", ["a"]), ("t2", ["b"]))
        instances = select_and_expand(specs)
        assert len(instances) == 2

    def test_dry_run_format_empty(self):
        result = dry_run([])
        formatted = result.format()
        assert isinstance(formatted, str)
        assert "DRY RUN" in formatted

    def test_id_generation_preserves_float_values(self):
        iid = _generate_instance_id("base", {"temperature": 0.0, "seed": 42})
        assert "temperature-0.0" in iid
        assert "seed-42" in iid
