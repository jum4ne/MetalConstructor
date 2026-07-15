"""
Тесты сохранения и загрузки модулей и проектов кухни (project_io.py).

Проверяют, что после round-trip (сохранил -> загрузил) данные не потерялись:
все детали, вырезы, линии гиба, вес - на месте.
"""
import pytest
import json
import os

from core.project_io import (
    save_module, load_module,
    save_kitchen_project, load_kitchen_project,
)
from core.calculator import CabinetCalculator
from core.builders import (
    TumbaBuilder, SinkCabinetBuilder, GrillCabinetBuilder, CountertopBuilder,
)
from core.kitchen_project import KitchenProject


# tmp_path - встроенная фикстура pytest, даёт временную папку для теста
class TestSaveLoadModule:
    def test_шкаф_сохраняется_и_загружается(self, tmp_path):
        original = CabinetCalculator.calculate(1800, 900, 500, 4, 1.0)
        path = tmp_path / "cabinet.json"

        save_module(original, str(path))
        loaded, _ = load_module(str(path))

        assert loaded.name == original.name
        assert loaded.total_parts == original.total_parts
        assert loaded.width == original.width
        assert loaded.height == original.height

    def test_шкаф_под_мойку_сохраняет_вырез(self, tmp_path):
        """У шкафа под мойку крыша имеет прямоугольный вырез - он должен уцелеть"""
        original = SinkCabinetBuilder.build(850, 600, 500, 1.2)
        path = tmp_path / "sink.json"

        save_module(original, str(path))
        loaded, _ = load_module(str(path))

        крыша_orig = next(p for p in original.parts if p.cutouts)
        крыша_load = next(p for p in loaded.parts if p.cutouts)

        assert len(крыша_orig.cutouts) == len(крыша_load.cutouts)
        cut_orig = крыша_orig.cutouts[0]
        cut_load = крыша_load.cutouts[0]
        assert cut_orig.shape == cut_load.shape
        assert cut_orig.width == cut_load.width
        assert cut_orig.height == cut_load.height
        assert cut_orig.x == cut_load.x
        assert cut_orig.y == cut_load.y

    def test_столешница_сохраняет_гибы(self, tmp_path):
        original = CountertopBuilder.build(1900, 600, 2.0, bend_height=30)
        path = tmp_path / "countertop.json"

        save_module(original, str(path))
        loaded, _ = load_module(str(path))

        assert len(loaded.parts[0].bend_lines) == len(original.parts[0].bend_lines)

    def test_шкаф_под_гриль_сохраняет_вентиляцию(self, tmp_path):
        """Круглые вырезы вентиляции тоже должны уцелеть"""
        original = GrillCabinetBuilder.build(850, 700, 500, 1.5, vent_holes=6)
        path = tmp_path / "grill.json"

        save_module(original, str(path))
        loaded, _ = load_module(str(path))

        vent_orig = next(p for p in original.parts if "вентил" in p.name.lower())
        vent_load = next(p for p in loaded.parts if "вентил" in p.name.lower())
        assert len(vent_orig.cutouts) == len(vent_load.cutouts) == 6
        assert all(c.shape == "circle" for c in vent_load.cutouts)


class TestSaveLoadKitchenProject:
    def test_проект_из_нескольких_модулей(self, tmp_path):
        project = KitchenProject(name="Кухня Иванова", client="Иванов И.И.")
        project.add_module(SinkCabinetBuilder.build(850, 600, 500, 1.2))
        project.add_module(GrillCabinetBuilder.build(850, 700, 500, 1.5))
        project.add_module(TumbaBuilder.build(850, 500, 500, 1.2, shelves=1))

        path = tmp_path / "kitchen.json"
        save_kitchen_project(project, str(path))
        loaded = load_kitchen_project(str(path))

        assert loaded.name == project.name
        assert loaded.client == project.client
        assert len(loaded.modules) == len(project.modules)
        assert loaded.total_parts == project.total_parts
        # Вес должен совпадать с точностью до грамма
        assert abs(loaded.weight - project.weight) < 0.001

    def test_загрузка_проекта_через_load_module_даёт_понятную_ошибку(self, tmp_path):
        """Файл проекта кухни нельзя открыть как модуль - должна быть ясная ошибка"""
        project = KitchenProject(name="Test")
        project.add_module(TumbaBuilder.build(850, 600, 500, 1.2, shelves=1))
        path = tmp_path / "kitchen.json"
        save_kitchen_project(project, str(path))

        with pytest.raises(ValueError) as exc:
            load_module(str(path))
        # ошибка должна быть человеко-понятной, а не "KeyError: 'parts'"
        assert "проект" in str(exc.value).lower()