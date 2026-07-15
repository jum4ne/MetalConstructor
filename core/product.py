from dataclasses import dataclass, field
from core.models import Part, TubePart

@dataclass
class Product:
    name: str
    parts: list = field(default_factory=list)
    tubes: list = field(default_factory=list)  # каркас из профильной трубы

    @property
    def total_parts(self):
        return sum(p.quantity for p in self.parts)

    @property
    def total_area(self):
        return sum(p.area * p.quantity for p in self.parts)

    @property
    def total_tube_length_m(self):
        """Суммарная длина всех труб каркаса, метры"""
        return sum(t.total_length_mm for t in self.tubes) / 1000

    def add_part(self, part: Part):
        # Проставляем description и is_hidden_in_assembly по роли детали
        # (см. core/part_semantics). Делаем это здесь, в одной точке, а не
        # в каждом билдере отдельно - иначе новый билдер легко забудет их
        # заполнить, и в документацию уйдёт деталь без пояснения и без
        # обязательной пометки о скрытости.
        #
        # annotate() не затирает уже заполненные вручную поля, поэтому
        # конструктор может переопределить и текст, и флаг в UI.
        from core.part_semantics import annotate
        annotate(part)
        self.parts.append(part)

    def add_tube(self, tube: TubePart):
        self.tubes.append(tube)