from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
CONFIG_EXAMPLE_PATH = REPO_ROOT / "config.yaml.example"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if CONFIG_EXAMPLE_PATH.exists():
        return yaml.safe_load(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8")) or {}
    return {}

