from krita import Krita, InfoObject
import os
import tempfile

tile_size = 1536

# 🔧 Dossiers à configurer
comfy_input_folder = r"C:\input"
comfy_output_folder = r"C:\output"

def export_tiles():
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        print("No document open.")
        return

    width = doc.width()
    height = doc.height()

    if doc.fileName():
        base_name = os.path.splitext(os.path.basename(doc.fileName()))[0]
    else:
        base_name = "untitled"

    os.makedirs(comfy_input_folder, exist_ok=True)
    os.makedirs(comfy_output_folder, exist_ok=True)

    # Étape 1 : exporter une version PNG aplatie
    temp_png = tempfile.mktemp(suffix=".png")
    info = InfoObject()
    info.setProperty("alpha", True)
    doc.exportImage(temp_png, info)

    # Étape 2 : ouvrir cette image comme base raster
    flat_doc = app.openDocument(temp_png)
    app.setActiveDocument(flat_doc)
    flat_doc.waitForDone()

    flat_layer = flat_doc.rootNode().childNodes()[0]
    tile_names = []

    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            w = min(tile_size, width - x)
            h = min(tile_size, height - y)

            tile_doc = app.createDocument(w, h, f"tile_{x}_{y}", "RGBA", "U8", "", 300.0)
            tile_layer = tile_doc.rootNode().childNodes()[0]

            pixel_data = flat_layer.pixelData(x, y, w, h)
            tile_layer.setPixelData(pixel_data, 0, 0, w, h)

            # Export
            index = len(tile_names)
            export_name = f"{base_name}_{index:04d}_{x}_{y}.jpg"
            export_path = os.path.join(comfy_input_folder, export_name)

            jpg_info = InfoObject()
            jpg_info.setProperty("createFolder", True)
            jpg_info.setProperty("quality", 90)
            jpg_info.setProperty("useExportConfiguration", True)
            jpg_info.setProperty("exportConfiguration", "JPEG")

            tile_doc.exportImage(export_path, jpg_info)
            print(f"Saved: {export_path}")
            tile_doc.close()

            tile_names.append(export_name)

    flat_doc.close()
    os.remove(temp_png)

    # Enregistrement de l’ordre des tuiles pour reconstruction
    index_path = os.path.join(comfy_output_folder, "tile_order.txt")
    with open(index_path, "w") as f:
        for name in tile_names:
            f.write(name + "\n")

    print(f"tile_order.txt written to: {index_path}")

export_tiles()
