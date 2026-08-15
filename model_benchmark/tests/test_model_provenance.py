import io
import json

from model_benchmark.metadata import collect_ollama_metadata


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_ollama_metadata_records_exact_digest_quantization_and_version(monkeypatch):
    payloads = {
        "/api/tags": {"models": [{
            "name": "fixture:latest", "digest": "a" * 64,
            "details": {"quantization_level": "Q4_K_M", "family": "fixture", "parameter_size": "9B", "context_length": 32768},
        }]},
        "/api/version": {"version": "1.2.3"},
    }

    def fake_open(url, timeout):
        path = "/" + url.split("/", 3)[-1]
        return _Response(json.dumps(payloads[path]).encode())

    monkeypatch.setattr("model_benchmark.metadata.urllib.request.urlopen", fake_open)

    configs, version = collect_ollama_metadata("http://ollama", ("fixture:latest",))

    assert configs[0]["digest"] == "a" * 64
    assert configs[0]["quantization"] == "Q4_K_M"
    assert configs[0]["context_length"] == "32768"
    assert version == "1.2.3"


def test_ollama_metadata_failure_is_explicit(monkeypatch):
    monkeypatch.setattr("model_benchmark.metadata.urllib.request.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))

    configs, version = collect_ollama_metadata("http://offline", ("fixture:latest",))

    assert configs == ({"model": "fixture:latest", "digest": "unknown"},)
    assert version == "unknown"
