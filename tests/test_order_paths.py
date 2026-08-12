# -*- coding: utf-8 -*-
"""
РАСКЛАДКА ФАЙЛОВ ПО ПАПКАМ ЗАКАЗОВ.

Раньше всё сыпалось в две общие папки (cad/dxf и cad/reports) с именами,
которые различались только секундами - при десятках заказов от разных людей
найти нужный было невозможно, а файлы одного заказа лежали в разных папках.
"""
import os

from core.order_paths import slug, order_folder_name, order_dir, order_dir_for


class TestSlug:
    def test_запрещённые_символы_windows_вырезаются(self):
        bad = 'Иванов/И.И.:*?"<>|'
        s = slug(bad)
        for ch in '\\/:*?"<>|':
            assert ch not in s, f"символ {ch!r} остался в имени папки"

    def test_пробелы_становятся_дефисами(self):
        assert slug("Секция с выдвижными ящиками") == "Секция-с-выдвижными-ящиками"

    def test_пустое_и_none_не_падают(self):
        assert slug("") == ""
        assert slug(None) == ""


class TestOrderFolderName:
    def test_имя_папки_дата_заказчик_изделие(self):
        name = order_folder_name("Секция с ящиками", "Иванов")
        assert name.startswith("20")               # дата впереди - сортировка по времени
        assert "Иванов" in name
        assert "Секция-с-ящиками" in name

    def test_без_заказчика_папка_только_дата_и_изделие(self):
        name = order_folder_name("Фартук", "")
        assert "Фартук" in name
        assert name.count("_") == 1                # дата_изделие

    def test_прочерк_вместо_заказчика_не_попадает_в_имя(self):
        # в истории пустой клиент хранится как '-'
        assert "-_" not in order_folder_name("Фартук", "-")


class TestOrderDir:
    def test_повторный_экспорт_кладёт_в_ТУ_ЖЕ_папку(self):
        """
        Ключевое свойство: DXF, PDF и Excel - это РАЗНЫЕ нажатия кнопок в
        разные моменты. Если в имя папки попадёт время, каждое нажатие
        создаст свою папку и комплект снова окажется раскидан.
        """
        a = order_dir("Секция с ящиками", "Иванов", create=False)
        b = order_dir("Секция с ящиками", "Иванов", create=False)
        assert a == b, "папка заказа зависит от момента экспорта, а не от заказа"

    def test_разные_заказчики_разные_папки(self):
        a = order_dir("Секция с ящиками", "Иванов", create=False)
        b = order_dir("Секция с ящиками", "Петров", create=False)
        assert a != b

    def test_разные_изделия_разные_папки(self):
        a = order_dir("Секция с ящиками", "Иванов", create=False)
        b = order_dir("Секция под мойку", "Иванов", create=False)
        assert a != b

    def test_папка_лежит_внутри_orders(self):
        d = order_dir("Фартук", "Иванов", create=False)
        assert os.path.join("cad", "orders") in d


class TestOrderDirForObject:
    def test_модуль_и_проект_дают_папку_с_заказчиком(self):
        from core import real_modules as R
        from core.kitchen_project import KitchenProject

        m = R.build("section_drawers")
        m.client = "Иванов"
        assert "Иванов" in order_dir_for(m, create=False)

        proj = KitchenProject(name="Кухня на террасу", client="Петров")
        d = order_dir_for(proj, create=False)
        assert "Петров" in d and "Кухня-на-террасу" in d

    def test_модуль_без_заказчика_не_падает(self):
        from core import real_modules as R
        m = R.build("apron")
        assert order_dir_for(m, create=False)      # просто дата_изделие
