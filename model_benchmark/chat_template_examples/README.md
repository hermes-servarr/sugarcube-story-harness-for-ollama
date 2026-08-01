# Chat-template source examples

These files preserve byte-for-byte operator-provided examples used to design the benchmark's
closed ingestion-profile registry. They are reference material, not templates
loaded or executed at runtime. The signed implementations live in
`harness/ingestion_profiles.py` and intentionally contain no generic assistant
persona or other task pre-prompt.

Machine-readable provenance is stored separately in `provenance.json` so the
captured source examples remain unchanged.

| File | Family | Provenance | Runtime authority |
| --- | --- | --- | --- |
| `alpaca.source.json` | Alpaca-style instruction framing | Operator-provided example, captured 2026-08-01 | No |
| `gemma.source.jinja` | Gemma user/model turn template | Operator-provided example, captured 2026-08-01 | No |
| `llama_template.source.json` | Llama 3 header-token framing | Operator-provided example, captured 2026-08-01 | No |
| `mistral_instruct.source.json` | Mistral `[INST]` framing | Operator-provided example, captured 2026-08-01 | No |
| `qwen3.source.jinja` | Qwen3 ChatML/reasoning template | Operator-provided example, captured 2026-08-01 | No |
| `llama3.source.jinja` | Llama 3 message template | Operator-provided example, captured 2026-08-01 | No |
| `official_profile_sources.json` | Upstream family URLs and signed single-turn forms | Official model repositories, captured 2026-08-01 | Registry provenance only |

The Qwen example is a captured reference and may differ from later upstream
revisions. Keeping it non-executable prevents an unsigned or stale template
from changing protected benchmark behavior.
