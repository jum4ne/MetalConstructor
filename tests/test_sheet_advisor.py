"""
Тесты советчика листов (sheet_advisor.py).

Проверяет две основные функции:
- find_ideal_sheet - минимально возможный лист под конкретный заказ
- find_ideal_sheet_for_n - минимальный лист при условии разложения в N листов

Особое внимание: сюда идут регрессионные тесты на баги, которые Женя нашёл
в реальной работе (например, "идеальный лист не считается на проекте кухни").
"""
import pytest

from core.sheet_advisor import find_ideal_sheet, find_ideal_sheet_for_n
from core.calculator import CabinetCalculator
from core.builders import (
    TumbaBuilder, SinkCabinetBuilder, GrillCabinetBuilder, CountertopBuilder,
)
from core.kitchen_project import KitchenProject
from core.nesting import pack_parts


# ==================== ОСНОВНЫЕ СЦЕНАРИИ ====================
class TestFindIdealSheet:
    def test_возвращает_валидный_лист_для_шкафа(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        result = find_ideal_sheet(cabinet.parts, 10, 2)
        assert result is not None
        w, h = result
        assert w > 0 and h > 0

    def test_детали_реально_влезают_в_идеальный_лист(self):
        """Ключевая проверка: все детали действительно должны влезть в один лист"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w, h = find_ideal_sheet(cabinet.parts, 10, 2)

        sheets = pack_parts(cabinet.parts, w, h, 10, 2)
        assert len(sheets) == 1, (
            f"Найден 'идеальный' лист {w}×{h}, но детали в него не помещаются "
            f"в один лист (потребовалось {len(sheets)} листов)"
        )

    def test_идеальный_лист_дает_высокое_использование(self):
        """На типичном шкафе идеальный лист должен давать хотя бы 75% использования"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w, h = find_ideal_sheet(cabinet.parts, 10, 2)
        sheet_area = w * h / 1_000_000
        usage = cabinet.total_area / sheet_area * 100
        assert usage >= 75, f"Идеальный лист даёт всего {usage:.1f}% использования"

    def test_баг_идеальный_лист_на_проекте_кухни(self):
        """
        Регрессионный тест: раньше find_ideal_sheet возвращал None на проекте
        из 3 модулей, потому что max_dim=6000 был слишком мал.
        Теперь max_dim=12000 и должно работать.
        """
        project = KitchenProject(name="Test")
        project.add_module(CabinetCalculator.calculate(1800, 900, 500, 4, 1.0))
        project.add_module(GrillCabinetBuilder.build(850, 700, 500, 1.5))
        project.add_module(TumbaBuilder.build(850, 600, 500, 1.2, shelves=1))

        result = find_ideal_sheet(project.parts, 10, 2, round_step=100)
        assert result is not None, (
            "БАГ вернулся: идеальный лист не подобрался на проекте из 3 модулей "
            "(было исправлено 04.07 повышением max_dim до 12000)"
        )


# ==================== ОКРУГЛЕНИЕ ====================
class TestRounding:
    def test_округление_кратно_100(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w, h = find_ideal_sheet(cabinet.parts, 10, 2, round_step=100)
        assert w % 100 == 0, f"Ширина {w} не кратна 100"
        assert h % 100 == 0, f"Высота {h} не кратна 100"

    def test_округление_кратно_50(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w, h = find_ideal_sheet(cabinet.parts, 10, 2, round_step=50)
        assert w % 50 == 0
        assert h % 50 == 0

    def test_округление_не_ломает_вместимость(self):
        """После округления вверх все детали всё равно должны влезать"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w, h = find_ideal_sheet(cabinet.parts, 10, 2, round_step=100)
        sheets = pack_parts(cabinet.parts, w, h, 10, 2)
        assert len(sheets) == 1


# ==================== РАЗБИВКА НА N ЛИСТОВ ====================
class TestSplitIntoN:
    def test_разбивка_на_2_листа(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        result = find_ideal_sheet_for_n(cabinet.parts, 10, 2, 2)
        assert result is not None
        w, h = result
        # Проверяем, что реально влезает в 2 листа
        sheets = pack_parts(cabinet.parts, w, h, 10, 2)
        assert len(sheets) <= 2

    def test_2_листа_меньше_чем_1_большой(self):
        """При разбивке на 2 листа каждый должен быть меньше по площади,
        чем один большой лист"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        w1, h1 = find_ideal_sheet(cabinet.parts, 10, 2)
        w2, h2 = find_ideal_sheet_for_n(cabinet.parts, 10, 2, 2)
        assert w2 * h2 < w1 * h1