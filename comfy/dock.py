"""Dock widget exposing the workflow pane inside Krita's right panel."""

from typing import Callable, Optional
from krita import DockWidget, DockWidgetFactory, DockWidgetFactoryBase
from PyQt5 import QtWidgets

from .workflow_pane import WorkflowPane

_ENHANCER_PROVIDER: Optional[Callable[[], object]] = None


def set_enhancer_provider(provider: Callable[[], object]) -> None:
    """Set a callable returning the active enhancer instance."""
    global _ENHANCER_PROVIDER
    _ENHANCER_PROVIDER = provider


class ComfyWorkflowDock(DockWidget):
    """Hosts the workflow controls as a dock on the right."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ComfyUI Workflow")
        self.workflow_pane = WorkflowPane(parent=self)
        self.setWidget(self.workflow_pane)
        self._attach_enhancer()

    def _attach_enhancer(self) -> None:
        enhancer = _ENHANCER_PROVIDER() if callable(_ENHANCER_PROVIDER) else _ENHANCER_PROVIDER
        if enhancer:
            try:
                enhancer.register_dock(self)
            except Exception:
                # Avoid crashing dock creation; enhancer will attach later.
                pass

    def canvasChanged(self, canvas):
        """Required by DockWidget; no per-canvas state needed."""
        # Krita calls this when the active canvas changes. No action required.
        return


def create_dock_factory() -> DockWidgetFactory:
    """Factory helper so the plugin can register the dock."""
    return DockWidgetFactory(
        "ComfyUI Workflow",
        DockWidgetFactoryBase.DockRight,
        ComfyWorkflowDock,
    )
