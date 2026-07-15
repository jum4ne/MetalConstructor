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
    def weight(self):
        return self.total_area * Rules.STEEL_DENSITY * self.thickness