from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent_runtime.config import REPO_ROOT
from agent_runtime.tasks import TaskSpec
from agent_runtime.workers import build_worker


RUNS_DIR = REPO_ROOT / "runs"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def execute_task(task: TaskSpec) -> dict:
    worker = build_worker(task.task_type)
    result = worker.run(task)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    artifact_rel = task.artifact_path or f"{run_id}-{task.task_type}.md"
    artifact_path = ARTIFACTS_DIR / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(result.content, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "task_type": task.task_type,
        "title": task.title,
        "worker": result.worker_name,
        "artifact_path": str(artifact_path),
    }
    (run_dir / "task.json").write_text(
        json.dumps(
            {
                "type": task.task_type,
                "title": task.title,
                "objective": task.objective,
                "context": task.context,
                "constraints": task.constraints,
                "output_format": task.output_format,
                "artifact_path": task.artifact_path,
                "model": task.model,
                "metadata": task.metadata,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary

