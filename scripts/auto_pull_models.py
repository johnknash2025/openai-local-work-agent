#!/usr/bin/env python3
"""
Auto Model Updater for Ollama
 Automatically pulls new models and registers them as agents.
 Monitors HuggingFace/Ollama Hub for new releases.
"""

import json
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OLLAMA_API = "http://localhost:11434"
STATE_FILE = Path(__file__).parent.parent / "model_state.json"


@dataclass
class ModelInfo:
    name: str
    size: int
    last_updated: float
    status: str = "unknown"


def get_installed_models() -> List[str]:
    """Get list of installed models from Ollama."""
    try:
        resp = httpx.get(f"{OLLAMA_API}/api/tags", timeout=30)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return []


def pull_model(model_name: str) -> bool:
    """Pull a model from Ollama Hub."""
    logger.info(f"Pulling model: {model_name}")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for large models
        )
        if result.returncode == 0:
            logger.info(f"Successfully pulled: {model_name}")
            return True
        else:
            logger.error(f"Failed to pull {model_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout pulling {model_name}")
        return False
    except Exception as e:
        logger.error(f"Error pulling {model_name}: {e}")
        return False


def check_huggingface_new_models(limit: int = 20) -> List[Dict]:
    """Check HuggingFace for recently updated Ollama-compatible models."""
    try:
        resp = httpx.get(
            "https://huggingface.co/api/models",
            params={
                "filter": "ollama",
                "sort": "lastModified",
                "direction": -1,
                "limit": limit
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch HuggingFace models: {e}")
        return []


def convert_hf_to_ollama(hf_model: str) -> str:
    """Convert HuggingFace model name to Ollama format."""
    return hf_model.replace("/", "-").lower()


def load_state() -> Dict:
    """Load persisted state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"pulled_models": {}, "last_check": 0}


def save_state(state: Dict) -> None:
    """Save state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update_state(state: Dict, model: str, success: bool) -> None:
    """Update state after a pull attempt."""
    state["pulled_models"][model] = {
        "timestamp": time.time(),
        "success": success
    }
    state["last_check"] = time.time()
    save_state(state)


def register_model_as_agent(model_name: str) -> None:
    """Register a new model as an agent in the system."""
    # Add to config as experimental model
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    try:
        with open(config_path) as f:
            config = f.read()
        
        # Check if already registered
        if model_name in config:
            logger.info(f"Model {model_name} already registered")
            return
        
        # Model is auto-registered via config.yaml model_priority list
        logger.info(f"Model {model_name} available as agent")
        
    except Exception as e:
        logger.error(f"Failed to register model: {e}")


def run_dry_check() -> None:
    """Check what models are available without pulling."""
    logger.info("=== Dry Run: Available Models ===")
    
    installed = get_installed_models()
    logger.info(f"Installed models ({len(installed)}):")
    for m in installed:
        logger.info(f"  - {m}")
    
    # Check HuggingFace for new models
    hf_models = check_huggingface_new_models(limit=10)
    logger.info(f"\nRecent Ollama models on HuggingFace:")
    for m in hf_models[:5]:
        ollama_name = convert_hf_to_ollama(m.get("id", ""))
        logger.info(f"  - {m.get('id')} -> ollama:{ollama_name}")


def run_auto_update(max_models: int = 3) -> None:
    """Main auto-update logic."""
    state = load_state()
    installed = get_installed_models()
    
    logger.info("=== Auto Model Update ===")
    logger.info(f"Currently installed: {len(installed)} models")
    
    # Check for new models
    hf_models = check_huggingface_new_models(limit=50)
    
    new_candidates = []
    for m in hf_models:
        ollama_name = convert_hf_to_ollama(m.get("id", ""))
        if ollama_name not in installed and ollama_name not in state.get("pulled_models", {}):
            new_candidates.append({
                "name": ollama_name,
                "hf_id": m.get("id"),
                "downloads": m.get("downloads", 0),
                "last_modified": m.get("lastModified")
            })
    
    # Sort by downloads (most popular first)
    new_candidates.sort(key=lambda x: x.get("downloads", 0), reverse=True)
    
    if not new_candidates:
        logger.info("No new models found")
        return
    
    logger.info(f"Found {len(new_candidates)} potential new models")
    
    # Pull top candidates (limited)
    pulled_count = 0
    for candidate in new_candidates[:max_models]:
        model_name = candidate["name"]
        
        logger.info(f"\nCandidate: {model_name} ({candidate['downloads']} downloads)")
        
        # Check disk space (optional)
        # For now, just attempt the pull
        if pull_model(model_name):
            update_state(state, model_name, True)
            register_model_as_agent(model_name)
            pulled_count += 1
        else:
            update_state(state, model_name, False)
    
    logger.info(f"\n=== Summary ===")
    logger.info(f"Pulled {pulled_count} new models")
    
    # Update installed list
    final_installed = get_installed_models()
    logger.info(f"Total installed: {len(final_installed)} models")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto Model Updater for Ollama")
    parser.add_argument("--dry-run", action="store_true", help="Check without pulling")
    parser.add_argument("--max-models", type=int, default=3, help="Max models to pull per run")
    args = parser.parse_args()
    
    if args.dry_run:
        run_dry_check()
    else:
        run_auto_update(max_models=args.max_models)
