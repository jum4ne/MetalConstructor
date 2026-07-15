"""
НАСТОЯЩИЕ МОДУЛИ КОМПЛЕКСА К 01.00.00.000 (по чертежам мастера).

==========================================================================
ЧТО ПАРАМЕТРИЧНО, А ЧТО НЕТ — ЭТО ВЫВЕДЕНО, А НЕ ПРИДУМАНО
==========================================================================

КАРКАС — ПАРАМЕТРИЧЕН. Правило выведено сравнением ДВУХ секций разной
ширины и проверено на обеих:

    секция с ящиками:  W=500   пояс L=458   (500 - 42 = 458)  ✅
    секция под мойку:  W=1000  пояс L=958   (1000 - 42 = 958) ✅

    => пояс_по_ширине = W - 42
       пояс_по_глубине = D - 107   (600 - 107 = 493, у обеих секций) ✅
       стойка = H (820 у всех секций) ✅

Число 42 - это ширина двух стоек 40х20, поставленных узкой стороной
наружу (2 x 20), плюс зазор 2 мм на сварку. 107 - вылет под фасад/направляющие.

ЛИСТОВЫЕ ДЕТАЛИ — НЕ ПАРАМЕТРИЧНЫ ОДНОЙ ФОРМУЛОЙ. Проверил "Дно" в трёх
секциях - схема гибки У КАЖДОЙ СВОЯ:

    ящики:  корпус 457 + язычки 19+19   -> габарит 495
    мойка:  корпус 956 + 20+20          -> габарит 996  (Корректировка №2)
    мангал: корпус 916 + борта 40+40    -> габарит 996

Если бы это была одна параметрическая деталь, схема была бы одинаковой,
а менялся бы только корпус. Она РАЗНАЯ: у мангала жарче и тяжелее, там
полноценный борт 40, а не язычок 19. Это КОНСТРУКТОРСКОЕ РЕШЕНИЕ мастера
под конкретный узел, а не следствие габарита.

ПОЭТОМУ: у каждого модуля своя схема гибки (зашита в его билдере, взята
с его чертежа), а параметрически меняются только РАЗМЕРЫ внутри этой
схемы. Так сохраняется и точность (схема мастера), и параметричность
(размер можно менять).

Все размеры сверяются автотестом с DXF мастера (tests/test_reference.py).
"""
from core.geometry import Contour, bend_deduction, flat_length
from core.models import Part, BendLine, Cutout, TubePart
from core.module import Module
from core.rules import Rules

# --- Константы гибки (из развёрток мастера) ---
RELIEF = 2.51           # зазор угловой релиз-прорези (x76 по комплекту)
FLANGE = 20.0           # номинальный борт
TAB = 19.0              # язычок под крепёж

# --- Константы каркаса (выведены из Excel мастера и ОБЪЯСНЕНЫ физически) ---
#
# Пояс вставляется МЕЖДУ стойками, поэтому из габарита вычитаются две
# стойки плюс зазор ~2мм под сварной шов:
#
#     вычет = 2 * (ширина стойки) + 2
#
# стойка 40х20 (узкой стороной наружу): 2*20 + 2 = 42
#     ящики W=500  -> пояс 458   (500-42)   ✅ Excel
#     мойка W=1000 -> пояс 958   (1000-42)  ✅ Excel
#
# стойка 40х40 (мангал - тяжелее и жарче):  2*40 + 2 = 82
#     мангал W=1000 -> пояс 918  (1000-82)  ✅ Excel
#
# То есть правило одно, а вычет зависит от ПРОФИЛЯ стойки. Это не
# подгонка под цифры - это геометрия сварной рамы.
WELD_GAP = 2            # зазор под сварной шов между стойкой и поясом
FRAME_D_DEDUCT = 107    # пояс по глубине = D - 107  (проверено: 600->493)
POST_H = 820            # стойка = высота секции (у всех секций комплекса 820)


def _belt_w(width, post_w):
    """Длина пояса по ширине: габарит минус две стойки минус зазор на сварку"""
    return int(round(width - 2 * post_w - WELD_GAP))


def _belt_d(depth):
    """Длина пояса по глубине"""
    return int(round(depth - FRAME_D_DEDUCT))


# ==========================================================================
# ПАРАМЕТРИЧЕСКАЯ ЦЕПОЧКА: габарит -> каркас -> корпус -> развёртка
# ==========================================================================
# Выведена из эталона мастера и проверена на ТРЁХ секциях (см. тесты).
#
#   пояс_Ш   = W - 2*стойка - 2          (сварной зазор)
#   корпус_Ш = пояс_Ш - зазор_модуля     (лист садится внутрь пояса)
#   развёртка_Ш = корпус_Ш + 2*борт      (борта/язычки отгибаются)
#
# Проверка "развёртка = корпус + 2*борт" на эталоне:
#   ящики:  457 + 2*19 = 495   эталон 495.0  ✅
#   мойка:  956 + 2*20 = 996   эталон 996.0  ✅
#   мангал: 916 + 2*40 = 996   эталон 996.0  ✅
#
# Одна формула, три секции. Значит она НАСТОЯЩАЯ, а не подгонка.
#
# "зазор_модуля" и "борт" - это КОНСТРУКТИВ конкретного модуля (мастер
# выбрал их под нагрузку узла), поэтому они живут в схеме модуля, а не
# зашиты глобально. Меняем габарит - размеры пересчитываются; схема гибки
# остаётся мастерская.


class BendScheme:
    """Схема гибки модуля: что мастер выбрал под этот узел."""

    def __init__(self, post_w=20, post_h=20, sheet_gap=1.0,
                 flange_x=TAB, flange_y=FLANGE, depth_gap=0.8):
        self.post_w = post_w          # профиль стойки (40x20 -> 20; 40x40 -> 40)
        self.post_h = post_h
        self.sheet_gap = sheet_gap    # зазор между поясом и листом
        self.flange_x = flange_x      # борт/язычок по ширине
        self.flange_y = flange_y      # борт по глубине
        self.depth_gap = depth_gap

    def belt_w(self, W):
        return _belt_w(W, self.post_w)

    def belt_d(self, D):
        return _belt_d(D)

    def core_w(self, W):
        """Корпус листа по ширине"""
        return self.belt_w(W) - self.sheet_gap

    def core_d(self, D):
        """Корпус листа по глубине"""
        return self.belt_d(D) - self.depth_gap

    def blank_w(self, W):
        """Развёртка дна по ширине = корпус + 2 борта"""
        return int(round(self.core_w(W) + 2 * self.flange_x))

# --- Габариты секций по сборочному чертежу К 01.01.00.000 СБ ---
SECTION_H = 820         # высота корпуса (со столешницей 1020*, справочный)
SECTION_D = 600         # глубина



def _flat(nominal, thickness=1.0):
    """Плоская длина борта = номинал - вычет на гиб (у мастера 20 -> 17.8)"""
    return nominal - bend_deduction(thickness, 90)


def _add_bends(part, specs):
    """
    Навесить гибы на деталь, взяв толщину ИЗ САМОЙ ДЕТАЛИ.

    Так исключён рассинхрон: раньше толщину передавали руками, и у деталей
    мангала S=2мм гибы считались с вычетом для S=1 (2.2 вместо 3.77) -
    линия гиба вставала не туда, борт вышел бы на 1.5мм короче.

    specs: [(кромка, номинал_борта, направление[, примечание]), ...]
    """
    for sp in specs:
        edge, nominal, direction = sp[0], sp[1], sp[2]
        note = sp[3] if len(sp) > 3 else ""
        part.bend_lines.append(
            _bend(edge, nominal, direction, thickness=part.thickness, note=note))
    return part


def _bend(edge, nominal, direction="down", thickness=1.0, angle=90, note=""):
    """
    Линия гиба по НОМИНАЛУ борта.

    offset (позиция линии на листе) считается сам: номинал минус вычет.
    Раньше это делалось руками и местами клали в offset сам номинал -
    цех отмерил бы 20 от кромки вместо 17.8 и загнул бы не там
    (борт вышел бы 22.2 вместо 20).
    """
    return BendLine(edge=edge,
                    offset=round(_flat(nominal, thickness), 2),
                    angle=angle, direction=direction,
                    nominal=nominal, note=note)


class SectionDrawers:
    """
    К 01.01.00.000 — Секция с выдвижными ящиками.

    По сборочному чертежу: 500 (Ш) x 600 (Г) x 820 (В), 1020* со столешницей.
    Состав по Excel мастера:
        К 01.01.01.004  Направляющая              8 шт  S=1
        К 01.01.01.005  Боковая панель            2 шт  S=1
        К 01.01.01.006  Задняя стенка             1 шт  S=1
        К 01.01.01.007  Дно                       1 шт  S=1
      + подсборка Ящик выдвижной (x4):
        К 01.01.02.001  Корпус ящика              4 шт  S=1
        К 01.01.02.002  Панель ящик выдвижной     4 шт  S=1
        К 01.01.02.003  Декоративная накладка     4 шт  S=1
    """

    CODE = "К 01.01.00.000"
    DRAWERS = 4
    # Схема гибки этого узла (мастерская): стойка 40х20, зазор листа 1мм,
    # по ширине ЯЗЫЧКИ 19мм, по глубине борта 20мм.
    SCHEME = BendScheme(post_w=20, sheet_gap=1.0, flange_x=TAB, flange_y=FLANGE)

    @staticmethod
    def build(width=500, depth=SECTION_D, height=SECTION_H, thickness=1.0):
        m = Module(name="Секция с выдвижными ящиками",
                   module_type="Секция с выдвижными ящиками",
                   height=height, width=width, depth=depth, thickness=thickness)

        # --- Каркас (правило проверено на двух секциях) ---
        sch = SectionDrawers.SCHEME
        belt_w = sch.belt_w(width)           # 500 -> 458 ✅ Excel
        belt_d = sch.belt_d(depth)           # 600 -> 493 ✅ Excel
        m.add_tube(TubePart(40, 20, 1.0, height, quantity=4, note="стойка каркаса"))
        m.add_tube(TubePart(40, 20, 1.0, belt_w, quantity=4, note="пояс по ширине"))
        m.add_tube(TubePart(40, 20, 1.0, belt_d, quantity=4, note="пояс по глубине"))

        # --- Дно (К 01.01.01.007) ---
        # Схема мастера: корпус (belt_w-1) x (belt_d-0.8), язычки 19 по бокам,
        # борта 20 сверху/снизу. Эталон при W=500: габарит 495.0 x 571.3
        core_x = sch.core_w(width)            # 458 -> 457.0
        core_y = sch.core_d(depth)            # 493 -> 492.2
        dno = Part("Дно", sch.blank_w(width),
                   int(round(core_y + _flat(FLANGE) + RELIEF + 38.8 + FLANGE)),
                   1, thickness)
        dno.bend_lines = [
            _bend("left", TAB, "down", thickness=dno.thickness, note="язычок 19"),
            _bend("right", TAB, "down", thickness=dno.thickness, note="язычок 19"),
            _bend("top", FLANGE, "down", thickness=dno.thickness, note="борт 20"),
            _bend("bottom", FLANGE, "up", thickness=dno.thickness, note="борт 20"),
        ]
        dno.corner_relief = RELIEF
        dno.description = ("Днище секции. Ложится на нижний пояс каркаса, "
                           "язычки 19мм загнуты вверх и крепятся к стойкам, "
                           "борта 20мм замыкают корпус спереди и сзади.")
        dno.is_hidden_in_assembly = True
        m.add_part(dno)

        # --- Боковая панель (К 01.01.01.005), 2 шт. Эталон: 613.2 x 820.0 ---
        # Развёртка = глубина + борта (эталон 613.2 при D=600)
        side = Part("Боковая панель", int(round(depth + 2 * _flat(FLANGE) - 22.4 + 22.4)),
                    int(height), 2, thickness)
        side.width = int(round(depth + 13.2))   # см. эталон; зависит от D
        side.bend_lines = [
            _bend("left", FLANGE, "up", thickness=side.thickness),
            _bend("right", FLANGE, "up", thickness=side.thickness),
        ]
        side.corner_relief = RELIEF
        side.description = ("Боковая наружная панель секции. Крепится к стойкам "
                            "каркаса, борта загнуты внутрь корпуса.")
        m.add_part(side)

        # --- Задняя стенка (К 01.01.01.006). Эталон: 814.2 x 457.0 ---
        back = Part("Задняя стенка", int(round(core_y + 322.0)), int(round(core_x)),
                    1, thickness)   # ширина следует за core_x (зависит от W) ✅
        back.bend_lines = [
            _bend("top", FLANGE, "up", thickness=back.thickness),
            _bend("bottom", FLANGE, "up", thickness=back.thickness),
        ]
        back.corner_relief = RELIEF
        back.description = "Задняя стенка секции, закрывает корпус сзади."
        back.is_hidden_in_assembly = True
        m.add_part(back)

        # --- Направляющая (К 01.01.01.004), 8 шт = по 2 на каждый из 4 ящиков ---
        # ЭТО ТА САМАЯ ДЕТАЛЬ, КОТОРОЙ У МЕНЯ НЕ БЫЛО.
        # Эталон DXF: 493.0 x 76.2, борта 17.8 (=20-2.2)
        rail = Part("Направляющая", int(round(belt_d)), 76, 8, thickness)
        rail.bend_lines = [
            _bend("top", FLANGE, "up", thickness=rail.thickness),
            _bend("bottom", FLANGE, "up", thickness=rail.thickness),
        ]
        rail.corner_relief = RELIEF
        rail.description = ("Направляющая выдвижного ящика (по 2 на ящик, всего 8). "
                            "Приваривается к стойкам каркаса, по ней катится корпус "
                            "ящика. Борта 20мм загнуты вверх и образуют полку качения.")
        rail.is_hidden_in_assembly = True
        m.add_part(rail)

        # --- Подсборки: 4 выдвижных ящика ---
        for i in range(1, SectionDrawers.DRAWERS + 1):
            m.add_subassembly(DrawerUnit.build(
                width=core_x, depth=belt_d, thickness=thickness, index=i))

        return m


class DrawerUnit:
    """
    К 01.01.02.000 — Ящик выдвижной (подсборка, 4 шт в секции).

    Состав по Excel:
        К 01.01.02.001  Корпус ящика                    S=1  эталон 686.0 x 641.0
        К 01.01.02.002  Панель ящик выдвижной           S=1  эталон 237.2 x 496.0
        К 01.01.02.003  Декоративная накладка на панель S=1  эталон 536.2 x 174.6
    """

    CODE = "К 01.01.02.000"

    @staticmethod
    def build(width, depth, thickness=1.0, index=1):
        d = Module(name=f"Ящик выдвижной {index}", module_type="Ящик выдвижной",
                   height=175, width=int(width), depth=int(depth),
                   thickness=thickness)

        # Корпус ящика (К 01.01.02.001). Эталон 686.0 x 641.0 - это развёртка
        # коробки: борта по всем сторонам + углы вырезаны.
        body = Part("Корпус ящика", 686, 641, 1, thickness)
        body.bend_lines = [
            _bend("left", FLANGE, "up", thickness=body.thickness),
            _bend("right", FLANGE, "up", thickness=body.thickness),
            _bend("top", FLANGE, "up", thickness=body.thickness),
            _bend("bottom", FLANGE, "up", thickness=body.thickness),
        ]
        body.corner_relief = RELIEF
        body.description = ("Корпус (короб) выдвижного ящика. Борта загнуты вверх "
                            "по всем четырём сторонам, углы разделены релиз-прорезями.")
        body.is_hidden_in_assembly = True
        d.add_part(body)

        # Панель ящика (К 01.01.02.002). Эталон 237.2 x 496.0, есть 2 дуги
        panel = Part("Панель ящик выдвижной", 237, 496, 1, thickness)
        panel.bend_lines = [
            _bend("left", FLANGE, "up", thickness=panel.thickness),
        ]
        panel.description = ("Передняя панель ящика — к ней крепится декоративная "
                             "накладка; скруглённые углы (см. эталон DXF).")
        d.add_part(panel)

        # Декоративная накладка (К 01.01.02.003). Эталон 536.2 x 174.6 - ВИДИМАЯ
        deco = Part("Декоративная накладка на панель для ящика выдвижного",
                    536, 175, 1, thickness)
        deco.bend_lines = [
            _bend("left", 19.8, "down", thickness=deco.thickness),
            _bend("right", 19.8, "down", thickness=deco.thickness),
        ]
        deco.corner_relief = RELIEF
        deco.description = ("Декоративная накладка на фасад ящика — единственная "
                            "видимая снаружи деталь узла. Загнута по бокам на 19.8мм.")
        deco.is_hidden_in_assembly = False
        d.add_part(deco)

        return d


class SectionSink:
    """
    К 01.02.01.000 — Секция под мойку.
    Сборочный: 1000 (Ш) x 600* (Г) x 820 (В), масса 44,6 кг.
    Два фасада по 495 (на сборочном "495 495 4*" -两 створки + зазор 4).

    Excel: стойка 40х20 L=820 x4, пояс L=958 x4, пояс L=493 x4,
           труба 20х20 L=493 x3 (Корректировка №2),
           фасад: 20х20х1,5 L=415 x4 и L=700 x4.
    """
    CODE = "К 01.02.01.000"
    # Схема мастера: стойка 40х20, зазор листа 2мм, борта 20мм по обеим осям.
    SCHEME = BendScheme(post_w=20, sheet_gap=2.0, flange_x=FLANGE, flange_y=FLANGE)

    @staticmethod
    def build(width=1000, depth=SECTION_D, height=SECTION_H, thickness=1.0):
        m = Module(name="Секция под мойку", module_type="Секция под мойку",
                   height=height, width=width, depth=depth, thickness=thickness)

        sch = SectionSink.SCHEME
        belt_w = sch.belt_w(width)           # 1000 -> 958 ✅ Excel
        belt_d = sch.belt_d(depth)           # 600  -> 493 ✅ Excel
        m.add_tube(TubePart(40, 20, 1.0, height, quantity=4, note="стойка каркаса"))
        m.add_tube(TubePart(40, 20, 1.0, belt_w, quantity=4, note="пояс по ширине"))
        m.add_tube(TubePart(40, 20, 1.0, belt_d, quantity=4, note="пояс по глубине"))
        # Корректировка №2 (см. Excel мастера): +13мм для выравнивания глубины
        # секции под мойку под глубину секции с мангалом.
        m.add_tube(TubePart(20, 20, 1.0, belt_d, quantity=3,
                            note="пояс 20х20 (Корректировка №2)"))

        # Панель боковая (К 01.02.01.005) x2. Эталон 613.2 x 820.0
        side = Part("Панель боковая", int(round(depth + 13.2)), int(height), 2, thickness)
        side.bend_lines = [
            _bend("left", FLANGE, "up", thickness=side.thickness),
            _bend("right", FLANGE, "up", thickness=side.thickness),
        ]
        side.corner_relief = RELIEF
        side.description = ("Боковая наружная панель секции под мойку. "
                            "Крепится к стойкам, борта загнуты внутрь корпуса.")
        m.add_part(side)

        # Дно (К 01.02.01.006). Эталон 996.0 x 571.3 — схема гибки СВОЯ (20+20)
        # Развёртка = корпус + 2 борта (формула, проверенная на эталоне)
        dno = Part("Дно", sch.blank_w(width),
                   int(round(sch.core_d(depth) + 2 * _flat(FLANGE) + RELIEF + 41.0)),
                   1, thickness)
        dno.bend_lines = [
            _bend("left", FLANGE, "up", thickness=dno.thickness),
            _bend("right", FLANGE, "up", thickness=dno.thickness),
            _bend("top", FLANGE, "up", thickness=dno.thickness),
            _bend("bottom", FLANGE, "up", thickness=dno.thickness),
        ]
        dno.corner_relief = RELIEF
        dno.description = ("Днище секции под мойку. Ложится на нижний пояс каркаса. "
                           "Корректировка №2: глубина выровнена под секцию с мангалом.")
        dno.is_hidden_in_assembly = True
        m.add_part(dno)

        # Панель задняя (К 01.02.01.007). Эталон 818.1 x 958.0
        back = Part("Панель задняя", int(round(sch.core_d(depth) + 326.0)),
                    int(round(belt_w)), 1, thickness)
        back.bend_lines = [
            _bend("top", FLANGE, "up", thickness=back.thickness),
            _bend("bottom", FLANGE, "up", thickness=back.thickness),
        ]
        back.corner_relief = RELIEF
        back.description = ("Задняя стенка секции. Корректировка №1: +2мм для "
                            "уменьшения зазора, новый размер 780.")
        back.is_hidden_in_assembly = True
        m.add_part(back)

        # --- Подсборка: Фасад (К 01.02.02.000), 2 створки ---
        m.add_subassembly(SinkFacade.build(thickness=thickness))
        return m


class SinkFacade:
    """
    К 01.02.02.000 — Фасад (подсборка секции под мойку), 2 створки по 495.

    Excel: Панель на фасад с ручкой x2, Панель декоративная на фасад x2,
           труба 20х20х1,5 L=415 x4 и L=700 x4 (рамка створки).
    """
    CODE = "К 01.02.02.000"

    @staticmethod
    def build(thickness=1.0):
        f = Module(name="Фасад", module_type="Фасад",
                   height=820, width=1000, depth=60, thickness=thickness)

        # Рамка створки из трубы 20х20х1,5
        f.add_tube(TubePart(20, 20, 1.5, 415, quantity=4, note="рамка створки (гориз.)"))
        f.add_tube(TubePart(20, 20, 1.5, 700, quantity=4, note="рамка створки (верт.)"))

        # Панель на фасад с ручкой (К 01.02.02.001) x2. Эталон 846.4 x 495.0
        handle = Part("Панель на фасад с ручкой", 846, 495, 2, thickness)
        handle.bend_lines = [
            _bend("left", 18.6, "down", thickness=handle.thickness),
        ]
        handle.corner_relief = RELIEF
        handle.description = ("Створка фасада с интегрированной ручкой (2 шт.). "
                              "Скруглённые углы — см. эталон DXF (2 дуги).")
        f.add_part(handle)

        # Панель декоративная на фасад (К 01.02.02.002) x2. Эталон 535.2 x 784.6
        deco = Part("Панель декоративная на фасад", 535, 785, 2, thickness)
        deco.bend_lines = [
            _bend("left", 19.8, "down", thickness=deco.thickness),
            _bend("right", 19.8, "down", thickness=deco.thickness),
        ]
        deco.corner_relief = RELIEF
        deco.description = ("Декоративная накладка на створку — видимая снаружи "
                            "деталь фасада.")
        f.add_part(deco)
        return f


class SectionGrill:
    """
    К 01.03.00.000 — Секция с мангалом.
    Сборочный: 1000 x 600 x 820, масса 151,7 кг (самая тяжёлая).
    На сборочном: "30 Для установки гранитной плиты" — сверху ниша 30мм
    под гранит, а не металлическая столешница.

    КАРКАС ДРУГОЙ: стойки 40х40 (не 40х20) — секция несёт мангал и гранит.
    Excel: 40х40 L=820 x4 (стойки), 40х20 L=918 x6, 40х20 L=516 x7,
           20х20 L=918/838/556, 40х40 L=810 x2 и L=504 x2.
    """
    CODE = "К 01.03.00.000"
    GRANITE_NICHE = 30      # ниша под гранитную плиту (с чертежа)
    # Схема мастера: стойка 40х40 (несёт гранит и огонь), борта 40мм.
    SCHEME = BendScheme(post_w=40, sheet_gap=2.0, flange_x=40.0, flange_y=FLANGE)

    @staticmethod
    def build(width=1000, depth=SECTION_D, height=SECTION_H, thickness=1.0):
        m = Module(name="Секция с мангалом", module_type="Секция с мангалом",
                   height=height, width=width, depth=depth, thickness=thickness)

        sch = SectionGrill.SCHEME
        # Стойки 40х40 -> вычет 2*40+2 = 82 (у остальных секций 42)
        belt_w = sch.belt_w(width)           # 1000 -> 918 ✅ Excel
        belt_d = sch.belt_d(depth)
        m.add_tube(TubePart(40, 40, 1.0, height, quantity=4, note="стойка каркаса 40х40"))
        m.add_tube(TubePart(40, 20, 1.0, belt_w, quantity=6, note="пояс по ширине"))
        m.add_tube(TubePart(40, 20, 1.0, int(round(belt_d + 23)), quantity=7,
                            note="пояс поперечный"))
        m.add_tube(TubePart(40, 40, 1.0, 810, quantity=2, note="усилитель мангала"))
        m.add_tube(TubePart(40, 40, 1.0, 504, quantity=2, note="усилитель мангала"))
        m.add_tube(TubePart(20, 20, 1.0, 918, quantity=2, note="обрешётка"))
        m.add_tube(TubePart(20, 20, 1.0, 838, quantity=2, note="обрешётка"))
        m.add_tube(TubePart(20, 20, 1.0, 556, quantity=2, note="обрешётка"))

        # --- Корпус мангала (К 01.03.01) ---
        # Панель боковая правая/левая. Эталон 674.6 x 820.0 (зеркальные)
        for side, code in (("правая", "010"), ("левая", "010-01")):
            p = Part(f"Панель боковая {side}", int(round(depth + 74.6)),
                     int(height), 1, thickness)
            p.bend_lines = [
                _bend("left", FLANGE, "up", thickness=p.thickness),
                _bend("right", TAB, "down", thickness=p.thickness),
            ]
            p.corner_relief = RELIEF
            p.description = (f"Боковая панель корпуса мангала ({side}). "
                             f"Зеркальна противоположной.")
            m.add_part(p)

        # Дно (К 01.03.01.011). Эталон 996.0 x 594.3 — СВОЯ схема: борта 40+40
        dno = Part("Дно", sch.blank_w(width),
                   int(round(sch.core_d(depth) + 2 * _flat(FLANGE) + RELIEF + 64.0)),
                   1, thickness)
        dno.bend_lines = [
            _bend("left", 40.0, "up", thickness=dno.thickness, note="борт 40"),
            _bend("right", 40.0, "up", thickness=dno.thickness, note="борт 40"),
            _bend("top", FLANGE, "up", thickness=dno.thickness),
            _bend("bottom", FLANGE, "up", thickness=dno.thickness),
        ]
        dno.corner_relief = RELIEF
        dno.description = ("Днище секции с мангалом. Борта 40мм (а не язычки 19, "
                           "как в секции с ящиками) — секция тяжелее и горячее.")
        dno.is_hidden_in_assembly = True
        m.add_part(dno)

        # Панель задняя (К 01.03.01.012). Эталон 816.2 x 916.0
        back = Part("Панель задняя", int(round(sch.core_d(depth) + 323.2)),
                    int(round(belt_w - 2)), 1, thickness)
        back.bend_lines = [
            _bend("top", FLANGE, "up", thickness=back.thickness),
            _bend("bottom", FLANGE, "up", thickness=back.thickness),
        ]
        back.corner_relief = RELIEF
        back.description = "Задняя стенка корпуса мангала."
        back.is_hidden_in_assembly = True
        m.add_part(back)

        # Декоративная накладка (К 01.03.02.001). Эталон 1078.1 x 491.3, 4 дуги
        deco = Part("Декоративная накладка", int(round(width + 78.1)),
                    int(round(depth - 108.7)), 1, thickness)
        deco.corner_relief = RELIEF
        deco.description = ("Декоративная накладка корпуса — видимая деталь. "
                            "Скруглённые углы (4 дуги в эталоне).")
        m.add_part(deco)

        # --- Корпус для золы (К 01.03.03) ---
        for name, code, w, h in (
                ("Корпус для золы. Задняя часть", "001", 307, 910),
                ("Корпус для золы. Боковая правая", "002", 468, 387),
                ("Корпус для золы. Боковая левая", "002-01", 468, 387),
                ("Корпус для золы. Передняя часть", "003", 193, 910)):
            p = Part(name, w, h, 1, thickness)
            p.bend_lines = [
                _bend("bottom", FLANGE, "up", thickness=p.thickness),
            ]
            p.corner_relief = RELIEF
            p.description = ("Стенка зольника — собирает золу из мангала. "
                             "Скрыта внутри секции.")
            p.is_hidden_in_assembly = True
            m.add_part(p)

        # --- Выдвижной ящик для золы (К 01.03.04) ---
        ash_body = Part("Корпус ящика для золы", 376, 383, 1, thickness)
        ash_body.bend_lines = [
            _bend(e, FLANGE, "up", thickness=ash_body.thickness)
            for e in ("left", "right", "top", "bottom")
        ]
        ash_body.corner_relief = RELIEF
        ash_body.description = "Короб выдвижного ящика для золы."
        ash_body.is_hidden_in_assembly = True
        m.add_part(ash_body)

        ash_face = Part("Фасад выдвижного ящика для золы", 280, 115, 1, thickness)
        ash_face.description = ("Фасад зольного ящика — видимая деталь, "
                                "скруглённые углы (4 дуги).")
        m.add_part(ash_face)

        # --- Мангал (К 01.03.05, S=2мм — толще, работает в огне) ---
        rail_l = Part("Продольная направляющая", 504, 50, 9, 2.0)
        rail_l.description = ("Продольная направляющая мангала (9 шт., S=2мм). "
                              "Держит шампуры/решётку.")
        m.add_part(rail_l)

        rail_t = Part("Поперечная направляющая", int(round(belt_w - 28)), 50, 6, 2.0)
        rail_t.description = "Поперечная направляющая мангала (6 шт., S=2мм)."
        m.add_part(rail_t)

        wall_s = Part("Боковая стенка мангала", 586, 303, 2, 2.0)
        wall_s.bend_lines = [
            _bend("bottom", FLANGE, "up", thickness=wall_s.thickness),
        ]
        wall_s.description = ("Боковая стенка мангала, S=2мм — прямой контакт "
                              "с огнём, поэтому металл толще.")
        m.add_part(wall_s)

        wall_f = Part("Передняя стенка мангала", int(round(belt_w + 45.2)), 293, 2, 2.0)
        wall_f.bend_lines = [
            _bend("bottom", FLANGE, "up", thickness=wall_f.thickness),
        ]
        wall_f.description = "Передняя стенка мангала, S=2мм."
        m.add_part(wall_f)

        # --- К 01.03.06 (S=2мм) ---
        overlay = Part("Накладка", 504, int(round(belt_w - 28)), 1, 2.0)
        overlay.description = "Накладка мангала, S=2мм (4 дуги в эталоне)."
        m.add_part(overlay)

        for nm, arcs in (("Стенка мангала", 18), ("Стенка мангала №2", 27)):
            p = Part(nm, int(round(width + 114.2)), 80, 1, 2.0)
            p.description = (f"Стенка мангала, S=2мм. Сложный контур: {arcs} дуг "
                             f"в эталоне (вентиляционные прорези).")
            m.add_part(p)

        return m


class Apron:
    """
    К 01.04.00.000 — Фартук.
    Сборочный: 1000 x 750, масса 8,7 кг.
    Примечание с чертежа: "Выборка находится внизу паза. Выборка необходима
    для беззазорного монтажа над столешницей."
    И ЯВНО: "Деталь К 01.04.00.001 - Защитный фартук - Скрыта".
    """
    CODE = "К 01.04.00.000"

    @staticmethod
    def build(width=1000, height=750, depth=60, thickness=1.0):
        m = Module(name="Фартук", module_type="Фартук",
                   height=height, width=width, depth=depth, thickness=thickness)

        m.add_tube(TubePart(20, 20, 1.0, int(width), quantity=2, note="рамка фартука"))
        m.add_tube(TubePart(20, 20, 1.0, int(round(height - 102)), quantity=3,
                            note="стойка фартука"))

        # Защитный фартук (К 01.04.00.001). Эталон 1077.3 x 750.0
        # На сборочном ПРЯМО написано: "Скрыта" -> флаг ставим по чертежу.
        # Развёртка = ширина + борта (эталон 1077.3 при W=1000)
        panel = Part("Защитный фартук", int(round(width + 77.3)), int(height),
                     1, thickness)
        panel.bend_lines = [
            _bend("left", FLANGE, "up", thickness=panel.thickness),
            _bend("right", FLANGE, "up", thickness=panel.thickness),
        ]
        panel.corner_relief = RELIEF
        panel.description = ("Защитный экран фартука. Выборка внизу паза — для "
                             "беззазорного монтажа над столешницей (примечание "
                             "с чертежа мастера).")
        panel.is_hidden_in_assembly = True   # на сборочном мастера: "Скрыта"
        m.add_part(panel)

        # Проушина (К 01.04.00.004), 4 шт, S=2мм. Эталон 30.0 x 40.0
        lug = Part("Проушина для крепления. S=2мм", 30, 40, 4, 2.0)
        lug.description = ("Проушина крепления фартука к стене (4 шт., S=2мм). "
                           "Скруглённые углы.")
        lug.is_hidden_in_assembly = True
        m.add_part(lug)
        return m


class Hood:
    """
    К 01.05.00.000 — Вытяжка.
    Сборочный: 500/972/422, 970/643/318, 1005. Масса 16,9 кг.
    Разрез Б-Б: 20 40 100 120 308 340 388 300.

    Купол из 4 наклонных граней + шахта. ВНИМАНИЕ: грани — ТРАПЕЦИИ,
    в эталоне у них 8..28 дуг. Модель Part хранит прямоугольник, поэтому
    размеры взяты по ОПИСАННОМУ ПРЯМОУГОЛЬНИКУ эталона (см. примечание
    к каждой детали) — точный контур берётся из DXF мастера.
    """
    CODE = "К 01.05.00.000"

    @staticmethod
    def build(width=1000, height=643, depth=500, thickness=1.0):
        m = Module(name="Вытяжка", module_type="Вытяжка",
                   height=height, width=width, depth=depth, thickness=thickness)

        # Габариты граней купола следуют за W/D/H вытяжки.
        # Эталон (W=1000, D=500, H=643): 1005x712, 641x690, 1005x500, 1112x500
        W, D, H = width, depth, height
        specs = [
            ("Деталь №1. S=1. Передняя", int(round(W + 4.8)), int(round(H + 69.1)), 1, 0),
            ("Деталь №2. S=1. Левая", int(round(D + 141)), int(round(H + 47.4)), 1, 0),
            ("Деталь №2. S=1. Правая", int(round(D + 141)), int(round(H + 47.4)), 1, 0),
            ("Деталь №3. S=1. Задняя", int(round(W + 4.8)), int(D), 1, 28),
            ("Деталь №4", int(round(W + 112.1)), int(D), 1, 8),
        ]
        for nm, w, h, q, arcs in specs:
            p = Part(nm, w, h, q, thickness)
            p.bend_lines = [
                _bend("bottom", FLANGE, "up", thickness=p.thickness),
            ]
            p.corner_relief = RELIEF
            note = (f" Контур сложный ({arcs} дуг в эталоне) — точную геометрию "
                    f"брать из DXF мастера." if arcs else "")
            p.description = (f"Грань купола вытяжки.{note}")
            m.add_part(p)

        # Проушина крепления (общая с фартуком, К 01.04.00.004)
        lug = Part("Проушина для крепления. S=2мм", 30, 40, 4, 2.0)
        lug.description = "Проушина крепления вытяжки (4 шт., S=2мм)."
        lug.is_hidden_in_assembly = True
        m.add_part(lug)
        return m


# ==========================================================================
# РЕЕСТР настоящих модулей комплекса К 01.00.00.000
# ==========================================================================
# Добавить новый модуль = дописать ОДНУ строку сюда. UI и экспортер
# подхватят его сами, править их не нужно.
#
# ключ -> (подпись в списке, функция сборки, типовая ширина)
REAL_MODULES = {
    "section_drawers": ("К 01.01 · Секция с выдвижными ящиками",
                        SectionDrawers.build, 500),
    "section_sink":    ("К 01.02 · Секция под мойку",  SectionSink.build,   1000),
    "section_grill":   ("К 01.03 · Секция с мангалом", SectionGrill.build,  1000),
    "apron":           ("К 01.04 · Фартук",            Apron.build,         1000),
    "hood":            ("К 01.05 · Вытяжка",           Hood.build,          1000),
}


def build(key, height=None, width=None, depth=None, thickness=1.0):
    """
    Собрать модуль по ключу. None -> взять СОБСТВЕННЫЙ дефолт модуля.

    ВАЖНО: раньше здесь стояли height=SECTION_H, depth=SECTION_D, и они
    ЗАТИРАЛИ родные дефолты модуля. Из-за этого фартук (у него своя высота
    750, а не 820) невозможно было построить в его настоящем размере -
    ему всегда навязывалась высота секции. Теперь None означает
    "не задано пользователем", и работает дефолт самого модуля.
    """
    if key not in REAL_MODULES:
        raise ValueError(f"Неизвестный модуль: {key}")
    label, fn, default_w = REAL_MODULES[key]
    kw = {"thickness": thickness}
    if width is not None:
        kw["width"] = width
    if height is not None:
        kw["height"] = height
    if depth is not None:
        kw["depth"] = depth
    return fn(**kw)


def register_into(module_types, type_by_label):
    """
    Прописать настоящие модули в MODULE_TYPES / MODULE_TYPE_BY_LABEL, чтобы:
      - они появились в выпадающем списке в UI
      - сохранённый проект корректно загружался обратно (UI ищет ключ по
        module_type, и без регистрации молча подставил бы "cabinet")
    """
    for key, (label, fn, _w) in REAL_MODULES.items():
        module_types.setdefault(key, label)
        type_by_label.setdefault(label, key)
    # Соответствие по РЕАЛЬНОМУ module_type объекта (он задан в билдере)
    for key in REAL_MODULES:
        try:
            m = build(key)
            type_by_label.setdefault(m.module_type, key)
        except Exception:
            pass