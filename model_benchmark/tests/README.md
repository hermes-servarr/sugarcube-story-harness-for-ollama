# Declarative Test Configuration — tests/

This directory holds the declarative test configuration system for the
SugarCube model benchmark. See `model_benchmark/config_schema.py` for the
canonical pydantic schema and `DESIGN_NOTE.md` for merge semantics + versioning.

## Structure (from the spec, t_e3b4162e)

```
tests/
  schemas/test_config.schema.json   # Formal JSON Schema (draft 2020-12) for IDE/validation
  examples/full_feature_example.yaml # Reference example showing ALL features (3-doc multi-doc YAML)
  cases/sugarcube_markup_001.yaml    # Individual test case referenced by the example suite
  DESIGN_NOTE.md                     # Merge semantics + versioning policy
  defaults.yaml                       # (future) Global defaults — created by t_172dd683
  suites/                             # (future) Test suites — created by t_172dd683
  cases/                              # Individual test definitions (this dir)
  evaluators/                          # (future) Evaluator plugin configs — created by t_b8e82f29
  prompts/                             # (future) Prompt template files
```

## Current Deliverables

| Task | File | Purpose |
|------|------|---------|
| t_798ee62f (schema) | `../config_schema.py` | Canonical pydantic v2 schema (source of truth) |
| t_798ee62f (schema) | `../test_config_schema.py` | 51 tests validating the schema |
| t_798ee62f (schema) | `schemas/test_config.schema.json` | JSON Schema export for IDE autocompletion |
| t_798ee62f (schema) | `examples/full_feature_example.yaml` | Reference example: defaults + suite + test (all features) |
| t_798ee62f (schema) | `DESIGN_NOTE.md` | Merge semantics, versioning policy, validation rules |
| t_172dd683 (loader) | `../config_loader.py` | Config loader: discovery, validation, merge resolution |
| t_172dd683 (loader) | `../test_config_loader.py` | 65 tests for the loader |
| t_172dd683 (loader) | `cases/sugarcube_markup_001.yaml` | Test case so the example suite fully resolves |

## Quick Start

```bash
# Validate the reference example against the schema
uv run python -m pytest model_benchmark/test_config_schema.py -v

# Export the JSON Schema (regenerate after schema changes)
uv run python -c "
from model_benchmark.config_schema import export_json_schema
import json
print(json.dumps(export_json_schema(), indent=2, default=str))
" > model_benchmark/tests/schemas/test_config.schema.json

# Parse and resolve the example config (built-in -> global -> suite -> test)
uv run python -c "
import yaml
from model_benchmark.config_schema import parse_config_dict, resolve_test, BUILTIN_DEFAULTS
with open('model_benchmark/tests/examples/full_feature_example.yaml') as f:
    docs = list(yaml.safe_load_all(f))
d, s, t = (parse_config_dict(x) for x in docs)
resolved = resolve_test(BUILTIN_DEFAULTS, d.defaults, s.defaults, t.to_test_config())
print(resolved.id, resolved.tags, resolved.model_parameters.temperature)
"

# Discover, validate, and resolve all configs via the loader (t_172dd683)
uv run python -m model_benchmark.config_loader
```
