"""CLI configuration — reads/writes ~/.cawnex/config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".cawnex"
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict[str, Any]) -> None:
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set_key(key: str, value: Any) -> None:
    config = load_config()
    config[key] = value
    save_config(config)


def is_setup_complete() -> bool:
    config = load_config()
    return bool(
        config.get("fernet_key")
        and config.get("database_url")
        and config.get("redis_url")
    )
