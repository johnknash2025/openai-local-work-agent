from __future__ import annotations

from dataclasses import dataclass, field

from creator_runtime.persona import Persona
from writer.ollama_client import chat as ollama_chat


@dataclass
class ConversationState:
    persona: Persona
    history: list[dict[str, str]] = field(default_factory=list)


def build_prompt(user_message: str, history: list[dict[str, str]]) -> str:
    lines = []
    for item in history[-8:]:
        lines.append(f"{item['role'].upper()}: {item['content']}")
    lines.append(f"USER: {user_message}")
    lines.append("ASSISTANT:")
    return "\n".join(lines)


def reply(state: ConversationState, user_message: str, model: str = "fast") -> str:
    prompt = build_prompt(user_message, state.history)
    output = ollama_chat(
        prompt=prompt,
        model=model,
        system=state.persona.system_prompt,
    ).strip()
    state.history.append({"role": "user", "content": user_message})
    state.history.append({"role": "assistant", "content": output})
    return output

