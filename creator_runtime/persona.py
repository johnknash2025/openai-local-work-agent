from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from agent_runtime.config import REPO_ROOT


PERSONAS_DIR = REPO_ROOT / "personas"


@dataclass
class Persona:
    name: str
    tagline: str
    style: str
    audience: str
    topics: list[str]
    system_prompt: str
    first_message: str


def list_personas() -> list[Path]:
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(PERSONAS_DIR.glob("*.json"))


def load_persona(name: str) -> Persona:
    path = PERSONAS_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Persona(**data)


def save_persona(persona: Persona) -> Path:
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    path = PERSONAS_DIR / f"{persona.name}.json"
    path.write_text(json.dumps(asdict(persona), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ensure_default_persona() -> Path:
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    path = PERSONAS_DIR / "lab_vtuber.json"
    if path.exists():
        return path
    persona = Persona(
        name="lab_vtuber",
        tagline="Local-first physical AI host",
        style="Calm, sharp, technical, a little playful, never fake hype.",
        audience="Engineers, builders, and curious technical founders.",
        topics=[
            "physical AI",
            "robotics simulation",
            "Isaac Sim",
            "Genesis",
            "local GPU workflows",
            "AI creator experiments"
        ],
        system_prompt=(
            "You are Lab VTuber, a local-first AI creator persona. "
            "Speak like a technically credible host who enjoys explaining robotics, physical AI, "
            "simulation, and practical experiments. Avoid fake confidence, separate verified facts "
            "from ideas, and keep answers concise but vivid. Ask a short follow-up question when helpful."
        ),
        first_message="Hi, I'm Lab VTuber. Ask me about physical AI, local agents, or what we should build next.",
    )
    return save_persona(persona)

