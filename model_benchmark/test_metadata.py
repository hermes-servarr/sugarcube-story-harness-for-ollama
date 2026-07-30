"""Tests for reproducibility metadata collection (Phase 4 stub).

TODO markers for test functions to be implemented in P5/P7.
"""
import pytest

# TODO(benchmark-upgrade): test_metadata.py — implement tests for:
# - collect_run_manifest: collects reproducibility metadata (commit, env, versions, config)
# - redact_secrets: replaces known secret keys with '<redacted>'
# - get_source_commit: returns git commit hash or 'unknown'
# - RunManifest fields: run_id, benchmark_name/version, schema_version, source_commit_hash,
#   model_names, provider, model_configs, generation_params, prompt_template/version,
#   evaluator_prompt/version, dataset fields, runtime settings, timestamps, env_vars_redacted
# - INV-A7: no secrets/credentials/API keys in any output file
