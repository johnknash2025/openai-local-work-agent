# Workflow

## Operating Rules

1. Treat this repo as the OpenAI-main implementation.
2. Use `task` execution as the default interface.
3. Keep local model assumptions explicit in docs.
4. Write outputs to `artifacts/` and execution metadata to `runs/`.
5. Keep legacy content automation working, but do not let it define the repo identity.

## Change Discipline

1. Update `HANDOFF.md` when changing the main operating model.
2. Add example tasks when introducing a new worker style.
3. Do not commit generated artifacts unless explicitly requested.
