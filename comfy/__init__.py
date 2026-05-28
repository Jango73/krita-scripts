"""ComfyUI Image Enhance plugin for Krita."""

from ._version import __version__

from krita import Krita
from .plugin import ComfyExtension

app = Krita.instance()
extension = ComfyExtension(parent=app)
app.addExtension(extension)
