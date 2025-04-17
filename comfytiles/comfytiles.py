from krita import *
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QByteArray, QObject, pyqtSignal
import os
import tempfile
import json
import sys

class StreamLogger(QObject):
    message = pyqtSignal(str)

    def __init__(self, output_widget):
        super().__init__()
        self.output_widget = output_widget
        self.message.connect(self.write_message)

    def write(self, msg):
        self.message.emit(msg)

    def flush(self):
        pass

    def write_message(self, msg):
        self.output_widget.appendPlainText(msg.strip())

tile_size = 1408
overlap = 64

def export_tiles(comfy_input_folder, comfy_output_folder):
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

            export_name = f"{base_name}_{index:04d}_{x}_{y}.png"
            export_path = os.path.join(comfy_input_folder, export_name)

            png_info = InfoObject()
            png_info.setProperty("createFolder", True)
            png_info.setProperty("quality", 90)
            png_info.setProperty("useExportConfiguration", True)
            png_info.setProperty("exportConfiguration", "PNG")
            png_info.setProperty("alpha", True)
            png_info.setProperty("compression", 9)
            png_info.setProperty("forceSRGB", True)
            png_info.setProperty("saveSRGBProfile", True)
            png_info.setProperty("interlaced", False)
            png_info.setProperty("transparencyFillColor", 0)
            png_info.setProperty("useExportConfiguration", True)

            tile_doc.exportImage(export_path, png_info)
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

def reassemble_from_meta(comfy_input_folder, comfy_output_folder):
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        print("❌ No Krita document open.")
        return

    tile_meta_path = os.path.join(comfy_input_folder, "tile_meta.json")
    if not os.path.exists(tile_meta_path):
        print("❌ tile_meta.json is missing.")
        return

    with open(tile_meta_path, "r") as f:
        tile_meta = json.load(f)

    comfy_images = sorted([
        f for f in os.listdir(comfy_output_folder)
        if f.lower().endswith((".jpg", ".png")) # and "comfyui_" in f.lower()
    ])

    if len(comfy_images) != len(tile_meta):
        print(f"❌ Number of Comfy images ({len(comfy_images)}) ≠ tiles ({len(tile_meta)})")
        return

    base_layer = doc.createNode("MergedTiles", "paintLayer")
    doc.rootNode().addChildNode(base_layer, None)

    for i, meta in enumerate(tile_meta):
        path = os.path.join(comfy_output_folder, comfy_images[i])
        image = QImage(path)
        if image.isNull():
            print(f"❌ Failed to load : {path}")
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

        bytes_per_line = img.bytesPerLine()
        ptr = img.bits()
        ptr.setsize(h * bytes_per_line)
        raw_data = ptr.asstring()

        existing_data = base_layer.pixelData(insert_x, insert_y, w, h)

        blended_data = bytearray()

        for y in range(h):
            for x in range(w):
                offset = (y * bytes_per_line) + x * 4
                sr = raw_data[offset]
                sg = raw_data[offset + 1]
                sb = raw_data[offset + 2]
                sa = alpha_mask[y][x]

                doffset = (y * w + x) * 4
                dr = existing_data[doffset]
                dg = existing_data[doffset + 1]
                db = existing_data[doffset + 2]
                da = existing_data[doffset + 3]

                r, g, b, a = blend_pixel((sr, sg, sb, sa), (dr, dg, db, da))
                blended_data.extend([r, g, b, a])

        byte_array = QByteArray(bytes(blended_data))
        base_layer.setPixelData(byte_array, insert_x, insert_y, w, h)

CONFIG_PATH = os.path.expanduser("~/.config/comfy_config.json")

def load_config():
    default = {
        "comfy_input_folder": "",
        "comfy_output_folder": ""
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

class ComfyTilesExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("comfy_tiles_action", "ComfyTiles", "tools/scripts")
        action.triggered.connect(self.show_dialog)

    def show_dialog(self):
        config = load_config()

        dialog = QDialog()
        dialog.setWindowTitle("ComfyTiles Configuration")
        layout = QVBoxLayout()

        input_label = QLabel("Comfy Input Folder:")
        input_edit = QLineEdit(config["comfy_input_folder"])
        input_btn = QPushButton("Browse...")

        def browse_input():
            path = QFileDialog.getExistingDirectory()
            if path:
                input_edit.setText(path)

        input_btn.clicked.connect(browse_input)

        output_label = QLabel("Comfy Output Folder:")
        output_edit = QLineEdit(config["comfy_output_folder"])
        output_btn = QPushButton("Browse...")

        def browse_output():
            path = QFileDialog.getExistingDirectory()
            if path:
                output_edit.setText(path)

        output_btn.clicked.connect(browse_output)

        btn_export = QPushButton("Export tiles")
        btn_import = QPushButton("Import tiles")

        def do_export():
            export_tiles(input_edit.text(), output_edit.text())

        def do_import():
            reassemble_from_meta(input_edit.text(), output_edit.text())

        btn_export.clicked.connect(do_export)
        btn_import.clicked.connect(do_import)

        save_btn = QPushButton("Save")

        def save():
            config = {
                "comfy_input_folder": input_edit.text(),
                "comfy_output_folder": output_edit.text()
            }
            save_config(config)
            QMessageBox.information(None, "ComfyTiles", "Configuration saved.")

        save_btn.clicked.connect(save)

        log_label = QLabel("Log:")
        log_output = QPlainTextEdit()
        log_output.setReadOnly(True)

        sys.stdout = StreamLogger(log_output)

        for widget in [
            input_label, input_edit, input_btn,
            output_label, output_edit, output_btn,
            btn_export, btn_import, save_btn,
            log_label, log_output
        ]:
            layout.addWidget(widget)

        dialog.setLayout(layout)
        dialog.exec_()

Krita.instance().addExtension(ComfyTilesExtension(Krita.instance()))
