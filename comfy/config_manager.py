"""Configuration manager for ComfyUI enhancer settings."""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Callable, Any, List

def _default_workflow_dir() -> str:
    if os.name == "nt":
        return str(Path.home() / "Documents" / "ComfyUI" / "user" / "default" / "workflows")
    return "/comfy/workflows"

def _default_output_dir() -> str:
    if os.name == "nt":
        return str(Path.home() / "Documents" / "ComfyUI" / "output")
    return str(Path.home() / "ComfyUI" / "output")

DEFAULT_WORKFLOW_DIR = _default_workflow_dir()
DEFAULT_OUTPUT_DIR = _default_output_dir()
DEFAULT_SERVER_URL = "http://127.0.0.1:8188"

DEFAULT_GLOBAL_PARAMS = [
    {"target": "Img2img", "value": "1"},
    {"target": "Reduce input", "value": "1"},
    {"target": "Reduce input amount", "value": "0.5"},
    {"target": "Keep original size output", "value": "1"},
    {"target": "Refine stage 1", "value": "1"},
    {"target": "Refine stage 2", "value": "0"},
    {"target": "Face detailer", "value": "0"},
    {"target": "Seed", "value": "0"},
    {"target": "Steps", "value": "7"},
    {"target": "CFG", "value": "1.0"},
    {"target": "Denoise", "value": "0.2"},
    {"target": "Refine steps", "value": "7"},
    {"target": "Refine CFG", "value": "1.0"},
    {"target": "Refine denoise", "value": "0.2"},
]

DEFAULT_REGION_PARAMS = [
    {"target": "Img2img", "value": "1"},
    {"target": "Reduce input", "value": "1"},
    {"target": "Reduce input amount", "value": "{best-scale}"},
    {"target": "Keep original size output", "value": "1"},
    {"target": "Refine stage 1", "value": "1"},
    {"target": "Refine stage 2", "value": "0"},
    {"target": "Face detailer", "value": "0"},
    {"target": "Seed", "value": "0"},
    {"target": "Steps", "value": "7"},
    {"target": "CFG", "value": "1.0"},
    {"target": "Denoise", "value": "0.2"},
    {"target": "Refine steps", "value": "7"},
    {"target": "Refine CFG", "value": "1.0"},
    {"target": "Refine denoise", "value": "0.2"},
]

DEFAULT_CONFIG_PATH = Path.home() / ".krita" / "comfy_config.json"


def _make_simple_params(base_params: List[Dict[str, str]]) -> List[Dict[str, str]]:
    replacements = {
        "Seed": "{seed}",
        "Steps": "{steps}",
        "CFG": "{classifier-free-guidance}",
        "Denoise": "{denoise}",
        "Refine steps": "{steps}",
        "Refine CFG": "{classifier-free-guidance}",
        "Refine denoise": "{denoise}",
    }
    updated: List[Dict[str, str]] = []
    for param in base_params:
        target = param.get("target", "")
        value = replacements.get(target, param.get("value", ""))
        updated.append({"target": target, "value": value})
    return updated


DEFAULT_GLOBAL_PARAMS_SIMPLE = _make_simple_params(DEFAULT_GLOBAL_PARAMS)
DEFAULT_REGION_PARAMS_SIMPLE = _make_simple_params(DEFAULT_REGION_PARAMS)

class ConfigManager:
    """Load and save basic configuration values."""

    def __init__(self, storage_path: Optional[str] = None, logger: Optional[Callable[[str], None]] = None):
        self.storage_path = storage_path or str(DEFAULT_CONFIG_PATH)
        self._log = logger
        self.data: Dict[str, Any] = {
            "server_url": DEFAULT_SERVER_URL,
            "workflows_dir": DEFAULT_WORKFLOW_DIR,
            "output_dir": DEFAULT_OUTPUT_DIR,
            "workflow_global": "Universal.json",
            "workflow_region": "Universal.json",
            "params_global_advanced": [dict(p) for p in DEFAULT_GLOBAL_PARAMS],
            "params_region_advanced": [dict(p) for p in DEFAULT_REGION_PARAMS],
            "params_global_simple": [dict(p) for p in DEFAULT_GLOBAL_PARAMS_SIMPLE],
            "params_region_simple": [dict(p) for p in DEFAULT_REGION_PARAMS_SIMPLE],
            "mode": "advanced",
            "enhance_value": 20,
            "random_seed": 0,
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
                        mapped = "params_global_advanced" if k == "params_global" else "params_region_advanced"
                        self.data[mapped] = self._normalize_params(v)
                        continue
                    if k in (
                        "params_global_advanced",
                        "params_region_advanced",
                        "params_global_simple",
                        "params_region_simple",
                    ):
                        self.data[k] = self._normalize_params(v)
                    else:
                        self.data[k] = v
            self._write_log(
                f"Loaded config: server={self.data.get('server_url')}, "
                f"global wf={self.data.get('workflow_global')}, region wf={self.data.get('workflow_region')}, "
                f"params_global={len(self.data.get('params_global_advanced') or [])}, "
                f"params_region={len(self.data.get('params_region_advanced') or [])}"
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
