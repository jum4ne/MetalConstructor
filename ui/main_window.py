"""
Главное окно программы
"""
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QFileDialog,
    QComboBox,
    QMessageBox,
    QGroupBox,
    QTabWidget,
    QScrollArea,
    QAbstractItemView,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
)

from ui import theme

from core.calculator import CabinetCalculator
from core.builders import (
    TumbaBuilder,
    SinkCabinetBuilder,
    GrillCabinetBuilder,
    CountertopBuilder,
    MODULE_TYPES,
    MODULE_TYPE_BY_LABEL,
)
from core.kitchen_project import KitchenProject
from core.dxf_exporter import DXFExporter
from core.excel_exporter import ExcelExporter
from core.pdf_exporter import PDFExporter
from core.technical_drawing import TechnicalDrawingExporter
from core import real_modules
from core.project_io import save_module, load_module, save_kitchen_project, load_kitchen_project
from core.order_history import add_record, get_history, update_status, delete_record, STATUSES
from core.sheet_advisor import analyze_sheets, pick_best
from core.rules import Rules
from config import Config
from ui.sheet_advisor_dialog import SheetAdvisorDialog
from ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Главное окно конструктора"""

    def __init__(self):
        super().__init__()

        self.cabinet = None
        self.last_report = None
        self.kitchen_project = KitchenProject(name="Новый проект кухни")
        self.last_project_report = None

        # Если модуль/проект был ЗАГРУЖЕН из истории заказов (кнопка "Загрузить
        # в расчёт"), тут хранится id этого заказа - чтобы при повторном
        # экспорте DXF не создавать в истории ДУБЛИКАТ уже существующего
        # заказа. Сбрасывается в None при новом расчёте (calculate/recalc_project).
        self._loaded_module_order_id = None
        self._loaded_project_order_id = None

        self.setWindowTitle("🏭 Metal Constructor - Конструктор металлической мебели")
        self.resize(1050, 750)

        self._init_ui()

    def _init_ui(self):
        """Создать интерфейс"""

        # Тема (QSS + палитра) применяется на уровне приложения в app.py -
        # так она гарантированно действует и на диалоги (открыть/сохранить файл,
        # сообщения), а не только на это окно.

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # === ШАПКА ===
        header = QWidget()
        header.setStyleSheet(f"background: {theme.GRAPHITE}; border-radius: 10px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("METAL CONSTRUCTOR")
        title.setStyleSheet(f"""
            color: white; font-size: 19px; font-weight: 800; letter-spacing: 1.5px;
            font-family: '{theme.FONT_UI}';
        """)
        subtitle = QLabel("Раскрой и чертежи для уличных кухонь из нержавейки")
        subtitle.setStyleSheet(f"color: #aab4be; font-size: 12px; font-family: '{theme.FONT_UI}';")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        spark_dot = QLabel("●")
        spark_dot.setStyleSheet(f"color: {theme.SPARK}; font-size: 20px;")

        settings_btn = QPushButton("⚙️ Настройки")
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: white;
                border: 1px solid #4a5563;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {theme.STEEL_LIGHT}; border-color: white; }}
        """)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addWidget(settings_btn)
        header_layout.addWidget(spark_dot)

        main_layout.addWidget(header)

        # === ВКЛАДКИ ===
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        module_tab = QWidget()
        project_tab = QWidget()
        history_tab = QWidget()

        self.tabs.addTab(module_tab, "🧩  Модуль")
        self.tabs.addTab(project_tab, "🏗️  Проект кухни")
        self.tabs.addTab(history_tab, "📜  История заказов")

        self._build_module_tab(module_tab)
        self._build_project_tab(project_tab)
        self._build_history_tab(history_tab)

        self._on_module_type_changed()
        self._on_sheet_size_changed()
        self.refresh_history()

    @staticmethod
    def _scrollable(parent_widget):
        """Обернуть содержимое вкладки в скролл, вернуть layout контента"""
        outer = QVBoxLayout(parent_widget)
        outer.setContentsMargins(0, 12, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(2, 2, 12, 12)
        return layout

    def _build_module_tab(self, parent):
        """Вкладка: расчёт одного модуля"""

        layout = self._scrollable(parent)

        # --- Параметры ---
        params_group = QGroupBox("Параметры изделия")
        params_group.setStyleSheet(theme.card_style(theme.SPARK))
        params_layout = QFormLayout()
        params_layout.setSpacing(10)
        params_layout.setContentsMargins(16, 6, 16, 16)

        self.module_type = QComboBox()
        for key, label in MODULE_TYPES.items():
            self.module_type.addItem(label, key)
        self.module_type.currentIndexChanged.connect(self._on_module_type_changed)

        # Заказчик: попадает в имя папки заказа (cad/orders/дата_заказчик_изделие)
        # и в историю. Раньше у модулей заказчика не было вообще - выгрузки
        # разных людей сваливались в одну кучу с именами по секундам.
        self.module_client_field = QLineEdit()
        self.module_client_field.setPlaceholderText("ФИО клиента / номер заказа (необязательно)")

        self.height = QSpinBox()
        self.height.setRange(50, 5000)
        self.height.setValue(1800)
        self.height.setSuffix(" мм")

        self.width = QSpinBox()
        self.width.setRange(100, 5000)
        self.width.setValue(900)
        self.width.setSuffix(" мм")

        self.depth = QSpinBox()
        self.depth.setRange(100, 5000)
        self.depth.setValue(500)
        self.depth.setSuffix(" мм")

        self.thickness = QDoubleSpinBox()
        self.thickness.setRange(0.5, 10.0)
        self.thickness.setValue(1.0)
        self.thickness.setSingleStep(0.1)
        self.thickness.setSuffix(" мм")

        self.shelves = QSpinBox()
        self.shelves.setRange(0, 20)
        self.shelves.setValue(4)

        self.sheet_size = QComboBox()
        for key, name in Rules.get_available_sheets().items():
            self.sheet_size.addItem(name, key)
        self.sheet_size.addItem("✏️ Свой размер...", "custom")
        self.sheet_size.currentIndexChanged.connect(self._on_sheet_size_changed)

        self.custom_sheet_width = QSpinBox()
        self.custom_sheet_width.setRange(100, 10000)
        self.custom_sheet_width.setValue(Rules.SHEET_WIDTH)
        self.custom_sheet_width.setSuffix(" мм")

        self.custom_sheet_height = QSpinBox()
        self.custom_sheet_height.setRange(100, 10000)
        self.custom_sheet_height.setValue(Rules.SHEET_HEIGHT)
        self.custom_sheet_height.setSuffix(" мм")

        params_layout.addRow("Заказчик", self.module_client_field)
        params_layout.addRow("Тип модуля", self.module_type)
        params_layout.addRow("Высота", self.height)
        params_layout.addRow("Ширина", self.width)
        params_layout.addRow("Глубина", self.depth)
        params_layout.addRow("Толщина металла", self.thickness)
        self.shelves_label = QLabel("Количество полок")
        params_layout.addRow(self.shelves_label, self.shelves)
        params_layout.addRow("Размер листа", self.sheet_size)
        self.custom_sheet_width_label = QLabel("　↳ Ширина листа")
        self.custom_sheet_height_label = QLabel("　↳ Длина листа")
        params_layout.addRow(self.custom_sheet_width_label, self.custom_sheet_width)
        params_layout.addRow(self.custom_sheet_height_label, self.custom_sheet_height)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # --- Кнопка расчёта (главное действие вкладки) ---
        calc_row = QHBoxLayout()

        calc_btn = QPushButton("🧮  РАССЧИТАТЬ")
        calc_btn.clicked.connect(self._on_calculate_button_clicked)
        calc_btn.setMinimumHeight(46)
        calc_btn.setStyleSheet(theme.btn_style(theme.SPARK, theme.SPARK_HOVER))
        calc_row.addWidget(calc_btn, 2)

        advise_btn = QPushButton("💡 Подобрать лист")
        advise_btn.clicked.connect(self.advise_sheet)
        advise_btn.setMinimumHeight(46)
        advise_btn.setStyleSheet(theme.btn_style(theme.WELD_TEAL, theme.WELD_TEAL_HOVER))
        calc_row.addWidget(advise_btn, 1)

        layout.addLayout(calc_row)

        # --- Экспорт ---
        export_group = QGroupBox("Экспорт и файлы")
        export_group.setStyleSheet(theme.card_style(theme.STEEL))
        export_v = QVBoxLayout()
        export_v.setContentsMargins(16, 6, 16, 16)
        export_v.setSpacing(8)

        row1 = QHBoxLayout()
        self.export_dxf_btn = QPushButton("📤 DXF")
        self.export_dxf_btn.clicked.connect(self.export_dxf)
        self.export_dxf_btn.setEnabled(False)
        self.export_dxf_btn.setMinimumHeight(42)
        self.export_dxf_btn.setStyleSheet(theme.btn_style(theme.STEEL, theme.STEEL_LIGHT))

        # Отдельный DXF на каждую деталь - как поставляет мастер (папка
        # «развертки dxf»). Общий DXF выше - это раскрой на листы под резку,
        # а этот - по одному файлу на деталь, только геометрия реза.
        self.export_dxf_parts_btn = QPushButton("📤 DXF по деталям")
        self.export_dxf_parts_btn.clicked.connect(self.export_dxf_parts)
        self.export_dxf_parts_btn.setEnabled(False)
        self.export_dxf_parts_btn.setMinimumHeight(42)
        self.export_dxf_parts_btn.setStyleSheet(theme.btn_style(theme.STEEL, theme.STEEL_LIGHT))

        self.export_excel_btn = QPushButton("📊 Excel")
        self.export_excel_btn.clicked.connect(self.export_excel)
        self.export_excel_btn.setEnabled(False)
        self.export_excel_btn.setMinimumHeight(42)
        self.export_excel_btn.setStyleSheet(theme.btn_style(theme.WELD_TEAL, theme.WELD_TEAL_HOVER))

        self.export_pdf_btn = QPushButton("📄 PDF")
        self.export_pdf_btn.clicked.connect(self.export_pdf)
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_btn.setMinimumHeight(42)
        self.export_pdf_btn.setStyleSheet(theme.btn_style(theme.AMBER, theme.AMBER_HOVER))

        self.export_bend_map_btn = QPushButton("📐 Карта гибки")
        self.export_bend_map_btn.clicked.connect(self.export_bend_map)
        self.export_bend_map_btn.setEnabled(False)
        self.export_bend_map_btn.setMinimumHeight(42)
        self.export_bend_map_btn.setStyleSheet(theme.btn_style(theme.DANGER, theme.DANGER_HOVER))

        self.export_drawings_btn = QPushButton("📋 Полный комплект чертежей")
        self.export_drawings_btn.clicked.connect(self.export_technical_drawings)
        self.export_drawings_btn.setEnabled(False)
        self.export_drawings_btn.setMinimumHeight(42)
        self.export_drawings_btn.setStyleSheet(theme.btn_style(theme.PURPLE, theme.PURPLE_HOVER))

        row1.addWidget(self.export_dxf_btn)
        row1.addWidget(self.export_dxf_parts_btn)
        row1.addWidget(self.export_excel_btn)
        row1.addWidget(self.export_pdf_btn)
        row1.addWidget(self.export_bend_map_btn)
        row1.addWidget(self.export_drawings_btn)
        export_v.addLayout(row1)

        row2 = QHBoxLayout()
        open_btn = QPushButton("📁 Открыть модуль")
        open_btn.clicked.connect(self.open_project)
        open_btn.setMinimumHeight(40)
        open_btn.setStyleSheet(theme.btn_outline_style())

        save_btn = QPushButton("💾 Сохранить модуль")
        save_btn.clicked.connect(self.save_module_to_file)
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet(theme.btn_outline_style())

        row2.addWidget(open_btn)
        row2.addWidget(save_btn)
        export_v.addLayout(row2)

        export_group.setLayout(export_v)
        layout.addWidget(export_group)

        # --- Таблица деталей ---
        parts_group = QGroupBox("Список деталей")
        parts_group.setStyleSheet(theme.card_style(theme.STEEL))
        parts_v = QVBoxLayout()
        parts_v.setContentsMargins(16, 6, 16, 16)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(6)
        self.parts_table.setAlternatingRowColors(True)
        self.parts_table.setHorizontalHeaderLabels([
            "Деталь", "Ширина, мм", "Высота, мм", "Толщина, мм", "Кол-во", "Вырезы / Гибы"
        ])
        self.parts_table.horizontalHeader().setStretchLastSection(True)
        self.parts_table.setMinimumHeight(220)
        self.parts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        parts_v.addWidget(self.parts_table)
        parts_group.setLayout(parts_v)
        layout.addWidget(parts_group)

        # --- Инфо ---
        self.info_label = QLabel("Заполни параметры и нажми «Рассчитать».")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"""
            font-size: 13px;
            padding: 14px 16px;
            background: {theme.SURFACE};
            border: 1px solid {theme.BORDER};
            border-left: 4px solid {theme.SPARK};
            border-radius: 6px;
            color: {theme.TEXT};
        """)
        layout.addWidget(self.info_label)
        layout.addStretch()

    def _build_project_tab(self, parent):
        """Вкладка: проект кухни целиком"""

        layout = self._scrollable(parent)

        info_card = QLabel(
            "Собери несколько модулей вместе — программа посчитает общий раскрой "
            "по всем деталям сразу, что обычно экономит металл по сравнению с резкой "
            "каждого модуля отдельно."
        )
        info_card.setWordWrap(True)
        info_card.setStyleSheet(f"""
            font-size: 12px; color: {theme.TEXT_MUTED}; padding: 4px 4px 0px 4px;
        """)
        layout.addWidget(info_card)

        # --- Модули проекта ---
        modules_group = QGroupBox("Модули проекта")
        modules_group.setStyleSheet(theme.card_style(theme.PURPLE))
        modules_v = QVBoxLayout()
        modules_v.setContentsMargins(16, 6, 16, 16)
        modules_v.setSpacing(10)

        project_form = QFormLayout()
        project_form.setSpacing(8)
        self.project_name_field = QLineEdit("Новый проект кухни")
        self.project_client_field = QLineEdit()
        self.project_client_field.setPlaceholderText("ФИО клиента / номер заказа")
        project_form.addRow("Название проекта", self.project_name_field)
        project_form.addRow("Клиент", self.project_client_field)
        modules_v.addLayout(project_form)

        add_remove_row = QHBoxLayout()
        add_to_project_btn = QPushButton("➕ Добавить рассчитанный модуль")
        add_to_project_btn.clicked.connect(self.add_module_to_project)
        add_to_project_btn.setStyleSheet(theme.btn_style(theme.PURPLE, theme.PURPLE_HOVER))
        add_to_project_btn.setMinimumHeight(40)

        remove_from_project_btn = QPushButton("🗑️ Удалить выбранный")
        remove_from_project_btn.clicked.connect(self.remove_module_from_project)
        remove_from_project_btn.setStyleSheet(theme.btn_outline_style())
        remove_from_project_btn.setMinimumHeight(40)

        placement_btn = QPushButton("🎯 Позиция/угол")
        placement_btn.clicked.connect(self.edit_module_placement)
        placement_btn.setStyleSheet(theme.btn_outline_style())
        placement_btn.setMinimumHeight(40)

        add_remove_row.addWidget(add_to_project_btn)
        add_remove_row.addWidget(remove_from_project_btn)
        add_remove_row.addWidget(placement_btn)
        modules_v.addLayout(add_remove_row)

        self.project_modules_list = QListWidget()
        self.project_modules_list.setMinimumHeight(130)
        self.project_modules_list.setMaximumHeight(160)
        modules_v.addWidget(self.project_modules_list)

        modules_group.setLayout(modules_v)
        layout.addWidget(modules_group)

        # --- Экспорт проекта ---
        export_group = QGroupBox("Экспорт и сохранение проекта")
        export_group.setStyleSheet(theme.card_style(theme.STEEL))
        export_v = QVBoxLayout()
        export_v.setContentsMargins(16, 6, 16, 16)
        export_v.setSpacing(8)

        recalc_row = QHBoxLayout()

        recalc_project_btn = QPushButton("🧮 ПЕРЕСЧИТАТЬ ПРОЕКТ")
        recalc_project_btn.clicked.connect(self._on_recalc_project_button_clicked)
        recalc_project_btn.setMinimumHeight(44)
        recalc_project_btn.setStyleSheet(theme.btn_style(theme.SPARK, theme.SPARK_HOVER))
        recalc_row.addWidget(recalc_project_btn, 2)

        advise_project_btn = QPushButton("💡 Подобрать лист")
        advise_project_btn.clicked.connect(self.advise_sheet_project)
        advise_project_btn.setMinimumHeight(44)
        advise_project_btn.setStyleSheet(theme.btn_style(theme.WELD_TEAL, theme.WELD_TEAL_HOVER))
        recalc_row.addWidget(advise_project_btn, 1)

        export_v.addLayout(recalc_row)

        row1 = QHBoxLayout()
        self.export_project_dxf_btn = QPushButton("📤 DXF")
        self.export_project_dxf_btn.clicked.connect(self.export_project_dxf)
        self.export_project_dxf_btn.setMinimumHeight(42)
        self.export_project_dxf_btn.setStyleSheet(theme.btn_style(theme.STEEL, theme.STEEL_LIGHT))

        self.export_project_excel_btn = QPushButton("📊 Excel")
        self.export_project_excel_btn.clicked.connect(self.export_project_excel)
        self.export_project_excel_btn.setMinimumHeight(42)
        self.export_project_excel_btn.setStyleSheet(theme.btn_style(theme.WELD_TEAL, theme.WELD_TEAL_HOVER))

        self.export_project_pdf_btn = QPushButton("📄 PDF")
        self.export_project_pdf_btn.clicked.connect(self.export_project_pdf)
        self.export_project_pdf_btn.setMinimumHeight(42)
        self.export_project_pdf_btn.setStyleSheet(theme.btn_style(theme.AMBER, theme.AMBER_HOVER))

        self.export_project_bend_map_btn = QPushButton("📐 Карта гибки")
        self.export_project_bend_map_btn.clicked.connect(self.export_project_bend_map)
        self.export_project_bend_map_btn.setMinimumHeight(42)
        self.export_project_bend_map_btn.setStyleSheet(theme.btn_style(theme.DANGER, theme.DANGER_HOVER))

        self.export_project_drawings_btn = QPushButton("📋 Полный комплект чертежей")
        self.export_project_drawings_btn.clicked.connect(self.export_project_technical_drawings)
        self.export_project_drawings_btn.setMinimumHeight(42)
        self.export_project_drawings_btn.setStyleSheet(theme.btn_style(theme.PURPLE, theme.PURPLE_HOVER))

        row1.addWidget(self.export_project_dxf_btn)
        row1.addWidget(self.export_project_excel_btn)
        row1.addWidget(self.export_project_pdf_btn)
        row1.addWidget(self.export_project_bend_map_btn)
        row1.addWidget(self.export_project_drawings_btn)
        export_v.addLayout(row1)

        row2 = QHBoxLayout()
        save_project_btn = QPushButton("💾 Сохранить проект")
        save_project_btn.clicked.connect(self.save_project_to_file)
        save_project_btn.setMinimumHeight(40)
        save_project_btn.setStyleSheet(theme.btn_outline_style())

        load_project_btn = QPushButton("📂 Загрузить проект")
        load_project_btn.clicked.connect(self.load_project_from_file)
        load_project_btn.setMinimumHeight(40)
        load_project_btn.setStyleSheet(theme.btn_outline_style())

        row2.addWidget(save_project_btn)
        row2.addWidget(load_project_btn)
        export_v.addLayout(row2)

        export_group.setLayout(export_v)
        layout.addWidget(export_group)

        self.project_info_label = QLabel("Модулей в проекте: 0")
        self.project_info_label.setWordWrap(True)
        self.project_info_label.setStyleSheet(f"""
            font-size: 13px;
            padding: 14px 16px;
            background: {theme.SURFACE};
            border: 1px solid {theme.BORDER};
            border-left: 4px solid {theme.PURPLE};
            border-radius: 6px;
            color: {theme.TEXT};
        """)
        layout.addWidget(self.project_info_label)
        layout.addStretch()

    def _build_history_tab(self, parent):
        """Вкладка: история заказов"""

        layout = self._scrollable(parent)

        history_group = QGroupBox("История заказов")
        history_group.setStyleSheet(theme.card_style(theme.GRAPHITE_LIGHT))
        history_v = QVBoxLayout()
        history_v.setContentsMargins(16, 6, 16, 16)
        history_v.setSpacing(10)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setHorizontalHeaderLabels([
            "Дата", "Название", "Клиент", "Тип", "Листов", "Сумма, руб", "Статус"
        ])
        # ВАЖНО: раньше тут был setStretchLastSection(True) - это растягивало
        # столбец "Статус" на весь остаток ширины, из-за чего он менял размер
        # каждый раз при обновлении таблицы (в зависимости от длины названий
        # заказов в других столбцах). Теперь растягивается "Название" (у него
        # и так разная длина, это нормально), а "Статус" держит фиксированную
        # ширину и не прыгает.
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.setMinimumHeight(260)
        # ВАЖНО: запрещаем редактирование прямо в ячейках. Иначе двойной клик по
        # статусу открывает встроенный редактор ПОВЕРХ текста (визуально текст
        # накладывается сам на себя), и при этом изменение никуда не сохраняется -
        # статус меняется только через комбобокс + кнопку "Применить" ниже.
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        history_v.addWidget(self.history_table)

        history_buttons = QHBoxLayout()
        refresh_history_btn = QPushButton("🔄 Обновить")
        refresh_history_btn.clicked.connect(self.refresh_history)
        refresh_history_btn.setStyleSheet(theme.btn_outline_style())
        refresh_history_btn.setMinimumHeight(40)

        self.status_combo = QComboBox()
        for s in STATUSES:
            self.status_combo.addItem(s)

        apply_status_btn = QPushButton("✏️ Применить статус к выбранному")
        apply_status_btn.clicked.connect(self.apply_status_to_selected)
        apply_status_btn.setStyleSheet(theme.btn_style(theme.STEEL, theme.STEEL_LIGHT))
        apply_status_btn.setMinimumHeight(40)

        open_folder_btn = QPushButton("📁 Открыть папку заказа")
        open_folder_btn.clicked.connect(self.open_selected_order_folder)
        open_folder_btn.setStyleSheet(theme.btn_style(theme.STEEL, theme.STEEL_LIGHT))
        open_folder_btn.setMinimumHeight(40)

        delete_order_btn = QPushButton("🗑️ Удалить заказ")
        delete_order_btn.clicked.connect(self.delete_selected_order)
        delete_order_btn.setStyleSheet(theme.btn_style(theme.DANGER, theme.DANGER_HOVER))
        delete_order_btn.setMinimumHeight(40)

        history_buttons.addWidget(refresh_history_btn)
        history_buttons.addWidget(open_folder_btn)
        history_buttons.addWidget(self.status_combo)
        history_buttons.addWidget(apply_status_btn)
        history_buttons.addWidget(delete_order_btn)
        history_v.addLayout(history_buttons)

        load_row = QHBoxLayout()
        load_into_calc_btn = QPushButton("📂 Загрузить в расчёт (DXF/PDF/Excel)")
        load_into_calc_btn.clicked.connect(self.load_order_into_calculator)
        load_into_calc_btn.setStyleSheet(theme.btn_style(theme.SPARK, theme.SPARK_HOVER))
        load_into_calc_btn.setMinimumHeight(42)
        load_row.addWidget(load_into_calc_btn)
        history_v.addLayout(load_row)

        load_hint = QLabel(
            "Доступно только для заказов с сервера (созданных с телефона или "
            "с другого компьютера) — старые локальные записи не хранят полные "
            "размеры для пересборки."
        )
        load_hint.setWordWrap(True)
        load_hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        history_v.addWidget(load_hint)

        history_group.setLayout(history_v)
        layout.addWidget(history_group)
        layout.addStretch()

    def _on_sheet_size_changed(self):
        """Показать поля ручного ввода, если выбран 'Свой размер'"""
        is_custom = self.sheet_size.currentData() == "custom"
        self.custom_sheet_width.setVisible(is_custom)
        self.custom_sheet_height.setVisible(is_custom)
        self.custom_sheet_width_label.setVisible(is_custom)
        self.custom_sheet_height_label.setVisible(is_custom)

    def _on_module_type_changed(self):
        """Показать/скрыть поля в зависимости от выбранного типа модуля"""
        module_key = self.module_type.currentData()

        is_countertop = module_key == "countertop"
        # У модулей каталога состав задан самим модулем (ящики/полки/двери),
        # поле "полки" к ним не применяется.
        has_shelves = module_key in ("cabinet", "tumba")

        # для столешницы высота = толщина листа, поле высоты не нужно
        self.height.setEnabled(not is_countertop)

        self.shelves.setVisible(has_shelves)
        self.shelves_label.setVisible(has_shelves)


    def _on_calculate_button_clicked(self):
        """Обработчик именно нажатия кнопки 'Рассчитать' пользователем -
        в отличие от программных пересчётов (например, из советчика листа),
        явный клик означает НОВЫЙ расчёт, не связанный с ранее загруженным
        из истории заказом."""
        self._loaded_module_order_id = None
        self.calculate()

    def calculate(self):
        """Расчёт модуля в зависимости от выбранного типа"""

        sheet_key = self.sheet_size.currentData()
        if sheet_key == "custom":
            Rules.set_custom_sheet_size(
                self.custom_sheet_width.value(),
                self.custom_sheet_height.value()
            )
        else:
            Rules.set_sheet_size(sheet_key)

        module_key = self.module_type.currentData()

        h = self.height.value()
        w = self.width.value()
        d = self.depth.value()
        t = self.thickness.value()

        if module_key in real_modules.REAL_MODULES:
            # Настоящий модуль комплекса (геометрия сверена с DXF мастера)
            self.cabinet = real_modules.build(module_key, height=h, width=w,
                                              depth=d, thickness=t)
        elif module_key == "cabinet":
            self.cabinet = CabinetCalculator.calculate(
                height=h, width=w, depth=d, shelves=self.shelves.value(), thickness=t
            )
        elif module_key == "tumba":
            self.cabinet = TumbaBuilder.build(
                height=h, width=w, depth=d, thickness=t, shelves=self.shelves.value()
            )
        elif module_key == "sink_cabinet":
            self.cabinet = SinkCabinetBuilder.build(height=h, width=w, depth=d, thickness=t)
        elif module_key == "grill_cabinet":
            self.cabinet = GrillCabinetBuilder.build(height=h, width=w, depth=d, thickness=t)
        elif module_key == "countertop":
            self.cabinet = CountertopBuilder.build(width=w, depth=d, thickness=t)
        else:
            QMessageBox.warning(self, "Ошибка", f"Неизвестный тип модуля: {module_key}")
            return

        # Заказчик -> в модуль: по нему строится имя папки заказа
        # (cad/orders/дата_заказчик_изделие) и запись в истории.
        self.cabinet.client = self.module_client_field.text().strip()

        self.update_parts_table(self.cabinet.parts)

        self.info_label.setText(f"""
            <b>📊 Результаты расчёта:</b><br>
            🧩 Тип: <b>{self.cabinet.module_type}</b><br>
            📐 Общая площадь деталей: <b>{self.cabinet.total_area:.3f} м²</b><br>
            ⚖️ Вес изделия: <b>{self.cabinet.weight:.2f} кг</b><br>
            🔩 Количество деталей: <b>{self.cabinet.total_parts} шт</b>
        """)

        self.export_dxf_btn.setEnabled(True)
        self.export_dxf_parts_btn.setEnabled(True)
        self.export_excel_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)
        self.export_bend_map_btn.setEnabled(True)
        self.export_drawings_btn.setEnabled(True)

    def update_parts_table(self, parts):
        """Обновить таблицу деталей"""

        self.parts_table.setRowCount(len(parts))

        for row, part in enumerate(parts):
            self.parts_table.setItem(row, 0, QTableWidgetItem(part.name))
            self.parts_table.setItem(row, 1, QTableWidgetItem(str(part.width)))
            self.parts_table.setItem(row, 2, QTableWidgetItem(str(part.height)))
            self.parts_table.setItem(row, 3, QTableWidgetItem(str(part.thickness)))
            self.parts_table.setItem(row, 4, QTableWidgetItem(str(part.quantity)))

            notes = []
            if getattr(part, 'cutouts', None):
                notes.append(f"вырезов: {len(part.cutouts)}")
            if getattr(part, 'bend_lines', None):
                notes.append(f"гибов: {len(part.bend_lines)}")
            self.parts_table.setItem(row, 5, QTableWidgetItem(", ".join(notes) if notes else "-"))

        self.parts_table.resizeColumnsToContents()

    def export_dxf_parts(self):
        """Экспорт отдельного DXF на каждую деталь (папка «развертки»)"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            res = DXFExporter.export_parts_separately(self.cabinet)
            QMessageBox.information(
                self, "Готово",
                f"Сохранено файлов: {res['count']}\n\n"
                f"Папка:\n{res['dir']}\n\n"
                "В каждом файле — только геометрия реза одной детали "
                "(контур и отверстия) на слое «Системный слой»."
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выгрузить DXF по деталям:\n{e}")

    def export_dxf(self):
        """Экспорт в DXF"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            result = DXFExporter.export(self.cabinet, optimize=True)
            self.last_report = result['report']
            self.show_export_report(result)

            if self._loaded_module_order_id is not None:
                # Этот модуль уже существует как заказ (загружен из истории) -
                # не создаём дубликат, просто обновим статус на "В резке"
                # локально это не трогаем (уже был какой-то статус), а на
                # сервере заказ и так уже есть.
                pass
            else:
                add_record(
                    name=self.cabinet.name,
                    client=getattr(self.cabinet, 'client', ''),
                    module_type=self.cabinet.module_type,
                    report=result['report'],
                    dxf_path=result['dxf_path'],
                )

                # Best-effort отправка на сервер (если настроен в "Настройки → Синхронизация").
                # Если сервера нет или он недоступен - молча пропускаем, локальная
                # запись выше уже сделана, программа продолжает работать как обычно.
                from core.remote_sync import push_module_order, is_configured
                if is_configured():
                    push_module_order(self.cabinet.name, "", self.cabinet, result['report'])

            # Для электрошкафа генерируется ДВА файла (с пунктиром линий гиба и
            # с уголками-метками) — показываем оба.
            files = result['report'].get('dxf_files') or [result['dxf_path']]
            files_txt = "\n".join(os.path.basename(f) for f in files)
            QMessageBox.information(
                self, "Успех",
                f"✅ Чертёж сохранён ({len(files)} файл(а)):\n{files_txt}\n\n"
                f"Папка:\n{os.path.dirname(result['dxf_path'])}\n\n"
                f"📊 Отчёт сохранён:\n{os.path.basename(result['report_path'])}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта DXF:\n{str(e)}")

    def export_bend_map(self):
        """Экспорт карты гибки для гибочного станка"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            path = PDFExporter.export_bend_map(self.cabinet)
            QMessageBox.information(self, "Успех", f"✅ Карта гибки сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта карты гибки:\n{str(e)}")

    def export_technical_drawings(self):
        """Экспорт полного комплекта чертежей - отдельная размерная страница
        на каждую уникальную деталь, с проставленными размерами и штампом
        (как в настоящей конструкторской документации)."""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            path = TechnicalDrawingExporter.export(self.cabinet)
            QMessageBox.information(
                self, "Успех",
                f"✅ Комплект чертежей сохранён:\n{path}\n\n"
                f"Одна страница на каждую уникальную деталь, с размерами и штампом."
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта чертежей:\n{str(e)}")

    def export_excel(self):
        """Экспорт спецификации в Excel"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            path = ExcelExporter.export(self.cabinet)
            QMessageBox.information(self, "Успех", f"✅ Спецификация Excel сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта Excel:\n{str(e)}")

    def export_pdf(self):
        """Экспорт спецификации в PDF"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        try:
            path = PDFExporter.export(self.cabinet, report=self.last_report)
            QMessageBox.information(self, "Успех", f"✅ PDF-спецификация сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта PDF:\n{str(e)}")

    def show_export_report(self, result):
        """Показать отчёт после экспорта DXF"""

        rep = result['report']

        seam_warning = ""
        if rep.get('split_parts_count'):
            seam_warning = f"<br>⚠️ <b>Требуют сварного шва: {rep['split_parts_count']} кусков</b> (деталь была длиннее листа)<br>"

        self.info_label.setText(f"""
            <b>✅ Экспорт выполнен!</b><br><br>

            <b>📊 Раскрой:</b><br>
            📄 Листов: <b>{rep['sheets_count']}</b><br>
            🔩 Деталей (физических кусков): <b>{rep['parts_count']}</b>{seam_warning}
            📐 Площадь деталей: <b>{rep['parts_area_m2']:.3f} м²</b><br>
            📏 Площадь листов: <b>{rep['sheet_area_m2']:.3f} м²</b><br>
            ✅ Использование материала: <b>{rep['usage_percent']:.2f}%</b><br>
            ❌ Отходы: <b>{rep['waste_percent']:.2f}%</b><br><br>

            <b>💰 Стоимость:</b><br>
            🔘 Металл: <b>{rep['metal_cost_rub']:.2f} руб</b><br>
            🔧 Работа: <b>{rep['work_cost_rub']:.2f} руб</b><br>
            💵 <b>ИТОГО: {rep['total_cost_rub']:.2f} руб</b>
        """)

    def add_module_to_project(self):
        """Добавить последний рассчитанный модуль в проект кухни"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала рассчитайте модуль (кнопка 'Рассчитать' выше)!")
            return

        self.kitchen_project.name = self.project_name_field.text() or "Новый проект кухни"
        self.kitchen_project.client = self.project_client_field.text()
        self.kitchen_project.add_module(self.cabinet)

        self._refresh_project_list()
        QMessageBox.information(
            self, "Добавлено",
            f"✅ Модуль «{self.cabinet.name}» добавлен в проект.\n"
            f"Теперь в проекте: {len(self.kitchen_project.modules)} модулей."
        )

    def remove_module_from_project(self):
        """Удалить выбранный модуль из проекта"""

        row = self.project_modules_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите модуль в списке, который нужно удалить.")
            return

        self.kitchen_project.remove_module(row)
        self._refresh_project_list()

    def edit_module_placement(self):
        """Открыть диалог задания позиции (x,y) и угла поворота выбранного
        модуля - для сборки кухни с углом или нестандартной расстановкой
        (по умолчанию модули стоят в ряд встык, это только для ручной правки)."""

        row = self.project_modules_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите модуль в списке, которому нужно задать позицию.")
            return

        placements = getattr(self.kitchen_project, 'placements', None) or []
        current = placements[row] if row < len(placements) else None
        cur_x = current.x if current else 0
        cur_y = current.y if current else 0
        cur_angle = current.angle if current else 0

        dialog = QDialog(self)
        dialog.setWindowTitle("Позиция и угол модуля")
        layout = QFormLayout(dialog)

        x_input = QDoubleSpinBox()
        x_input.setRange(-100000, 100000)
        x_input.setSuffix(" мм")
        x_input.setValue(cur_x)
        layout.addRow("Позиция X (влево-вправо):", x_input)

        y_input = QDoubleSpinBox()
        y_input.setRange(-100000, 100000)
        y_input.setSuffix(" мм")
        y_input.setValue(cur_y)
        layout.addRow("Позиция Y (глубина, для угла кухни):", y_input)

        angle_input = QComboBox()
        angle_input.addItems(["0°", "90°", "180°", "270°"])
        angle_input.setCurrentIndex(int(cur_angle // 90) % 4)
        layout.addRow("Угол поворота:", angle_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            angle_value = int(angle_input.currentText().replace("°", ""))
            self.kitchen_project.set_module_placement(
                row, x=x_input.value(), y=y_input.value(), angle=angle_value
            )
            self._refresh_project_list()

    def _refresh_project_list(self):
        """Обновить список модулей проекта в интерфейсе"""

        self.project_modules_list.clear()
        placements = getattr(self.kitchen_project, 'placements', None) or []
        for i, m in enumerate(self.kitchen_project.modules):
            pos_str = ""
            if i < len(placements):
                p = placements[i]
                pos_str = f"  [x={p.x:.0f} y={p.y:.0f} угол={p.angle:.0f}°]"
            self.project_modules_list.addItem(
                f"{m.name} ({m.module_type}) — {m.width}×{m.depth}×{m.height} мм, "
                f"t={m.thickness} мм, {m.total_parts} деталей{pos_str}"
            )

        self.project_info_label.setText(f"Модулей в проекте: {len(self.kitchen_project.modules)}")

    def _on_recalc_project_button_clicked(self):
        """Обработчик явного нажатия кнопки 'Пересчитать проект' пользователем -
        сбрасывает связь с загруженным заказом, в отличие от программных
        пересчётов из советчика листа."""
        self._loaded_project_order_id = None
        self.recalc_project()

    def recalc_project(self):
        """Пересчитать сводку по всему проекту кухни"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте пока нет ни одного модуля. Добавьте модули выше.")
            return

        # ВАЖНО: раньше этого блока тут не было вообще - проект всегда считался
        # с тем размером листа, что случайно остался в Rules с прошлого раза
        # (обычно стандартный), полностью игнорируя выбор пользователя и советчик
        # листа. Теперь применяем размер листа точно так же, как для модуля.
        sheet_key = self.sheet_size.currentData()
        if sheet_key == "custom":
            Rules.set_custom_sheet_size(
                self.custom_sheet_width.value(),
                self.custom_sheet_height.value()
            )
        else:
            Rules.set_sheet_size(sheet_key)

        self.kitchen_project.name = self.project_name_field.text() or "Новый проект кухни"
        self.kitchen_project.client = self.project_client_field.text()

        self.project_info_label.setText(f"""
            <b>📊 Проект: {self.kitchen_project.name}</b><br>
            👤 Клиент: {self.kitchen_project.client or '-'}<br>
            🧩 Модулей: <b>{len(self.kitchen_project.modules)}</b><br>
            🔩 Деталей всего: <b>{self.kitchen_project.total_parts}</b><br>
            📐 Общая площадь: <b>{self.kitchen_project.total_area:.3f} м²</b><br>
            ⚖️ Общий вес: <b>{self.kitchen_project.weight:.2f} кг</b>
        """)

    def export_project_dxf(self):
        """Экспорт общего DXF по всем модулям проекта (общий раскрой)"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для экспорта.")
            return

        try:
            result = DXFExporter.export(self.kitchen_project, optimize=True)
            self.last_project_report = result['report']

            if self._loaded_project_order_id is None:
                add_record(
                    name=self.kitchen_project.name,
                    client=self.kitchen_project.client,
                    module_type="Проект кухни",
                    report=result['report'],
                    dxf_path=result['dxf_path'],
                )

                from core.remote_sync import push_project_order, is_configured
                if is_configured():
                    push_project_order(self.kitchen_project, result['report'])

            rep = result['report']
            self.project_info_label.setText(f"""
                <b>✅ Экспорт проекта выполнен!</b><br><br>
                📄 Листов: <b>{rep['sheets_count']}</b><br>
                🔩 Деталей: <b>{rep['parts_count']}</b><br>
                ✅ Использование материала: <b>{rep['usage_percent']:.2f}%</b><br>
                ❌ Отходы: <b>{rep['waste_percent']:.2f}%</b><br>
                💵 ИТОГО: <b>{rep['total_cost_rub']:.2f} руб</b>
            """)

            QMessageBox.information(
                self, "Успех",
                f"✅ Общий чертёж проекта сохранён:\n{result['dxf_path']}\n\n"
                f"📊 Отчёт сохранён:\n{result['report_path']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта DXF проекта:\n{str(e)}")

    def export_project_excel(self):
        """Экспорт общей Excel-спецификации по проекту"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для экспорта.")
            return

        try:
            path = ExcelExporter.export(self.kitchen_project)
            QMessageBox.information(self, "Успех", f"✅ Excel-спецификация проекта сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта Excel проекта:\n{str(e)}")

    def export_project_pdf(self):
        """Экспорт общей PDF-спецификации по проекту"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для экспорта.")
            return

        try:
            path = PDFExporter.export(self.kitchen_project, report=self.last_project_report)
            QMessageBox.information(self, "Успех", f"✅ PDF-спецификация проекта сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта PDF проекта:\n{str(e)}")

    def save_module_to_file(self):
        """Сохранить текущий рассчитанный модуль в JSON"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт!")
            return

        Config.init_dirs()
        default_name = f"{self.cabinet.module_type}_{self.cabinet.width}x{self.cabinet.depth}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить модуль",
            os.path.join(Config.TEMPLATES_DIR, default_name),
            "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            save_module(self.cabinet, file_path)
            QMessageBox.information(self, "Успех", f"✅ Модуль сохранён:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения:\n{str(e)}")

    def export_project_bend_map(self):
        """Экспорт карты гибки для всего проекта кухни"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для экспорта.")
            return

        try:
            path = PDFExporter.export_bend_map(self.kitchen_project)
            QMessageBox.information(self, "Успех", f"✅ Карта гибки проекта сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта карты гибки:\n{str(e)}")

    def export_project_technical_drawings(self):
        """Экспорт полного комплекта чертежей для всего проекта кухни -
        отдельная размерная страница на каждую уникальную деталь во всех
        модулях проекта сразу."""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для экспорта.")
            return

        try:
            path = TechnicalDrawingExporter.export(self.kitchen_project)
            QMessageBox.information(
                self, "Успех",
                f"✅ Комплект чертежей проекта сохранён:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта чертежей:\n{str(e)}")

    def advise_sheet(self):
        """Открыть диалог подбора листа для одного модуля"""

        if not self.cabinet:
            QMessageBox.warning(self, "Ошибка", "Сначала выполните расчёт модуля!")
            return

        dialog = SheetAdvisorDialog(self.cabinet.parts, "модуля", parent=self)
        if dialog.exec():
            chosen = dialog.chosen_sheet
            if chosen:
                self._apply_chosen_sheet(chosen, context="module")

    def advise_sheet_project(self):
        """Открыть диалог подбора листа для всего проекта кухни"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте пока нет модулей.")
            return

        dialog = SheetAdvisorDialog(self.kitchen_project.parts, "проекта кухни", parent=self)
        if dialog.exec():
            chosen = dialog.chosen_sheet
            if chosen:
                self._apply_chosen_sheet(chosen, context="project")

    def _apply_chosen_sheet(self, chosen, context="module"):
        """Применить выбранный из советчика лист: подставить в поля 'Свой размер'
        и запустить пересчёт ИМЕННО того объекта (модуль или проект), для
        которого открывался советчик - раньше здесь всегда пересчитывался
        модуль, даже если советчик вызывался для проекта кухни."""

        # Переключиться на "Свой размер" в комбо, подставить размеры
        idx = self.sheet_size.findData("custom")
        if idx >= 0:
            self.sheet_size.setCurrentIndex(idx)
        self.custom_sheet_width.setValue(chosen['width'])
        self.custom_sheet_height.setValue(chosen['height'])

        # Пересчёт того же объекта, для которого выбирали лист. Используем
        # calculate()/recalc_project() НАПРЯМУЮ (не через _on_..._button_clicked),
        # чтобы не сбрасывать связь с заказом, загруженным из истории -
        # применение листа не должно создавать дубликат в истории при экспорте.
        if context == "module" and self.cabinet:
            self.calculate()
        elif context == "project" and self.kitchen_project.modules:
            self.recalc_project()

        QMessageBox.information(
            self, "Лист применён",
            f"✅ Размер листа установлен: {chosen['width']}×{chosen['height']} мм\n"
            f"({chosen['name']})\n\n"
            f"Пересчитано. Теперь можно экспортировать DXF/Excel/PDF."
        )

    def open_settings(self):
        """Открыть окно настроек"""
        dialog = SettingsDialog(self)
        dialog.exec()
        # После закрытия диалога Rules уже пересчитаны через apply_to_config.
        # Некоторые поля UI (комбобокс "Размер листа", "Толщина") были заполнены
        # при старте программы, для полного обновления списков — перезапуск.

    def refresh_history(self):
        """Перечитать историю заказов. Если сервер синхронизации настроен -
        показываем единый список с сервера (виден и в мобильном приложении).
        Если сервера нет или он недоступен - показываем локальную историю,
        как и раньше."""

        from core.remote_sync import fetch_orders, is_configured

        records = None
        if is_configured():
            remote = fetch_orders()
            if remote is not None:
                records = self._normalize_remote_records(remote)

        if records is None:
            records = get_history()

        self._history_records = records

        self.history_table.setRowCount(len(records))
        for row, r in enumerate(records):
            self.history_table.setItem(row, 0, QTableWidgetItem(r.get('date', '-')))
            self.history_table.setItem(row, 1, QTableWidgetItem(r.get('name', '-')))
            self.history_table.setItem(row, 2, QTableWidgetItem(r.get('client', '-')))
            self.history_table.setItem(row, 3, QTableWidgetItem(r.get('module_type', '-')))
            self.history_table.setItem(row, 4, QTableWidgetItem(str(r.get('sheets_count', '-'))))
            cost = r.get('total_cost_rub')
            self.history_table.setItem(row, 5, QTableWidgetItem(f"{cost:.2f}" if cost is not None else "-"))
            self.history_table.setItem(row, 6, QTableWidgetItem(r.get('status', '-')))

        self.history_table.resizeColumnsToContents()
        # "Название" и так растягивается (Stretch), а "Статус" держим на
        # фиксированной комфортной ширине, чтобы не прыгал между обновлениями
        self.history_table.setColumnWidth(6, 110)

    @staticmethod
    def _normalize_remote_records(remote_records):
        """Привести записи с сервера к тому же виду, что и локальная история"""
        normalized = []
        for r in remote_records:
            report = r.get('report') or {}
            normalized.append({
                'id': r['id'],
                'date': r.get('created_at', '-'),
                'name': r.get('name', '-'),
                'client': r.get('client', '-'),
                'module_type': 'Проект кухни' if r.get('order_type') == 'project' else 'Модуль',
                'sheets_count': report.get('sheets_count', '-'),
                'total_cost_rub': report.get('total_cost_rub'),
                'status': r.get('status', '-'),
                '_remote': True,
            })
        return normalized

    def open_selected_order_folder(self):
        """Открыть в проводнике папку выбранного заказа (со всеми выгрузками)"""

        row = self.history_table.currentRow()
        if row < 0 or row >= len(getattr(self, '_history_records', [])):
            QMessageBox.warning(self, "Ошибка", "Выберите заказ в таблице истории.")
            return

        record = self._history_records[row]
        dxf_path = record.get('dxf_path') or ''
        folder = os.path.dirname(dxf_path) if dxf_path else ''

        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(
                self, "Папка не найдена",
                "У этого заказа нет папки с выгрузками.\n\n"
                "Возможно, он создан до перехода на папки заказов — "
                "тогда файлы лежат в старых cad/dxf и cad/reports.\n"
                "Сделайте экспорт заново, и всё соберётся в одну папку."
            )
            return

        # Открыть системным файловым менеджером (Windows/macOS/Linux)
        try:
            if sys.platform.startswith('win'):
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            QMessageBox.information(self, "Папка заказа", f"{folder}\n\n({e})")

    def apply_status_to_selected(self):
        """Применить выбранный в комбобоксе статус к выделенному заказу в истории"""

        row = self.history_table.currentRow()
        if row < 0 or row >= len(getattr(self, '_history_records', [])):
            QMessageBox.warning(self, "Ошибка", "Выберите заказ в таблице истории.")
            return

        record = self._history_records[row]
        new_status = self.status_combo.currentText()

        if record.get('_remote'):
            from core.remote_sync import update_order_status
            ok = update_order_status(record['id'], new_status)
            if not ok:
                QMessageBox.warning(self, "Ошибка", "Не удалось обновить статус на сервере.")
                return
        else:
            update_status(record['id'], new_status)

        self.refresh_history()

    def delete_selected_order(self):
        """Удалить выбранный заказ из истории - локально или на сервере,
        в зависимости от того, откуда запись."""

        row = self.history_table.currentRow()
        if row < 0 or row >= len(getattr(self, '_history_records', [])):
            QMessageBox.warning(self, "Ошибка", "Выберите заказ в таблице истории.")
            return

        record = self._history_records[row]

        confirm = QMessageBox.question(
            self, "Удалить заказ?",
            f"Удалить заказ «{record.get('name', '-')}»? Это действие необратимо."
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if record.get('_remote'):
            from core.remote_sync import delete_order_remote
            ok = delete_order_remote(record['id'])
            if not ok:
                QMessageBox.warning(self, "Ошибка", "Не удалось удалить заказ на сервере.")
                return
        else:
            delete_record(record['id'])

        self.refresh_history()

    def load_order_into_calculator(self):
        """Загрузить заказ из истории (созданный на сервере, например с телефона)
        обратно в расчёт - чтобы можно было экспортировать DXF/PDF/Excel,
        как для только что посчитанного модуля/проекта."""

        row = self.history_table.currentRow()
        if row < 0 or row >= len(getattr(self, '_history_records', [])):
            QMessageBox.warning(self, "Ошибка", "Выберите заказ в таблице истории.")
            return

        record = self._history_records[row]
        if not record.get('_remote'):
            QMessageBox.information(
                self, "Недоступно для этой записи",
                "Эта запись из локальной истории (создана до настройки сервера "
                "или без него) — в ней не сохранены полные размеры деталей, "
                "поэтому пересобрать чертёж из неё нельзя.\n\n"
                "Загрузка доступна только для заказов из общего сервера "
                "(отмечены после настройки синхронизации)."
            )
            return

        from core.remote_sync import fetch_order_detail, rebuild_from_order_detail

        detail = fetch_order_detail(record['id'])
        if detail is None:
            QMessageBox.critical(
                self, "Ошибка",
                "Не удалось получить заказ с сервера. Проверьте соединение "
                "в Настройки → Синхронизация."
            )
            return

        try:
            obj, kind = rebuild_from_order_detail(detail)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось пересобрать заказ:\n{str(e)}")
            return

        if kind == 'module':
            self.cabinet = obj
            self._loaded_module_order_id = record['id']

            module_key = MODULE_TYPE_BY_LABEL.get(obj.module_type, "cabinet")
            idx = self.module_type.findData(module_key)
            if idx >= 0:
                self.module_type.setCurrentIndex(idx)

            self.height.setValue(obj.height or 1800)
            self.width.setValue(obj.width or 900)
            self.depth.setValue(obj.depth or 500)
            self.thickness.setValue(obj.thickness or 1.0)

            self.update_parts_table(obj.parts)
            self.export_dxf_btn.setEnabled(True)
            self.export_excel_btn.setEnabled(True)
            self.export_pdf_btn.setEnabled(True)
            self.export_bend_map_btn.setEnabled(True)
            self.export_drawings_btn.setEnabled(True)

            self.tabs.setCurrentIndex(0)  # вкладка "Модуль"
            QMessageBox.information(
                self, "Загружено",
                f"✅ Заказ «{obj.name}» загружен во вкладку «Модуль».\n"
                "Теперь доступны экспорт DXF, Excel, PDF и карта гибки."
            )
        else:  # project
            self.kitchen_project = obj
            self._loaded_project_order_id = record['id']
            self.project_name_field.setText(obj.name)
            self.project_client_field.setText(obj.client)
            self._refresh_project_list()

            self.tabs.setCurrentIndex(1)  # вкладка "Проект кухни"
            QMessageBox.information(
                self, "Загружено",
                f"✅ Проект «{obj.name}» ({len(obj.modules)} модулей) загружен "
                "во вкладку «Проект кухни».\nТеперь доступен экспорт DXF, Excel, "
                "PDF и карта гибки для всего проекта."
            )

    def open_project(self):
        """Открыть один модуль из JSON (новый формат с деталями или старый формат шкафа)"""

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть модуль", Config.TEMPLATES_DIR, "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            module, data = load_module(file_path)
            self.cabinet = module

            # Подставить тип модуля в комбобокс, если он известен
            module_key = MODULE_TYPE_BY_LABEL.get(module.module_type, "cabinet")
            idx = self.module_type.findData(module_key)
            if idx >= 0:
                self.module_type.setCurrentIndex(idx)

            self.height.setValue(module.height or 1800)
            self.width.setValue(module.width or 900)
            self.depth.setValue(module.depth or 500)
            self.thickness.setValue(module.thickness or 1.0)

            self.update_parts_table(module.parts)

            self.info_label.setText(f"""
                <b>📁 Модуль загружен</b><br>
                Файл: {os.path.basename(file_path)}<br>
                Название: {module.name}<br>
                Деталей: {module.total_parts}
            """)

            self.export_dxf_btn.setEnabled(True)
            self.export_excel_btn.setEnabled(True)
            self.export_pdf_btn.setEnabled(True)
            self.export_bend_map_btn.setEnabled(True)
            self.export_drawings_btn.setEnabled(True)

        except ValueError as e:
            QMessageBox.warning(self, "Не тот файл", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки:\n{str(e)}")

    def save_project_to_file(self):
        """Сохранить весь проект кухни в JSON"""

        if not self.kitchen_project.modules:
            QMessageBox.warning(self, "Ошибка", "В проекте нет модулей для сохранения.")
            return

        self.kitchen_project.name = self.project_name_field.text() or "Новый проект кухни"
        self.kitchen_project.client = self.project_client_field.text()

        Config.init_dirs()
        default_name = f"{self.kitchen_project.name}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект кухни",
            os.path.join(Config.TEMPLATES_DIR, default_name),
            "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            save_kitchen_project(self.kitchen_project, file_path)
            QMessageBox.information(self, "Успех", f"✅ Проект сохранён:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения проекта:\n{str(e)}")

    def load_project_from_file(self):
        """Загрузить проект кухни из JSON"""

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить проект кухни", Config.TEMPLATES_DIR, "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            self.kitchen_project = load_kitchen_project(file_path)
            self.project_name_field.setText(self.kitchen_project.name)
            self.project_client_field.setText(self.kitchen_project.client)
            self._refresh_project_list()
            self.recalc_project()

            QMessageBox.information(
                self, "Успех",
                f"✅ Проект загружен: {self.kitchen_project.name}\n"
                f"Модулей: {len(self.kitchen_project.modules)}"
            )
        except ValueError as e:
            QMessageBox.warning(self, "Не тот файл", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки проекта:\n{str(e)}")