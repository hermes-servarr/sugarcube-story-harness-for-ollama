"""Anonymization layer for benchmark results, metadata, and error objects.

Replaces all identity-bearing strings (model names, provider hosts, config
identifiers, run ids, file paths, base URLs) with deterministic aliases so
that benchmark artifacts can be shared for review without leaking which
models or infrastructure were tested.

**Embedded core policy (spec §4.1 rule 5):** the ``ResultRecord.scored_result``
field (an embedded ``ModelRunResult``) is kept in the anonymized variant but
scrubbed — ``model_name`` is replaced with its alias, ``error`` and
``raw_response`` are run through ``redact_identity_strings``, and
``category_results`` details/evidence are scrubbed.  This preserves
traceability to the scoring core without leaking identity.  The alternative
policy (set ``scored_result=None``) is not used by default.

**Determinism (spec §2.5):** aliases are assigned by a stable sort of the
original identity set.  Two runs with the same set of models/providers/configs
produce the same aliases, independent of insertion order.  The mapping is
built once per run and reused across all artifacts (INV-A1/A5).

**Mapping file (spec §3):** serialized as JSON using the P2-approved
schema (§3.2): a top-level ``"private": true`` marker, an integer
``"version"`` (``MAPPING_FILE_VERSION``), and each alias set as an array
of ``[alias, original]`` pairs.  The in-memory ``AnonymizationMapping``
stores ``alias -> original`` tuples (per P2 §3.8); the on-disk arrays
mirror that direction.  The file is written atomically (``tempfile`` +
``os.replace``) at mode ``0600``.

Source grounding: ``p1_research.md`` §4.6, ``p2_data_structures.md`` §3.8–§3.9,
and the design spec at
``/opt/data/kanban/workspaces/t_329c966a/anonymization_design_spec.md``.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Iterator

from model_benchmark.schema import (
    AnonymizationMapping,
    ResultRecord,
    RunManifest,
)
from model_benchmark.benchmark import (
    BenchmarkConfig,
    BenchmarkReport,
    CategoryResult,
    ModelReport,
    ModelRunResult,
)

__all__ = [
    "AnonymizationMapping",
    "build_anonymization_mapping",
    "anonymize_result",
    "anonymize_results",
    "anonymize_metadata",
    "anonymize_errors",
    "anonymize_report",
    "save_mapping",
    "load_mapping",
    "redact_identity_strings",
    "verify_no_identity",
]

# TODO(anonymization): module constants - P2-anon §3.1 REDACTION_TOKEN, MAPPING_FILENAME, MAPPING_FILE_VERSION, MAPPING_FILE_PRIVATE_FLAG; _PATH_RE for path discovery (P3 5.1/5.2)

# ── Constants (P2-anon §3.1) ────────────────────────────────────────────

# Generic replacement token for identity strings that have no direct alias
# (e.g. a file path embedded in an error message). Used by redact_identity_strings (P3 2.9).
REDACTION_TOKEN: str = "[REDACTED]"

# Filename for the private mapping file. Never referenced in anonymized
# outputs. The ".private." segment signals that this file must NOT be shared.
MAPPING_FILENAME: str = "anonymization_mapping.private.json"

# Schema version of the mapping file format. Incremented if the on-disk
# shape changes. Checked by load_mapping (P3 2.8) for forward/backward compat.
MAPPING_FILE_VERSION: int = 1

# Top-level boolean field in the mapping file JSON that marks it private.
# Defensive: the filename convention is the primary guard; this field is
# a belt-and-suspenders marker so that any tool reading the JSON sees the
# private flag without parsing the filename.
MAPPING_FILE_PRIVATE_FLAG: str = "private"

# Heuristic regex for absolute file paths that may leak identity (repo roots,
# output dirs, etc.).  Matches common Unix path prefixes.
_PATH_RE = re.compile(r"/(?:opt|home|tmp|var|usr|etc|root|mnt|srv|data)[/\w.+-]*")


# ── Alias generation helpers ─────────────────────────────────────────


# TODO(anonymization): _model_alias - generate model alias - Model_A..Model_J (letter), fallback Model_NN for index 10+ (P3 4)
def _model_alias(index: int) -> str:
    """Generate a model alias for the given 0-based index.

    Indices 0–9 use the letter scheme (Model_A … Model_J).  Index 10+
    falls back to zero-padded numeric (Model_11, Model_12, …) per spec §2.1.
    """
    if index < 10:
        return f"Model_{chr(ord('A') + index)}"
    return f"Model_{index + 1:02d}"


# TODO(anonymization): _provider_alias - generate provider alias - Provider_A, Provider_B (P3 4)
def _provider_alias(index: int) -> str:
    """Generate a provider alias (Provider_A, Provider_B, …)."""
    return f"Provider_{chr(ord('A') + index)}"


# TODO(anonymization): _config_alias - generate config alias - Config_01, Config_02, zero-padded (P3 4)
def _config_alias(index: int) -> str:
    """Generate a config alias (Config_01, Config_02, …) — zero-padded."""
    return f"Config_{index + 1:02d}"


# TODO(anonymization): _run_alias - generate run alias - Run_01, Run_02, zero-padded (P3 4)
def _run_alias(index: int) -> str:
    """Generate a run alias (Run_01, Run_02, …) — zero-padded."""
    return f"Run_{index + 1:02d}"


# ── Identity extraction helpers ──────────────────────────────────────


# TODO(anonymization): _extract_host - extract hostname from URL/host string via urllib.parse.urlparse (P3 4)
def _extract_host(url_or_host: str) -> str:
    """Extract the hostname from a base_url or host string.

    Falls back to the full string if URL parsing fails or yields no hostname.
    """
    if not url_or_host:
        return url_or_host
    try:
        parsed = urllib.parse.urlparse(url_or_host)
        if parsed.hostname:
            return parsed.hostname
    except Exception:
        pass
    return url_or_host


# TODO(anonymization): _config_label - build canonical config label temp={t},num_predict={n} (P3 4)
def _config_label(temperature: Any, num_predict: Any) -> str:
    """Build the canonical config label ``temp={t},num_predict={n}``."""
    return f"temp={temperature},num_predict={num_predict}"


# TODO(anonymization): _discover_paths - find absolute file paths in text via regex scan - identity leak vector (P3 4)
def _discover_paths(text: str) -> set[str]:
    """Find absolute file paths in *text* that may leak identity.

    Returns the set of matched path strings.  Parent directories of each
    match are also included so that a full file path and its repo-root
    prefix are both redacted.
    """
    if not text:
        return set()
    found: set[str] = set()
    for match in _PATH_RE.findall(text):
        found.add(match)
        # Add parent directories so longer paths are redacted first.
        parent = os.path.dirname(match)
        while parent and parent != "/" and parent != match:
            if re.match(r"/(?:opt|home|tmp|var|usr|etc|root|mnt|srv|data)", parent):
                found.add(parent)
            parent = os.path.dirname(parent)
    return found


# TODO(anonymization): _extract_all_strings - recursively yield every str value in dataclasses/dicts/tuples/lists (P3 4)
def _extract_all_strings(obj: Any) -> Iterator[str]:
    """Recursively yield every ``str`` value inside dataclasses, dicts, tuples, and lists."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, (tuple, list)):
        for item in obj:
            yield from _extract_all_strings(item)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _extract_all_strings(value)
    elif dataclasses.is_dataclass(obj):
        for field in dataclasses.fields(obj):
            yield from _extract_all_strings(getattr(obj, field.name))


# ── Reverse-lookup helpers (alias→original tuples → original→alias) ──


# TODO(anonymization): _lookup_alias - reverse lookup - find alias for original from alias-to-original tuple-of-pairs (P3 4)
def _lookup_alias(
    alias_pairs: tuple[tuple[str, str], ...], original: str
) -> str | None:
    """Return the alias for *original* from an ``alias→original`` tuple-of-pairs."""
    for alias, orig in alias_pairs:
        if orig == original:
            return alias
    return None


# TODO(anonymization): _build_replacements - build original-to-replacement dict for redact_identity_strings - aliased + redaction tokens (P3 4)
def _build_replacements(mapping: AnonymizationMapping) -> dict[str, str]:
    """Build an ``original → replacement`` dict for ``redact_identity_strings``.

    Includes every identity string.  Aliased identities (models, providers,
    runs) map to their alias; non-aliased identities (base URLs, file paths)
    map to a redaction token.
    """
    replacements: dict[str, str] = {}

    # Aliased identities → their alias.
    for alias, original in mapping.model_aliases:
        replacements[original] = alias
    for alias, original in mapping.provider_aliases:
        replacements[original] = alias
    for alias, original in mapping.run_aliases:
        replacements[original] = alias
    for alias, original in mapping.config_aliases:
        replacements[original] = alias

    # Remaining identity strings → redaction token (P2-anon §3.1 REDACTION_TOKEN).
    for s in mapping.identity_strings:
        if s in replacements:
            continue
        replacements[s] = REDACTION_TOKEN

    return replacements


# ── Public: build_anonymization_mapping ──────────────────────────────


# TODO(anonymization): build_anonymization_mapping - collect identity strings from results/manifest/config/report, stable-sort, produce deterministic aliases (P3 2.1)
def build_anonymization_mapping(
    results: list[ResultRecord],
    *,
    manifest: RunManifest | None = None,
    config: BenchmarkConfig | None = None,
    report: BenchmarkReport | None = None,
) -> AnonymizationMapping:
    """Scan all inputs for identity strings, stable-sort, and produce aliases.

    Pure function of its inputs — the same input set always yields the same
    mapping.  The returned mapping should be reused by every ``anonymize_*``
    call so all artifacts stay consistent (INV-A1/A5).
    """
    # ── Collect model names ──
    model_names: set[str] = set()
    for r in results:
        if r.scored_result is not None:
            model_names.add(r.scored_result.model_name)
        if r.model_alias and not r.model_alias.startswith("Model_"):
            model_names.add(r.model_alias)
    if config is not None:
        model_names.update(config.models)
    if manifest is not None:
        model_names.update(manifest.model_names)
    if report is not None:
        for mr in report.models:
            model_names.add(mr.model_name)
        model_names.update(report.config.models)

    # ── Collect provider hosts and full base URLs ──
    provider_hosts: set[str] = set()
    base_urls: set[str] = set()

    if config is not None:
        base_urls.add(config.base_url)
        provider_hosts.add(_extract_host(config.base_url))
    if report is not None:
        base_urls.add(report.config.base_url)
        provider_hosts.add(_extract_host(report.config.base_url))
    if manifest is not None:
        # manifest.provider may be a hostname or a full URL.
        provider_hosts.add(_extract_host(manifest.provider))
        if manifest.provider.startswith(("http://", "https://")):
            base_urls.add(manifest.provider)

    # ── Collect config identifiers ──
    config_labels: set[str] = set()
    if config is not None:
        config_labels.add(_config_label(config.temperature, config.num_predict))
    if manifest is not None:
        for mc in manifest.model_configs:
            t = mc.get("temperature", "")
            n = mc.get("num_predict", "")
            if t or n:
                config_labels.add(_config_label(t, n))
        t = manifest.generation_params.get("temperature", "")
        n = manifest.generation_params.get("num_predict", "")
        if t or n:
            config_labels.add(_config_label(t, n))

    # ── Collect run ids ──
    run_ids: set[str] = set()
    if manifest is not None:
        run_ids.add(manifest.run_id)
        if manifest.parent_run_id:
            run_ids.add(manifest.parent_run_id)

    # ── Stable-sort all identity sets ──
    sorted_models = sorted(model_names)
    sorted_hosts = sorted(provider_hosts)
    sorted_configs = sorted(config_labels)
    sorted_runs = sorted(run_ids)

    # ── Assign aliases (alias → original tuples) ──
    model_alias_pairs = tuple(
        (_model_alias(i), name) for i, name in enumerate(sorted_models)
    )
    provider_alias_pairs = tuple(
        (_provider_alias(i), host) for i, host in enumerate(sorted_hosts)
    )
    config_alias_pairs = tuple(
        (_config_alias(i), label) for i, label in enumerate(sorted_configs)
    )
    run_alias_pairs = tuple(
        (_run_alias(i), rid) for i, rid in enumerate(sorted_runs)
    )

    # ── Build identity_strings ──
    identity_strings: set[str] = set()
    identity_strings.update(sorted_models)
    identity_strings.update(sorted_hosts)
    identity_strings.update(base_urls)
    identity_strings.update(sorted_runs)

    # Scan all string fields in the inputs for file paths and other leaks.
    scan_targets: list[Any] = []
    scan_targets.extend(results)
    if manifest is not None:
        scan_targets.append(manifest)
    if config is not None:
        scan_targets.append(config)
    if report is not None:
        scan_targets.append(report)

    for obj in scan_targets:
        for s in _extract_all_strings(obj):
            identity_strings.update(_discover_paths(s))

    # Sort identity_strings by descending length then alphabetically so
    # redact_identity_strings replaces longest matches first.
    sorted_identity = tuple(sorted(identity_strings, key=lambda s: (-len(s), s)))

    return AnonymizationMapping(
        model_aliases=model_alias_pairs,
        provider_aliases=provider_alias_pairs,
        config_aliases=config_alias_pairs,
        run_aliases=run_alias_pairs,
        identity_strings=sorted_identity,
    )


# ── Public: redact_identity_strings & verify_no_identity ─────────────


# TODO(anonymization): redact_identity_strings - replace every identity string in text with alias or redaction token - longest-first (P3 2.9)
def redact_identity_strings(text: str, mapping: AnonymizationMapping) -> str:
    """Replace every identity string in *text* with its alias or a redaction token.

    Replacements are applied longest-first so that a full URL is replaced
    before its hostname substring (spec §4.1 rule 4).
    """
    # TODO(benchmark-upgrade): anonymization.py — this function implements
    # the P3 §3.6 `anonymize_string` interface.  Add an alias:
    #   anonymize_string = redact_identity_strings
    # so the P3 interface name is available.  The existing name
    # `redact_identity_strings` can remain as a backward-compatible alias.
    if not text:
        return text
    replacements = _build_replacements(mapping)
    # Sort by descending length to avoid partial matches.
    for original in sorted(replacements, key=len, reverse=True):
        if original and original in text:
            text = text.replace(original, replacements[original])
    return text


# TODO(anonymization): verify_no_identity - return list of identity strings still present in artifact_text - leak scan (P3 2.10, INV-A2)
def verify_no_identity(
    artifact_text: str, mapping: AnonymizationMapping
) -> list[str]:
    """Return the list of identity strings still present in *artifact_text*.

    An empty list means the artifact is clean (INV-A2 leak scan).
    """
    if not artifact_text:
        return []
    return [s for s in mapping.identity_strings if s and s in artifact_text]


# ── Public: anonymize_result & anonymize_results ─────────────────────


# TODO(anonymization): anonymize_result - scrub identity from a single ResultRecord - model_name to alias, error/string fields redacted, scored_result scrubbed (P3 2.2)
def anonymize_result(
    record: ResultRecord, mapping: AnonymizationMapping
) -> ResultRecord:
    """Return a new ``ResultRecord`` with all identity scrubbed.

    - ``model_alias`` set from the mapping (falls back to existing if already
      aliased or if the model name is not in the mapping).
    - ``config_alias`` set from the mapping if the current value is not
      already an alias.
    - ``scored_result``: scrubbed copy (model_name → alias, error and
      raw_response redacted, category_results details/evidence redacted).
    - All string fields (error_details, actual_output_raw, input_summary,
      etc.) run through ``redact_identity_strings``.
    - Never mutates the input (uses ``dataclasses.replace``).
    """
    # Determine the original model name for this record.
    original_model = ""
    if record.scored_result is not None:
        original_model = record.scored_result.model_name
    elif record.model_alias and not record.model_alias.startswith("Model_"):
        original_model = record.model_alias

    model_alias = record.model_alias
    if original_model:
        looked_up = _lookup_alias(mapping.model_aliases, original_model)
        if looked_up:
            model_alias = looked_up

    # Config alias: keep if already aliased, else look up.
    config_alias = record.config_alias
    if config_alias and not config_alias.startswith("Config_"):
        looked_up = _lookup_alias(mapping.config_aliases, config_alias)
        if looked_up:
            config_alias = looked_up

    # Scrub the embedded scored_result (keep but scrub — spec §4.1 rule 5).
    scored_result = None
    if record.scored_result is not None:
        sr = record.scored_result
        sr_model = original_model or sr.model_name
        sr_alias = _lookup_alias(mapping.model_aliases, sr_model) or sr_model
        sr_error = redact_identity_strings(sr.error, mapping) if sr.error else sr.error
        sr_raw = redact_identity_strings(sr.raw_response, mapping)
        # Scrub category_results details/evidence.
        new_cat_results = tuple(
            dataclasses.replace(
                cr,
                details=redact_identity_strings(cr.details, mapping),
                evidence=tuple(
                    redact_identity_strings(e, mapping) for e in cr.evidence
                ),
            )
            for cr in sr.category_results
        )
        scored_result = dataclasses.replace(
            sr,
            model_name=sr_alias,
            error=sr_error,
            raw_response=sr_raw,
            category_results=new_cat_results,
        )

    # Scrub all string fields on the ResultRecord itself.
    return dataclasses.replace(
        record,
        model_alias=model_alias,
        config_alias=config_alias,
        scored_result=scored_result,
        input_summary=redact_identity_strings(record.input_summary, mapping),
        expected_behavior=redact_identity_strings(record.expected_behavior, mapping),
        reference_rubric=redact_identity_strings(record.reference_rubric, mapping),
        actual_output_raw=redact_identity_strings(record.actual_output_raw, mapping),
        error_details=redact_identity_strings(record.error_details, mapping),
        evaluator_reasoning=redact_identity_strings(
            record.evaluator_reasoning, mapping
        ),
        random_seed=redact_identity_strings(record.random_seed, mapping),
        timestamp_start=redact_identity_strings(record.timestamp_start, mapping),
        timestamp_end=redact_identity_strings(record.timestamp_end, mapping),
        artifact_refs=tuple(
            redact_identity_strings(ref, mapping) for ref in record.artifact_refs
        ),
    )


# TODO(anonymization): anonymize_results - batch wrapper - apply anonymize_result across a list, preserving order and length (P3 2.3)
def anonymize_results(
    data: list[ResultRecord], mapping: AnonymizationMapping
) -> list[ResultRecord]:
    """Apply ``anonymize_result`` across a list, preserving order and length.

    All non-identity fields (metrics, ordering, precision) are unchanged
    (INV-A1).
    """
    return [anonymize_result(r, mapping) for r in data]


# ── Public: anonymize_metadata ───────────────────────────────────────


# TODO(anonymization): anonymize_metadata - scrub identity from RunManifest - model_names, provider, configs, run_ids, all string fields (P3 2.4)
def anonymize_metadata(
    # TODO(benchmark-upgrade): anonymization.py — this function implements
    # the P3 §3.6 `anonymize_manifest` interface (manifest = metadata).
    # Add an alias: `anonymize_manifest = anonymize_metadata` so the P3
    # interface name is available.  The existing name can remain.
    meta: RunManifest, mapping: AnonymizationMapping
) -> RunManifest:
    """Return a new ``RunManifest`` with all identity scrubbed.

    - ``model_names`` → aliases.
    - ``provider`` → provider alias.
    - ``model_configs`` → values redacted.
    - ``generation_params``, ``runtime_settings``, ``env_vars_redacted``,
      ``cli_args``, ``os_info``, ``hardware``: every identity string replaced.
    - ``run_id`` and ``parent_run_id`` → run aliases.
    - ``source_commit_hash``, ``config_file_checksum``: kept (not identity;
      ``redact_identity_strings`` is a no-op on them since they are not in the
      identity set).
    - ``config_file_contents``: scrubbed (may contain model names / paths).
    - Pure: returns a new frozen instance.
    """
    # Model names → aliases.
    new_model_names = tuple(
        _lookup_alias(mapping.model_aliases, name) or name
        for name in meta.model_names
    )

    # Provider → alias.
    provider_host = _extract_host(meta.provider)
    provider_alias = (
        _lookup_alias(mapping.provider_aliases, provider_host)
        or _lookup_alias(mapping.provider_aliases, meta.provider)
        or meta.provider
    )

    # Model configs → redacted values.
    new_model_configs = tuple(
        {k: redact_identity_strings(v, mapping) for k, v in mc.items()}
        for mc in meta.model_configs
    )

    # Dict fields → redacted values.
    new_generation_params = {
        k: redact_identity_strings(v, mapping)
        for k, v in meta.generation_params.items()
    }
    new_runtime_settings = {
        k: redact_identity_strings(v, mapping) for k, v in meta.runtime_settings.items()
    }
    new_env_vars = {
        k: redact_identity_strings(v, mapping)
        for k, v in meta.env_vars_redacted.items()
    }
    new_package_versions = {
        k: redact_identity_strings(v, mapping)
        for k, v in meta.package_versions.items()
    }

    # CLI args → redacted.
    new_cli_args = tuple(
        redact_identity_strings(arg, mapping) for arg in meta.cli_args
    )

    # Run ids → aliases.
    new_run_id = _lookup_alias(mapping.run_aliases, meta.run_id) or meta.run_id
    new_parent_run_id = (
        _lookup_alias(mapping.run_aliases, meta.parent_run_id)
        or meta.parent_run_id
        if meta.parent_run_id
        else meta.parent_run_id
    )

    return dataclasses.replace(
        meta,
        run_id=new_run_id,
        model_names=new_model_names,
        provider=provider_alias,
        model_configs=new_model_configs,
        generation_params=new_generation_params,
        runtime_settings=new_runtime_settings,
        env_vars_redacted=new_env_vars,
        package_versions=new_package_versions,
        cli_args=new_cli_args,
        os_info=redact_identity_strings(meta.os_info, mapping),
        hardware=redact_identity_strings(meta.hardware, mapping),
        parent_run_id=new_parent_run_id,
        config_file_contents=redact_identity_strings(
            meta.config_file_contents, mapping
        ),
        prompt_template=redact_identity_strings(meta.prompt_template, mapping),
        evaluator_prompt=redact_identity_strings(meta.evaluator_prompt, mapping),
    )


# ── Public: anonymize_errors ─────────────────────────────────────────


# TODO(anonymization): anonymize_errors - scrub identity strings from a list of error messages, return new list (P3 2.5)
def anonymize_errors(
    errs: list[str] | tuple[str, ...], mapping: AnonymizationMapping
) -> list[str]:
    """Replace every identity string in each error message with its alias.

    Returns a new list; never mutates the input.
    """
    return [redact_identity_strings(e, mapping) for e in errs]


# ── Public: anonymize_report ─────────────────────────────────────────


# TODO(anonymization): anonymize_report - scrub identity from BenchmarkReport - config.models, base_url, each ModelReport/ModelRunResult (P3 2.6)
def anonymize_report(
    report: BenchmarkReport, mapping: AnonymizationMapping
) -> BenchmarkReport:
    """Return a new ``BenchmarkReport`` with identity scrubbed.

    - ``config.models`` → aliases.
    - ``config.base_url`` → provider alias.
    - Each ``ModelReport.model_name`` → alias.
    - Each ``ModelRunResult.model_name`` → alias, ``error`` and
      ``raw_response`` redacted.
    - Preserves all scores and structure (INV-A1).
    """
    # Anonymize the embedded BenchmarkConfig.
    new_models = tuple(
        _lookup_alias(mapping.model_aliases, m) or m for m in report.config.models
    )
    base_host = _extract_host(report.config.base_url)
    new_base_url = (
        _lookup_alias(mapping.provider_aliases, base_host) or report.config.base_url
    )
    new_config = dataclasses.replace(
        report.config,
        models=new_models,
        base_url=new_base_url,
    )

    # Anonymize each ModelReport and its runs.
    new_model_reports = tuple(
        _anonymize_model_report(mr, mapping) for mr in report.models
    )

    return dataclasses.replace(
        report,
        models=new_model_reports,
        config=new_config,
    )


# TODO(anonymization): _anonymize_model_report - scrub one ModelReport - model_name to alias + all embedded runs (P3 4, called by anonymize_report)
def _anonymize_model_report(
    mr: ModelReport, mapping: AnonymizationMapping
) -> ModelReport:
    """Scrub one ``ModelReport`` — model_name and all embedded runs."""
    new_model_name = (
        _lookup_alias(mapping.model_aliases, mr.model_name) or mr.model_name
    )
    new_runs = tuple(
        _anonymize_model_run(run, mapping) for run in mr.runs
    )
    return dataclasses.replace(
        mr,
        model_name=new_model_name,
        runs=new_runs,
    )


# TODO(anonymization): _anonymize_model_run - scrub one ModelRunResult - model_name to alias, error/raw_response redacted, category_results scrubbed (P3 4)
def _anonymize_model_run(
    run: ModelRunResult, mapping: AnonymizationMapping
) -> ModelRunResult:
    """Scrub one ``ModelRunResult`` — model_name, error, raw_response."""
    new_model_name = (
        _lookup_alias(mapping.model_aliases, run.model_name) or run.model_name
    )
    new_error = redact_identity_strings(run.error, mapping) if run.error else run.error
    new_raw = redact_identity_strings(run.raw_response, mapping)
    # Scrub category_results details/evidence.
    new_cat_results = tuple(
        dataclasses.replace(
            cr,
            details=redact_identity_strings(cr.details, mapping),
            evidence=tuple(
                redact_identity_strings(e, mapping) for e in cr.evidence
            ),
        )
        for cr in run.category_results
    )
    return dataclasses.replace(
        run,
        model_name=new_model_name,
        error=new_error,
        raw_response=new_raw,
        category_results=new_cat_results,
    )


# ── Public: save_mapping & load_mapping ──────────────────────────────


# TODO(anonymization): save_mapping - serialize AnonymizationMapping to JSON file - atomic write (tempfile+os.replace), mode 0600 (P3 2.7)
def save_mapping(mapping: AnonymizationMapping, path: str | Path) -> None:
    """Serialize *mapping* to *path* as JSON (P2-anon §3.2 format).

    Written atomically (``tempfile`` + ``os.replace``) at mode ``0600``.
    Overwrites if the file exists.  The on-disk schema uses the P2-approved
    shape: a top-level ``"private": true`` marker, an integer ``"version"``
    (``MAPPING_FILE_VERSION``), and each alias set serialized as an array of
    ``[alias, original]`` pairs (the in-memory tuple-of-pairs direction is
    ``alias -> original``, so the array is a direct conversion).
    """
    path = Path(path)
    data = {
        MAPPING_FILE_PRIVATE_FLAG: True,
        "version": MAPPING_FILE_VERSION,
        "model_aliases": [list(pair) for pair in mapping.model_aliases],
        "provider_aliases": [list(pair) for pair in mapping.provider_aliases],
        "config_aliases": [list(pair) for pair in mapping.config_aliases],
        "run_aliases": [list(pair) for pair in mapping.run_aliases],
        "identity_strings": list(mapping.identity_strings),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, str(path))
    except BaseException:
        # Clean up the temp file on any error so no partial file is left.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# TODO(anonymization): load_mapping - deserialize AnonymizationMapping from JSON file - validate schema version, reconstruct tuples (P3 2.8)
def load_mapping(path: str | Path) -> AnonymizationMapping:
    """Load a mapping from a JSON file written by ``save_mapping``.

    Reconstructs the ``AnonymizationMapping`` (alias → original tuples +
    ``identity_strings`` tuple).  Raises ``FileNotFoundError`` if the file
    is missing; raises ``ValueError`` on schema-version mismatch, a missing
    or false private marker, or malformed JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed mapping JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Mapping JSON root must be an object, got {type(data).__name__}")

    # Validate the private marker (P2-anon §3.1 MAPPING_FILE_PRIVATE_FLAG).
    if data.get(MAPPING_FILE_PRIVATE_FLAG) is not True:
        raise ValueError(
            f"Mapping file missing or false {MAPPING_FILE_PRIVATE_FLAG!r} marker: "
            f"got {data.get(MAPPING_FILE_PRIVATE_FLAG)!r}"
        )

    # Validate the schema version (P2-anon §3.1 MAPPING_FILE_VERSION).
    if data.get("version") != MAPPING_FILE_VERSION:
        raise ValueError(
            f"Unsupported mapping version: {data.get('version')!r} "
            f"(expected {MAPPING_FILE_VERSION!r})"
        )

    # Reconstruct alias → original tuples from P2 array-of-pairs [alias, original].
    # Sort by alias for determinism (matches build_anonymization_mapping ordering).
    model_aliases = tuple(
        sorted(
            ((pair[0], pair[1]) for pair in data.get("model_aliases", [])),
            key=lambda p: p[0],
        )
    )
    provider_aliases = tuple(
        sorted(
            ((pair[0], pair[1]) for pair in data.get("provider_aliases", [])),
            key=lambda p: p[0],
        )
    )
    config_aliases = tuple(
        sorted(
            ((pair[0], pair[1]) for pair in data.get("config_aliases", [])),
            key=lambda p: p[0],
        )
    )
    run_aliases = tuple(
        sorted(
            ((pair[0], pair[1]) for pair in data.get("run_aliases", [])),
            key=lambda p: p[0],
        )
    )
    identity_strings = tuple(data.get("identity_strings", []))

    return AnonymizationMapping(
        model_aliases=model_aliases,
        provider_aliases=provider_aliases,
        config_aliases=config_aliases,
        run_aliases=run_aliases,
        identity_strings=identity_strings,
    )
