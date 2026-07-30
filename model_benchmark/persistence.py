"""Atomic persistence utilities for the model benchmark (P7 implementation).

Implements the four crash-safe write utilities specified in the task brief
and the P1 module layout (§4.1 ``persistence.py``):

1. :func:`create_run_dir`      — timestamped run directory creation.
2. :func:`write_json`          — atomic JSON writer (tmpfile + ``os.replace``).
3. :func:`write_jsonl`          — atomic JSONL writer with append semantics.
4. :func:`write_manifest`       — atomic manifest writer (a JSON file).

Design constraints (from P1 §7 / P6 INV-A3):

- **Crash safety.**  Every writer builds the full content in a temporary file
  in the *same directory* as the target, then calls :func:`os.replace` to swap
  it into place atomically.  ``os.replace`` is POSIX-atomic; placing the temp
  file in the target directory guarantees the rename stays on the same
  filesystem (a cross-device rename would raise ``OSError``).  On crash the
  worst case is a leftover ``.tmp`` file — the real file is either the old
  version or the complete new version, never a partial write.
- **Append semantics for JSONL.**  Existing file content is read into the
  temp file first, new records are appended as newline-delimited JSON lines,
  then the whole file is swapped in via ``os.replace``.  This makes the
  append atomic — a crash never leaves a truncated/partial line at the end
  of the JSONL file.
- **stdlib only.**  ``json``, ``os``, ``tempfile``, ``uuid``, ``datetime``,
  ``pathlib`` — no new dependencies (P1 §7 constraint).
- **Serialization compatibility.**  The shared ``_default_serializer``
  mirrors the existing ``format_report_json`` convention in
  ``benchmark.py``: frozen dataclasses → ``dataclasses.asdict`` (tuples →
  lists), pydantic models → ``model_dump()``, everything else → ``str``.
  This keeps round-tripping ``ResultRecord`` / ``RunManifest`` / etc.
  consistent with how the current benchmark serializes its report.
- **No harness imports.**  This module does not import from ``harness`` or
  modify it (INV-5).  It operates on plain serializable objects.

The four utilities are the only public API; helper functions are prefixed
with ``_``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "create_run_dir",
    "write_json",
    "write_jsonl",
    "write_manifest",
]


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


def _default_serializer(obj: Any) -> Any:
    """Convert a Python object into a JSON-serializable structure.

    Mirrors the convention in ``benchmark.py:format_report_json``:

    - frozen dataclasses → ``dataclasses.asdict`` with tuples converted to
      lists (JSON has no tuple type);
    - pydantic v2 models → ``model_dump()``;
    - everything else → ``str(obj)`` (the ``json.dumps(..., default=...)``
      fallback handles remaining primitives).

    This is used both as the ``default=`` callable for ``json.dumps`` and
    as a pre-serializer for nested structures.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = dataclasses.asdict(obj)
        # Convert tuples to lists for JSON (matches benchmark.py convention).
        for k, v in d.items():
            if isinstance(v, tuple):
                d[k] = list(v)
        return d
    # Pydantic v2 models expose model_dump(); use getattr to stay type-checker
    # friendly (duck-typing, matching benchmark.py:format_report_json).
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)


def _atomic_write_bytes(
    target: Path,
    data: bytes,
    *,
    suffix: str = ".tmp",
) -> Path:
    """Write ``data`` to a temp file in ``target``'s dir, then ``os.replace``.

    Returns the final target path on success.  The temp file is created with
    :func:`tempfile.NamedTemporaryFile` (``delete=False``) in the *same
    directory* as ``target`` so the subsequent ``os.replace`` is a same-
    filesystem rename (POSIX-atomic).  On any exception the temp file is
    removed; the original ``target`` (if it existed) is left untouched.

    Parameters
    ----------
    target
        Final destination path.  Parent directories must already exist
        (callers create them as needed).
    data
        Fully materialised bytes to write.
    suffix
        Suffix for the temp file (default ``.tmp``).

    Raises
    ------
    TypeError
        If ``target`` is not a :class:`~pathlib.Path`.
    """
    if not isinstance(target, Path):
        raise TypeError(f"target must be a pathlib.Path, got {type(target).__name__}")
    if data is None:  # defensive — bytes(None) is a TypeError
        raise TypeError("data must be bytes, not None")

    tmp_path: Path | None = None
    try:
        # Same dir as target → guarantees same-filesystem rename.
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=target.name + ".",
            suffix=suffix,
        )
        tmp_path = Path(tmp_name)
        os.write(fd, data)
        os.close(fd)
        # os.replace is atomic on POSIX (and Windows for same-volume).
        os.replace(tmp_path, target)
    except BaseException:
        # Clean up the temp file on any failure (including KeyboardInterrupt).
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    return target


def _atomic_write_text(
    target: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    suffix: str = ".tmp",
) -> Path:
    """Encode ``text`` to UTF-8 and write atomically (see ``_atomic_write_bytes``)."""
    return _atomic_write_bytes(target, text.encode(encoding), suffix=suffix)


# ═══════════════════════════════════════════════════════════════════════════
# Public API — 1. create_run_dir
# ═══════════════════════════════════════════════════════════════════════════


def create_run_dir(
    output_dir: str | Path = "benchmark_outputs",
    *,
    timestamp: datetime | None = None,
    benchmark_id: str = "sugarcube-bench",
    run_id: str | None = None,
) -> Path:
    """Create a timestamped run directory, returning the resolved path.

    Produces a collision-resistant directory name of the form::

        <output_dir>/<YYYYMMDD_HHMMSS>_<short-uuid>/

    matching the task brief's ``runs/YYYYMMDD_HHMMSS_<short-uuid>/`` example.
    The short UUID is the first 8 hex chars of :func:`uuid.uuid4`.  If a
    ``run_id`` is supplied it replaces the random short-uuid suffix (useful
    for deterministic / reproducible runs); it is sanitised to filesystem-safe
    characters.

    Parent directories (``output_dir`` and any intermediates) are created with
    ``exist_ok=True`` so concurrent processes or repeated calls don't race.
    The run directory itself is created with ``exist_ok=False`` and will
    raise :class:`FileExistsError` on an unlikely collision — callers can
    retry with a fresh ``run_id``.

    Per P6 INV-A8, the run-dir name contains **no model/provider identity**;
    identity lives only inside the internal files in that directory.

    Parameters
    ----------
    output_dir
        Root directory under which run directories are created.  Created if
        missing.  Defaults to ``"benchmark_outputs"`` (matches
        ``BenchmarkConfig.output_dir``).
    timestamp
        Timestamp to embed in the directory name.  Defaults to the current
        UTC time.  Only the year/month/day/hour/minute/second are used; the
        timezone is ignored (the name is local-agnostic, just sortable).
    benchmark_id
        Short benchmark identifier prepended to the run id.  Only used when
        ``run_id`` is not provided (otherwise the caller controls the full
        suffix).  Defaults to ``"sugarcube-bench"`` per P1 §4.3.
    run_id
        Explicit run id to use as the directory-name suffix instead of the
        random short-uuid.  Sanitised: only ``[A-Za-z0-9._-]`` are kept;
        everything else becomes ``_``.  Pass ``""`` (empty string) to get
        the random short-uuid even when explicitly passing the argument.

    Returns
    -------
    pathlib.Path
        Absolute path to the freshly created run directory.

    Raises
    ------
    FileExistsError
        If the generated directory name already exists (extremely unlikely
        with the random short-uuid; possible with an explicit ``run_id``).
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    # Use only the sortable time components; ignore tz for the name.
    ts_part = timestamp.strftime("%Y%m%d_%H%M%S")

    if run_id is None:
        short_uuid = uuid.uuid4().hex[:8]
        suffix = f"{benchmark_id}_{short_uuid}"
    else:
        # Sanitise explicit run_id to filesystem-safe characters.
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in run_id)
        suffix = safe if safe else f"{benchmark_id}_{uuid.uuid4().hex[:8]}"

    dir_name = f"{ts_part}_{suffix}"
    run_path = Path(output_dir).resolve() / dir_name
    # Create parents (output_dir and any missing intermediates).
    run_path.parent.mkdir(parents=True, exist_ok=True)
    # Create the run directory itself — exist_ok=False so a collision is loud.
    run_path.mkdir(parents=False, exist_ok=False)
    return run_path


# ═══════════════════════════════════════════════════════════════════════════
# Public API — 2. write_json (atomic JSON writer)
# ═══════════════════════════════════════════════════════════════════════════


def write_json(
    path: str | Path,
    data: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write ``data`` as JSON to ``path``.

    Serialises ``data`` to a JSON string (using :func:`json.dumps` with the
    shared :func:`_default_serializer` so frozen dataclasses, pydantic
    models, :class:`~pathlib.Path` and tuples are handled), encodes to UTF-8,
    writes the full payload to a temp file in the same directory, then swaps
    it into place with :func:`os.replace`.

    Crash safety (P6 INV-A3): on crash the destination is either the previous
    complete file (if it existed) or the new complete file — never a partial
    write.  A leftover ``.tmp`` file is the only debris and is cleaned up on
    the next successful write.

    Parameters
    ----------
    path
        Destination file path.  Parent directories are created if missing
        (``parents=True, exist_ok=True``).
    data
        Any JSON-serialisable object.  Dataclasses and pydantic models are
        handled by the shared serializer.
    indent
        Indentation level for ``json.dumps`` (default 2, matches
        ``format_report_json``).
    ensure_ascii
        Passed to ``json.dumps``.  Defaults to ``False`` so UTF-8 content
        (e.g. model responses with non-ASCII characters) is written
        verbatim rather than ``\\uXXXX``-escaped.
    sort_keys
        If ``True``, sort object keys in the output (default ``False`` —
        preserves insertion order for readability).
    encoding
        Text encoding for the temp file (default ``utf-8``).

    Returns
    -------
    pathlib.Path
        The resolved destination path on success.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        data,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        default=_default_serializer,
    )
    return _atomic_write_text(target, text, encoding=encoding)


# ═══════════════════════════════════════════════════════════════════════════
# Public API — 3. write_jsonl (atomic JSONL writer with append semantics)
# ═══════════════════════════════════════════════════════════════════════════


def write_jsonl(
    path: str | Path,
    records: Any,
    *,
    append: bool = True,
    ensure_ascii: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write/append ``records`` as newline-delimited JSON (JSONL).

    Each element of ``records`` is serialised to a single JSON object on its
    own line, with no trailing newline on the final line beyond the standard
    JSONL one-trailing-newline convention (a terminating ``\\n`` is written
    so the file is a valid text file and appends stay clean).

    **Append semantics** (``append=True``, default): the existing file's
    content is read into a temp file first, new record lines are appended,
    then the whole file is swapped in via :func:`os.replace`.  This makes the
    append **atomic** — a crash never leaves a partial/truncated line at the
    tail of the JSONL file (the failure mode of naive ``open(mode="a")``).

    **Replace semantics** (``append=False``): the existing file (if any) is
    overwritten atomically — same behaviour as :func:`write_json` but with
    JSONL formatting.

    Parameters
    ----------
    path
        Destination JSONL file path.  Parent directories are created if
        missing.  When ``append=True`` and the file does not yet exist, it is
        simply created.
    records
        An iterable of JSON-serialisable objects.  Each element becomes one
        JSONL line.  Accepts lists, tuples, generators, or any iterable.
        Dataclasses and pydantic models are handled by the shared serializer.
        An empty iterable with ``append=True`` and no existing file produces
        an empty file; with ``append=False`` produces an empty file.
    append
        If ``True`` (default), preserve existing content and add new lines.
        If ``False``, overwrite.
    ensure_ascii
        Passed to ``json.dumps`` for each record (default ``False``).
    encoding
        Text encoding for reading existing content and writing the new file
        (default ``utf-8``).  The same encoding is used for both so a
        round-trip is lossless.

    Returns
    -------
    pathlib.Path
        The resolved destination path on success.

    Raises
    ------
    TypeError
        If ``records`` is not iterable (e.g. a single non-iterable object).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Materialise the new lines first so we fail early on non-iterable input
    # before touching the existing file.
    new_lines: list[str] = []
    for rec in records:
        line = json.dumps(rec, ensure_ascii=ensure_ascii, default=_default_serializer)
        new_lines.append(line)

    # Build the full content: existing lines (if appending) + new lines.
    parts: list[str] = []
    if append and target.exists():
        existing = target.read_text(encoding=encoding)
        if existing:
            # Ensure existing content ends with a newline so appended lines
            # start on their own line.  A well-formed JSONL file already does.
            if not existing.endswith("\n"):
                existing += "\n"
            parts.append(existing)
    parts.extend("\n".join(new_lines))
    content = "".join(parts)
    # Ensure file ends with a newline if it has content (POSIX text-file
    # convention; keeps appends clean next time).
    if content and not content.endswith("\n"):
        content += "\n"

    return _atomic_write_text(target, content, encoding=encoding)


# ═══════════════════════════════════════════════════════════════════════════
# Public API — 4. write_manifest (atomic manifest writer)
# ═══════════════════════════════════════════════════════════════════════════


def write_manifest(
    path: str | Path,
    manifest: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write a JSON manifest file to ``path``.

    A manifest is a JSON document describing a run (e.g. ``run_manifest.json``
    holding a :class:`~model_benchmark.schema.RunManifest`).  This is a
    thin specialisation of :func:`write_json` with manifest-appropriate
    defaults: keys are sorted (``sort_keys=True``) so manifests are
    deterministic / diff-friendly across runs, and the default filename in
    the docstring convention is ``run_manifest.json``.

    The write is atomic (tmpfile + ``os.replace``) per P6 INV-A3.

    Parameters
    ----------
    path
        Destination manifest file path (convention: ``run_manifest.json``
        inside the run directory).  Parent directories are created if missing.
    manifest
        The manifest object — typically a frozen dataclass
        (:class:`~model_benchmark.schema.RunManifest`) or a plain ``dict``.
        Dataclasses and pydantic models are handled by the shared serializer.
    indent
        Indentation level (default 2).
    ensure_ascii
        Passed to ``json.dumps`` (default ``False``).
    encoding
        Text encoding (default ``utf-8``).

    Returns
    -------
    pathlib.Path
        The resolved destination path on success.
    """
    # Manifests are diff-friendly: sort keys for deterministic output.
    return write_json(
        path,
        manifest,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=True,
        encoding=encoding,
    )


# TODO(benchmark-upgrade): persistence.py — add P3 §3.7 interfaces:
#   def write_results(records: list[ResultRecord], path: str, *, format: str) -> None:
#     Write ResultRecords to a file in 'json' or 'jsonl' format; atomic for 'json'.
#     Delegates to write_json (format='json') or write_jsonl (format='jsonl').
#
#   def write_report(content: str, path: str) -> None:
#     Write a report string (text, markdown, or HTML) to a file (non-atomic).
#
#   def write_anonymization_mapping(mapping: AnonymizationMapping, path: str) -> None:
#     Atomically write the private alias->original mapping to a .private.json
#     file.  Uses write_json with the mapping serialized via dataclasses.asdict.
#
#   def write_failures_csv(records: list[ResultRecord], path: str, *, anonymized: bool) -> None:
#     Write failure records to a CSV file grouped by failure category.
#     Delegates grouping to failures.group_failures (P3 §3.9).
#
# These are NEW interfaces not yet present in this module.
