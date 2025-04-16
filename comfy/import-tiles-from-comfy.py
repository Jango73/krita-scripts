from krita import Krita, InfoObject
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QByteArray
import os
import re
import json

# 🔧 Charger les chemins depuis le fichier config
with open("c:/krita-scripts/comfy/comfy_config.json", "r") as f:
    config = json.load(f)

comfy_output_folder = config["comfy_output_folder"]

def reassemble_from_tile_order():
    app = Krita.instance()

    tile_order_path = os.path.join(comfy_output_folder, "tile_order.txt")
    if not os.path.exists(tile_order_path):
        print("tile_order.txt not found.")
        return

    with open(tile_order_path, "r") as f:
        original_names = [line.strip() for line in f.readlines()]

    tile_count = len(original_names)

    # Chercher les fichiers générés par Comfy (jpg ou png)
    all_images = sorted([
        f for f in os.listdir(comfy_output_folder)
        if f.lower().endswith((".jpg", ".png")) and f != "tile_order.txt"
    ])

    # Extraire les index numériques des noms (ex: ComfyUI_00034_.png)
    def extract_index(name):
        match = re.search(r"(\d+)", name)
        return int(match.group(1)) if match else -1

    indexed_images = [(extract_index(f), f) for f in all_images if extract_index(f) >= 0]
    if not indexed_images:
        print("No indexed Comfy images found.")
        return

    # Prendre les N dernières images selon l'index le plus élevé
    indexed_images.sort()
    max_index = indexed_images[-1][0]
    start_index = max_index - tile_count + 1
    comfy_selected = [f for (i, f) in indexed_images if i >= start_index][:tile_count]

    if len(comfy_selected) != tile_count:
        print("Not enough images found for reassembly.")
        return

    # Charger les images sélectionnées et les associer à leurs positions
    positions = []
    max_x = max_y = 0

    for i, name in enumerate(original_names):
        parts = os.path.splitext(name)[0].split("_")
        x = int(parts[-2])
        y = int(parts[-1])

        img_path = os.path.join(comfy_output_folder, comfy_selected[i])
        image = QImage(img_path)
        if image.isNull():
            print(f"Failed to load: {img_path}")
            continue

        w = image.width()
        h = image.height()
        positions.append((x, y, w, h, image))
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    new_doc = app.createDocument(max_x, max_y, "Reassembled", "RGBA", "U8", "", 300.0)

    # Créer un seul calque fusionné
    base_layer = new_doc.createNode("MergedTiles", "paintLayer")
    new_doc.rootNode().addChildNode(base_layer, None)

    for (x, y, w, h, image) in positions:
        raw = QByteArray(image.bits().asstring(w * h * 4))
        base_layer.setPixelData(raw, x, y, w, h)

    app.activeWindow().addView(new_doc)
    print("Reassembly complete.")

reassemble_from_tile_order()
