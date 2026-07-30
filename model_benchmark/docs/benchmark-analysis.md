# SugarCube Benchmark Analysis Report

**Date:** 2026-07-30  
**Data source:** `benchmark_anon/results_anonymized.json` (108 results, 12 models, 3 variants x 3 directions)  
**Anonymized:** Model names replaced with `Model_A` through `Model_12`

---

## 1. Executive Summary

The benchmark tests 12 anonymized models on their ability to generate SugarCube-formatted interactive fiction passages. Each model runs 9 cases: 3 prompt variants (compact, full, json) x 3 direction prompts (A, B, C). Each response is scored across 6 categories.

**Key findings:**

- **Overall pass rate: 6/108 (5.6%)** -- extremely low
- **Passage structure is the universal bottleneck:** 102/108 failures (94%) are caused by `passage_structure` failures
- **Only 1 category (passage_structure) separates models** -- variable_scoping, naked_interpolation, and link_setter_syntax have 100% pass rates across all models
- **The benchmark does not differentiate models well:** scores cluster between 0.67 and 1.0 with almost no spread
- **Models exhibit systematic behavioral failures** that suggest prompt design issues, not model capability issues

---

## 2. Score Distribution

| Model | Avg Score | Passes | Failures | Fastest variant | Slowest variant |
|-------|-----------|--------|----------|-----------------|-----------------|
| Model_E | 0.889 | 3 | 6 | compact (7.4s) | json (5.1s) |
| Model_G | 0.870 | 2 | 7 | json (15.3s) | full (42.0s) |
| Model_C | 0.833 | 0 | 9 | json (5.2s) | compact (7.3s) |
| Model_D | 0.833 | 0 | 9 | json (3.9s) | compact (5.9s) |
| Model_F | 0.833 | 0 | 9 | json (4.6s) | full (8.3s) |
| Model_H | 0.833 | 0 | 9 | json (10.8s) | full (28.7s) |
| Model_I | 0.833 | 0 | 9 | json (15.3s) | full (46.8s) |
| Model_12 | 0.833 | 0 | 9 | json (3.7s) | compact (4.5s) |
| Model_B | 0.815 | 0 | 9 | json (5.2s) | compact (10.1s) |
| Model_A | 0.741 | 0 | 9 | compact (3.2s) | full (4.1s) |
| Model_11 | 0.759 | 1 | 8 | json (7.6s) | compact (18.2s) |
| Model_J | 0.722 | 0 | 9 | json (7.1s) | compact (17.3s) |

**Score clustering:** 7 of 12 models score exactly 0.833 (5/6 categories pass, only passage_structure fails). The benchmark cannot distinguish between these models.

---

## 3. Category-Level Failure Analysis

| Category | Pass | Fail | Pass rate | Root cause |
|----------|------|------|-----------|------------|
| markup_compliance | 93 | 15 | 86.1% | Models emit `**bold**` and `*italic*` Markdown instead of `''bold''` and `//italic//` |
| variable_scoping | 108 | 0 | 100% | All models use `to` operator correctly |
| passage_structure | 6 | 102 | 5.6% | Missing section headers OR parser warnings from null/malformed JSON |
| macro_usage | 106 | 2 | 98.1% | Only 2 cases of unbalanced `<<if>>` nesting |
| naked_interpolation | 108 | 0 | 100% | All models use naked `$var` correctly |
| link_setter_syntax | 108 | 0 | 100% | All models avoid `[[link]]` in choices |

**The benchmark is dominated by a single failure mode.** Three categories have 100% pass rates and contribute zero signal. The effective discriminating power of the benchmark rests entirely on `passage_structure` and `markup_compliance`.

---

## 4. Passage Structure Failure Deep Dive

### 4.1 Failure Pattern A: "Thinking preamble" (27 cases)

Models emit a chain-of-thought analysis before writing the passage. Example:

```
1.  **Analyze the Request:**
    *   **Genre/Setting:** Fantasy/Magical, Apprentice setting...
    *   **Characters:** Apprentice (protagonist), Mentor (wise old wizard)...
2.  **Drafting the Scene - The Encounter:**
    *   *Setting:* Late evening in a tower attic...
```

The section headers `PROSE:`, `CHOICES:`, `SUMMARY:` never appear because the model spends its entire output budget on analysis.

**Affected models:** Model_J (all compact + full), Model_11 (compact A-C, full A-B), Model_A (compact A-C)

**Root cause:** The prompt says "Begin now.\n\nPROSE:" at the end, but does not explicitly forbid chain-of-thought reasoning before the formatted output. Some models interpret the open-ended prompt as an instruction to "think step by step."

### 4.2 Failure Pattern B: Missing PROSE: header (45 cases)

Models write prose directly without the `PROSE:` section header. Example (Model_C):

```
''The air was thick with dust and the scent of old books. The apprentice's eyes adjusted slowly to the dim light...
```

The `_SECTION_RE` regex requires `PROSE:` at the start of a line (multiline mode). The model starts with formatted prose text, includes `CHOICES:` correctly, but omits `PROSE:` and `SUMMARY:` headers entirely.

**Affected models:** Model_C (all compact), Model_D (compact, missing SUMMARY only), Model_B, Model_F, Model_G, Model_H, Model_I (full variant)

### 4.3 Failure Pattern C: JSON parser cascade (27 cases, json variant only)

Models produce JSON with structural issues:
- `"prose": null` -- model sets the prose field to null
- `"prose": ["paragraph 1", "paragraph 2"]` -- model returns an array instead of a string
- Nested JSON wrapper: `{"user": {...}, "json_object": {"prose": [...]}}` instead of flat `{"prose": "..."}`

The JSON parser (`parse_model_output_json`) validates with pydantic and emits "Required section 'PROSE' missing" when prose is null/empty, even though the JSON key technically exists.

**Affected models:** All models on json variant except Model_G (which passes json B/C) and Model_11 (which passes json C)

### 4.4 Failure Pattern D: Full prompt is too long (38 cases)

The `build_full_passage_prompt` generates a prompt with 20+ section headers, SUGARCUBE_GUIDANCE block, and extensive formatting instructions. Models with smaller context windows or weaker instruction-following produce rambling outputs that miss all section headers.

**Evidence:** The full variant has the worst pass rate across all models:
- compact: 3 passes / 36 total (Model_E only)
- full: 0 passes / 36 total
- json: 3 passes / 36 total (Model_G B/C, Model_11 C)

### 4.5 The Scoring Contradiction

The `passage_structure` scorer has a logical inconsistency:

1. **Section detection** uses a regex: `re.search(rf'^{section}\s*:', raw, re.MULTILINE)` or `f'"{section.lower()}"' in raw.lower()`
2. **Warning detection** reads `parsed.parse_warnings` from the parser

For the JSON variant, the second check (`"prose" in raw.lower()`) matches the JSON key `"prose"`, so the scorer reports "Sections missing=none." But the parser found `prose: null` and emitted "Required section 'PROSE' missing" as a warning.

**Result:** The scorer says sections are present, but warnings are 6, and the category fails. The details string reads "Sections missing=none; warnings=6" which is confusing and contradictory.

---

## 5. Markup Compliance Failure Analysis

15 failures across 4 models. Two distinct patterns:

### 5.1 Pattern A: Full Markdown substitution (Model_J, Model_11 compact)

Models completely ignore SugarCube markup instructions and use Markdown throughout:
- `**bold**` instead of `''bold''`
- `*italic*` instead of `//italic//`
- Zero SugarCube markup tokens in output

This correlates with the "thinking preamble" pattern -- if the model is reasoning in Markdown, it continues in Markdown for the passage.

### 5.2 Pattern B: Section headers as Markdown (Model_A, Model_11 full)

Models bold the section headers themselves: `**PROSPEE**`, `**CHARACTERS_PRESENT**`, `**CURRENT ARC**`. This triggers both the bold regex and creates malformed section headers the parser can't find.

---

## 6. Model Behavior Taxonomy

### 6.1 "The Thinker" (Model_J, Model_11, Model_A compact)

**Behavior:** Writes a multi-paragraph chain-of-thought analysis before any formatted output. Uses Markdown throughout. Never reaches the actual passage format.

**Characteristics:**
- Response length: 2,000-2,900 chars (above average)
- Time: 15-23s per call (slow)
- JSON variant: sometimes works because JSON format constrains output
- Failure mode: 100% passage_structure + markup_compliance

**Prompt fix needed:** Explicit "Output ONLY the formatted passage. Do not include analysis, reasoning, or commentary."

### 6.2 "The Almost-There" (Model_C, Model_D, Model_B, Model_F, Model_H, Model_I)

**Behavior:** Writes actual SugarCube prose with correct markup, but omits `PROSE:` and `SUMMARY:` section headers. Includes `CHOICES:` correctly.

**Characteristics:**
- Response length: 600-2,800 chars
- Time: varies (4-47s depending on model size)
- SugarCube markup used correctly (`''bold''`, `//italic//`)
- Failure mode: passage_structure only (missing headers)

**Prompt fix needed:** Stronger emphasis on section headers. "Your output MUST begin with PROSE: on the first line."

### 6.3 "The JSON Wrangler" (Model_11 json, Model_C json, Model_I json)

**Behavior:** Produces valid JSON but with structural mismatches:
- `prose` as array instead of string
- `prose` as null
- Nested JSON wrapper objects
- Extra non-schema keys

**Characteristics:**
- JSON variant specific
- Parser falls back to delimited mode or produces empty ModelOutput
- Failure mode: passage_structure (parser warnings)

**Prompt fix needed:** Clearer JSON schema description. Emphasize `prose` must be a string, not array.

### 6.4 "The Good Citizen" (Model_E compact, Model_G json)

**Behavior:** Follows all formatting instructions. Produces clean section headers, correct SugarCube markup, proper choices.

**Characteristics:**
- Model_E: only passes compact variant, fails full (too many sections to track)
- Model_G: only passes json variant B/C, fails compact and full
- Response length: 650-930 chars (concise)
- Time: Model_E is fast (4-7s), Model_G is slow (13-45s)

**Implication:** Different models are better at different prompt formats. The benchmark should test all three variants and aggregate.

---

## 7. Scoring System Weaknesses

### 7.1 Binary pass/fail is too coarse

Each category returns only pass/fail. A response with 1 out of 4 required sections gets the same score (0.0) as one with 3 out of 4. The sub-check scores provide some granularity but are not surfaced in the per-model summary.

### 7.2 Three categories provide zero signal

`variable_scoping`, `naked_interpolation`, and `link_setter_syntax` have 100% pass rates. They are too easy for any model that produces SugarCube output at all. They waste 50% of the scoring surface.

### 7.3 No partial credit for section presence

A model that writes perfect prose with `CHOICES:` but forgets `SUMMARY:` scores 0.0 on passage_structure. This makes passage_structure a cliff: one missing header = total failure.

### 7.4 The parser/scorer contradiction

The scorer checks for section headers in raw text, while the parser checks for parsed content. These can disagree (see 4.5 above), producing confusing "Sections missing=none; warnings=6" results.

### 7.5 No content quality scoring

The benchmark only checks format compliance. A model that writes "PROSE:\nThe cat sat on the mat.\n\nCHOICES:\n- Go | hint\n\nSUMMARY:\nA cat." passes all categories. There is no check for narrative quality, length, coherence, or adherence to the direction prompt.

### 7.6 No direction-following scoring

The three directions (A: inventory/set flag, B: conditional, C: stats) test specific SugarCube features, but the scoring does not check whether the model actually followed the direction. A response that ignores the direction but has correct format passes.

---

## 8. Benchmark Coverage Gaps

### 8.1 Only one fixture context

All prompts use the same fantasy "apprentice discovers tome" scenario. Models may perform differently with different genres, tones, or complexity levels. A single context cannot distinguish genre-specific capability from general SugarCube compliance.

### 8.2 Only 3 directions, all easy

- Direction A: "check inventory and set a flag" -- tests `<<set>>`
- Direction B: "include a conditional" -- tests `<<if>>`
- Direction C: "show gold count and complex stat" -- tests `$var` interpolation

These are the simplest SugarCube features. Missing:
- `<<include>>` for shared content
- `<<capture>>` for loop variable safety
- `<<widget>>` for reusable macros
- Input macros (`<<textbox>>`, `<<radiobutton>>`, `<<listbox>>`)
- `<<for>>` loops
- `<<switch>>`/`<<case>>` conditionals
- `<<nobr>>` blocks
- Complex nested conditionals
- Multi-variable state management

### 8.3 No edge case testing

No tests for:
- Empty responses
- Very long responses (token limit truncation)
- Responses with mixed Markdown/SugarCube
- Responses with malformed macros
- Responses with correct format but wrong content
- Non-English responses
- Responses that include the prompt back

### 8.4 No multi-run variance testing

Each model runs each case exactly once (`--runs 1`). There is no measurement of run-to-run consistency. A model that passes 1/1 might fail 5/10 with temperature 0.2.

### 8.5 No latency/throughput scoring

Response time varies from 2.5s to 51s. This is not captured in the score. For production use, a model that takes 51s per passage may be unsuitable even if it scores perfectly.

---

## 9. Recommendations

### 9.1 Immediate: Improve prompt clarity (PROMPT FIX)

1. Add anti-thinking preamble to all prompt variants: "Output ONLY the formatted passage. Do not include analysis, reasoning, or step-by-step thinking."
2. Add first-line enforcement: "Your response MUST begin with `PROSE:` on the very first line."
3. For JSON variant: emphasize "The `prose` field must be a string (not an array, not null)."
4. For full variant: consider trimming the section list. 20+ sections overwhelms smaller models.

### 9.2 Short-term: Add more directions and contexts (TEST EXPANSION)

1. Add 5 new direction prompts (D-H) testing advanced SugarCube features
2. Add 3-4 new fixture contexts (sci-fi, horror, modern, cyberpunk)
3. Add edge case tests (empty, truncated, mixed markup)
4. Total case count should grow from 9 to 40+ per model

### 9.3 Short-term: Fix scoring granularity (SCORING FIX)

1. Surface sub-check scores in the per-model summary, not just pass/fail
2. Add partial credit for passage_structure (3/4 sections = 0.75, not 0.0)
3. Resolve the section-detection/parser-warning contradiction
4. Add a "direction_following" scoring category

### 9.4 Medium-term: Add content quality scoring (QUALITY SCORING)

1. Minimum prose length check (at least 2 sentences)
2. Choice count check (at least 2 choices)
3. Summary relevance check (mentions key entities from prompt)
4. Direction adherence check (response actually follows the direction prompt)

### 9.5 Deferred: Harness improvements (HARNESS UPGRADE)

**Do not implement yet.** Run the improved benchmark 10+ times first to collect baseline data. Then evaluate:
1. Parser improvements: handle `prose` as array, nested JSON, null fields
2. Scorer improvements: weighted categories, content quality
3. New scoring categories: direction_following, content_quality, format_efficiency
4. Multi-run variance scoring
5. Latency/throughput tracking

The harness improvement proposal is documented separately in `harness-improvement-proposal.md`.

---

## 10. Conclusion

The current benchmark has a single point of failure: `passage_structure` accounts for 94% of all failures, and the root cause is prompt design (models thinking before writing, missing section headers) rather than model capability. Three of six scoring categories provide zero signal.

The benchmark needs:
1. Better prompts that prevent thinking preambles and enforce section headers
2. More diverse test cases (directions, contexts, edge cases)
3. More granular scoring with partial credit and content quality checks
4. More runs per case to measure variance

The harness improvements (parser fixes, new scoring categories) should wait until we have a larger dataset from the improved benchmark to validate that the changes actually improve discrimination.
