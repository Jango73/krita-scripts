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
        self._init_parameter_sets_ui()

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

        workflow_tab = QtWidgets.QWidget()
        workflow_tab_layout = QtWidgets.QVBoxLayout(workflow_tab)
        workflow_scroll = QtWidgets.QScrollArea()
        workflow_scroll.setWidgetResizable(True)
        workflow_inner = QtWidgets.QWidget()
        workflow_layout = QtWidgets.QVBoxLayout(workflow_inner)
        workflow_layout.addWidget(self._build_parameter_sets_group())
        workflow_layout.addWidget(self._build_prompts_group())
        workflow_layout.addWidget(self._build_parameters_group())
        workflow_layout.addStretch(1)
        workflow_scroll.setWidget(workflow_inner)
        workflow_tab_layout.addWidget(workflow_scroll)

        log_tab = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(self._build_log_group())

        manual_tab = QtWidgets.QWidget()
        manual_layout = QtWidgets.QVBoxLayout(manual_tab)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(self._build_manual_group())

        self.tabs.addTab(server_tab, "Server & Workflows")
        self.tabs.addTab(workflow_tab, "Workflow")
        self.tabs.addTab(manual_tab, "Manual")
        self.log_tab_index = self.tabs.addTab(log_tab, "Log")

        main_layout.addWidget(self.tabs)
        main_layout.addLayout(self._build_status_bar())
        main_layout.addLayout(self._build_actions())

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

        layout.addWidget(QtWidgets.QLabel("New layer opacity (0-1)"), 0, 0)
        layout.addWidget(self.opacity_spin, 0, 1)
        layout.addWidget(QtWidgets.QLabel("Edge fade ratio (0-0.5)"), 1, 0)
        layout.addWidget(self.fade_spin, 1, 1)
        layout.setColumnStretch(2, 1)
        return group

    def _build_prompts_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Prompts")
        layout = QtWidgets.QGridLayout(group)

        self.global_prompt_edit = QtWidgets.QLineEdit()
        layout.addWidget(QtWidgets.QLabel("Global prompt"), 0, 0)
        layout.addWidget(self.global_prompt_edit, 0, 1)

        self.region_prompts_edits: List[QtWidgets.QLineEdit] = []
        for idx in range(4):
            edit = QtWidgets.QLineEdit()
            self.region_prompts_edits.append(edit)
            layout.addWidget(QtWidgets.QLabel(f"Region prompt {idx + 1}"), idx + 1, 0)
            layout.addWidget(edit, idx + 1, 1)
        return group

    def _build_parameter_sets_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Parameter sets")
        layout = QtWidgets.QVBoxLayout(group)

        self.parameter_sets_list = QtWidgets.QListWidget()
        self.parameter_sets_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.parameter_sets_list)

        btn_row = QtWidgets.QHBoxLayout()
        self.load_set_btn = QtWidgets.QPushButton("Load")
        self.save_set_btn = QtWidgets.QPushButton("Save as new")
        self.overwrite_set_btn = QtWidgets.QPushButton("Overwrite selected")
        self.delete_set_btn = QtWidgets.QPushButton("Delete")
        self.clear_sets_btn = QtWidgets.QPushButton("Delete all")

        self.load_set_btn.clicked.connect(self._load_selected_set)
        self.save_set_btn.clicked.connect(self._save_set_as_new)
        self.overwrite_set_btn.clicked.connect(self._overwrite_selected_set)
        self.delete_set_btn.clicked.connect(self._delete_selected_set)
        self.clear_sets_btn.clicked.connect(self._delete_all_sets)

        btn_row.addStretch(1)
        btn_row.addWidget(self.load_set_btn)
        btn_row.addWidget(self.save_set_btn)
        btn_row.addWidget(self.overwrite_set_btn)
        btn_row.addWidget(self.delete_set_btn)
        btn_row.addWidget(self.clear_sets_btn)
        layout.addLayout(btn_row)
        return group

    def _build_parameters_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Workflow parameters")
        layout = QtWidgets.QGridLayout(group)

        self.global_params = self._make_param_table()
        add_global = QtWidgets.QPushButton("Add")
        remove_global = QtWidgets.QPushButton("Remove")
        clear_global = QtWidgets.QPushButton("Clear")
        add_global.clicked.connect(lambda: self._add_param_row(self.global_params))
        remove_global.clicked.connect(lambda: self._remove_param_row(self.global_params))
        clear_global.clicked.connect(lambda: self._confirm_and_clear(self.global_params, "Clear global parameters?"))
        global_btn_row = QtWidgets.QHBoxLayout()
        global_btn_row.addWidget(add_global)
        global_btn_row.addWidget(remove_global)
        global_btn_row.addWidget(clear_global)
        global_btn_row.addStretch(1)

        self.region_params = self._make_param_table()
        add_region = QtWidgets.QPushButton("Add")
        remove_region = QtWidgets.QPushButton("Remove")
        clear_region = QtWidgets.QPushButton("Clear")
        add_region.clicked.connect(lambda: self._add_param_row(self.region_params))
        remove_region.clicked.connect(lambda: self._remove_param_row(self.region_params))
        clear_region.clicked.connect(lambda: self._confirm_and_clear(self.region_params, "Clear region parameters?"))
        region_btn_row = QtWidgets.QHBoxLayout()
        region_btn_row.addWidget(add_region)
        region_btn_row.addWidget(remove_region)
        region_btn_row.addWidget(clear_region)
        region_btn_row.addStretch(1)
        copy_global_to_region = QtWidgets.QPushButton("Copy global to region")
        copy_global_to_region.clicked.connect(self._copy_global_params_to_region)

        layout.addWidget(QtWidgets.QLabel("Global parameters"), 0, 0)
        layout.addWidget(self.global_params, 1, 0, 1, 2)
        layout.addLayout(global_btn_row, 2, 0, 1, 2)

        layout.addWidget(QtWidgets.QLabel("Region parameters"), 3, 0)
        layout.addWidget(self.region_params, 4, 0, 1, 2)
        layout.addLayout(region_btn_row, 5, 0, 1, 2)
        layout.addWidget(copy_global_to_region, 6, 0, 1, 2)

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

    def _build_actions(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()
        layout.addStretch(1)
        self.enhance_regions_btn = QtWidgets.QPushButton("Regions")
        self.enhance_btn = QtWidgets.QPushButton("Go")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setMaximumHeight(self.cancel_btn.sizeHint().height())
        self.stop_btn.setSizePolicy(self.cancel_btn.sizePolicy())
        self.stop_btn.setMaximumHeight(self.cancel_btn.sizeHint().height())
        self.stop_btn.setEnabled(False)

        self.cancel_stop_stack = QtWidgets.QStackedLayout()
        self.cancel_stop_stack.setStackingMode(QtWidgets.QStackedLayout.StackOne)
        self.cancel_stop_stack.addWidget(self.cancel_btn)
        self.cancel_stop_stack.addWidget(self.stop_btn)
        self.cancel_stop_stack.setCurrentWidget(self.cancel_btn)
        stack_container = QtWidgets.QWidget()
        stack_container.setLayout(self.cancel_stop_stack)
        stack_container.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        stack_container.setMaximumHeight(self.cancel_btn.sizeHint().height())

        layout.addWidget(self.enhance_regions_btn)
        layout.addWidget(self.enhance_btn)
        layout.addSpacing(12)
        layout.addWidget(stack_container)
        return layout

    def _build_status_bar(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Status:"))
        self.status_label = QtWidgets.QLabel("Idle")
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        return layout

    def _make_param_table(self) -> QtWidgets.QTableWidget:
        table = QtWidgets.QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Parameter name", "Value"])
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setMinimumHeight(260)
        table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        return table

    def _add_param_row(self, table: QtWidgets.QTableWidget) -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))

    def _remove_param_row(self, table: QtWidgets.QTableWidget) -> None:
        current = table.currentRow()
        if current >= 0:
            table.removeRow(current)

    def _clear_param_table(self, table: QtWidgets.QTableWidget) -> None:
        table.setRowCount(0)

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
            "global": self._read_table(self.global_params),
            "regions": self._read_table(self.region_params),
            "opacity": self.opacity_spin.value(),
            "fade_ratio": self.fade_spin.value(),
        }

    def set_parameters(self, params: Dict[str, List[Dict[str, str]]]) -> None:
        self._fill_table(self.global_params, params.get("global", []))
        self._fill_table(self.region_params, params.get("regions", []))
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
        return {
            "global": [self.global_prompt_edit.text()],
            "regions": [edit.text() for edit in self.region_prompts_edits],
        }

    def set_prompts(self, prompts: Dict[str, List[str]]) -> None:
        if not prompts:
            return
        global_prompt = ""
        if isinstance(prompts.get("global"), list) and prompts["global"]:
            global_prompt = prompts["global"][0] or ""
        elif isinstance(prompts.get("global"), str):
            global_prompt = prompts.get("global") or ""
        self.global_prompt_edit.setText(global_prompt)

        regions = prompts.get("regions") or []
        for idx, edit in enumerate(self.region_prompts_edits):
            value = regions[idx] if idx < len(regions) else ""
            edit.setText(value or "")

    def get_config(self) -> Dict[str, str]:
        return {
            "server_url": self.server_edit.text(),
            "workflows_dir": self.workflow_dir_edit.text(),
            "output_dir": self.output_dir_edit.text(),
            "workflow_global": self.global_workflow_edit.text(),
            "workflow_region": self.region_workflow_edit.text(),
        }

    def _read_table(self, table: QtWidgets.QTableWidget) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            value_item = table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            value = value_item.text().strip() if value_item else ""
            if name and value:
                rows.append({"target": name, "value": value})
        return rows

    def _fill_table(self, table: QtWidgets.QTableWidget, rows: List[Dict[str, str]]) -> None:
        table.setRowCount(0)
        for row_data in rows:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(row_data.get("target", "")))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(row_data.get("value", "")))

    def append_log(self, message: str) -> None:
        self.log_area.append(message)

    def append_log_dot(self) -> None:
        cursor = self.log_area.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(".")
        self.log_area.setTextCursor(cursor)
        self.log_area.ensureCursorVisible()

    def set_status(self, message: str) -> None:
        if hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(message)

    def set_running(self, running: bool) -> None:
        if running:
            self.stop_btn.setEnabled(True)
            if hasattr(self, "cancel_stop_stack"):
                self.cancel_stop_stack.setCurrentWidget(self.stop_btn)
            self.enhance_btn.setEnabled(False)
            self.enhance_regions_btn.setEnabled(False)
        else:
            self.stop_btn.setEnabled(False)
            if hasattr(self, "cancel_stop_stack"):
                self.cancel_stop_stack.setCurrentWidget(self.cancel_btn)
            self.enhance_btn.setEnabled(True)
            self.enhance_regions_btn.setEnabled(True)

    def clear_log(self) -> None:
        self.log_area.clear()

    def copy_log(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.log_area.toPlainText())

    def _init_parameter_sets_ui(self) -> None:
        """Prepare parameter set controls based on availability of a manager."""
        widgets = [
            getattr(self, "parameter_sets_list", None),
            getattr(self, "load_set_btn", None),
            getattr(self, "save_set_btn", None),
            getattr(self, "overwrite_set_btn", None),
            getattr(self, "delete_set_btn", None),
        ]
        if not self.parameter_sets:
            for widget in widgets:
                if widget:
                    widget.setEnabled(False)
            return
        self._refresh_parameter_sets_list()
        if self.parameter_sets_list:
            self.parameter_sets_list.itemDoubleClicked.connect(lambda _: self._load_selected_set())

    def _refresh_parameter_sets_list(self) -> None:
        if not self.parameter_sets or not hasattr(self, "parameter_sets_list"):
            return
        self.parameter_sets_list.clear()
        for name in self.parameter_sets.list_names():
            self.parameter_sets_list.addItem(name)

    def _selected_set_name(self) -> Optional[str]:
        if not hasattr(self, "parameter_sets_list"):
            return None
        item = self.parameter_sets_list.currentItem()
        return item.text() if item else None

    def _save_set_as_new(self) -> None:
        if not self.parameter_sets:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Save parameter set", "Set name:")
        if not ok or not name.strip():
            return
        self._save_parameter_set(name.strip())

    def _overwrite_selected_set(self) -> None:
        if not self.parameter_sets:
            return
        name = self._selected_set_name()
        if not name:
            return
        self._save_parameter_set(name)

    def _save_parameter_set(self, name: str) -> None:
        prompts = self.get_prompts()
        params = self.get_parameters()
        payload = {
            "global": params.get("global", []),
            "regions": params.get("regions", []),
        }
        self.parameter_sets.save_set(name, prompts, payload)
        self._refresh_parameter_sets_list()
        self._write_log(f"Saved parameter set '{name}'")

    def _load_selected_set(self) -> None:
        if not self.parameter_sets:
            return
        name = self._selected_set_name()
        if not name:
            return
        data = self.parameter_sets.get(name)
        if not data:
            return
        prompts = data.get("prompts") or {}
        params = data.get("params") or {}
        self.set_prompts(prompts)
        self.set_parameters({
            "global": params.get("global", []),
            "regions": params.get("regions", []),
        })
        self._write_log(f"Loaded parameter set '{name}'")

    def _delete_selected_set(self) -> None:
        if not self.parameter_sets:
            return
        name = self._selected_set_name()
        if not name:
            return
        self.parameter_sets.delete(name)
        self._refresh_parameter_sets_list()
        self._write_log(f"Deleted parameter set '{name}'")

    def _delete_all_sets(self) -> None:
        if not self.parameter_sets:
            return
        confirmed = self._ask_confirmation(
            "Delete all parameter sets",
            "Are you sure you want to delete all parameter sets?",
        )
        if not confirmed:
            return
        self.parameter_sets.sets.clear()
        self.parameter_sets.save()
        self._refresh_parameter_sets_list()
        self._write_log("Deleted all parameter sets")

    def _write_log(self, message: str) -> None:
        if self._logger:
            self._logger(message)

    def _copy_global_params_to_region(self) -> None:
        params = self._read_table(self.global_params)
        self._fill_table(self.region_params, params)

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
        self._fill_table(self.global_params, [dict(p) for p in DEFAULT_GLOBAL_PARAMS])
        self._fill_table(self.region_params, [dict(p) for p in DEFAULT_REGION_PARAMS])
