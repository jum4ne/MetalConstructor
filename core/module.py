"""Базовый класс модуля уличной кухни (тумба, шкаф, столешница и т.д.)"""
from dataclasses import dataclass, field
from core.product import Product
from core.rules import Rules

@dataclass
class Module(Product):
    module_type: str = "Модуль"
    height: int = 0
    width: int = 0
    depth: int = 0
    thickness: float = Rules.DEFAULT_THICKNESS

    # Заказчик. Нужен, чтобы выгрузки легли в папку заказа с понятным именем
    # (cad/orders/2026-07-16_Иванов_Секция-с-ящиками/) - см. core/order_paths.
    # У KitchenProject такое поле уже было, у одиночного модуля - не было.
    client: str = ""

    # Вложенные сборочные единицы (напр. "Ящик под хранение" внутри "Секции
    # с ящиками"). Дерево сборки (core/assembly_tree) рекурсивно обходит это
    # поле: каждая подсборка получает свой раздел с разделителем, сборочными
    # видами, ведомостью и чертежами СВОИХ деталей - и закрывается целиком
    # раньше, чем начнутся детали родителя.
    #
    # Сейчас ни один билдер подсборок не создаёт (модули плоские), но
    # экспортер уже умеет их выпускать - достаточно заполнить это поле.
    subassemblies: list = field(default_factory=list)

    def add_subassembly(self, module):
        self.subassemblies.append(module)
        return module

    @property
    def all_parts(self):
        """
        СВОИ детали + детали ВСЕХ подсборок (рекурсивно).

        `parts` намеренно остаётся «только свои» — на нём держатся ведомость
        узла и дерево сборки, где подсборка идёт отдельным разделом. Но для
        раскроя и сметы нужны ВСЕ физические детали: иначе панели ящиков и
        фасада не попадали в общий DXF, и цех резал неполный комплект.
        """
        out = list(self.parts)
        for sub in self.subassemblies:
            out.extend(sub.all_parts)
        return out

    @property
    def all_tubes(self):
        """Свои трубы + трубы всех подсборок (рекурсивно) — см. all_parts."""
        out = list(getattr(self, "tubes", []) or [])
        for sub in self.subassemblies:
            out.extend(sub.all_tubes)
        return out

    @property
    def weight(self):
        return self.total_area * Rules.STEEL_DENSITY * self.thickness