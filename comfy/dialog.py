"""UI dialog definitions for the ComfyUI enhancer."""

from typing import Callable, Dict, List, Optional
from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore

from .config_manager import (
    DEFAULT_WORKFLOW_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_GLOBAL_PARAMS,
    DEFAULT_SERVER_URL,
    DEFAULT_REGION_PARAMS,
)
from .parameter_set_manager import ParameterSetManager


class ComfyUIDialog(QtWidgets.QDialog):
    """Main dialog handling configuration, prompts, and execution."""

    reset_defaults_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        logger: Optional[Callable[[str], None]] = None,
        parameter_sets: Optional[ParameterSetManager] = None,
    ):
        super().__init__(parent)
        self._logger = logger
        self.parameter_sets = parameter_sets
        self.setWindowTitle("ComfyUI Image Enhance")
        self._resize_relatively()
        self._build_ui()

    def _resize_relatively(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            width = int(available.width() * 0.55)
            height = int(available.height() * 0.8)
            self.resize(width, height)
            self.setMaximumHeight(int(available.height() * 0.95))
        else:
            self.resize(self.sizeHint())

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        self.log_tab_index = -1

        server_tab = QtWidgets.QWidget()
        server_layout = QtWidgets.QVBoxLayout(server_tab)
        server_layout.addWidget(self._build_server_group())
        server_layout.addWidget(self._build_workflow_group())
        server_layout.addWidget(self._build_misc_group())
        reset_btn = QtWidgets.QPushButton("Reset to defaults")
        reset_btn.clicked.connect(self._reset_config_defaults)
        server_layout.addWidget(reset_btn)
        server_layout.addStretch(1)

        log_tab = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(self._build_log_group())

        manual_tab = QtWidgets.QWidget()
        manual_layout = QtWidgets.QVBoxLayout(manual_tab)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(self._build_manual_group())

        self.tabs.addTab(manual_tab, "Manual")
        self.tabs.addTab(server_tab, "Settings")
        self.log_tab_index = self.tabs.addTab(log_tab, "Log")

        main_layout.addWidget(self.tabs)

    def _build_server_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Server and paths")
        layout = QtWidgets.QGridLayout(group)

        self.server_edit = QtWidgets.QLineEdit(DEFAULT_SERVER_URL)

        layout.addWidget(QtWidgets.QLabel("Server URL"), 0, 0)
        layout.addWidget(self.server_edit, 0, 1, 1, 2)
        return group

    def _build_manual_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Manual")
        layout = QtWidgets.QVBoxLayout(group)
        self.manual_view = QtWidgets.QTextBrowser()
        self.manual_view.setOpenExternalLinks(True)
        layout.addWidget(self.manual_view)
        self._load_manual()
        return group

    def _load_manual(self) -> None:
        """Load Manual.html if available."""
        manual_path = Path(__file__).resolve().parent / "Manual.html"
        if manual_path.exists():
            self.manual_view.setSource(QtCore.QUrl.fromLocalFile(str(manual_path)))
        else:
            self.manual_view.setText("Manual not found.")

    def _build_workflow_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Workflows")
        layout = QtWidgets.QGridLayout(group)

        self.workflow_dir_edit = QtWidgets.QLineEdit(DEFAULT_WORKFLOW_DIR)
        browse_dir = QtWidgets.QPushButton("Browse")
        browse_dir.clicked.connect(self._browse_workflow_dir)

        self.output_dir_edit = QtWidgets.QLineEdit(DEFAULT_OUTPUT_DIR)
        browse_output_dir = QtWidgets.QPushButton("Browse")
        browse_output_dir.clicked.connect(self._browse_output_dir)

        self.global_workflow_edit = QtWidgets.QLineEdit("Universal.json")
        self.region_workflow_edit = QtWidgets.QLineEdit("Universal.json")

        layout.addWidget(QtWidgets.QLabel("Workflows folder"), 0, 0)
        layout.addWidget(self.workflow_dir_edit, 0, 1)
        layout.addWidget(browse_dir, 0, 2)

        layout.addWidget(QtWidgets.QLabel("Output folder"), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1, 1, 2)
        layout.addWidget(browse_output_dir, 1, 2)

        layout.addWidget(QtWidgets.QLabel("Global workflow name"), 2, 0)
        layout.addWidget(self.global_workflow_edit, 2, 1, 1, 2)
        layout.addWidget(QtWidgets.QLabel("Region workflow name"), 3, 0)
        layout.addWidget(self.region_workflow_edit, 3, 1, 1, 2)
        return group

    def _build_misc_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Miscellaneous")
        layout = QtWidgets.QGridLayout(group)

        self.opacity_spin = QtWidgets.QDoubleSpinBox()
        self.opacity_spin.setRange(0.0, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(0.8)
        self.opacity_spin.setDecimals(2)

        self.fade_spin = QtWidgets.QDoubleSpinBox()
        self.fade_spin.setRange(0.0, 0.5)
        self.fade_spin.setSingleStep(0.01)
        self.fade_spin.setValue(0.1)
        self.fade_spin.setDecimals(3)

        self.delete_output_checkbox = QtWidgets.QCheckBox("Delete output image after import")

        layout.addWidget(QtWidgets.QLabel("New layer opacity (0-1)"), 0, 0)
        layout.addWidget(self.opacity_spin, 0, 1)
        layout.addWidget(QtWidgets.QLabel("Edge fade ratio (0-0.5)"), 1, 0)
        layout.addWidget(self.fade_spin, 1, 1)
        layout.addWidget(self.delete_output_checkbox, 2, 0, 1, 2)
        layout.setColumnStretch(2, 1)
        return group

    def _build_log_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Log")
        layout = QtWidgets.QVBoxLayout(group)
        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QtGui.QFont("Monospace"))
        self.log_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        clear_btn = QtWidgets.QPushButton("Clear log")
        clear_btn.clicked.connect(self.clear_log)
        copy_btn = QtWidgets.QPushButton("Copy log")
        copy_btn.clicked.connect(self.copy_log)

        layout.addWidget(self.log_area)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)
        layout.setStretch(0, 1)
        layout.setContentsMargins(6, 6, 6, 6)
        return group

    def _ask_confirmation(self, title: str, question: str) -> bool:
        reply = QtWidgets.QMessageBox.question(
            self,
            title,
            question,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return reply == QtWidgets.QMessageBox.Yes

    def _confirm_and_clear(self, table: QtWidgets.QTableWidget, question: str) -> None:
        if self._ask_confirmation("Confirm", question):
            self._clear_param_table(table)

    def _browse_workflow_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select workflows folder")
        if directory:
            self.workflow_dir_edit.setText(directory)

    def _browse_output_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder")
        if directory:
            self.output_dir_edit.setText(directory)

    def get_parameters(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "global": [],
            "regions": [],
            "opacity": self.opacity_spin.value(),
            "fade_ratio": self.fade_spin.value(),
        }

    def set_parameters(self, params: Dict[str, List[Dict[str, str]]]) -> None:
        if "opacity" in params:
            try:
                self.opacity_spin.setValue(float(params["opacity"]))
            except Exception:
                pass
        if "fade_ratio" in params:
            try:
                self.fade_spin.setValue(float(params["fade_ratio"]))
            except Exception:
                pass

    def get_prompts(self) -> Dict[str, List[str]]:
        return {"global": [""], "regions": ["", "", "", ""]}

    def set_prompts(self, prompts: Dict[str, List[str]]) -> None:
        return

    def get_config(self) -> Dict[str, object]:
        return {
            "server_url": self.server_edit.text(),
            "workflows_dir": self.workflow_dir_edit.text(),
            "output_dir": self.output_dir_edit.text(),
            "workflow_global": self.global_workflow_edit.text(),
            "workflow_region": self.region_workflow_edit.text(),
            "delete_output_after_import": self.delete_output_checkbox.isChecked(),
        }

    def append_log(self, message: str) -> None:
        self.log_area.append(message)

    def append_log_dot(self) -> None:
        cursor = self.log_area.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(".")
        self.log_area.setTextCursor(cursor)
        self.log_area.ensureCursorVisible()

    def set_status(self, message: str) -> None:
        return

    def set_running(self, running: bool) -> None:
        return

    def clear_log(self) -> None:
        self.log_area.clear()

    def copy_log(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.log_area.toPlainText())

    def _reset_config_defaults(self) -> None:
        confirmed = self._ask_confirmation(
            "Reset configuration",
            "Reset configuration to defaults? Current settings will be overwritten.",
        )
        if not confirmed:
            return
        self.server_edit.setText(DEFAULT_SERVER_URL)
        self.workflow_dir_edit.setText(DEFAULT_WORKFLOW_DIR)
        self.output_dir_edit.setText(DEFAULT_OUTPUT_DIR)
        self.global_workflow_edit.setText("Universal.json")
        self.region_workflow_edit.setText("Universal.json")
        self.opacity_spin.setValue(0.8)
        self.fade_spin.setValue(0.1)
        self.delete_output_checkbox.setChecked(False)
        self.reset_defaults_requested.emit()
