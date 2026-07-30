#!/usr/bin/env python3
"""Test selection and parameterized matrix expansion for the SugarCube benchmark.

This module implements the test selection and matrix expansion logic that sits
between the config loader (``config_loader.py``, t_172dd683) and the benchmark
engine.  It consumes ``ResolvedTestSpec`` instances produced by the loader and
produces concrete, ready-to-execute test instances.

Five capabilities (from task t_503bdee2):

1. **Selection by name, tag, or glob pattern** — boolean expression parser
   supporting ``tag:smoke``, ``name:story_*``, ``id:arithmetic_001``,
   ``capability:reasoning``, ``category:arithmetic``, ``difficulty:hard``,
   ``suite:core``, ``enabled:true``, and compound expressions with
   ``AND``/``OR``/``NOT`` and parentheses: ``tag:regression AND NOT tag:slow``.

2. **Include/exclude filters and priority-based selection** — multiple
   ``--select`` expressions (ALL must match), multiple ``--exclude``
   expressions (ANY match removes), and priority-based truncation when
   ``max_selected`` is set (lower ``priority`` value = higher priority).

3. **Parameterized matrix expansion** — a test with ``parameters`` (dimension
   → value list) and ``matrix`` config expands into the full Cartesian product
   (or pairwise/explicit/sample) of concrete test instances, each with a
   deterministic generated ID: ``<test_id>__<dim1>-<val1>__<dim2>-<val2>``.

4. **Deduplication** — when matrix combinations produce the same generated ID
   (same dimension values), duplicates are removed.

5. **Dry-run mode** — lists what would be selected/expanded without executing,
   producing a human-readable summary.

See ``tests/DESIGN_NOTE.md`` §6 for the matrix ID format and strategies.
"""
from __future__ import annotations

import fnmatch
import hashlib
import itertools
import random
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

from model_benchmark.config_loader import ConfigLoader, ResolvedTestSpec
from model_benchmark.config_schema import MatrixConfig, TestConfig

__all__ = [
    # Expression AST
    "Predicate",
    "AndExpr",
    "OrExpr",
    "NotExpr",
    "Expr",
    # Parser
    "SelectionParser",
    "ParseError",
    "parse_selection",
    # Selection
    "SelectionFilters",
    "select_tests",
    # Matrix expansion
    "ExpandedTestInstance",
    "MatrixExpansionResult",
    "expand_matrix",
    "expand_all",
    # Dry-run
    "DryRunResult",
    "dry_run",
    # Top-level convenience
    "select_and_expand",
]

# ── Sentinel for unset priority in sorting ─────────────────────────────

# When sorting by priority, ``None`` (unset) is treated as the lowest priority
# (sorts last).  We use a large sentinel instead of ``float('inf')`` so the
# sort key remains comparable with ints.
_UNSET_PRIORITY = 10**9


# ══════════════════════════════════════════════════════════════════════════
# 1. SELECTION EXPRESSION AST + PARSER
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Predicate:
    """A single selection predicate: ``field:value``.

    ``field`` is one of: tag, name, id, capability, category, subcategory,
    difficulty, suite, enabled.  ``value`` may contain glob characters
    (``*``, ``?``, ``[...]``) for glob-based matching, except for ``difficulty``
    and ``enabled`` which use exact/boolean matching.
    """

    field: str
    value: str
    negate: bool = False

    def __str__(self) -> str:
        prefix = "NOT " if self.negate else ""
        return f"{prefix}{self.field}:{self.value}"


@dataclass(frozen=True)
class AndExpr:
    """Logical AND of sub-expressions."""

    children: tuple["Expr", ...]

    def __str__(self) -> str:
        return "(" + " AND ".join(str(c) for c in self.children) + ")"


@dataclass(frozen=True)
class OrExpr:
    """Logical OR of sub-expressions."""

    children: tuple["Expr", ...]

    def __str__(self) -> str:
        return "(" + " OR ".join(str(c) for c in self.children) + ")"


@dataclass(frozen=True)
class NotExpr:
    """Logical NOT of a sub-expression."""

    child: "Expr"

    def __str__(self) -> str:
        return f"NOT {self.child}"


Expr = Union[Predicate, AndExpr, OrExpr, NotExpr]
"""Type alias for any selection expression node."""


# ── Tokenizer ───────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
    (?P<LPAREN>\()                    # (
  | (?P<RPAREN>\))                    # )
  | (?P<AND>\bAND\b)                  # AND keyword
  | (?P<OR>\bOR\b)                    # OR keyword
  | (?P<NOT>\bNOT\b)                  # NOT keyword
  | (?P<PREDICATE>                    # field:value or field:"quoted value"
        [a-zA-Z_][a-zA-Z0-9_]*        #   field name
        \s*:\s*                       #   colon (with optional spaces)
        (?:
            "[^"]*"                   #   quoted value
          | [^\s()]+                  #   unquoted value (no spaces/parens)
        )
    )
  | (?P<WS>\s+)                       # whitespace (skipped)
    """,
    re.VERBOSE | re.IGNORECASE,
)


class ParseError(ValueError):
    """Raised when a selection expression cannot be parsed."""


def _tokenize(text: str) -> list[tuple[str, str]]:
    """Tokenize a selection expression string into (kind, value) pairs."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(
                f"Unexpected character at position {pos}: {text[pos:pos + 20]!r}"
            )
        pos = m.end()
        kind = m.lastgroup
        value = m.group()
        if kind == "WS":
            continue
        # Normalize keyword tokens to uppercase.
        if kind in ("AND", "OR", "NOT"):
            value = value.upper()
        tokens.append((kind, value))
    return tokens


# ── Recursive descent parser ────────────────────────────────────────────


class SelectionParser:
    """Recursive descent parser for selection expressions.

    Grammar (precedence: NOT > AND > OR; implicit AND between adjacent atoms)::

        expr      := or_expr
        or_expr   := and_expr (OR and_expr)*
        and_expr  := not_expr ((AND)? not_expr)*
        not_expr  := NOT not_expr | atom
        atom      := '(' expr ')' | predicate
        predicate := IDENT ':' (VALUE | "QUOTED_VALUE")
    """

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse(self) -> Expr:
        if not self._tokens:
            raise ParseError("Empty selection expression")
        expr = self._or_expr()
        if self._pos < len(self._tokens):
            raise ParseError(
                f"Unexpected token after expression: {self._tokens[self._pos]}"
            )
        return expr

    def _peek(self) -> Optional[tuple[str, str]]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> tuple[str, str]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _or_expr(self) -> Expr:
        children = [self._and_expr()]
        while True:
            tok = self._peek()
            if tok and tok[0] == "OR":
                self._advance()
                children.append(self._and_expr())
            else:
                break
        if len(children) == 1:
            return children[0]
        return OrExpr(children=tuple(children))

    def _and_expr(self) -> Expr:
        children = [self._not_expr()]
        while True:
            tok = self._peek()
            if tok and tok[0] == "AND":
                self._advance()
                children.append(self._not_expr())
            elif tok and tok[0] in ("PREDICATE", "NOT", "LPAREN"):
                # Implicit AND: adjacent atom without explicit AND keyword.
                children.append(self._not_expr())
            else:
                break
        if len(children) == 1:
            return children[0]
        return AndExpr(children=tuple(children))

    def _not_expr(self) -> Expr:
        tok = self._peek()
        if tok and tok[0] == "NOT":
            self._advance()
            return NotExpr(child=self._not_expr())
        return self._atom()

    def _atom(self) -> Expr:
        tok = self._peek()
        if tok is None:
            raise ParseError("Unexpected end of expression")
        if tok[0] == "LPAREN":
            self._advance()
            expr = self._or_expr()
            close = self._peek()
            if close is None or close[0] != "RPAREN":
                raise ParseError("Missing closing parenthesis")
            self._advance()
            return expr
        if tok[0] == "PREDICATE":
            self._advance()
            return self._parse_predicate(tok[1])
        raise ParseError(f"Unexpected token: {tok}")

    @staticmethod
    def _parse_predicate(token: str) -> Predicate:
        """Parse a ``field:value`` or ``field:"quoted value"`` token."""
        colon_idx = token.index(":")
        field_name = token[:colon_idx].strip().lower()
        raw_value = token[colon_idx + 1:].strip()
        # Strip quotes if quoted.
        if len(raw_value) >= 2 and raw_value[0] == '"' and raw_value[-1] == '"':
            value = raw_value[1:-1]
        else:
            value = raw_value
        # Validate field name.
        valid_fields = {
            "tag", "name", "id", "capability", "category",
            "subcategory", "difficulty", "suite", "enabled",
        }
        if field_name not in valid_fields:
            raise ParseError(
                f"Unknown selection field '{field_name}'. "
                f"Valid: {', '.join(sorted(valid_fields))}."
            )
        return Predicate(field=field_name, value=value)


def parse_selection(text: str) -> Expr:
    """Parse a selection expression string into an AST.

    Examples::

        parse_selection("tag:smoke")
        parse_selection("name:story_*")
        parse_selection("tag:regression AND NOT tag:slow")
        parse_selection("(tag:smoke OR tag:fast) AND NOT difficulty:expert")
    """
    tokens = _tokenize(text)
    return SelectionParser(tokens).parse()


# ══════════════════════════════════════════════════════════════════════════
# 2. EXPRESSION EVALUATION
# ══════════════════════════════════════════════════════════════════════════


def _glob_match(pattern: str, value: Optional[str]) -> bool:
    """Case-sensitive glob match.  ``None`` value never matches."""
    if value is None:
        return False
    return fnmatch.fnmatchcase(value, pattern)


def _exact_match(expected: str, value: Optional[str]) -> bool:
    """Exact match.  ``None`` value never matches."""
    if value is None:
        return False
    return value == expected


def _eval_predicate(pred: Predicate, spec: ResolvedTestSpec) -> bool:
    """Evaluate a single predicate against a resolved test spec."""
    cfg = spec.config
    result: bool

    if pred.field == "tag":
        # Glob match against any tag (including suite_tags).
        all_tags = list(cfg.tags) + list(spec.suite_tags)
        result = any(_glob_match(pred.value, t) for t in all_tags)
    elif pred.field == "name":
        result = _glob_match(pred.value, cfg.name)
    elif pred.field == "id":
        result = _glob_match(pred.value, cfg.id)
    elif pred.field == "capability":
        result = _glob_match(pred.value, cfg.capability)
    elif pred.field == "category":
        result = _glob_match(pred.value, cfg.category)
    elif pred.field == "subcategory":
        result = _glob_match(pred.value, cfg.subcategory)
    elif pred.field == "difficulty":
        # Difficulty is an enum — exact match.
        result = _exact_match(pred.value, cfg.difficulty)
    elif pred.field == "suite":
        result = _glob_match(pred.value, spec.suite_name)
    elif pred.field == "enabled":
        expected = pred.value.lower() in ("true", "yes", "1")
        actual = cfg.enabled if cfg.enabled is not None else True
        result = actual == expected
    else:
        result = False

    return (not result) if pred.negate else result


def eval_expr(expr: Expr, spec: ResolvedTestSpec) -> bool:
    """Evaluate a selection expression AST against a resolved test spec."""
    if isinstance(expr, Predicate):
        return _eval_predicate(expr, spec)
    if isinstance(expr, AndExpr):
        return all(eval_expr(child, spec) for child in expr.children)
    if isinstance(expr, OrExpr):
        return any(eval_expr(child, spec) for child in expr.children)
    if isinstance(expr, NotExpr):
        return not eval_expr(expr.child, spec)
    raise TypeError(f"Unknown expression type: {type(expr)}")


# ══════════════════════════════════════════════════════════════════════════
# 3. SELECTION FILTERS
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class SelectionFilters:
    """Include/exclude filters and priority-based selection controls.

    * ``include`` — a list of selection expressions.  A test must match ALL
      of them to be selected.
    * ``exclude`` — a list of selection expressions.  A test matching ANY of
      them is removed.
    * ``max_selected`` — if set, truncate the selected set to this many tests,
      keeping the highest-priority ones (lower ``priority`` value first).
    * ``include_disabled`` — if False (default), tests with ``enabled: false``
      are filtered out before selection expressions are applied.
    """

    include: list[Expr] = field(default_factory=list)
    exclude: list[Expr] = field(default_factory=list)
    max_selected: Optional[int] = None
    include_disabled: bool = False

    def add_include(self, expr_str: str) -> "SelectionFilters":
        """Parse and add an include expression.  Returns self for chaining."""
        self.include.append(parse_selection(expr_str))
        return self

    def add_exclude(self, expr_str: str) -> "SelectionFilters":
        """Parse and add an exclude expression.  Returns self for chaining."""
        self.exclude.append(parse_selection(expr_str))
        return self


def select_tests(
    specs: Sequence[ResolvedTestSpec],
    filters: Optional[SelectionFilters] = None,
) -> list[ResolvedTestSpec]:
    """Apply selection filters to a list of resolved test specs.

    Pipeline: disabled filter → include expressions → exclude expressions →
    priority truncation (if ``max_selected`` set).

    Returns the selected specs in priority order (lower priority value first;
    stable for equal priorities — preserves input order).
    """
    if filters is None:
        filters = SelectionFilters()

    candidates = list(specs)

    # Filter out disabled tests (unless include_disabled).
    if not filters.include_disabled:
        candidates = [
            s for s in candidates
            if (s.config.enabled if s.config.enabled is not None else True)
        ]

    # Apply include expressions (ALL must match).
    if filters.include:
        candidates = [
            s for s in candidates
            if all(eval_expr(expr, s) for expr in filters.include)
        ]

    # Apply exclude expressions (ANY match removes).
    if filters.exclude:
        candidates = [
            s for s in candidates
            if not any(eval_expr(expr, s) for expr in filters.exclude)
        ]

    # Priority truncation.
    if filters.max_selected is not None and len(candidates) > filters.max_selected:
        # Sort by priority (lower = higher priority), stable for ties.
        candidates = _sort_by_priority(candidates)
        candidates = candidates[: filters.max_selected]
    else:
        # Still sort by priority for deterministic ordering (but no truncation).
        candidates = _sort_by_priority(candidates)

    return candidates


def _sort_by_priority(specs: Sequence[ResolvedTestSpec]) -> list[ResolvedTestSpec]:
    """Stable sort by priority (lower value = higher priority, None = last)."""
    # Python's sort is stable, so equal-priority items keep their input order.
    indexed = list(enumerate(specs))
    indexed.sort(
        key=lambda pair: (
            pair[1].config.priority if pair[1].config.priority is not None else _UNSET_PRIORITY,
            pair[0],
        ),
    )
    return [s for _, s in indexed]


# ══════════════════════════════════════════════════════════════════════════
# 4. MATRIX EXPANSION
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExpandedTestInstance:
    """A single concrete test instance after matrix expansion.

    ``instance_id`` is the deterministic generated ID:
    ``<source_id>__<dim1>-<val1>__<dim2>-<val2>``.

    For tests without a matrix, ``instance_id`` equals ``source_id`` and
    ``parameters`` is empty.
    """

    instance_id: str
    source_id: str
    spec: ResolvedTestSpec
    parameters: dict[str, Any] = field(default_factory=dict)
    config: Optional[TestConfig] = None

    @property
    def is_matrix_expansion(self) -> bool:
        return bool(self.parameters)

    def __repr__(self) -> str:
        params = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return f"<ExpandedTestInstance {self.instance_id} ({params})>"


@dataclass
class MatrixExpansionResult:
    """Result of expanding a single test's matrix."""

    source_id: str
    strategy: str
    dimensions: dict[str, list]
    instances: list[ExpandedTestInstance]
    truncated: bool = False
    max_cases: Optional[int] = None

    @property
    def num_instances(self) -> int:
        return len(self.instances)

    @property
    def full_product_size(self) -> int:
        """Size of the full Cartesian product (before strategy reduction)."""
        if not self.dimensions:
            return 1
        size = 1
        for vals in self.dimensions.values():
            size *= len(vals)
        return size


# ── ID generation ───────────────────────────────────────────────────────


def _sanitize_value(value: Any) -> str:
    """Convert a dimension value to a URL-safe ID component.

    Replaces characters that are problematic in IDs/pathnames with ``_``.
    Floats like ``0.0`` keep their decimal point; booleans become ``true``/
    ``false``; ``None`` becomes ``none``.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    s = str(value)
    # Replace path-unsafe characters: /, :, space, etc.
    s = re.sub(r"[^\w.\-]", "_", s)
    return s


def _generate_instance_id(source_id: str, params: dict[str, Any]) -> str:
    """Generate a deterministic instance ID from source ID + parameter values.

    Format: ``<source_id>__<dim1>-<val1>__<dim2>-<val2>``
    (per DESIGN_NOTE.md §6).

    Dimension names are sorted alphabetically for deterministic ordering
    regardless of the dict iteration order.
    """
    if not params:
        return source_id
    parts = [source_id]
    for dim_name in sorted(params):
        val_str = _sanitize_value(params[dim_name])
        parts.append(f"{dim_name}-{val_str}")
    return "__".join(parts)


# ── Strategy implementations ───────────────────────────────────────────


def _full_product(dimensions: dict[str, list]) -> list[dict[str, Any]]:
    """Full Cartesian product of all dimensions."""
    if not dimensions:
        return [{}]
    keys = list(dimensions.keys())
    value_lists = [dimensions[k] for k in keys]
    return [
        dict(zip(keys, combo))
        for combo in itertools.product(*value_lists)
    ]


def _pairwise_product(dimensions: dict[str, list]) -> list[dict[str, Any]]:
    """Pairwise (all-pairs) combination using a greedy algorithm.

    Produces a minimal set of test cases such that every pair of values from
    any two dimensions appears in at least one case.  For 0-2 dimensions this
    is the full product; for 3+ it greedily selects from the full product.
    """
    if not dimensions:
        return [{}]
    dim_names = list(dimensions.keys())
    dim_values = [dimensions[k] for k in dim_names]

    if len(dim_names) <= 2:
        # Full product for 0-2 dimensions — all pairs are already covered.
        return _full_product(dimensions)

    # Generate all pairs that need to be covered.
    all_pairs: set[tuple[str, Any, str, Any]] = set()
    for i, j in itertools.combinations(range(len(dim_names)), 2):
        for vi, vj in itertools.product(dim_values[i], dim_values[j]):
            all_pairs.add((dim_names[i], vi, dim_names[j], vj))

    # Generate the full product as candidates.
    full = _full_product(dimensions)

    # Greedily select cases that cover the most uncovered pairs.
    selected: list[dict[str, Any]] = []
    uncovered = set(all_pairs)

    # Shuffle candidates deterministically for tie-breaking (helps coverage).
    # Use a stable secondary sort by the string repr for determinism.
    for case in full:
        if not uncovered:
            break
        # Count how many uncovered pairs this case covers.
        count = 0
        for i, j in itertools.combinations(range(len(dim_names)), 2):
            pair = (dim_names[i], case[dim_names[i]], dim_names[j], case[dim_names[j]])
            if pair in uncovered:
                count += 1
        if count == 0:
            continue
        # We want the case with the maximum count; track the best.
        # Since we iterate in order, we need to find the max — but for
        # efficiency we'll just take cases in order if they cover > 0.
        # A proper greedy would find the max; let's do that.

    # Reset for proper greedy selection.
    selected = []
    uncovered = set(all_pairs)

    while uncovered:
        best_case: Optional[dict[str, Any]] = None
        best_count = 0
        for case in full:
            count = 0
            for i, j in itertools.combinations(range(len(dim_names)), 2):
                pair = (
                    dim_names[i], case[dim_names[i]],
                    dim_names[j], case[dim_names[j]],
                )
                if pair in uncovered:
                    count += 1
            if count > best_count:
                best_count = count
                best_case = case

        if best_case is None or best_count == 0:
            break

        selected.append(best_case)
        for i, j in itertools.combinations(range(len(dim_names)), 2):
            pair = (
                dim_names[i], best_case[dim_names[i]],
                dim_names[j], best_case[dim_names[j]],
            )
            uncovered.discard(pair)

    return selected


def _explicit_combinations(
    dimensions: dict[str, list],
    matrix_config: MatrixConfig,
) -> list[dict[str, Any]]:
    """Only the combinations listed in ``explicit_combinations``."""
    if not matrix_config.explicit_combinations:
        return []
    result: list[dict[str, Any]] = []
    for combo in matrix_config.explicit_combinations:
        # Validate that all keys are known dimensions.
        validated: dict[str, Any] = {}
        for key, val in combo.items():
            if key not in dimensions:
                # Unknown dimension in explicit combination — skip with warning.
                continue
            validated[key] = val
        if validated:
            result.append(validated)
    return result


def _sample_combinations(
    dimensions: dict[str, list],
    matrix_config: MatrixConfig,
) -> list[dict[str, Any]]:
    """Random sample of ``sample_size`` cases from the full product."""
    full = _full_product(dimensions)
    sample_size = matrix_config.sample_size or len(full)
    seed = matrix_config.seed
    rng = random.Random(seed)
    if sample_size >= len(full):
        return full
    return rng.sample(full, sample_size)


def _apply_strategy(
    dimensions: dict[str, list],
    matrix_config: MatrixConfig,
) -> list[dict[str, Any]]:
    """Apply the matrix strategy to generate parameter combinations."""
    strategy = matrix_config.strategy
    if strategy == "full":
        return _full_product(dimensions)
    if strategy == "pairwise":
        return _pairwise_product(dimensions)
    if strategy == "explicit":
        return _explicit_combinations(dimensions, matrix_config)
    if strategy == "sample":
        return _sample_combinations(dimensions, matrix_config)
    raise ValueError(f"Unknown matrix strategy: {strategy}")


# ── Parameter application to config ─────────────────────────────────────


# Fields that can be overridden directly on TestConfig (scalar fields only).
_DIRECT_OVERRIDE_FIELDS: frozenset[str] = frozenset({
    "difficulty", "timeout", "repetitions", "random_seed",
    "max_input_tokens", "max_output_tokens", "priority",
})

# Special mappings: dimension name → nested config path.
_SPECIAL_OVERRIDES: dict[str, tuple[str, ...]] = {
    "variant": ("prompt_template", "variant"),
    "temperature": ("model_parameters", "temperature"),
    "num_predict": ("model_parameters", "num_predict"),
    "top_p": ("model_parameters", "top_p"),
    "top_k": ("model_parameters", "top_k"),
    "seed": ("model_parameters", "seed"),
    "timeout": ("model_parameters", "timeout"),  # also a direct field, but
    # model_parameters.timeout is where it lives for generation.
}


def _apply_parameters(
    base_config: TestConfig,
    params: dict[str, Any],
) -> TestConfig:
    """Apply matrix parameter values to a TestConfig, returning a new instance.

    Mapping rules:
    * If the dimension name is a known direct TestConfig scalar field
      (difficulty, timeout, repetitions, etc.), override that field.
    * If the dimension name has a special override path (variant →
      prompt_template.variant, temperature → model_parameters.temperature),
      override at that path.
    * Otherwise, inject the value into ``input_variables[dim_name]``.

    Non-matrix tests (empty params) return the config unchanged.
    """
    if not params:
        return base_config

    data = base_config.model_dump(exclude_none=False)

    for dim_name, value in params.items():
        if dim_name in _DIRECT_OVERRIDE_FIELDS:
            data[dim_name] = value
        elif dim_name in _SPECIAL_OVERRIDES:
            # Navigate the nested dict path.
            path = _SPECIAL_OVERRIDES[dim_name]
            d = data
            for key in path[:-1]:
                if d.get(key) is None:
                    d[key] = {}
                d = d[key]
            d[path[-1]] = value
        else:
            # Inject into input_variables.
            if data.get("input_variables") is None:
                data["input_variables"] = {}
            data["input_variables"][dim_name] = value

    return TestConfig(**data)


# ── Expansion functions ──────────────────────────────────────────────────


def expand_matrix(spec: ResolvedTestSpec) -> MatrixExpansionResult:
    """Expand a single test's parameterized matrix into concrete instances.

    If the test has no ``parameters``/``matrix``, returns a single instance
    (the test itself, unchanged).

    If ``matrix.max_cases`` is set and the expansion exceeds it, the result is
    truncated to ``max_cases`` instances (in deterministic order), and
    ``truncated`` is set to True.
    """
    cfg = spec.config
    dimensions = cfg.parameters or {}
    matrix_config = cfg.matrix

    # No parameters → single instance (the test itself).
    if not dimensions:
        instance = ExpandedTestInstance(
            instance_id=spec.id,
            source_id=spec.id,
            spec=spec,
            parameters={},
            config=cfg,
        )
        return MatrixExpansionResult(
            source_id=spec.id,
            strategy="none",
            dimensions={},
            instances=[instance],
        )

    # If matrix config is missing but parameters exist, default to full.
    if matrix_config is None:
        matrix_config = MatrixConfig(strategy="full")

    # Generate combinations.
    combos = _apply_strategy(dimensions, matrix_config)

    # Deduplicate by generated ID (handles overlapping combinations).
    seen_ids: dict[str, dict[str, Any]] = {}
    unique_combos: list[dict[str, Any]] = []
    for combo in combos:
        iid = _generate_instance_id(spec.id, combo)
        if iid not in seen_ids:
            seen_ids[iid] = combo
            unique_combos.append(combo)

    # Truncate to max_cases if set.
    truncated = False
    max_cases = matrix_config.max_cases
    if max_cases is not None and len(unique_combos) > max_cases:
        unique_combos = unique_combos[:max_cases]
        truncated = True

    # Build instances.
    instances: list[ExpandedTestInstance] = []
    for combo in unique_combos:
        iid = _generate_instance_id(spec.id, combo)
        applied_config = _apply_parameters(cfg, combo)
        instances.append(ExpandedTestInstance(
            instance_id=iid,
            source_id=spec.id,
            spec=spec,
            parameters=dict(combo),
            config=applied_config,
        ))

    return MatrixExpansionResult(
        source_id=spec.id,
        strategy=matrix_config.strategy,
        dimensions={k: list(v) for k, v in dimensions.items()},
        instances=instances,
        truncated=truncated,
        max_cases=max_cases,
    )


def expand_all(
    specs: Sequence[ResolvedTestSpec],
) -> list[ExpandedTestInstance]:
    """Expand matrix for all specs, returning a flat list of test instances.

    Tests without matrices produce a single instance each; tests with matrices
    produce one instance per parameter combination.
    """
    instances: list[ExpandedTestInstance] = []
    for spec in specs:
        result = expand_matrix(spec)
        instances.extend(result.instances)
    return instances


# ══════════════════════════════════════════════════════════════════════════
# 5. DRY-RUN MODE
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class DryRunResult:
    """Result of a dry-run: what would be selected and expanded.

    Contains the full pipeline breakdown for human-readable output.
    """

    total_discovered: int
    selected_specs: list[ResolvedTestSpec]
    excluded_specs: list[ResolvedTestSpec]
    disabled_specs: list[ResolvedTestSpec]
    expansion_results: list[MatrixExpansionResult]
    total_instances: int
    filters: SelectionFilters

    @property
    def num_selected(self) -> int:
        return len(self.selected_specs)

    @property
    def num_excluded(self) -> int:
        return len(self.excluded_specs)

    @property
    def num_disabled(self) -> int:
        return len(self.disabled_specs)

    @property
    def num_truncated(self) -> int:
        return sum(1 for r in self.expansion_results if r.truncated)

    def format(self) -> str:
        """Format the dry-run result as a human-readable string."""
        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("DRY RUN — Test Selection & Matrix Expansion")
        lines.append("=" * 72)
        lines.append("")

        # Filters summary.
        lines.append("Filters:")
        if self.filters.include:
            lines.append(f"  Include (ALL must match):")
            for expr in self.filters.include:
                lines.append(f"    - {expr}")
        else:
            lines.append("  Include: (none — all tests match)")
        if self.filters.exclude:
            lines.append(f"  Exclude (ANY match removes):")
            for expr in self.filters.exclude:
                lines.append(f"    - {expr}")
        else:
            lines.append("  Exclude: (none)")
        if self.filters.max_selected is not None:
            lines.append(f"  Max selected: {self.filters.max_selected}")
        lines.append(f"  Include disabled: {self.filters.include_disabled}")
        lines.append("")

        # Selection summary.
        lines.append(f"Selection:")
        lines.append(f"  Discovered:  {self.total_discovered}")
        lines.append(f"  Disabled:    {self.num_disabled}")
        lines.append(f"  Excluded:    {self.num_excluded}")
        lines.append(f"  Selected:    {self.num_selected}")
        lines.append("")

        # Per-test expansion.
        lines.append("Matrix Expansion:")
        lines.append(f"  Total instances: {self.total_instances}")
        if self.num_truncated:
            lines.append(f"  Truncated tests: {self.num_truncated}")
        lines.append("")

        for result in self.expansion_results:
            lines.append(f"  ── {result.source_id} ──")
            if result.strategy == "none":
                lines.append(f"    Strategy:  (no matrix — 1 instance)")
                if result.instances:
                    lines.append(f"    Instance:  {result.instances[0].instance_id}")
            else:
                dim_summary = ", ".join(
                    f"{k}[{len(v)}]" for k, v in result.dimensions.items()
                )
                full_size = result.full_product_size
                lines.append(f"    Strategy:    {result.strategy}")
                lines.append(f"    Dimensions:  {dim_summary}")
                lines.append(f"    Full product: {full_size}")
                lines.append(f"    Instances:   {result.num_instances}")
                if result.truncated:
                    lines.append(f"    Truncated:   yes (max_cases={result.max_cases})")
                # Show first few instance IDs.
                show = result.instances[:5]
                for inst in show:
                    param_str = ", ".join(
                        f"{k}={v}" for k, v in inst.parameters.items()
                    )
                    lines.append(f"      → {inst.instance_id}  ({param_str})")
                if len(result.instances) > 5:
                    lines.append(
                        f"      ... and {len(result.instances) - 5} more"
                    )
            lines.append("")

        lines.append("=" * 72)
        lines.append(
            f"Summary: {self.num_selected} test(s) → {self.total_instances} instance(s)"
        )
        lines.append("=" * 72)
        return "\n".join(lines)


def dry_run(
    specs: Sequence[ResolvedTestSpec],
    filters: Optional[SelectionFilters] = None,
) -> DryRunResult:
    """Run the selection + expansion pipeline without executing tests.

    Returns a ``DryRunResult`` with the full breakdown.  Call ``.format()``
    for human-readable output.
    """
    if filters is None:
        filters = SelectionFilters()

    total_discovered = len(specs)

    # Separate disabled tests.
    if filters.include_disabled:
        disabled: list[ResolvedTestSpec] = []
        active = list(specs)
    else:
        disabled = [
            s for s in specs
            if not (s.config.enabled if s.config.enabled is not None else True)
        ]
        active = [
            s for s in specs
            if (s.config.enabled if s.config.enabled is not None else True)
        ]

    # Apply include expressions.
    included = active
    if filters.include:
        included = [
            s for s in active
            if all(eval_expr(expr, s) for expr in filters.include)
        ]

    # Apply exclude expressions — excluded = included but matching an exclude.
    excluded: list[ResolvedTestSpec] = []
    if filters.exclude:
        excluded = [
            s for s in included
            if any(eval_expr(expr, s) for expr in filters.exclude)
        ]
        included = [
            s for s in included
            if not any(eval_expr(expr, s) for expr in filters.exclude)
        ]

    # Priority truncation.
    selected = _sort_by_priority(included)
    if filters.max_selected is not None and len(selected) > filters.max_selected:
        selected = selected[: filters.max_selected]

    # Expand matrices.
    expansion_results = [expand_matrix(spec) for spec in selected]
    total_instances = sum(r.num_instances for r in expansion_results)

    return DryRunResult(
        total_discovered=total_discovered,
        selected_specs=selected,
        excluded_specs=excluded,
        disabled_specs=disabled,
        expansion_results=expansion_results,
        total_instances=total_instances,
        filters=filters,
    )


# ══════════════════════════════════════════════════════════════════════════
# 6. TOP-LEVEL CONVENIENCE
# ══════════════════════════════════════════════════════════════════════════


def select_and_expand(
    source: Union[ConfigLoader, Sequence[ResolvedTestSpec]],
    filters: Optional[SelectionFilters] = None,
) -> list[ExpandedTestInstance]:
    """Select tests and expand matrices in one step.

    Args:
        source: A ``ConfigLoader`` (calls ``resolve_all()``) or a pre-resolved
            list of ``ResolvedTestSpec`` instances.
        filters: Selection filters.  If None, all tests are selected.

    Returns a flat list of ``ExpandedTestInstance`` ready for execution.
    """
    if isinstance(source, ConfigLoader):
        specs = source.resolve_all()
    else:
        specs = list(source)

    selected = select_tests(specs, filters)
    return expand_all(selected)


if __name__ == "__main__":
    # CLI: dry-run on the default config directory.
    import sys

    loader = ConfigLoader()
    loader.reload()
    specs = loader.resolve_all()
    if not specs:
        print("No test configs discovered.")
        sys.exit(0)

    # Parse CLI args for --select / --exclude.
    filters = SelectionFilters()
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--select" and i + 1 < len(args):
            filters.add_include(args[i + 1])
            i += 2
        elif args[i] == "--exclude" and i + 1 < len(args):
            filters.add_exclude(args[i + 1])
            i += 2
        elif args[i] == "--max-selected" and i + 1 < len(args):
            filters.max_selected = int(args[i + 1])
            i += 2
        elif args[i] == "--include-disabled":
            filters.include_disabled = True
            i += 1
        else:
            i += 1

    result = dry_run(specs, filters)
    print(result.format())
