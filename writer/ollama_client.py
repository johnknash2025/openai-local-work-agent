"""Ollama API client shared by legacy content flows and the generic runtime."""
import json
from typing import Generator

import httpx

from agent_runtime.config import load_config

CONFIG = load_config()
OLLAMA_URL = CONFIG.get("ollama", {}).get("base_url", "http://localhost:11434")
DEFAULT_TEMPERATURE = CONFIG.get("ollama", {}).get("temperature", 0.7)


def _resolve_model(model: str) -> str:
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=30)
        resp.raise_for_status()
        available = [item.get("name", "") for item in resp.json().get("models", []) if item.get("name")]
    except Exception:
        return model

    if model in available:
        return model

    quality_model = CONFIG.get("ollama", {}).get("model_quality")
    if quality_model in available:
        return quality_model

    fast_model = CONFIG.get("ollama", {}).get("model_fast")
    if fast_model in available:
        return fast_model

    return available[0] if available else model

def chat(prompt: str, model: str, system: str = "", stream: bool = False) -> str:
    model = _resolve_model(model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": DEFAULT_TEMPERATURE},
    }
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        timeout=300,
    )
    if resp.status_code == 404:
        prompt_text = "\n\n".join(
            part["content"] for part in messages if part["content"]
        )
        fallback_resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt_text,
                "stream": False,
                "options": {"temperature": DEFAULT_TEMPERATURE},
            },
            timeout=300,
        )
        fallback_resp.raise_for_status()
        return fallback_resp.json()["response"]

    resp.raise_for_status()
    return resp.json()["message"]["content"]

def stream_chat(prompt: str, model: str, system: str = "") -> Generator[str, None, None]:
    model = _resolve_model(model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": DEFAULT_TEMPERATURE},
    }
    with httpx.stream(
        "POST",
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        timeout=300,
    ) as resp:
        if resp.status_code == 404:
            prompt_text = "\n\n".join(
                part["content"] for part in messages if part["content"]
            )
            with httpx.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt_text,
                    "stream": True,
                    "options": {"temperature": DEFAULT_TEMPERATURE},
                },
                timeout=300,
            ) as fallback_resp:
                for line in fallback_resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        if not data.get("done"):
                            yield data.get("response", "")
            return

        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                if not data.get("done"):
                    yield data["message"]["content"]
