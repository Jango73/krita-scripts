from .comfytiles import Comfytiles

# And add the extension to Krita's list of extensions:
app = Krita.instance()
# Instantiate your class:
extension = Comfytiles(parent = app)
app.addExtension(extension)
