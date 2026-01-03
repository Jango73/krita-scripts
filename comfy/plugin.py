"""Krita extension binding for the ComfyUI enhancer."""

from krita import Extension, Krita
from typing import Optional

from .comfyui_enhancer import ComfyUIEnhancer
from .dock import create_dock_factory, set_enhancer_provider


ACTION_ID = "comfyui_image_enhance"
MENU_TEXT = "ComfyUI Image Enhance"
MENU_LOCATION = "tools/scripts"


class ComfyExtension(Extension):
    """Registers the action and bridges Krita with the enhancer."""

    def __init__(self, parent: Optional[object]):
        super().__init__(parent)
        self.enhancer = ComfyUIEnhancer(logger=self._log)
        set_enhancer_provider(lambda: self.enhancer)

    def setup(self) -> None:
        """Called once when the extension is loaded."""
        app = Krita.instance()
        app.addDockWidgetFactory(create_dock_factory())

    def createActions(self, window) -> None:
        """Create the menu action under Tools > Scripts."""
        action = window.createAction(ACTION_ID, MENU_TEXT, MENU_LOCATION)
        action.triggered.connect(self._on_triggered)

    def _on_triggered(self) -> None:
        # Ensure the workflow dock is available; dialog holds secondary settings.
        self.enhancer.open_dialog()

    def _log(self, message: str) -> None:
        print(message)
