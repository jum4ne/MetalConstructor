"""
Тесты алгоритма раскроя (nesting.py).

Проверяют главные инварианты, которые нельзя нарушать никогда:
1. Детали не выходят за границы листа
2. Никакие две детали не пересекаются
3. Слишком большая деталь вызывает понятную ошибку
"""
import pytest

from core.nesting import pack_parts
from core.models import Part
from core.calculator import CabinetCalculator
from core.builders import (
    TumbaBuilder, SinkCabinetBuilder, GrillCabinetBuilder, CountertopBuilder,
)


# ==================== ХЕЛПЕРЫ ДЛЯ ПРОВЕРОК ====================
def rects_overlap(r1, r2, tolerance=0.01):
    """Проверка пересечения двух прямоугольников (x, y, w, h)"""
    return not (
        r1[0] + r1[2] <= r2[0] + tolerance or
        r2[0] + r2[2] <= r1[0] + tolerance or
        r1[1] + r1[3] <= r2[1] + tolerance or
        r2[1] + r2[3] <= r1[1] + tolerance
    )


def assert_no_overlaps_and_in_bounds(sheets, sheet_w, sheet_h):
    """Проверяет для каждого листа: детали в границах и не пересекаются"""
    for sheet_num, sheet in enumerate(sheets, 1):
        rects = [(pd['x'], pd['y'], pd['width'], pd['height']) for pd in sheet['parts']]

        # 1. Границы листа
        for r, pd in zip(rects, sheet['parts']):
            assert r[0] >= 0, f"Лист {sheet_num}: деталь {pd['part'].name} имеет x < 0"
            assert r[1] >= 0, f"Лист {sheet_num}: деталь {pd['part'].name} имеет y < 0"
            assert r[0] + r[2] <= sheet_w + 0.01, (
                f"Лист {sheet_num}: деталь {pd['part'].name} вышла за правый край "
                f"({r[0] + r[2]:.1f} > {sheet_w})"
            )
            assert r[1] + r[3] <= sheet_h + 0.01, (
                f"Лист {sheet_num}: деталь {pd['part'].name} вышла за верхний край "
                f"({r[1] + r[3]:.1f} > {sheet_h})"
            )

        # 2. Пересечения
        for a in range(len(rects)):
            for b in range(a + 1, len(rects)):
                assert not rects_overlap(rects[a], rects[b]), (
                    f"Лист {sheet_num}: детали {sheet['parts'][a]['part'].name} и "
                    f"{sheet['parts'][b]['part'].name} пересекаются"
                )


# ==================== ОСНОВНЫЕ СЦЕНАРИИ ====================
class TestBasicPacking:
    def test_шкаф_на_стандартном_листе(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        sheets = pack_parts(cabinet.parts, 1250, 2500, 10, 2)
        assert len(sheets) >= 1
        assert_no_overlaps_and_in_bounds(sheets, 1250, 2500)

    def test_шкаф_на_большом_листе(self):
        """На большом листе шкаф укладывается в 3 листа (было 2 до того, как
        добавили двойной загиб полкам/боковинам - раньше расход металла
        недооценивался, т.к. плоская заготовка на самом деле крупнее
        "чистого" размера детали на величину припуска на загиб)"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        sheets = pack_parts(cabinet.parts, 1500, 3000, 10, 2)
        assert len(sheets) <= 3
        assert_no_overlaps_and_in_bounds(sheets, 1500, 3000)

    def test_тумба(self):
        tumba = TumbaBuilder.build(850, 600, 500, 1.2, shelves=1)
        sheets = pack_parts(tumba.parts, 1250, 2500, 10, 2)
        assert_no_overlaps_and_in_bounds(sheets, 1250, 2500)

    def test_шкаф_под_мойку(self):
        sink = SinkCabinetBuilder.build(850, 600, 500, 1.2)
        sheets = pack_parts(sink.parts, 1250, 2500, 10, 2)
        assert_no_overlaps_and_in_bounds(sheets, 1250, 2500)

    def test_шкаф_под_гриль(self):
        grill = GrillCabinetBuilder.build(850, 700, 500, 1.5)
        sheets = pack_parts(grill.parts, 1250, 2500, 10, 2)
        assert_no_overlaps_and_in_bounds(sheets, 1250, 2500)


# ==================== КРАЕВЫЕ СЛУЧАИ ====================
class TestEdgeCases:
    def test_деталь_больше_листа_вызывает_ошибку(self):
        """Деталь 3000×800 не помещается на лист 1250×2500 - должно быть ValueError"""
        huge = Part("Огромная", 3000, 800, 1, 1.0)
        with pytest.raises(ValueError) as exc:
            pack_parts([huge], 1250, 2500, 10, 2)
        assert "не помещается" in str(exc.value)

    def test_одна_маленькая_деталь_помещается(self):
        small = Part("Маленькая", 100, 100, 1, 1.0)
        sheets = pack_parts([small], 1250, 2500, 10, 2)
        assert len(sheets) == 1
        assert len(sheets[0]['parts']) == 1

    def test_учитывается_отступ_от_края(self):
        """Деталь ровно в размер листа не влезет - есть отступ от края"""
        exact = Part("Точная", 1250, 2500, 1, 1.0)
        # margin=10 → полезная зона 1230×2480, так что деталь 1250×2500 не влезет
        with pytest.raises(ValueError):
            pack_parts([exact], 1250, 2500, 10, 2)

    def test_учитывается_пропил_между_деталями(self):
        """Две детали, которые ТОЧНО помещаются впритык, требуют доп. зазор на пропил"""
        # 620 + 620 = 1240 < 1250-2*10 = 1230? нет, > 1230
        # значит нужен зазор
        a = Part("A", 610, 100, 1, 1.0)
        b = Part("B", 610, 100, 1, 1.0)
        sheets = pack_parts([a, b], 1250, 2500, 10, 2)
        assert_no_overlaps_and_in_bounds(sheets, 1250, 2500)


# ==================== РАЗБИВКА ДЛИННЫХ ДЕТАЛЕЙ СО ШВОМ ====================
class TestSplitting:
    def test_длинная_столешница_разбивается_на_две_части(self):
        """Столешница 2900×600 не влезает в лист 1250×2500 - должна разбиться на 2"""
        from core.dxf_exporter import DXFExporter
        ct = CountertopBuilder.build(2900, 600, 2.0)
        sheets = DXFExporter._optimize_layout(ct.parts)
        # На листе должно оказаться 2 куска, оба с меткой "шов"
        placed = [pd['part'].name for s in sheets for pd in s['parts']]
        seam_parts = [n for n in placed if "шов" in n.lower()]
        assert len(seam_parts) == 2

    def test_столешница_с_вырезом_не_разбивается_а_падает_с_ошибкой(self):
        """Столешница с вырезом под мойку разбивать нельзя - вырез потеряется"""
        from core.dxf_exporter import DXFExporter
        ct = CountertopBuilder.build(2900, 600, 2.0,
                                        cutout_type="sink",
                                        cutout_width=400, cutout_height=350)
        with pytest.raises(ValueError) as exc:
            DXFExporter._optimize_layout(ct.parts)
        assert "не помещается" in str(exc.value)