# Dataset Integration Guide

This guide explains how to reference external and inline datasets from
declarative test configs. Datasets let you separate test *logic* (the
prompt, expected behavior, evaluator) from test *content* (the actual
questions, prompts, and answers), so one test definition can run across
many data rows.

---

## Why use datasets?

Without a dataset, each test case is a single prompt + expected pair. With
a dataset, one test config can expand into N test cases — one per row in
the dataset. This is useful for:

- **QA tests:** a CSV of question/answer pairs becomes N test cases.
- **Direction-following:** a JSONL of direction prompts becomes N cases
  across variants.
- **Regression suites:** a dataset of known-failing prompts ensures
  regressions are caught.
- **Large-scale evaluation:** sample N rows from a HuggingFace dataset
  for broad coverage without defining each case manually.

---

## The `dataset` field

A test references a dataset via the `dataset` block:

```yaml
dataset:
  name: my_dataset
  format: csv
  path: datasets/my_data.csv
  filters:
    difficulty: easy
    category: [math, science]
  sample: 100
  seed: 42
  checksum: "sha256:abc123"
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Stable dataset identifier |
| `version` | `Optional[str]` | `None` | Dataset version tag |
| `split` | `Optional[str]` | `None` | Train/val/test split name (used by HuggingFace) |
| `path` | `Optional[str]` | `None` | Local file path (relative to `model_benchmark/tests/`) |
| `format` | `Literal["csv", "jsonl", "json", "huggingface", "inline"]` | `"jsonl"` | Source format |
| `huggingface_id` | `Optional[str]` | `None` | HF dataset repo ID (required if `format=huggingface`) |
| `filters` | `Optional[dict[str, Any]]` | `None` | Row filters (column → value or value-list) |
| `sample` | `Optional[int]` | `None` | Random sample N rows (after filtering) |
| `seed` | `Optional[int]` | `None` | Seed for reproducible sampling |
| `checksum` | `Optional[str]` | `None` | Content checksum (sha256) for integrity verification |
| `inline_data` | `Optional[list[dict[str, Any]]]` | `None` | Inline rows (required if `format=inline`) |

### Cross-field constraints

- `format="huggingface"` requires `huggingface_id`
- `format="inline"` requires `inline_data`
- All other formats require `path`

---

## Supported formats

### CSV (`format: csv`)

Comma-separated values, first row is the header. Each subsequent row
becomes a dict mapping column names to string values.

**File:** `tests/datasets/qa_simple.csv`
```csv
question,answer,difficulty,category
What is the capital of France?,Paris,easy,geography
What is 2+2?,4,easy,math
Who wrote Hamlet?,William Shakespeare,medium,literature
```

**Config:**
```yaml
dataset:
  name: qa_simple
  format: csv
  path: datasets/qa_simple.csv
  filters:
    difficulty: easy
```

Each row becomes: `{"question": "What is the capital of France?", "answer":
"Paris", "difficulty": "easy", "category": "geography"}`.

### JSONL (`format: jsonl`)

JSON Lines — one JSON object per line. Each object becomes a row dict.

**File:** `tests/datasets/directions.jsonl`
```jsonl
{"prompt": "Generate a SugarCube passage...", "direction": "A", "variant": "compact"}
{"prompt": "Write a passage where the player sets a flag...", "direction": "B", "variant": "compact"}
```

**Config:**
```yaml
dataset:
  name: directions
  format: jsonl
  path: datasets/directions.jsonl
  filters:
    variant: compact
  sample: 3
  seed: 42
```

### JSON (`format: json`)

A single JSON file containing either:
- A **list of objects** — each object is a row.
- A **dict with a `data`, `rows`, or `examples` key** — the value (a list)
  is used as the rows.
- A **single dict** — treated as a one-row dataset.

**Config:**
```yaml
dataset:
  name: my_json_data
  format: json
  path: datasets/my_data.json
```

### HuggingFace (`format: huggingface`)

A HuggingFace `datasets` repository. Requires the `datasets` package
(`pip install datasets`).

**Config:**
```yaml
dataset:
  name: squad
  format: huggingface
  huggingface_id: squad
  split: validation
  sample: 100
  seed: 42
```

If the `datasets` package is not installed, the loader raises a clear
error with install instructions.

### Inline (`format: inline`)

Rows defined directly in the config — no external file needed. Useful for
small datasets or self-contained examples.

**Config:**
```yaml
dataset:
  name: inline_qa
  format: inline
  inline_data:
    - {question: "What is 2+2?", answer: "4", difficulty: "easy"}
    - {question: "What is 3+3?", answer: "6", difficulty: "easy"}
    - {question: "What is the capital of Japan?", answer: "Tokyo", difficulty: "easy"}
```

---

## Path resolution

Relative paths are resolved relative to `model_benchmark/tests/` (the
default `base_dir` of the `DatasetLoader`). Absolute paths are used as-is.

| Path in config | Resolved to |
|----------------|-------------|
| `datasets/qa.csv` | `model_benchmark/tests/datasets/qa.csv` |
| `../other/data.jsonl` | `model_benchmark/tests/../other/data.jsonl` |
| `/absolute/path/to/data.csv` | `/absolute/path/to/data.csv` (unchanged) |

Use **portable, relative paths** — never machine-specific absolute paths —
so configs work across environments.

---

## Filters

The `filters` dict applies row-level filters **before** sampling. Each key
is a column name; the value is either:

- A **scalar** (str, int, bool) — keep rows where `row[column] == value`
  (type-coerced comparison).
- A **list** — keep rows where `row[column]` is in the list (membership
  test).

**Example:**
```yaml
filters:
  difficulty: ["easy", "medium"]   # difficulty ∈ {easy, medium}
  category: math                     # category == "math"
  enabled: true                      # enabled == true (bool coercion)
```

Filtering happens before sampling, so `sample: 100` draws from the
filtered set.

---

## Sampling

If `sample` is set, the loader randomly samples N rows from the filtered
result (without replacement). `seed` ensures reproducibility — the same
seed always produces the same sample.

```yaml
sample: 100
seed: 42
```

If `sample` is not set, all filtered rows are used.

---

## How dataset rows become test inputs

Dataset rows are injected as **`input_variables`**. The test's `input`
field and `prompt_template.input_variables` can reference row values via
template variables.

For example, with this config:

```yaml
input: "{question}"
input_variables:
  question: ""

expected:
  answer_type: exact
  # answer injected from dataset row at runtime

evaluation:
  name: exact_match

dataset:
  name: qa_simple
  format: csv
  path: datasets/qa_simple.csv
```

And a CSV row `{"question": "What is 2+2?", "answer": "4"}`, the runner
substitutes `{question}` with the row's `question` value and uses the
row's `answer` value as the expected answer.

The exact injection mechanism depends on the runner implementation — see
`model_benchmark/runner.py` for details. The `DatasetLoader.load()` method
returns a `LoadedDataset` with a `rows` list, which downstream code
iterates over.

---

## Programmatic usage

```python
from model_benchmark.config_schema import DatasetReference
from model_benchmark.dataset_loader import DatasetLoader

# Define a dataset reference
ref = DatasetReference(
    name="qa_simple",
    format="csv",
    path="datasets/qa_simple.csv",
    filters={"difficulty": "easy"},
)

# Load it
loader = DatasetLoader()  # base_dir defaults to model_benchmark/tests/
loaded = loader.load(ref)

print(f"Loaded {len(loaded.rows)} rows from {loaded.source}")
print(f"Total: {loaded.total_rows}, Filtered: {loaded.filtered_rows}")
for row in loaded.rows:
    print(f"  {row['question']} -> {row['answer']}")
```

---

## Sample dataset files

The repo includes sample datasets in `model_benchmark/tests/datasets/`:

| File | Format | Rows | Columns |
|------|--------|------|---------|
| `qa_simple.csv` | CSV | 10 | question, answer, difficulty, category |
| `directions.jsonl` | JSONL | 5 | prompt, expected_sections, difficulty, variant, direction |

Use these for testing your configs without creating your own data files.

---

## Checksums and integrity

The `checksum` field is for content integrity verification. The loader
does not currently enforce it automatically, but it is recorded in the run
manifest for reproducibility. A future version may validate checksums at
load time.

**Convention:** prefix with the algorithm: `sha256:abc123def456`.

---

## Dataset reference in the run manifest

When a test references a dataset, the run manifest records:

- `dataset.name`
- `dataset.version`
- `dataset.split`
- `dataset.checksum`
- `dataset.filters` (the filters applied)
- `dataset.sample` and `dataset.seed` (if sampling)
- Number of rows actually loaded

This ensures every result is traceable to the exact dataset version and
filter configuration that produced it.
