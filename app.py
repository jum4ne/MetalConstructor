import sys

from PySide6.QtWidgets import QApplication

# ВАЖНО: настройки надо применить ДО импорта MainWindow, потому что при импорте
# ui/main_window.py уже читает Config.SHEET_SIZES, THICKNESS_OPTIONS и т.д.
# для построения выпадающих меню. Если применить после - меню будут собраны
# со старыми (заводскими) значениями.
from core.settings_store import load_settings, apply_to_config
apply_to_config(load_settings())

from ui.main_window import MainWindow
from ui import theme


def main():
    app = QApplication(sys.argv)

    # Стиль Fusion + палитра - чтобы UI выглядел одинаково на любой машине
    # (нативный стиль Windows игнорирует часть наших QSS-правил).
    app.setStyle("Fusion")
    app.setPalette(theme.build_palette())
    app.setStyleSheet(theme.build_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()