from krita import Krita, InfoObject
import os
import tempfile
import json

tile_size = 1408
overlap = 64

# 🔧 Charger les chemins depuis le fichier config
with open("c:/krita-scripts/comfy/comfy_config.json", "r") as f:
    config = json.load(f)

comfy_input_folder = config["comfy_input_folder"]
comfy_output_folder = config["comfy_output_folder"]

def export_tiles():
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        print("❌ No document open.")
        return

    width = doc.width()
    height = doc.height()

    base_name = os.path.splitext(os.path.basename(doc.fileName() or "untitled"))[0]

    os.makedirs(comfy_input_folder, exist_ok=True)
    os.makedirs(comfy_output_folder, exist_ok=True)

    # 🔄 Export PNG aplati
    temp_png = tempfile.mktemp(suffix=".png")
    info = InfoObject()
    info.setProperty("alpha", True)
    doc.exportImage(temp_png, info)

    flat_doc = app.openDocument(temp_png)
    app.setActiveDocument(flat_doc)
    flat_doc.waitForDone()

    flat_layer = flat_doc.rootNode().childNodes()[0]
    tile_names = []
    tile_meta = []

    index = 0
    y = 0
    while y < height:
        x = 0
        while x < width:
            central_w = min(tile_size, width - x)
            central_h = min(tile_size, height - y)

            ol_left = overlap if x > 0 else 0
            ol_top = overlap if y > 0 else 0
            ol_right = overlap if x + central_w < width else 0
            ol_bottom = overlap if y + central_h < height else 0

            export_x = x - ol_left
            export_y = y - ol_top
            export_w = central_w + ol_left + ol_right
            export_h = central_h + ol_top + ol_bottom

            tile_doc = app.createDocument(export_w, export_h, f"tile_{x}_{y}", "RGBA", "U8", "", 300.0)
            tile_layer = tile_doc.rootNode().childNodes()[0]

            pixel_data = flat_layer.pixelData(export_x, export_y, export_w, export_h)
            tile_layer.setPixelData(pixel_data, 0, 0, export_w, export_h)

            export_name = f"{base_name}_{index:04d}_{x}_{y}.jpg"
            export_path = os.path.join(comfy_input_folder, export_name)

            jpg_info = InfoObject()
            jpg_info.setProperty("createFolder", True)
            jpg_info.setProperty("quality", 90)
            jpg_info.setProperty("useExportConfiguration", True)
            jpg_info.setProperty("exportConfiguration", "JPEG")

            tile_doc.exportImage(export_path, jpg_info)
            tile_doc.close()
            print(f"✅ Saved: {export_path}")

            tile_names.append(export_name)
            tile_meta.append({
                "filename": export_name,
                "x": x,
                "y": y,
                "width": export_w,
                "height": export_h,
                "overlap_top": ol_top,
                "overlap_left": ol_left,
                "overlap_bottom": ol_bottom,
                "overlap_right": ol_right
            })

            x += tile_size
            index += 1
        y += tile_size

    flat_doc.close()
    os.remove(temp_png)

    with open(os.path.join(comfy_output_folder, "tile_meta.json"), "w") as f:
        json.dump(tile_meta, f, indent=4)

    print("✅ Export terminé avec tile_meta.json.")

export_tiles()
