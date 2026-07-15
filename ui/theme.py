"""
Тема оформления Metal Constructor.

Идея: инструмент для цеха резки нержавейки — не потребительское приложение.
Палитра и структура читаются как "приборная панель станка", а не как сайт.

Токены:
  GRAPHITE   #1c2733  — тёмный графит, шапка/заголовки
  STEEL      #2c3e50  — сталь, вторичные акценты (уже был в проекте)
  PLATE      #eef1f5  — холодный светлый фон, "стальной лист под цеховым светом"
  SPARK      #ff6b35  — искра реза (горячий металл) — единственный "громкий" акцент
  WELD_TEAL  #16a085  — цвет сварного шва/материала — акцент для складских/материальных действий
  CHALK      #5a6b7a  — приглушённый текст, как меловая разметка на металле

Типографика:
  Segoe UI  — интерфейс, заголовки полужирным с небольшим трекингом (заводская табличка)
  Consolas  — ВСЕ числовые/размерные данные (мм, руб, кол-во) — точность, как на чертеже

Фирменный приём: пунктирная верхняя линия карточки цветом её основного действия —
как линия лазерного/плазменного реза, с которой "начинается" эта карточка.
"""

GRAPHITE = "#1c2733"
GRAPHITE_LIGHT = "#26313f"
STEEL = "#2c3e50"
STEEL_LIGHT = "#3d5570"
PLATE = "#eef1f5"
SURFACE = "#ffffff"
BORDER = "#d5dbe0"
SPARK = "#ff6b35"
SPARK_HOVER = "#ff8555"
WELD_TEAL = "#16a085"
WELD_TEAL_HOVER = "#1abc9c"
AMBER = "#e08e2b"
AMBER_HOVER = "#eda23f"
DANGER = "#c0392b"
DANGER_HOVER = "#d9483a"
PURPLE = "#7d5ba6"
PURPLE_HOVER = "#9370c0"
TEXT = "#1c2733"
TEXT_MUTED = "#5a6b7a"

# Путь к иконкам стрелочек спинбокса. Раньше пробовали нарисовать треугольник
# через границы в QSS ("border-triangle" трюк) - Qt отрисовал это как закрашенный
# квадрат, а не треугольник (известное ограничение движка QSS для некоторых
# субконтролов). Обычные PNG-иконки работают надёжно везде.
#
# ВАЖНО: путь считается по-разному в обычном запуске (python app.py) и после
# упаковки в .exe через PyInstaller (там файлы распаковываются во временную
# папку sys._MEIPASS) - без этой развилки иконки не найдутся в собранном .exe.
import os as _os
import sys as _sys

if getattr(_sys, 'frozen', False) and hasattr(_sys, '_MEIPASS'):
    _ICONS_DIR = _os.path.join(_sys._MEIPASS, "ui", "icons").replace("\\", "/")
else:
    _ICONS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "icons").replace("\\", "/")

ARROW_UP_PNG = f"{_ICONS_DIR}/arrow_up.png"
ARROW_DOWN_PNG = f"{_ICONS_DIR}/arrow_down.png"

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"


def build_palette():
    """
    Палитра Qt для стиля Fusion.

    ВАЖНО: на Windows стиль по умолчанию (windowsvista) рисует часть элементов
    (стрелки спинбоксов, попап комбобокса, диалоги) через нативный движок ОС,
    и он игнорирует часть правил QSS. Палитра + стиль Fusion решают это -
    Qt рисует буквально всё сам, и наши цвета применяются везде без исключений.
    """
    from PySide6.QtGui import QPalette, QColor

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(PLATE))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f6f8fa"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(GRAPHITE))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("white"))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("red"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(SPARK))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    return palette


def btn_style(color, hover, text_color="white"):
    return f"""
        QPushButton {{
            background: {color};
            color: {text_color};
            font-family: '{FONT_UI}';
            font-size: 14px;
            font-weight: 600;
            border: none;
            border-radius: 6px;
            padding: 10px 14px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:pressed {{ background: {color}; }}
        QPushButton:disabled {{ background: #b7c0c9; color: #eef1f5; }}
    """


def btn_outline_style():
    """Второстепенное действие: сохранить/открыть/обновить — не должно спорить с основными кнопками"""
    return f"""
        QPushButton {{
            background: transparent;
            color: {GRAPHITE};
            font-family: '{FONT_UI}';
            font-size: 13px;
            font-weight: 600;
            border: 1.5px solid {BORDER};
            border-radius: 6px;
            padding: 9px 14px;
        }}
        QPushButton:hover {{ border-color: {STEEL_LIGHT}; background: {PLATE}; }}
        QPushButton:pressed {{ background: {BORDER}; }}
    """


def card_style(accent=STEEL):
    """Карточка (QGroupBox) с пунктирной 'линией реза' сверху цветом акцента раздела"""
    return f"""
        QGroupBox {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-top: 3px dashed {accent};
            border-radius: 8px;
            margin-top: 14px;
            padding-top: 14px;
            font-family: '{FONT_UI}';
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
            color: {GRAPHITE};
            font-weight: 700;
            font-size: 13px;
        }}
    """


def build_stylesheet():
    return f"""
        QMainWindow {{
            background: {PLATE};
        }}
        QWidget {{
            font-family: '{FONT_UI}';
            font-size: 13px;
        }}
        QLabel {{
            background: transparent;
            color: {TEXT};
        }}
        QGroupBox {{
            color: {TEXT};
        }}
        QCheckBox, QRadioButton {{
            color: {TEXT};
        }}

        /* Диалоги и всплывающие окна - ПРИНУДИТЕЛЬНО светлые.
           Без этого при тёмной системной теме Windows текст (унаследованный
           тёмным от общих правил) оказывается на тёмном системном фоне -
           тёмное на тёмном, ничего не видно. */
        QDialog, QFileDialog, QMessageBox {{
            background: {PLATE};
            color: {TEXT};
        }}
        QFileDialog QWidget, QMessageBox QWidget {{
            color: {TEXT};
            background: {PLATE};
        }}
        QFileDialog QListView, QFileDialog QTreeView {{
            background: {SURFACE};
            color: {TEXT};
        }}
        QComboBox QAbstractItemView {{
            background: {SURFACE};
            color: {TEXT};
            selection-background-color: {SPARK};
            selection-color: white;
            border: 1px solid {BORDER};
            outline: none;
        }}
        QMenu {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
        }}
        QMenu::item:selected {{
            background: {SPARK};
            color: white;
        }}
        QToolTip {{
            background: {GRAPHITE};
            color: white;
            border: 1px solid {GRAPHITE};
            padding: 4px 8px;
        }}

        /* Вкладки */
        QTabWidget::pane {{
            border: none;
            background: transparent;
            top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {TEXT_MUTED};
            font-weight: 600;
            font-size: 13px;
            padding: 10px 20px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        QTabBar::tab:selected {{
            background: {SURFACE};
            color: {GRAPHITE};
            border-bottom: 3px solid {SPARK};
        }}
        QTabBar::tab:hover:!selected {{
            color: {GRAPHITE};
        }}

        /* Поля ввода */
        QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 5px;
            padding: 6px 4px 6px 8px;
            font-family: '{FONT_MONO}';
            selection-background-color: {SPARK};
        }}
        QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
            border: 1px solid {SPARK};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 22px;
        }}

        /* Стрелки +/- спинбоксов - задаём явную геометрию, иначе Qt может
           схлопнуть кнопки при кастомном padding, и они перестают кликаться */
        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 18px;
            height: 12px;
            border-left: 1px solid {BORDER};
            border-bottom: 1px solid {BORDER};
            border-top-right-radius: 5px;
            background: {PLATE};
        }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 18px;
            height: 12px;
            border-left: 1px solid {BORDER};
            border-bottom-right-radius: 5px;
            background: {PLATE};
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background: {BORDER};
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: url({ARROW_UP_PNG});
            width: 9px;
            height: 9px;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: url({ARROW_DOWN_PNG});
            width: 9px;
            height: 9px;
        }}

        /* Таблицы */
        QTableWidget, QListWidget {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 6px;
            gridline-color: {BORDER};
            font-family: '{FONT_MONO}';
            selection-background-color: #ffe4d6;
            selection-color: {GRAPHITE};
            alternate-background-color: #f6f8fa;
        }}
        QHeaderView::section {{
            background: {GRAPHITE};
            color: white;
            font-family: '{FONT_UI}';
            font-weight: 600;
            font-size: 12px;
            padding: 8px;
            border: none;
        }}
        QTableWidget::item, QListWidget::item {{
            padding: 4px;
        }}

        /* Скроллбары - тонкие, не мешают */
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER};
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {STEEL_LIGHT};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """