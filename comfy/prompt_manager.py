"""Prompt management for global and region prompts."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Callable


class PromptManager:
    """Stores, retrieves, and persists prompts."""

    def __init__(self, storage_path: Optional[str] = None, logger: Optional[Callable[[str], None]] = None):
        self.storage_path = storage_path or str(Path.home() / ".krita" / "comfy_prompts.json")
        self._log = logger
        self.global_prompt: str = ""
        self.region_prompts: List[str] = ["", "", "", ""]

    def load(self) -> None:
        """Load prompts from persistent storage."""
        if not os.path.exists(self.storage_path):
            self._write_log(f"No prompt storage found at {self.storage_path}, using defaults")
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.global_prompt = data.get("global", "") or ""
            regions = data.get("regions") or []
            merged_regions = (regions + ["", "", "", ""])[:4]
            self.region_prompts = [p or "" for p in merged_regions]
            self._write_log("Loaded prompts from disk")
        except (json.JSONDecodeError, OSError) as exc:
            self._write_log(f"Failed to load prompts: {exc}")

    def save(self) -> None:
        """Save prompts to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as handle:
                json.dump(self._to_dict(), handle, indent=2)
            self._write_log("Saved prompts to disk")
        except OSError as exc:
            self._write_log(f"Failed to save prompts: {exc}")

    def set_global(self, prompt: str) -> None:
        self.global_prompt = prompt or ""

    def set_region(self, index: int, prompt: str) -> None:
        if 0 <= index < len(self.region_prompts):
            self.region_prompts[index] = prompt or ""

    def _to_dict(self) -> Dict[str, List[str]]:
        return {
            "global": self.global_prompt,
            "regions": list(self.region_prompts),
        }

    def _write_log(self, message: str) -> None:
        if self._log:
            self._log(message)
