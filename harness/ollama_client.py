"""Thin HTTP client + sampling/profile policy for Ollama's /api/generate.

Only the transport and model-profile concerns live here. Prompt assembly is in
``generators``; output parsing is in ``parsers``.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import time

import httpx

from .ingestion_profiles import render_ingestion
from .models import HarnessConfig


# ── Debug call log ────────────────────────────────────────────────────────────
# Ring buffer of recent Ollama generation calls so the UI can show exactly which
# model + prompt variant + options served each call. In-memory only (resets on
# server restart); newest first.

_CALL_LOG: deque = deque(maxlen=50)


def record_call(entry: dict) -> None:
    _CALL_LOG.appendleft(entry)


def get_call_log() -> list[dict]:
    return list(_CALL_LOG)


def clear_call_log() -> None:
    _CALL_LOG.clear()


def _compact_mode(cfg: HarnessConfig) -> bool:
    profile = model_profile(cfg.ollama_model)
    return (
        cfg.model_mode == "compact"
        or (cfg.model_mode == "auto" and profile.use_compact_prompt)
    )


def _log_call(
    cfg: HarnessConfig, payload: dict, label: str, format_spec,
    *, status: str, ms: int, detail: str = "",
) -> None:
    opts = payload.get("options", {})
    record_call({
        "ts": datetime.now(timezone.utc).isoformat(),
        "label": label or "(generation)",
        "model": payload.get("model", cfg.ollama_model),
        "variant": "json" if format_spec is not None else ("compact" if _compact_mode(cfg) else "full"),
        "model_mode": cfg.model_mode,
        "profile": model_profile(cfg.ollama_model).name,
        "num_ctx": opts.get("num_ctx"),
        "num_predict": opts.get("num_predict"),
        "temperature": opts.get("temperature"),
        "prompt_chars": len(payload.get("prompt", "")),
        "status": status,
        "ms": ms,
        "detail": detail[:200],
    })


# ── Small/medium-model detection ─────────────────────────────────────────────

_SMALL_MODEL_RE = re.compile(
    r'(?:tinyllama|smollm|llama3\.2:(?:1b|3b)|mini|tiny|small)',
    re.IGNORECASE,
)
_PARAM_B_RE = re.compile(r'(?<!\d)(\d+(?:\.\d+)?)\s*b\b', re.IGNORECASE)


@dataclass(frozen=True)
class ModelProfile:
    name: str
    use_compact_prompt: bool
    num_ctx_cap: int
    num_predict_cap: int
    temperature_cap: float
    repeat_penalty_floor: float
    top_k: int
    top_p: float
    premise_chars: int
    story_points_chars: int
    arc_chars: int
    snapshot_chars: int
    parent_chars: int
    entities_chars: int
    inspiration_chars: int


@dataclass(frozen=True)
class OllamaGenerationResult:
    """Generated text plus tokenizer/runtime counters returned by Ollama."""

    response: str
    prompt_eval_count: int = 0
    eval_count: int = 0
    done_reason: str = ""


def _is_small_model(model_name: str) -> bool:
    return bool(_SMALL_MODEL_RE.search(model_name))


def _model_param_billions(model_name: str) -> float | None:
    m = _PARAM_B_RE.search(model_name)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def model_profile(model_name: str) -> ModelProfile:
    """Pick a tuning profile based on parameter count + family hints."""
    low = (model_name or "").lower()
    size_b = _model_param_billions(low)
    likely_medium_family = bool(re.search(r'(?:mistral|gemma|phi|qwen|llama3)', low))

    if _is_small_model(low) or (size_b is not None and size_b <= 4.5):
        return ModelProfile(
            name="small",
            use_compact_prompt=True,
            num_ctx_cap=3072,
            num_predict_cap=420,
            temperature_cap=0.55,
            repeat_penalty_floor=1.18,
            top_k=30,
            top_p=0.88,
            premise_chars=320,
            story_points_chars=180,
            arc_chars=160,
            snapshot_chars=220,
            parent_chars=700,
            entities_chars=220,
            inspiration_chars=450,
        )

    if (size_b is not None and size_b <= 12.5) or (size_b is None and likely_medium_family):
        return ModelProfile(
            name="medium",
            use_compact_prompt=True,
            num_ctx_cap=4096,
            num_predict_cap=640,
            temperature_cap=0.65,
            repeat_penalty_floor=1.13,
            top_k=40,
            top_p=0.90,
            premise_chars=420,
            story_points_chars=260,
            arc_chars=240,
            snapshot_chars=320,
            parent_chars=1000,
            entities_chars=340,
            inspiration_chars=700,
        )

    return ModelProfile(
        name="large",
        use_compact_prompt=False,
        num_ctx_cap=6144,
        num_predict_cap=1024,
        temperature_cap=0.75,
        repeat_penalty_floor=1.10,
        top_k=50,
        top_p=0.92,
        premise_chars=800,
        story_points_chars=500,
        arc_chars=500,
        snapshot_chars=800,
        parent_chars=2000,
        entities_chars=1600,
        inspiration_chars=1800,
    )


# ── Payload + transport ──────────────────────────────────────────────────────

def _raise_if_missing(resp: httpx.Response, model: str) -> None:
    if resp.status_code == 404:
        body = ""
        try:
            body = resp.json().get("error", "")
        except Exception:
            body = resp.text[:200]
        raise RuntimeError(
            f"Model {model!r} not found on Ollama. "
            f"Run: ollama pull {model}"
            + (f" ({body})" if body else "")
        )


def _ollama_payload(
    cfg: HarnessConfig,
    prompt: str,
    *,
    temperature_override: float | None = None,
    num_predict_override: int | None = None,
    format_spec: str | dict | None = None,
    ingestion_profile: str = "",
    seed_override: int | None = None,
) -> dict:
    profile = model_profile(cfg.ollama_model)
    compact_mode = (
        cfg.model_mode == "compact"
        or (cfg.model_mode == "auto" and profile.use_compact_prompt)
    )
    num_ctx = min(cfg.num_ctx, profile.num_ctx_cap) if compact_mode else cfg.num_ctx
    num_predict = min(cfg.num_predict, profile.num_predict_cap) if compact_mode else cfg.num_predict
    if num_predict_override is not None:
        num_predict = max(1, num_predict_override)
    base_temp = cfg.temperature if temperature_override is None else temperature_override
    # Profile cap still applies in compact mode to keep small models stable.
    temperature = min(base_temp, profile.temperature_cap) if compact_mode else base_temp
    repeat_penalty = max(cfg.repeat_penalty, profile.repeat_penalty_floor) if compact_mode else cfg.repeat_penalty

    payload: dict = {
        "model": cfg.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "repeat_penalty": repeat_penalty,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "top_k": profile.top_k,
            "top_p": profile.top_p,
            # Terminal markers some models emit. Avoid stop on section headers —
            # that would truncate the section's content before it starts.
            "stop": ["<|endoftext|>", "<|im_end|>", "<|eot_id|>"],
        },
    }
    selected_ingestion_profile = (
        ingestion_profile
        or getattr(cfg, "ingestion_profile", "")
    )
    if selected_ingestion_profile:
        rendered = render_ingestion(selected_ingestion_profile, prompt)
        payload["prompt"] = rendered.prompt
        if rendered.raw:
            payload["raw"] = True
        for marker in rendered.stop:
            if marker not in payload["options"]["stop"]:
                payload["options"]["stop"].append(marker)
    if format_spec is not None:
        payload["format"] = format_spec
    if seed_override is not None:
        payload["options"]["seed"] = max(0, int(seed_override))
    return payload


async def call_ollama(
    cfg: HarnessConfig,
    prompt: str,
    timeout: float = 120.0,
    *,
    temperature: float | None = None,
    num_predict: int | None = None,
    format_spec: str | dict | None = None,
    label: str = "",
    ingestion_profile: str = "",
    seed: int | None = None,
) -> str:
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    payload = _ollama_payload(
        cfg, prompt,
        temperature_override=temperature,
        num_predict_override=num_predict,
        format_spec=format_spec,
        ingestion_profile=ingestion_profile,
        seed_override=seed,
    )
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            _raise_if_missing(resp, cfg.ollama_model)
            resp.raise_for_status()
            out = resp.json().get("response", "")
        _log_call(cfg, payload, label, format_spec,
                  status="ok", ms=int((time.monotonic() - t0) * 1000))
        return out
    except Exception as e:
        _log_call(cfg, payload, label, format_spec,
                  status="error", ms=int((time.monotonic() - t0) * 1000), detail=str(e))
        raise


def call_ollama_sync(
    cfg: HarnessConfig,
    prompt: str,
    timeout: float = 120.0,
    *,
    temperature: float | None = None,
    num_predict: int | None = None,
    format_spec: str | dict | None = None,
    label: str = "",
    ingestion_profile: str = "",
    seed: int | None = None,
) -> str:
    """Sync variant for CLI / non-async callers."""
    return call_ollama_sync_detailed(
        cfg,
        prompt,
        timeout,
        temperature=temperature,
        num_predict=num_predict,
        format_spec=format_spec,
        label=label,
        ingestion_profile=ingestion_profile,
        seed=seed,
    ).response


def call_ollama_sync_detailed(
    cfg: HarnessConfig,
    prompt: str,
    timeout: float = 120.0,
    *,
    temperature: float | None = None,
    num_predict: int | None = None,
    format_spec: str | dict | None = None,
    label: str = "",
    ingestion_profile: str = "",
    seed: int | None = None,
) -> OllamaGenerationResult:
    """Sync generation retaining Ollama's actual token counters."""
    url = f"{cfg.ollama_base_url.rstrip('/')}/api/generate"
    payload = _ollama_payload(
        cfg, prompt,
        temperature_override=temperature,
        num_predict_override=num_predict,
        format_spec=format_spec,
        ingestion_profile=ingestion_profile,
        seed_override=seed,
    )
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            _raise_if_missing(resp, cfg.ollama_model)
            resp.raise_for_status()
            data = resp.json()
            result = OllamaGenerationResult(
                response=str(data.get("response", "")),
                prompt_eval_count=max(0, int(data.get("prompt_eval_count", 0) or 0)),
                eval_count=max(0, int(data.get("eval_count", 0) or 0)),
                done_reason=str(data.get("done_reason", "") or ""),
            )
        _log_call(cfg, payload, label, format_spec,
                  status="ok", ms=int((time.monotonic() - t0) * 1000))
        return result
    except Exception as e:
        _log_call(cfg, payload, label, format_spec,
                  status="error", ms=int((time.monotonic() - t0) * 1000), detail=str(e))
        raise
