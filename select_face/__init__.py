from .select_face import Select_face

# And add the extension to Krita's list of extensions:
app = Krita.instance()
# Instantiate your class:
extension = Select_face(parent = app)
app.addExtension(extension)
