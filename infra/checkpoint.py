"""
Lightweight JSON checkpointing for minimal runtime state.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict


DEFAULT_PATH = "checkpoint.json"


def load_checkpoint(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_checkpoint(data: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp_path, path)

