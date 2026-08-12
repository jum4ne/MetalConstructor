"""
Лист детали в стиле мастера (ЕСКД / ГОСТ 2.104, форма 1) — чистый чертёж
без текстовых блоков-пояснений, как в референсном комплекте
«К 01.00.00.000 - Комплекс».

Отличие от старого draw_part_page (core/technical_drawing.py): там под
контуром был большой текстовый блок (таблица гибов/вырезов/назначение).
У мастера так НЕ делают — лист чисто графический:

  1. Развёртка (плоская заготовка) с размерами прямо на чертеже:
     бортики/язычки у кромок, габаритная ширина и высота.
  2. Вид сбоку (профиль) справа — высота в согнутом виде, борт, толщина,
     со значком «повернуть/гиб».
  3. Аксонометрический эскиз согнутой детали (справа снизу) с габаритами
     готовой детали.
  4. Штамп ЕСКД снизу + рамка + левая колонка граф.

Всё параметрично: размеры берутся из самой детали (Part), поэтому при
изменении габаритов модуля размеры на листе меняются автоматически.
"""
import math
from reportlab.lib.units import mm

from core.sheet_metal import (get_corners_needing_relief, build_outline_points,
                              get_corner_cuts)

# Тонкие обёртки над общими примитивами из technical_drawing, чтобы не
# дублировать код (шрифт, штамп, стрелки).
from core import technical_drawing as _td


# --------------------------------------------------------------------------
# Форматирование чисел «по-чертёжному»: целое без дробной части, иначе
# запятая (571.3 -> "571,3", 495.0 -> "495").
# --------------------------------------------------------------------------
def fmt(v):
    v = round(float(v), 1)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


# Стандартный ряд масштабов уменьшения по ГОСТ 2.302.
_STD_SCALES = [1.0, 0.5, 0.4, 0.25, 0.2, 0.1, 0.05, 0.04, 0.025, 0.02]


def snap_scale(fit):
    """Ближайший СТАНДАРТНЫЙ масштаб, не крупнее вписывающегося (1:1,1:2,1:2.5,1:4,1:5,1:10…)."""
    for s in _STD_SCALES:
        if s <= fit + 1e-9:
            return s
    return _STD_SCALES[-1]


def scale_label(scale):
    """'1:5' для 0.2, '1:2,5' для 0.4, '2:1' для 2.0 и т.п."""
    if scale >= 1:
        return f"{int(round(scale))}:1"
    inv = 1 / scale
    return "1:" + (str(int(round(inv))) if abs(inv - round(inv)) < 0.05
                   else f"{inv:.1f}".replace(".", ","))


# ==========================================================================
# РАЗМЕРНЫЕ ПРИМИТИВЫ (тонкие, в стиле ЕСКД: стрелки-засечки внутрь)
# ==========================================================================
ARROW = 2.0 * mm
GAP = 1.2 * mm         # зазор деталь -> выносная линия
OVER = 1.5 * mm        # выносная выступает за размерную


def _arrow(c, x, y, ang):
    a = math.radians(ang)
    bx, by = x - ARROW * math.cos(a), y - ARROW * math.sin(a)
    p = a + math.pi / 2
    w = 0.7 * mm
    path = c.beginPath()
    path.moveTo(x, y)
    path.lineTo(bx + w * math.cos(p), by + w * math.sin(p))
    path.lineTo(bx - w * math.cos(p), by - w * math.sin(p))
    path.close()
    c.setFillColorRGB(0, 0, 0)
    c.drawPath(path, fill=1, stroke=0)


def hdim(c, x1, x2, y_edge, off, text, above=True):
    """Горизонтальный размер под (или над) деталью."""
    yd = y_edge - off if off > 0 else y_edge - off
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    # выносные линии
    s = -1 if off >= 0 else 1
    c.line(x1, y_edge - s * GAP, x1, yd + s * OVER)
    c.line(x2, y_edge - s * GAP, x2, yd + s * OVER)
    c.line(x1, yd, x2, yd)
    _arrow(c, x1, yd, 0)
    _arrow(c, x2, yd, 180)
    c.setFont(_td.FONT_NAME, 7.5)
    c.setFillColorRGB(0, 0, 0)
    ty = yd + (0.8 * mm if above else -2.6 * mm)
    c.drawCentredString((x1 + x2) / 2, ty, text)


def vdim(c, y1, y2, x_edge, off, text, left=True):
    """Вертикальный размер слева (left=True) или справа от детали."""
    xd = x_edge - off if left else x_edge + off
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    s = 1 if left else -1
    c.line(x_edge - s * GAP, y1, xd + s * OVER, y1)
    c.line(x_edge - s * GAP, y2, xd + s * OVER, y2)
    c.line(xd, y1, xd, y2)
    _arrow(c, xd, y1, 90)
    _arrow(c, xd, y2, 270)
    c.saveState()
    c.translate(xd + (-1.4 * mm if left else 1.4 * mm), (y1 + y2) / 2)
    c.rotate(90)
    c.setFont(_td.FONT_NAME, 7.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def _centerlines(c, x0, y0, w, h):
    """Осевые линии (штрихпунктир) через середину детали."""
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.25)
    c.setDash([6, 2, 1, 2], 0)
    c.line(x0 - 4 * mm, y0 + h / 2, x0 + w + 4 * mm, y0 + h / 2)
    c.line(x0 + w / 2, y0 - 4 * mm, x0 + w / 2, y0 + h + 4 * mm)
    c.setDash()


def _bend_symbol(c, x, y, r=3.2 * mm):
    """Значок «гиб/повернуть»: дуга со стрелкой (как в референсе)."""
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.arc(x - r, y - r, x + r, y + r, 40, 260)
    # стрелка на конце дуги (внизу справа)
    ex, ey = x + r * math.cos(math.radians(40)), y + r * math.sin(math.radians(40))
    _arrow(c, ex, ey - 0.2 * mm, -10)


# ==========================================================================
# ВИДЫ
# ==========================================================================
def _bend_by_edge(part):
    d = {}
    for b in part.bend_lines:
        if b.direction != 'seam':
            d.setdefault(b.edge, b)
    return d


def draw_flat_pattern(c, part, x0, y0, scale):
    """Развёртка с осями, линиями гиба и размерами бортов/габарита."""
    w = part.flat_width * scale
    h = part.flat_height * scale
    bends = _bend_by_edge(part)

    corners = get_corners_needing_relief(part)

    # --- контур заготовки ---
    # Вырез в углу — прямоугольник ДО ЛИНИЙ ГИБА обоих смежных бортов
    # (иначе борта столкнутся при гибке), а не квадратик 2.5мм.
    if corners:
        cuts = {k: (dx * scale, dy * scale)
                for k, (dx, dy) in get_corner_cuts(part).items()}
        pts = build_outline_points(x0, y0, w, h, corners, cuts)
    else:
        pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h), (x0, y0)]
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0, 0, 0)
    path = c.beginPath()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    c.drawPath(path, fill=0, stroke=1)

    # --- оси ---
    _centerlines(c, x0, y0, w, h)

    # --- линии гиба: тонкий ПУНКТИР, чтобы цех не спутал их с контуром
    #     реза (толстая сплошная) и с осевой (штрихпунктир). ---
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0, 0, 0)
    c.setDash([3.5, 2], 0)
    for edge, b in bends.items():
        off = b.offset * scale
        if edge == 'left':
            c.line(x0 + off, y0, x0 + off, y0 + h)
        elif edge == 'right':
            c.line(x0 + w - off, y0, x0 + w - off, y0 + h)
        elif edge == 'top':
            c.line(x0, y0 + h - off, x0 + w, y0 + h - off)
        elif edge == 'bottom':
            c.line(x0, y0 + off, x0 + w, y0 + off)
    c.setDash()

    # --- вырезы: контур + осевые. Подпись — ОДНА на группу одинаковых
    #     вырезов («14 отв. ⌀6»), иначе на детали с рядом отверстий подписи
    #     сливаются в кашу и цех не может прочитать размер. ---
    from collections import OrderedDict
    groups = OrderedDict()
    for ct in part.cutouts:
        cx = x0 + ct.x * scale
        cy = y0 + ct.y * scale
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0, 0, 0)
        if ct.shape == 'rect':
            rx, ry = ct.width * scale / 2, ct.height * scale / 2
            c.rect(cx - rx, cy - ry, 2 * rx, 2 * ry, fill=0, stroke=1)
            key = ('rect', round(ct.width, 1), round(ct.height, 1))
            spec = f"{fmt(ct.width)}x{fmt(ct.height)}"
        else:
            rx = ry = ct.radius * scale
            c.circle(cx, cy, rx, fill=0, stroke=1)
            key = ('circle', round(ct.radius, 1))
            spec = f"⌀{fmt(ct.radius * 2)}"
        # осевые линии выреза (штрихпунктир) — база для замера центра
        c.setDash([4, 2, 1, 2], 0)
        c.setLineWidth(0.2)
        c.line(cx - rx - 2 * mm, cy, cx + rx + 2 * mm, cy)
        c.line(cx, cy - ry - 2 * mm, cx, cy + ry + 2 * mm)
        c.setDash()
        g = groups.setdefault(key, {"spec": spec, "items": []})
        g["items"].append((cx, cy, rx, ry))
    # одна подпись на группу — у первого выреза группы
    c.setFont(_td.FONT_NAME, 6.5)
    c.setFillColorRGB(0, 0, 0)
    for g in groups.values():
        cx, cy, rx, ry = g["items"][0]
        n = len(g["items"])
        label = (f"{n} отв. {g['spec']}" if n > 1 and g["spec"].startswith("⌀")
                 else (f"{n}× {g['spec']}" if n > 1 else g["spec"]))
        c.drawString(cx + rx + 1.2 * mm, cy + ry + 1 * mm, label)

    # --- размеры бортов у верхнего-левого угла (как у мастера: 19 и 20) ---
    inset = 8 * mm
    if 'top' in bends:
        nb = bends['top'].nominal or bends['top'].offset
        _small_vtick(c, x0 + inset, y0 + h - bends['top'].offset * scale, y0 + h, fmt(nb))
    if 'left' in bends:
        nb = bends['left'].nominal or bends['left'].offset
        _small_htick(c, y0 + h - inset, x0, x0 + bends['left'].offset * scale, fmt(nb))
    if 'right' in bends:
        nb = bends['right'].nominal or bends['right'].offset
        _small_htick(c, y0 + h - inset, x0 + w - bends['right'].offset * scale, x0 + w, fmt(nb))
    if 'bottom' in bends:
        nb = bends['bottom'].nominal or bends['bottom'].offset
        _small_vtick(c, x0 + inset, y0, y0 + bends['bottom'].offset * scale, fmt(nb))

    # --- габаритные размеры ---
    hdim(c, x0, x0 + w, y0, 11 * mm, fmt(part.flat_width))
    vdim(c, y0, y0 + h, x0, 11 * mm, fmt(part.flat_height), left=True)


def _small_htick(c, y, x1, x2, text):
    """Короткий горизонтальный размер (для борта) прямо на детали."""
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x1, y, x2, y)
    _arrow(c, x1, y, 0)
    _arrow(c, x2, y, 180)
    c.setFont(_td.FONT_NAME, 6.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString((x1 + x2) / 2, y + 0.8 * mm, text)


def _small_vtick(c, x, y1, y2, text):
    """Короткий вертикальный размер (для борта) прямо на детали."""
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x, y1, x, y2)
    _arrow(c, x, y1, 90)
    _arrow(c, x, y2, 270)
    c.saveState()
    c.translate(x - 1.2 * mm, (y1 + y2) / 2)
    c.rotate(90)
    c.setFont(_td.FONT_NAME, 6.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def draw_side_view(c, part, cx, y0, h_scale, thickness_pt=2.2 * mm):
    """
    Вид сбоку (профиль) — тонкая вертикальная полоса высотой = развёртка,
    с отогнутым бортом снизу и значком гиба. cx — ось вида.
    """
    h = part.flat_height * h_scale
    bends = _bend_by_edge(part)
    flange = 0
    if 'bottom' in bends:
        flange = (bends['bottom'].nominal or bends['bottom'].offset) * h_scale
    flange = max(flange, 6 * mm)

    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0, 0, 0)
    # вертикальная стенка (толщина 1*), борт снизу вправо
    x = cx
    c.line(x, y0, x, y0 + h)                       # стенка
    c.line(x, y0, x + flange, y0)                  # борт внизу
    # высота профиля
    vdim(c, y0, y0 + h, x, 10 * mm, fmt(part.flat_height), left=False)
    # борт (номинал, а если он не задан — позиция линии гиба)
    flange_nom = 20
    if 'bottom' in bends:
        flange_nom = bends['bottom'].nominal or bends['bottom'].offset
    hdim(c, x, x + flange, y0, 6 * mm, fmt(flange_nom))
    # толщина листа (пояснено в легенде: * — толщина S)
    c.setFont(_td.FONT_NAME, 6.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(x + 1 * mm, y0 + h - 4 * mm, "S*")


def draw_folded_pictorial(c, part, x0, y0, scale):
    """
    Эскиз согнутой детали: габарит готовой детали (formed) + намёк на борта.
    """
    w = part.formed_width * scale
    h = part.formed_height * scale
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(x0, y0, w, h, fill=0, stroke=1)
    # борта — тонкая внутренняя рамка (условно)
    inset = 3 * mm
    c.setLineWidth(0.3)
    c.setDash(2, 2)
    c.rect(x0 + inset, y0 + inset, w - 2 * inset, h - 2 * inset, fill=0, stroke=1)
    c.setDash()
    # габариты готовой детали
    hdim(c, x0, x0 + w, y0, 8 * mm, fmt(part.formed_width))
    vdim(c, y0, y0 + h, x0, 8 * mm, fmt(part.formed_height), left=True)


# ==========================================================================
# ОФОРМЛЕНИЕ ЛИСТА (рамка + левая колонка + «Копировал Формат A4»)
# ==========================================================================
def draw_frame(c, pw, ph, paper_format="A4",
               ml=20 * mm, mr=5 * mm, mt=5 * mm, mb=5 * mm):
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(ml, mb, pw - ml - mr, ph - mb - mt, fill=0, stroke=1)

    # Левая колонка граф ЕСКД (узкая полоса вдоль левой рамки)
    col_w = 7 * mm
    x = ml
    c.setLineWidth(0.5)
    c.line(x + col_w, mb, x + col_w, ph - mt)
    labels = [
        (0.14, "Перв. примен."),
        (0.30, "Справ. №"),
        (0.55, "Подп. и дата"),
        (0.66, "Инв. № дубл."),
        (0.76, "Взам. инв. №"),
        (0.87, "Инв. № подл."),
        (0.955, "Подп. и дата"),
    ]
    GREY = (0.25, 0.25, 0.25)
    for frac, text in labels:
        yy = mb + (ph - mb - mt) * frac
        c.saveState()
        c.translate(x + col_w - 1.6 * mm, yy)
        c.rotate(90)
        c.setFont(_td.FONT_NAME, 5.5)
        c.setFillColorRGB(*GREY)
        c.drawCentredString(0, 0, text)
        c.restoreState()
    # горизонтальные разделители колонки (по ЕСКД)
    for frac in (0.22, 0.42, 0.62, 0.82):
        yy = mb + (ph - mb - mt) * frac
        c.line(x, yy, x + col_w, yy)
    # Примечание: строку «Копировал / Формат A4» под рамкой НЕ рисуем —
    # формат уже указан в штампе, а текст в поле подшивки нарушает правило
    # «ничего за рамкой листа» (tests/test_layout.py).


def draw_designation_corner(c, x0, y0, code, bw=62 * mm, bh=13 * mm):
    """Обозначение в перевёрнутой рамочке в левом верхнем углу — как у мастера."""
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(x0, y0, bw, bh, fill=0, stroke=1)
    c.saveState()
    c.translate(x0 + bw / 2, y0 + bh / 2)
    c.rotate(180)
    c.setFont(_td.FONT_NAME, 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(0, -3, code)
    c.restoreState()


def _view_label(c, cx, y, text, size=7.5):
    """Подпись вида по центру (например, «Развёртка»)."""
    c.setFont(_td.FONT_NAME, size)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(cx, y, text)


def draw_line_legend(c, x0, y_top, w=54 * mm):
    """
    Легенда типов линий — чтобы цех однозначно понимал, что резать, а что
    гнуть. Рисуется в свободном правом верхнем углу листа.
    """
    rows = [
        ('cut', 'контур реза (лазер)'),
        ('bend', 'линия гиба (не резать)'),
        ('axis', 'осевая / центр (не резать)'),
    ]
    line_h = 4.6 * mm
    h = 5.5 * mm + len(rows) * line_h + 4.6 * mm
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(1, 1, 1)
    c.rect(x0, y_top - h, w, h, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_td.FONT_NAME, 6.5)
    c.drawString(x0 + 2 * mm, y_top - 4 * mm, "УСЛОВНЫЕ ОБОЗНАЧЕНИЯ")
    yy = y_top - 8.6 * mm
    for kind, label in rows:
        x1, x2 = x0 + 2 * mm, x0 + 14 * mm
        c.setStrokeColorRGB(0, 0, 0)
        if kind == 'cut':
            c.setDash(); c.setLineWidth(0.9)
        elif kind == 'bend':
            c.setDash([3.5, 2], 0); c.setLineWidth(0.4)
        else:
            c.setDash([5, 2, 1, 2], 0); c.setLineWidth(0.25)
        c.line(x1, yy, x2, yy)
        c.setDash()
        c.setFillColorRGB(0, 0, 0)
        c.setFont(_td.FONT_NAME, 6)
        c.drawString(x0 + 15.5 * mm, yy - 1 * mm, label)
        yy -= line_h
    c.setFont(_td.FONT_NAME, 6)
    c.drawString(x0 + 2 * mm, yy - 0.5 * mm, "Размеры в мм.  * — толщина листа S.")


def draw_tube_legend(c, x0, y_top, w=54 * mm):
    """Легенда для листа трубы — те же обозначения, что и на листах деталей."""
    rows = [
        ('cut', 'контур реза (пила/лазер)'),
        ('axis', 'осевая линия (не резать)'),
    ]
    line_h = 4.6 * mm
    h = 5.5 * mm + len(rows) * line_h + 4.6 * mm
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(1, 1, 1)
    c.rect(x0, y_top - h, w, h, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_td.FONT_NAME, 6.5)
    c.drawString(x0 + 2 * mm, y_top - 4 * mm, "УСЛОВНЫЕ ОБОЗНАЧЕНИЯ")
    yy = y_top - 8.6 * mm
    for kind, label in rows:
        x1, x2 = x0 + 2 * mm, x0 + 14 * mm
        c.setStrokeColorRGB(0, 0, 0)
        if kind == 'cut':
            c.setDash(); c.setLineWidth(0.9)
        else:
            c.setDash([5, 2, 1, 2], 0); c.setLineWidth(0.25)
        c.line(x1, yy, x2, yy)
        c.setDash()
        c.setFillColorRGB(0, 0, 0)
        c.setFont(_td.FONT_NAME, 6)
        c.drawString(x0 + 15.5 * mm, yy - 1 * mm, label)
        yy -= line_h
    c.setFont(_td.FONT_NAME, 6)
    c.drawString(x0 + 2 * mm, yy - 0.5 * mm, "Размеры в мм. Рез под 90°.")


def draw_tube_sheet(c, tube, page_size, code, quantity, mass_kg, company_name,
                    material=None, sheet_num=1, sheets_total=1, paper_format="A4"):
    """
    Лист отрезка профильной трубы — В ЕДИНОМ СТИЛЕ с листами деталей
    (рамка ЕСКД + левая колонка + обозначение-уголок + легенда + штамп).

    Два вида: отрезок сбоку (габаритная длина реза) и сечение профиля
    крупнее — с наружными размерами и толщиной стенки.
    """
    _td._register_font()
    pw, ph = page_size
    ml, mr, mt, mb = 20 * mm, 5 * mm, 5 * mm, 5 * mm
    title_h = 55 * mm
    main_x0 = ml + 7 * mm + 16 * mm
    LBL = 4.5 * mm

    region_bottom = mb + title_h + 14 * mm
    region_top = ph - mt - 32 * mm

    # ---- Главный вид: отрезок трубы сбоку, стандартный масштаб ----
    avail_w = (pw - mr - 10 * mm) - main_x0
    r = snap_scale(min(avail_w / (tube.length * mm), 1.0))
    scale = r * mm
    bar_w = tube.length * scale
    bar_h = max(tube.profile_h * scale, 5 * mm)   # очень тонкую трубу поднимаем до видимой

    main_y0 = region_top - bar_h - 12 * mm
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(main_x0, main_y0, bar_w, bar_h, fill=0, stroke=1)
    # осевая линия по длине
    c.setDash([6, 2, 1, 2], 0)
    c.setLineWidth(0.25)
    c.line(main_x0 - 4 * mm, main_y0 + bar_h / 2, main_x0 + bar_w + 4 * mm, main_y0 + bar_h / 2)
    c.setDash()

    hdim(c, main_x0, main_x0 + bar_w, main_y0, 11 * mm, fmt(tube.length))
    _view_label(c, main_x0 + bar_w / 2, main_y0 - 11 * mm - LBL,
                f"Отрезок трубы {tube.profile_label} — длина реза")

    # ---- Сечение профиля (крупнее, чтобы читалась стенка) ----
    sec_r = snap_scale(min((36 * mm) / (max(tube.profile_w, tube.profile_h) * mm), 2.0))
    sec_scale = sec_r * mm
    sw = tube.profile_w * sec_scale
    sh = tube.profile_h * sec_scale
    wall = tube.wall * sec_scale
    sec_x0 = main_x0 + 6 * mm
    sec_y0 = main_y0 - 11 * mm - LBL - 30 * mm - sh
    sec_y0 = max(sec_y0, region_bottom + 16 * mm)

    c.setLineWidth(0.7)
    c.rect(sec_x0, sec_y0, sw, sh, fill=0, stroke=1)
    if wall * 2 < min(sw, sh):        # внутренняя полость
        c.setLineWidth(0.5)
        c.rect(sec_x0 + wall, sec_y0 + wall, sw - 2 * wall, sh - 2 * wall, fill=0, stroke=1)

    hdim(c, sec_x0, sec_x0 + sw, sec_y0, 9 * mm, fmt(tube.profile_w))
    vdim(c, sec_y0, sec_y0 + sh, sec_x0, 9 * mm, fmt(tube.profile_h), left=True)
    _view_label(c, sec_x0 + sw / 2, sec_y0 - 9 * mm - LBL,
                f"Сечение профиля ({scale_label(sec_r)})")

    # Толщина стенки — выноской справа от сечения
    c.setFont(_td.FONT_NAME, 7)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(sec_x0 + sw + 8 * mm, sec_y0 + sh / 2,
                 f"Стенка S = {fmt(tube.wall)} мм")
    if tube.note:
        c.setFont(_td.FONT_NAME, 6.5)
        c.drawString(sec_x0 + sw + 8 * mm, sec_y0 + sh / 2 - 5 * mm, f"({tube.note})")

    # ---- Оформление листа ----
    draw_frame(c, pw, ph, paper_format, ml, mr, mt, mb)
    draw_designation_corner(c, main_x0, ph - mt - 15 * mm, code)
    draw_tube_legend(c, pw - mr - 56 * mm, ph - mt - 3 * mm)

    if material is None:
        material = f"Труба профильная {tube.profile_label}"
    stamp_x0 = pw - mr - 185 * mm
    _td.draw_title_block(c, stamp_x0, mb, {
        "code": code,
        "name": tube.name,
        "mass": fmt(mass_kg),
        "scale": scale_label(r),
        "qty": quantity,
        "material": material,
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })


# ==========================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==========================================================================
def draw_detail_sheet(c, part, page_size, code, quantity, mass_kg, company_name,
                      material=None, sheet_num=1, sheets_total=1, paper_format="A4"):
    """Нарисовать один лист детали в стиле мастера."""
    _td._register_font()
    pw, ph = page_size
    ml, mr, mt, mb = 20 * mm, 5 * mm, 5 * mm, 5 * mm
    title_h = 55 * mm

    main_x0 = ml + 7 * mm + 16 * mm        # левая колонка + место под верт. размер

    # Масштаб СТАНДАРТНЫЙ (ГОСТ 2.302): вписываем главный вид в ~110x150мм и
    # снапим к ряду 1:1,1:2,1:2.5,1:4,1:5… — как выбирает конструктор.
    fit_r = min((110 * mm) / (part.flat_width * mm),
                (150 * mm) / (part.flat_height * mm))
    r = snap_scale(fit_r)
    scale = r * mm                          # points на 1 мм детали
    w = part.flat_width * scale
    h = part.flat_height * scale

    # Эскиз согнутой детали — компактнее главного вида
    pict_scale = r * 0.45 * mm
    pict_w = part.formed_width * pict_scale
    pict_h = part.formed_height * pict_scale

    is_bent = part.is_bent
    LBL = 4.5 * mm          # место под подпись вида
    GAP = 12 * mm           # зазор между главным видом и эскизом (с размерами)

    # Рабочая область между штампом снизу и полосой «обозначение/легенда» сверху.
    region_bottom = mb + title_h + 12 * mm
    region_top = ph - mt - 32 * mm          # ниже уголка обозначения и легенды
    region_h = region_top - region_bottom

    main_block = h + 11 * mm + LBL          # главный вид + нижний размер + подпись
    pict_block = (pict_h + 8 * mm + LBL) if is_bent else 0

    # Эскиз кладём ПОД главным видом только если вертикально помещается;
    # иначе (высокая узкая деталь) — справа. Так вид НИКОГДА не вылезает за
    # рамку листа (раньше высокая деталь выезжала на штамп/обозначение).
    stack_below = is_bent and (main_block + GAP + pict_block <= region_h)

    if stack_below:
        stacked_h = main_block + GAP + pict_block
        group_top = min(region_bottom + (region_h + stacked_h) / 2, region_top)
        main_y0 = group_top - h
    else:
        main_y0 = region_top - h            # верхнее выравнивание — без наложений

    # --- Главный вид: развёртка ---
    draw_flat_pattern(c, part, main_x0, main_y0, scale)
    _view_label(c, main_x0 + w / 2, main_y0 - 11 * mm - LBL,
                "Развёртка — заготовка под лазерную резку" if is_bent
                else "Развёртка (гибка не требуется)")

    # --- Вид сбоку — только для гнутых деталей и только если помещается справа ---
    side_cx = main_x0 + w + 22 * mm
    side_drawn = False
    if is_bent and 'bottom' in _bend_by_edge(part) and side_cx + 26 * mm < pw - mr:
        draw_side_view(c, part, side_cx, main_y0, scale)
        _view_label(c, side_cx + 4 * mm, main_y0 - 11 * mm - LBL, "Вид сбоку")
        side_drawn = True

    # --- Эскиз согнутой детали ---
    if is_bent and stack_below:
        pict_y0 = main_y0 - 11 * mm - LBL - GAP - pict_h
        draw_folded_pictorial(c, part, main_x0, pict_y0, pict_scale)
        _view_label(c, main_x0 + pict_w / 2, pict_y0 - 8 * mm - LBL,
                    "Готовая деталь (после гибки)")
    elif is_bent:
        # высокая деталь: эскиз справа (если влезает по ширине), иначе не рисуем
        base_x = (side_cx + 20 * mm) if side_drawn else (main_x0 + w + 22 * mm)
        if base_x + pict_w <= pw - mr - 3 * mm and pict_block <= region_h:
            pict_y0 = min(region_bottom + 10 * mm + pict_h, region_top) - pict_h
            draw_folded_pictorial(c, part, base_x, pict_y0, pict_scale)
            _view_label(c, base_x + pict_w / 2, pict_y0 - 8 * mm - LBL,
                        "Готовая деталь (после гибки)")

    # --- рамка, колонка, обозначение-уголок (слева сверху, как у мастера) ---
    draw_frame(c, pw, ph, paper_format, ml, mr, mt, mb)
    draw_designation_corner(c, main_x0, ph - mt - 15 * mm, code)

    # --- легенда типов линий (правый верхний угол, свободное место) ---
    draw_line_legend(c, pw - mr - 56 * mm, ph - mt - 3 * mm)

    # --- штамп ЕСКД (переиспользуем проверенный по мастеру блок) ---
    if material is None:
        # Толщину пишем как у мастера — всегда с десятой: «S 1,0», «S 2,0».
        material = "Лист НЕРЖ S " + f"{part.thickness:.1f}".replace(".", ",")
    stamp_x0 = pw - mr - 185 * mm
    _td.draw_title_block(c, stamp_x0, mb, {
        "code": code,
        "name": part.name,
        "mass": fmt(mass_kg),
        "scale": scale_label(r),
        "qty": quantity,
        "material": material,
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })
