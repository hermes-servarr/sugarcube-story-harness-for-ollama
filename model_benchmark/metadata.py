"""Reproducibility metadata collection for the model benchmark (Phase 7).

This module is the **home** of the :class:`RunManifest` data structure per
``p2_data_structures.md`` §3.7 (module-home table §1).  The structure itself
is defined in :mod:`model_benchmark.schema` (alongside the other 14 new
types) to avoid circular imports and keep a single type registry; this
module re-exports it so callers can import it from its logical home::

    from model_benchmark.metadata import RunManifest

Phase 7 implementation adds three pieces of behaviour on top of the
Phase 2 data-structure stub:

1. :func:`collect_reproducibility_metadata` — gather git hash (via
   :mod:`subprocess`), OS info (via :mod:`platform`), Python version (via
   :mod:`sys`), installed packages (via :mod:`importlib.metadata`),
   environment variables (redacted via :func:`redact_secrets`), and CLI
   args (``sys.argv``), then bundle them into a :class:`RunManifest`.
2. :func:`redact_secrets` — pattern-match common secret-bearing env var
   names (``*_KEY``, ``*_TOKEN``, ``*_SECRET``, ``*_PASSWORD``,
   ``*_API_KEY``) and replace their values with ``[REDACTED]``.
3. :func:`write_manifest_atomic` — atomically persist a :class:`RunManifest`
   to ``run_manifest.json`` by delegating to :func:`model_benchmark.persistence.write_manifest`
   (tmpfile + ``os.replace`` per P6 INV-A3).

Design constraints
------------------
- **stdlib only** (``subprocess``, ``platform``, ``sys``,
  ``importlib.metadata``, ``os``, ``re``, ``uuid``, ``datetime``) — no new
  dependencies (P1 §7).  ``git`` is invoked via :mod:`subprocess`; no
  GitPython dependency.
- **No harness imports** (INV-5).  This module does not import from
  ``harness`` and operates on plain serialisable objects.
- **Secrets never persisted** (P6 INV-A7).  :func:`redact_secrets` is the
  only path env vars take into a manifest; raw values are dropped.
- **Graceful degradation.**  Every collector (git, packages, hardware)
  catches its own failures and records an explanatory sentinel string
  (e.g. ``"<git-unavailable: ...>"``) rather than raising, so a run can
  still produce a manifest in a stripped-down environment (no git, no
  ``pip``, a read-only container).
- The :class:`RunManifest` frozen dataclass requires *every* field at
  construction (per P2 §3.7 — no field defaults).  The collector therefore
  supplies a value for all ~35 fields, defaulting unknown/optional
  values to empty strings / empty tuples / zero as appropriate rather
  than leaving them unset.

Source grounding: ``p1_research.md`` §4.1 (module layout), §5 OQ-7
(concurrency recorded as metadata), §7 (constraints); ``p2_data_structures.md``
§3.7 (RunManifest fields); the task brief (env redaction patterns).
"""
from __future__ import annotations

import importlib.metadata
import os
import platform
import re
import subprocess
import sys
import uuid
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

# Re-export the RunManifest dataclass so callers can import it from its
# logical home (metadata.py) without a second import.  Imported eagerly —
# it is a cheap, dependency-free frozen dataclass defined in schema.py.
from model_benchmark.schema import RunManifest
# Reuse the atomic manifest writer from persistence.py (P6 INV-A3) rather
# than re-implementing tmpfile + os.replace.  This is the "import and reuse
# atomic JSON writer from model_benchmark/persistence.py" requirement.
from model_benchmark.persistence import write_manifest

__all__ = [
    "RunManifest",
    "REDACTED_VALUE",
    "SECRET_ENV_PATTERNS",
    "redact_secrets",
    "collect_git_hash",
    "collect_os_info",
    "collect_python_version",
    "collect_package_versions",
    "collect_hardware_info",
    "collect_env_vars_redacted",
    "collect_cli_args",
    "collect_reproducibility_metadata",
    "collect_ollama_metadata",
    "write_manifest_atomic",
    "manifest_to_dict",
]


def collect_ollama_metadata(
    base_url: str, model_names: Sequence[str], *, timeout: float = 5.0
) -> tuple[tuple[dict[str, str], ...], str]:
    """Resolve exact local model artifacts and Ollama version, or mark unknown."""
    fallback = tuple({"model": str(name), "digest": "unknown"} for name in model_names)
    if not base_url:
        return fallback, "unknown"
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as response:
            tags = json.loads(response.read().decode("utf-8"))
        by_name = {item.get("name"): item for item in tags.get("models", [])}
        configs = []
        for name in model_names:
            item = by_name.get(name, {})
            details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
            configs.append({
                "model": str(name),
                "digest": str(item.get("digest", "unknown")),
                "quantization": str(details.get("quantization_level", "unknown")),
                "family": str(details.get("family", "unknown")),
                "parameter_size": str(details.get("parameter_size", "unknown")),
                "context_length": str(details.get("context_length", "unknown")),
            })
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/version", timeout=timeout) as response:
            version = str(json.loads(response.read().decode("utf-8")).get("version", "unknown"))
        return tuple(configs), version
    except Exception:
        return fallback, "unknown"

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

#: The sentinel value that replaces a secret env var's value after redaction.
#: Chosen to be obvious in diffs / JSON inspection without being a value
#: any real secret would take.
REDACTED_VALUE = "[REDACTED]"

#: Regex patterns matching env-var names that carry secrets.  A name match
#: on ANY of these triggers redaction of that variable's value.  Patterns
#: are compiled once at import; matching is case-insensitive (env var
#: conventions vary: ``API_KEY`` vs ``api_key`` vs ``ApiKey``).
#:
#: The five required patterns from the task brief:
#:
#:   ``*_KEY``       — e.g. OPENAI_API_KEY, SECRET_KEY
#:   ``*_TOKEN``     — e.g. GITHUB_TOKEN, ACCESS_TOKEN
#:   ``*_SECRET``    — e.g. CLIENT_SECRET, JWT_SECRET
#:   ``*_PASSWORD``  — e.g. DB_PASSWORD, SUDO_PASSWORD
#:   ``*_API_KEY``   — e.g. OLLAMA_API_KEY (overlaps *_KEY; listed explicitly
#:                     for clarity and so a reviewer grepping for the
#:                     requirement finds it)
#:
#: Anchored at start and end so ``KEY_ID`` (not a secret) is not matched
#: by ``*_KEY``; the ``*`` maps to one or more leading word characters.
SECRET_ENV_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        r"^.+_API_KEY$",
        r"^.+_API_SECRET$",
        r"^.+_KEY$",
        r"^.+_TOKEN$",
        r"^.+_SECRET$",
        r"^.+_PASSWORD$",
        r"^.+_PASSWD$",
        r"^.+_CREDENTIALS$",
        r"^.+_CREDENTIAL$",
        # Common explicit secret-bearing names without a suffix pattern.
        r"^PASSWORD$",
        r"^PASSWD$",
        r"^SECRET$",
        r"^TOKEN$",
        r"^API_KEY$",
        r"^AUTH$",
        r"^AUTHORIZATION$",
        # Common prefix forms: AWS_SECRET_ACCESS_KEY, GCP_..._KEY, etc.
        r"^.*_PRIVATE_KEY$",
        r"^PRIVATE_KEY$",
    )
)


# ═══════════════════════════════════════════════════════════════════════════
# Secret redaction
# ═══════════════════════════════════════════════════════════════════════════


def _is_secret_name(name: str) -> bool:
    """Return ``True`` if ``name`` matches any secret-bearing pattern."""
    return any(pat.match(name) for pat in SECRET_ENV_PATTERNS)


def redact_secrets(
    # TODO(benchmark-upgrade): metadata.py — redact_secrets implements the
    # P3 §3.5 interface.  P3 signature:
    #   def redact_secrets(env_dict: dict[str, str]) -> dict[str, str]:
    # Current accepts Mapping with optional redacted_value kwarg; the P3
    # interface is simpler.  The existing implementation is compatible —
    # just ensure it's callable as `redact_secrets(env_dict) -> dict`.
    env: Mapping[str, str] | Mapping[str, str | None] | None,
    *,
    redacted_value: str = REDACTED_VALUE,
) -> dict[str, str]:
    """Return a copy of ``env`` with secret values replaced.

    Secret-bearing variable names (matched by :data:`SECRET_ENV_PATTERNS`)
    have their values replaced with ``redacted_value`` (default
    ``"[REDACTED]"``).  Non-secret names keep their value, stringified.

    ``None`` values (``os.environ.get`` can return ``None``-ish in some
    stubs) are rendered as the empty string.  Non-string values are
    stringified via ``str()`` so the result is always ``dict[str, str]``
    (the ``RunManifest.env_vars_redacted`` field type).

    The original ``env`` mapping is never mutated.

    Parameters
    ----------
    env
        Environment mapping to redact.  Accepts ``os.environ`` directly,
        a plain ``dict``, or ``None`` (returns ``{}``).
    redacted_value
        Sentinel substituted for secret values.  Override only in tests
        to assert exact-match behaviour.

    Returns
    -------
    dict[str, str]
        A new dict with the same keys; secret values masked.

    Examples
    --------
    >>> redact_secrets({"OPENAI_API_KEY": "sk-xxx", "PATH": "/usr/bin"})
    {'OPENAI_API_KEY': '[REDACTED]', 'PATH': '/usr/bin'}
    >>> redact_secrets(None)
    {}
    """
    if env is None:
        return {}
    out: dict[str, str] = {}
    for key, value in env.items():
        if _is_secret_name(key):
            out[key] = redacted_value
        else:
            # Stringify: os.environ values are str, but be defensive for
            # test doubles / mock mappings that may insert None or ints.
            out[key] = "" if value is None else str(value)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Individual collectors (each gracefully degrades on failure)
# ═══════════════════════════════════════════════════════════════════════════


def _run_git(args: Sequence[str], *, cwd: str | Path | None = None,
             timeout: float = 5.0) -> str:
    """Run a git subcommand and return ``stdout`` (stripped).

    Raises on any failure (non-zero exit, FileNotFoundError for missing
    git, TimeoutExpired).  Callers catch and record a sentinel.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout.strip()


def collect_git_hash(
    # TODO(benchmark-upgrade): metadata.py — collect_git_hash implements the
    # P3 §3.5 `get_source_commit` interface.  Add an alias:
    #   get_source_commit = collect_git_hash
    # P3 signature: def get_source_commit() -> str
    # Returns "unknown" on any error (not a git repo, git not installed).
    cwd: str | Path | None = None,
    *,
    timeout: float = 5.0,
) -> str:
    """Return the current git commit hash for the repo at ``cwd``.

    Uses ``git rev-parse HEAD`` via :mod:`subprocess` (no GitPython
    dependency).  On any failure (git not installed, not a repo,
    timeout, non-zero exit) returns a sentinel string of the form
    ``"<git-unavailable: <reason>>"`` so the manifest still records that
    collection was attempted and why it failed — a missing hash is a
    reproducibility gap worth surfacing, not silently dropping.

    Parameters
    ----------
    cwd
        Directory to run git in.  Defaults to the process cwd
        (``None`` → git uses its own cwd resolution).
    timeout
        Max seconds to wait for git (default 5).  Git is fast for
        ``rev-parse HEAD``; a hang indicates a broken environment.

    Returns
    -------
    str
        40-char hex commit hash, or a ``<git-unavailable: ...>`` sentinel.
    """
    try:
        return _run_git(["rev-parse", "HEAD"], cwd=cwd, timeout=timeout)
    except FileNotFoundError as exc:
        return f"<git-unavailable: git not found: {exc}>"
    except subprocess.TimeoutExpired:
        return f"<git-unavailable: git timed out after {timeout}s>"
    except subprocess.CalledProcessError as exc:
        # Most common: "not a git repository" when cwd is outside a repo.
        stderr = (exc.stderr or "").strip().splitlines()
        reason = stderr[-1] if stderr else f"exit code {exc.returncode}"
        return f"<git-unavailable: {reason}>"


def collect_os_info() -> str:
    """Return a single-line OS/platform description.

    Uses :func:`platform.platform` plus :func:`platform.machine` for the
    CPU architecture.  This never raises (``platform`` reads ``/etc/os-
    release`` / ``uname``; if those fail it returns generic strings), so
    no try/except is needed.

    Returns
    -------
    str
        e.g. ``"Linux-6.8.0-136-generic-x86_64-with-glibc2.39 (x86_64)"``.
    """
    base = platform.platform()
    arch = platform.machine()
    if arch and arch not in base:
        return f"{base} ({arch})"
    return base


def collect_python_version() -> str:
    """Return the full Python version string (``sys.version``).

    ``sys.version`` is a multi-line string on some builds; this returns
    the first line (the canonical ``"3.13.5 (main, ...)"`` form) for a
    tidy single-line manifest field.

    Returns
    -------
    str
        e.g. ``"3.13.5 (main, Jul 30 2026, 12:00:00) [Clang 18.1.8]"``.
    """
    # sys.version can be multi-line; the first line is the canonical form.
    return sys.version.splitlines()[0] if sys.version else ""


def collect_package_versions() -> dict[str, str]:
    """Return ``{package: version}`` for all installed distributions.

    Uses :mod:`importlib.metadata` (stdlib, Python 3.8+) which reads the
    same metadata ``pip freeze`` does without shelling out.  On failure
    (very unusual — would mean the ``importlib.metadata`` API is broken
    on this interpreter) returns ``{"<package-collection-error>": "<reason>"}``
    so the manifest records the attempt.

    Returns
    -------
    dict[str, str]
        e.g. ``{"pytest": "9.0.3", "httpx": "0.27.2", ...}``.
    """
    try:
        return {
            dist.metadata["Name"] or dist.metadata.get("Name", dist.name) or dist.name: dist.version
            for dist in importlib.metadata.distributions()
        }
    except Exception as exc:  # pragma: no cover - extremely defensive
        return {"<package-collection-error>": str(exc)}


def collect_hardware_info() -> str:
    """Return a best-effort single-line hardware description.

    Combines CPU brand (``platform.processor()``), architecture
    (``platform.machine()``), and (on Linux) core count from
    :func:`os.cpu_count`.  All lookups are individually guarded so a
    missing ``/proc`` or an exotic platform yields a partial string,
    not an exception.

    Returns
    -------
    str
        e.g. ``"amd64 CPU, x86_64, 8 cores"``.
    """
    parts: list[str] = []
    cpu = platform.processor() or ""
    if cpu:
        parts.append(cpu)
    arch = platform.machine()
    if arch:
        parts.append(arch)
    try:
        cores = os.cpu_count()
        if cores is not None:
            parts.append(f"{cores} cores")
    except NotImplementedError:
        # os.cpu_count() can raise NotImplementedError on rare platforms.
        pass
    return ", ".join(parts) if parts else "unknown"


def collect_env_vars_redacted(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the process environment with secrets redacted.

    Convenience wrapper around :func:`redact_secrets` that defaults to
    :data:`os.environ` when ``env`` is ``None``.

    Parameters
    ----------
    env
        Environment mapping.  Defaults to :data:`os.environ`.

    Returns
    -------
    dict[str, str]
        Redacted environment dict (see :func:`redact_secrets`).
    """
    if env is None:
        env = dict(os.environ)
    return redact_secrets(env)


def collect_cli_args(argv: Sequence[str] | None = None) -> tuple[str, ...]:
    """Return the CLI args as a tuple (defaults to :data:`sys.argv`).

    The full ``sys.argv`` is recorded so a run can be reproduced by
    re-invoking with the same arguments.  Pass an explicit ``argv`` in
    tests to avoid capturing the test runner's own argv.

    Returns
    -------
    tuple[str, ...]
        The argv list as an immutable tuple (matches RunManifest.cli_args
        type).
    """
    if argv is None:
        argv = sys.argv
    return tuple(str(a) for a in argv)


# ═══════════════════════════════════════════════════════════════════════════
# Manifest assembly + serialization
# ═══════════════════════════════════════════════════════════════════════════


def _new_run_id() -> str:
    """Generate a fresh run id (8-char hex prefix of a uuid4)."""
    return uuid.uuid4().hex[:8]


def _iso_utc(dt: datetime | None = None) -> str:
    """Return an ISO-8601 UTC timestamp string (``...Z`` suffix)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    # Use 'Z' suffix (RFC 3339 / ISO-8601 UTC indicator) for readability.
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_reproducibility_metadata(
    # TODO(benchmark-upgrade): metadata.py — collect_reproducibility_metadata
    # implements the P3 §3.5 `collect_run_manifest` interface.  Add an alias:
    #   collect_run_manifest = collect_reproducibility_metadata
    # P3 signature:
    #   def collect_run_manifest(
    #       config: BenchmarkConfig, models: list[str], results: list[ResultRecord],
    #       *, benchmark_name: str, benchmark_version: str, schema_version: str,
    #       resumed: bool = False, parent_run_id: str = "",
    #   ) -> RunManifest:
    # Current signature takes (config, *, run_id, commit_hash, ...) which is
    # more granular.  Add a wrapper that derives models/results/timestamps
    # from the config and results list per P3.
    config: Any | None = None,
    *,
    run_id: str | None = None,
    commit_hash: str | None = None,
    start_timestamp: datetime | str | None = None,
    completion_timestamp: datetime | str | None = None,
    duration_seconds: float = 0.0,
    benchmark_name: str = "sugarcube-bench",
    benchmark_version: str = "0.1.0",
    schema_version: str = "manifest-v1",
    provider: str = "ollama",
    prompt_template: str = "compact",
    prompt_version: int = 7,
    evaluator_prompt: str = "default",
    evaluator_version: str = "1.0",
    dataset_name: str = "fixture",
    dataset_version: str = "1",
    dataset_split: str = "test",
    dataset_checksums: tuple[str, ...] = (),
    concurrency: int = 1,
    retry_policy: str = "none",
    random_seed: str = "",
    sampling_seed: str = "",
    repeated_runs_count: int = 1,
    resumed: bool = False,
    parent_run_id: str = "",
    cwd: str | Path | None = None,
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> RunManifest:
    """Collect reproducibility metadata and assemble a :class:`RunManifest`.

    This is the single entry point the CLI/runner uses to build a run
    manifest.  It gathers:

    - **git hash** — ``git rev-parse HEAD`` via :func:`collect_git_hash`
      (unless ``commit_hash`` is supplied explicitly);
    - **OS info** — :func:`collect_os_info` via :mod:`platform`;
    - **Python version** — :func:`collect_python_version` via ``sys.version``;
    - **installed packages** — :func:`collect_package_versions` via
      :mod:`importlib.metadata`;
    - **hardware** — :func:`collect_hardware_info`;
    - **environment variables** — :func:`collect_env_vars_redacted`
      (secrets masked via :func:`redact_secrets`);
    - **CLI args** — :func:`collect_cli_args` (``sys.argv``).

    Fields not derivable from the local environment (model names,
    generation params, config file contents, etc.) are pulled from the
    ``config`` object when one is supplied (duck-typed attribute access),
    else default to empty values.  This keeps the collector usable both
    with the full :class:`~model_benchmark.benchmark.BenchmarkConfig` and
    in isolation (e.g. unit tests).

    Parameters
    ----------
    config
        Optional benchmark config object (duck-typed).  When supplied,
        its ``models``, ``base_url``, ``temperature``, ``num_predict``,
        ``timeout``, ``runs``, ``random_seed``, ``output_dir``,
        ``variants``, ``directions`` attributes are read (all via
        ``getattr`` with defaults, so a partial object is fine).
    run_id
        Explicit run id.  Generated via :func:`_new_run_id` if ``None``.
    commit_hash
        Explicit commit hash.  Collected via :func:`collect_git_hash`
        (from ``cwd``) if ``None``.
    start_timestamp, completion_timestamp
        Run timestamps.  Accept a :class:`~datetime.datetime` (converted
        to ISO-UTC) or a raw string (used verbatim).  Default
        ``start_timestamp`` = now; ``completion_timestamp`` = "".
    duration_seconds
        Run duration in seconds (default 0.0).
    benchmark_name, benchmark_version, schema_version
        Identity fields (defaults match the existing benchmark).
    provider
        Provider name (default ``"ollama"``).
    prompt_template, prompt_version, evaluator_prompt, evaluator_version
        Prompt/evaluator identity (defaults match the harness's
        ``PROMPT_VERSION = 7``).
    dataset_name, dataset_version, dataset_split, dataset_checksums
        Dataset identity (defaults: the built-in fixture).
    concurrency, retry_policy, random_seed, sampling_seed, repeated_runs_count
        Runtime/reproducibility knobs.  ``random_seed`` /
        ``sampling_seed`` default to ``""`` (unset) unless passed.
    resumed, parent_run_id
        Resume provenance (default ``False`` / ``""``).
    cwd
        Directory to run git in (default: process cwd).
    argv
        CLI args (default: :data:`sys.argv`).
    env
        Environment mapping (default: :data:`os.environ`).

    Returns
    -------
    RunManifest
        A fully-populated, frozen manifest with secrets already masked.

    Raises
    ------
    TypeError
        Only if ``RunManifest`` construction fails (a caller passed a
        fundamentally wrong type).  Collector functions themselves never
        raise — they record sentinels on failure.
    """
    # ── Resolve run id / commit hash ───────────────────────────────────
    rid = run_id if run_id is not None else _new_run_id()
    if commit_hash is None:
        commit_hash = collect_git_hash(cwd=cwd)

    # ── Timestamps ─────────────────────────────────────────────────────
    def _ts(value: datetime | str | None, fallback: str) -> str:
        if value is None:
            return fallback
        if isinstance(value, datetime):
            return _iso_utc(value)
        return str(value)

    start_ts = _ts(start_timestamp, _iso_utc())
    completion_ts = _ts(completion_timestamp, "")

    # ── Derive model/config fields from `config` (duck-typed) ───────────
    # All attribute access is getattr-with-default so a None config and a
    # partial config both work.
    def g(attr: str, default: Any) -> Any:
        if config is None:
            return default
        return getattr(config, attr, default)

    model_names: tuple[str, ...] = tuple(g("models", ()) or ())
    base_url = str(g("base_url", ""))
    model_configs, ollama_version = collect_ollama_metadata(base_url, model_names)

    generation_params: dict[str, str] = {
        "temperature": str(g("temperature", 0.0)),
        "num_predict": str(g("num_predict", 0)),
    }
    timeouts = int(g("timeout", 0))
    runs = int(g("runs", 1))
    # random_seed / sampling_seed: explicit args take precedence over config.
    rs = random_seed if random_seed != "" else str(g("random_seed", ""))
    ss = sampling_seed if sampling_seed != "" else str(g("sampling_seed", ""))

    runtime_settings: dict[str, str] = {
        "base_url": base_url,
        "timeout": str(timeouts),
        "num_predict": str(g("num_predict", 0)),
        "temperature": str(g("temperature", 0.0)),
        "runs": str(runs),
        "dry_run": str(g("dry_run", False)),
        "variants": ",".join(str(v) for v in (g("variants", ()) or ())),
        "directions": ",".join(str(d) for d in (g("directions", ()) or ())),
        "benchmark_profile": str(g("benchmark_profile", "") or "custom"),
        "refactor_architectures": ",".join(
            str(value)
            for value in (g("refactor_architectures", ()) or ())
        ),
        "ollama_version": ollama_version,
    }

    # ── Environment / system collectors ─────────────────────────────────
    os_info = collect_os_info()
    python_version = collect_python_version()
    package_versions = collect_package_versions()
    hardware = collect_hardware_info()
    env_vars_redacted = collect_env_vars_redacted(env)
    cli_args = collect_cli_args(argv)

    return RunManifest(
        run_id=rid,
        benchmark_name=benchmark_name,
        benchmark_version=benchmark_version,
        schema_version=schema_version,
        source_commit_hash=commit_hash,
        model_names=model_names,
        provider=provider,
        model_configs=model_configs,
        generation_params=generation_params,
        prompt_template=prompt_template,
        prompt_version=prompt_version,
        evaluator_prompt=evaluator_prompt,
        evaluator_version=evaluator_version,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        dataset_split=dataset_split,
        dataset_checksums=dataset_checksums,
        runtime_settings=runtime_settings,
        concurrency=concurrency,
        retry_policy=retry_policy,
        timeouts=timeouts,
        random_seed=rs,
        sampling_seed=ss,
        repeated_runs_count=runs,
        start_timestamp=start_ts,
        completion_timestamp=completion_ts,
        duration_seconds=duration_seconds,
        os_info=os_info,
        python_version=python_version,
        package_versions=package_versions,
        hardware=hardware,
        env_vars_redacted=env_vars_redacted,
        cli_args=cli_args,
        config_file_contents="",
        config_file_checksum="",
        resumed=resumed,
        parent_run_id=parent_run_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Serialization helpers
# ═══════════════════════════════════════════════════════════════════════════


def manifest_to_dict(manifest: RunManifest) -> dict[str, Any]:
    """Convert a :class:`RunManifest` to a JSON-serialisable ``dict``.

    Frozen dataclass → ``dict`` with tuples converted to lists (JSON has
    no tuple type), matching the convention in
    :func:`model_benchmark.persistence._default_serializer` and
    :func:`model_benchmark.benchmark.format_report_json`.

    This is exposed primarily so tests and callers can inspect the
    serialised form without writing to disk; the atomic writer
    (:func:`write_manifest_atomic`) uses the persistence layer's
    serializer directly and does not require this helper.

    Returns
    -------
    dict[str, Any]
        A plain dict suitable for ``json.dumps``.
    """
    import dataclasses

    d = dataclasses.asdict(manifest)
    # dataclasses.asdict recurses; top-level tuple fields become lists,
    # but tuple-of-dicts (model_configs) becomes list-of-dicts too — all
    # good for JSON.  Ensure consistency: convert any remaining tuples.
    for k, v in d.items():
        if isinstance(v, tuple):
            d[k] = list(v)
    return d


def write_manifest_atomic(
    manifest: RunManifest,
    path: str | Path,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write ``manifest`` as JSON to ``path``.

    Delegates to :func:`model_benchmark.persistence.write_manifest`, which
    serialises the dataclass (via the shared ``_default_serializer``),
    writes the full payload to a temp file in the target directory, then
    swaps it into place with :func:`os.replace` (POSIX-atomic, P6 INV-A3).
    On crash the destination is either the previous complete file or the
    new complete file — never a partial write.

    This is the canonical way to persist a :class:`RunManifest` to
    ``run_manifest.json`` in the run directory.  It reuses the atomic
    JSON writer from :mod:`model_benchmark.persistence` rather than
    re-implementing ``tempfile`` + ``os.replace`` (the task brief's
    "import and reuse atomic JSON writer from
    model_benchmark/persistence.py" requirement).

    Parameters
    ----------
    manifest
        The :class:`RunManifest` to serialise.
    path
        Destination file path (convention: ``run_manifest.json`` inside
        the run directory).  Parent directories are created if missing.
    indent, ensure_ascii, encoding
        Forwarded to :func:`write_manifest` (defaults: indent 2,
        UTF-8, non-ASCII preserved).

    Returns
    -------
    pathlib.Path
        The resolved destination path on success.
    """
    return write_manifest(
        path,
        manifest,
        indent=indent,
        ensure_ascii=ensure_ascii,
        encoding=encoding,
    )
