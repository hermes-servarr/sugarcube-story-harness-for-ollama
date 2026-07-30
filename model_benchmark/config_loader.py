#!/usr/bin/env python3
"""Config loader for the SugarCube model benchmark.

This module is the bridge between the declarative test configuration schema
(``config_schema.py``) and the benchmark engine (``benchmark.py``).  It:

* **Discovers** test config files (YAML/JSON) by scanning a configurable set of
  directories (default: ``model_benchmark/tests/**/*.{yaml,yml,json}``).
* **Loads** each file, auto-detecting document kind, supporting multi-doc YAML.
* **Validates** every loaded document against the pydantic schema, collecting
  *all* errors (each with file path + line number context) before failing.
* **Merges** config layers per the hierarchy defined in the design note:
  built-in → global defaults → suite defaults → test config.
* **Resolves** every test into a normalized ``ResolvedTestSpec`` — a
  fully-merged, ready-to-execute test definition the engine consumes.
* Provides a **registry** (``ConfigLoader``) so custom directories can be
  added programmatically and the loader can be extended/reconfigured at runtime.

Acceptance criteria (from the task body):
* discovers and validates the example configs from the schema task
* rejects invalid configs with clear error messages (file + line context)
* the resolved output matches expected merge results

See ``model_benchmark/tests/DESIGN_NOTE.md`` for merge semantics and the
layered hierarchy this loader implements.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

import yaml
from pydantic import ValidationError

from model_benchmark.config_schema import (
    BUILTIN_DEFAULTS,
    ConfigDocument,
    DefaultsDocument,
    MergePolicy,
    SuiteDocument,
    TestConfig,
    TestDocument,
    deep_merge,
    parse_config_dict,
    resolve_test,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigError",
    "ConfigErrorCollection",
    "LoadedDocument",
    "ResolvedTestSpec",
    "ConfigLoader",
    "load_directory",
    "load_file",
    "default_search_dirs",
]

# ── Defaults ───────────────────────────────────────────────────────────

# Default search roots (relative to a project root or absolute).
DEFAULT_ROOT = "model_benchmark/tests"
# File extensions we treat as config files.
CONFIG_GLOBS: tuple[str, ...] = ("*.yaml", "*.yml", "*.json")
# Subdirectories that typically hold different document kinds.
# Discovery scans these recursively.
_DEFAULT_DIR_KINDS: dict[str, str] = {
    "defaults": "defaults",
    "suites": "suites",
    "cases": "cases",
    "examples": "examples",
}

# Directories under the tests root that are NOT config files and must be
# excluded from discovery.  ``schemas/`` holds the JSON Schema export (a
# ``.json`` file, but not a test config); ``prompts/`` holds prompt templates.
_EXCLUDE_SUBDIRS: frozenset[str] = frozenset({"schemas", "prompts", "evaluators"})


def default_search_dirs(project_root: Optional[Union[str, Path]] = None) -> list[Path]:
    """Return the default list of directories the loader scans.

    By default this is ``<root>/model_benchmark/tests`` and its subdirectories
    (``defaults``, ``suites``, ``cases``, ``examples``).  Only directories that
    exist on disk are returned, so callers can iterate without guarding.
    """
    root = Path(project_root) if project_root else Path.cwd()
    base = root / DEFAULT_ROOT
    dirs: list[Path] = []
    if base.is_dir():
        dirs.append(base)
    for sub in _DEFAULT_DIR_KINDS.values():
        sub_path = base / sub
        if sub_path.is_dir():
            dirs.append(sub_path)
    return dirs


# ── Errors ─────────────────────────────────────────────────────────────


@dataclass
class ConfigError:
    """A single validation error with file path + line number context.

    ``location`` is a human-readable string like ``"path/to/file.yaml:42"``
    (line number when known, else just the path).  ``loc`` is the pydantic
    field-path tuple (e.g. ``("defaults", "timeout")``) when available.
    """

    file_path: Path
    message: str
    line: Optional[int] = None
    loc: tuple[Any, ...] = field(default_factory=tuple)
    doc_index: Optional[int] = None  # for multi-doc YAML (0-based)

    @property
    def location(self) -> str:
        parts = [str(self.file_path)]
        if self.doc_index is not None:
            parts.append(f"doc#{self.doc_index}")
        if self.line is not None:
            parts.append(f"line {self.line}")
        return ":".join(parts) if len(parts) > 1 else parts[0]

    def __str__(self) -> str:
        loc_str = f" ({'.'.join(str(x) for x in self.loc)})" if self.loc else ""
        return f"[{self.location}] {self.message}{loc_str}"


@dataclass
class ConfigErrorCollection(Exception):
    """Raised when one or more config files fail validation.

    Carries all collected errors so callers can report them together rather
    than failing on the first one.  Iterate ``.errors`` for structured access
    or ``str(collection)`` for a formatted multi-line message.
    """

    errors: list[ConfigError] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.errors:
            return "No errors"
        header = f"{len(self.errors)} config validation error(s):\n"
        body = "\n".join(f"  {i + 1}. {e}" for i, e in enumerate(self.errors))
        return header + body

    def add(self, error: ConfigError) -> None:
        self.errors.append(error)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


# ── Loaded document ─────────────────────────────────────────────────────


@dataclass
class LoadedDocument:
    """A successfully parsed and validated config document, with provenance.

    ``source_path`` is the file it came from; ``doc_index`` is the 0-based
    position within a multi-doc YAML file (``None`` for JSON or single-doc).
    """

    document: ConfigDocument
    source_path: Path
    doc_index: Optional[int] = None

    @property
    def kind(self) -> str:
        return self.document.kind  # type: ignore[union-attr]

    @property
    def id(self) -> str:
        """Return the document's identifying key (id for tests, name for suites)."""
        if isinstance(self.document, TestDocument):
            return self.document.id
        if isinstance(self.document, SuiteDocument):
            return self.document.name
        return "defaults"

    def __repr__(self) -> str:
        idx = f"#{self.doc_index}" if self.doc_index is not None else ""
        return f"<LoadedDocument {self.kind}:{self.id} from {self.source_path}{idx}>"


# ── Resolved test spec (the engine-facing normalized representation) ────


@dataclass(frozen=True)
class ResolvedTestSpec:
    """A fully-resolved, ready-to-execute test specification.

    This is the normalized in-memory representation the benchmark engine
    consumes.  It is produced by ``ConfigLoader.resolve()`` after merging all
    config layers (built-in → global → suite → test).  Each spec corresponds
    to a single concrete test case (matrix dimensions already expanded by
    the selection/matrix task, t_503bdee2 — but the *base* spec is produced
    here; matrix expansion is a downstream concern that consumes this).

    ``config`` is the fully-merged ``TestConfig``.  ``source_files`` traces
    every file that contributed to this test (for provenance/debugging).
    ``suite_name`` is ``None`` for standalone tests not in any suite.
    """

    config: TestConfig
    source_files: tuple[str, ...] = field(default_factory=tuple)
    suite_name: Optional[str] = None
    suite_tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return self.config.id or ""

    @property
    def enabled(self) -> bool:
        return self.config.enabled if self.config.enabled is not None else True

    def __repr__(self) -> str:
        suite = f" suite={self.suite_name}" if self.suite_name else ""
        return f"<ResolvedTestSpec id={self.id!r}{suite}>"


# ── Line number extraction ─────────────────────────────────────────────


def _find_line_for_path(raw_lines: Sequence[str], doc_start: int, loc: tuple) -> Optional[int]:
    """Best-effort: find a line number for a pydantic ``loc`` path.

    This walks the YAML/JSON lines of a single document looking for the last
    element of ``loc`` (a field name).  ``doc_start`` is the 0-based line
    index where this document begins in the file.  It is a heuristic; YAML
    anchors/flow style may defeat it, in which case we return ``None``.
    """
    if not loc:
        return None
    key = str(loc[-1])
    # Look for ``key:`` (YAML) or ``"key"`` (JSON) within the document's lines.
    for i in range(len(raw_lines) - 1, doc_start - 1, -1):
        line = raw_lines[i]
        # YAML: `  key:` or `  key: value`
        if f"{key}:" in line:
            return i + 1  # 1-based line numbers
        # JSON: `"key":`
        if f'"{key}"' in line:
            return i + 1
    return None


def _doc_line_ranges(raw_text: str) -> list[tuple[int, int]]:
    """Return (start_line, end_line) ranges for each YAML document in a multi-doc file.

    For JSON (single doc), returns [(1, len(lines))].  Lines are 1-based.
    """
    lines = raw_text.splitlines()
    if not lines:
        return [(1, 0)]
    # Detect YAML document separators (lines that are exactly ``---``).
    starts = [1]
    for i, line in enumerate(lines):
        if line.strip() == "---":
            starts.append(i + 2)  # next line is 1-based i+2
    ranges: list[tuple[int, int]] = []
    for idx, s in enumerate(starts):
        e = (starts[idx + 1] - 2) if idx + 1 < len(starts) else len(lines)
        ranges.append((s, e))
    return ranges


# ── File loading ───────────────────────────────────────────────────────


def load_file(
    path: Union[str, Path],
    errors: Optional[list[ConfigError]] = None,
) -> list[LoadedDocument]:
    """Load and validate a single config file.

    Supports both YAML (including multi-doc ``---`` separated) and JSON.
    Returns a list of ``LoadedDocument`` (one per YAML document; one for JSON).
    Any validation errors are appended to ``errors`` (if provided) rather
    than raised immediately, so callers can collect all errors across files.

    Raises ``ConfigErrorCollection`` if ``errors`` is ``None`` and validation
    fails (immediate-fail mode).  When ``errors`` is a list, validation
    failures are appended and an empty list is returned for that file.
    """
    file_path = Path(path)
    own_errors: list[ConfigError] = errors if errors is not None else []

    if not file_path.is_file():
        err = ConfigError(file_path=file_path, message="File not found")
        if errors is None:
            raise ConfigErrorCollection(errors=[err])
        own_errors.append(err)
        return []

    raw_text = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    # Parse into a list of raw dicts (one per YAML document).
    raw_docs: list[dict[str, Any]] = []
    doc_line_starts: list[int] = []

    try:
        if suffix == ".json":
            data = json.loads(raw_text)
            if isinstance(data, list):
                # A JSON array of documents.
                for item in data:
                    if not isinstance(item, dict):
                        raise ValueError(f"Expected a dict in JSON array, got {type(item).__name__}")
                    raw_docs.append(item)
            elif isinstance(data, dict):
                raw_docs.append(data)
            else:
                raise ValueError(f"Expected a JSON object or array, got {type(data).__name__}")
            doc_line_starts = [1] * len(raw_docs)
        else:
            # YAML — may be multi-doc.
            loaded = list(yaml.safe_load_all(raw_text))
            ranges = _doc_line_ranges(raw_text)
            for i, doc in enumerate(loaded):
                if doc is None:
                    continue  # skip empty docs (trailing ---)
                if not isinstance(doc, dict):
                    raise ValueError(
                        f"YAML document {i} is not a mapping (got {type(doc).__name__})"
                    )
                raw_docs.append(doc)
                start = ranges[i][0] if i < len(ranges) else 1
                doc_line_starts.append(start)
    except (yaml.YAMLError, json.JSONDecodeError, ValueError) as exc:
        err = ConfigError(file_path=file_path, message=f"Parse error: {exc}")
        if errors is None:
            raise ConfigErrorCollection(errors=[err])
        own_errors.append(err)
        return []

    # Validate each raw dict against the schema.
    results: list[LoadedDocument] = []
    raw_lines = raw_text.splitlines()

    for doc_idx, raw_dict in enumerate(raw_docs):
        doc_start_line = doc_line_starts[doc_idx] if doc_idx < len(doc_line_starts) else 1
        try:
            document = parse_config_dict(raw_dict)
        except ValidationError as exc:
            # Must be caught BEFORE ValueError — pydantic's ValidationError
            # is a subclass of ValueError in both v1 and v2.
            _collect_pydantic_errors(
                exc, file_path, doc_idx if len(raw_docs) > 1 else None,
                raw_lines, doc_start_line, own_errors,
            )
            continue
        except ValueError as exc:
            # Discrimination error (ambiguous/unknown kind) or other ValueError.
            err = ConfigError(
                file_path=file_path,
                message=str(exc),
                doc_index=doc_idx if len(raw_docs) > 1 else None,
            )
            own_errors.append(err)
            continue

        results.append(
            LoadedDocument(
                document=document,
                source_path=file_path,
                doc_index=doc_idx if len(raw_docs) > 1 else None,
            )
        )

    if errors is None and own_errors:
        raise ConfigErrorCollection(errors=list(own_errors))

    return results


def _collect_pydantic_errors(
    exc: ValidationError,
    file_path: Path,
    doc_index: Optional[int],
    raw_lines: Sequence[str],
    doc_start_line: int,
    out: list[ConfigError],
) -> None:
    """Convert a pydantic ValidationError into one or more ConfigError entries.

    Pydantic v2's ``ValidationError.errors()`` returns one entry per field
    error, so a single document with two bad fields produces two entries here.
    """
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        msg = err.get("msg", "Validation error")
        err_type = err.get("type", "")
        full_msg = f"{msg}" if not err_type else f"{msg} (type={err_type})"
        line = _find_line_for_path(raw_lines, doc_start_line - 1, loc)
        out.append(
            ConfigError(
                file_path=file_path,
                message=full_msg,
                line=line,
                loc=loc,
                doc_index=doc_index,
            )
        )


# ── Directory discovery ────────────────────────────────────────────────


def _discover_files(dirs: Iterable[Union[str, Path]]) -> list[Path]:
    """Recursively scan ``dirs`` for config files (YAML/JSON).

    Returns a sorted list of unique file paths.  Files are matched by
    ``CONFIG_GLOBS``.  Sorting is deterministic (by path) so load order is
    stable across runs.
    """
    seen: set[Path] = set()
    files: list[Path] = []
    for d in dirs:
        dir_path = Path(d)
        if not dir_path.is_dir():
            continue
        for glob in CONFIG_GLOBS:
            for f in dir_path.rglob(glob):
                if not f.is_file() or f in seen:
                    continue
                # Exclude non-config subdirectories (schemas/, prompts/, ...).
                if any(part in _EXCLUDE_SUBDIRS for part in f.relative_to(dir_path).parts[:-1]):
                    continue
                seen.add(f)
                files.append(f)
    files.sort()
    return files


def load_directory(
    dirs: Union[str, Path, Sequence[Union[str, Path]], None] = None,
    *,
    collect_errors: bool = True,
) -> tuple[list[LoadedDocument], list[ConfigError]]:
    """Discover and load all config files under ``dirs``.

    Args:
        dirs: One or more directories to scan.  If ``None``, uses
            ``default_search_dirs()``.
        collect_errors: If True (default), validation errors are collected
            and returned alongside successfully loaded documents.  If False,
            the first error raises ``ConfigErrorCollection``.

    Returns a ``(documents, errors)`` tuple.  When ``collect_errors`` is
    False and errors occur, ``ConfigErrorCollection`` is raised instead.
    """
    if dirs is None:
        dirs = default_search_dirs()
    elif isinstance(dirs, (str, Path)):
        dirs = [dirs]

    files = _discover_files(dirs)
    errors: list[ConfigError] = []
    documents: list[LoadedDocument] = []

    for f in files:
        if collect_errors:
            docs = load_file(f, errors=errors)
            documents.extend(docs)
        else:
            try:
                docs = load_file(f, errors=None)
                documents.extend(docs)
            except ConfigErrorCollection as exc:
                raise

    return documents, errors


# ── ConfigLoader (the registry) ───────────────────────────────────────


class ConfigLoader:
    """Stateful config loader with a directory registry.

    The loader maintains a list of search directories (the "registry") that
    can be extended programmatically via ``add_directory()``.  It caches
    loaded documents and resolves tests on demand.  Typical usage::

        loader = ConfigLoader()
        loader.add_directory("path/to/extra/configs")
        specs = loader.resolve_all()
        for spec in specs:
            print(spec.id, spec.config.evaluation.name)

    The loader is intentionally cheap to construct and resolves lazily —
    ``resolve_all()`` triggers discovery + load + merge.  Call ``reload()``
    to invalidate the cache and re-scan.
    """

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        search_dirs: Optional[Sequence[Union[str, Path]]] = None,
    ) -> None:
        """Create a loader.

        Args:
            project_root: Root directory for resolving relative paths.
                Defaults to ``cwd``.  Used only when ``search_dirs`` is None
                (to compute ``default_search_dirs``).
            search_dirs: Explicit list of directories to scan.  Overrides
                the defaults.  Additional dirs can be added later via
                ``add_directory()``.
        """
        self._project_root = Path(project_root) if project_root else None
        if search_dirs is not None:
            self._dirs: list[Path] = [Path(d) for d in search_dirs]
        else:
            self._dirs = default_search_dirs(self._project_root)
        self._documents: Optional[list[LoadedDocument]] = None
        self._errors: list[ConfigError] = []
        self._defaults_docs: list[LoadedDocument] = []
        self._suite_docs: list[LoadedDocument] = []
        self._test_docs: list[LoadedDocument] = []

    # ── Registry ──

    def add_directory(self, path: Union[str, Path]) -> "ConfigLoader":
        """Add a search directory to the registry.  Returns self for chaining.

        The directory is scanned on the next ``resolve_all()`` / ``reload()``.
        Non-existent directories are skipped silently (logged at debug).
        """
        p = Path(path)
        if p not in self._dirs:
            self._dirs.append(p)
        self._invalidate_cache()
        return self

    def remove_directory(self, path: Union[str, Path]) -> "ConfigLoader":
        """Remove a search directory.  Returns self for chaining."""
        p = Path(path)
        if p in self._dirs:
            self._dirs.remove(p)
        self._invalidate_cache()
        return self

    @property
    def search_dirs(self) -> list[Path]:
        """The current registry of search directories (copy)."""
        return list(self._dirs)

    # ── Loading ──

    def reload(self) -> "ConfigLoader":
        """Re-scan directories and reload all config files.

        Returns self for chaining.  After this call, ``documents()``,
        ``errors()``, and ``resolve_all()`` reflect the latest disk state.
        """
        self._invalidate_cache()
        self._do_load()
        return self

    def _do_load(self) -> None:
        if self._documents is not None:
            return  # cached
        docs, errs = load_directory(self._dirs, collect_errors=True)
        self._documents = docs
        self._errors = errs
        self._defaults_docs = [d for d in docs if d.kind == "defaults"]
        self._suite_docs = [d for d in docs if d.kind == "suite"]
        self._test_docs = [d for d in docs if d.kind == "test"]

    def _invalidate_cache(self) -> None:
        self._documents = None
        self._errors = []
        self._defaults_docs = []
        self._suite_docs = []
        self._test_docs = []

    # ── Accessors ──

    def documents(self) -> list[LoadedDocument]:
        """All successfully loaded documents (triggers load if needed)."""
        self._do_load()
        return list(self._documents or [])

    def defaults_documents(self) -> list[LoadedDocument]:
        """All loaded ``defaults`` documents."""
        self._do_load()
        return list(self._defaults_docs)

    def suite_documents(self) -> list[LoadedDocument]:
        """All loaded ``suite`` documents."""
        self._do_load()
        return list(self._suite_docs)

    def test_documents(self) -> list[LoadedDocument]:
        """All loaded ``test`` documents (standalone, not in suites)."""
        self._do_load()
        return list(self._test_docs)

    def errors(self) -> list[ConfigError]:
        """Validation errors collected during loading."""
        self._do_load()
        return list(self._errors)

    def has_errors(self) -> bool:
        return bool(self.errors())

    # ── Resolution ──

    def _global_defaults_config(self) -> TestConfig:
        """Merge all defaults documents into a single TestConfig overlay.

        If multiple defaults documents exist, they are merged in file order
        (later files override earlier ones).  If none, returns an empty
        TestConfig (built-in defaults fill the gaps during resolve_test).
        """
        if not self._defaults_docs:
            return TestConfig()
        merged: dict[str, Any] = {}
        for doc in self._defaults_docs:
            defaults_doc = doc.document
            assert isinstance(defaults_doc, DefaultsDocument)
            policy = defaults_doc.merge
            merged = deep_merge(
                merged,
                defaults_doc.defaults.model_dump(exclude_none=False),
                policy,
            )
        return TestConfig(**merged)

    def _resolve_standalone_test(
        self,
        test_ldoc: LoadedDocument,
        global_defaults: TestConfig,
        source_files_extra: tuple[str, ...] = (),
    ) -> ResolvedTestSpec:
        """Resolve a standalone test document (not referenced by any suite).

        ``source_files_extra`` are prepended to the test's own source path
        (used when the test was referenced by a suite — we want the suite
        file in the provenance too).
        """
        assert isinstance(test_ldoc.document, TestDocument)
        config = resolve_test(
            BUILTIN_DEFAULTS,
            global_defaults,
            test_ldoc.document.to_test_config(),
        )
        src = (str(test_ldoc.source_path),) + source_files_extra
        return ResolvedTestSpec(
            config=config,
            source_files=src,
            suite_name=None,
            suite_tags=(),
        )

    def _resolve_suite_test(
        self,
        suite_ldoc: LoadedDocument,
        test_entry: Union[str, TestConfig],
        global_defaults: TestConfig,
        test_index: int,
    ) -> Optional[ResolvedTestSpec]:
        """Resolve one test entry within a suite.

        ``test_entry`` is either a string ID reference (resolved against
        standalone test documents) or an inline ``TestConfig``.

        Returns ``None`` if the entry is a string reference to a test ID that
        we cannot find (a warning is logged; the error is reported via
        ``self._errors``).
        """
        assert isinstance(suite_ldoc.document, SuiteDocument)
        suite_doc = suite_ldoc.document
        suite_defaults = suite_doc.defaults or TestConfig()
        suite_tags = tuple(suite_doc.tags)
        suite_path = str(suite_ldoc.source_path)

        if isinstance(test_entry, str):
            # Find the standalone test with this ID.
            test_ldoc = self._find_test_ldoc_by_id(test_entry)
            if test_ldoc is None:
                self._errors.append(
                    ConfigError(
                        file_path=suite_ldoc.source_path,
                        message=f"Suite '{suite_doc.name}' references unknown test id '{test_entry}'",
                    )
                )
                logger.warning(
                    "Suite '%s' references unknown test id '%s' — skipped", suite_doc.name, test_entry
                )
                return None
            assert isinstance(test_ldoc.document, TestDocument)
            test_config = test_ldoc.document.to_test_config()
            source_files = (str(test_ldoc.source_path), suite_path)
        else:
            # Inline TestConfig (defined directly in the suite file).
            test_config = test_entry
            source_files = (suite_path,)

        resolved = resolve_test(
            BUILTIN_DEFAULTS,
            global_defaults,
            suite_defaults,
            test_config,
        )
        return ResolvedTestSpec(
            config=resolved,
            source_files=source_files,
            suite_name=suite_doc.name,
            suite_tags=suite_tags,
        )

    def _find_test_ldoc_by_id(self, test_id: str) -> Optional[LoadedDocument]:
        """Find a standalone test LoadedDocument by ID."""
        for doc in self._test_docs:
            assert isinstance(doc.document, TestDocument)
            if doc.document.id == test_id:
                return doc
        return None

    def resolve_all(self) -> list[ResolvedTestSpec]:
        """Resolve all tests into ``ResolvedTestSpec`` instances.

        This merges all layers (built-in → global → suite → test) for every
        test found: standalone test documents plus every test referenced by
        or inline in suite documents.  Tests referenced by a suite are
        resolved with that suite's defaults applied; the same test ID
        referenced by multiple suites produces one spec per suite.

        Order: suite tests first (in suite/file order), then standalone tests
        not referenced by any suite.  This keeps related tests together.
        """
        self._do_load()
        global_defaults = self._global_defaults_config()

        specs: list[ResolvedTestSpec] = []
        referenced_ids: set[str] = set()

        # Resolve tests in suites.
        for suite_ldoc in self._suite_docs:
            assert isinstance(suite_ldoc.document, SuiteDocument)
            suite = suite_ldoc.document
            for i, entry in enumerate(suite.tests):
                spec = self._resolve_suite_test(suite_ldoc, entry, global_defaults, i)
                if spec is not None:
                    specs.append(spec)
                if isinstance(entry, str):
                    referenced_ids.add(entry)

        # Resolve standalone tests not referenced by any suite.
        for doc in self._test_docs:
            assert isinstance(doc.document, TestDocument)
            if doc.document.id in referenced_ids:
                continue
            spec = self._resolve_standalone_test(doc, global_defaults)
            specs.append(spec)

        return specs

    def resolve_by_id(self, test_id: str) -> Optional[ResolvedTestSpec]:
        """Resolve a single test by ID (first match)."""
        for spec in self.resolve_all():
            if spec.id == test_id:
                return spec
        return None

    def resolve_suite(self, suite_name: str) -> list[ResolvedTestSpec]:
        """Resolve all tests in a named suite."""
        return [s for s in self.resolve_all() if s.suite_name == suite_name]

    # ── Validation-only mode ──

    def validate(self) -> list[ConfigError]:
        """Load and validate all configs without resolving.  Returns errors.

        This is the "validate" command's backend — it discovers, loads, and
        validates every file, returning all errors (empty list = all valid).
        """
        self.reload()
        return self.errors()


if __name__ == "__main__":
    # Simple CLI: validate and report.
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    loader = ConfigLoader()
    loader.reload()
    docs = loader.documents()
    errs = loader.errors()
    print(f"Discovered {len(docs)} valid document(s) across {len(loader.search_dirs)} dir(s).")
    for d in docs:
        print(f"  {d.kind}: {d.id}  ({d.source_path})")
    if errs:
        print(f"\n{len(errs)} error(s):")
        for e in errs:
            print(f"  {e}")
        sys.exit(1)
    print("All configs valid.")
