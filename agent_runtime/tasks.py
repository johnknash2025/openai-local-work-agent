from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskSpec:
    task_type: str
    title: str
    objective: str
    context: str = ""
    constraints: list[str] = field(default_factory=list)
    output_format: str = "markdown"
    artifact_path: str = ""
    model: str = "quality"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        return cls(
            task_type=data["type"],
            title=data["title"],
            objective=data["objective"],
            context=data.get("context", ""),
            constraints=list(data.get("constraints", [])),
            output_format=data.get("output_format", "markdown"),
            artifact_path=data.get("artifact_path", ""),
            model=data.get("model", "quality"),
            metadata=dict(data.get("metadata", {})),
        )


def load_task(path: Path) -> TaskSpec:
    return TaskSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))

