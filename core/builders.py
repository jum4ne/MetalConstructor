"""
Билдеры модулей уличной кухни.
Каждый билдер собирает список деталей (Part) для конкретного типа модуля
и возвращает объект Module.
"""
from core.models import Part, BendLine, Cutout
from core.module import Module
from core.rules import Rules
from core.tube_frame import build_frame
from core.sheet_metal import add_flange

# Несущие листовые детали получают загиб 20мм по периметру (жёсткость), как
# в реальных чертежах. Раньше add_flange() вызывался ТОЛЬКО в старом
# CabinetCalculator, а билдеры модулей уличной кухни его не звали вовсе -
# из-за этого у всех деталей проекта не было ни одной линии гиба, и на
# чертёж уходила "плоская деталь" без развёртки и без угловых релиз-прорезей.
# Для цеха это значит: нет данных для гибочного станка и нет припуска в
# раскрое. Здесь это исправлено.
#
# Что гнём, а что нет:
#   боковина, дно, полка - гнём по всем 4 краям (несущая обшивка на каркас)
#   крыша с вырезом      - гнём (борта вниз), вырез при этом ставится ПОСЛЕ
#                          гибки, т.к. add_flange меняет width/height и
#                          координаты выреза иначе уехали бы от центра
#   дверь                - плоская (навесной элемент, жёсткость не нужна)


class TumbaBuilder:
    """Открытая тумба без дверей"""

    @staticmethod
    def build(height, width, depth, thickness, shelves=1):
        parts = [
            add_flange(Part("Боковина", depth, height, 2, thickness)),
            add_flange(Part("Крыша", width, depth, 1, thickness)),
            add_flange(Part("Дно", width, depth, 1, thickness)),
        ]
        if shelves > 0:
            parts.append(add_flange(Part(
                "Полка", width, depth - Rules.EDGE_CLEARANCE * 2, shelves, thickness
            )))

        module = Module(
            name="Тумба открытая", module_type="Тумба",
            height=height, width=width, depth=depth, thickness=thickness,
        )
        for p in parts:
            module.add_part(p)
        for t in build_frame(height, width, depth):
            module.add_tube(t)
        return module


class SinkCabinetBuilder:
    """Шкаф под мойку — верхняя панель с прямоугольным вырезом по центру"""

    @staticmethod
    def build(height, width, depth, thickness,
              sink_cut_width=400, sink_cut_height=350):

        parts = [
            add_flange(Part("Боковина", depth, height, 2, thickness)),
            add_flange(Part("Дно", width, depth, 1, thickness)),
        ]

        # ВАЖЕН ПОРЯДОК: сначала загиб (он меняет width/height детали),
        # только потом вырез - его координаты абсолютные, и если поставить
        # вырез до гибки, центр уедет на величину припуска.
        top = add_flange(Part("Крыша (вырез под мойку)", width, depth, 1, thickness))
        top.cutouts.append(Cutout(
            shape="rect", x=top.width / 2, y=top.height / 2,
            width=sink_cut_width, height=sink_cut_height,
            label="Вырез под мойку"
        ))
        parts.append(top)

        door_width = (width - Rules.DOOR_GAP) // 2
        parts.append(Part("Дверь", door_width, height - Rules.EDGE_CLEARANCE, 2, thickness))

        module = Module(
            name="Шкаф под мойку", module_type="Шкаф под мойку",
            height=height, width=width, depth=depth, thickness=thickness,
        )
        for p in parts:
            module.add_part(p)
        for t in build_frame(height, width, depth):
            module.add_tube(t)
        return module


class GrillCabinetBuilder:
    """Шкаф под варочную панель/гриль — вырез в крыше + вентиляционные отверстия в боковине"""

    @staticmethod
    def build(height, width, depth, thickness,
              hob_cut_width=560, hob_cut_height=480,
              vent_holes=6, vent_hole_radius=8):

        parts = [add_flange(Part("Боковина глухая", depth, height, 1, thickness))]

        # Загиб ДО расстановки вент. отверстий (см. комментарий выше о порядке):
        # шаг сетки отверстий считаем уже по размеру ЗАГОТОВКИ, иначе крайние
        # отверстия попадут на линию гиба и станок их порвёт.
        vent_side = add_flange(Part("Боковина с вентиляцией", depth, height, 1, thickness))
        cols = 2
        rows = max(1, vent_holes // cols)
        step_x = vent_side.width / (cols + 1)
        step_y = vent_side.height / (rows + 1)
        count = 0
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                if count >= vent_holes:
                    break
                vent_side.cutouts.append(Cutout(
                    shape="circle", x=c * step_x, y=r * step_y,
                    radius=vent_hole_radius, label="Вент."
                ))
                count += 1
        parts.append(vent_side)

        parts.append(add_flange(Part("Дно", width, depth, 1, thickness)))

        top = add_flange(Part("Крыша (вырез под гриль)", width, depth, 1, thickness))
        top.cutouts.append(Cutout(
            shape="rect", x=top.width / 2, y=top.height / 2,
            width=hob_cut_width, height=hob_cut_height,
            label="Вырез под гриль/варочную панель"
        ))
        parts.append(top)

        module = Module(
            name="Шкаф под гриль", module_type="Шкаф под гриль",
            height=height, width=width, depth=depth, thickness=thickness,
        )
        for p in parts:
            module.add_part(p)
        for t in build_frame(height, width, depth):
            module.add_tube(t)
        return module


class CountertopBuilder:
    """Столешница — лист с отбортовкой по периметру (кроме заднего края у стены)
    и опциональным вырезом под мойку/варочную панель"""

    @staticmethod
    def build(width, depth, thickness, bend_height=30,
              cutout_type=None, cutout_width=0, cutout_height=0,
              cutout_x=None, cutout_y=None):

        top = Part("Столешница", width, depth, 1, thickness)

        top.bend_lines.append(BendLine(edge="left", offset=bend_height, direction="up", note=f"борт {bend_height}мм"))
        top.bend_lines.append(BendLine(edge="right", offset=bend_height, direction="up", note=f"борт {bend_height}мм"))
        top.bend_lines.append(BendLine(edge="bottom", offset=bend_height, direction="up", note=f"борт {bend_height}мм"))

        if cutout_type:
            cx = cutout_x if cutout_x is not None else width / 2
            cy = cutout_y if cutout_y is not None else depth / 2
            top.cutouts.append(Cutout(
                shape="rect", x=cx, y=cy,
                width=cutout_width, height=cutout_height,
                label="Вырез под мойку" if cutout_type == "sink" else "Вырез под варочную панель"
            ))

        module = Module(
            name="Столешница", module_type="Столешница",
            height=thickness, width=width, depth=depth, thickness=thickness,
        )
        module.add_part(top)
        return module


MODULE_TYPES = {
    "cabinet": "Шкаф (закрытый, с дверями)",
    "tumba": "Тумба открытая",
    "sink_cabinet": "Шкаф под мойку",
    "grill_cabinet": "Шкаф под гриль/варочную панель",
    "countertop": "Столешница",
}

# Точное соответствие module.module_type (как он реально записан в объекте) -> ключ типа.
# Отдельно от MODULE_TYPES, т.к. подписи в выпадающем списке длиннее/красивее,
# чем короткие module_type, которые реально хранятся в объектах Module.
MODULE_TYPE_BY_LABEL = {
    "Шкаф": "cabinet",
    "Тумба": "tumba",
    "Шкаф под мойку": "sink_cabinet",
    "Шкаф под гриль": "grill_cabinet",
    "Столешница": "countertop",
}


# --- Регистрация настоящих модулей комплекса К 01.00.00.000 ---
# Импорт в КОНЦЕ файла, а не сверху: core.real_modules сам импортирует
# зависимости из builders-слоя, поэтому импорт сверху дал бы цикл.
def _register_real_modules():
    try:
        from core import real_modules
        real_modules.register_into(MODULE_TYPES, MODULE_TYPE_BY_LABEL)
    except Exception:
        # Каталог не критичен для ядра: если он сломан, базовые
        # 5 модулей должны продолжать работать.
        pass


_register_real_modules()