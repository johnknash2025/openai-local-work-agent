from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.llm import ask_local_llm
from agent_runtime.tasks import TaskSpec


SYSTEM_BASE = (
    "You are a local work agent. Be concrete, operational, and honest about uncertainty. "
    "Prefer structured outputs, explicit assumptions, and actionable next steps."
)


@dataclass
class WorkerResult:
    worker_name: str
    content: str


class BaseWorker:
    worker_name = "base"

    def build_prompt(self, task: TaskSpec) -> str:
        raise NotImplementedError

    def run(self, task: TaskSpec) -> WorkerResult:
        use_quality = task.model != "fast"
        content = ask_local_llm(
            self.build_prompt(task),
            quality=use_quality,
            system=SYSTEM_BASE,
        )
        return WorkerResult(worker_name=self.worker_name, content=content)


class ResearchWorker(BaseWorker):
    worker_name = "research"

    def build_prompt(self, task: TaskSpec) -> str:
        constraints = "\n".join(f"- {item}" for item in task.constraints) or "- None"
        return (
            f"Prepare a research memo.\n\n"
            f"Title: {task.title}\n"
            f"Objective: {task.objective}\n"
            f"Context: {task.context or 'None'}\n"
            f"Constraints:\n{constraints}\n\n"
            "Output sections:\n"
            "1. Executive summary\n"
            "2. What is known\n"
            "3. Risks and unknowns\n"
            "4. Suggested experiments\n"
            "5. Next actions\n"
        )


class WritingWorker(BaseWorker):
    worker_name = "writing"

    def build_prompt(self, task: TaskSpec) -> str:
        constraints = "\n".join(f"- {item}" for item in task.constraints) or "- None"
        return (
            f"Draft a deliverable.\n\n"
            f"Title: {task.title}\n"
            f"Objective: {task.objective}\n"
            f"Context: {task.context or 'None'}\n"
            f"Constraints:\n{constraints}\n\n"
            "Write in a way that can be handed to an engineer or operator. "
            "Use headings, compact bullets when useful, and keep the output immediately usable."
        )


class OpsWorker(BaseWorker):
    worker_name = "ops"

    def build_prompt(self, task: TaskSpec) -> str:
        constraints = "\n".join(f"- {item}" for item in task.constraints) or "- None"
        return (
            f"Produce an operations checklist or runbook.\n\n"
            f"Title: {task.title}\n"
            f"Objective: {task.objective}\n"
            f"Context: {task.context or 'None'}\n"
            f"Constraints:\n{constraints}\n\n"
            "Output sections:\n"
            "1. Goal\n"
            "2. Preconditions\n"
            "3. Steps\n"
            "4. Validation\n"
            "5. Failure recovery\n"
        )


def build_worker(task_type: str) -> BaseWorker:
    mapping = {
        "research": ResearchWorker,
        "writing": WritingWorker,
        "ops": OpsWorker,
    }
    worker_cls = mapping.get(task_type)
    if not worker_cls:
        raise ValueError(f"Unsupported task type: {task_type}")
    return worker_cls()

