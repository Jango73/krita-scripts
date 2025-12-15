"""Workflow parsing and parameter injection utilities."""

from typing import Dict, List, Any, Optional, Callable
import json
import os


class WorkflowParser:
    """Parses workflow JSON and applies parameter overrides."""

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        self._log = logger

    def load(self, path: str) -> Dict[str, Any]:
        """Load a workflow from disk."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Workflow file not found: {path}")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self._normalize_nodes(data)
        return data

    def apply_parameters(self, workflow: Dict[str, Any], parameters: List[Dict[str, str]]) -> Dict[str, Any]:
        """Apply parameter overrides to the workflow."""
        self._normalize_nodes(workflow)
        for param in parameters:
            target = param.get("target", "")
            value = param.get("value", "")
            if not target:
                continue
            try:
                self._apply_single(workflow, target, value)
            except Exception as exc:
                self._write_log(f"Failed to apply parameter '{target}': {exc}")
        return workflow

    def to_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a ComfyUI workflow file (nodes list/links) to a prompt dict."""
        nodes = workflow.get("nodes") or []
        links = workflow.get("links") or []
        link_map = {}
        for entry in links:
            if isinstance(entry, list) and len(entry) >= 5:
                link_id, from_node, from_slot, to_node, to_slot = entry[:5]
                link_map[entry[0]] = {
                    "from_node": str(from_node),
                    "from_slot": from_slot,
                    "to_node": str(to_node),
                    "to_slot": to_slot,
                }

        prompt: Dict[str, Any] = {}
        if isinstance(nodes, dict):
            node_iterable = nodes.values()
        else:
            node_iterable = nodes

        for node in node_iterable:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id"))
            class_type = node.get("type") or node.get("class_type")
            inputs_obj: Dict[str, Any] = {}

            widgets = node.get("widgets_values") if isinstance(node.get("widgets_values"), list) else []
            widget_idx = 0
            widget_map = self._build_widget_map(class_type, widgets)

            node_inputs = node.get("inputs")
            if isinstance(node_inputs, list):
                for inp in node_inputs:
                    if not isinstance(inp, dict):
                        continue
                    name = inp.get("name")
                    link_id = inp.get("link")
                    has_widget = isinstance(inp.get("widget"), dict)
                    linked = link_id is not None and link_id in link_map
                    if linked:
                        src = link_map[link_id]
                        inputs_obj[name] = [src["from_node"], src["from_slot"]]
                    else:
                        if widget_map and name in widget_map:
                            inputs_obj[name] = widget_map[name]
                        elif has_widget and widget_idx < len(widgets):
                            inputs_obj[name] = widgets[widget_idx]
                        elif "value" in inp:
                            inputs_obj[name] = inp.get("value")
                    if has_widget:
                        widget_idx += 1
            elif isinstance(node_inputs, dict):
                inputs_obj.update(node_inputs)

            prompt[node_id] = {
                "class_type": class_type,
                "inputs": inputs_obj,
            }
        return prompt

    def _build_widget_map(self, class_type: Optional[str], widgets: List[Any]) -> Dict[str, Any]:
        """Map known widget sequences to input names to avoid misalignment."""
        if not class_type or not widgets:
            return {}

        sequences = {
            "KSampler": ["seed", "seed_mode", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
            "BNK_TiledKSampler": [
                "seed",
                "seed_mode",
                "tile_width",
                "tile_height",
                "tiling_strategy",
                "steps",
                "cfg",
                "sampler_name",
                "scheduler",
                "denoise",
            ],
            "DZ_Face_Detailer": [
                "seed",
                "seed_mode",
                "steps",
                "cfg",
                "sampler_name",
                "scheduler",
                "denoise",
                "mask_blur",
                "mask_type",
                "mask_control",
                "dilate_mask_value",
                "erode_mask_value",
            ],
            "ImageScale": ["upscale_method", "width", "height", "crop"],
            "ImageScaleBy": ["upscale_method", "scale_by"],
            "PrimitiveInt": ["value"],
            "PrimitiveFloat": ["value"],
            "PrimitiveBoolean": ["value"],
            "CheckpointLoaderSimple": ["ckpt_name"],
            "UpscaleModelLoader": ["model_name"],
            "LoadImage": ["image", "upload"],
            "SaveImage": ["filename_prefix"],
            "ImpactCompare": ["cmp"],
            "ImpactLogicalOperators": ["operator"],
            "EmptyLatentImage": ["width", "height", "batch_size"],
            "CLIPTextEncode": ["text"],
        }

        seq = sequences.get(class_type)
        if not seq:
            return {}

        mapping: Dict[str, Any] = {}
        for idx, name in enumerate(seq):
            if idx < len(widgets):
                mapping[name] = widgets[idx]
        return mapping

    def _normalize_nodes(self, workflow: Dict[str, Any]) -> None:
        """Ensure workflow['nodes'] is a dict keyed by node id as string."""
        nodes = workflow.get("nodes")
        if isinstance(nodes, dict):
            return
        if isinstance(nodes, list):
            normalized = {}
            for idx, node in enumerate(nodes):
                if not isinstance(node, dict):
                    continue
                node_id = node.get("id")
                key = str(node_id) if node_id is not None else str(idx)
                normalized[key] = node
            workflow["nodes"] = normalized

    def _apply_single(self, workflow: Dict[str, Any], target: str, value: Any) -> None:
        segments = target.split(".")
        if not segments:
            return

        nodes = workflow.get("nodes") or {}
        node_identifier = segments[0]
        remainder = segments[1:]

        # If only one segment, try to find a node that has this as an input key or widget.
        if not remainder:
            node, leaf_key = self._find_input_target(nodes, node_identifier)
            if node and leaf_key:
                self._set_leaf(node, leaf_key, value, target)
                return
            if node:
                if self._set_widget_value(node, value, target):
                    return
            # Try node by identifier directly
            node = self._find_node(nodes, node_identifier)
            if node:
                # If target matches a widget or input name, set it
                if self._set_widget_value(node, value, target):
                    return
                # If node has list inputs with matching name, set their value
                inputs = node.get("inputs")
                if isinstance(inputs, list):
                    for entry in inputs:
                        if isinstance(entry, dict) and entry.get("name") == target:
                            entry["value"] = self._convert_value(value)
                            self._write_log(f"Set input list value for {target} on node '{node.get('name') or node.get('title') or node.get('id')}'")
                            return
            self._write_log(f"Parameter target not found: input/widget '{node_identifier}'")
            return

        node = self._find_node(nodes, node_identifier)
        if node is None:
            self._write_log(f"Parameter target not found: node='{node_identifier}'")
            return

        current = node
        for segment in remainder[:-1]:
            if isinstance(current, list) and segment.isdigit():
                idx = int(segment)
                if 0 <= idx < len(current):
                    current = current[idx]
                    continue
                self._write_log(f"Parameter path index out of range '{segment}' for target '{target}'")
                return
            if not isinstance(current, dict) or segment not in current:
                self._write_log(f"Parameter path missing segment '{segment}' for target '{target}'")
                return
            current = current.get(segment)
            if current is None:
                self._write_log(f"Parameter path resolved to None at '{segment}' for '{target}'")
                return

        leaf_key = remainder[-1]
        if isinstance(current, list) and leaf_key.isdigit():
            idx = int(leaf_key)
            if 0 <= idx < len(current):
                current[idx] = self._convert_value(value)
                self._write_log(f"Set {target} to {current[idx]}")
            else:
                self._write_log(f"Leaf index '{leaf_key}' out of range for target '{target}'")
        elif isinstance(current, dict):
            # Allow setting even if key not pre-existing to align with ComfyUI flexibility
            current[leaf_key] = self._convert_value(value)
            self._write_log(f"Set {target} to {current[leaf_key]}")
        else:
            self._write_log(f"Leaf key '{leaf_key}' not found for target '{target}'")

    def _set_leaf(self, container: Dict[str, Any], leaf_key: str, value: Any, target: str) -> None:
        container[leaf_key] = self._convert_value(value)
        self._write_log(f"Set {target} to {container[leaf_key]}")

    def _set_widget_value(self, node: Dict[str, Any], value: Any, target: str) -> bool:
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            widgets[0] = self._convert_value(value)
            self._write_log(f"Set widget value for {target} on node '{node.get('name') or node.get('title') or node.get('id')}' to {widgets[0]}")
            return True
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            for entry in inputs:
                if isinstance(entry, dict) and entry.get("name") == target:
                    entry["value"] = self._convert_value(value)
                    self._write_log(f"Set input list value for {target} on node '{node.get('name') or node.get('title') or node.get('id')}'")
                    return True
        return False

    def _find_node(self, nodes: Dict[str, Any], identifier: str) -> Optional[Dict[str, Any]]:
        if isinstance(nodes, dict) and identifier in nodes:
            return nodes[identifier]

        iterable = nodes.items() if isinstance(nodes, dict) else enumerate(nodes) if isinstance(nodes, list) else []
        for _, node in iterable:
            if not isinstance(node, dict):
                continue
            if node.get("name") == identifier or node.get("title") == identifier:
                return node
            if str(node.get("id")) == identifier:
                return node
            class_type = node.get("type") or node.get("class_type")
            if class_type == identifier:
                return node

        # Fallback: if identifier looks numeric, try direct index in list
        if isinstance(nodes, list) and identifier.isdigit():
            idx = int(identifier)
            if 0 <= idx < len(nodes) and isinstance(nodes[idx], dict):
                return nodes[idx]

        # Last resort: search inside nodes for an inputs key matching identifier
        for _, node in iterable:
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if isinstance(inputs, dict) and identifier in inputs:
                return node

        return None

    def _find_input_target(self, nodes: Any, input_key: str) -> (Optional[Dict[str, Any]], Optional[str]):
        iterable = nodes.items() if isinstance(nodes, dict) else enumerate(nodes) if isinstance(nodes, list) else []
        for _, node in iterable:
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs") or {}
            if isinstance(inputs, dict) and input_key in inputs:
                return node, input_key
            if isinstance(inputs, list):
                for entry in inputs:
                    if isinstance(entry, dict) and entry.get("name") == input_key:
                        return node, input_key
        return None, None

    def _convert_value(self, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if value.isdigit():
                try:
                    return int(value)
                except ValueError:
                    pass
            try:
                return float(value)
            except ValueError:
                return value
        return value

    def _write_log(self, message: str) -> None:
        if self._log:
            self._log(message)
