"""
КАТАЛОГ СЕРИЙ TERRASA и VERANDA — модули уличной кухни.

==========================================================================
ОТКУДА ВЗЯТЫ ДАННЫЕ И ЧТО В НИХ ДОСТОВЕРНО
==========================================================================
Состав модулей (сколько панелей, где ящики, где двери, куда идёт каркас)
разобран по фотореалистичным рендерам двух серий. Это ДОСТОВЕРНО: на
рендере видно топологию изделия.

Габариты, профиль трубы и толщина листа с рендера НЕ ЧИТАЮТСЯ. Здесь они
взяты ТИПОВЫЕ (согласовано):

    высота корпуса   850 мм   (стандарт кухонной рабочей высоты)
    глубина          600 мм
    ширины           400 / 600 / 800 / 1200 мм
    труба            40х20х1   (как в текущем tube_frame.POST_PROFILE)
    лист             1.0 мм    (как Config.DEFAULT_THICKNESS)

ВСЕ ЧИСЛА, ПОМЕЧЕННЫЕ КОММЕНТАРИЕМ "# ДОПУЩЕНИЕ", НУЖНО СВЕРИТЬ С ЦЕХОМ
ПЕРЕД ЗАПУСКОМ В ПРОИЗВОДСТВО. Они физически правдоподобны, но это не
замер с реального изделия. Список всех допущений печатает
`python -m core.catalog --assumptions`.

==========================================================================
РАЗНИЦА СЕРИЙ (видна на рендерах)
==========================================================================
TERRASA — МОБИЛЬНАЯ: каркас на колёсах, снизу открытый пояс-рейлинг
          (нижняя полка-решётка между стойками), корпус приподнят.
          Есть купольная вытяжка. Панели гладкие, без видимого крепежа.

VERANDA — СТАЦИОНАРНАЯ: на регулируемых ножках-опорах, корпус опущен
          ниже, по периметру панелей видимый крепёж (болты с шагом),
          то есть панели ПРИКРУЧЕНЫ к каркасу, а не приварены.
          Есть модуль с ветрозащитным экраном.

Это влияет на детали: у TERRASA — кронштейны колёс и рейлинг, у VERANDA —
пятки-опоры и отверстия под крепёж в панелях.
"""
from core.models import Part, BendLine, Cutout, TubePart
from core.module import Module
from core.rules import Rules
from core.sheet_metal import add_flange
from core.tube_frame import build_frame, POST_PROFILE

# --- Типовые габариты (согласовано) ---
STD_HEIGHT = 850
STD_DEPTH = 600

# --- Конструктивные константы ---
# Все помечены как ДОПУЩЕНИЕ: правдоподобны, но не замерены с изделия.
COUNTERTOP_OVERHANG = 20      # ДОПУЩЕНИЕ: вылет столешницы за корпус, мм
DRAWER_FRONT_GAP = 3          # ДОПУЩЕНИЕ: зазор между фасадами ящиков, мм
DRAWER_SLIDE_CLEARANCE = 13   # ДОПУЩЕНИЕ: зазор на направляющую с каждой стороны
                              # (типовая шариковая направляющая 45мм = 12.7мм)
DRAWER_BOX_HEIGHT = 0.75      # ДОПУЩЕНИЕ: высота короба ящика от высоты фасада
TOE_KICK_HEIGHT = 100         # ДОПУЩЕНИЕ: высота цоколя/подстолья, мм
CASTER_PLATE = 100            # ДОПУЩЕНИЕ: площадка под колесо 100x100мм
CASTER_HOLE_D = 10            # ДОПУЩЕНИЕ: отверстие под болт колеса, мм
LEG_PLATE = 80                # ДОПУЩЕНИЕ: пятка регулируемой опоры 80x80мм
FASTENER_HOLE_D = 6           # ДОПУЩЕНИЕ: отверстие под крепёж панели (M6)
FASTENER_PITCH = 200          # ДОПУЩЕНИЕ: шаг крепежа по периметру панели VERANDA
VENT_HOLE_D = 16              # ДОПУЩЕНИЕ: диаметр вент. отверстия


def _tag(part, note):
    """Дописать примечание в description (не затирая пояснение по роли)"""
    if part.description:
        part.description = f"{part.description} {note}"
    else:
        part.description = note
    return part


def _fastener_holes(part, pitch=FASTENER_PITCH, margin=25, d=FASTENER_HOLE_D):
    """
    Отверстия под крепёж по периметру панели (серия VERANDA — панели
    ПРИКРУЧЕНЫ к каркасу, на рендере крепёж виден по краям).

    Отверстия ставятся по 4 краям с шагом pitch, отступ от края margin.
    Координаты — от левого нижнего угла ЗАГОТОВКИ (т.е. вызывать ПОСЛЕ
    add_flange, иначе отверстия уедут).
    """
    w, h = part.width, part.height
    xs = _series(margin, w - margin, pitch)
    ys = _series(margin, h - margin, pitch)
    for x in xs:
        part.cutouts.append(Cutout(shape="circle", x=x, y=margin,
                                   radius=d / 2, label="крепёж M6"))
        part.cutouts.append(Cutout(shape="circle", x=x, y=h - margin,
                                   radius=d / 2, label="крепёж M6"))
    for y in ys[1:-1]:  # углы уже закрыты горизонтальными рядами
        part.cutouts.append(Cutout(shape="circle", x=margin, y=y,
                                   radius=d / 2, label="крепёж M6"))
        part.cutouts.append(Cutout(shape="circle", x=w - margin, y=y,
                                   radius=d / 2, label="крепёж M6"))
    return part


def _series(start, end, pitch):
    """Равномерный ряд координат от start до end с шагом ~pitch (концы включены)"""
    span = end - start
    if span <= 0:
        return [start]
    n = max(1, round(span / pitch))
    return [start + span * i / n for i in range(n + 1)]


# ==========================================================================
# ОБЩИЕ УЗЛЫ (используются обеими сериями)
# ==========================================================================

def build_drawer(width, depth, front_height, thickness, name="Ящик"):
    """
    Ящик как ПОДСБОРКА (Module с собственными деталями) — на рендерах у
    ящиков видны фасады, а короб скрыт внутри корпуса.

    Короб ящика: дно + 2 боковины + задняя стенка + фасад.
    Ширина короба уменьшена на зазор под направляющие с двух сторон.
    """
    box_w = int(width - 2 * DRAWER_SLIDE_CLEARANCE)
    box_h = int(front_height * DRAWER_BOX_HEIGHT)
    box_d = int(depth - 30)   # ДОПУЩЕНИЕ: короб короче корпуса на 30мм (задний упор)

    drawer = Module(name=name, module_type="Ящик",
                    height=front_height, width=width, depth=depth,
                    thickness=thickness)

    # Фасад — единственная видимая деталь ящика
    front = Part("Фасад ящика", int(width), int(front_height), 1, thickness)
    front.cutouts.append(Cutout(
        shape="rect", x=width / 2, y=front_height / 2,
        width=150, height=20,          # ДОПУЩЕНИЕ: врезная ручка-планка 150x20
        label="Врезная ручка"
    ))
    _tag(front, "Фасад ящика — единственная видимая снаружи деталь узла; "
                "крепится к передней стенке короба, ручка врезная.")
    drawer.add_part(front)

    # Короб — всё внутри, не видно
    bottom = add_flange(Part("Дно ящика", box_w, box_d, 1, thickness))
    _tag(bottom, "Днище короба, борта загнуты вверх — образуют стенки короба.")
    bottom.is_hidden_in_assembly = True
    drawer.add_part(bottom)

    side = add_flange(Part("Боковина ящика", box_d, box_h, 2, thickness),
                      edges=("top",))
    _tag(side, f"Боковая стенка короба. К ней крепится шариковая направляющая "
               f"(зазор {DRAWER_SLIDE_CLEARANCE}мм на сторону).")
    side.is_hidden_in_assembly = True
    drawer.add_part(side)

    back = add_flange(Part("Задняя стенка ящика", box_w, box_h, 1, thickness),
                      edges=("top",))
    _tag(back, "Задняя стенка короба, замыкает короб сзади.")
    back.is_hidden_in_assembly = True
    drawer.add_part(back)

    return drawer


def _add_countertop(module, width, depth, thickness):
    """Столешница-крышка с вылетом и бортом (видна на всех модулях обеих серий)"""
    top = add_flange(
        Part("Столешница-крышка",
             int(width + 2 * COUNTERTOP_OVERHANG),
             int(depth + COUNTERTOP_OVERHANG),
             1, thickness),
        edges=("left", "right", "bottom"),   # задний край у стены прямой
    )
    _tag(top, f"Верхняя рабочая поверхность. Свес {COUNTERTOP_OVERHANG}мм по "
              f"бокам и спереди, борта загнуты вниз.")
    module.add_part(top)
    return top


def _add_casters(module, width, depth, thickness):
    """Кронштейны колёс — серия TERRASA (на рендере корпус стоит на колёсах)"""
    plate = Part("Площадка колеса", CASTER_PLATE, CASTER_PLATE, 4, max(thickness, 2.0))
    for dx, dy in ((25, 25), (75, 25), (25, 75), (75, 75)):
        plate.cutouts.append(Cutout(shape="circle", x=dx, y=dy,
                                    radius=CASTER_HOLE_D / 2, label="болт колеса"))
    _tag(plate, "Опорная площадка поворотного колеса — приваривается к низу "
                "стойки каркаса, колесо крепится 4 болтами.")
    plate.is_hidden_in_assembly = True
    module.add_part(plate)


def _add_legs(module, thickness):
    """Пятки регулируемых опор — серия VERANDA (на рендере ножки-опоры)"""
    pad = Part("Пятка опоры", LEG_PLATE, LEG_PLATE, 4, max(thickness, 2.0))
    pad.cutouts.append(Cutout(shape="circle", x=LEG_PLATE / 2, y=LEG_PLATE / 2,
                              radius=6, label="резьба под винт опоры M12"))
    _tag(pad, "Пятка регулируемой опоры — приваривается к низу стойки, "
              "в центре резьба под винт регулировки по высоте.")
    pad.is_hidden_in_assembly = True
    module.add_part(pad)


def _add_rail_shelf(module, width, depth, thickness):
    """Нижняя полка-рейлинг между стойками — серия TERRASA (видна на рендере)"""
    shelf = add_flange(Part("Полка нижняя (рейлинг)",
                            int(width - 2 * POST_PROFILE[0]),
                            int(depth - 2 * POST_PROFILE[1]),
                            1, thickness))
    _tag(shelf, "Нижняя открытая полка между стойками каркаса — придаёт "
                "жёсткость раме и служит местом хранения.")
    # Правило по роли ("полка" = внутри корпуса за дверьми) здесь НЕ работает:
    # на рендере это ОТКРЫТАЯ нижняя полка-рейлинг, она на виду. Переопределяем.
    shelf.is_hidden_in_assembly = False
    module.add_part(shelf)


def _add_doors(module, width, height, thickness, count=2):
    """Распашные двери (видны на рендерах обеих серий)"""
    if count == 2:
        door_w = int((width - Rules.DOOR_GAP) // 2)
    else:
        door_w = int(width - Rules.DOOR_GAP)
    door_h = int(height - Rules.EDGE_CLEARANCE)
    door = Part("Дверь", door_w, door_h, count, thickness)
    door.cutouts.append(Cutout(
        shape="rect", x=door_w - 60, y=door_h / 2,
        width=20, height=120,           # ДОПУЩЕНИЕ: ручка-скоба 120мм
        label="Отверстия под ручку"
    ))
    _tag(door, f"Створка ({count} шт.) — навешивается на петли к боковине "
               f"корпуса, зазор между створками {Rules.DOOR_GAP}мм.")
    module.add_part(door)


def _corpus(module, width, depth, height, thickness, series,
            back_panel=True, bottom=True):
    """
    Общий корпус: 2 боковины + дно + (задняя стенка).

    series='veranda' -> в панелях сверлятся отверстия под крепёж (панели
                        прикручены к каркасу, крепёж виден на рендере)
    series='terrasa' -> панели без крепежа (гладкие, приварены/на клипсах)
    """
    side = add_flange(Part("Боковина", int(depth), int(height), 2, thickness))
    if series == "veranda":
        _fastener_holes(side)
        _tag(side, f"Прикручивается к стойкам каркаса по периметру "
                   f"(крепёж M{FASTENER_HOLE_D}, шаг ~{FASTENER_PITCH}мм).")
    module.add_part(side)

    if bottom:
        btm = add_flange(Part("Дно", int(width), int(depth), 1, thickness))
        if series == "veranda":
            _fastener_holes(btm)
        module.add_part(btm)

    if back_panel:
        back = add_flange(Part("Задняя стенка", int(width), int(height), 1, thickness))
        if series == "veranda":
            _fastener_holes(back)
        back.is_hidden_in_assembly = True
        module.add_part(back)


def _frame(module, height, width, depth, series):
    """Каркас + опоры/колёса по серии"""
    for t in build_frame(height, width, depth):
        module.add_tube(t)
    if series == "terrasa":
        # Дополнительный нижний пояс под рейлинг + кронштейны колёс
        _add_casters(module, width, depth, module.thickness)
    else:
        _add_legs(module, module.thickness)


def _make(name, mtype, height, width, depth, thickness):
    return Module(name=name, module_type=mtype, height=int(height),
                  width=int(width), depth=int(depth), thickness=thickness)


# ==========================================================================
# СЕРИЯ TERRASA (мобильная, на колёсах)
# ==========================================================================

class Terrasa:
    SERIES = "terrasa"

    @staticmethod
    def tumba_2_drawers(height=STD_HEIGHT, width=400, depth=STD_DEPTH,
                        thickness=Rules.DEFAULT_THICKNESS):
        """Узкая тумба с 2 выдвижными ящиками на колёсах (рендер: 1-й слева)"""
        m = _make("TERRASA Тумба 2 ящика", "TERRASA Тумба 2 ящика",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Terrasa.SERIES)
        _add_countertop(m, width, depth, thickness)
        _add_rail_shelf(m, width, depth, thickness)
        _frame(m, height, width, depth, Terrasa.SERIES)

        # 2 ящика делят высоту корпуса пополам
        front_h = (height - 3 * DRAWER_FRONT_GAP) / 2
        for i in range(2):
            m.add_subassembly(build_drawer(width - 2 * DRAWER_FRONT_GAP, depth,
                                           front_h, thickness,
                                           name=f"Ящик {i+1}"))
        return m

    @staticmethod
    def tumba_1_drawer(height=STD_HEIGHT, width=400, depth=STD_DEPTH,
                       thickness=Rules.DEFAULT_THICKNESS):
        """Тумба с 1 ящиком + отделение под ним (рендер: 3-й в верхнем ряду)"""
        m = _make("TERRASA Тумба 1 ящик", "TERRASA Тумба 1 ящик",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Terrasa.SERIES)
        _add_countertop(m, width, depth, thickness)
        _add_rail_shelf(m, width, depth, thickness)
        _frame(m, height, width, depth, Terrasa.SERIES)

        front_h = height * 0.35   # ДОПУЩЕНИЕ: ящик занимает верхнюю треть
        m.add_subassembly(build_drawer(width - 2 * DRAWER_FRONT_GAP, depth,
                                       front_h, thickness, name="Ящик"))
        # Под ящиком — глухая панель-фасад
        panel = Part("Панель нижняя", int(width - DRAWER_FRONT_GAP),
                     int(height - front_h - 2 * DRAWER_FRONT_GAP), 1, thickness)
        _tag(panel, "Глухая панель под ящиком — закрывает нижнее отделение корпуса.")
        m.add_part(panel)
        return m

    @staticmethod
    def hood(height=700, width=1200, depth=STD_DEPTH,
             thickness=Rules.DEFAULT_THICKNESS):
        """
        Купольная вытяжка (рендер: центр верхнего ряда).
        Наклонные скосы (4 шт.) сходятся к прямой шахте.
        """
        m = _make("TERRASA Вытяжка купольная", "TERRASA Вытяжка",
                  height, width, depth, thickness)

        duct_w = 300                    # ДОПУЩЕНИЕ: шахта 300x300мм
        duct_h = int(height * 0.55)     # ДОПУЩЕНИЕ: шахта — верхние 55% высоты
        skirt_h = int(height - duct_h)

        # 4 трапециевидных скоса купола. Геометрия трапеции в модели Part
        # НЕ ВЫРАЖАЕТСЯ (Part — прямоугольник + вырезы), поэтому в раскрой
        # уходит ОПИСАННЫЙ ПРЯМОУГОЛЬНИК заготовки. Это ЧЕСТНО завышает
        # расход металла и требует ручной доработки контура в DXF.
        front = Part("Скос купола передний/задний", int(width), skirt_h, 2, thickness)
        _tag(front, f"Наклонная грань купола (трапеция {width}->{duct_w}мм). "
                    f"ВНИМАНИЕ: в раскрое дан ОПИСАННЫЙ ПРЯМОУГОЛЬНИК — "
                    f"истинный контур трапеции модель Part не описывает, "
                    f"скорректировать в DXF вручную.")
        m.add_part(front)

        side = Part("Скос купола боковой", int(depth), skirt_h, 2, thickness)
        _tag(side, f"Боковая наклонная грань купола (трапеция {depth}->{duct_w}мм). "
                   f"В раскрое — описанный прямоугольник, см. примечание выше.")
        m.add_part(side)

        duct = add_flange(Part("Стенка шахты", duct_w, duct_h, 4, thickness),
                          edges=("left", "right"))
        _tag(duct, "Стенка вертикальной шахты вытяжки, 4 шт. образуют короб; "
                   "борта загнуты для стыковки между собой.")
        m.add_part(duct)

        flange = Part("Фланец дымохода", duct_w, duct_w, 1, thickness)
        flange.cutouts.append(Cutout(shape="circle", x=duct_w / 2, y=duct_w / 2,
                                     radius=75, label="Патрубок ⌀150"))
        _tag(flange, "Верхний фланец с патрубком ⌀150 под гофру дымохода.")
        flange.is_hidden_in_assembly = True
        m.add_part(flange)

        filt = Part("Рамка жироулавливающего фильтра", int(width - 100),
                    int(depth - 100), 1, thickness)
        _tag(filt, "Рамка под жироулавливающий фильтр — нижняя плоскость купола.")
        filt.is_hidden_in_assembly = True
        m.add_part(filt)

        for t in build_frame(height, width, depth):
            m.add_tube(t)
        return m

    @staticmethod
    def grill_section(height=STD_HEIGHT, width=1200, depth=STD_DEPTH,
                      thickness=Rules.DEFAULT_THICKNESS):
        """Секция с грилем + 2 двери (рендер: 1-й в среднем ряду)"""
        m = _make("TERRASA Секция с грилем", "TERRASA Секция с грилем",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Terrasa.SERIES)

        # Столешница с вырезом под гриль — загиб ДО выреза (порядок важен)
        top = _add_countertop(m, width, depth, thickness)
        top.name = "Столешница (вырез под гриль)"
        top.cutouts.append(Cutout(
            shape="rect", x=top.width / 2, y=top.height / 2,
            width=560, height=480,      # ДОПУЩЕНИЕ: посадочное место гриля
            label="Вырез под встраиваемый гриль"
        ))

        _add_doors(m, width, height, thickness, count=2)
        _add_rail_shelf(m, width, depth, thickness)

        # Вентиляция в боковине — обязательна для газового гриля
        vent = add_flange(Part("Боковина с вентиляцией", int(depth), int(height),
                               1, thickness))
        for y in _series(150, height - 150, 120):
            for x in (depth * 0.35, depth * 0.65):
                vent.cutouts.append(Cutout(shape="circle", x=x, y=y,
                                           radius=VENT_HOLE_D / 2, label="Вент."))
        _tag(vent, "Боковина с вентиляционными отверстиями — обязательна для "
                   "отвода тепла от гриля, без неё горелка перегревается.")
        m.add_part(vent)

        _frame(m, height, width, depth, Terrasa.SERIES)
        return m

    @staticmethod
    def bridge_stand(height=STD_HEIGHT, width=400, depth=STD_DEPTH,
                     thickness=Rules.DEFAULT_THICKNESS):
        """Стойка-переходник: только каркас + столешница (рендер: центр среднего ряда)"""
        m = _make("TERRASA Стойка-переходник", "TERRASA Стойка-переходник",
                  height, width, depth, thickness)
        _add_countertop(m, width, depth, thickness)
        _add_rail_shelf(m, width, depth, thickness)
        _frame(m, height, width, depth, Terrasa.SERIES)
        return m

    @staticmethod
    def cabinet_2_doors(height=STD_HEIGHT, width=1200, depth=STD_DEPTH,
                        thickness=Rules.DEFAULT_THICKNESS):
        """Секция с 2 распашными дверями (рендер: 3-й в среднем ряду)"""
        m = _make("TERRASA Секция 2 двери", "TERRASA Секция 2 двери",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Terrasa.SERIES)
        _add_countertop(m, width, depth, thickness)
        _add_doors(m, width, height, thickness, count=2)
        _add_rail_shelf(m, width, depth, thickness)

        shelf = add_flange(Part("Полка внутренняя", int(width - 20),
                                int(depth - 40), 1, thickness))
        m.add_part(shelf)
        _frame(m, height, width, depth, Terrasa.SERIES)
        return m

    @staticmethod
    def shelf_unit(height=STD_HEIGHT, width=600, depth=STD_DEPTH,
                   thickness=Rules.DEFAULT_THICKNESS):
        """Этажерка открытая, 2 полки (рендер: 1-й в нижнем ряду)"""
        m = _make("TERRASA Этажерка открытая", "TERRASA Этажерка",
                  height, width, depth, thickness)
        _add_countertop(m, width, depth, thickness)
        shelf = add_flange(Part("Полка", int(width - 2 * POST_PROFILE[0]),
                                int(depth - 2 * POST_PROFILE[1]), 2, thickness))
        _tag(shelf, "Открытая полка этажерки (2 шт.), лежит на поясах каркаса.")
        shelf.is_hidden_in_assembly = False   # этажерка открытая, полки на виду
        m.add_part(shelf)
        _frame(m, height, width, depth, Terrasa.SERIES)
        return m

    @staticmethod
    def work_table(height=STD_HEIGHT, width=1200, depth=STD_DEPTH,
                   thickness=Rules.DEFAULT_THICKNESS):
        """Стол-каркас на колёсах, без корпуса (рендер: центр нижнего ряда)"""
        m = _make("TERRASA Стол-каркас", "TERRASA Стол",
                  height, width, depth, thickness)
        _add_countertop(m, width, depth, thickness)
        _frame(m, height, width, depth, Terrasa.SERIES)
        return m

    @staticmethod
    def stool(height=750, width=400, depth=400,
              thickness=Rules.DEFAULT_THICKNESS):
        """Табурет A-образный (рендер: справа в нижнем ряду)"""
        m = _make("TERRASA Табурет", "TERRASA Табурет",
                  height, width, depth, thickness)
        seat = add_flange(Part("Сиденье", int(width), int(depth), 1, thickness))
        _tag(seat, "Сиденье табурета — лист с загнутыми вниз бортами, "
                   "приваривается к верху A-образной рамы.")
        m.add_part(seat)
        # A-образная рама: 4 наклонные стойки + 2 поперечины.
        # Наклон рамы (стойки не вертикальны) моделью TubePart не выражается —
        # длина дана по факту отрезка, угол реза цех ставит по месту.
        pw, ph, wall = POST_PROFILE
        m.add_tube(TubePart(pw, ph, wall, int(height), quantity=4,
                            note="стойка A-рамы (рез под углом — по месту)"))
        m.add_tube(TubePart(pw, ph, wall, int(width - 2 * pw), quantity=2,
                            note="поперечина"))
        return m


# ==========================================================================
# СЕРИЯ VERANDA (стационарная, на опорах, панели на крепеже)
# ==========================================================================

class Veranda:
    SERIES = "veranda"

    @staticmethod
    def low_cabinet(height=STD_HEIGHT, width=1200, depth=STD_DEPTH,
                    thickness=Rules.DEFAULT_THICKNESS):
        """Низкая секция с крышкой, глухой фасад (рендер: 1-й в верхнем ряду)"""
        m = _make("VERANDA Секция низкая", "VERANDA Секция низкая",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Veranda.SERIES)
        _add_countertop(m, width, depth, thickness)

        face = Part("Фасад глухой", int(width - Rules.DOOR_GAP),
                    int(height - Rules.EDGE_CLEARANCE), 1, thickness)
        _fastener_holes(face)
        _tag(face, "Глухой передний фасад — прикручен к каркасу по периметру.")
        m.add_part(face)
        _frame(m, height, width, depth, Veranda.SERIES)
        return m

    @staticmethod
    def open_rack(height=STD_HEIGHT, width=600, depth=STD_DEPTH,
                  thickness=Rules.DEFAULT_THICKNESS):
        """Стеллаж открытый, 2 полки (рендер: центр верхнего ряда)"""
        m = _make("VERANDA Стеллаж открытый", "VERANDA Стеллаж",
                  height, width, depth, thickness)
        _add_countertop(m, width, depth, thickness)
        shelf = add_flange(Part("Полка", int(width - 2 * POST_PROFILE[0]),
                                int(depth - 2 * POST_PROFILE[1]), 2, thickness))
        _fastener_holes(shelf)
        shelf.is_hidden_in_assembly = False   # стеллаж открытый, полки на виду
        m.add_part(shelf)
        _frame(m, height, width, depth, Veranda.SERIES)
        return m

    @staticmethod
    def chest_3_drawers(height=STD_HEIGHT, width=400, depth=STD_DEPTH,
                        thickness=Rules.DEFAULT_THICKNESS):
        """Комод с 3 ящиками (рендер: 3-й в верхнем ряду)"""
        m = _make("VERANDA Комод 3 ящика", "VERANDA Комод 3 ящика",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Veranda.SERIES)
        _add_countertop(m, width, depth, thickness)
        _frame(m, height, width, depth, Veranda.SERIES)

        front_h = (height - 4 * DRAWER_FRONT_GAP) / 3
        for i in range(3):
            m.add_subassembly(build_drawer(width - 2 * DRAWER_FRONT_GAP, depth,
                                           front_h, thickness,
                                           name=f"Ящик {i+1}"))
        return m

    @staticmethod
    def sink_cabinet(height=STD_HEIGHT, width=800, depth=STD_DEPTH,
                     thickness=Rules.DEFAULT_THICKNESS):
        """Секция под мойку: врезная мойка + смеситель, 2 двери (рендер: 1-й в среднем ряду)"""
        m = _make("VERANDA Секция под мойку", "VERANDA Секция под мойку",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Veranda.SERIES)

        top = _add_countertop(m, width, depth, thickness)
        top.name = "Столешница (вырез под мойку)"
        top.cutouts.append(Cutout(
            shape="rect", x=top.width / 2, y=top.height / 2 - 30,
            width=500, height=400,      # ДОПУЩЕНИЕ: чаша мойки 500x400
            label="Вырез под врезную мойку"
        ))
        top.cutouts.append(Cutout(
            shape="circle", x=top.width / 2, y=top.height - 80,
            radius=17,                  # ДОПУЩЕНИЕ: отверстие смесителя ⌀34
            label="Отверстие под смеситель ⌀34"
        ))

        _add_doors(m, width, height, thickness, count=2)
        _frame(m, height, width, depth, Veranda.SERIES)
        return m

    @staticmethod
    def grill_stand(height=STD_HEIGHT, width=800, depth=STD_DEPTH,
                    thickness=Rules.DEFAULT_THICKNESS):
        """Секция под гриль: открытый каркас + полка (рендер: центр среднего ряда)"""
        m = _make("VERANDA Секция под гриль", "VERANDA Секция под гриль",
                  height, width, depth, thickness)

        top = _add_countertop(m, width, depth, thickness)
        top.name = "Столешница (вырез под гриль)"
        top.cutouts.append(Cutout(
            shape="rect", x=top.width / 2, y=top.height / 2,
            width=560, height=480,
            label="Вырез под встраиваемый гриль"
        ))
        shelf = add_flange(Part("Полка нижняя", int(width - 2 * POST_PROFILE[0]),
                                int(depth - 2 * POST_PROFILE[1]), 1, thickness))
        _fastener_holes(shelf)
        _tag(shelf, "Нижняя полка открытого каркаса — под газовый баллон/утварь.")
        shelf.is_hidden_in_assembly = False   # открытый каркас, полка на виду
        m.add_part(shelf)
        _frame(m, height, width, depth, Veranda.SERIES)
        return m

    @staticmethod
    def cabinet_2_doors(height=STD_HEIGHT, width=800, depth=STD_DEPTH,
                        thickness=Rules.DEFAULT_THICKNESS):
        """Секция с 2 дверями (рендер: 3-й в среднем ряду)"""
        m = _make("VERANDA Секция 2 двери", "VERANDA Секция 2 двери",
                  height, width, depth, thickness)
        _corpus(m, width, depth, height, thickness, Veranda.SERIES)
        _add_countertop(m, width, depth, thickness)
        _add_doors(m, width, height, thickness, count=2)

        shelf = add_flange(Part("Полка внутренняя", int(width - 20),
                                int(depth - 40), 1, thickness))
        m.add_part(shelf)
        _frame(m, height, width, depth, Veranda.SERIES)
        return m

    @staticmethod
    def side_frame(height=STD_HEIGHT, width=400, depth=STD_DEPTH,
                   thickness=Rules.DEFAULT_THICKNESS):
        """Боковая рама-лестница, 3 секции (рендер: 1-й в нижнем ряду)"""
        m = _make("VERANDA Рама боковая", "VERANDA Рама боковая",
                  height, width, depth, thickness)
        pw, ph, wall = POST_PROFILE
        m.add_tube(TubePart(pw, ph, wall, int(height), quantity=2, note="стойка рамы"))
        m.add_tube(TubePart(pw, ph, wall, int(width - 2 * pw), quantity=4,
                            note="перекладина рамы (3 секции)"))
        _add_legs(m, thickness)
        return m

    @staticmethod
    def door_facade(height=STD_HEIGHT, width=800, depth=60,
                    thickness=Rules.DEFAULT_THICKNESS):
        """Фасад-дверь двустворчатый как отдельная позиция (рендер: центр нижнего ряда)"""
        m = _make("VERANDA Фасад двустворчатый", "VERANDA Фасад",
                  height, width, depth, thickness)
        door_w = int((width - Rules.DOOR_GAP) // 2)
        door = add_flange(Part("Створка фасада", door_w, int(height), 2, thickness))
        _fastener_holes(door)
        _tag(door, "Створка двустворчатого фасада, борта загнуты назад для "
                   "жёсткости; крепёж по периметру виден снаружи.")
        m.add_part(door)

        hinge = Part("Пластина петли", 60, 40, 4, max(thickness, 2.0))
        for dx in (15, 45):
            hinge.cutouts.append(Cutout(shape="circle", x=dx, y=20,
                                        radius=3, label="крепёж петли"))
        _tag(hinge, "Усилительная пластина под петлю — приваривается изнутри "
                    "створки в местах навески.")
        hinge.is_hidden_in_assembly = True
        m.add_part(hinge)
        return m

    @staticmethod
    def windbreak(height=STD_HEIGHT, width=600, depth=STD_DEPTH,
                  thickness=Rules.DEFAULT_THICKNESS):
        """
        Секция с ветрозащитой: перфорированный экран + верхнее стекло
        (рендер: справа в нижнем ряду).
        """
        m = _make("VERANDA Секция с ветрозащитой", "VERANDA Ветрозащита",
                  height, width, depth, thickness)
        _add_countertop(m, width, depth, thickness)

        screen_h = 300              # ДОПУЩЕНИЕ: высота перфоэкрана
        screen = add_flange(Part("Экран перфорированный", int(width), screen_h,
                                 1, thickness))
        # Перфорация: сетка отверстий. На рендере — мелкая частая перфорация;
        # шаг взят 25мм (ДОПУЩЕНИЕ). Отверстий много -> раскрой считается,
        # но на чертёж выносками они не выводятся (только в таблицу).
        for x in _series(20, screen.width - 20, 25):
            for y in _series(20, screen.height - 20, 25):
                screen.cutouts.append(Cutout(shape="circle", x=x, y=y,
                                             radius=3, label="перфорация ⌀6"))
        _tag(screen, "Перфорированный ветрозащитный экран — гасит ветер, не "
                     "перекрывая тягу. Перфорация ⌀6 с шагом 25мм.")
        m.add_part(screen)

        glass_frame = add_flange(Part("Рамка стекла", int(width), 200, 1, thickness),
                                 edges=("left", "right", "bottom"))
        _tag(glass_frame, "Рамка верхнего защитного стекла (само стекло — "
                          "покупное, в раскрой не входит).")
        m.add_part(glass_frame)

        _frame(m, height, width, depth, Veranda.SERIES)
        return m


# ==========================================================================
# РЕЕСТР — чтобы UI не пришлось переписывать под каждый новый модуль
# ==========================================================================
#
# Раньше UI выбирал билдер длинной цепочкой if/elif по module_key. С 18
# модулями это стало бы нечитаемо. Реестр: ключ -> (подпись, функция,
# нужны ли полки/ширина по умолчанию). UI просто перебирает реестр.

CATALOG = {
    # --- TERRASA ---
    "terrasa_tumba_2drw":  ("TERRASA · Тумба 2 ящика",      Terrasa.tumba_2_drawers, 400),
    "terrasa_tumba_1drw":  ("TERRASA · Тумба 1 ящик",       Terrasa.tumba_1_drawer,  400),
    "terrasa_hood":        ("TERRASA · Вытяжка купольная",  Terrasa.hood,            1200),
    "terrasa_grill":       ("TERRASA · Секция с грилем",    Terrasa.grill_section,   1200),
    "terrasa_bridge":      ("TERRASA · Стойка-переходник",  Terrasa.bridge_stand,    400),
    "terrasa_2doors":      ("TERRASA · Секция 2 двери",     Terrasa.cabinet_2_doors, 1200),
    "terrasa_shelf":       ("TERRASA · Этажерка открытая",  Terrasa.shelf_unit,      600),
    "terrasa_table":       ("TERRASA · Стол-каркас",        Terrasa.work_table,      1200),
    "terrasa_stool":       ("TERRASA · Табурет",            Terrasa.stool,           400),
    # --- VERANDA ---
    "veranda_low":         ("VERANDA · Секция низкая",      Veranda.low_cabinet,     1200),
    "veranda_rack":        ("VERANDA · Стеллаж открытый",   Veranda.open_rack,       600),
    "veranda_chest_3drw":  ("VERANDA · Комод 3 ящика",      Veranda.chest_3_drawers, 400),
    "veranda_sink":        ("VERANDA · Секция под мойку",   Veranda.sink_cabinet,    800),
    "veranda_grill":       ("VERANDA · Секция под гриль",   Veranda.grill_stand,     800),
    "veranda_2doors":      ("VERANDA · Секция 2 двери",     Veranda.cabinet_2_doors, 800),
    "veranda_side_frame":  ("VERANDA · Рама боковая",       Veranda.side_frame,      400),
    "veranda_facade":      ("VERANDA · Фасад двустворчатый", Veranda.door_facade,    800),
    "veranda_windbreak":   ("VERANDA · Секция с ветрозащитой", Veranda.windbreak,    600),
}


def register_into(module_types, type_by_label):
    """
    Прописать модули каталога в словари builders.MODULE_TYPES /
    MODULE_TYPE_BY_LABEL, чтобы загрузка сохранённого проекта из JSON
    находила нужный тип и выставляла его в выпадающем списке.

    Без этого модуль каталога сохранялся бы нормально, но при загрузке
    UI не смог бы сопоставить module_type -> ключ и молча подставил бы
    "cabinet" (см. MODULE_TYPE_BY_LABEL.get(..., "cabinet") в main_window).
    """
    for key, (label, fn, _w) in CATALOG.items():
        module_types.setdefault(key, label)
        # module_type объекта Module - это то, что реально записано в самом
        # модуле (см. _make), по нему и ищем ключ при загрузке.
        sample_type = fn.__doc__ or ""
        type_by_label.setdefault(label, key)
    # Точное соответствие module_type -> ключ (module_type задан в _make)
    for key in CATALOG:
        m = build(key)
        type_by_label.setdefault(m.module_type, key)


def build(key, height=STD_HEIGHT, width=None, depth=STD_DEPTH,
          thickness=Rules.DEFAULT_THICKNESS):
    """Собрать модуль каталога по ключу. width=None -> ширина по умолчанию."""
    if key not in CATALOG:
        raise ValueError(f"Неизвестный модуль каталога: {key}")
    label, fn, default_w = CATALOG[key]
    return fn(height=height, width=width or default_w,
              depth=depth, thickness=thickness)


ASSUMPTIONS = [
    ("Габариты", f"В{STD_HEIGHT} / Г{STD_DEPTH} / ширины 400-1200 — ТИПОВЫЕ, не замер"),
    ("Труба", f"{POST_PROFILE[0]}х{POST_PROFILE[1]}х{POST_PROFILE[2]} — из текущего кода"),
    ("Лист", f"{Rules.DEFAULT_THICKNESS} мм — из текущего кода"),
    ("Свес столешницы", f"{COUNTERTOP_OVERHANG} мм"),
    ("Направляющая ящика", f"зазор {DRAWER_SLIDE_CLEARANCE} мм на сторону (шариковая 45мм)"),
    ("Высота короба ящика", f"{DRAWER_BOX_HEIGHT*100:.0f}% от высоты фасада"),
    ("Колесо TERRASA", f"площадка {CASTER_PLATE}x{CASTER_PLATE}, болт ⌀{CASTER_HOLE_D}"),
    ("Опора VERANDA", f"пятка {LEG_PLATE}x{LEG_PLATE}, винт M12"),
    ("Крепёж VERANDA", f"M{FASTENER_HOLE_D}, шаг {FASTENER_PITCH} мм по периметру панели"),
    ("Вырез гриля", "560x480 мм"),
    ("Мойка", "чаша 500x400, смеситель ⌀34"),
    ("Вытяжка", "шахта 300x300, патрубок ⌀150"),
    ("Перфорация ветрозащиты", "⌀6, шаг 25 мм"),
    ("!! ГЕОМЕТРИЯ", "Скосы купола вытяжки — ТРАПЕЦИИ. Модель Part описывает "
                     "только прямоугольник, поэтому в раскрой уходит ОПИСАННЫЙ "
                     "ПРЯМОУГОЛЬНИК (перерасход). Нужен контур-полигон в модели."),
    ("!! ГЕОМЕТРИЯ", "A-рама табурета — наклонные стойки. TubePart хранит только "
                     "длину, угол реза не хранится — цех режет по месту."),
]


if __name__ == "__main__":
    import sys
    if "--assumptions" in sys.argv:
        print("ДОПУЩЕНИЯ КАТАЛОГА (сверить с цехом!):\n")
        for k, v in ASSUMPTIONS:
            print(f"  {k:26} {v}")
    else:
        for key in CATALOG:
            m = build(key)
            print(f"{key:22} {m.name:34} деталей={m.total_parts:3}  "
                  f"подсборок={len(m.subassemblies)}  вес={m.weight:.1f}кг")