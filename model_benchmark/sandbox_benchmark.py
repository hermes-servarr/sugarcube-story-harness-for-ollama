"""Frozen deterministic Hybrid/Sandbox runtime benchmark scenarios."""
from __future__ import annotations

import hashlib
import json
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from harness.generation import ExperienceProfile, NarrativeSlot, PassagePlan
from harness.models import ModelOutput
from harness.simulation import (
    CharacterEffect,
    CharacterStatDefinition,
    EncounterTemplate,
    FactionEffect,
    FactionState,
    LocationNode,
    WorldTopology,
    apply_character_effect,
    apply_faction_effect,
    apply_local_action,
    available_opportunities,
    create_runtime_session,
    character_context,
    initialize_character,
    record_encounter,
    select_encounter,
    travel,
)
from model_benchmark.scoring import CategoryResult
from model_benchmark.scoring import ModelRunResult
from model_benchmark.runner import result_record_from_model_run


SANDBOX_CASES_PATH = Path(__file__).with_name("sandbox_cases.json")
SANDBOX_DOMAIN_CASES_PATH = Path(__file__).with_name("sandbox_domain_cases.json")
SANDBOX_CANARY_IDS = ("S0-CYCLIC-REVISIT", "S1-RESOURCE-BOUND")


class SandboxCaseError(ValueError):
    pass


@dataclass(frozen=True)
class SandboxAction:
    kind: str
    id: str


@dataclass(frozen=True)
class SandboxExpected:
    location: str
    tick: int
    world_state: dict[str, Any]
    resources: dict[str, float | int]
    visits: int
    opportunity_ids: tuple[str, ...]


@dataclass(frozen=True)
class SandboxCase:
    id: str
    seed: int
    topology: WorldTopology
    start_location: str
    time_model: str
    world_state: dict[str, Any]
    resources: dict[str, float | int]
    actions: tuple[SandboxAction, ...]
    expected: SandboxExpected


def sandbox_corpus_hash(path: Path = SANDBOX_CASES_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sandbox_corpus_checksums(path: Path = SANDBOX_CASES_PATH) -> tuple[str, ...]:
    return (
        f"sha256:{sandbox_corpus_hash(path)}",
        f"sha256:{hashlib.sha256(SANDBOX_DOMAIN_CASES_PATH.read_bytes()).hexdigest()}",
    )


def _validate_case(raw: Any) -> SandboxCase:
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "id", "seed", "topology", "start_location",
        "time_model", "world_state", "resources", "actions", "expected",
    }:
        raise SandboxCaseError("sandbox case fields do not match schema")
    if raw["schema_version"] != 1 or not isinstance(raw["seed"], int):
        raise SandboxCaseError("unsupported sandbox case schema or seed")
    actions = tuple(SandboxAction(**item) for item in raw["actions"])
    if not actions or any(item.kind not in {"local_action", "travel"} for item in actions):
        raise SandboxCaseError("sandbox case needs valid actions")
    expected = SandboxExpected(
        **{**raw["expected"], "opportunity_ids": tuple(raw["expected"]["opportunity_ids"])}
    )
    return SandboxCase(
        id=raw["id"], seed=raw["seed"], topology=WorldTopology.model_validate(raw["topology"]),
        start_location=raw["start_location"], time_model=raw["time_model"],
        world_state=dict(raw["world_state"]), resources=dict(raw["resources"]),
        actions=actions, expected=expected,
    )


def load_sandbox_cases(path: Path = SANDBOX_CASES_PATH) -> tuple[SandboxCase, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SandboxCaseError("sandbox case file must contain an array")
    cases = tuple(_validate_case(item) for item in raw)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise SandboxCaseError("duplicate sandbox case id")
    return cases


def select_sandbox_cases(cases: Iterable[SandboxCase], profile: str) -> tuple[SandboxCase, ...]:
    cases = tuple(cases)
    if profile == "sandbox-core":
        return cases
    if profile != "sandbox-canary":
        raise SandboxCaseError("unknown sandbox profile")
    by_id = {case.id: case for case in cases}
    try:
        return tuple(by_id[case_id] for case_id in SANDBOX_CANARY_IDS)
    except KeyError as exc:
        raise SandboxCaseError(f"missing sandbox canary case: {exc.args[0]}") from exc


def _run(case: SandboxCase):
    topology_before = case.topology.model_dump_json()
    session = create_runtime_session(
        case.topology, session_id=f"benchmark_{case.id.lower().replace('-', '_')}",
        experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
        start_location=case.start_location, time_model=case.time_model, seed=case.seed,
        world_state=case.world_state, resources=case.resources,
    )
    eligibility_exact = True
    authority = True
    traces = []
    for action in case.actions:
        available = available_opportunities(case.topology, session)
        opportunity = next((item for item in available if item.source_id == action.id and item.kind == action.kind), None)
        eligibility_exact &= opportunity is not None
        if opportunity is None:
            authority = False
            break
        if action.kind == "travel":
            session, trace = travel(case.topology, session, action.id, expected_revision=session.revision)
        else:
            session, trace = apply_local_action(case.topology, session, action.id, expected_revision=session.revision)
        traces.append(trace.model_dump(mode="json"))
    return session, traces, eligibility_exact, authority, topology_before == case.topology.model_dump_json()


def evaluate_sandbox_case(case: SandboxCase) -> tuple[CategoryResult, ...]:
    first = _run(case)
    second = _run(case)
    session, traces, eligibility_exact, authority, topology_immutable = first
    final_opportunities = tuple(item.source_id for item in available_opportunities(case.topology, session))
    expected = case.expected
    state_correct = (
        session.current_location == expected.location and session.clock.tick == expected.tick
        and session.world_state == expected.world_state and session.resources == expected.resources
        and len(session.visits) == expected.visits and final_opportunities == expected.opportunity_ids
    )
    resource_safe = all(value >= 0 for value in session.resources.values())
    replay = first[0] == second[0] and traces == second[1]
    liveness = len(traces) == len(case.actions)
    checks = (
        ("choice_eligibility_precision", eligibility_exact, "every selected action was exactly eligible"),
        ("action_authority", authority and topology_immutable, "runtime accepted only authored actions and preserved topology"),
        ("state_delta_correctness", state_correct, "final state matches the frozen oracle"),
        ("replay_determinism", replay, "same seed and actions reproduce exact state and trace"),
        ("resource_invariants", resource_safe, "resources never finish below zero"),
        ("sandbox_liveness", liveness, "the declared multi-turn sequence remains live"),
    )
    return tuple(CategoryResult(name=name, passed=passed, score=float(passed), details=details) for name, passed, details in checks)


def execute_sandbox_cases(cfg: Any, cases: Iterable[SandboxCase]) -> list[Any]:
    """Emit runtime-gate records alongside each configured model cohort."""
    records = []
    for model in cfg.models:
        for case in cases:
            categories = evaluate_sandbox_case(case)
            run = ModelRunResult(
                model_name=model, variant="json", direction="A", run_index=0,
                raw_response="", parsed_output=ModelOutput(),
                category_results=categories,
                overall_pass=all(item.passed for item in categories if item.gating),
                random_seed=str(case.seed), finish_reason="deterministic_runtime",
            )
            record = result_record_from_model_run(run)
            records.append(dataclasses.replace(
                record,
                test_id=f"{model}:{case.id}:runtime:1",
                test_version="sandbox-runtime-v1",
                capability="sandbox_runtime",
                category="sandbox_runtime",
                subcategory="deterministic_simulation",
                difficulty=case.id.split("-", 1)[0],
                dataset="sandbox_core",
                split="frozen",
                input_summary=f"{case.id}:{len(case.actions)} actions:seed {case.seed}",
                expected_behavior="deterministic authoritative runtime transition sequence",
                reference_rubric="eligibility + authority + state + replay + resources + liveness v1",
                evaluator_reasoning="pure typed simulation evaluator",
            ))
        domain_cases = load_sandbox_domain_cases()
        if cfg.benchmark_profile == "sandbox-canary":
            domain_cases = domain_cases[:1]
        for case in domain_cases:
            categories = evaluate_sandbox_domain_case(case)
            run = ModelRunResult(
                model_name=model, variant="json", direction="A", run_index=0,
                raw_response="", parsed_output=ModelOutput(), category_results=categories,
                overall_pass=all(item.passed for item in categories),
                random_seed=str(case["seed"]), finish_reason="deterministic_runtime",
            )
            records.append(dataclasses.replace(
                result_record_from_model_run(run), test_id=f"{model}:{case['id']}:runtime:1",
                test_version="sandbox-domain-v1", capability="sandbox_runtime",
                category="sandbox_runtime", subcategory=case["kind"], difficulty="SD",
                dataset="sandbox_core", split="frozen",
                input_summary=f"{case['id']}:seed {case['seed']}",
                expected_behavior="bounded deterministic domain transition",
                reference_rubric="faction + encounter + character authority v1",
                evaluator_reasoning="pure typed sandbox domain evaluator",
            ))
    return records


def load_sandbox_domain_cases() -> tuple[dict[str, Any], ...]:
    raw = json.loads(SANDBOX_DOMAIN_CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or any(
        not isinstance(item, dict) or set(item) != {"schema_version", "id", "kind", "seed"}
        or item["schema_version"] != 1 or item["kind"] not in {"faction", "encounter", "character"}
        for item in raw
    ):
        raise SandboxCaseError("invalid sandbox domain corpus")
    if len({item["id"] for item in raw}) != len(raw):
        raise SandboxCaseError("duplicate sandbox domain case id")
    return tuple(raw)


def evaluate_sandbox_domain_case(case: dict[str, Any]) -> tuple[CategoryResult, ...]:
    kind = case["kind"]
    if kind == "faction":
        initial = FactionState(faction_id="guild", influence=0.9, resources={"coin": 2})
        final = apply_faction_effect(initial, FactionEffect(faction_id="guild", operation="influence", delta=0.5))
        final = apply_faction_effect(final, FactionEffect(faction_id="guild", operation="resource", target="coin", delta=-2))
        passed = initial.influence == 0.9 and final.influence == 1 and final.resources["coin"] == 0
        name, details = "faction_state_authority", "faction bounds and resources are harness-owned"
    elif kind == "encounter":
        topology = WorldTopology(locations=(LocationNode(id="harbor", name="Harbor", region_id="coast"),))
        session = create_runtime_session(
            topology, session_id="domain_encounter", experience_profile_fingerprint=ExperienceProfile.sandbox().fingerprint(),
            start_location="harbor", time_model="turn", seed=case["seed"],
        )
        template = EncounterTemplate(
            id="market", label="Market", occurrence_limit=1,
            plan=PassagePlan(plan_id="market_plan", revision=1, passage_mode="normal", narrative_slots=(NarrativeSlot(id="body", kind="paragraph"),), choice_slots=("continue",)),
        )
        first = select_encounter(session, (template,), location=topology.locations[0])
        recorded, _ = record_encounter(session, template, first, expected_revision=1) if first else (session, None)
        passed = first is not None and select_encounter(recorded, (template,), location=topology.locations[0]) is None
        name, details = "encounter_reuse_authority", "seeded selection respects occurrence limits"
    else:
        definitions = (
            CharacterStatDefinition(id="energy", value_type="float", default=1.0, minimum=0, maximum=1, visibility="public", allowed_operations=("add",)),
            CharacterStatDefinition(id="secret", value_type="bool", default=True, visibility="private"),
        )
        initial = initialize_character("captain", "harbor", definitions)
        final = apply_character_effect(initial, definitions, CharacterEffect(operation="add", character_id="captain", target="energy", value=-0.25), expected_revision=1, tick=1)
        context = character_context(final, definitions, audience="model")
        passed = final.stats["energy"] == 0.75 and "secret" not in context["stats"] and initial.stats["energy"] == 1
        name, details = "character_state_authority", "bounded persistent state excludes private model context"
    return (CategoryResult(name=name, passed=passed, score=float(passed), details=details),)
