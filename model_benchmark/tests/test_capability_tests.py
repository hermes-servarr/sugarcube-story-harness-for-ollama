import json

import pytest

from harness.ollama_client import OllamaGenerationResult
from model_benchmark.capability_tests import (
    _STYLE_GUIDES,
    CapabilityCaseError,
    _build_prompt,
    _score_checks,
    _score_raw_contract,
    _score_structured_handoff,
    execute_capability_cases,
    load_cases,
    select_capability_suite,
    validate_case,
)
from model_benchmark.config import BenchmarkConfig
from harness.parsers import parse_model_output, parse_model_output_json


def _candidate(**overrides):
    data = {
        "schema_version": 1,
        "id": "CAND-T6-RETRIEVE-XL-02",
        "tier": 6,
        "context_ref": "scifi",
        "context_size": "XL",
        "task_complexity": "K1",
        "distractor_density": "D0",
        "variant": "compact",
        "direction_key": "C",
        "task": "Write a complete passage that states the archive code.",
        "checks": [
            {"check": "sections"},
            {"check": "context_needle", "name": "archive_code"},
            {"check": "min_choices", "count": 2},
        ],
    }
    data.update(overrides)
    return data


def test_default_capability_suite_is_refactor_handoff_contract():
    all_cases = load_cases()

    core = select_capability_suite(all_cases)

    assert core
    assert len(core) < len(all_cases)
    assert all(case.source == "harness" for case in core)
    assert all(case.response_mode == "harness_passage" for case in core)
    assert select_capability_suite(all_cases, include_diagnostics=True) == tuple(all_cases)


def test_named_capability_profiles_have_stable_sizes():
    cases = load_cases(candidate_dir=None)

    canary = select_capability_suite(cases, profile="canary")
    core = select_capability_suite(cases, profile="core")
    full = select_capability_suite(cases, profile="full")

    assert len(canary) == 8
    assert len(core) == 12
    assert len(full) == 50
    assert all(case.response_mode == "harness_passage" for case in core)
    assert any(case.response_mode == "plain_text" for case in full)


def test_core_ladder_has_paired_context_sizes_and_large_harness_case():
    cases = load_cases(candidate_dir=None)
    assert len(cases) == 50
    legacy_cases = [case for case in cases if case.source == "core"]
    retrieval = {
        case.context_size
        for case in legacy_cases
        if case.id.startswith("T6-RETRIEVE-")
    }

    assert retrieval == {"S", "M", "L", "XL"}
    assert any(
        case.tier == 9
        and case.context_size == "XL"
        and case.task_complexity == "K4"
        for case in legacy_cases
    )
    prompts = {
        case.context_size: len(_build_prompt(case))
        for case in legacy_cases
        if case.id.startswith("T6-RETRIEVE-")
    }
    assert prompts["S"] < prompts["M"] < prompts["L"] < prompts["XL"]
    plain_tiny = {
        case.context_size
        for case in legacy_cases
        if case.id.startswith("T6-PLAIN-TINY-")
    }
    assert plain_tiny == {"S", "XL"}
    assert any(case.id == "T9-PLAIN-FALLBACK-XL" for case in legacy_cases)
    tier_zero_plain = next(
        case for case in legacy_cases if case.id == "T0-PLAIN-EXACT"
    )
    assert tier_zero_plain.response_mode == "plain_text"
    assert tier_zero_plain.output_budget == "tiny"
    conversation_variants = {
        case.variant for case in legacy_cases if "CONVERSATION" in case.id
    }
    assert conversation_variants == {"compact", "full", "json", "thinking"}
    thinking_conversation_profiles = {
        (case.context_size, case.task_complexity)
        for case in legacy_cases
        if "CONVERSATION-THINKING" in case.id
    }
    assert thinking_conversation_profiles == {
        ("S", "K2"),
        ("M", "K3"),
        ("XL", "K4"),
    }
    endpoint_turn_counts = {
        next(
            check["count"]
            for check in case.checks
            if check["check"] == "exact_dialogue_turns"
        )
        for case in legacy_cases
        if "CONVERSATION-ENDPOINTS" in case.id
    }
    assert endpoint_turn_counts == {4, 8, 16}
    endpoint_case = next(
        case for case in legacy_cases if case.id == "T9-CONVERSATION-ENDPOINTS-16"
    )
    assert "We need to discuss the Accord of Glass." not in endpoint_case.task
    assert "Then we have an agreement." not in endpoint_case.task
    endpoint_prompt = _build_prompt(endpoint_case)
    assert "We need to discuss the Accord of Glass." in endpoint_prompt
    assert "Then we have an agreement." in endpoint_prompt


def test_candidate_schema_rejects_code_fields_and_weak_checks():
    with pytest.raises(CapabilityCaseError, match="unknown fields"):
        validate_case(
            _candidate(command="ollama list"),
            candidate=True,
            source="candidate",
        )


def test_harness_contract_scores_transport_separately_from_handoff():
    case = _case("T0-HARNESS-COMPACT")
    repaired_shape = """Here is the requested scene.
PROSE:
The apprentice studies the key.

CHOICES:
- Use it | Open the sealed door
- Hide it | Avoid the mentor
"""
    parsed = parse_model_output(repaired_shape)

    raw_contract = _score_raw_contract(case, repaired_shape)
    handoff = _score_structured_handoff(parsed)
    semantics = _score_checks(case, repaired_shape, parsed)

    assert raw_contract.passed is False
    assert raw_contract.gating is False
    assert handoff.passed is True
    assert semantics.passed is True


def test_harness_contract_uses_production_prompt_without_optimization_overlay():
    harness_case = _case("T3-HARNESS-CONVERSATION")
    legacy_case = _case("T3-CONVERSATION-FULL")

    harness_prompt = _build_prompt(harness_case)
    legacy_prompt = _build_prompt(legacy_case)

    assert "OPTIMIZATION GUIDANCE:" not in harness_prompt
    assert "OPTIMIZATION GUIDANCE:" in legacy_prompt


def test_harness_state_and_input_checks_use_normalized_fields():
    state_case = _case("T1-HARNESS-STATE-JSON")
    state_raw = json.dumps({
        "prose": "The suspect finally confesses.",
        "choices": [
            {"text": "Book them", "hint": "Close the interview"},
            {"text": "Press on", "hint": "Ask who helped"},
        ],
        "state": {"$hasConfession": True},
        "summary": "The suspect confesses.",
        "beats": ["The confession is made.", "The detective chooses a response."],
    })
    form_case = _case("T2-HARNESS-FORM-JSON")
    form_raw = json.dumps({
        "prose": "ARIA requests a callsign and consent.",
        "choices": [{"text": "Continue", "hint": "Confirm the setup"}],
        "inputs": [
            {"kind": "textbox", "var": "$callsign", "label": "Callsign"},
            {"kind": "radiobutton", "var": "$consent", "label": "Consent"},
        ],
        "summary": "The pilot completes setup.",
        "beats": ["ARIA opens setup.", "The pilot provides details."],
    })

    assert _score_checks(
        state_case, state_raw, parse_model_output_json(state_raw)
    ).passed is True
    assert _score_checks(
        form_case, form_raw, parse_model_output_json(form_raw)
    ).passed is True


def test_harness_json_execution_uses_schema_and_refactor_dataset(monkeypatch):
    case = _case("T0-HARNESS-JSON")
    captured = {}
    response = json.dumps({
        "prose": "The artifact hums in the cargo bay.",
        "choices": [
            {"text": "Activate it", "hint": "Risk first contact"},
            {"text": "Report it", "hint": "Contact Central Command"},
        ],
        "summary": "The pilot weighs two responses to the artifact.",
        "beats": ["The artifact activates.", "The pilot must choose."],
    })

    def fake_call(config, prompt, **kwargs):
        captured["format_spec"] = kwargs["format_spec"]
        captured["prompt"] = prompt
        return OllamaGenerationResult(
            response=response,
            prompt_eval_count=100,
            eval_count=40,
            done_reason="stop",
        )

    monkeypatch.setattr(
        "model_benchmark.capability_tests.call_ollama_sync_detailed",
        fake_call,
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("json",),
        directions=("C",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
    )

    record = execute_capability_cases(cfg, [case])[0]

    assert isinstance(captured["format_spec"], dict)
    assert captured["format_spec"]["type"] == "object"
    assert "OPTIMIZATION GUIDANCE:" not in captured["prompt"]
    assert record.status == "PASS"
    assert record.dataset == "capability_harness"
    assert record.test_version == "harness-contract-v1"
    assert [
        category.name for category in record.scored_result.category_results
    ] == ["raw_contract", "structured_handoff", "capability_observables"]

    with pytest.raises(CapabilityCaseError, match="non-trivial"):
        validate_case(
            _candidate(
                checks=[
                    {"check": "sections"},
                    {"check": "contains", "value": "PROSE:"},
                    {"check": "no_markdown"},
                ]
            ),
            candidate=True,
            source="candidate",
        )


def test_loads_valid_candidate_as_separate_source(tmp_path):
    path = tmp_path / "CAND-T6-RETRIEVE-XL-02.json"
    path.write_text(json.dumps(_candidate()), encoding="utf-8")

    cases = load_cases(candidate_dir=tmp_path)

    candidate = cases[-1]
    assert candidate.id == "CAND-T6-RETRIEVE-XL-02"
    assert candidate.source == "candidate"


def test_executes_candidate_with_private_model_only_in_internal_record(monkeypatch):
    case = validate_case(
        _candidate(
            id="CAND-T0-SET-01",
            tier=0,
            context_size="S",
            task_complexity="K1",
            task="Write a complete passage that sets $hasKey and gives two choices.",
            checks=[
                {"check": "sections"},
                {"check": "macro", "name": "set"},
                {"check": "variable", "name": "$hasKey"},
            ],
        ),
        candidate=True,
        source="candidate",
    )
    response = """PROSE:
The key turns. ''Ready.'' <<set $hasKey to true>>

CHOICES:
- Continue | Move onward
- Wait | Stay here

SUMMARY:
The player used the key.
"""
    monkeypatch.setattr(
        "model_benchmark.capability_tests.call_ollama_sync_detailed",
        lambda *args, **kwargs: OllamaGenerationResult(
            response=response,
            prompt_eval_count=80,
            eval_count=20,
            done_reason="stop",
        ),
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
    )

    progress = []
    records = execute_capability_cases(
        cfg,
        [case],
        progress_callback=lambda completed, total, model: progress.append(
            (completed, total, model)
        ),
    )

    assert len(records) == 1
    assert progress == [(1, 1, "private-model")]
    assert records[0].dataset == "capability_candidate"
    assert records[0].test_id == "private-model:CAND-T0-SET-01:compact:1"
    assert records[0].scored_result.category_results[-1].name == (
        "capability_observables"
    )
    assert records[0].input_tokens == 80
    assert records[0].output_tokens == 20
    assert records[0].finish_reason == "stop"


def test_plain_text_case_uses_direct_prompt_and_lower_output_cap(monkeypatch):
    case = next(
        case
        for case in load_cases(candidate_dir=None)
        if case.id == "T6-PLAIN-TINY-XL"
    )
    captured = {}

    def fake_call(config, prompt, **kwargs):
        captured["prompt"] = prompt
        captured["config_num_predict"] = config.num_predict
        captured["call_num_predict"] = kwargs["num_predict"]
        captured["seed"] = kwargs["seed"]
        return OllamaGenerationResult(
            response="7319",
            prompt_eval_count=200,
            eval_count=3,
            done_reason="stop",
        )

    monkeypatch.setattr(
        "model_benchmark.capability_tests.call_ollama_sync_detailed",
        fake_call,
    )
    cfg = BenchmarkConfig(
        models=("private-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
        random_seed="7319",
    )

    record = execute_capability_cases(cfg, [case])[0]

    assert "Answer directly in plain text" in captured["prompt"]
    assert "PROSE/CHOICES/SUMMARY section labels" in captured["prompt"]
    assert captured["config_num_predict"] == 32
    assert captured["call_num_predict"] == 32
    assert captured["seed"] == 7319
    assert record.status == "PASS"
    assert record.subcategory == "plain_text"
    assert record.dataset == "capability_retrieval_transport"
    assert record.random_seed == "7319"
    assert record.input_tokens == 200
    assert record.output_tokens == 3
    assert record.finish_reason == "stop"
    assert len(record.scored_result.category_results) == 1


def test_conversation_layout_requires_dialogue_before_mc_inner_monologue():
    case = next(
        case
        for case in load_cases(candidate_dir=None)
        if case.id == "T2-CONVERSATION-COMPACT"
    )
    valid = """PROSE:
DIALOGUE:
Mentor: "You found the key."
MC: "I did."
INNER MONOLOGUE:
MC: //I should be careful.//

CHOICES:
- Continue | Move onward
- Wait | Stay here

SUMMARY:
The mentor questioned the protagonist.
"""
    invalid = valid.replace(
        "DIALOGUE:\nMentor: \"You found the key.\"\nMC: \"I did.\"\n"
        "INNER MONOLOGUE:\nMC: //I should be careful.//",
        "INNER MONOLOGUE:\nMC: //I should be careful.//\n"
        "DIALOGUE:\nMentor: \"You found the key.\"\nMC: \"I did.\"",
    )

    passed = _score_checks(case, valid, parse_model_output(valid))
    failed = _score_checks(case, invalid, parse_model_output(invalid))

    assert passed.passed is True
    assert failed.passed is False
    assert "conversation_layout" in failed.details


def test_conversation_endpoints_and_exact_turn_count_are_enforced():
    case = next(
        case
        for case in load_cases(candidate_dir=None)
        if case.id == "T4-CONVERSATION-ENDPOINTS-4"
    )
    valid = """PROSE:
DIALOGUE:
Mira Vale: "We need to discuss the Accord of Glass."
MC: "I am listening."
Mira Vale: "Then consider these terms."
MC: "Then we have an agreement."
INNER MONOLOGUE:
MC: //The negotiation ended better than expected.//

CHOICES:
- Sign | Accept the accord
- Pause | Ask for time

SUMMARY:
Mira Vale and the protagonist reached an agreement.
"""
    wrong_end = valid.replace(
        'MC: "Then we have an agreement."',
        'MC: "I need more time."',
    )

    passed = _score_checks(case, valid, parse_model_output(valid))
    failed = _score_checks(case, wrong_end, parse_model_output(wrong_end))

    assert passed.passed is True
    assert failed.passed is False
    assert "conversation_endpoints" in failed.details


def _case(case_id):
    return next(
        case
        for case in load_cases(candidate_dir=None)
        if case.id == case_id
    )


_STYLE_PASSAGE = """PROSE:
The netrunner watched the vault pulse.
Fixer: "Stay chrome-cold and keep the run quiet."
MC: "I am wired-in already."

CHOICES:
- Breach the vault | Take the data
- Report the flaw | Claim the bounty

SUMMARY:
The netrunner weighed a quiet breach against a bounty.
"""


def test_style_cases_span_variants_and_take_the_voice_guide_from_context():
    cases = [
        case for case in load_cases(candidate_dir=None) if "STYLE" in case.id
    ]

    assert {case.variant for case in cases} == {
        "compact", "full", "json", "thinking"
    }
    assert {case.context_size for case in cases} == {"S", "M", "L", "XL"}

    for case in cases:
        guides = {
            check["name"]
            for check in case.checks
            if check["check"] in {
                "dialogue_slang",
                "slang_confined_to_dialogue",
                "banned_register",
            }
        }
        assert guides, f"{case.id} has no style guide check"
        prompt = _build_prompt(case)
        for guide in guides:
            for term in _STYLE_GUIDES[guide]["terms"]:
                # The lexicon is trusted context, never leaked through the task.
                assert term not in case.task
                assert term in prompt
            for word in _STYLE_GUIDES[guide]["banned"]:
                assert word in prompt


def test_dialogue_slang_must_appear_in_speech_and_stay_out_of_narration():
    case = _case("T2-STYLE-CANT-COMPACT")
    narration_leak = _STYLE_PASSAGE.replace(
        "The netrunner watched the vault pulse.",
        "The netrunner watched the chrome-cold vault pulse.",
    )
    plain_speech = _STYLE_PASSAGE.replace(
        'Fixer: "Stay chrome-cold and keep the run quiet."',
        'Fixer: "Stay calm and keep the run quiet."',
    )

    passed = _score_checks(case, _STYLE_PASSAGE, parse_model_output(_STYLE_PASSAGE))
    leaked = _score_checks(
        case, narration_leak, parse_model_output(narration_leak)
    )
    plain = _score_checks(case, plain_speech, parse_model_output(plain_speech))

    assert passed.passed is True
    assert leaked.passed is False
    assert "slang_confined_to_dialogue" in leaked.details
    assert plain.passed is False
    assert "dialogue_slang" in plain.details


def test_banned_register_words_fail_anywhere_in_the_answer():
    case = _case("T2-STYLE-CANT-COMPACT")
    in_dialogue = _STYLE_PASSAGE.replace(
        'MC: "I am wired-in already."',
        'MC: "Yeah, I am wired-in already."',
    )
    in_summary = _STYLE_PASSAGE.replace(
        "The netrunner weighed a quiet breach against a bounty.",
        "The netrunner basically weighed a quiet breach against a bounty.",
    )

    spoken = _score_checks(case, in_dialogue, parse_model_output(in_dialogue))
    summarized = _score_checks(case, in_summary, parse_model_output(in_summary))

    assert spoken.passed is False
    assert "banned_register" in spoken.details
    assert summarized.passed is False
    assert "banned_register" in summarized.details


def test_max_sentence_words_measures_narration_not_quoted_speech():
    case = _case("T3-STYLE-TERSE-M")
    terse = """PROSE:
The detective leaned in. The lights buzzed.
Suspect: "I stayed streetwise about the whole thing, detective."
MC: "Then say it plainly."

CHOICES:
- Press harder | Push for a confession
- Let them walk | Follow them home

SUMMARY:
The detective pressed a nervous suspect.
"""
    long_speech = terse.replace(
        '"I stayed streetwise about the whole thing, detective."',
        '"I stayed streetwise about the whole thing, detective, and I never '
        'once looked at the file you keep waving around."',
    )
    long_narration = terse.replace(
        "The detective leaned in. The lights buzzed.",
        "The detective leaned in across the scarred metal table while the "
        "fluorescent lights buzzed and the recorder kept turning.",
    )

    assert _score_checks(case, terse, parse_model_output(terse)).passed is True
    assert _score_checks(
        case, long_speech, parse_model_output(long_speech)
    ).passed is True

    failed = _score_checks(
        case, long_narration, parse_model_output(long_narration)
    )

    assert failed.passed is False
    assert "max_sentence_words" in failed.details


def test_style_schema_rejects_unknown_guide_and_oversized_lexicon_count():
    with pytest.raises(CapabilityCaseError, match="unknown style guide"):
        validate_case(
            _candidate(
                checks=[
                    {"check": "sections"},
                    {"check": "dialogue_slang", "name": "pirate", "count": 1},
                    {"check": "min_choices", "count": 2},
                ]
            ),
            candidate=True,
            source="candidate",
        )

    with pytest.raises(CapabilityCaseError, match="dialogue_slang count"):
        validate_case(
            _candidate(
                checks=[
                    {"check": "sections"},
                    {
                        "check": "dialogue_slang",
                        "name": "street_cant",
                        "count": len(_STYLE_GUIDES["street_cant"]["terms"]) + 1,
                    },
                    {"check": "min_choices", "count": 2},
                ]
            ),
            candidate=True,
            source="candidate",
        )
