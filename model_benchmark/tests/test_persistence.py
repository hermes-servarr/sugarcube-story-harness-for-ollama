"""Tests for persistence (run dir creation, atomic writes) (Phase 4 stub).

TODO markers for test functions to be implemented in P5/P7.
"""
import pytest

# TODO(benchmark-upgrade): test_persistence.py — implement tests for:
# - create_run_dir: creates timestamped run dir with logs/ and artifacts/ subdirs
# - write_results: writes ResultRecords to JSON and JSONL formats
# - write_manifest: atomically writes RunManifest to JSON
# - write_report: writes report string to file
# - write_anonymization_mapping: atomically writes private mapping to .private.json
# - write_failures_csv: writes failure records to CSV grouped by category
# - INV-A3: all persisted files are atomic (tmpfile + os.replace)
# - INV-A8: run dir names contain no model/provider identity
