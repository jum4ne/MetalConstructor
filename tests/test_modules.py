"""
Тесты расчёта модулей.

Проверяют, что билдеры возвращают правильный набор деталей с правильными
размерами, вырезами и линиями гиба.
"""
import pytest

from core.calculator import CabinetCalculator
from core.builders import (
    TumbaBuilder, SinkCabinetBuilder, GrillCabinetBuilder, CountertopBuilder,
)
from core.rules import Rules


# ==================== ШКАФ ====================
class TestCabinet:
    def test_кол_во_деталей(self):
        """Стандартный шкаф 1800×900×500 с 4 полками = 10 деталей"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        # 2 боковины + крыша + дно + 4 полки + 2 двери = 10
        assert cabinet.total_parts == 10

    def test_боковины_имеют_правильный_размер(self):
        """Боковина - несущий элемент, получает загиб (жёсткость), поэтому
        плоская заготовка крупнее финального размера на 40мм по каждой
        стороне (2 x 20мм загиб). Одинарный загиб без подгибки кромки -
        подтверждено разбором реальных профессиональных чертежей."""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        боковины = [p for p in cabinet.parts if p.name == "Боковина"]
        assert len(боковины) == 1
        assert боковины[0].quantity == 2
        assert боковины[0].width == 500 + 40  # глубина шкафа + припуск на загиб
        assert боковины[0].height == 1800 + 40  # высота шкафа + припуск на загиб
        assert боковины[0].corner_relief > 0, "У боковины должна быть угловая прорезь"

    def test_ширина_двери_учитывает_зазор(self):
        """Ширина одной двери = (общая ширина - зазор между дверями) / 2"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        дверь = next(p for p in cabinet.parts if p.name == "Дверь")
        expected_width = (900 - Rules.DOOR_GAP) // 2
        assert дверь.width == expected_width
        assert дверь.quantity == 2

    def test_полки_уже_шкафа(self):
        """Полки должны быть уже глубины на 2*EDGE_CLEARANCE (не упираются в край),
        плюс получают припуск на загиб (жёсткость) - одинарный, 20мм на сторону"""
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        полка = next(p for p in cabinet.parts if p.name == "Полка")
        base_height = 500 - Rules.EDGE_CLEARANCE * 2
        assert полка.height == base_height + 40  # + припуск на загиб по высоте
        assert полка.corner_relief > 0, "У полки должна быть угловая прорезь"

    def test_нет_полок_если_shelves_0(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 0, 1.0)
        полки = [p for p in cabinet.parts if p.name == "Полка"]
        assert полки[0].quantity == 0 if полки else True

    def test_вес_положительный(self):
        cabinet = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        assert cabinet.weight > 0


# ==================== ТУМБА ====================
class TestTumba:
    def test_тумба_без_дверей(self):
        """Тумба - открытый модуль, у неё нет деталей 'Дверь'"""
        tumba = TumbaBuilder.build(850, 600, 500, 1.2, shelves=1)
        двери = [p for p in tumba.parts if p.name == "Дверь"]
        assert len(двери) == 0

    def test_тумба_имеет_боковины_крышу_дно(self):
        tumba = TumbaBuilder.build(850, 600, 500, 1.2, shelves=1)
        имена = {p.name for p in tumba.parts}
        assert "Боковина" in имена
        assert "Крыша" in имена
        assert "Дно" in имена


# ==================== ШКАФ ПОД МОЙКУ ====================
class TestSinkCabinet:
    def test_имеет_вырез_под_мойку(self):
        """У крыши шкафа под мойку должен быть один прямоугольный вырез"""
        sink = SinkCabinetBuilder.build(850, 600, 500, 1.2)
        крыша = next(p for p in sink.parts if "мойк" in p.name.lower())
        assert len(крыша.cutouts) == 1
        assert крыша.cutouts[0].shape == "rect"

    def test_вырез_внутри_детали(self):
        """Вырез должен полностью помещаться внутри детали крыши"""
        sink = SinkCabinetBuilder.build(850, 600, 500, 1.2)
        крыша = next(p for p in sink.parts if "мойк" in p.name.lower())
        cut = крыша.cutouts[0]
        # Центр выреза + половина размера не должны выходить за края
        assert cut.x - cut.width / 2 >= 0
        assert cut.x + cut.width / 2 <= крыша.width
        assert cut.y - cut.height / 2 >= 0
        assert cut.y + cut.height / 2 <= крыша.height


# ==================== ШКАФ ПОД ГРИЛЬ ====================
class TestGrillCabinet:
    def test_имеет_вырез_под_гриль(self):
        grill = GrillCabinetBuilder.build(850, 700, 500, 1.5)
        крыша = next(p for p in grill.parts if "гриль" in p.name.lower())
        assert len(крыша.cutouts) == 1
        assert крыша.cutouts[0].shape == "rect"

    def test_имеет_вентиляционные_отверстия(self):
        """Одна из боковин должна иметь круглые вентотверстия"""
        grill = GrillCabinetBuilder.build(850, 700, 500, 1.5, vent_holes=6)
        боковина_с_вент = next(p for p in grill.parts if "вентил" in p.name.lower())
        круги = [c for c in боковина_с_вент.cutouts if c.shape == "circle"]
        assert len(круги) == 6

    def test_боковин_две_но_разные(self):
        """У шкафа под гриль ДВЕ боковины: одна глухая, одна с вентиляцией"""
        grill = GrillCabinetBuilder.build(850, 700, 500, 1.5)
        боковины = [p for p in grill.parts if "боковин" in p.name.lower()]
        assert len(боковины) == 2
        # У одной должны быть вырезы, у другой - нет
        with_cutouts = sum(1 for p in боковины if p.cutouts)
        assert with_cutouts == 1


# ==================== СТОЛЕШНИЦА ====================
class TestCountertop:
    def test_столешница_одна_деталь(self):
        ct = CountertopBuilder.build(1900, 600, 2.0)
        assert len(ct.parts) == 1

    def test_имеет_три_линии_гиба(self):
        """Столешница имеет отбортовку с 3 сторон (кроме задней у стены)"""
        ct = CountertopBuilder.build(1900, 600, 2.0, bend_height=30)
        столешница = ct.parts[0]
        assert len(столешница.bend_lines) == 3
        кромки = {b.edge for b in столешница.bend_lines}
        assert "left" in кромки
        assert "right" in кромки
        assert "bottom" in кромки
        assert "top" not in кромки  # задняя сторона у стены - без борта

    def test_вырез_если_указан(self):
        ct = CountertopBuilder.build(1900, 600, 2.0,
                                        cutout_type="sink",
                                        cutout_width=400, cutout_height=350)
        столешница = ct.parts[0]
        assert len(столешница.cutouts) == 1