from krita import *
from PyQt5.QtWidgets import *
import os
import json

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

        btn_export = QPushButton("Exporter les tuiles")
        btn_import = QPushButton("Importer les tuiles")

        def do_export():
            QMessageBox.information(None, "TODO", "Appel à la fonction d'export ici.")

        def do_import():
            QMessageBox.information(None, "TODO", "Appel à la fonction d'import ici.")

        btn_export.clicked.connect(do_export)
        btn_import.clicked.connect(do_import)

        save_btn = QPushButton("Sauvegarder")
        def save():
            config = {
                "comfy_input_folder": input_edit.text(),
                "comfy_output_folder": output_edit.text()
            }
            save_config(config)
            QMessageBox.information(None, "ComfyTiles", "Configuration sauvegardée.")

        save_btn.clicked.connect(save)

        for widget in [
            input_label, input_edit, input_btn,
            output_label, output_edit, output_btn,
            btn_export, btn_import, save_btn
        ]:
            layout.addWidget(widget)

        dialog.setLayout(layout)
        dialog.exec_()

Krita.instance().addExtension(ComfyTilesExtension(Krita.instance()))
