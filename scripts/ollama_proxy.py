"""Ollama-to-OpenAI compatibility proxy.

The sugarcube harness talks to Ollama's /api/generate and /api/tags endpoints.
This proxy translates those calls to an OpenAI-compatible chat completions API,
so the harness can use any OpenAI-compatible endpoint (e.g. NTNU IDUN) without
modifying harness source code.

Run:  python3 scripts/ollama_proxy.py --port 11434

Environment:
  OPENAI_BASE_URL  - e.g. https://llm.hpc.ntnu.no/v1
  OPENAI_API_KEY   - e.g. sk-...
  OPENAI_MODEL     - e.g. mistralai/Mistral-Medium-3.5-128B
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI(title="Ollama-OpenAI Proxy")

# Populated from CLI args / env at startup.
PROXY_CONFIG: dict[str, str] = {}


def _get_base_url() -> str:
    return PROXY_CONFIG["base_url"].rstrip("/")


def _get_api_key() -> str:
    return PROXY_CONFIG["api_key"]


def _get_default_model() -> str:
    return PROXY_CONFIG["model"]


@app.get("/api/tags")
async def ollama_tags():
    """Return a fake Ollama /api/tags response listing the configured model."""
    model = _get_default_model()
    return JSONResponse({
        "models": [
            {
                "name": model,
                "model": model,
                "size": 0,
                "digest": "proxy",
                "modified_at": "",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": "proxy",
                    "families": [],
                    "parameter_size": "unknown",
                    "quantization_level": "unknown",
                },
            }
        ],
    })


@app.get("/api/version")
async def ollama_version():
    return JSONResponse({"version": "0.1.0-proxy"})


@app.post("/api/generate")
async def ollama_generate(request: Request):
    """Translate Ollama /api/generate to OpenAI /chat/completions.

    Ollama generate payload: {model, prompt, stream, options: {temperature, ...}}
    OpenAI chat payload:   {model, messages: [{role, content}], stream, temperature}
    """
    body = await request.json()
    model = body.get("model") or _get_default_model()
    prompt = body.get("prompt", "")
    stream = body.get("stream", False)
    options = body.get("options", {})

    temperature = options.get("temperature", 0.8)
    num_predict = options.get("num_predict", -1)
    seed = options.get("seed")

    # Translate Ollama system-style prompt to chat messages.
    # The harness sends prompts that may contain structured sections.
    # We send the whole prompt as a single user message.
    messages = [{"role": "user", "content": prompt}]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,  # always non-streaming, then we synthesize Ollama response
    }
    if num_predict and num_predict > 0:
        payload["max_tokens"] = num_predict
    if seed is not None:
        payload["seed"] = seed

    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        try:
            r = await client.post(
                f"{_get_base_url()}/chat/completions",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            return JSONResponse(
                {"error": str(e), "detail": e.response.text[:500]},
                status_code=e.response.status_code,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    # Extract the generated text from the OpenAI response.
    generated_text = ""
    if data.get("choices"):
        generated_text = data["choices"][0].get("message", {}).get("content", "")

    if stream:
        # Synthesize a simple Ollama-style stream (single chunk + done)
        async def gen():
            yield json.dumps({
                "model": model,
                "response": generated_text,
                "done": True,
            }) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # Non-streaming Ollama response shape
    return JSONResponse({
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "response": generated_text,
        "done": True,
        "context": [],
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
        "prompt_eval_duration": 0,
        "eval_count": 0,
        "eval_duration": 0,
    })


@app.post("/api/chat")
async def ollama_chat(request: Request):
    """Translate Ollama /api/chat to OpenAI /chat/completions."""
    body = await request.json()
    model = body.get("model") or _get_default_model()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    options = body.get("options", {})
    temperature = options.get("temperature", 0.8)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        try:
            r = await client.post(
                f"{_get_base_url()}/chat/completions",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            return JSONResponse(
                {"error": str(e), "detail": e.response.text[:500]},
                status_code=e.response.status_code,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    generated_text = ""
    if data.get("choices"):
        generated_text = data["choices"][0].get("message", {}).get("content", "")

    return JSONResponse({
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": {"role": "assistant", "content": generated_text},
        "done": True,
    })


def main():
    parser = argparse.ArgumentParser(description="Ollama-to-OpenAI proxy")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", ""))
    args = parser.parse_args()

    if not args.base_url or not args.api_key or not args.model:
        print("Error: --base-url, --api-key, and --model are required")
        print("Set via flags or env vars: OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL")
        sys.exit(1)

    global PROXY_CONFIG
    PROXY_CONFIG = {
        "base_url": args.base_url,
        "api_key": args.api_key,
        "model": args.model,
    }

    print(f"Proxy: Ollama API on {args.host}:{args.port} -> OpenAI at {args.base_url}")
    print(f"Model: {args.model}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
