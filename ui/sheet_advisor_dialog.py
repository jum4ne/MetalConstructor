"""
Диалог "Подобрать лист": пользователь выбирает какие листы участвуют в анализе -
галочки на стандартных, свой список размеров, и опция "подобрать идеальный".
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QSpinBox, QLineEdit, QTableWidget, QTableWidgetItem, QGroupBox,
    QFormLayout, QScrollArea, QWidget, QMessageBox, QHeaderView, QAbstractItemView,
    QComboBox,
)

from ui import theme
from core.sheet_advisor import analyze_sheets, pick_best, IDEAL_KEY
from core.rules import Rules
from config import Config


class SheetAdvisorDialog(QDialog):
    """Диалог подбора листа с тремя режимами"""

    def __init__(self, parts, subject_name, parent=None):
        super().__init__(parent)
        self.parts = parts
        self.subject_name = subject_name
        self.custom_rows = []
        self._results_cache = None

        self.setWindowTitle("💡 Подобрать лист")
        self.setMinimumSize(760, 640)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # Заголовок
        title = QLabel(f"Подобрать лист для {self.subject_name}")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.GRAPHITE};")
        outer.addWidget(title)

        subtitle = QLabel(
            "Отметьте, какие листы участвуют в анализе. Можно комбинировать любые "
            "три способа: стандартные листы, свои размеры, автоподбор идеального."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"font-size: 12px; color: {theme.TEXT_MUTED};")
        outer.addWidget(subtitle)

        # Прокручиваемая зона
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        outer.addWidget(scroll, 1)

        # === 1. Стандартные листы ===
        std_group = QGroupBox("📋 Стандартные листы (из справочника)")
        std_group.setStyleSheet(theme.card_style(theme.STEEL))
        std_v = QVBoxLayout()
        std_v.setContentsMargins(16, 6, 16, 12)

        self.sheet_checkboxes = {}
        for key, info in Config.SHEET_SIZES.items():
            price = info.get('price_per_m2', Config.METAL_PRICE_PER_M2)
            cb = QCheckBox(f"{info['name']}  —  {price} руб/м²")
            cb.setChecked(True)  # по умолчанию все отмечены
            cb.setStyleSheet(f"color: {theme.TEXT}; padding: 2px;")
            self.sheet_checkboxes[key] = cb
            std_v.addWidget(cb)

        std_group.setLayout(std_v)
        layout.addWidget(std_group)

        # === 2. Свои размеры ===
        custom_group = QGroupBox("✏️ Свои размеры (например, что есть в наличии)")
        custom_group.setStyleSheet(theme.card_style(theme.PURPLE))
        custom_v = QVBoxLayout()
        custom_v.setContentsMargins(16, 6, 16, 12)
        custom_v.setSpacing(8)

        self.custom_table = QTableWidget(0, 4)
        self.custom_table.setHorizontalHeaderLabels([
            "Название", "Ширина, мм", "Длина, мм", "Цена, руб/м²"
        ])
        self.custom_table.horizontalHeader().setStretchLastSection(True)
        self.custom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.custom_table.setMinimumHeight(120)
        self.custom_table.setMaximumHeight(160)
        self.custom_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        custom_v.addWidget(self.custom_table)

        buttons_row = QHBoxLayout()
        add_row_btn = QPushButton("➕ Добавить свой лист")
        add_row_btn.clicked.connect(self._add_custom_row)
        add_row_btn.setStyleSheet(theme.btn_outline_style())
        add_row_btn.setMinimumHeight(36)

        remove_row_btn = QPushButton("🗑️ Удалить выбранный")
        remove_row_btn.clicked.connect(self._remove_custom_row)
        remove_row_btn.setStyleSheet(theme.btn_outline_style())
        remove_row_btn.setMinimumHeight(36)

        buttons_row.addWidget(add_row_btn)
        buttons_row.addWidget(remove_row_btn)
        buttons_row.addStretch()
        custom_v.addLayout(buttons_row)

        custom_group.setLayout(custom_v)
        layout.addWidget(custom_group)

        # === 3. Идеальный лист ===
        ideal_group = QGroupBox("🎯 Идеальный лист (программа сама подбирает размер)")
        ideal_group.setStyleSheet(theme.card_style(theme.SPARK))
        ideal_v = QVBoxLayout()
        ideal_v.setContentsMargins(16, 6, 16, 12)
        ideal_v.setSpacing(6)

        self.ideal_checkbox = QCheckBox(
            "Подобрать минимально возможный размер под этот заказ"
        )
        self.ideal_checkbox.setChecked(True)
        self.ideal_checkbox.setStyleSheet(f"color: {theme.TEXT}; padding: 2px;")
        ideal_v.addWidget(self.ideal_checkbox)

        ideal_note = QLabel(
            "Обычно даёт лучший результат по использованию металла (80–90%). "
            "Требует заказа/резки нестандартного листа у поставщика."
        )
        ideal_note.setWordWrap(True)
        ideal_note.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; padding-left: 22px;")
        ideal_v.addWidget(ideal_note)

        # Округление размера
        round_form = QFormLayout()
        round_form.setContentsMargins(22, 6, 0, 0)
        round_form.setSpacing(6)

        self.round_step_combo = QComboBox()
        self.round_step_combo.addItem("Без округления (точный размер)", 0)
        self.round_step_combo.addItem("Кратно 10 мм", 10)
        self.round_step_combo.addItem("Кратно 50 мм", 50)
        self.round_step_combo.addItem("Кратно 100 мм", 100)
        self.round_step_combo.setCurrentIndex(3)  # по умолчанию 100 мм - самый практичный
        round_form.addRow("Округлить размер:", self.round_step_combo)

        # Количество листов
        self.sheet_count_combo = QComboBox()
        self.sheet_count_combo.addItem("Программа сама подберёт", 0)
        for n in range(1, 11):
            self.sheet_count_combo.addItem(f"Ровно {n} лист(а/ов)", n)
        round_form.addRow("Разложить в:", self.sheet_count_combo)

        ideal_v.addLayout(round_form)

        count_note = QLabel(
            "Если единый лист получается слишком большой для завода — можно "
            "разложить заказ в 2–3 листа поменьше (каждый лист будет одного размера)."
        )
        count_note.setWordWrap(True)
        count_note.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED}; padding-left: 22px;")
        ideal_v.addWidget(count_note)

        ideal_group.setLayout(ideal_v)
        layout.addWidget(ideal_group)

        layout.addStretch()

        # === Нижняя панель ===
        bottom = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(theme.btn_outline_style())
        cancel_btn.setMinimumHeight(40)

        analyze_btn = QPushButton("🔍 Проанализировать")
        analyze_btn.clicked.connect(self._analyze)
        analyze_btn.setStyleSheet(theme.btn_style(theme.SPARK, theme.SPARK_HOVER))
        analyze_btn.setMinimumHeight(40)

        bottom.addWidget(cancel_btn)
        bottom.addStretch()
        bottom.addWidget(analyze_btn)
        outer.addLayout(bottom)

    def _add_custom_row(self):
        row = self.custom_table.rowCount()
        self.custom_table.insertRow(row)
        self.custom_table.setItem(row, 0, QTableWidgetItem(f"Свой лист {row + 1}"))
        self.custom_table.setItem(row, 1, QTableWidgetItem("1500"))
        self.custom_table.setItem(row, 2, QTableWidgetItem("3000"))
        self.custom_table.setItem(row, 3, QTableWidgetItem(str(Config.METAL_PRICE_PER_M2)))

    def _remove_custom_row(self):
        row = self.custom_table.currentRow()
        if row >= 0:
            self.custom_table.removeRow(row)

    def _collect_custom_sheets(self):
        """Собрать пользовательские листы из таблицы, отсеять невалидные строки"""
        result = []
        for row in range(self.custom_table.rowCount()):
            try:
                name_item = self.custom_table.item(row, 0)
                w_item = self.custom_table.item(row, 1)
                h_item = self.custom_table.item(row, 2)
                p_item = self.custom_table.item(row, 3)
                if not (w_item and h_item):
                    continue
                w = int(w_item.text().strip())
                h = int(h_item.text().strip())
                if w < 100 or h < 100:
                    continue
                price = float(p_item.text().strip()) if p_item and p_item.text().strip() else Config.METAL_PRICE_PER_M2
                name = name_item.text().strip() if name_item and name_item.text().strip() else f"Свой {w}×{h}"
                result.append({'width': w, 'height': h, 'name': name, 'price_per_m2': price})
            except (ValueError, AttributeError):
                continue
        return result

    def _analyze(self):
        """Собрать выбор пользователя, прогнать анализ и показать результаты"""
        sheet_keys = [k for k, cb in self.sheet_checkboxes.items() if cb.isChecked()]
        custom_sheets = self._collect_custom_sheets()
        include_ideal = self.ideal_checkbox.isChecked()

        if not sheet_keys and not custom_sheets and not include_ideal:
            QMessageBox.warning(self, "Ничего не выбрано",
                                 "Отметьте хотя бы один вариант листа для анализа.")
            return

        # Идеальный лист считается пару секунд, поэтому показываем "Идёт расчёт..."
        # через изменение курсора
        round_step = self.round_step_combo.currentData() or None
        force_sheet_count = self.sheet_count_combo.currentData() or None

        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            variants = analyze_sheets(
                self.parts, Rules.MIN_EDGE_DISTANCE, Rules.CUT_TOLERANCE,
                Rules.WORK_PRICE_PER_PART,
                sheet_keys=sheet_keys,
                custom_sheets=custom_sheets,
                include_ideal=include_ideal,
                ideal_round_step=round_step,
                force_sheet_count=force_sheet_count,
            )
        finally:
            self.unsetCursor()

        self._results_cache = variants
        self._show_results(variants)

    def _show_results(self, variants):
        """Показать результаты в отдельном окне с кнопками 'Применить' для каждого листа"""
        best = pick_best(variants)

        if best['least_waste'] is None:
            QMessageBox.warning(
                self, "Нет подходящего листа",
                f"Ни один из выбранных листов не подходит для {self.subject_name}. "
                "Возможно, детали слишком большие."
            )
            return

        results = SheetAdvisorResultsDialog(variants, best, self)
        if results.exec():
            self._chosen = results.chosen_sheet
            self.accept()  # закрыть главный диалог с "OK"
        # если пользователь просто закрыл окно результатов - остаёмся в главном диалоге

    @property
    def chosen_sheet(self):
        """Лист, выбранный пользователем через 'Применить' (или None)"""
        return getattr(self, '_chosen', None)


class SheetAdvisorResultsDialog(QDialog):
    """Окно с результатами анализа: карточки вариантов + кнопка 'Применить' у каждой"""

    def __init__(self, variants, best, parent=None):
        super().__init__(parent)
        self.variants = variants
        self.best = best
        self.chosen_sheet = None

        self.setWindowTitle("Результат подбора листа")
        self.setMinimumSize(720, 640)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title = QLabel("💡 Рекомендация по листу")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme.GRAPHITE};")
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        outer.addWidget(scroll, 1)

        best = self.best
        if best['same']:
            v = best['least_waste']
            layout.addWidget(self._make_card(
                v, "🏆 Лучший по обоим критериям", theme.SPARK
            ))
        else:
            row = QHBoxLayout()
            row.addWidget(self._make_card(
                best['least_waste'], "🎯 Меньше отходов", theme.WELD_TEAL
            ))
            row.addWidget(self._make_card(
                best['least_cost'], "💰 Меньше денег", theme.SPARK
            ))
            layout.addLayout(row)

            diff = best['least_waste']['total_cost'] - best['least_cost']['total_cost']
            diff_label = QLabel(
                f"Разница в стоимости: <b>{diff:.2f} руб</b> "
                f"(экономия при выборе более дешёвого варианта)"
            )
            diff_label.setStyleSheet(f"color: {theme.TEXT}; padding: 4px;")
            layout.addWidget(diff_label)

        # Заголовок "Все варианты"
        all_label = QLabel("Все проанализированные варианты:")
        all_label.setStyleSheet(f"font-weight: 600; color: {theme.TEXT_MUTED}; margin-top: 8px;")
        layout.addWidget(all_label)

        for v in self.variants:
            layout.addWidget(self._make_row(v))

        layout.addStretch()

        # Кнопка закрыть
        bottom = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet(theme.btn_outline_style())
        close_btn.setMinimumHeight(40)
        bottom.addStretch()
        bottom.addWidget(close_btn)
        outer.addLayout(bottom)

    def _make_card(self, variant, badge, accent_color):
        """Большая карточка для лучших вариантов, с крупными цифрами и кнопкой 'Применить'"""
        card = QGroupBox()
        card.setStyleSheet(theme.card_style(accent_color))
        v = QVBoxLayout()
        v.setContentsMargins(14, 10, 14, 14)
        v.setSpacing(6)

        badge_label = QLabel(badge)
        badge_label.setStyleSheet(f"color: {accent_color}; font-weight: 700; font-size: 12px;")
        v.addWidget(badge_label)

        name_label = QLabel(variant['name'])
        name_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.GRAPHITE};")
        name_label.setWordWrap(True)
        v.addWidget(name_label)

        info_label = QLabel(
            f"Размер: <b>{variant['width']}×{variant['height']} мм</b><br>"
            f"Листов: <b>{variant['sheets_count']}</b> шт<br>"
            f"Использование: <b>{variant['usage_percent']}%</b> "
            f"(отходы {variant['waste_percent']}%)<br>"
            f"Стоимость: <b>{variant['total_cost']:.2f} руб</b>"
        )
        info_label.setStyleSheet(f"color: {theme.TEXT}; font-size: 12px;")
        info_label.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(info_label)

        apply_btn = QPushButton(f"✅ Применить {variant['width']}×{variant['height']} к расчёту")
        apply_btn.clicked.connect(lambda: self._apply_variant(variant))
        apply_btn.setStyleSheet(theme.btn_style(accent_color, accent_color))
        apply_btn.setMinimumHeight(38)
        v.addWidget(apply_btn)

        card.setLayout(v)
        return card

    def _make_row(self, variant):
        """Компактная строка для полной таблицы вариантов, тоже с кнопкой 'Применить'"""
        row = QGroupBox()
        row.setStyleSheet(f"""
            QGroupBox {{
                background: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                margin-top: 2px;
            }}
        """)
        h = QHBoxLayout()
        h.setContentsMargins(8, 4, 8, 4)

        if variant['error']:
            info = QLabel(f"<b>{variant['name']}</b> — <span style='color:{theme.DANGER};'>не подходит</span>")
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setStyleSheet(f"color: {theme.TEXT};")
            h.addWidget(info)
        else:
            info = QLabel(
                f"<b>{variant['name']}</b> — "
                f"{variant['width']}×{variant['height']} мм, "
                f"{variant['sheets_count']} лист(ов), "
                f"использ. {variant['usage_percent']}%, "
                f"<b>{variant['total_cost']:.2f} руб</b>"
            )
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setStyleSheet(f"color: {theme.TEXT};")
            h.addWidget(info, 1)

            apply_btn = QPushButton("Применить")
            apply_btn.clicked.connect(lambda checked=False, var=variant: self._apply_variant(var))
            apply_btn.setStyleSheet(theme.btn_outline_style())
            apply_btn.setMinimumHeight(30)
            apply_btn.setMaximumWidth(120)
            h.addWidget(apply_btn)

        row.setLayout(h)
        return row

    def _apply_variant(self, variant):
        """Пользователь нажал 'Применить' - сохраняем выбор и закрываем окно"""
        self.chosen_sheet = {
            'width': variant['width'],
            'height': variant['height'],
            'name': variant['name'],
        }
        self.accept()