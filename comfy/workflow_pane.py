"""Shared workflow UI pane for dock and dialog."""

from typing import Callable, Dict, List, Optional
from PyQt5 import QtWidgets, QtCore

from .parameter_set_manager import ParameterSetManager


class WorkflowPane(QtWidgets.QWidget):
    """Encapsulates the workflow controls (prompts, params, actions)."""

    enhance_requested = QtCore.pyqtSignal(bool)  # True when regions-only
    stop_requested = QtCore.pyqtSignal()
    settings_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        logger: Optional[Callable[[str], None]] = None,
        parameter_sets: Optional[ParameterSetManager] = None,
    ) -> None:
        super().__init__(parent)
        self._logger = logger
        self.parameter_sets = parameter_sets
        self._build_ui()
        self._init_parameter_sets_ui()

    def set_parameter_manager(self, parameter_sets: Optional[ParameterSetManager]) -> None:
        """Inject a parameter manager after construction."""
        self.parameter_sets = parameter_sets
        self._init_parameter_sets_ui()

    def set_logger(self, logger: Optional[Callable[[str], None]]) -> None:
        """Inject a logger after construction."""
        self._logger = logger

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        inner = QtWidgets.QWidget()
        inner_layout = QtWidgets.QVBoxLayout(inner)
        inner_layout.addWidget(self._build_parameter_sets_group())
        inner_layout.addWidget(self._build_prompts_group())
        inner_layout.addWidget(self._build_parameters_group())
        inner_layout.addStretch(1)
        scroll.setWidget(inner)

        layout.addWidget(scroll)
        layout.addLayout(self._build_status_bar())
        layout.addLayout(self._build_actions())

    def _build_parameter_sets_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Parameter sets")
        layout = QtWidgets.QVBoxLayout(group)

        self.parameter_sets_list = QtWidgets.QListWidget()
        self.parameter_sets_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.parameter_sets_list)

        btn_row = QtWidgets.QVBoxLayout()
        top_row = QtWidgets.QHBoxLayout()
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

        top_row.addWidget(self.load_set_btn)
        top_row.addWidget(self.save_set_btn)
        top_row.addWidget(self.overwrite_set_btn)
        top_row.addStretch(1)
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addWidget(self.delete_set_btn)
        bottom_row.addWidget(self.clear_sets_btn)
        bottom_row.addStretch(1)
        btn_row.addLayout(top_row)
        btn_row.addLayout(bottom_row)
        layout.addLayout(btn_row)
        return group

    def _build_prompts_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Prompts")
        layout = QtWidgets.QGridLayout(group)

        self.global_prompt_edit = QtWidgets.QPlainTextEdit()
        line_height = self.global_prompt_edit.fontMetrics().lineSpacing()
        self.global_prompt_edit.setFixedHeight(line_height * 2 + 10)
        layout.addWidget(QtWidgets.QLabel("Global prompt"), 0, 0)
        layout.addWidget(self.global_prompt_edit, 0, 1)

        self.region_prompts_edits: List[QtWidgets.QLineEdit] = []
        for idx in range(4):
            edit = QtWidgets.QLineEdit()
            self.region_prompts_edits.append(edit)
            layout.addWidget(QtWidgets.QLabel(f"Region prompt {idx + 1}"), idx + 1, 0)
            layout.addWidget(edit, idx + 1, 1)
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

    def _build_actions(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QVBoxLayout()
        top_row = QtWidgets.QHBoxLayout()
        top_row.addStretch(1)
        self.enhance_regions_btn = QtWidgets.QPushButton("Regions")
        self.settings_btn = QtWidgets.QPushButton("Settings")
        self.enhance_btn = QtWidgets.QPushButton("Go")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        top_row.addWidget(self.settings_btn)
        top_row.addWidget(self.enhance_btn)
        top_row.addWidget(self.enhance_regions_btn)
        top_row.addWidget(self.stop_btn)
        layout.addLayout(top_row)

        self.enhance_btn.clicked.connect(lambda: self.enhance_requested.emit(False))
        self.enhance_regions_btn.clicked.connect(lambda: self.enhance_requested.emit(True))
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
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
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
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

    def _copy_global_params_to_region(self) -> None:
        params = self._read_table(self.global_params)
        self._fill_table(self.region_params, params)

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

    def get_prompts(self) -> Dict[str, List[str]]:
        return {
            "global": [self.global_prompt_edit.toPlainText()],
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
        self.global_prompt_edit.setPlainText(global_prompt)

        regions = prompts.get("regions") or []
        for idx, edit in enumerate(self.region_prompts_edits):
            value = regions[idx] if idx < len(regions) else ""
            edit.setText(value or "")

    def get_parameters(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "global": self._read_table(self.global_params),
            "regions": self._read_table(self.region_params),
        }

    def set_parameters(self, params: Dict[str, List[Dict[str, str]]]) -> None:
        self._fill_table(self.global_params, params.get("global", []))
        self._fill_table(self.region_params, params.get("regions", []))

    def set_running(self, running: bool) -> None:
        if running:
            self.stop_btn.setEnabled(True)
            self.enhance_btn.setEnabled(False)
            self.enhance_regions_btn.setEnabled(False)
            self.settings_btn.setEnabled(False)
        else:
            self.stop_btn.setEnabled(False)
            self.enhance_btn.setEnabled(True)
            self.enhance_regions_btn.setEnabled(True)
            self.settings_btn.setEnabled(True)

    def set_status(self, message: str) -> None:
        if hasattr(self, "status_label") and self.status_label:
            self.status_label.setText(message)

    def _init_parameter_sets_ui(self) -> None:
        """Prepare parameter set controls based on availability of a manager."""
        widgets = [
            getattr(self, "parameter_sets_list", None),
            getattr(self, "load_set_btn", None),
            getattr(self, "save_set_btn", None),
            getattr(self, "overwrite_set_btn", None),
            getattr(self, "delete_set_btn", None),
            getattr(self, "clear_sets_btn", None),
        ]
        if not self.parameter_sets:
            for widget in widgets:
                if widget:
                    widget.setEnabled(False)
            return
        for widget in widgets:
            if widget:
                widget.setEnabled(True)
        self._refresh_parameter_sets_list()
        if self.parameter_sets_list:
            self.parameter_sets_list.itemDoubleClicked.connect(lambda _: self._load_selected_set())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_param_tables()

    def _resize_param_tables(self) -> None:
        for table in (getattr(self, "global_params", None), getattr(self, "region_params", None)):
            if not table:
                continue
            width = table.viewport().width()
            if width <= 0:
                continue
            left_width = int(width * 2 / 3)
            right_width = max(1, width - left_width)
            table.setColumnWidth(0, left_width)
            table.setColumnWidth(1, right_width)

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
