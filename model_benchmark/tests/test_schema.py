"""Tests for schema conversion (ResultRecord <-> ModelRunResult) (Phase 4 stub).

TODO markers for test functions to be implemented in P5/P7.
"""
import pytest

# TODO(benchmark-upgrade): test_schema.py — implement tests for:
# - result_to_record: converts scored ModelRunResult into enriched ResultRecord
# - result_to_record: derives status (PASS/FAIL/ERROR) from scored core
# - result_to_record: derives score (fraction of passed categories / 6)
# - record_to_result_core: extracts embedded ModelRunResult from ResultRecord
# - record_to_result_core: returns None if scored_result is absent
# - INV-A6: result schema is versioned (schema_version field present on every record)
