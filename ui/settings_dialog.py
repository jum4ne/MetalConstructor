"""
Окно настроек программы: цены, зазоры, толщины, типоразмеры листов.
Настройки сохраняются в settings.json и подхватываются при следующем запуске.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QLineEdit,
    QTabWidget, QWidget, QFormLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox,
)

from ui import theme
from core.settings_store import load_settings, save_settings, apply_to_config, get_defaults


class SettingsDialog(QDialog):
    """Окно настроек с четырьмя вкладками"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()

        self.setWindowTitle("⚙️ Настройки")
        self.setMinimumSize(720, 620)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title = QLabel("⚙️ Настройки")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.GRAPHITE};")
        outer.addWidget(title)

        hint = QLabel(
            "Все изменения сохраняются в settings.json рядом с программой. "
            "Они переживают перезапуск и обновление exe-файла."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        outer.addWidget(hint)

        tabs = QTabWidget()
        outer.addWidget(tabs, 1)

        materials_tab = QWidget()
        cutting_tab = QWidget()
        prices_tab = QWidget()
        sheets_tab = QWidget()
        sync_tab = QWidget()

        tabs.addTab(materials_tab, "🔩  Материалы")
        tabs.addTab(cutting_tab, "✂️  Раскрой")
        tabs.addTab(prices_tab, "💰  Цены")
        tabs.addTab(sheets_tab, "📄  Листы")
        tabs.addTab(sync_tab, "🌐  Синхронизация")

        self._build_materials_tab(materials_tab)
        self._build_cutting_tab(cutting_tab)
        self._build_prices_tab(prices_tab)
        self._build_sheets_tab(sheets_tab)
        self._build_sync_tab(sync_tab)

        # Нижняя панель
        bottom = QHBoxLayout()
        reset_btn = QPushButton("🔄 Сбросить к заводским")
        reset_btn.clicked.connect(self._reset_defaults)
        reset_btn.setStyleSheet(theme.btn_outline_style())
        reset_btn.setMinimumHeight(40)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(theme.btn_outline_style())
        cancel_btn.setMinimumHeight(40)

        save_btn = QPushButton("💾 Сохранить и применить")
        save_btn.clicked.connect(self._save_and_apply)
        save_btn.setStyleSheet(theme.btn_style(theme.SPARK, theme.SPARK_HOVER))
        save_btn.setMinimumHeight(40)

        bottom.addWidget(reset_btn)
        bottom.addStretch()
        bottom.addWidget(cancel_btn)
        bottom.addWidget(save_btn)
        outer.addLayout(bottom)

    # ==================== ВКЛАДКА: МАТЕРИАЛЫ ====================
    def _build_materials_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        group = QGroupBox("Металл")
        group.setStyleSheet(theme.card_style(theme.STEEL))
        form = QFormLayout()
        form.setContentsMargins(16, 6, 16, 12)
        form.setSpacing(10)

        self.default_thickness = QDoubleSpinBox()
        self.default_thickness.setRange(0.1, 20.0)
        self.default_thickness.setSingleStep(0.1)
        self.default_thickness.setSuffix(" мм")
        self.default_thickness.setValue(self.settings["default_thickness"])

        self.steel_density = QDoubleSpinBox()
        self.steel_density.setRange(0.1, 20.0)
        self.steel_density.setSingleStep(0.01)
        self.steel_density.setDecimals(2)
        self.steel_density.setSuffix(" кг/м² на 1мм")
        self.steel_density.setValue(self.settings["steel_density"])

        form.addRow("Толщина по умолчанию:", self.default_thickness)
        form.addRow("Плотность стали:", self.steel_density)

        density_hint = QLabel(
            "Для нержавейки AISI 304 обычно 7.9, для AISI 430 — 7.7. "
            "От этого зависит расчёт веса изделия."
        )
        density_hint.setWordWrap(True)
        density_hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        form.addRow("", density_hint)

        group.setLayout(form)
        layout.addWidget(group)

        # Толщины на выбор в основном окне
        thickness_group = QGroupBox("Доступные толщины металла (через запятую, мм)")
        thickness_group.setStyleSheet(theme.card_style(theme.STEEL))
        thv = QVBoxLayout()
        thv.setContentsMargins(16, 6, 16, 12)
        self.thickness_options_field = QLineEdit(
            ", ".join(str(t) for t in self.settings["thickness_options"])
        )
        thv.addWidget(self.thickness_options_field)
        thv.addWidget(QLabel(
            "Пример: 0.8, 1.0, 1.2, 1.5, 2.0, 3.0 — эти значения появятся в подсказках."
        ))
        thv_hint = thv.itemAt(thv.count() - 1).widget()
        thv_hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        thickness_group.setLayout(thv)
        layout.addWidget(thickness_group)

        layout.addStretch()

    # ==================== ВКЛАДКА: РАСКРОЙ ====================
    def _build_cutting_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        group = QGroupBox("Допуски и зазоры")
        group.setStyleSheet(theme.card_style(theme.STEEL))
        form = QFormLayout()
        form.setContentsMargins(16, 6, 16, 12)
        form.setSpacing(10)

        self.cut_tolerance = QSpinBox()
        self.cut_tolerance.setRange(0, 50)
        self.cut_tolerance.setSuffix(" мм")
        self.cut_tolerance.setValue(self.settings["cut_tolerance"])

        self.door_gap = QSpinBox()
        self.door_gap.setRange(0, 50)
        self.door_gap.setSuffix(" мм")
        self.door_gap.setValue(self.settings["door_gap"])

        self.edge_clearance = QSpinBox()
        self.edge_clearance.setRange(0, 50)
        self.edge_clearance.setSuffix(" мм")
        self.edge_clearance.setValue(self.settings["edge_clearance"])

        self.min_edge_distance = QSpinBox()
        self.min_edge_distance.setRange(0, 200)
        self.min_edge_distance.setSuffix(" мм")
        self.min_edge_distance.setValue(self.settings["min_edge_distance"])

        form.addRow("Пропил лазера/плазмы:", self.cut_tolerance)
        form.addRow("Зазор между дверями:", self.door_gap)
        form.addRow("Отступ полки от края:", self.edge_clearance)
        form.addRow("Минимум от края листа:", self.min_edge_distance)

        group.setLayout(form)
        layout.addWidget(group)

        hint = QLabel(
            "Пропил лазера — это сколько миллиметров металла «съедает» луч; "
            "программа добавляет этот зазор между деталями, чтобы они не слиплись при резке. "
            "Отступ от края листа — сколько миллиметров нельзя занимать по краям "
            "(обычно там крепления или дефекты)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; padding: 8px;")
        layout.addWidget(hint)

        layout.addStretch()

    # ==================== ВКЛАДКА: ЦЕНЫ ====================
    def _build_prices_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        group = QGroupBox("Ценообразование")
        group.setStyleSheet(theme.card_style(theme.WELD_TEAL))
        form = QFormLayout()
        form.setContentsMargins(16, 6, 16, 12)
        form.setSpacing(10)

        self.metal_price = QDoubleSpinBox()
        self.metal_price.setRange(0, 100000)
        self.metal_price.setSingleStep(50)
        self.metal_price.setSuffix(" руб/м²")
        self.metal_price.setValue(self.settings["metal_price_per_m2"])

        self.work_price = QDoubleSpinBox()
        self.work_price.setRange(0, 100000)
        self.work_price.setSingleStep(10)
        self.work_price.setSuffix(" руб/деталь")
        self.work_price.setValue(self.settings["work_price_per_part"])

        form.addRow("Стоимость металла:", self.metal_price)
        form.addRow("Стоимость работы:", self.work_price)

        group.setLayout(form)
        layout.addWidget(group)

        hint = QLabel(
            "Цена металла — усреднённая цена за м² нержавейки (используется, если у "
            "конкретного листа не указана своя цена на вкладке «Листы»). "
            "Работа — стоимость обработки одной детали (резка + гибка)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; padding: 8px;")
        layout.addWidget(hint)

        layout.addStretch()

    # ==================== ВКЛАДКА: ЛИСТЫ ====================
    def _build_sheets_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hint = QLabel(
            "Список типоразмеров листов, доступных на заводе. Программа использует "
            "их при выборе размера листа и в советчике «Подобрать лист»."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        layout.addWidget(hint)

        self.sheets_table = QTableWidget(0, 5)
        self.sheets_table.setHorizontalHeaderLabels([
            "Код", "Название", "Ширина, мм", "Длина, мм", "Цена, руб/м²"
        ])
        self.sheets_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.sheets_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sheets_table.setMinimumHeight(240)
        layout.addWidget(self.sheets_table)

        for sheet in self.settings["sheet_sizes"]:
            self._add_sheet_row(sheet)

        buttons = QHBoxLayout()
        add_btn = QPushButton("➕ Добавить лист")
        add_btn.clicked.connect(self._add_empty_sheet_row)
        add_btn.setStyleSheet(theme.btn_outline_style())
        add_btn.setMinimumHeight(38)

        remove_btn = QPushButton("🗑️ Удалить выбранный")
        remove_btn.clicked.connect(self._remove_sheet_row)
        remove_btn.setStyleSheet(theme.btn_outline_style())
        remove_btn.setMinimumHeight(38)

        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        code_hint = QLabel(
            "Код — короткое латинское слово-идентификатор (standard, large и т.п.). "
            "Должно быть уникальным и не содержать пробелов."
        )
        code_hint.setWordWrap(True)
        code_hint.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        layout.addWidget(code_hint)

    def _add_sheet_row(self, sheet):
        row = self.sheets_table.rowCount()
        self.sheets_table.insertRow(row)
        self.sheets_table.setItem(row, 0, QTableWidgetItem(sheet.get("key", "")))
        self.sheets_table.setItem(row, 1, QTableWidgetItem(sheet.get("name", "")))
        self.sheets_table.setItem(row, 2, QTableWidgetItem(str(sheet.get("width", 1250))))
        self.sheets_table.setItem(row, 3, QTableWidgetItem(str(sheet.get("height", 2500))))
        self.sheets_table.setItem(row, 4, QTableWidgetItem(str(sheet.get("price_per_m2", 1200))))

    def _add_empty_sheet_row(self):
        row = self.sheets_table.rowCount()
        self._add_sheet_row({
            "key": f"sheet_{row + 1}",
            "name": f"Лист {row + 1}",
            "width": 1250,
            "height": 2500,
            "price_per_m2": self.settings["metal_price_per_m2"],
        })

    def _remove_sheet_row(self):
        row = self.sheets_table.currentRow()
        if row >= 0:
            self.sheets_table.removeRow(row)

    # ==================== СОХРАНЕНИЕ / СБРОС ====================
    # ==================== ВКЛАДКА: СИНХРОНИЗАЦИЯ ====================
    def _build_sync_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        hint = QLabel(
            "Если настроен адрес сервера — заказы, сохранённые в этой программе, "
            "будут видны в мобильном приложении и наоборот. Без сервера программа "
            "продолжает работать полностью локально, как раньше."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        layout.addWidget(hint)

        group = QGroupBox("Сервер")
        group.setStyleSheet(theme.card_style(theme.WELD_TEAL))
        form = QFormLayout()
        form.setContentsMargins(16, 6, 16, 12)
        form.setSpacing(10)

        self.server_url_field = QLineEdit(self.settings.get("server_url", ""))
        self.server_url_field.setPlaceholderText("https://ваш-домен.ru/api")

        self.server_password_field = QLineEdit(self.settings.get("server_password", ""))
        self.server_password_field.setEchoMode(QLineEdit.EchoMode.Password)
        self.server_password_field.setPlaceholderText("пароль доступа")

        form.addRow("Адрес сервера:", self.server_url_field)
        form.addRow("Пароль доступа:", self.server_password_field)

        group.setLayout(form)
        layout.addWidget(group)

        check_btn = QPushButton("🔌 Проверить соединение")
        check_btn.clicked.connect(self._check_server_connection)
        check_btn.setStyleSheet(theme.btn_outline_style())
        check_btn.setMinimumHeight(40)
        layout.addWidget(check_btn)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setWordWrap(True)
        self.sync_status_label.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED}; padding: 8px;")
        layout.addWidget(self.sync_status_label)

        layout.addStretch()

    def _check_server_connection(self):
        """Проверить связь с сервером прямо из окна настроек (используя ещё
        не сохранённые значения полей, чтобы не заставлять сохранять вслепую)"""
        # Временно сохраняем текущие значения полей, чтобы remote_sync их подхватил
        temp_settings = load_settings()
        temp_settings["server_url"] = self.server_url_field.text().strip()
        temp_settings["server_password"] = self.server_password_field.text()
        save_settings(temp_settings)

        from core.remote_sync import check_connection
        ok, message = check_connection()
        color = theme.WELD_TEAL if ok else theme.DANGER
        icon = "✅" if ok else "❌"
        self.sync_status_label.setText(f"{icon} {message}")
        self.sync_status_label.setStyleSheet(f"font-size: 12px; color: {color}; padding: 8px; font-weight: 600;")

    def _collect_settings(self):
        """Собрать все значения из полей UI в словарь настроек"""
        # Толщины из строки через запятую
        try:
            thickness_options = [
                float(t.strip())
                for t in self.thickness_options_field.text().split(",")
                if t.strip()
            ]
        except ValueError:
            raise ValueError("В поле «Доступные толщины» должны быть числа через запятую")

        # Листы из таблицы
        sheets = []
        keys_seen = set()
        for row in range(self.sheets_table.rowCount()):
            try:
                key_item = self.sheets_table.item(row, 0)
                name_item = self.sheets_table.item(row, 1)
                w_item = self.sheets_table.item(row, 2)
                h_item = self.sheets_table.item(row, 3)
                p_item = self.sheets_table.item(row, 4)

                key = (key_item.text().strip() if key_item else "") or f"sheet_{row + 1}"
                key = key.replace(" ", "_")
                if key in keys_seen:
                    raise ValueError(f"Код листа «{key}» встречается дважды — должен быть уникальным")
                keys_seen.add(key)

                name = (name_item.text().strip() if name_item else "") or key
                w = int(w_item.text().strip()) if w_item else 1250
                h = int(h_item.text().strip()) if h_item else 2500
                price = float(p_item.text().strip()) if p_item and p_item.text().strip() else self.metal_price.value()

                if w < 100 or h < 100:
                    raise ValueError(f"Размер листа в строке {row + 1} слишком мал (нужен минимум 100 мм)")

                sheets.append({
                    "key": key, "name": name,
                    "width": w, "height": h, "price_per_m2": price,
                })
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Ошибка в строке листа {row + 1}: {e}")

        if not sheets:
            raise ValueError("Должен быть указан хотя бы один лист")

        return {
            "metal_price_per_m2": self.metal_price.value(),
            "work_price_per_part": self.work_price.value(),
            "default_thickness": self.default_thickness.value(),
            "steel_density": self.steel_density.value(),
            "cut_tolerance": self.cut_tolerance.value(),
            "door_gap": self.door_gap.value(),
            "edge_clearance": self.edge_clearance.value(),
            "min_edge_distance": self.min_edge_distance.value(),
            "thickness_options": thickness_options,
            "sheet_sizes": sheets,
            "server_url": self.server_url_field.text().strip(),
            "server_password": self.server_password_field.text(),
        }

    def _save_and_apply(self):
        try:
            new_settings = self._collect_settings()
        except ValueError as e:
            QMessageBox.warning(self, "Неверные данные", str(e))
            return

        save_settings(new_settings)
        apply_to_config(new_settings)

        QMessageBox.information(
            self, "Настройки сохранены",
            "✅ Настройки применены и сохранены в settings.json.\n\n"
            "Часть изменений (список листов в выпадающих меню, доступные толщины) "
            "может потребовать перезапуска программы, чтобы полностью подтянуться "
            "во все места интерфейса."
        )
        self.accept()

    def _reset_defaults(self):
        confirm = QMessageBox.question(
            self, "Сбросить настройки?",
            "Все настройки будут возвращены к заводским значениям. "
            "Ваши изменения (в том числе список листов) будут потеряны. Продолжить?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.settings = get_defaults()

        self.default_thickness.setValue(self.settings["default_thickness"])
        self.steel_density.setValue(self.settings["steel_density"])
        self.thickness_options_field.setText(", ".join(str(t) for t in self.settings["thickness_options"]))
        self.cut_tolerance.setValue(self.settings["cut_tolerance"])
        self.door_gap.setValue(self.settings["door_gap"])
        self.edge_clearance.setValue(self.settings["edge_clearance"])
        self.min_edge_distance.setValue(self.settings["min_edge_distance"])
        self.metal_price.setValue(self.settings["metal_price_per_m2"])
        self.work_price.setValue(self.settings["work_price_per_part"])

        self.sheets_table.setRowCount(0)
        for sheet in self.settings["sheet_sizes"]:
            self._add_sheet_row(sheet)
