"""
Проект уличной кухни целиком: несколько модулей вместе,
общий раскрой по всем деталям сразу и общая смета.

Каждый модуль в проекте имеет ПОЗИЦИЮ (x, y в мм) и УГОЛ ПОВОРОТА (градусы) -
это нужно для построения общей сцены кухни целиком (уровень "Комплекс" в
документации, а не только по отдельным модулям). Если позицию не задавать
явно, модули автоматически встают в ряд слева направо (типовая прямая
кухня) - это поведение по умолчанию, обратно совместимое со старым кодом.
"""
from dataclasses import dataclass, field, replace
from core.rules import Rules


@dataclass
class ModulePlacement:
    """Положение модуля в общей сцене кухни"""
    x: float = 0        # мм, положение по горизонтали (слева направо)
    y: float = 0        # мм, положение по глубине (для угловых кухонь)
    angle: float = 0    # градусы поворота модуля (0/90/180/270 - для угла кухни)


@dataclass
class KitchenProject:
    name: str
    client: str = ""
    modules: list = field(default_factory=list)
    module_type: str = "Проект кухни"
    placements: list = field(default_factory=list)  # ModulePlacement, по одному на модуль

    def add_module(self, module, x=None, y=None, angle=0):
        """
        Добавить модуль в проект. Если x не задан явно - модуль встаёт
        в ряд сразу после предыдущего (авто-раскладка "по порядку слева
        направо", подходит для типовой прямой кухни без угла).
        """
        if x is None:
            x = sum(m.width for m in self.modules)  # встык за предыдущим модулем
        if y is None:
            y = 0
        self.modules.append(module)
        self.placements.append(ModulePlacement(x=x, y=y, angle=angle))

    def set_module_placement(self, index, x=None, y=None, angle=None):
        """Изменить положение/угол уже добавленного модуля (для ручной раскладки в UI)"""
        if not (0 <= index < len(self.placements)):
            return
        p = self.placements[index]
        self.placements[index] = ModulePlacement(
            x=p.x if x is None else x,
            y=p.y if y is None else y,
            angle=p.angle if angle is None else angle,
        )

    def remove_module(self, index):
        if 0 <= index < len(self.modules):
            self.modules.pop(index)
            if 0 <= index < len(self.placements):
                self.placements.pop(index)

    @property
    def parts(self):
        """
        Все детали всех модулей вместе, с префиксом названия модуля.

        ВАЖНО: берём module.all_parts (СВОИ + детали подсборок), а не
        module.parts. Раньше здесь был module.parts — и панели ящиков,
        декоративные накладки и панели фасада (14 типов, 16 шт на комплексе
        К 01) НЕ попадали ни в общий DXF-раскрой, ни в массу/смету: цех
        получал неполный комплект.
        """
        combined = []
        for module in self.modules:
            for part in module.all_parts:
                combined.append(replace(part, name=f"[{module.name}] {part.name}"))
        return combined

    @property
    def tubes(self):
        """Все трубы каркаса всех модулей вместе (вкл. подсборки), с префиксом модуля"""
        combined = []
        for module in self.modules:
            for tube in module.all_tubes:
                combined.append(replace(tube, note=f"[{module.name}] {tube.note}".strip()))
        return combined

    @property
    def total_tube_length_m(self):
        return sum(t.total_length_mm for t in self.tubes) / 1000

    @property
    def total_parts(self):
        return sum(p.quantity for p in self.parts)

    @property
    def total_area(self):
        return sum(p.area * p.quantity for p in self.parts)

    @property
    def weight(self):
        return sum(p.area * p.quantity * Rules.STEEL_DENSITY * p.thickness for p in self.parts)