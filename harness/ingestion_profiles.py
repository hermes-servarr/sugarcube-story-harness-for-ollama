"""Signed, deterministic prompt-ingestion profiles for Ollama requests.

The protocol registry is deliberately closed: private configuration may select
a profile by ID, but it cannot provide executable templates or alter framing.
Official profiles contain no task pre-prompt. Optimized and story profiles may
add only bounded plain-text envelopes around the complete benchmark prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RenderedIngestion:
    """Prompt bytes and transport options produced by a signed profile."""

    prompt: str
    raw: bool
    stop: tuple[str, ...] = ()


_BASE_PROFILE_IDS = (
    "harness-generate-neutral",
    "ollama-native",
    "neutral-raw",
    "alpaca-neutral",
    "llama2-chat-neutral",
    "llama3-neutral",
    "gemma-instruct-neutral",
    "mistral-neutral",
    "qwen3-thinking",
    "qwen3-nonthinking",
    "deepseek-r1-thinking",
)

_ENVELOPE_BASES = (
    "harness-generate",
    "alpaca",
    "llama2-chat",
    "llama3",
    "gemma-instruct",
    "mistral",
    "qwen3-thinking",
    "qwen3-nonthinking",
    "deepseek-r1-thinking",
)

PROFILE_IDS = _BASE_PROFILE_IDS + tuple(
    f"{base}-{variant}"
    for base in _ENVELOPE_BASES
    for variant in ("official", "optimized", "story")
)

DEFAULT_ENVELOPE_PATH = (
    Path(__file__).resolve().parents[1]
    / "model_benchmark"
    / "ingestion_overrides.json"
)
MAX_ENVELOPE_FRAGMENT = 4_000
_ENVELOPE_NAMES = {"optimized", "story"}
_ENVELOPE_FIELDS = {"user_prefix", "user_suffix"}
_RESERVED_TEMPLATE_MARKERS = (
    "{{",
    "{%",
    "<|",
    "|>",
    "[INST]",
    "[/INST]",
    "<start_of_turn>",
    "<end_of_turn>",
    "<s>",
    "</s>",
    "<｜",
    "｜>",
)


class IngestionEnvelopeError(ValueError):
    """Raised when an editable semantic envelope is malformed."""


def load_ingestion_envelopes(
    path: str | Path = DEFAULT_ENVELOPE_PATH,
) -> dict[str, dict[str, str]]:
    """Load bounded semantic envelopes without accepting protocol syntax."""
    target = Path(path)
    if not target.exists():
        raise IngestionEnvelopeError("ingestion envelope document is missing")
    try:
        payload: Any = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionEnvelopeError("could not load ingestion envelopes") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "envelopes"}:
        raise IngestionEnvelopeError("invalid ingestion envelope document")
    if payload["schema_version"] != 1:
        raise IngestionEnvelopeError("unsupported ingestion envelope schema")
    envelopes = payload["envelopes"]
    if not isinstance(envelopes, dict) or set(envelopes) != _ENVELOPE_NAMES:
        raise IngestionEnvelopeError("ingestion envelopes must define optimized and story")
    result: dict[str, dict[str, str]] = {}
    for name, envelope in envelopes.items():
        if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_FIELDS:
            raise IngestionEnvelopeError("invalid ingestion envelope fields")
        rendered: dict[str, str] = {}
        for field, value in envelope.items():
            if not isinstance(value, str) or len(value) > MAX_ENVELOPE_FRAGMENT:
                raise IngestionEnvelopeError("invalid ingestion envelope fragment")
            if any(marker in value for marker in _RESERVED_TEMPLATE_MARKERS):
                raise IngestionEnvelopeError("ingestion envelope contains reserved protocol syntax")
            rendered[field] = value.strip()
        result[name] = rendered
    return result


def _resolve_profile(profile_id: str, prompt: str) -> tuple[str, str]:
    """Resolve aliases and apply an optional shared semantic envelope."""
    aliases = {
        "harness-generate-official": "harness-generate-neutral",
        "alpaca-official": "alpaca-neutral",
        "llama2-chat-official": "llama2-chat-neutral",
        "llama3-official": "llama3-neutral",
        "gemma-instruct-official": "gemma-instruct-neutral",
        "mistral-official": "mistral-neutral",
        "qwen3-thinking-official": "qwen3-thinking",
        "qwen3-nonthinking-official": "qwen3-nonthinking",
        "deepseek-r1-thinking-official": "deepseek-r1-thinking",
    }
    base_profile = aliases.get(profile_id, profile_id)
    envelope_name = ""
    for candidate in _ENVELOPE_NAMES:
        suffix = f"-{candidate}"
        if profile_id.endswith(suffix):
            family = profile_id[: -len(suffix)]
            base_profile = aliases[f"{family}-official"]
            envelope_name = candidate
            break
    if envelope_name:
        envelope = load_ingestion_envelopes()[envelope_name]
        pieces = [envelope["user_prefix"], prompt.strip(), envelope["user_suffix"]]
        prompt = "\n\n".join(piece for piece in pieces if piece)
    return base_profile, prompt


def render_ingestion(profile_id: str, prompt: str) -> RenderedIngestion:
    """Render one user prompt with a known profile, or fail closed."""
    if profile_id not in PROFILE_IDS:
        raise ValueError("unknown ingestion profile")
    profile_id, prompt = _resolve_profile(profile_id, prompt)
    if profile_id in {"harness-generate-neutral", "ollama-native"}:
        return RenderedIngestion(prompt=prompt, raw=False)
    if profile_id == "neutral-raw":
        return RenderedIngestion(prompt=prompt, raw=True)
    if profile_id == "alpaca-neutral":
        return RenderedIngestion(
            prompt=f"### Instruction:\n{prompt}\n\n### Response:\n",
            raw=True,
            stop=("### Instruction:",),
        )
    if profile_id == "llama2-chat-neutral":
        return RenderedIngestion(
            prompt=f"<s>[INST] {prompt.strip()} [/INST]",
            raw=True,
            stop=("</s>",),
        )
    if profile_id == "llama3-neutral":
        return RenderedIngestion(
            prompt=(
                "<|begin_of_text|>"
                "<|start_header_id|>user<|end_header_id|>\n\n"
                f"{prompt}<|eot_id|>"
                "<|start_header_id|>assistant<|end_header_id|>\n\n"
            ),
            raw=True,
            stop=("<|eot_id|>",),
        )
    if profile_id == "gemma-instruct-neutral":
        return RenderedIngestion(
            prompt=(
                f"<bos><start_of_turn>user\n{prompt.strip()}"
                "<end_of_turn>\n<start_of_turn>model\n"
            ),
            raw=True,
            stop=("<end_of_turn>",),
        )
    if profile_id == "mistral-neutral":
        return RenderedIngestion(
            prompt=f"<s>[INST] {prompt.strip()}[/INST]",
            raw=True,
            stop=("</s>",),
        )
    if profile_id in {"qwen3-thinking", "qwen3-nonthinking"}:
        generation_prefix = ""
        if profile_id == "qwen3-nonthinking":
            generation_prefix = "<think>\n\n</think>\n\n"
        return RenderedIngestion(
            prompt=(
                f"<|im_start|>user\n{prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n{generation_prefix}"
            ),
            raw=True,
            stop=("<|im_end|>",),
        )
    if profile_id == "deepseek-r1-thinking":
        return RenderedIngestion(
            prompt=(
                f"<｜begin▁of▁sentence｜><｜User｜>{prompt}"
                "<｜Assistant｜><think>\n"
            ),
            raw=True,
            stop=("<｜end▁of▁sentence｜>",),
        )
    raise ValueError("unknown ingestion profile")
