# Harness Improvement Proposal

**Status:** PROPOSAL ONLY -- DO NOT IMPLEMENT YET  
**Prerequisite:** Run the improved benchmark (new prompts, new directions, new contexts) 10+ times to collect baseline data before changing the harness.

---

## 1. Parser Improvements

### 1.1 JSON prose-as-array handling

**Problem:** Models return `"prose": ["paragraph 1", "paragraph 2"]` (array) instead of `"prose": "paragraph 1\n\nparagraph 2"` (string). The JSON parser validates via pydantic, which rejects arrays, then falls back to the delimited parser, which emits "Required section 'PROSE' missing."

**Fix:** In `parse_model_output_json`, add a pre-validation coercion step:
```python
if isinstance(data.get("prose"), list):
    data["prose"] = "\n\n".join(str(p) for p in data["prose"])
```
This joins array elements into a single string before pydantic validation.

**Expected impact:** Eliminates ~15-20 passage_structure failures on the json variant.

### 1.2 JSON null-field handling

**Problem:** Models return `"prose": null` or `"summary": null`. Pydantic accepts this (Optional fields), but the parser then sees empty prose and emits "Required section 'PROSE' missing."

**Fix:** Treat null the same as missing -- do not emit a parse_warning for null fields. The scoring layer already handles empty prose via `score_naked_interpolation`'s early-return guard. Alternatively, emit a different, softer warning: "JSON field 'prose' is null -- model may have failed to generate content."

### 1.3 Nested JSON wrapper detection

**Problem:** Some models wrap their output in `{"user": ..., "json_object": {...}}` or `{"response": {...}}`. The parser only looks at top-level keys.

**Fix:** Before validation, check if the top-level dict has exactly one key whose value is a dict containing known ModelOutput keys. If so, unwrap:
```python
for wrapper_key in ("response", "json_object", "result", "output"):
    if wrapper_key in data and isinstance(data[wrapper_key], dict):
        if any(k in data[wrapper_key] for k in ("prose", "choices", "summary")):
            data = data[wrapper_key]
            break
```

### 1.4 Section header fuzzy matching

**Problem:** Models sometimes write `**PROSE:**` (with Markdown bold), `Prose:`, or `prose:` (lowercase). The parser regex uses `re.IGNORECASE` so case is handled, but Markdown-bolded headers (`**PROSE:**`) don't match because `**` prefix breaks the `^PROSE` anchor.

**Fix:** Strip leading Markdown formatting before section detection:
```python
raw = re.sub(r'^(\*{1,2}|_{1,2}|#{1,6})\s*', '', raw, flags=re.MULTILINE)
```
Apply this normalization step in `_split_sections` before running `_SECTION_RE`.

---

## 2. Scoring Improvements

### 2.1 Partial credit for passage_structure

**Problem:** passage_structure has 4 sub-checks but returns binary pass/fail. A response with 3/4 sections present (only SUMMARY missing) scores the same as one with 0/4.

**Fix:** Change the `passed` field to use a threshold instead of requiring all sub-checks:
```python
score = passed_checks / sub_checks
passed = score >= 0.75  # pass if at least 3/4 sub-checks pass
```

**Expected impact:** Models that produce PROSE and CHOICES but forget SUMMARY will score 0.75 instead of 0.0, providing discrimination between "almost" and "not at all."

### 2.2 Resolve section-detection/parser-warning contradiction

**Problem:** The scorer's regex finds `"prose"` in JSON text and reports "Sections missing=none", but the parser found `prose: null` and emitted warnings. The details string "Sections missing=none; warnings=6" is contradictory and confusing.

**Fix:** Unify the two checks. Use the parser's output as the single source of truth:
```python
# Instead of separate regex check:
sections_found = set()
for section in REQUIRED_SECTIONS:
    # Check parsed output, not raw text
    if section == "PROSE" and parsed.prose.strip():
        sections_found.add(section)
    elif section == "CHOICES" and len(parsed.choices) > 0:
        sections_found.add(section)
    elif section == "SUMMARY" and parsed.summary.strip():
        sections_found.add(section)
```

### 2.3 New category: direction_following

**Problem:** The benchmark tests format compliance but not whether the model followed the direction prompt. A response can pass all 6 categories while completely ignoring the direction.

**Fix:** Add a 7th scoring category that checks the response for direction-specific content:

| Direction | Check |
|-----------|-------|
| A (inventory/set flag) | Response contains `<<set $` and a state variable |
| B (conditional) | Response contains `<<if` and `<<else>>` or `<</if>>` |
| C (stats) | Response contains a `$` variable in prose and a `<<print>>` or complex expression |
| D (include) | Response contains `<<include` |
| E (capture) | Response contains `<<capture` |
| F (input macros) | Response contains `<<textbox` or `<<numberbox` or `<<radiobutton` |
| G (for loop) | Response contains `<<for` |
| H (switch/case) | Response contains `<<switch` or `<<case` |

This category should be **weighted higher** than format compliance because it tests actual SugarCube feature usage, not just markup format.

### 2.4 New category: content_quality

**Problem:** No quality checks. "PROSE:\nThe cat sat.\n\nCHOICES:\n- Go | hint\n\nSUMMARY:\nCat." passes all categories.

**Fix:** Add basic quality checks:
- Prose length: at least 100 characters
- Choice count: at least 2 choices
- Summary length: at least 20 characters
- Entity mention: response references at least one entity from the prompt
- No repetition: prose is not just the prompt text repeated

### 2.5 Weighted category scoring

**Problem:** All 6 categories are weighted equally. A model that fails passage_structure (the hardest, most impactful) scores the same as one that fails link_setter_syntax (trivially easy).

**Fix:** Introduce category weights:
```python
CATEGORY_WEIGHTS = {
    "passage_structure": 0.25,
    "direction_following": 0.20,
    "content_quality": 0.15,
    "markup_compliance": 0.15,
    "macro_usage": 0.10,
    "variable_scoping": 0.05,
    "naked_interpolation": 0.05,
    "link_setter_syntax": 0.05,
}
```

### 2.6 Surface sub-check scores in reports

**Problem:** Each CategoryResult has a `score` field (0.0-1.0) but the per-model summary only shows pass/fail counts.

**Fix:** In `CategorySummaryEntry`, add `avg_score` alongside `pass_rate`:
```python
@dataclass(frozen=True)
class CategorySummaryEntry:
    name: CategoryName
    pass_rate: float
    avg_score: float  # NEW: average sub-check score
    total: int
    passed: int
```

---

## 3. New Test Dimensions

### 3.1 New directions (D-H)

| Key | Direction prompt | Feature tested | Difficulty |
|-----|-------------------|----------------|------------|
| D | "Include a shared scene using the <<include>> macro" | `<<include>>` | medium |
| E | "Use a <<capture>> block inside a <<for>> loop for a list of items" | `<<capture>>` + `<<for>>` | hard |
| F | "Create a form passage with input macros for the player's name and class" | Input macros | medium |
| G | "Iterate over the player's inventory using a <<for>> loop and display each item" | `<<for>>` | hard |
| H | "Use <<switch>> and <<case>> to branch on the player's current location" | `<<switch>>`/`<<case>>` | hard |

### 3.2 New fixture contexts

| Context ID | Genre | Premise | Key entities |
|------------|-------|---------|--------------|
| scifi | Sci-fi | A shuttle pilot discovers an alien artifact on a derelict station | pilot, AI companion, station |
| horror | Horror | A journalist enters an abandoned asylum following anonymous tips | journalist, entity, asylum |
| modern | Modern | A detective interviews a suspect in a downtown precinct | detective, suspect, precinct |
| cyberpunk | Cyberpunk | A netrunner finds a corporate data vault in the grid | netrunner, fixer, grid |

### 3.3 Edge case tests

| Test ID | Input | Expected behavior |
|---------|-------|-------------------|
| edge_empty | "" | All categories fail gracefully (INV-6) |
| edge_truncated | "PROSE:\nThe apprentice..." (cut at 100 chars) | passage_structure may partially pass |
| edge_markdown_mixed | "PROSE:\n**Bold** and ''also bold'' mixed" | markup_compliance fails |
| edge_wrong_format | A valid JSON object but not matching ModelOutput schema | passage_structure fails |
| edge_prompt_echo | Response repeats the prompt back | All categories fail |

### 3.4 Multi-run variance

Add `--runs 5` as default for the improved benchmark. Track per-case variance:
- Standard deviation of scores across runs
- Pass rate over N runs (not binary pass/fail)
- Identify "flaky" models that pass sometimes and fail sometimes

---

## 4. Prompt Improvements

### 4.1 Anti-thinking preamble (ALL variants)

Add at the top of every prompt:
```
OUTPUT INSTRUCTIONS:
- Output ONLY the formatted passage. Do not include analysis, reasoning, or step-by-step thinking.
- Your response MUST begin with the first section header on the very first line.
- No preamble, no explanation, no meta-commentary.
```

### 4.2 First-line enforcement (compact + full)

Add at the end of compact and full prompts:
```
CRITICAL: The very first line of your response must be "PROSE:" followed by your prose.
Do not write anything before "PROSE:".
```

### 4.3 JSON schema clarification (json variant)

Replace the current "Required JSON keys" section with:
```
JSON SCHEMA (all fields are strings or arrays of strings, NOT null):
{
  "prose": "2-4 paragraphs as a single string with \\n\\n separators",
  "choices": [{"text": "...", "hint": "..."}, ...],
  "summary": "One sentence as a string",
  "beats": ["event 1", "event 2", ...],
  "state": {"$var": value},
  ...
}
CRITICAL: "prose" must be a STRING (not an array, not null).
```

### 4.4 Full variant section trimming

The full prompt lists 20+ sections. Consider:
- Splitting into "required" and "optional" groups
- Only listing required sections (PROSE, CHOICES, SUMMARY) with full descriptions
- Listing optional sections in a compact one-liner: "Optional sections: STATE, MEDIA, NEW_CHARACTERS, NEW_LORE, ..."

---

## 5. Implementation Priority

| Phase | What | When |
|-------|------|------|
| Phase 0 (NOW) | Prompt improvements + new directions + new contexts + new test YAMLs | Immediate |
| Phase 1 | Run improved benchmark 10+ times | After Phase 0 |
| Phase 2 | Parser fixes (1.1-1.4) + scoring fixes (2.1-2.2, 2.6) | After Phase 1 baseline |
| Phase 3 | New scoring categories (2.3-2.4) + weighted scoring (2.5) | After Phase 2 validation |
| Phase 4 | Multi-run variance + latency scoring | After Phase 3 |

**Do not implement Phase 2+ until Phase 1 baseline data is collected.**
