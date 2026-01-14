"""Persistence for named parameter sets (prompts + workflow parameters)."""

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any


DEFAULT_PARAMETER_SETS_PATH = Path.home() / ".krita" / "comfy_param_sets.json"


class ParameterSetManager:
    """Stores, retrieves, and persists named parameter sets."""

    def __init__(self, storage_path: Optional[str] = None, logger: Optional[Callable[[str], None]] = None):
        self.storage_path = storage_path or str(DEFAULT_PARAMETER_SETS_PATH)
        self._log = logger
        self.sets: Dict[str, Dict[str, Any]] = {}

    def load(self) -> None:
        """Load sets from disk."""
        if not os.path.exists(self.storage_path):
            self._write_log(f"No parameter sets at {self.storage_path}, starting empty")
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                raw_sets = data.get("sets") or {}
            elif isinstance(data, list):
                # Legacy list-only format
                raw_sets = {item.get("name", f"set-{idx}"): item for idx, item in enumerate(data) if isinstance(item, dict)}
            else:
                raw_sets = {}
            normalized: Dict[str, Dict[str, Any]] = {}
            for name, payload in raw_sets.items():
                if not isinstance(payload, dict):
                    continue
                prompts = payload.get("prompts") or {}
                params_advanced = payload.get("params_advanced") or payload.get("params") or {}
                params_simple = payload.get("params_simple") or params_advanced or {}
                mode = payload.get("mode")
                if mode not in ("simple", "advanced"):
                    mode = "advanced"
                normalized[name] = {
                    "mode": mode,
                    "prompts": self._normalize_prompts(prompts),
                    "params_advanced": self._normalize_params(params_advanced),
                    "params_simple": self._normalize_params(params_simple),
                    "enhance_value": self._normalize_int(payload.get("enhance_value"), 20),
                    "random_seed": self._normalize_int(payload.get("random_seed"), 0),
                }
            self.sets = normalized
            self._write_log(f"Loaded {len(self.sets)} parameter set(s)")
        except (OSError, json.JSONDecodeError) as exc:
            self._write_log(f"Failed to load parameter sets: {exc}")

    def save(self) -> None:
        """Persist sets to disk."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            payload = {"sets": self.sets}
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            self._write_log(f"Saved parameter sets to {self.storage_path}")
        except OSError as exc:
            self._write_log(f"Failed to save parameter sets: {exc}")

    def list_names(self) -> List[str]:
        """Return set names sorted alphabetically."""
        return sorted(self.sets.keys())

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch a set by name."""
        return self.sets.get(name)

    def save_set(self, name: str, payload: Dict[str, Any]) -> None:
        """Create or overwrite a set."""
        if not name:
            return
        prompts = payload.get("prompts") or {}
        params_advanced = payload.get("params_advanced") or payload.get("params") or {}
        params_simple = payload.get("params_simple") or params_advanced or {}
        mode = payload.get("mode")
        if mode not in ("simple", "advanced"):
            mode = "advanced"
        self.sets[name] = {
            "mode": mode,
            "prompts": self._normalize_prompts(prompts),
            "params_advanced": self._normalize_params(params_advanced),
            "params_simple": self._normalize_params(params_simple),
            "enhance_value": self._normalize_int(payload.get("enhance_value"), 20),
            "random_seed": self._normalize_int(payload.get("random_seed"), 0),
        }
        self.save()
        self._write_log(f"Saved parameter set '{name}'")

    def delete(self, name: str) -> None:
        """Delete a set by name."""
        if name in self.sets:
            self.sets.pop(name, None)
            self.save()
            self._write_log(f"Deleted parameter set '{name}'")

    def _normalize_prompts(self, prompts: Any) -> Dict[str, List[str]]:
        if not isinstance(prompts, dict):
            return {"global": [""], "regions": ["", "", "", ""]}
        global_prompt = prompts.get("global")
        if isinstance(global_prompt, list):
            global_prompt = global_prompt[0] if global_prompt else ""
        if global_prompt is None:
            global_prompt = ""
        regions = prompts.get("regions") or []
        if not isinstance(regions, list):
            regions = []
        merged_regions = (regions + ["", "", "", ""])[:4]
        merged_regions = [p or "" for p in merged_regions]
        return {"global": [str(global_prompt)], "regions": merged_regions}

    def _normalize_params(self, params: Any) -> Dict[str, List[Dict[str, str]]]:
        if not isinstance(params, dict):
            return {"global": [], "regions": []}
        global_params = self._normalize_param_list(params.get("global"))
        region_params = self._normalize_param_list(params.get("regions"))
        return {"global": global_params, "regions": region_params}

    def _normalize_param_list(self, items: Any) -> List[Dict[str, str]]:
        if not isinstance(items, list):
            return []
        normalized: List[Dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target", "") or "")
            value = str(item.get("value", "") or "")
            if target:
                normalized.append({"target": target, "value": value})
        return normalized

    def _normalize_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _write_log(self, message: str) -> None:
        if self._log:
            self._log(message)
