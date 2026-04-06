# Handoff

## Last Updated

- Date: 2026-04-06
- Updated by: Codex

## Repo Role

- This is the OpenAI-main local work agent repository.
- It was forked logically from `local-content-agent`, but it is now a separate repo with a different owner role.
- Primary purpose: generic local task execution with Ollama/Gemma.

## Current State

- Generic runtime added under `agent_runtime/`
- New entry commands:
  - `python main.py models`
  - `python main.py workers`
  - `python main.py task-init`
  - `python main.py task <task.json>`
- Example tasks added under `examples/tasks/`
- Legacy content automation is still available for compatibility

## Expected Model Setup

- fast: `gemma4:e2b`
- quality: `gemma4:26b`
- fallback logic is still handled in `writer/ollama_client.py`

## Run Checklist

```bash
cd ~/github/openai-local-work-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml
python main.py models
python main.py task-init
python main.py task examples/tasks/research_physical_ai.json
```

## Next Useful Work

1. Add more worker types if needed
2. Add project-specific task templates
3. Separate legacy content features into optional modules if the repo should become fully generic
4. Add tests around task loading and artifact writing

## Constraints

- Do not commit secrets or filled `config.yaml`
- Prefer local-only execution paths
- Keep the OpenAI-main identity clear in docs and naming

