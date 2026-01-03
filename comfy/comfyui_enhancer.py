"""Entry point for the Krita ComfyUI enhancer plugin."""

import os
import tempfile
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, List, Tuple

from PyQt5 import QtWidgets, QtGui, QtCore
from krita import Krita, InfoObject
from math import isfinite

from .dialog import ComfyUIDialog
from .comfyui_client import ComfyUIClient
from .workflow_parser import WorkflowParser
from .prompt_manager import PromptManager
from .config_manager import (
    ConfigManager,
    DEFAULT_WORKFLOW_DIR,
    DEFAULT_GLOBAL_PARAMS,
    DEFAULT_OUTPUT_DIR,
)
from .parameter_set_manager import ParameterSetManager


@dataclass
class RegionRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def pos(self) -> Tuple[int, int]:
        return self.x, self.y

    @property
    def size(self) -> Tuple[int, int]:
        return self.width, self.height


class ComfyUIEnhancer:
    """Main extension controller hooking into Krita."""

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        self._logger = logger
        self._log_buffer: List[str] = []
        self._max_log_entries = 1000
        self.dialog: Optional[ComfyUIDialog] = None
        self.client: Optional[ComfyUIClient] = None
        self.parser = WorkflowParser(logger=self._log)
        self.prompts = PromptManager(logger=self._log)
        self.config = ConfigManager(logger=self._log)
        self.parameter_sets = ParameterSetManager(logger=self._log)
        self._cancel_requested = False
        self.dock = None
        self.workflow_pane = None
        self._initialized = False

    def setup(self) -> None:
        """Setup plugin resources and UI hooks."""
        self._ensure_initialized()
        self.dialog = ComfyUIDialog(logger=self._log, parameter_sets=self.parameter_sets)
        self._populate_prompts()
        self._populate_config()
        self._populate_parameters()
        self.dialog.finished.connect(self._on_dialog_closed)
        self._flush_log_buffer()

    def unload(self) -> None:
        """Cleanup when the plugin is unloaded."""
        self.prompts.save()
        self.config.save()

    def register_dock(self, dock) -> None:
        """Attach the workflow dock and wire its signals."""
        self._ensure_initialized()
        self.dock = dock
        self.workflow_pane = getattr(dock, "workflow_pane", None)
        if self.workflow_pane:
            self.workflow_pane.set_logger(self._log)
            self.workflow_pane.set_parameter_manager(self.parameter_sets)
            self.workflow_pane.enhance_requested.connect(self._on_enhance_clicked)
            self.workflow_pane.stop_requested.connect(self._on_stop_clicked)
            self.workflow_pane.settings_requested.connect(self.open_dialog)
        self._populate_prompts()
        self._populate_parameters()

    def open_dialog(self) -> None:
        """Display the dialog."""
        if self.dialog is None:
            self.setup()
        else:
            # Keep dialog in sync with the active workflow UI before showing
            active_ui = self._active_workflow_ui()
            dialog_pane = getattr(self.dialog, "workflow_pane", None)
            if active_ui and dialog_pane is not active_ui:
                try:
                    self.dialog.set_prompts(active_ui.get_prompts())
                    params = active_ui.get_parameters()
                    params["opacity"] = self.config.data.get("opacity")
                    params["fade_ratio"] = self.config.data.get("fade_ratio")
                    self.dialog.set_parameters(params)
                except Exception:
                    pass
        if self.dialog:
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()

    def _populate_prompts(self) -> None:
        prompts = {
            "global": [self.prompts.global_prompt],
            "regions": list(self.prompts.region_prompts),
        }
        if self.dialog and getattr(self.dialog, "set_prompts", None):
            try:
                self.dialog.set_prompts(prompts)
            except Exception:
                pass
        if self.workflow_pane:
            self.workflow_pane.set_prompts(prompts)

    def _populate_config(self) -> None:
        if not self.dialog:
            return
        self.dialog.server_edit.setText(self.config.data.get("server_url", ""))
        workflow_dir = self.config.data.get("workflows_dir") or DEFAULT_WORKFLOW_DIR
        self.dialog.workflow_dir_edit.setText(workflow_dir)
        output_dir = self.config.data.get("output_dir") or DEFAULT_OUTPUT_DIR
        self.dialog.output_dir_edit.setText(output_dir)
        self.dialog.global_workflow_edit.setText(self.config.data.get("workflow_global", "Universal.json"))
        self.dialog.region_workflow_edit.setText(self.config.data.get("workflow_region", "Universal.json"))

    def _populate_parameters(self) -> None:
        global_params = self.config.data.get("params_global") or [dict(p) for p in DEFAULT_GLOBAL_PARAMS]
        params = {
            "global": global_params,
            "regions": self.config.data.get("params_region") or [],
            "opacity": self.config.data.get("opacity"),
            "fade_ratio": self.config.data.get("fade_ratio"),
        }
        if self.dialog and getattr(self.dialog, "set_parameters", None):
            self.dialog.set_parameters(params)
        if self.workflow_pane:
            self.workflow_pane.set_parameters(params)

    def _on_enhance_clicked(self, regions_only: bool = False) -> None:
        self._ensure_initialized()
        self._cancel_requested = False
        self._set_running(True)
        self._set_status("Starting...")
        config = self._get_config()
        prompts = self._get_prompts()
        parameters = self._get_parameters()

        self._log_settings(config, prompts, parameters)
        self._persist_state(prompts, parameters, config)

        self.client = self._create_client(config["server_url"])
        if regions_only:
            self._append_log("Starting region-only enhance...")
            self._set_status("Running (regions)")
        else:
            self._append_log("Starting image enhance...")
            self._set_status("Running (global + regions)")
        try:
            self._run_enhance(config, prompts, parameters, regions_only=regions_only)
            self._append_log("Enhance completed.")
            self._set_status("Done")
        except Exception as exc:
            self._append_log(f"Enhance failed: {exc}")
            self._set_status("Failed")
        finally:
            self._set_running(False)
            self._cancel_requested = False

    def _on_cancel_clicked(self) -> None:
        self._cancel_requested = True
        self._persist_state()
        if self.dialog:
            try:
                self.dialog.reject()
            except Exception:
                pass

    def _on_stop_clicked(self) -> None:
        self._cancel_requested = True
        self._set_status("Stopping...")
        if self.client:
            try:
                self.client.interrupt()
            except Exception:
                pass

    def _on_dialog_closed(self) -> None:
        self._persist_state()

    def _persist_state(
        self,
        prompts: Optional[Dict[str, List[str]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        prompts = prompts or self._get_prompts()
        parameters = parameters or self._get_parameters()
        config = config or self._get_config()

        if not config.get("workflows_dir"):
            config["workflows_dir"] = DEFAULT_WORKFLOW_DIR

        self.prompts.set_global(prompts["global"][0])
        for idx, prompt in enumerate(prompts["regions"]):
            self.prompts.set_region(idx, prompt)
        self.prompts.save()

        self.config.update(config)
        self.config.data["params_global"] = parameters.get("global", [])
        self.config.data["params_region"] = parameters.get("regions", [])
        if "opacity" in parameters:
            self.config.data["opacity"] = parameters.get("opacity")
        if "fade_ratio" in parameters:
            self.config.data["fade_ratio"] = parameters.get("fade_ratio")
        self.config.save()

    def _active_workflow_ui(self):
        if self.dock and getattr(self.dock, "workflow_pane", None):
            return self.dock.workflow_pane
        return None

    def _get_prompts(self) -> Dict[str, List[str]]:
        ui = self._active_workflow_ui()
        if ui:
            return ui.get_prompts()
        return {
            "global": [self.prompts.global_prompt],
            "regions": list(self.prompts.region_prompts),
        }

    def _get_parameters(self) -> Dict[str, Any]:
        ui = self._active_workflow_ui()
        params = ui.get_parameters() if ui else {"global": [], "regions": []}
        if "opacity" not in params:
            params["opacity"] = self.config.data.get("opacity")
        if "fade_ratio" not in params:
            params["fade_ratio"] = self.config.data.get("fade_ratio")
        return params

    def _get_config(self) -> Dict[str, Any]:
        if self.dialog:
            config = self.dialog.get_config()
        else:
            config = {
                "server_url": self.config.data.get("server_url", ""),
                "workflows_dir": self.config.data.get("workflows_dir") or DEFAULT_WORKFLOW_DIR,
                "output_dir": self.config.data.get("output_dir") or DEFAULT_OUTPUT_DIR,
                "workflow_global": self.config.data.get("workflow_global", "Universal.json"),
                "workflow_region": self.config.data.get("workflow_region", "Universal.json"),
            }
        if not config.get("workflows_dir"):
            config["workflows_dir"] = DEFAULT_WORKFLOW_DIR
        config["workflows_dir"] = self._resolve_path(config["workflows_dir"])
        self.config.data["workflows_dir"] = config["workflows_dir"]
        if not config.get("output_dir"):
            config["output_dir"] = DEFAULT_OUTPUT_DIR
        config["output_dir"] = self._resolve_path(config["output_dir"])
        self.config.data["output_dir"] = config["output_dir"]
        return config

    def _append_log(self, message: str) -> None:
        echo = self.dialog is None
        self._write_log_entry(message, echo=echo)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self.prompts.load()
        self.config.load()
        self.parameter_sets.load()
        self._initialized = True

    def _run_enhance(self, config: Dict[str, Any], prompts: Dict[str, Any], parameters: Dict[str, Any], regions_only: bool = False) -> None:
        doc = self._get_document()
        if doc is None:
            self._log("No active document.")
            self._set_status("No document")
            return

        region_rects = self._get_region_rectangles(doc)
        region_rects.sort(key=lambda r: r.x)

        temp_files: List[str] = []
        try:
            if self._cancel_requested:
                self._set_status("Cancelled")
                return
            global_img_path = self._export_full_image(doc)
            temp_files.append(global_img_path)

            # Export regions before any document mutation (global layer insertion) so that
            # region-only runs and combined runs use identical region inputs and derived
            # placeholder values such as {best-scale}.
            region_exports: List[Tuple[RegionRect, str]] = []
            for rect in region_rects:
                path = self._export_region_image(doc, rect)
                temp_files.append(path)
                region_exports.append((rect, path))

            global_workflow_path = self._resolve_workflow_path(
                name=config.get("workflow_global", ""),
                workflows_dir=config.get("workflows_dir") or DEFAULT_WORKFLOW_DIR,
            )
            region_workflow_path = self._resolve_workflow_path(
                name=config.get("workflow_region", ""),
                workflows_dir=config.get("workflows_dir") or DEFAULT_WORKFLOW_DIR,
            )

            self._log(f"Global workflow: {global_workflow_path}")
            self._log(f"Region workflow: {region_workflow_path}")
            self._log(f"Global prompt used: {prompts['global'][0]}")
            self._log("Global parameters used:")
            for param in parameters.get("global", []):
                self._log(f"  - {param.get('target')} = {param.get('value')}")
            if "opacity" in parameters:
                self._log(f"Layer opacity: {parameters.get('opacity')}")
            if "fade_ratio" in parameters:
                self._log(f"Region edge fade ratio: {parameters.get('fade_ratio')}")

            if not regions_only and not global_workflow_path:
                raise FileNotFoundError("Global workflow not found.")

            global_layer = None
            if not regions_only:
                # Run global workflow
                self._set_status("Running global workflow")
                global_payload = self._prepare_workflow(
                    workflow_path=global_workflow_path,
                    image_path=global_img_path,
                    prompt_text=prompts["global"][0],
                    parameters=parameters.get("global", []),
                )
                prompt_id = self.client.run_workflow(global_payload).get("prompt_id")
                result = self.client.poll_result(
                    prompt_id,
                    stop_requested=lambda: self._cancel_requested,
                    tick=self._yield_ui,
                )
                global_output = self._find_output_image(result)
                if not global_output:
                    raise FileNotFoundError("Global output image not found.")
                global_layer = self._insert_layer_from_file(
                    doc=doc,
                    image_path=global_output,
                    name="Global enhance",
                    position=(0, 0),
                    opacity=parameters.get("opacity", 0.8),
                    apply_fade=False,
                )

            # Region processing
            for idx, rect in enumerate(region_rects):
                if self._cancel_requested:
                    self._log("Enhance cancelled before region processing.")
                    self._set_status("Cancelled")
                    break
                prompt_idx = min(idx, 3)
                prompt_text = prompts["regions"][prompt_idx]
                self._log(f"Region {idx + 1}: using prompt index {prompt_idx + 1} value '{prompt_text}'")
                self._log("Region parameters used:")
                for param in parameters.get("regions", []):
                    self._log(f"  - {param.get('target')} = {param.get('value')}")
                region_img_path = ""
                if idx < len(region_exports):
                    region_img_path = region_exports[idx][1]
                else:
                    region_img_path = self._export_region_image(doc, rect)
                    temp_files.append(region_img_path)

                if not region_workflow_path:
                    self._log("No region workflow provided; skipping region enhancements.")
                    break

                if global_layer:
                    self._punch_hole_on_layer(global_layer, rect, parameters.get("fade_ratio", 0.1))

                self._set_status(f"Running region {idx + 1}")
                region_payload = self._prepare_workflow(
                    workflow_path=region_workflow_path,
                    image_path=region_img_path,
                    prompt_text=prompt_text,
                    parameters=parameters.get("regions", []),
                )
                region_prompt_id = self.client.run_workflow(region_payload).get("prompt_id")
                region_result = self.client.poll_result(
                    region_prompt_id,
                    stop_requested=lambda: self._cancel_requested,
                    tick=self._yield_ui,
                )
                region_output = self._find_output_image(region_result)
                if not region_output:
                    self._log(f"No output for region {idx + 1}")
                    continue

                self._insert_layer_from_file(
                    doc=doc,
                    image_path=region_output,
                    name=f"Region enhance #{idx + 1}",
                    position=rect.pos,
                    opacity=parameters.get("opacity", 0.8),
                    apply_fade=True,
                    fade_ratio=parameters.get("fade_ratio", 0.1),
                )
        finally:
            for path in temp_files:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except OSError:
                    self._log(f"Failed to delete temp file {path}")
        if self._cancel_requested:
            self._set_status("Cancelled")
        else:
            self._set_status("Done")

    def _create_client(self, server_url: str) -> ComfyUIClient:
        return ComfyUIClient(server_url=server_url, logger=self._log)

    def _get_document(self):
        app = Krita.instance()
        doc = app.activeDocument()
        return doc

    def _get_region_rectangles(self, doc) -> List[RegionRect]:
        selection = doc.selection()
        if not selection:
            return []

        rects: List[RegionRect] = []

        if hasattr(selection, "rectangles"):
            try:
                qrects = selection.rectangles()
                for r in qrects:
                    rects.append(RegionRect(r.x(), r.y(), r.width(), r.height()))
            except Exception:
                pass

        if not rects:
            rects = self._extract_mask_components(selection, doc)

        if not rects and hasattr(selection, "boundingRect"):
            try:
                r = selection.boundingRect()
                rects.append(RegionRect(r.x(), r.y(), r.width(), r.height()))
            except Exception:
                pass

        if not rects:
            try:
                if all(hasattr(selection, attr) for attr in ("x", "y", "width", "height")):
                    rects.append(RegionRect(selection.x(), selection.y(), selection.width(), selection.height()))
            except Exception:
                pass

        if not rects:
            self._log("Selection found but no rectangles could be extracted; skipping regions.")
        return rects

    def _export_full_image(self, doc) -> str:
        temp_path = self._make_input_temp_path("full")
        qimage = doc.projection(0, 0, doc.width(), doc.height())
        qimage = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
        qimage.save(temp_path, "JPG", 95)
        self._log(f"Exported full image to {temp_path}")
        return temp_path

    def _export_region_image(self, doc, rect: RegionRect) -> str:
        qimage = doc.projection(rect.x, rect.y, rect.width, rect.height)
        qimage = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
        temp_path = self._make_input_temp_path(f"region_{rect.x}_{rect.y}", ext=".jpg")
        qimage.save(temp_path, "JPG", 95)
        self._log(f"Exported region to {temp_path}")
        return temp_path

    def _prepare_workflow(self, workflow_path: str, image_path: str, prompt_text: str, parameters: List[Dict[str, str]]) -> Dict[str, Any]:
        workflow = self.parser.load(workflow_path)
        context = self._build_value_context(image_path)
        resolved_prompt = self._fill_placeholders(prompt_text, context)
        resolved_params = self._fill_parameters(parameters, context)
        self._log(f"Value context: width={context.get('width')}, height={context.get('height')}, best-scale={context.get('best-scale')}")
        if resolved_params:
            self._log("Resolved parameters:")
            for param in resolved_params:
                self._log(f"  - {param.get('target')} = {param.get('value')}")
        self._inject_image(workflow, image_path)
        self._inject_prompt(workflow, resolved_prompt)
        workflow = self.parser.apply_parameters(workflow, resolved_params)
        prompt_payload = self.parser.to_prompt(workflow)
        return {"prompt": prompt_payload}

    def _inject_image(self, workflow: Dict[str, Any], image_path: str) -> None:
        node = self._find_load_image_node(workflow)
        if not node:
            self._log("Load Image node not found for injection.")
            return
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            # Attempt widget-based injection (widgets_values[0])
            widgets = node.get("widgets_values")
            if isinstance(widgets, list) and widgets:
                widgets[0] = image_path
                self._log(f"Injected image via widget into node '{node.get('name') or node.get('id') or node.get('type') or node.get('class_type') or 'unknown'}'")
                return
            self._log(f"Load Image node inputs are not a dict (type={type(inputs).__name__}); cannot inject.")
            return
        inputs["image"] = image_path
        node["inputs"] = inputs
        node_name = node.get("name") or node.get("id") or node.get("type") or node.get("class_type") or "unknown"
        self._log(f"Injected image into node '{node_name}': {image_path}")

    def _inject_prompt(self, workflow: Dict[str, Any], prompt_text: str) -> None:
        node = self._find_prompt_node(workflow)
        if not node:
            self._log("Prompt node not found; prompt not injected.")
            return
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict):
            inputs["text"] = prompt_text
            node["inputs"] = inputs
            node_name = node.get("name") or node.get("id") or node.get("type") or node.get("class_type") or "unknown"
            self._log(f"Injected prompt into node '{node_name}' (dict inputs).")
            return
        if isinstance(inputs, list):
            injected = False
            for entry in inputs:
                if isinstance(entry, dict) and entry.get("name") == "text":
                    entry["value"] = prompt_text
                    injected = True
                    break
            if injected:
                widgets = node.get("widgets_values")
                if isinstance(widgets, list) and widgets:
                    widgets[0] = prompt_text
                node_name = node.get("name") or node.get("id") or node.get("type") or node.get("class_type") or "unknown"
                self._log(f"Injected prompt into node '{node_name}' (list inputs).")
                return
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            widgets[0] = prompt_text
            node_name = node.get("name") or node.get("id") or node.get("type") or node.get("class_type") or "unknown"
            self._log(f"Injected prompt into node '{node_name}' (widget).")
            return
        node_name = node.get("name") or node.get("id") or node.get("type") or node.get("class_type") or "unknown"
        self._log(f"Prompt node inputs not usable for injection (type={type(inputs).__name__}) on node '{node_name}'.")

    def _find_node(self, workflow: Dict[str, Any], identifier: str) -> Optional[Dict[str, Any]]:
        nodes = workflow.get("nodes") or {}
        if isinstance(nodes, dict) and identifier in nodes:
            return nodes[identifier]
        iterable = nodes.items() if isinstance(nodes, dict) else enumerate(nodes) if isinstance(nodes, list) else []
        for _, node in iterable:
            if isinstance(node, dict) and node.get("name") == identifier:
                return node
        return None

    def _find_load_image_node(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Prefer node named "Load Image"
        node = self._find_node(workflow, "Load Image")
        if node:
            return node
        nodes = workflow.get("nodes") or {}
        iterable = nodes.items() if isinstance(nodes, dict) else enumerate(nodes) if isinstance(nodes, list) else []
        for _, candidate in iterable:
            if not isinstance(candidate, dict):
                continue
            ctype = candidate.get("class_type") or candidate.get("type") or ""
            inputs = candidate.get("inputs") or {}
            if ctype.lower().find("loadimage") >= 0 or ctype.lower().find("load image") >= 0:
                return candidate
            if isinstance(inputs, dict) and "image" in inputs:
                return candidate
        return None

    def _find_prompt_node(self, workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Prefer node named "Prompt"
        node = self._find_node(workflow, "Prompt")
        if node:
            return node
        nodes = workflow.get("nodes") or {}
        iterable = nodes.items() if isinstance(nodes, dict) else enumerate(nodes) if isinstance(nodes, list) else []
        for _, candidate in iterable:
            if not isinstance(candidate, dict):
                continue
            inputs = candidate.get("inputs") or {}
            if isinstance(inputs, dict) and "text" in inputs:
                return candidate
            if isinstance(inputs, list):
                for entry in inputs:
                    if isinstance(entry, dict) and entry.get("name") == "text":
                        return candidate
            if (candidate.get("type") or candidate.get("class_type")) == "CLIPTextEncode":
                return candidate
        return None

    def _find_output_image(self, result: Dict[str, Any]) -> Optional[str]:
        outputs = result.get("outputs") or {}
        if isinstance(outputs, list):
            entries = outputs
        elif isinstance(outputs, dict):
            entries = outputs.values()
        else:
            entries = []

        candidate_dirs = []
        output_dir = ""
        if self.config:
            output_dir = self.config.data.get("output_dir", "")
        if not output_dir:
            output_dir = DEFAULT_OUTPUT_DIR
        if output_dir:
            candidate_dirs.append(output_dir)

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            images = entry.get("images") or []
            if not images and isinstance(entry.get("images"), dict):
                images = list(entry.get("images").values())
            if not images:
                continue
            img_meta = images[0]
            if not isinstance(img_meta, dict):
                continue
            filename = img_meta.get("filename")
            subfolder = img_meta.get("subfolder") or ""
            if filename:
                # Absolute filename support
                if os.path.isabs(filename) and os.path.exists(filename):
                    self._log(f"Using output image {filename}")
                    return filename
                for base_dir in candidate_dirs:
                    candidate = os.path.join(base_dir, subfolder, filename)
                    if os.path.exists(candidate):
                        self._log(f"Using output image {candidate}")
                        return candidate
        self._log("No output image found in result.")
        return None

    def _make_input_temp_path(self, prefix: str, ext: str = ".jpg") -> str:
        base_input = os.path.abspath(os.path.join(os.path.dirname(__file__), "input"))
        os.makedirs(base_input, exist_ok=True)
        handle, path = tempfile.mkstemp(prefix=f"{prefix}_", suffix=ext, dir=base_input)
        os.close(handle)
        return path

    def _insert_layer_from_file(
        self,
        doc,
        image_path: str,
        name: str,
        position: Tuple[int, int],
        opacity: float,
        apply_fade: bool,
        fade_ratio: float = 0.1,
    ):
        image = QtGui.QImage(image_path)
        if image.isNull():
            self._log(f"Failed to load image {image_path}")
            return None
        image = image.convertToFormat(QtGui.QImage.Format_ARGB32)

        if apply_fade:
            self._apply_edge_fade(image, fade_ratio)

        layer = doc.createNode(name, "paintLayer")
        doc.rootNode().addChildNode(layer, None)

        width = image.width()
        height = image.height()
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        layer.setPixelData(ptr.asstring(), 0, 0, width, height)
        if hasattr(layer, "setX") and hasattr(layer, "setY"):
            layer.setX(position[0])
            layer.setY(position[1])
        elif hasattr(layer, "setOffset"):
            layer.setOffset(position[0], position[1])
        elif hasattr(layer, "move"):
            layer.move(position[0], position[1])
        elif hasattr(layer, "setPosition"):
            layer.setPosition(QtCore.QPointF(position[0], position[1]))
        opacity_value = int(opacity if opacity > 1 else opacity * 255)
        opacity_value = max(0, min(255, opacity_value))
        layer.setOpacity(opacity_value)
        self._log(f"Inserted layer '{name}' at {position} with opacity {opacity_value}")
        self._refresh_views(doc)
        return layer

    def _apply_edge_fade(self, image: QtGui.QImage, fade_ratio: float) -> None:
        width = image.width()
        height = image.height()
        if width == 0 or height == 0:
            return
        fade = max(1, int(min(width, height) * fade_ratio))
        ptr = image.bits()
        ptr.setsize(image.byteCount())
        data = bytearray(ptr.asstring())

        def alpha_index(x: int, y: int) -> int:
            return (y * width + x) * 4 + 3

        for y in range(height):
            for x in range(width):
                dist = min(x, y, width - 1 - x, height - 1 - y)
                if dist >= fade:
                    continue
                factor = max(0.0, min(1.0, dist / float(fade)))
                idx = alpha_index(x, y)
                original_alpha = data[idx]
                data[idx] = int(original_alpha * factor)

        view = memoryview(ptr)
        view[:] = data

    def _resolve_workflow_path(self, name: str, workflows_dir: str) -> str:
        if not name:
            self._log("No workflow name provided.")
            return ""

        # Accept absolute paths directly
        if os.path.isabs(name):
            if os.path.exists(name):
                return name
            # If user provided a folder plus filename, ensure it exists
            self._log(f"Workflow path does not exist: {name}")
            return ""

        # Normalize folder
        base_dir = workflows_dir or DEFAULT_WORKFLOW_DIR

        # If name already has .json, try as-is under base_dir
        possible_names = [name]
        if not name.lower().endswith(".json"):
            possible_names.append(f"{name}.json")

        for candidate_name in possible_names:
            candidate = os.path.join(base_dir, candidate_name)
            if os.path.exists(candidate):
                return candidate

        self._log(f"Workflow not found for name '{name}'. Looked under {base_dir}")
        return ""

    def _resolve_path(self, path_value: str) -> str:
        """Resolve special plugin-relative paths (e.g., '/comfy/...') to absolute."""
        if not path_value:
            return path_value
        if path_value.startswith("/comfy"):
            plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            relative = path_value.lstrip("/")
            resolved = os.path.abspath(os.path.join(plugin_root, relative))
            return resolved
        return path_value

    def _log_settings(self, config: Dict[str, Any], prompts: Dict[str, Any], parameters: Dict[str, Any]) -> None:
        self._log(f"Server URL: {config.get('server_url')}")
        self._log(f"Workflows dir: {config.get('workflows_dir') or DEFAULT_WORKFLOW_DIR}")
        self._log(f"Output dir: {config.get('output_dir') or DEFAULT_OUTPUT_DIR}")
        self._log(f"Workflow global: {config.get('workflow_global')}")
        self._log(f"Workflow region: {config.get('workflow_region')}")
        self._log(f"Global prompt: {prompts.get('global', [''])[0]}")
        region_prompts = prompts.get("regions", [])
        for idx, p in enumerate(region_prompts):
            self._log(f"Region prompt {idx + 1}: {p}")

    def _log(self, message: str) -> None:
        self._write_log_entry(message, echo=True)

    def _write_log_entry(self, message: str, echo: bool = True) -> None:
        self._record_log(message)
        # Avoid echo loops by writing to dialog only when not already inside dialog logging
        if message == "__PENDING_DOT__":
            # Inline dot without extra newline
            if self.dialog and hasattr(self.dialog, "append_log_dot"):
                try:
                    self.dialog.append_log_dot()
                except Exception:
                    pass
            return
        if echo:
            if self._logger:
                self._logger(message)
            else:
                print(message)
        # Write to dialog log last to avoid feedback loops if logger points to dialog
        if self.dialog and hasattr(self.dialog, "append_log"):
            try:
                if not getattr(self.dialog, "_log_guard", False):
                    self.dialog._log_guard = True
                    self.dialog.append_log(message)
            finally:
                self.dialog._log_guard = False

    def _record_log(self, message: str) -> None:
        self._log_buffer.append(message)
        if len(self._log_buffer) > self._max_log_entries:
            self._log_buffer = self._log_buffer[-self._max_log_entries :]

    def _flush_log_buffer(self) -> None:
        if not self.dialog:
            return
        for entry in self._log_buffer:
            if entry == "__PENDING_DOT__":
                if hasattr(self.dialog, "append_log_dot"):
                    try:
                        self.dialog.append_log_dot()
                    except Exception:
                        pass
            else:
                try:
                    self.dialog.append_log(entry)
                except Exception:
                    pass

    def _set_status(self, message: str) -> None:
        if self.dialog and hasattr(self.dialog, "set_status"):
            try:
                self.dialog.set_status(message)
            except Exception:
                pass
        ui = self._active_workflow_ui()
        if ui:
            try:
                ui.set_status(message)
            except Exception:
                pass

    def _set_running(self, running: bool) -> None:
        if self.dialog and hasattr(self.dialog, "set_running"):
            try:
                self.dialog.set_running(running)
            except Exception:
                pass
        ui = self._active_workflow_ui()
        if ui:
            try:
                ui.set_running(running)
            except Exception:
                pass

    def _yield_ui(self) -> None:
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
        except Exception:
            pass

    def _build_value_context(self, image_path: str) -> Dict[str, Any]:
        img = QtGui.QImage(image_path)
        width = img.width() if img and not img.isNull() else 0
        height = img.height() if img and not img.isNull() else 0
        max_dim = max(width, height)
        best_scale = 1.0
        if max_dim > 0:
            best_scale = 640.0 / float(max_dim)
            best_scale = max(0.2, min(1.0, best_scale))
        if not isfinite(best_scale):
            best_scale = 1.0
        return {
            "width": width,
            "height": height,
            "best-scale": round(best_scale, 4),
        }

    def _fill_placeholders(self, text: Any, context: Dict[str, Any]) -> Any:
        if not isinstance(text, str):
            return text
        result = text
        for key, val in context.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result

    def _fill_parameters(self, parameters: List[Dict[str, str]], context: Dict[str, Any]) -> List[Dict[str, str]]:
        resolved: List[Dict[str, str]] = []
        for param in parameters or []:
            target = param.get("target", "")
            value = param.get("value", "")
            if not target:
                continue
            resolved.append({"target": target, "value": self._fill_placeholders(value, context)})
        return resolved

    def _refresh_views(self, doc) -> None:
        try:
            if hasattr(doc, "refreshProjection"):
                doc.refreshProjection()
            app = Krita.instance()
            window = app.activeWindow() if hasattr(app, "activeWindow") else None
            if window:
                for view in window.views():
                    try:
                        if hasattr(view, "canvas") and view.canvas():
                            view.canvas().update()
                        elif hasattr(view, "update"):
                            view.update()
                    except Exception:
                        continue
        except Exception:
            pass
        self._yield_ui()

    def _punch_hole_on_layer(self, layer, rect: RegionRect, fade_ratio: float) -> None:
        try:
            width = rect.width
            height = rect.height
            if width <= 0 or height <= 0:
                return
            fade = max(1, int(min(width, height) * fade_ratio))
            data = layer.pixelData(rect.x, rect.y, width, height)
            if not data:
                return
            buf = bytearray(data)
            stride = 4

            def idx(x: int, y: int) -> int:
                return (y * width + x) * stride + 3

            for y in range(height):
                for x in range(width):
                    dist = min(x, y, width - 1 - x, height - 1 - y)
                    alpha_idx = idx(x, y)
                    original_alpha = buf[alpha_idx]
                    if dist >= fade:
                        buf[alpha_idx] = 0
                    else:
                        factor = max(0.0, 1.0 - (dist / float(fade)))
                        buf[alpha_idx] = int(original_alpha * factor)

            layer.setPixelData(bytes(buf), rect.x, rect.y, width, height)
            self._log(f"Applied inverse fade to global layer at {rect.pos} size {rect.size}")
            self._refresh_views(layer.document())
        except Exception as exc:
            self._log(f"Failed to punch hole on layer: {exc}")

    def _extract_mask_components(self, selection, doc) -> List[RegionRect]:
        components: List[RegionRect] = []
        try:
            bounds = selection.boundingRect() if hasattr(selection, "boundingRect") else None
        except Exception:
            bounds = None

        if bounds and bounds.width() > 0 and bounds.height() > 0:
            x0, y0, width, height = bounds.x(), bounds.y(), bounds.width(), bounds.height()
        else:
            x0, y0, width, height = 0, 0, doc.width(), doc.height()

        try:
            raw = selection.pixelData(x0, y0, width, height)
        except Exception:
            raw = None

        if not raw:
            return components

        buf = memoryview(raw)
        pixel_count = width * height
        if pixel_count == 0:
            return components

        channels = max(1, len(buf) // pixel_count)

        def alpha_at(idx: int) -> int:
            if channels == 1:
                return buf[idx]
            base = idx * channels
            if channels >= 4:
                return buf[base + 3]
            return buf[base]

        visited = bytearray(pixel_count)
        stack: List[int] = []
        max_components = 32

        for idx in range(pixel_count):
            if visited[idx]:
                continue
            if alpha_at(idx) == 0:
                visited[idx] = 1
                continue
            minx = maxx = idx % width
            miny = maxy = idx // width
            stack.append(idx)
            visited[idx] = 1

            while stack:
                p = stack.pop()
                x = p % width
                y = p // width
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        nidx = ny * width + nx
                        if visited[nidx]:
                            continue
                        if alpha_at(nidx) == 0:
                            visited[nidx] = 1
                            continue
                        visited[nidx] = 1
                        stack.append(nidx)
                        if nx < minx:
                            minx = nx
                        if nx > maxx:
                            maxx = nx
                        if ny < miny:
                            miny = ny
                        if ny > maxy:
                            maxy = ny

            components.append(RegionRect(x0 + minx, y0 + miny, maxx - minx + 1, maxy - miny + 1))
            if len(components) >= max_components:
                break

        if components:
            self._log(f"Detected {len(components)} region(s) from selection mask.")
        return components
