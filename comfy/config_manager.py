"""Configuration manager for ComfyUI enhancer settings."""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Callable, Any, List


DEFAULT_WORKFLOW_DIR = "/comfy/workflows"
DEFAULT_OUTPUT_DIR = "/comfy/output"
DEFAULT_SERVER_URL = "http://127.0.0.1:8188"
DEFAULT_GLOBAL_PARAMS = [
    {"target": "Img2img", "value": "1"},
    {"target": "Reduce input", "value": "1"},
    {"target": "Reduce input amount", "value": "0.5"},
    {"target": "Keep original size output", "value": "1"},
    {"target": "Refine stage 1", "value": "1"},
    {"target": "Refine stage 2", "value": "0"},
    {"target": "Seed", "value": "0"},
    {"target": "Denoise", "value": "0.2"},
    {"target": "Steps", "value": "7"},
    {"target": "CFG", "value": "1.0"},
]
DEFAULT_REGION_PARAMS = [
    {"target": "Img2img", "value": "1"},
    {"target": "Reduce input", "value": "1"},
    {"target": "Reduce input amount", "value": "{best-scale}"},
    {"target": "Keep original size output", "value": "1"},
    {"target": "Refine stage 1", "value": "1"},
    {"target": "Refine stage 2", "value": "0"},
    {"target": "Seed", "value": "0"},
    {"target": "Denoise", "value": "0.2"},
    {"target": "Steps", "value": "7"},
    {"target": "CFG", "value": "1.0"},
]


DEFAULT_CONFIG_PATH = Path.home() / ".krita" / "comfy_config.json"


class ConfigManager:
    """Load and save basic configuration values."""

    def __init__(self, storage_path: Optional[str] = None, logger: Optional[Callable[[str], None]] = None):
        self.storage_path = storage_path or str(DEFAULT_CONFIG_PATH)
        self._log = logger
        self.data: Dict[str, Any] = {
            "server_url": DEFAULT_SERVER_URL,
            "workflows_dir": DEFAULT_WORKFLOW_DIR,
            "workflow_global": "Universal.json",
            "workflow_region": "Universal.json",
            "params_global": [dict(p) for p in DEFAULT_GLOBAL_PARAMS],
            "params_region": [dict(p) for p in DEFAULT_REGION_PARAMS],
        }

    def load(self) -> None:
        if not os.path.exists(self.storage_path):
            self._write_log(f"No config at {self.storage_path}, using defaults")
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                for k, v in data.items():
                    if v is None:
                        continue
                    if k in ("params_global", "params_region"):
                        self.data[k] = self._normalize_params(v)
                    else:
                        self.data[k] = v
            # Drop legacy entries we no longer support
            self.data.pop("output_dir", None)
            self._write_log(
                f"Loaded config: server={self.data.get('server_url')}, "
                f"global wf={self.data.get('workflow_global')}, region wf={self.data.get('workflow_region')}, "
                f"params_global={len(self.data.get('params_global') or [])}, "
                f"params_region={len(self.data.get('params_region') or [])}"
            )
        except (OSError, json.JSONDecodeError) as exc:
            self._write_log(f"Failed to load config: {exc}")

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2)
            self._write_log(f"Saved config to {self.storage_path}")
        except OSError as exc:
            self._write_log(f"Failed to save config: {exc}")

    def update(self, new_values: Dict[str, str]) -> None:
        for key, value in new_values.items():
            if value is not None:
                self.data[key] = value

    def _normalize_params(self, value: Any) -> List[Dict[str, str]]:
        if isinstance(value, str):
            try:
                maybe = json.loads(value)
                value = maybe
            except Exception:
                return []
        if not isinstance(value, list):
            return []
        normalized: List[Dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target", "") or "")
            val = str(item.get("value", "") or "")
            if target:
                normalized.append({"target": target, "value": val})
        return normalized

    def _write_log(self, message: str) -> None:
        if self._log:
            self._log(message)
