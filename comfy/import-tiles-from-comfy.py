from krita import Krita
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QByteArray
import os
import json

# 🔧 Charger les chemins depuis le fichier config
with open("c:/krita-scripts/comfy/comfy_config.json", "r") as f:
    config = json.load(f)

comfy_output_folder = config["comfy_output_folder"]

def generate_alpha_mask(w, h, top, left, bottom, right):
    mask = [[255 for _ in range(w)] for _ in range(h)]

    if bottom > 0:
        for y in range(h - bottom, h):
            alpha = int(255 * (h - 1 - y) / bottom)
            for x in range(left, w - right):
                mask[y][x] = min(mask[y][x], alpha)

    if right > 0:
        for x in range(w - right, w):
            alpha = int(255 * (w - 1 - x) / right)
            for y in range(top, h - bottom):
                mask[y][x] = min(mask[y][x], alpha)

    if bottom > 0 and right > 0:
        for y in range(h - bottom, h):
            for x in range(w - right, w):
                a_y = int(255 * (h - 1 - y) / bottom)
                a_x = int(255 * (w - 1 - x) / right)
                mask[y][x] = min(mask[y][x], a_x, a_y)

    if top > 0:
        for y in range(top):
            alpha = int(255 * y / top)
            for x in range(left, w - right):
                mask[y][x] = min(mask[y][x], alpha)

    if left > 0:
        for x in range(left):
            alpha = int(255 * x / left)
            for y in range(top, h - bottom):
                mask[y][x] = min(mask[y][x], alpha)

    if top > 0 and left > 0:
        for y in range(top):
            for x in range(left):
                a_y = int(255 * y / top)
                a_x = int(255 * x / left)
                mask[y][x] = min(mask[y][x], a_x, a_y)

    if top > 0 and right > 0:
        for y in range(top):
            for x in range(w - right, w):
                a_y = int(255 * y / top)
                a_x = int(255 * (w - 1 - x) / right)
                mask[y][x] = min(mask[y][x], a_x, a_y)

    if bottom > 0 and left > 0:
        for y in range(h - bottom, h):
            for x in range(left):
                a_y = int(255 * (h - 1 - y) / bottom)
                a_x = int(255 * x / left)
                mask[y][x] = min(mask[y][x], a_x, a_y)

    return mask

def to_int(val):
    return val if isinstance(val, int) else int.from_bytes(val, byteorder='little')

def blend_pixel(src_rgba, dst_rgba):
    sr, sg, sb, sa = [to_int(v) for v in src_rgba]
    dr, dg, db, da = [to_int(v) for v in dst_rgba]

    sa_f = sa / 255.0
    da_f = da / 255.0

    out_a = sa_f + da_f * (1 - sa_f)
    if out_a == 0:
        return (0, 0, 0, 0)

    out_r = (sr * sa_f + dr * da_f * (1 - sa_f)) / out_a
    out_g = (sg * sa_f + dg * da_f * (1 - sa_f)) / out_a
    out_b = (sb * sa_f + db * da_f * (1 - sa_f)) / out_a
    out_alpha = out_a * 255

    return (
        int(min(out_r, 255)),
        int(min(out_g, 255)),
        int(min(out_b, 255)),
        int(min(out_alpha, 255))
    )

def reassemble_from_meta():
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        print("❌ Aucun document Krita ouvert.")
        return

    tile_meta_path = os.path.join(comfy_output_folder, "tile_meta.json")
    if not os.path.exists(tile_meta_path):
        print("❌ tile_meta.json manquant.")
        return

    with open(tile_meta_path, "r") as f:
        tile_meta = json.load(f)

    comfy_images = sorted([
        f for f in os.listdir(comfy_output_folder)
        if f.lower().endswith((".jpg", ".png")) and "comfyui_" in f.lower()
    ])

    if len(comfy_images) != len(tile_meta):
        print(f"❌ Nombre d’images Comfy ({len(comfy_images)}) ≠ tuiles ({len(tile_meta)})")
        return

    base_layer = doc.createNode("MergedTiles", "paintLayer")
    doc.rootNode().addChildNode(base_layer, None)

    for i, meta in enumerate(tile_meta):
        path = os.path.join(comfy_output_folder, comfy_images[i])
        image = QImage(path)
        if image.isNull():
            print(f"❌ Échec chargement : {path}")
            continue

        img = image.convertToFormat(QImage.Format_ARGB32)
        w = img.width()
        h = img.height()

        top = meta["overlap_top"]
        left = meta["overlap_left"]
        bottom = meta["overlap_bottom"]
        right = meta["overlap_right"]

        insert_x = meta["x"] - left
        insert_y = meta["y"] - top

        alpha_mask = generate_alpha_mask(w, h, top, left, bottom, right)

        # Source image RGBA
        bytes_per_line = img.bytesPerLine()
        ptr = img.bits()
        ptr.setsize(h * bytes_per_line)
        raw_data = ptr.asstring()

        # Destination : lire ce qui est déjà là
        existing_data = base_layer.pixelData(insert_x, insert_y, w, h)

        blended_data = bytearray()

        for y in range(h):
            for x in range(w):
                offset = (y * bytes_per_line) + x * 4
                sr = raw_data[offset]
                sg = raw_data[offset + 1]
                sb = raw_data[offset + 2]
                sa = alpha_mask[y][x]  # Ce n’est pas un byte array mais déjà un int

                doffset = (y * w + x) * 4
                dr = existing_data[doffset]
                dg = existing_data[doffset + 1]
                db = existing_data[doffset + 2]
                da = existing_data[doffset + 3]

                # Appel au blend manuel
                r, g, b, a = blend_pixel((sr, sg, sb, sa), (dr, dg, db, da))
                blended_data.extend([r, g, b, a])

        byte_array = QByteArray(bytes(blended_data))
        base_layer.setPixelData(byte_array, insert_x, insert_y, w, h)

    print("✅ Reconstruction terminée avec blend manuel.")

reassemble_from_meta()
