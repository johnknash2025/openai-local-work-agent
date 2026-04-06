from __future__ import annotations

from dataclasses import dataclass

import httpx

from agent_runtime.config import load_config
from writer.ollama_client import chat


@dataclass
class ModelProfile:
    fast: str
    quality: str


def get_model_profile() -> ModelProfile:
    config = load_config()
    ollama = config.get("ollama", {})
    return ModelProfile(
        fast=ollama.get("model_fast", "gemma4:e2b"),
        quality=ollama.get("model_quality", "gemma4:26b"),
    )


def list_models() -> list[str]:
    config = load_config()
    base_url = config.get("ollama", {}).get("base_url", "http://localhost:11434")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=10)
        response.raise_for_status()
    except Exception:
        return []
    return [item.get("name", "") for item in response.json().get("models", []) if item.get("name")]


def ask_local_llm(prompt: str, *, quality: bool = True, system: str = "") -> str:
    profile = get_model_profile()
    model = profile.quality if quality else profile.fast
    return chat(prompt=prompt, model=model, system=system)

