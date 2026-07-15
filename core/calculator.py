from core.models import Part
from core.rules import Rules
from core.sheet_metal import add_flange
from core.tube_frame import build_frame
from models.cabinet import Cabinet

class CabinetCalculator:
    @staticmethod
    def calculate(height, width, depth, shelves, thickness):
        parts = []

        # Боковина и полка - несущие элементы, получают загиб на 20мм
        # (подтверждено разбором реальных профессиональных чертежей -
        # одинарный загиб, без подгибки кромки, т.к. жёсткость всей
        # конструкции обеспечивает сварной каркас, а не сама обшивка).
        # Плоская заготовка при этом крупнее финального размера - это
        # учтено внутри add_flange, раскрой считает уже по факту.
        боковина = Part("Боковина", depth, height, 2, thickness)
        parts.append(add_flange(боковина))

        parts.append(Part("Крыша", width, depth, 1, thickness))
        parts.append(Part("Дно", width, depth, 1, thickness))

        полка = Part("Полка", width, depth - Rules.EDGE_CLEARANCE * 2, shelves, thickness)
        parts.append(add_flange(полка))

        door_width = (width - Rules.DOOR_GAP) // 2
        parts.append(Part("Дверь", door_width, height - Rules.EDGE_CLEARANCE, 2, thickness))

        cabinet = Cabinet(name="Металлический шкаф", height=height, width=width, depth=depth, thickness=thickness)
        for p in parts:
            cabinet.add_part(p)
        for t in build_frame(height, width, depth):
            cabinet.add_tube(t)
        return cabinet