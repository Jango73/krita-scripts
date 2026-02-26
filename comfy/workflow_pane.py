"""Shared workflow UI pane for dock and dialog."""

from typing import Callable, Dict, List, Optional, Tuple
from PyQt5 import QtWidgets, QtCore

from .parameter_set_manager import ParameterSetManager
from .config_manager import (
    DEFAULT_GLOBAL_PARAMS,
    DEFAULT_GLOBAL_PARAMS_SIMPLE,
    DEFAULT_REGION_PARAMS,
    DEFAULT_REGION_PARAMS_SIMPLE,
    DEFAULT_DETAIL_VALUE,
    DETAIL_MIN,
    DETAIL_MAX,
)


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
        self._mode = "advanced"
        self._params_by_mode = {
            "simple_enhance": {"global": [], "regions": []},
            "simple_creation": {"global": [], "regions": []},
            "advanced": {"global": [], "regions": []},
        }
        self._simple_params_visible = False
        self._prompt_sync_guard = False
        self._prompt_editor_buttons: List[QtWidgets.QToolButton] = []
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
        inner_layout.addLayout(self._build_mode_toggle_row())
        self.simple_controls_group = self._build_simple_controls_group()
        inner_layout.addWidget(self.simple_controls_group)
        inner_layout.addWidget(self._build_parameter_sets_group())
        inner_layout.addLayout(self._build_show_hide_row())
        self.prompts_group = self._build_prompts_group()
        inner_layout.addWidget(self.prompts_group)
        self.parameters_group = self._build_parameters_group()
        inner_layout.addWidget(self.parameters_group)
        inner_layout.addStretch(1)
        scroll.setWidget(inner)

        layout.addWidget(scroll)
        layout.addLayout(self._build_status_bar())
        layout.addLayout(self._build_actions())
        self._apply_mode_ui()
        self._schedule_param_resize()

    def _build_parameter_sets_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Parameter sets")
        group.setFixedHeight(200)
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

    def _build_mode_toggle_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.mode_toggle_btn = QtWidgets.QPushButton()
        self.mode_toggle_btn.clicked.connect(self._toggle_mode)
        row.addWidget(self.mode_toggle_btn)
        row.addStretch(1)
        return row

    def _build_show_hide_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.toggle_params_btn = QtWidgets.QPushButton()
        self.toggle_params_btn.clicked.connect(self._toggle_params_visibility)
        row.addWidget(self.toggle_params_btn)
        row.addStretch(1)
        return row

    def _build_prompts_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Prompts")
        layout = QtWidgets.QGridLayout(group)

        self.global_prompt_edit = QtWidgets.QPlainTextEdit()
        self.global_prompt_edit.textChanged.connect(self._sync_simple_creation_prompt_from_global)
        line_height = self.global_prompt_edit.fontMetrics().lineSpacing()
        self.global_prompt_edit.setFixedHeight(line_height * 2 + 10)
        layout.addWidget(QtWidgets.QLabel("Global prompt"), 0, 0)
        layout.addLayout(
            self._build_prompt_editor_row(
                self.global_prompt_edit,
                "Global prompt editor",
                self.global_prompt_edit.toPlainText,
                self.global_prompt_edit.setPlainText,
            ),
            0,
            1,
        )

        self.region_prompts_edits: List[QtWidgets.QLineEdit] = []
        for idx in range(4):
            edit = QtWidgets.QLineEdit()
            self.region_prompts_edits.append(edit)
            layout.addWidget(QtWidgets.QLabel(f"Region prompt {idx + 1}"), idx + 1, 0)
            layout.addLayout(
                self._build_prompt_editor_row(
                    edit,
                    f"Region prompt {idx + 1} editor",
                    edit.text,
                    edit.setText,
                ),
                idx + 1,
                1,
            )
        return group

    def _build_simple_controls_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Simple controls")
        layout = QtWidgets.QGridLayout(group)
        self.enhance_slider, enhance_spin = self._build_slider_row(0, 100, 20)
        self.enhance_spin = enhance_spin
        self.random_seed_slider, seed_spin = self._build_slider_row(0, 10000, 0)
        self.creation_detail_slider, creation_detail_spin = self._build_slider_row(
            DETAIL_MIN,
            DETAIL_MAX,
            DEFAULT_DETAIL_VALUE,
        )
        self.creation_detail_spin = creation_detail_spin
        self.simple_enhance_label = QtWidgets.QLabel("Enhance")
        layout.addWidget(self.simple_enhance_label, 0, 0)
        layout.addWidget(self.enhance_slider, 0, 1)
        layout.addWidget(self.enhance_spin, 0, 2)
        self.image_size_label = QtWidgets.QLabel("Image size")
        self.image_size_combo = QtWidgets.QComboBox()
        self.image_size_combo.addItems(["Small", "Medium", "Large"])
        self.image_size_combo.setCurrentText("Medium")
        layout.addWidget(self.image_size_label, 1, 0)
        layout.addWidget(self.image_size_combo, 1, 1, 1, 2)
        self.simple_creation_prompt_label = QtWidgets.QLabel("Prompt")
        self.simple_creation_prompt_edit = QtWidgets.QLineEdit()
        self.simple_creation_prompt_edit.textChanged.connect(self._sync_global_prompt_from_simple_creation)
        layout.addWidget(self.simple_creation_prompt_label, 2, 0)
        layout.addWidget(self.simple_creation_prompt_edit, 2, 1, 1, 2)
        self.simple_creation_detail_label = QtWidgets.QLabel("Detail")
        layout.addWidget(self.simple_creation_detail_label, 3, 0)
        layout.addWidget(self.creation_detail_slider, 3, 1)
        layout.addWidget(self.creation_detail_spin, 3, 2)
        layout.addWidget(QtWidgets.QLabel("Random Seed"), 4, 0)
        layout.addWidget(self.random_seed_slider, 4, 1)
        layout.addWidget(seed_spin, 4, 2)
        layout.setColumnStretch(1, 1)
        return group

    def _build_slider_row(
        self,
        minimum: int,
        maximum: int,
        default: int,
    ) -> Tuple[QtWidgets.QSlider, QtWidgets.QSpinBox]:
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(default)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    def _build_parameters_group(self) -> QtWidgets.QGroupBox:
        self.parameters_group = QtWidgets.QGroupBox("Workflow parameters")
        layout = QtWidgets.QGridLayout(self.parameters_group)

        self.global_params = self._make_param_table()
        self.add_global_btn = QtWidgets.QPushButton("Add")
        self.remove_global_btn = QtWidgets.QPushButton("Remove")
        self.clear_global_btn = QtWidgets.QPushButton("Clear")
        self.reset_global_btn = QtWidgets.QPushButton("Reset")
        self.add_global_btn.clicked.connect(lambda: self._add_param_row(self.global_params))
        self.remove_global_btn.clicked.connect(lambda: self._remove_param_row(self.global_params))
        self.clear_global_btn.clicked.connect(lambda: self._confirm_and_clear(self.global_params, "Clear global parameters?"))
        self.reset_global_btn.clicked.connect(lambda: self._reset_param_table("global"))
        global_btn_row = QtWidgets.QHBoxLayout()
        global_btn_row.addWidget(self.add_global_btn)
        global_btn_row.addWidget(self.remove_global_btn)
        global_btn_row.addWidget(self.clear_global_btn)
        global_btn_row.addWidget(self.reset_global_btn)
        global_btn_row.addStretch(1)

        self.region_params = self._make_param_table()
        self.add_region_btn = QtWidgets.QPushButton("Add")
        self.remove_region_btn = QtWidgets.QPushButton("Remove")
        self.clear_region_btn = QtWidgets.QPushButton("Clear")
        self.reset_region_btn = QtWidgets.QPushButton("Reset")
        self.add_region_btn.clicked.connect(lambda: self._add_param_row(self.region_params))
        self.remove_region_btn.clicked.connect(lambda: self._remove_param_row(self.region_params))
        self.clear_region_btn.clicked.connect(lambda: self._confirm_and_clear(self.region_params, "Clear region parameters?"))
        self.reset_region_btn.clicked.connect(lambda: self._reset_param_table("regions"))
        region_btn_row = QtWidgets.QHBoxLayout()
        region_btn_row.addWidget(self.add_region_btn)
        region_btn_row.addWidget(self.remove_region_btn)
        region_btn_row.addWidget(self.clear_region_btn)
        region_btn_row.addWidget(self.reset_region_btn)
        region_btn_row.addStretch(1)
        self.copy_global_to_region_btn = QtWidgets.QPushButton("Copy global to region")
        self.copy_global_to_region_btn.clicked.connect(self._copy_global_params_to_region)

        self.global_params_label = QtWidgets.QLabel("Global parameters")
        self.region_params_label = QtWidgets.QLabel("Region parameters")
        layout.addWidget(self.global_params_label, 0, 0)
        layout.addWidget(self.global_params, 1, 0, 1, 2)
        layout.addLayout(global_btn_row, 2, 0, 1, 2)

        layout.addWidget(self.region_params_label, 3, 0)
        layout.addWidget(self.region_params, 4, 0, 1, 2)
        layout.addLayout(region_btn_row, 5, 0, 1, 2)
        layout.addWidget(self.copy_global_to_region_btn, 6, 0, 1, 2)

        return self.parameters_group

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

    def _build_prompt_editor_row(
        self,
        edit_widget: QtWidgets.QWidget,
        title: str,
        get_text: Callable[[], str],
        set_text: Callable[[str], None],
    ) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.addWidget(edit_widget)
        editor_btn = QtWidgets.QToolButton()
        editor_btn.setText("...")
        editor_btn.setToolTip("Edit prompt in a modal dialog")
        editor_btn.clicked.connect(lambda: self._open_prompt_editor(title, get_text, set_text))
        row.addWidget(editor_btn)
        self._prompt_editor_buttons.append(editor_btn)
        return row

    def _open_prompt_editor(
        self,
        title: str,
        get_text: Callable[[], str],
        set_text: Callable[[str], None],
    ) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        layout = QtWidgets.QVBoxLayout(dialog)
        text_edit = QtWidgets.QPlainTextEdit()
        text_edit.setPlainText(get_text())
        text_edit.setMinimumSize(480, 220)
        layout.addWidget(text_edit)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            set_text(text_edit.toPlainText())

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

    def _sync_simple_creation_prompt_from_global(self) -> None:
        if self._prompt_sync_guard:
            return
        self._prompt_sync_guard = True
        try:
            self.simple_creation_prompt_edit.setText(self.global_prompt_edit.toPlainText())
        finally:
            self._prompt_sync_guard = False

    def _sync_global_prompt_from_simple_creation(self, text: str) -> None:
        if self._prompt_sync_guard:
            return
        self._prompt_sync_guard = True
        try:
            self.global_prompt_edit.setPlainText(text)
        finally:
            self._prompt_sync_guard = False

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

    def _defaults_for_current_mode(self, scope: str) -> List[Dict[str, str]]:
        if self._mode in ("simple_enhance", "simple_creation"):
            return [dict(p) for p in (DEFAULT_GLOBAL_PARAMS_SIMPLE if scope == "global" else DEFAULT_REGION_PARAMS_SIMPLE)]
        return [dict(p) for p in (DEFAULT_GLOBAL_PARAMS if scope == "global" else DEFAULT_REGION_PARAMS)]

    def _reset_param_table(self, scope: str) -> None:
        if scope not in ("global", "regions"):
            return
        table = self.global_params if scope == "global" else self.region_params
        defaults = self._defaults_for_current_mode(scope)
        self._fill_table(table, defaults)

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

    def get_mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode == "simple":
            mode = "simple_enhance"
        if mode not in ("simple_enhance", "simple_creation", "advanced"):
            mode = "advanced"
        if self._mode == mode:
            return
        self._snapshot_current_params()
        self._mode = mode
        self._apply_mode_ui()
        self._load_mode_params(mode)

    def get_simple_values(self) -> Dict[str, object]:
        return {
            "enhance_value": self.enhance_slider.value(),
            "detail_value": self.creation_detail_slider.value(),
            "random_seed": self.random_seed_slider.value(),
            "image_size": self.image_size_combo.currentText(),
        }

    def set_simple_values(
        self,
        enhance_value: int,
        random_seed: int,
        image_size: str = "Medium",
        detail_value: int = DEFAULT_DETAIL_VALUE,
    ) -> None:
        self.enhance_slider.setValue(int(enhance_value))
        self.creation_detail_slider.setValue(int(detail_value))
        self.random_seed_slider.setValue(int(random_seed))
        if image_size in ("Small", "Medium", "Large"):
            self.image_size_combo.setCurrentText(image_size)

    def get_parameters(self) -> Dict[str, List[Dict[str, str]]]:
        self._snapshot_current_params()
        params = self._params_by_mode.get(self._mode, {"global": [], "regions": []})
        return {
            "global": list(params.get("global", [])),
            "regions": list(params.get("regions", [])),
        }

    def set_parameters(self, params: Dict[str, List[Dict[str, str]]]) -> None:
        self._params_by_mode[self._mode] = {
            "global": list(params.get("global", [])),
            "regions": list(params.get("regions", [])),
        }
        self._fill_table(self.global_params, params.get("global", []))
        self._fill_table(self.region_params, params.get("regions", []))

    def get_all_parameters(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        self._snapshot_current_params()
        active_simple_key = "simple_creation" if self._mode == "simple_creation" else "simple_enhance"
        return {
            "simple": {
                "global": list(self._params_by_mode.get(active_simple_key, {}).get("global", [])),
                "regions": list(self._params_by_mode.get(active_simple_key, {}).get("regions", [])),
            },
            "simple_creation": {
                "global": list(self._params_by_mode.get("simple_creation", {}).get("global", [])),
                "regions": list(self._params_by_mode.get("simple_creation", {}).get("regions", [])),
            },
            "advanced": {
                "global": list(self._params_by_mode.get("advanced", {}).get("global", [])),
                "regions": list(self._params_by_mode.get("advanced", {}).get("regions", [])),
            },
        }

    def set_all_parameters(
        self,
        params_simple: Dict[str, List[Dict[str, str]]],
        params_advanced: Dict[str, List[Dict[str, str]]],
        mode: str,
    ) -> None:
        self._params_by_mode = {
            "simple_enhance": {
                "global": list(params_simple.get("global", [])),
                "regions": list(params_simple.get("regions", [])),
            },
            "simple_creation": {
                "global": list(params_simple.get("global", [])),
                "regions": list(params_simple.get("regions", [])),
            },
            "advanced": {
                "global": list(params_advanced.get("global", [])),
                "regions": list(params_advanced.get("regions", [])),
            },
        }
        if mode == "simple":
            mode = "simple_enhance"
        self._mode = "advanced" if mode not in ("simple_enhance", "simple_creation", "advanced") else mode
        self._apply_mode_ui()
        self._load_mode_params(self._mode)

    def _snapshot_current_params(self) -> None:
        if not hasattr(self, "global_params") or not hasattr(self, "region_params"):
            return
        self._params_by_mode[self._mode] = {
            "global": self._read_table(self.global_params),
            "regions": self._read_table(self.region_params),
        }

    def _load_mode_params(self, mode: str) -> None:
        params = self._params_by_mode.get(mode)
        if not params:
            return
        self._fill_table(self.global_params, params.get("global", []))
        self._fill_table(self.region_params, params.get("regions", []))

    def _toggle_mode(self) -> None:
        if self._mode == "advanced":
            next_mode = "simple_enhance"
        elif self._mode == "simple_enhance":
            next_mode = "simple_creation"
        else:
            next_mode = "advanced"
        self.set_mode(next_mode)

    def _apply_mode_ui(self) -> None:
        if not hasattr(self, "prompts_group"):
            return
        is_simple = self._mode in ("simple_enhance", "simple_creation")
        is_simple_creation = self._mode == "simple_creation"
        self.simple_controls_group.setVisible(is_simple)
        self.simple_enhance_label.setVisible(not is_simple_creation)
        self.enhance_slider.setVisible(not is_simple_creation)
        self.enhance_spin.setVisible(not is_simple_creation)
        self.image_size_label.setVisible(is_simple_creation)
        self.image_size_combo.setVisible(is_simple_creation)
        self.simple_creation_prompt_label.setVisible(is_simple_creation)
        self.simple_creation_prompt_edit.setVisible(is_simple_creation)
        self.simple_creation_detail_label.setVisible(is_simple_creation)
        self.creation_detail_slider.setVisible(is_simple_creation)
        self.creation_detail_spin.setVisible(is_simple_creation)
        self.toggle_params_btn.setVisible(is_simple)
        if is_simple:
            self._set_params_visibility(self._simple_params_visible)
        else:
            self.prompts_group.setVisible(True)
            self.parameters_group.setVisible(True)
        self._set_prompt_editors_enabled(not is_simple)
        self._set_parameters_enabled(not is_simple)
        self._update_mode_button()
        self._schedule_param_resize()

    def _toggle_params_visibility(self) -> None:
        self._set_params_visibility(not self._simple_params_visible)

    def _set_params_visibility(self, visible: bool) -> None:
        self._simple_params_visible = visible
        self.prompts_group.setVisible(visible)
        self.parameters_group.setVisible(visible)
        self._update_toggle_params_btn()
        self._schedule_param_resize()

    def _update_toggle_params_btn(self) -> None:
        if not hasattr(self, "toggle_params_btn"):
            return
        self.toggle_params_btn.setText("Hide parameters" if self._simple_params_visible else "Show parameters")

    def _update_mode_button(self) -> None:
        if not hasattr(self, "mode_toggle_btn"):
            return
        if self._mode == "simple_enhance":
            label = "Simple enhance"
        elif self._mode == "simple_creation":
            label = "Simple creation"
        else:
            label = "Advanced"
        self.mode_toggle_btn.setText(f"Mode: {label}")

    def _set_parameters_enabled(self, enabled: bool) -> None:
        widgets = [
            getattr(self, "global_params", None),
            getattr(self, "region_params", None),
            getattr(self, "add_global_btn", None),
            getattr(self, "remove_global_btn", None),
            getattr(self, "clear_global_btn", None),
            getattr(self, "reset_global_btn", None),
            getattr(self, "add_region_btn", None),
            getattr(self, "remove_region_btn", None),
            getattr(self, "clear_region_btn", None),
            getattr(self, "reset_region_btn", None),
            getattr(self, "copy_global_to_region_btn", None),
            getattr(self, "global_params_label", None),
            getattr(self, "region_params_label", None),
        ]
        for widget in widgets:
            if widget:
                widget.setEnabled(enabled)

    def _set_prompt_editors_enabled(self, enabled: bool) -> None:
        for button in self._prompt_editor_buttons:
            button.setEnabled(enabled)

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
        self._schedule_param_resize()

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

    def _schedule_param_resize(self) -> None:
        if hasattr(self, "_resize_pending") and self._resize_pending:
            return
        self._resize_pending = True

        def _run() -> None:
            self._resize_pending = False
            self._resize_param_tables()

        QtCore.QTimer.singleShot(0, _run)

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
        all_params = self.get_all_parameters()
        simple_values = self.get_simple_values()
        payload = {
            "mode": self.get_mode(),
            "prompts": prompts,
            "params_simple": all_params.get("simple", {}),
            "params_advanced": all_params.get("advanced", {}),
            "enhance_value": simple_values.get("enhance_value", 20),
            "detail_value": simple_values.get("detail_value", DEFAULT_DETAIL_VALUE),
            "random_seed": simple_values.get("random_seed", 0),
            "image_size": simple_values.get("image_size", "Medium"),
        }
        self.parameter_sets.save_set(name, payload)
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
        params_advanced = data.get("params_advanced") or data.get("params") or {}
        params_simple = data.get("params_simple") or params_advanced
        mode = data.get("mode") or "advanced"
        self.set_prompts(prompts)
        self.set_all_parameters(params_simple, params_advanced, mode)
        self.set_simple_values(
            data.get("enhance_value", 20),
            data.get("random_seed", 0),
            data.get("image_size", "Medium"),
            data.get("detail_value", DEFAULT_DETAIL_VALUE),
        )
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
