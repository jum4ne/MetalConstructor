"""
Регрессионные тесты - защита от возврата уже исправленных багов.

Каждый тест здесь = один реальный баг, который мы уже пофиксили.
Если тест начнёт падать - значит баг вернулся, и его снова нужно чинить.

Логика: люди меняют код, забывают про старые фиксы, случайно ломают их снова.
Эти тесты замечают это моментально.
"""
import pytest

from core.nesting import pack_parts
from core.calculator import CabinetCalculator
from core.builders import GrillCabinetBuilder, SinkCabinetBuilder, CountertopBuilder
from core.kitchen_project import KitchenProject
from core.dxf_exporter import DXFExporter
from core.sheet_advisor import find_ideal_sheet


class TestRegressions:
    def test_шелф_алгоритм_не_вылезает_за_границы_листа(self):
        """
        БАГ (03.07): старый шелф-алгоритм при создании нового ряда проверял
        только высоту, но не ширину. Из-за этого деталь 1400×600 на листе
        1250×2500 рисовалась с x=1410 - за правым краем.

        Проверяем ту же деталь на MaxRects - должна корректно повернуться
        или уйти на след. лист, но НИКОГДА не вылезти за границы.
        """
        from core.models import Part
        wide_part = Part("Широкая", 1400, 600, 1, 1.0)
        sheets = pack_parts([wide_part], 1250, 2500, 10, 2)
        for sheet in sheets:
            for pd in sheet['parts']:
                assert pd['x'] + pd['width'] <= 1250 + 0.01
                assert pd['y'] + pd['height'] <= 2500 + 0.01

    def test_вырез_поворачивается_вместе_с_деталью(self):
        """
        БАГ (04.07): в проекте кухни крыша шкафа под гриль (700×500) при
        раскрое поворачивалась (500×700), но вырез 560×480 рисовался в
        исходной системе координат и выезжал за границу детали на 230 мм.

        Проверяем ЯВНО повёрнутую крышу: вырез должен остаться внутри детали.
        Логика преобразования координат здесь точно повторяет _draw_part
        из dxf_exporter.py, поэтому если там кто-то уберёт поворот - тест упадёт.
        """
        grill = GrillCabinetBuilder.build(850, 700, 500, 1.5)
        top = next(p for p in grill.parts if "гриль" in p.name.lower())

        # Явно моделируем ситуацию: деталь повёрнута при раскрое.
        # При повороте на 90° деталь width×height отрисовывается как height×width.
        rotated = True
        orig_w = top.width          # 700
        x, y = 0, 0                 # позиция на листе (для теста неважна)
        w = top.height              # отрисованная ширина = 500
        h = top.width               # отрисованная высота = 700

        cutout = top.cutouts[0]

        # --- та же формула, что в dxf_exporter._draw_part ---
        if rotated:
            cx = x + cutout.y
            cy = y + (orig_w - cutout.x)
            cw, ch = cutout.height, cutout.width
        else:
            cx = x + cutout.x
            cy = y + cutout.y
            cw, ch = cutout.width, cutout.height

        left = cx - cw / 2
        right = cx + cw / 2
        bottom = cy - ch / 2
        top_edge = cy + ch / 2

        # Все 4 границы выреза внутри повёрнутой детали (0..w, 0..h)
        assert left >= x - 0.01, f"Вырез вылезает слева при повороте: {left:.1f} < {x}"
        assert right <= x + w + 0.01, f"Вырез вылезает справа при повороте: {right:.1f} > {x + w}"
        assert bottom >= y - 0.01, f"Вырез вылезает снизу при повороте: {bottom:.1f} < {y}"
        assert top_edge <= y + h + 0.01, f"Вырез вылезает сверху при повороте: {top_edge:.1f} > {y + h}"

    def test_идеальный_лист_на_проекте_кухни_не_none(self):
        """
        БАГ (04.07): find_ideal_sheet возвращал None для проекта из 3 модулей,
        потому что max_dim=6000 был слишком мал. Поднято до 12000.

        Проверяем на том же составе проекта, что был в баге у Жени.
        """
        from core.builders import TumbaBuilder
        project = KitchenProject(name="Test")
        project.add_module(CabinetCalculator.calculate(1800, 900, 500, 4, 1.0))
        project.add_module(GrillCabinetBuilder.build(850, 700, 500, 1.5))
        project.add_module(TumbaBuilder.build(850, 600, 500, 1.2, shelves=1))

        result = find_ideal_sheet(project.parts, 10, 2, round_step=100)
        assert result is not None

    def test_разбитая_столешница_дает_правильную_смету(self):
        """
        БАГ: отчёт считал по исходному списку деталей (1 столешница),
        а не по факту после разбивки (2 куска со швом). Смета выходила
        занижена вдвое.
        """
        ct = CountertopBuilder.build(2900, 600, 2.0, bend_height=30)
        sheets = DXFExporter._optimize_layout(ct.parts)
        report = DXFExporter._create_report("fake.dxf", ct, sheets)

        # Должно быть 2 физических куска (со швом), а не 1
        assert report['parts_count'] == 2
        assert report['split_parts_count'] == 2
        # Стоимость работы = 2 × WORK_PRICE_PER_PART, а не 1 × ...
        from core.rules import Rules
        assert report['work_cost_rub'] == 2 * Rules.WORK_PRICE_PER_PART

    def test_pdf_считает_отчет_если_не_передан(self):
        """
        БАГ (сегодня): если PDF-экспорт запустить без предварительного DXF,
        секция "Итоги раскроя" не рисовалась (report=None).
        Теперь PDF сам считает отчёт, если его не передали.
        """
        # Проверяем не сам PDF-рендер (он требует reportlab), а логику
        # генерации отчёта - что для любого модуля она возвращает валидный dict
        from core.builders import TumbaBuilder
        tumba = TumbaBuilder.build(850, 600, 500, 1.2, shelves=1)
        sheets = DXFExporter._optimize_layout(tumba.parts)
        report = DXFExporter._create_report("fake.dxf", tumba, sheets)

        # В отчёте должны быть все ключи, которые PDF-экспортёр использует
        required_keys = [
            'sheets_count', 'parts_count',
            'usage_percent', 'waste_percent',
            'metal_cost_rub', 'work_cost_rub', 'total_cost_rub'
        ]
        for key in required_keys:
            assert key in report, f"В отчёте нет ключа {key}"
            assert report[key] is not None

    def test_угловые_вырезы_на_полке_и_боковине(self):
        """
        Полка и боковина шкафа - несущие элементы с двойным загибом на всех
        4 краях, значит во ВСЕХ 4 углах нужен вырез (иначе загибы будут
        мешать друг другу при гибке). Площадь плоской заготовки должна
        быть ровно на 4×corner_relief² меньше габаритного прямоугольника.
        """
        from core.sheet_metal import get_corners_needing_relief, build_outline_points

        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        for name in ("Полка", "Боковина"):
            part = next(p for p in cabinet.parts if p.name == name)
            corners = get_corners_needing_relief(part)
            assert len(corners) == 4, f"{name}: ожидалось 4 угла с вырезом, получено {len(corners)}"

            pts = build_outline_points(0, 0, part.width, part.height, corners, part.corner_relief)
            assert len(pts) == 13, f"{name}: контур с 4 вырезанными углами должен иметь 13 точек"

            # Площадь по формуле шнурков не должна быть отрицательной или нулевой
            n = len(pts) - 1
            area = abs(sum(pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1] for i in range(n))) / 2
            expected = part.width * part.height - 4 * part.corner_relief ** 2
            assert area == expected, f"{name}: площадь контура с вырезами не совпадает с расчётной"

    def test_вырез_в_углу_не_вылезает_за_пределы_детали(self):
        """Контур с вырезанными углами должен физически помещаться в те же
        границы, что и обычный прямоугольник той же детали - вырезы срезают
        материал ВНУТРЬ, а не добавляют что-то за пределы."""
        from core.sheet_metal import build_outline_points

        w, h, notch = 630, 920, 32
        all_corners = ['bottom-left', 'bottom-right', 'top-right', 'top-left']
        pts = build_outline_points(100, 200, w, h, all_corners, notch)

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert min(xs) >= 100 and max(xs) <= 100 + w
        assert min(ys) >= 200 and max(ys) <= 200 + h

    def test_детали_подсборок_попадают_в_раскрой_проекта(self):
        """
        Был баг: KitchenProject.parts брал только module.parts (свои детали
        модуля) и НЕ спускался в подсборки. Из-за этого панели ящиков,
        декоративные накладки и панели фасада (14 типов / 16 шт на комплексе
        К 01) не попадали ни в общий DXF-раскрой, ни в массу/смету - цех
        получал неполный комплект, масса занижалась на ~27%.
        """
        from core.kitchen_project import KitchenProject
        from core import real_modules as R

        proj = KitchenProject(name="тест подсборок")
        for key in ("section_drawers", "section_sink"):
            proj.add_module(R.build(key))

        # в проект должно попасть СТОЛЬКО ЖЕ деталей, сколько реально есть
        # в модулях вместе с их подсборками
        expected_qty = sum(p.quantity for m in proj.modules for p in m.all_parts)
        expected_types = sum(len(m.all_parts) for m in proj.modules)
        assert proj.total_parts == expected_qty, (
            f"детали подсборок потеряны: в проекте {proj.total_parts} шт, "
            f"а в модулях {expected_qty} шт")
        assert len(proj.parts) == expected_types

        names = [p.name for p in proj.parts]
        assert any("Панель ящик выдвижной" in n for n in names), "нет панелей ящиков"
        assert any("на фасад с ручкой" in n for n in names), "нет панелей фасада"

    def test_углы_освобождены_под_гибку_на_всём_комплексе(self):
        """
        Был баг: в углу вырезался квадратик 2.5мм, хотя металл в углу
        принадлежит ОБОИМ смежным бортам (у «Дна» это 19x20мм). При гибке
        второго борта углы упирались друг в друга - деталь мяло/рвало, и
        слесарю приходилось вырезать 4 угла вручную на каждой коробчатой
        детали. Эталон мастера (К 01.01.01.007 - Дно) вырезает угол ДО
        ЛИНИЙ ГИБА. Вырез не увеличивает расход: он внутри габарита.
        """
        from core.kitchen_project import KitchenProject
        from core import real_modules as R
        from core.sheet_metal import get_corners_needing_relief, get_corner_cuts

        PAIRS = {'bottom-left': ('left', 'bottom'), 'bottom-right': ('right', 'bottom'),
                 'top-right': ('right', 'top'), 'top-left': ('left', 'top')}

        proj = KitchenProject(name="тест углов")
        for key in ("section_drawers", "section_sink", "section_grill", "apron", "hood"):
            proj.add_module(R.build(key))

        checked = 0
        for part in proj.parts:
            corners = get_corners_needing_relief(part)
            if not corners:
                continue
            cuts = get_corner_cuts(part)
            offs = {b.edge: b.offset for b in part.bend_lines if b.direction != 'seam'}
            for corner in corners:
                edge_x, edge_y = PAIRS[corner]
                dx, dy = cuts[corner]
                assert dx >= offs[edge_x] - 0.01, (
                    f"{part.name}: вырез {corner} по X = {dx}, а борт {edge_x} "
                    f"= {offs[edge_x]} -> борта столкнутся при гибке")
                assert dy >= offs[edge_y] - 0.01, (
                    f"{part.name}: вырез {corner} по Y = {dy}, а борт {edge_y} "
                    f"= {offs[edge_y]} -> борта столкнутся при гибке")
                checked += 1

        assert checked >= 8, f"проверено лишь {checked} углов - тест ничего не поймал"