"""
ЭЛЕКТРОМОНТАЖНЫЙ ШКАФ (навесной) — параметрический билдер.

Калибровка по эталону 400х445.dxf (реальный товар, 400 x 445 x 150, 1.2мм),
разобранному по связным компонентам. НАСТОЯЩИЙ состав — 10 деталей:

    Корпус                       714.5 x 441   8xD5 + 2xD6
    Крышка с кабельными вводами  401.0 x 160   3xD32
    Крышка глухая                401.0 x 160
    Монтажная панель             380.0 x 415   4xD8+4xD6+D4, углы-лапки
    Полоска A                    205.0 x 33    2xD3, надрез слева
    Полоска B                    305.0 x 33    2xD3
    Кронштейн                    20.0 x 50     D6 + П-паз + овал, R5
    Дверь x3                     430.5 x 471   релиз-углы 15.5, замок-восьмигранник

Контуры (скругления, надрезы, лапки-«носики») сняты С ЭТАЛОНА и заданы явно
через Part.outline (bulge-дуги). Замок — скруглённый восьмигранник, не квадрат.

Одно изделие = ОДИН чертёж-раскрой, где лежат ВСЕ детали + ВСЕ 3 двери
(оператор выбирает, какую дверь резать). Экспорт идёт через
DXFExporter.export_cut_layout (см. флаг Module.cut_layout).

Модель гиба — аддитивная (вычет ≈ 0), своя, не кухонная. Когда придут
параметры станка — правятся константы ниже.
"""
import math
from core.models import Part, BendLine, Cutout
from core.module import Module

_B90 = math.tan(math.radians(90) / 4)    # bulge дуги угла 90°
DOOR_FLANGE = 15.5                        # полка двери по всем сторонам
BIG_WINDOW = (270, 330)
SMALL_WINDOW = (104, 104)

# --- Параметры станка (получены от цеха 2026-08-13) ---
BEND_RADIUS = 1.2     # внутренний радиус гиба, мм
MIN_FLANGE = 10.0     # минимальная полка (борт), мм — короче станок не согнёт


# ==========================================================================
# ГЕОМЕТРИЯ КОНТУРОВ (сняты с эталона)
# ==========================================================================

def _rounded_rect(w, h, r):
    """Прямоугольник со скруглёнными углами R (CCW, bulge)."""
    B = _B90
    return [(r, 0, 0), (w - r, 0, B), (w, r, 0), (w, h - r, B),
            (w - r, h, 0), (r, h, B), (0, h - r, 0), (0, r, B)]


def _cover_outline(w, h):
    """Крышка: скруглённая панель (R3 низ, R2 верх) + отогнутая планка
    сверху шириной w-2*17.3 с фасками 45°. Точно как эталон 401x160."""
    B, r3, r2 = _B90, 3.0, 2.0
    fv, fi, band = 17.3, 12.6, 36.2      # верт. планки, инсет верх. кромки, высота планки
    main = h - band
    return [
        (r3, 0, 0), (w - r3, 0, B),
        (w, r3, 0), (w, main - r2, B),
        (w - r2, main, 0),
        (w - fv, main, 0), (w - fv, h - 9.4, 0), (w - fi, h, 0),
        (fi, h, 0), (fv, h - 9.4, 0), (fv, main, 0),
        (r2, main, B), (0, main - r2, 0), (0, r3, B),
    ]


def _panel_outline(w, h):
    """Монтажная панель: по углам лапки-«носики» 10мм с фаской 45° (эталон)."""
    return [
        (0, 15), (10, 15), (15, 10), (15, 0),
        (w - 15, 0), (w - 15, 10), (w - 10, 15), (w, 15),
        (w, h - 15), (w - 10, h - 15), (w - 15, h - 10), (w - 15, h),
        (15, h), (15, h - 10), (10, h - 15), (0, h - 15),
    ]


def _strip_a_outline(w, h, nx=15, ny=9):
    """Полоска A: надрез nx x ny в нижнем левом углу (эталон 205x33)."""
    return [(0, ny), (nx, ny), (nx, 0), (w, 0), (w, h), (0, h)]


def _body_outline(W, D, H):
    """
    Контур корпуса (задняя стенка + 2 боковины + возвратные полки), снятый
    с эталона 714.5x441. Симметричен. Возвратные полки по краям с угловым
    релизом (короче по высоте + фаска), чтобы согнуться без нахлёста.

    Параметрический: задняя стенка тянется за W, боковины за D, высота за H,
    возвратные полки фиксированы (крепёжные, ~20мм).
    """
    RF = 20.4              # возвратная полка (flat), фикс.
    SD = D - 12.7          # боковина (flat): эталон 137.3 при D=150
    BW = W - 1             # задняя стенка: эталон 399 при W=400
    Hf = H - 5             # высота развёртки: эталон 440 при H=445
    TW = 2 * RF + 2 * SD + BW
    ye, yr, ch, sub = 13.6, 18.3, 9.4, 18.4   # фикс. детали релиза/фаски
    xLb = RF + SD          # сгиб задняя↔левая боковина
    xRb = RF + SD + BW     # сгиб задняя↔правая боковина
    # Верхняя кромка идёт справа→налево; в точках сгиба задняя/боковина —
    # маленький полукруглый НАДРЕЗ (уголок гиба, R1) ВНИЗ в металл, как эталон.
    # bulge=-1.0 -> полуокружность, дуга уходит вниз (в тело детали).
    return [
        (0, ye), (ch, yr), (sub, yr), (RF, yr), (RF, 0),
        (TW - RF, 0),
        (TW - RF, yr), (TW - sub, yr), (TW - ch, yr), (TW, ye),
        (TW, Hf - ye), (TW - ch, Hf - yr), (TW - sub, Hf - yr), (TW - RF, Hf - yr), (TW - RF, Hf),
        (xRb + 1, Hf, -1.0), (xRb - 1, Hf),
        (xLb + 1, Hf, -1.0), (xLb - 1, Hf),
        (RF, Hf),
        (RF, Hf - yr), (sub, Hf - yr), (ch, Hf - yr), (0, Hf - ye),
    ]


def _body_folds(W, D):
    """X-позиции 4 линий гиба корпуса (от левого края): возврат/боковина,
    боковина/задняя, задняя/боковина, боковина/возврат."""
    RF, SD, BW = 20.4, D - 12.7, W - 1
    return [RF, RF + SD, RF + SD + BW, RF + 2 * SD + BW]


def _lock_octagon(cx, cy, s=22):
    """Замок — скруглённый восьмигранник s x s с центром (cx,cy) (эталон).
    Прямые в серединах сторон + скруглённые срезанные углы."""
    B = math.tan(math.radians(40) / 4)   # дуга угла ~40°
    ox, oy = cx - s / 2, cy - s / 2
    p = [(6.4, 1, 0), (15.6, 1, B), (21, 6.4, 0), (21, 15.6, B),
         (15.6, 21, 0), (6.4, 21, B), (1, 15.6, 0), (1, 6.4, B)]
    return [(ox + x, oy + y, b) for x, y, b in p]


def _bend(edge, flange, note=""):
    return BendLine(edge=edge, offset=flange, angle=90, direction="down",
                    nominal=flange, note=note or f"гиб {flange}мм")


def _edge_holes(part, specs):
    """
    Отверстия, привязанные к КРАЯМ детали фиксированным отступом (мм), а не
    в долях габарита. Так узор не «вылезает» на маленькой детали: реальный
    крепёж всегда на постоянном расстоянии от кромки.

    specs: [(ax, dx, ay, dy, d), ...]
      ax = 'L'|'R'  отступ dx от левого/правого края
      ay = 'B'|'T'  отступ dy от нижнего/верхнего края
      d  = диаметр отверстия
    """
    w, h = part.width, part.height
    for ax, dx, ay, dy, d in specs:
        x = dx if ax == 'L' else w - dx
        y = dy if ay == 'B' else h - dy
        part.cutouts.append(Cutout("circle", x, y, radius=d / 2))


# ==========================================================================
# ДЕТАЛИ
# ==========================================================================

def build_body(width=400, height=445, depth=150, thickness=1.2):
    # Развёртка = возвратные полки + боковины + задняя стенка (точный контур
    # с эталона). Габарит считается из этих же слагаемых.
    outline = _body_outline(width, depth, height)
    w = int(round(max(p[0] for p in outline)))     # полная ширина развёртки (~714)
    h = int(round(max(p[1] for p in outline)))     # ~440
    body = Part("Корпус", w, h, 1, thickness)
    body.outline = outline
    # 4 линии гиба: задняя↔боковины и боковины↔возвратные полки.
    # direction='inner' — внутренний сгиб, заданный АБСОЛЮТНОЙ позицией от края
    # (а не глубиной полки), поэтому НЕ вычитается из габарита (см. Part._fold_total).
    body.bend_lines = [
        BendLine(edge="left", offset=round(x, 1), angle=90, direction="inner",
                 note="гиб корпуса")
        for x in _body_folds(width, depth)
    ]
    # Отверстия — фиксированный отступ от краёв (узор с эталона), не в долях.
    _edge_holes(body, [
        ('L', 169.3, 'B', 11.6, 5), ('R', 168.8, 'B', 11.6, 5),
        ('L', 169.3, 'T', 12.6, 5), ('R', 168.8, 'T', 12.6, 5),
        ('L', 187.2, 'B', 32.5, 5), ('R', 186.8, 'B', 32.5, 5),
        ('L', 187.2, 'T', 33.5, 5), ('R', 186.8, 'T', 33.5, 5),
        ('L', 28.9, 'B', 70.0, 6), ('L', 28.9, 'T', 71.0, 6),
    ])
    body.description = ("Корпус шкафа: задняя стенка + боковины + возвратные "
                        "полки, гнётся из одного листа по 4 линиям гиба.")
    body.is_hidden_in_assembly = True
    return body


def build_cover(width=400, depth=150, thickness=1.2, cable=False):
    w = int(round(width + 1))         # 401
    h = int(round(depth + 10))        # 160
    name = "Крышка с кабельными вводами" if cable else "Крышка глухая"
    cover = Part(name, w, h, 1, thickness)
    cover.bend_lines = [_bend("top", 36, "отгиб планки")]
    cover.outline = _cover_outline(w, h)
    if cable:
        for x in (80.1, 201.8, 323.4):
            cover.cutouts.append(Cutout("circle", x * w / 401, h * 0.39, radius=16,
                                        label="Каб. ввод D32"))
    cover.description = ("Крышка корпуса (кабельные вводы D32)." if cable
                         else "Крышка корпуса (глухая).")
    cover.is_hidden_in_assembly = True
    return cover


def build_panel(width=400, height=445, thickness=1.2):
    w = int(round(width - 20))        # 380
    h = int(round(height - 30))       # 415
    panel = Part("Монтажная панель", w, h, 1, thickness)
    panel.outline = _panel_outline(w, h)
    # Отверстия на фиксированном отступе от краёв — не уезжают в угловые лапки.
    _edge_holes(panel, [
        ('L', 20, 'B', 20, 8), ('R', 20, 'B', 20, 8),
        ('L', 20, 'T', 20, 8), ('R', 20, 'T', 20, 8),
        ('L', 65, 'B', 80, 6), ('L', 65, 'T', 80, 6),
        ('R', 65, 'B', 80, 6), ('R', 65, 'T', 80, 6),
        ('R', 26, 'B', 45, 4),
    ])
    panel.description = ("Монтажная панель под аппаратуру (DIN-рейки, клеммы). "
                         "Угловые лапки для крепления.")
    panel.is_hidden_in_assembly = True
    return panel


def build_strip_a(thickness=1.2):
    """Полоска A 205x33 с надрезом слева, 2xD3."""
    s = Part("Полоска монтажная A", 205, 33, 1, thickness)
    s.outline = _strip_a_outline(205, 33)
    for x in (48, 151):
        s.cutouts.append(Cutout("circle", x, 16, radius=1.5))
    s.description = "Монтажная полоска (рейка) под аппаратуру."
    s.is_hidden_in_assembly = True
    return s


def build_strip_b(thickness=1.2):
    """Полоска B 305x33 (прямоугольная), 2xD3."""
    s = Part("Полоска монтажная B", 305, 33, 1, thickness)
    for x in (47, 250):
        s.cutouts.append(Cutout("circle", x, 16, radius=1.5))
    s.description = "Монтажная полоска (рейка) под аппаратуру."
    s.is_hidden_in_assembly = True
    return s


def build_bracket(thickness=1.2):
    """Кронштейн 20x50: скруглённая таблетка R5, D6, П-паз, овал (эталон)."""
    br = Part("Кронштейн", 20, 50, 1, thickness)
    br.outline = _rounded_rect(20, 50, 5)
    br.cutouts.append(Cutout("circle", 10, 44, radius=3))
    br.cutouts.append(Cutout("rect", 10, 7, width=5, height=3, label="паз"))
    br.extra_cuts.append((
        [(5, 20), (5, 13), (15, 13), (15, 20), (14, 20), (14, 14), (6, 14), (6, 20)], True))
    br.description = "Кронштейн крепления шкафа."
    br.is_hidden_in_assembly = True
    return br


DOOR_KINDS = {"blank": "глухая", "small": "с малым окном", "big": "с большим окном"}


def build_door(width=400, height=445, thickness=1.2, door_type="blank"):
    """Дверь. Полка 15.5 по всем сторонам, релиз-углы 15.5x15.5 (авто).
    Замок — скруглённый восьмигранник. Окно по типу двери."""
    if door_type not in DOOR_KINDS:
        raise ValueError(f"Неизвестный тип двери: {door_type}")
    flat_w = int(round(width + 2 * DOOR_FLANGE))       # 431
    flat_h = int(round(height - 5 + 2 * DOOR_FLANGE))  # 471 (лицо H-5)
    door = Part(f"Дверь {DOOR_KINDS[door_type]}", flat_w, flat_h, 1, thickness)
    door.bend_lines = [_bend(e, DOOR_FLANGE) for e in ("left", "right", "top", "bottom")]
    door.corner_relief = DOOR_FLANGE   # флаг + размер релиз-выреза (авто из гибов)

    # sx/sy — масштаб двери относительно эталона 430.5x471. И размер окна, и
    # его положение, и крепёж окна тянутся за размером двери (иначе на мелком
    # шкафу окно больше самой двери — был баг).
    sx, sy = flat_w / 430.5, flat_h / 471.0
    if door_type == "big":
        door.cutouts.append(Cutout("rect", 245 * sx, 236 * sy,
                                   width=BIG_WINDOW[0] * sx, height=BIG_WINDOW[1] * sy,
                                   label="Окно"))
    elif door_type == "small":
        # Малое окно КВАДРАТНОЕ -> равномерный масштаб (иначе на вытянутом
        # шкафу квадрат превращается в прямоугольник). 4 отверстия — на
        # СЕРЕДИНАХ граней окна (как в эталоне), а не по углам.
        wcx, wcy = 215 * sx, 364 * sy
        s = min(sx, sy)
        side = SMALL_WINDOW[0] * s
        door.cutouts.append(Cutout("rect", wcx, wcy, width=side, height=side, label="Окно"))
        off = (SMALL_WINDOW[0] / 2 - 2) * s     # чуть внутрь от кромки окна
        for dx, dy in ((0, -off), (0, off), (-off, 0), (off, 0)):
            door.cutouts.append(Cutout("circle", wcx + dx, wcy + dy, radius=2))

    # Замок — восьмигранник слева по центру (эталон)
    door.extra_cuts.append((_lock_octagon(66.5 * sx, 235.5 * sy, s=22), True))
    door.description = (f"Дверь электрошкафа ({DOOR_KINDS[door_type]}). Полка "
                        f"{DOOR_FLANGE}мм по периметру, замок-восьмигранник. "
                        f"Развёртка {flat_w}x{flat_h} (эталон 430.5x471).")
    door.is_hidden_in_assembly = False
    return door


# ==========================================================================
# СБОРКА
# ==========================================================================

class ElectricalCabinet:
    """Электромонтажный шкаф. Один чертёж-раскрой = все детали + 3 двери."""
    CODE = "ЭШ"

    @staticmethod
    def build(width=400, height=445, depth=150, thickness=1.2):
        m = Module(name=f"Электрошкаф {width}x{height}x{depth}",
                   module_type="Электрошкаф",
                   height=height, width=width, depth=depth, thickness=thickness)
        # 7 общих деталей
        for p in (build_body(width, height, depth, thickness),
                  build_cover(width, depth, thickness, cable=True),
                  build_cover(width, depth, thickness, cable=False),
                  build_panel(width, height, thickness),
                  build_strip_a(thickness),
                  build_strip_b(thickness),
                  build_bracket(thickness)):
            m.add_part(p)
        # 3 двери на выбор
        for dt in DOOR_KINDS:
            m.add_part(build_door(width, height, thickness, dt))

        # Флаг: экспорт DXF идёт единым раскроем в формате мастера, а не
        # кухонной раскладкой на лист (см. DXFExporter.export).
        m.cut_layout = True
        return m

    @staticmethod
    def showcase_parts(width=400, height=445, depth=150, thickness=1.2):
        """Все детали изделия (для единого раскроя)."""
        return list(ElectricalCabinet.build(width, height, depth, thickness).parts)
