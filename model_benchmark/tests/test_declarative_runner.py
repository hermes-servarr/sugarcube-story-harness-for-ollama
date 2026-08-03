from harness.ollama_client import OllamaGenerationResult
from model_benchmark.config import BenchmarkConfig
from model_benchmark.config_loader import ResolvedTestSpec
from model_benchmark.config_schema import TestConfig
from model_benchmark.declarative_runner import execute_declarative_tests
from model_benchmark.test_selection import ExpandedTestInstance


def test_declarative_result_records_generation_metadata(monkeypatch):
    config = TestConfig(
        id="metadata-case",
        input="Write a valid passage.",
        category="passage_structure",
        scoring_categories=["passage_structure"],
    )
    instance = ExpandedTestInstance(
        instance_id="metadata-case",
        source_id="metadata-case",
        spec=ResolvedTestSpec(config=config),
    )
    benchmark = BenchmarkConfig(
        models=("test-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
    )
    response = (
        "PROSE:\nText.\n"
        "CHOICES:\n- Continue | Move on\n"
        "SUMMARY:\nDone."
    )
    monkeypatch.setattr(
        "model_benchmark.declarative_runner.call_ollama_sync_detailed",
        lambda *args, **kwargs: OllamaGenerationResult(
            response=response,
            prompt_eval_count=75,
            eval_count=25,
            done_reason="stop",
        ),
    )

    record = execute_declarative_tests(
        [instance],
        benchmark,
        run_id="test-run",
    )[0]

    assert record.input_tokens == 75
    assert record.output_tokens == 25
    assert record.total_tokens == 100
    assert record.finish_reason == "stop"
