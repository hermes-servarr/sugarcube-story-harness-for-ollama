import pytest

from harness.ollama_client import OllamaGenerationResult
from model_benchmark.config import BenchmarkConfig
from model_benchmark.context_window_tests import (
    build_context_probe_prompt,
    execute_context_window_tests,
    validate_context_sizes,
)


def _config() -> BenchmarkConfig:
    return BenchmarkConfig(
        models=("private-model",),
        variants=("compact",),
        directions=("A",),
        base_url="http://127.0.0.1:11434",
        timeout=30,
        num_predict=640,
        temperature=0.2,
        runs=1,
        random_seed="42",
    )


def test_context_ladder_is_bounded_sorted_and_prompt_grows():
    assert validate_context_sizes([2048, 4096, 8192]) == (2048, 4096, 8192)
    with pytest.raises(ValueError, match="sorted and unique"):
        validate_context_sizes([4096, 2048])
    with pytest.raises(ValueError, match="outside the signed ladder"):
        validate_context_sizes([131072])

    small = build_context_probe_prompt(2048)
    large = build_context_probe_prompt(8192)
    assert len(small) < len(large)
    for marker in ("EMBER-271", "GLASS-593", "HARBOR-847"):
        assert marker in small
        assert marker in large


def test_context_probe_records_acceptance_retrieval_tokens_and_progress(monkeypatch):
    captured = {}

    def fake_call(config, prompt, **kwargs):
        captured["num_ctx"] = config.num_ctx
        captured["model_mode"] = config.model_mode
        captured["num_predict"] = kwargs["num_predict"]
        return OllamaGenerationResult(
            response="EMBER-271 GLASS-593 HARBOR-847",
            prompt_eval_count=1990,
            eval_count=9,
            done_reason="stop",
        )

    monkeypatch.setattr(
        "model_benchmark.context_window_tests.call_ollama_sync_detailed",
        fake_call,
    )
    progress = []
    record = execute_context_window_tests(
        _config(),
        [2048],
        progress_callback=lambda completed, total, model: progress.append(
            (completed, total, model)
        ),
    )[0]

    assert captured == {"num_ctx": 2048, "model_mode": "full", "num_predict": 32}
    assert progress == [(1, 1, "private-model")]
    assert record.status == "PASS"
    assert record.dataset == "capability_context_window"
    assert record.split == "num_ctx_2048"
    assert record.input_tokens == 1990
    assert record.output_tokens == 9
    assert record.total_tokens == 1999


def test_context_probe_preserves_api_failure_as_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("context allocation rejected")

    monkeypatch.setattr(
        "model_benchmark.context_window_tests.call_ollama_sync_detailed",
        fail,
    )
    record = execute_context_window_tests(_config(), [2048])[0]

    assert record.status == "ERROR"
    assert record.failure_category == "internal_exception"
