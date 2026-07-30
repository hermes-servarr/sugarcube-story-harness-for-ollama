#!/usr/bin/env python3
"""Thinking-model detection and extraction utilities.

Many modern LLMs (DeepSeek-R1, QwQ, gpt-oss, etc.) produce chain-of-thought
reasoning before their final answer. The benchmark needs to:

1. Detect whether a response contains thinking/reasoning content.
2. Separate the thinking content from the formatted output.
3. Score the thinking content for quality (does it show good reasoning?).
4. Score the formatted output separately (after thinking is stripped).

This module provides pure functions for steps 1-2. Step 3 is in scoring.py
as ``score_thinking_quality``. Step 4 reuses the existing 6 scorers on the
stripped output.

Thinking detection handles these patterns:
- Explicit thinking tags: <thinking>...</thinking>, <reasoning>...</reasoning>
- DeepSeek-R1 style: </think>...<think_end> or </think>... (end of thinking)
- Chain-of-thought preamble: analysis/step-by-step text before the first
  section header (PROSE:, CHOICES:, SUMMARY:, or JSON opening brace)
- Markdown-structured analysis: lines starting with "1.", "**Step", "Analysis:", etc.

All functions are pure (no I/O) and return dataclass results.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ── Thinking tag patterns ──────────────────────────────────────────────

# Explicit thinking tags (model-produced, not harness-injected)
_THINKING_TAGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'<thinking>\s*(.*?)\s*</thinking>', re.DOTALL | re.IGNORECASE), 'thinking_tag'),
    (re.compile(r'<reasoning>\s*(.*?)\s*</reasoning>', re.DOTALL | re.IGNORECASE), 'reasoning_tag'),
    (re.compile(r'<analysis>\s*(.*?)\s*</analysis>', re.DOTALL | re.IGNORECASE), 'analysis_tag'),
    (re.compile(r'<scratchpad>\s*(.*?)\s*</scratchpad>', re.DOTALL | re.IGNORECASE), 'scratchpad_tag'),
    (re.compile(r'<draft>\s*(.*?)\s*</draft>', re.DOTALL | re.IGNORECASE), 'draft_tag'),
]

# DeepSeek-R1 style thinking markers
# R1 uses  nothing special marker - thinking is everything before the first
# section header or JSON. Some models use <think>...</think> or <think_end>.
_R1_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'<think>\s*(.*?)\s*</think>', re.DOTALL | re.IGNORECASE), 'think_tag'),
    (re.compile(r'<think>\s*(.*?)$', re.DOTALL | re.IGNORECASE), 'think_open_only'),
]

# Section header markers that indicate the start of actual formatted output
_SECTION_START_RE = re.compile(
    r'^\s*(PROSE|CHOICES|INPUT|STATE|MEDIA|SUMMARY|BEATS|'
    r'CHARACTERS_PRESENT|CHARACTERS_EXIT|NEW_CHARACTERS|NEW_LORE|'
    r'THREADS_OPEN|THREADS_CLOSE|WORLD_STATE_ADD|WORLD_STATE_REMOVE|'
    r'CHARACTER_STATUS)\s*:',
    re.MULTILINE | re.IGNORECASE,
)

# JSON start marker
_JSON_START_RE = re.compile(r'^\s*\{', re.MULTILINE)

# Chain-of-thought preamble patterns (text before first section header)
# These indicate structured analysis, not formatted output
_COT_PATTERNS = [
    re.compile(r'^\s*\d+\.\s+\*{0,2}(Analyze|Step|Draft|Plan|Consider|Review)', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s+(Step|Analysis|Plan|Draft|Reasoning)', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*\*{0,2}(Let me|Let\'s|I need to|I should|First,|Now,)', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*(Analysis|Reasoning|Planning|Drafting)\s*:', re.MULTILINE | re.IGNORECASE),
]


@dataclass(frozen=True)
class ThinkingExtraction:
    """Result of separating thinking content from formatted output.

    Attributes:
        has_thinking: True if any thinking/reasoning content was detected.
        thinking_text: The extracted reasoning content (empty if no thinking).
        output_text: The formatted output (same as input if no thinking detected).
        method: How thinking was detected: 'thinking_tag', 'think_tag',
                'preamble_before_section', 'preamble_before_json', 'cot_patterns',
                or 'none'.
        thinking_ratio: Fraction of the response that is thinking (0.0-1.0).
    """
    has_thinking: bool
    thinking_text: str
    output_text: str
    method: str
    thinking_ratio: float


def extract_thinking(raw: str) -> ThinkingExtraction:
    """Separate thinking/reasoning content from the formatted output.

    Detection order (first match wins):
    1. Explicit thinking tags (<thinking>, <think>, etc.)
    2. Preamble before first section header (PROSE:, CHOICES:, etc.)
    3. Preamble before JSON opening brace
    4. Chain-of-thought pattern matching

    If no thinking is detected, returns the original text as output_text
    with has_thinking=False.
    """
    if not raw or not raw.strip():
        return ThinkingExtraction(
            has_thinking=False,
            thinking_text="",
            output_text=raw,
            method="none",
            thinking_ratio=0.0,
        )

    # 1. Check for explicit thinking tags
    for pattern, method_name in _THINKING_TAGS + _R1_PATTERNS:
        match = pattern.search(raw)
        if match:
            thinking_text = match.group(1).strip()
            # Remove the thinking tag from the raw text to get the output
            output_text = pattern.sub("", raw).strip()
            total_len = len(raw)
            thinking_len = len(thinking_text)
            ratio = thinking_len / total_len if total_len > 0 else 0.0
            return ThinkingExtraction(
                has_thinking=True,
                thinking_text=thinking_text,
                output_text=output_text if output_text else raw,
                method=method_name,
                thinking_ratio=ratio,
            )

    # 2. Check for preamble before first section header
    section_match = _SECTION_START_RE.search(raw)
    if section_match:
        preamble = raw[:section_match.start()].strip()
        # Only count as thinking if preamble is substantial (> 50 chars)
        # and contains COT-like patterns
        if len(preamble) > 50 and _has_cot_patterns(preamble):
            output_text = raw[section_match.start():].strip()
            total_len = len(raw)
            thinking_len = len(preamble)
            ratio = thinking_len / total_len if total_len > 0 else 0.0
            return ThinkingExtraction(
                has_thinking=True,
                thinking_text=preamble,
                output_text=output_text,
                method="preamble_before_section",
                thinking_ratio=ratio,
            )

    # 3. Check for preamble before JSON
    json_match = _JSON_START_RE.search(raw)
    if json_match and json_match.start() > 0:
        preamble = raw[:json_match.start()].strip()
        if len(preamble) > 50 and _has_cot_patterns(preamble):
            output_text = raw[json_match.start():].strip()
            total_len = len(raw)
            thinking_len = len(preamble)
            ratio = thinking_len / total_len if total_len > 0 else 0.0
            return ThinkingExtraction(
                has_thinking=True,
                thinking_text=preamble,
                output_text=output_text,
                method="preamble_before_json",
                thinking_ratio=ratio,
            )

    # 4. Check if entire response is COT (no section headers or JSON found)
    if _has_cot_patterns(raw) and not section_match and not json_match:
        # The entire response appears to be thinking with no formatted output
        return ThinkingExtraction(
            has_thinking=True,
            thinking_text=raw.strip(),
            output_text="",
            method="cot_only_no_output",
            thinking_ratio=1.0,
        )

    # No thinking detected
    return ThinkingExtraction(
        has_thinking=False,
        thinking_text="",
        output_text=raw,
        method="none",
        thinking_ratio=0.0,
    )


def _has_cot_patterns(text: str) -> bool:
    """Check if text contains chain-of-thought reasoning patterns.

    Returns True if at least 2 COT pattern matches are found, or if
    the text contains explicit thinking markers like "Let me" or "Step 1".
    """
    if not text or not text.strip():
        return False

    match_count = 0
    for pattern in _COT_PATTERNS:
        if pattern.search(text):
            match_count += 1

    return match_count >= 1


def detect_thinking_model(raw: str) -> bool:
    """Quick check: does this response look like it came from a thinking model?

    Returns True if the response contains thinking tags or a substantial
    COT preamble. This is a lighter check than extract_thinking for use
    in model classification and reporting.
    """
    if not raw or not raw.strip():
        return False

    # Check for explicit tags
    for pattern, _ in _THINKING_TAGS + _R1_PATTERNS:
        if pattern.search(raw):
            return True

    # Check for preamble before section headers
    section_match = _SECTION_START_RE.search(raw)
    if section_match:
        preamble = raw[:section_match.start()].strip()
        if len(preamble) > 50 and _has_cot_patterns(preamble):
            return True

    # Check for COT-only response (no formatted output at all)
    if _has_cot_patterns(raw) and not section_match and not _JSON_START_RE.search(raw):
        return True

    return False
