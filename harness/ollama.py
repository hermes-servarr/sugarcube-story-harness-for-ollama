"""Backwards-compat shim.

Original ``harness.ollama`` was split into:
- :mod:`harness.ollama_client` — HTTP, payload, model-profile policy.
- :mod:`harness.parsers`        — delimited + JSON output parsing.
- :mod:`harness.generators`     — context assembly + high-level generators.

RAG retrieval formatters moved to :mod:`harness.rag` and lost their leading
underscore (:func:`retrieve_inspiration`, :func:`retrieve_story_recall`).

Re-exports are kept so older import paths still resolve. New code should
import from the split modules directly.
"""
from __future__ import annotations

# Transport + policy
from .ollama_client import (
    ModelProfile,
    call_ollama,
    call_ollama_sync,
    model_profile,
)
# Parsers
from .parsers import (
    parse_entities_json,
    parse_json_object,
    parse_keywords_json,
    parse_model_output,
    parse_model_output_json,
)
# Generators
from .generators import (
    build_prompt,
    extract_entities,
    extract_keywords,
    generate_characters_sketch,
    generate_locations_sketch,
    generate_opening,
    generate_premise,
    generate_story_output,
    generate_tone_themes,
    generate_world,
)
# Retrieval formatters (live in rag now)
from .rag import (
    retrieve_inspiration,
    retrieve_story_recall,
)

# Legacy private aliases — some callers/tests imported the underscore names.
_retrieve_inspiration = retrieve_inspiration
_retrieve_story_recall = retrieve_story_recall


__all__ = [
    "ModelProfile",
    "build_prompt",
    "call_ollama",
    "call_ollama_sync",
    "extract_entities",
    "extract_keywords",
    "generate_characters_sketch",
    "generate_locations_sketch",
    "generate_opening",
    "generate_premise",
    "generate_story_output",
    "generate_tone_themes",
    "generate_world",
    "model_profile",
    "parse_entities_json",
    "parse_json_object",
    "parse_keywords_json",
    "parse_model_output",
    "parse_model_output_json",
    "retrieve_inspiration",
    "retrieve_story_recall",
]
