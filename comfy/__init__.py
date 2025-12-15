from krita import Krita
from .plugin import ComfyExtension

app = Krita.instance()
extension = ComfyExtension(parent=app)
app.addExtension(extension)
