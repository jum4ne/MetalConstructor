"""
Генерация полноценных технических чертежей деталей - с размерными линиями,
выносками и штампом, как в настоящей конструкторской документации
(разобрано на примере реального 91-страничного комплекта чертежей).

В отличие от старого PDFExporter (просто таблица деталей), здесь на
каждую уникальную деталь рисуется отдельная страница: масштабированный
контур детали (с вырезами и линиями гиба), проставленные размеры со
стрелками, и штамп снизу (обозначение/наименование/масса/масштаб) -
упрощённый аналог штампа по ГОСТ 2.104.
"""
import os
import time
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import Config
from core.sheet_metal import get_corners_needing_relief, build_outline_points
from core.exploded_view import build_cabinet_scene, draw_exploded_view
from core.assembly_view import draw_assembly_views
from core.spec_page import draw_spec_page, draw_project_spec_page
from core.project_scene import build_project_scene, draw_project_scene_page
from core.assembly_tree import build_assembly_tree
from core.section_page import draw_section_divider
from core.part_semantics import HIDDEN_NOTICE

FONT_NAME = "Helvetica"
_FONT_REGISTERED = False
_FONT_PATH = None


# Символы, которых НЕТ в чертёжном шрифте GOSTTypeA (проверено программно
# по cmap шрифта): длинное тире и его родня. Если их не заменить, reportlab
# рисует .notdef и в PDF получается пустой квадрат/\x00 вместо тире - что
# и вылезало в заголовках вида "Тумба — спецификация".
#
# Спецсимволы ⌀ (диаметр), ° (градус) и × в шрифте ЕСТЬ - их не трогаем.
# Запасные замены для символов, которых нет в АКТИВНОМ шрифте.
#
# ВАЖНО: таблица применяется НЕ вслепую. Раньше здесь заменялись «», № и
# другие символы "на всякий случай" - и в PDF выходило «Комплекс N1» и
# НПО "Кристалл" вместо №1 и «Кристалл», хотя эти глифы в шрифте ЕСТЬ.
#
# Теперь sanitize() сначала спрашивает у самого шрифта, умеет ли он
# рисовать символ (_font_supports), и заменяет ТОЛЬКО то, что он
# действительно не умеет. Если шрифт целый - не трогается ничего.
_GLYPH_FALLBACK = {
    "—": "-",   # em dash
    "–": "-",   # en dash
    "−": "-",   # minus sign
    "‑": "-",   # non-breaking hyphen
    "«": '"',
    "»": '"',
    "„": '"',
    "“": '"',
    "”": '"',
    "…": "...",
    "№": "N",
    "±": "+/-",
    "⌀": "d",
    "°": "гр.",
    "×": "x",
}

# Кэш "какие символы активный шрифт реально рисует"
_SUPPORTED = None


def _load_supported():
    """
    Спросить у зарегистрированного TTF, у каких символов есть КОНТУР.

    Именно контур, а не наличие в cmap: в битом GOSTTypeA коды букв в cmap
    были, а глифы пустые (замаплены на латинские "multiply", "dieresis"),
    из-за чего Ч, Ё, ±, ⌀ печатались как пустое место.
    """
    global _SUPPORTED
    if _SUPPORTED is not None:
        return _SUPPORTED
    _SUPPORTED = set()
    if not _FONT_PATH:
        return _SUPPORTED
    try:
        from fontTools.ttLib import TTFont as _TT
        f = _TT(_FONT_PATH)
        cmap = f.getBestCmap()
        glyf = f.get("glyf")
        for code, gname in cmap.items():
            if glyf is None:
                _SUPPORTED.add(code)
            else:
                g = glyf[gname]
                if getattr(g, "numberOfContours", 0) != 0:
                    _SUPPORTED.add(code)
    except Exception:
        # fontTools может быть не установлен на проде - тогда работаем
        # по старой схеме (заменяем всё из таблицы), это безопасный откат.
        _SUPPORTED = set()
    return _SUPPORTED


def _font_supports(ch):
    sup = _load_supported()
    if not sup:
        return False       # ничего не знаем -> считаем, что не умеет
    return ord(ch) in sup


def sanitize(text):
    """
    Заменить только те символы, которые АКТИВНЫЙ шрифт не умеет рисовать.

    Целый шрифт -> текст не меняется вообще (и «Кристалл», №1, ±0,5, ⌀34
    печатаются как надо). Битый -> подставляются безопасные аналоги, чтобы
    вместо буквы не было пустого места.
    """
    if not isinstance(text, str):
        return text
    if FONT_NAME != "CyrillicFont":
        return text
    out = []
    for ch in text:
        if ch in _GLYPH_FALLBACK and not _font_supports(ch):
            out.append(_GLYPH_FALLBACK[ch])
        else:
            out.append(ch)
    return "".join(out)


def _install_font_guard(canvas_cls):
    """
    Обернуть текстовые методы Canvas санитайзером один раз на класс.
    Так любой код (включая spec_page/exploded_view/assembly_view, которые
    рисуют текст сами) автоматически получает защиту от отсутствующих глифов.
    """
    if getattr(canvas_cls, "_mc_font_guard", False):
        return
    for meth in ("drawString", "drawCentredString", "drawRightString"):
        orig = getattr(canvas_cls, meth)

        def make(orig):
            def wrapper(self, x, y, text, *a, **kw):
                return orig(self, x, y, sanitize(text), *a, **kw)
            return wrapper

        setattr(canvas_cls, meth, make(orig))
    canvas_cls._mc_font_guard = True


def _register_font():
    global FONT_NAME, _FONT_REGISTERED, _FONT_PATH, _SUPPORTED
    _install_font_guard(pdfcanvas.Canvas)
    if _FONT_REGISTERED:
        return

    # Чертёжный шрифт ГОСТ 2.304 (GOSTTypeA), извлечён из референсного PDF.
    #
    # ВНИМАНИЕ, ИСТОРИЯ БАГА. Исходный GOSTTypeA.ttf НЕПОЛНОЦЕННЫЙ: в его
    # cmap коды всех русских букв ЕСТЬ, поэтому наивная проверка "все ли
    # буквы в шрифте" их находила и говорила "ОК". Но cmap - это лишь
    # таблица "код -> ИМЯ глифа"; она не гарантирует, что у глифа есть
    # КОНТУР. У 19 символов контура не было - они были замаплены на чужие
    # пустые латинские глифы:
    #
    #     'Ч' -> "multiply",  'Ё' -> "dieresis",  'Ц' -> "Odieresis", ...
    #     плюс ± ° ⌀ ×  (то есть ДОПУСКИ И ДИАМЕТРЫ тоже не печатались!)
    #
    # В PDF это давало пустое место: "Развёртка" -> "Разв ртка",
    # "НАЗНАЧЕНИЕ" -> "НАЗНА ЕНИЕ", "±0,5" -> " 0,5".
    #
    # Починенный GOSTTypeA-fixed.ttf собирается скриптом tools/fix_font.py:
    # он вклеивает недостающие глифы из шрифта с полной кириллицей,
    # сохраняя ГОСТ-начертание остальных букв. Его и берём ПЕРВЫМ.
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "assets", "fonts")
    fixed_path = os.path.normpath(os.path.join(fonts_dir, "GOSTTypeA-fixed.ttf"))
    gost_font_path = os.path.normpath(os.path.join(fonts_dir, "GOSTTypeA.ttf"))

    candidates = [
        fixed_path,          # починенный ГОСТ - основной вариант
        gost_font_path,      # оригинал (с дырами) - если починенного нет
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CyrillicFont", path))
                FONT_NAME = "CyrillicFont"
                _FONT_PATH = path
                _SUPPORTED = None       # сбросить кэш под новый шрифт
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    _FONT_REGISTERED = True  # не нашли - останется Helvetica (без кириллицы)


ARROW_LEN = 2.2 * mm
ARROW_WIDTH = 0.8 * mm
EXT_LINE_GAP = 1.5 * mm      # зазор между деталью и началом выносной линии
EXT_LINE_OVERSHOOT = 1.5 * mm  # выносная линия чуть выступает за размерную


def _draw_arrowhead(c, x, y, angle_deg):
    """Нарисовать закрашенную стрелку-треугольник в точке (x,y),
    направленную по углу angle_deg (0 = вправо, 90 = вверх и т.д.)"""
    import math
    a = math.radians(angle_deg)
    tip = (x, y)
    back_x = x - ARROW_LEN * math.cos(a)
    back_y = y - ARROW_LEN * math.sin(a)
    perp = a + math.pi / 2
    p1 = (back_x + ARROW_WIDTH * math.cos(perp), back_y + ARROW_WIDTH * math.sin(perp))
    p2 = (back_x - ARROW_WIDTH * math.cos(perp), back_y - ARROW_WIDTH * math.sin(perp))
    path = c.beginPath()
    path.moveTo(*tip)
    path.lineTo(*p1)
    path.lineTo(*p2)
    path.close()
    c.setFillColorRGB(0, 0, 0)
    c.drawPath(path, fill=1, stroke=0)


def draw_horizontal_dimension(c, x1, x2, y_part_edge, dim_offset, text):
    """
    Размерная линия по горизонтали под деталью: выносные линии вниз от
    краёв детали, размерная линия со стрелками между ними, текст по центру.
    """
    y_dim = y_part_edge - dim_offset

    # выносные линии (от края детали до чуть ниже размерной линии)
    c.setLineWidth(0.3)
    c.line(x1, y_part_edge - EXT_LINE_GAP, x1, y_dim - EXT_LINE_OVERSHOOT)
    c.line(x2, y_part_edge - EXT_LINE_GAP, x2, y_dim - EXT_LINE_OVERSHOOT)

    # размерная линия
    c.line(x1, y_dim, x2, y_dim)
    _draw_arrowhead(c, x1, y_dim, 0)     # стрелка смотрит вправо (внутрь линии)
    _draw_arrowhead(c, x2, y_dim, 180)   # стрелка смотрит влево (внутрь линии)

    # текст по центру над линией
    c.setFont(FONT_NAME, 8)
    c.drawCentredString((x1 + x2) / 2, y_dim + 1 * mm, text)


def draw_vertical_dimension(c, y1, y2, x_part_edge, dim_offset, text):
    """Аналогично, но размерная линия слева от детали (вертикальная)"""
    x_dim = x_part_edge - dim_offset

    c.setLineWidth(0.3)
    c.line(x_part_edge - EXT_LINE_GAP, y1, x_dim - EXT_LINE_OVERSHOOT, y1)
    c.line(x_part_edge - EXT_LINE_GAP, y2, x_dim - EXT_LINE_OVERSHOOT, y2)

    c.line(x_dim, y1, x_dim, y2)
    _draw_arrowhead(c, x_dim, y1, 90)
    _draw_arrowhead(c, x_dim, y2, 270)

    c.saveState()
    c.translate(x_dim - 2 * mm, (y1 + y2) / 2)
    c.rotate(90)
    c.setFont(FONT_NAME, 8)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def draw_title_block(c, x0, y0, fields):
    """
    Штамп по ГОСТ 2.104 (форма 1) - размеры и разбивка на графы взяты НЕ из
    памяти/интернета, а вычислены напрямую по координатам линий в реальном
    91-страничном комплекте чертежей стороннего производства (страница с
    деталью "Дно"). Общий размер блока 185x55мм подтверждён координатами
    с точностью до десятых долей миллиметра.

    x0, y0 - координаты ЛЕВОГО НИЖНЕГО угла штампа на странице.

    fields: dict с ключами code, name, mass, scale, qty, material, company,
            sheet (номер листа), sheets_total (кол-во листов), format (А4/А3)
    """
    W, H = 185 * mm, 55 * mm
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    c.rect(x0, y0, W, H)

    def vline(x, y1, y2):
        c.line(x0 + x * mm, y0 + y1 * mm, x0 + x * mm, y0 + y2 * mm)

    def hline(x1, x2, y):
        c.line(x0 + x1 * mm, y0 + y * mm, x0 + x2 * mm, y0 + y * mm)

    def text(x, y, s, size=7, color=(0, 0, 0), align="left", font=None):
        c.setFont(font or FONT_NAME, size)
        c.setFillColorRGB(*color)
        if align == "left":
            c.drawString(x0 + x * mm, y0 + y * mm, s)
        elif align == "center":
            c.drawCentredString(x0 + x * mm, y0 + y * mm, s)

    GREY = (0.45, 0.45, 0.45)

    # ============ ЛЕВАЯ ЧАСТЬ (0-65мм) ============
    vline(65, 0, 55)  # граница левой/правой части на всю высоту

    # --- Верхний блок слева: таблица изменений (30-55мм, 5 строк) ---
    for y in (30, 35, 40, 45, 50):
        hline(0, 65, y)
    for x in (7, 17, 40, 55):
        vline(x, 30, 55)
    text(1, 51, "Изм.", 5.5, GREY)
    text(8, 51, "Лист", 5.5, GREY)
    text(18, 51, "№ докум.", 5.5, GREY)
    text(41, 51, "Подп.", 5.5, GREY)
    text(56, 51, "Дата", 5.5, GREY)

    # --- Нижний блок слева: подписи разработчиков (0-30мм, 6 строк) ---
    for y in (5, 10, 15, 20, 25):
        hline(0, 65, y)
    for x in (17, 40, 55):
        vline(x, 0, 30)
    roles = ["Утв.", "Н.контр.", "", "Т.контр.", "Пров.", "Разраб."]
    for i, role in enumerate(roles):
        if role:
            text(1, 1.5 + i * 5, role, 6)

    # ============ ПРАВАЯ ЧАСТЬ (65-185мм, 120мм) ============
    # --- Обозначение (крупно, во всю ширину правой части, 40-55мм) ---
    hline(65, 185, 40)
    text(65 + 60, 44, fields["code"], 11, align="center")

    # --- Наименование (65+70=135мм, 15-40мм = 25мм высотой) ---
    vline(135, 15, 55)
    hline(65, 135, 15)
    text(65 + 35, 26, fields["name"], 10, align="center")

    # --- Правая колонка мелких граф (135-185мм) ---
    # Строка Лит/Масса/Масштаб (35-40мм)
    hline(135, 185, 35)
    vline(150, 35, 40)
    vline(167, 35, 40)
    text(137, 36.3, "Лит.", 5, GREY)
    text(152, 36.3, "Масса", 5, GREY)
    text(169, 36.3, "Масштаб", 5, GREY)

    # Значения Литеры/Массы/Масштаба (30-35мм)
    hline(135, 185, 30)
    vline(150, 30, 35)
    vline(167, 30, 35)
    text(137, 31.3, "", 8)
    text(152, 31.3, fields["mass"], 8)
    text(169, 31.3, fields["scale"], 8)

    # Лист / Листов (25-30мм)
    hline(135, 185, 25)
    vline(160, 25, 35)
    text(137, 26.3, "Лист", 5.5, GREY)
    text(162, 26.3, "Листов", 5.5, GREY)

    hline(135, 185, 20)
    vline(160, 15, 25)
    text(137, 21.3, str(fields["sheet"]), 8, align="left")
    text(162, 21.3, str(fields["sheets_total"]), 8, align="left")

    # --- Кол-во и Материал под Наименованием (0-15мм под левой подобластью Наименования) ---
    vline(135, 0, 15)
    hline(65, 135, 5)
    hline(65, 135, 10)
    text(66, 11.3, "Кол-во", 5.5, GREY)
    text(66, 6.3, str(fields["qty"]), 8)
    text(66, 1.3, f"Материал: {fields['material']}", 6.5)

    # --- Компания / формат снизу справа (0-15мм, правая колонка) ---
    hline(135, 185, 5)
    text(160, 8, fields["company"], 8, align="center")
    text(137, 1.3, f"Формат {fields['format']}", 6)


def draw_tube_page(c, tube, page_size, code, quantity, mass_kg, company_name,
                    sheet_num=1, sheets_total=1, paper_format="A4"):
    """
    Нарисовать страницу для отрезка профильной трубы - упрощённая схема
    (труба это прямой погонаж, не плоская деталь, поэтому вместо контура
    с вырезами рисуем схематичный отрезок с габаритной длиной + отдельно
    сечение профиля со своими размерами).
    """
    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    # --- Схематичный отрезок трубы (длинный тонкий прямоугольник) ---
    bar_area_w = page_w - margin_left - margin_right - 20 * mm - 10 * mm  # +10мм воздуха справа
    bar_h = 14 * mm
    bar_scale = min(bar_area_w / tube.length, 1.0)
    bar_w = tube.length * bar_scale

    bar_x0 = margin_left + 20 * mm
    bar_y0 = page_h - margin_top - 60 * mm

    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(bar_x0, bar_y0, bar_w, bar_h, fill=0, stroke=1)
    # штриховка внутри - условное обозначение проката по ГОСТ (наклонные линии)
    c.setLineWidth(0.25)
    step = 6 * mm
    x = bar_x0
    while x < bar_x0 + bar_w:
        c.line(max(x, bar_x0), bar_y0, min(x + bar_h, bar_x0 + bar_w), bar_y0 + bar_h)
        x += step

    draw_horizontal_dimension(c, bar_x0, bar_x0 + bar_w, bar_y0, 10 * mm, f"{tube.length}")

    # --- Сечение профиля (маленький прямоугольник со своими размерами) ---
    sec_scale = min(30 * mm / max(tube.profile_w, tube.profile_h), 3.0)
    sec_w = tube.profile_w * sec_scale
    sec_h = tube.profile_h * sec_scale
    sec_x0 = margin_left + 20 * mm
    sec_y0 = bar_y0 - 55 * mm

    c.setLineWidth(0.6)
    c.rect(sec_x0, sec_y0, sec_w, sec_h, fill=0, stroke=1)
    # внутренний контур стенки трубы (труба полая) - смещён на толщину стенки
    wall_scaled = tube.wall * sec_scale
    if wall_scaled * 2 < min(sec_w, sec_h):
        c.setLineWidth(0.3)
        c.rect(sec_x0 + wall_scaled, sec_y0 + wall_scaled,
               sec_w - 2 * wall_scaled, sec_h - 2 * wall_scaled, fill=0, stroke=1)

    draw_horizontal_dimension(c, sec_x0, sec_x0 + sec_w, sec_y0, 10 * mm, f"{tube.profile_w}")
    draw_vertical_dimension(c, sec_y0, sec_y0 + sec_h, sec_x0, 10 * mm, f"{tube.profile_h}")

    c.setFont(FONT_NAME, 8)
    c.drawString(sec_x0 + sec_w + 8 * mm, sec_y0 + sec_h / 2, f"Стенка {tube.wall}мм")
    if tube.note:
        c.drawString(sec_x0 + sec_w + 8 * mm, sec_y0 + sec_h / 2 - 6 * mm, f"({tube.note})")

    # --- Внешняя рамка листа ---
    c.setLineWidth(1.0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    # --- Штамп ---
    stamp_x0 = page_w - margin_right - 185 * mm
    draw_title_block(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": tube.name,
        "mass": f"{mass_kg:.2f}",
        "scale": "б/м",  # труба без масштаба - условная схема
        "qty": quantity,
        "material": f"профиль {tube.profile_label}мм",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })


EDGE_RU = {'left': 'левая', 'right': 'правая', 'top': 'верхняя', 'bottom': 'нижняя'}


def _wrap(text, max_chars):
    """Простой перенос текста по словам (у reportlab.canvas нет авто-переноса)"""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_leader(c, x_from, y_from, x_to, y_to, text, font_name=None):
    """Выноска: линия от точки на детали к тексту сбоку (полка + подпись)"""
    c.setLineWidth(0.3)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x_from, y_from, x_to, y_to)
    c.line(x_to, y_to, x_to + 4 * mm, y_to)   # полка выноски
    c.setFont(font_name or FONT_NAME, 6.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(x_to + 5 * mm, y_to - 0.8 * mm, text)


def _draw_line_legend(c, x, y, has_bends=True, has_cutouts=False):
    """
    Легенда типов линий на листе развёртки.

    Без неё цех не отличает контур реза от линии гиба - а это
    принципиально разные операции (лазер vs гибочный станок).
    """
    rows = [("solid", "— контур реза (лазер)")]
    if has_bends:
        rows.append(("bend", "— линия гиба (не резать)"))
    if has_cutouts:
        rows.append(("axis", "— осевая выреза (не резать)"))

    w = 50 * mm
    h = 5 * mm + len(rows) * 4.2 * mm

    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y - h, w, h, fill=1, stroke=1)

    c.setFillColorRGB(0, 0, 0)
    c.setFont(FONT_NAME, 6.5)
    c.drawString(x + 1.5 * mm, y - 4 * mm, "ЛИНИИ:")

    yy = y - 8 * mm
    for kind, label in rows:
        x1, x2 = x + 2 * mm, x + 12 * mm
        if kind == "solid":
            c.setDash()
            c.setLineWidth(0.6)
            c.setStrokeColorRGB(0, 0, 0)
        elif kind == "bend":
            c.setDash(2, 2)
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.2, 0.4, 0.7)
        else:
            c.setDash(1, 2)
            c.setLineWidth(0.25)
            c.setStrokeColorRGB(0.7, 0, 0.5)
        c.line(x1, yy, x2, yy)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        c.setFont(FONT_NAME, 6)
        c.drawString(x + 13 * mm, yy - 1 * mm, label)
        yy -= 4.2 * mm

    c.setLineWidth(0.5)


def draw_part_page(c, part, page_size, code, quantity, mass_kg, company_name,
                    sheet_num=1, sheets_total=1, paper_format="A4"):
    """
    Чертёж детали - ПОЛНЫЙ набор данных для раскроя и сборки, без сокращений:

      - контур РАЗВЁРТКИ (плоской заготовки под лазер/плазму), с угловыми
        разделительными прорезями
      - габарит развёртки (ширина/высота заготовки) - основные размеры
      - габарит ГОТОВОЙ детали после гибки (отдельной строкой в таблице)
      - все линии гиба: кромка, отступ, угол, направление
      - все вырезы: координаты центра от базовых кромок, размеры/диаметр
      - размер и расположение угловых релиз-прорезей
      - толщина металла, допуски
      - текстовое пояснение к детали
      - обязательная надпись, если деталь скрыта в собранном изделии
    """
    page_w, page_h = page_size

    # Отступы страницы ПОДОГНАНЫ под реальный ГОСТ-штамп: рамка листа отстоит
    # от края на 20мм слева (место под подшивку) и 5мм с других сторон -
    # это даёт ширину штампа ровно 185мм на листе А4 (210мм), как и положено.
    margin_left = 20 * mm
    margin_right = 5 * mm
    margin_top = 5 * mm
    margin_bottom = 5 * mm
    title_h = 55 * mm  # точная высота штампа по ГОСТ 2.104 форма 1

    # Блок технических данных под чертежом (таблица гибов/вырезов/пояснение).
    # Он занимает место, поэтому сам контур детали ужимается - зато на листе
    # есть ВСЁ, что нужно цеху, а не только габарит.
    # Высота блока данных считается ПОД СОДЕРЖИМОЕ, а не фиксированно:
    # таблица гибов теперь одноколоночная, и у детали с 4 гибами строк
    # больше. При фиксированных 58мм текст вылезал за границу блока и
    # налезал на штамп.
    _n_bends = len([b for b in part.bend_lines if b.direction != 'seam'])
    _n_cuts = len(part.cutouts)
    DATA_BLOCK_H = (34 * mm
                    + _n_bends * 3.8 * mm
                    + ((_n_cuts + 1) // 2) * 3.6 * mm
                    + (8 * mm if part.corner_relief else 0)
                    + (9 * mm if part.description else 0))
    DATA_BLOCK_H = max(46 * mm, min(DATA_BLOCK_H, 105 * mm))

    DIM_SPACE_LEFT = 18 * mm
    DIM_SPACE_BOTTOM = 14 * mm
    AIR_GAP_RIGHT = 42 * mm     # запас справа под выноски к вырезам/гибам
    AIR_GAP_TOP = 10 * mm

    # Начало чертежа (левый нижний угол контура)
    x0 = margin_left + DIM_SPACE_LEFT
    y0 = margin_bottom + title_h + DATA_BLOCK_H + DIM_SPACE_BOTTOM

    draw_area_w = (page_w - margin_right - AIR_GAP_RIGHT) - x0
    draw_area_h = (page_h - margin_top - AIR_GAP_TOP) - y0

    scale = min(draw_area_w / part.width, draw_area_h / part.height, 1.0)
    if part.width * scale < 40 * mm and part.height * scale < 40 * mm:
        scale = min(draw_area_w / part.width, draw_area_h / part.height)

    draw_w = part.width * scale
    draw_h = part.height * scale

    # Защита: контур физически не может выйти за пределы листа
    assert x0 + draw_w <= page_w - margin_right - AIR_GAP_RIGHT + 0.1, "контур впритык к правому краю (нет зазора)"
    assert y0 + draw_h <= page_h - margin_top - AIR_GAP_TOP + 0.1, "контур впритык к верху (нет зазора)"

    # --- Заголовок: это РАЗВЁРТКА, а не готовая деталь ---
    c.setFont(FONT_NAME, 9)
    c.setFillColorRGB(0, 0, 0)
    header = "Развёртка (плоская заготовка под резку)" if part.is_bent else "Плоская деталь (гибка не требуется)"
    c.drawString(margin_left + 2 * mm, page_h - margin_top - 6 * mm, header)

    # --- Контур детали (с угловыми прорезями, если есть) ---
    corners = get_corners_needing_relief(part)
    notch = part.corner_relief * scale if corners else 0
    if corners:
        pts = build_outline_points(x0, y0, draw_w, draw_h, corners, notch)
    else:
        pts = [(x0, y0), (x0 + draw_w, y0), (x0 + draw_w, y0 + draw_h), (x0, y0 + draw_h), (x0, y0)]

    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0, 0, 0)
    path = c.beginPath()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    c.drawPath(path, fill=0, stroke=1)

    # --- Линии гиба (пунктир) + подпись угла прямо у линии ---
    c.setDash(2, 2)
    for bend in part.bend_lines:
        if bend.direction == 'seam':
            continue
        c.setStrokeColorRGB(0.2, 0.4, 0.7)
        off = bend.offset * scale
        if bend.edge == 'left':
            bx = x0 + off
            c.line(bx, y0, bx, y0 + draw_h)
            lx, ly = bx, y0 + draw_h * 0.72
        elif bend.edge == 'right':
            bx = x0 + draw_w - off
            c.line(bx, y0, bx, y0 + draw_h)
            lx, ly = bx, y0 + draw_h * 0.72
        elif bend.edge == 'top':
            by = y0 + draw_h - off
            c.line(x0, by, x0 + draw_w, by)
            lx, ly = x0 + draw_w * 0.72, by
        else:
            by = y0 + off
            c.line(x0, by, x0 + draw_w, by)
            lx, ly = x0 + draw_w * 0.72, by
        c.setDash()
        c.setFillColorRGB(0.2, 0.4, 0.7)
        c.setFont(FONT_NAME, 6)
        # Раньше писали "R20 90°". Завод читал R как РАДИУС ГИБА - а это
        # ОТСТУП ЛИНИИ ГИБА ОТ КРОМКИ. Пишем словом, без двусмысленности.
        arrow = "вниз" if bend.direction == "down" else "вверх"
        # Подпись у линии держим КОРОТКОЙ: на детали с 4 гибами длинные
        # подписи налезали друг на друга. Подробности - в таблице внизу.
        c.drawString(lx + 1 * mm, ly + 1 * mm,
                     f"гиб {bend.offset:g} ({bend.angle:.0f}°)")
        c.setDash(2, 2)
    c.setDash()
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)

    # --- Вырезы + выноски с координатами ---
    leader_x = x0 + draw_w + 6 * mm
    # Легенда линий занимает правый верхний угол листа. Выноски начинаем
    # НИЖЕ неё, иначе текст выноски налезает на текст легенды (поймано
    # автотестом на пересечение строк).
    legend_bottom = page_h - margin_top - 8 * mm - (5 * mm + 3 * 4.2 * mm)
    leader_top = min(y0 + draw_h, legend_bottom - 4 * mm)
    for i, cutout in enumerate(part.cutouts):
        cx = x0 + cutout.x * scale
        cy = y0 + cutout.y * scale
        c.setStrokeColorRGB(0.7, 0, 0.5)
        if cutout.shape == 'rect':
            hw, hh = cutout.width * scale / 2, cutout.height * scale / 2
            c.rect(cx - hw, cy - hh, hw * 2, hh * 2, fill=0, stroke=1)
            # осевые линии выреза (база для замера)
            c.setDash(1, 2)
            c.setLineWidth(0.25)
            c.line(cx - hw - 2 * mm, cy, cx + hw + 2 * mm, cy)
            c.line(cx, cy - hh - 2 * mm, cx, cy + hh + 2 * mm)
            c.setDash()
            label = f"Выр.{i+1}: {cutout.width:g}x{cutout.height:g}"
            edge_pt = (cx + hw, cy + hh)
        else:
            r = cutout.radius * scale
            c.circle(cx, cy, r, fill=0, stroke=1)
            c.setDash(1, 2)
            c.setLineWidth(0.25)
            c.line(cx - r - 2 * mm, cy, cx + r + 2 * mm, cy)
            c.line(cx, cy - r - 2 * mm, cx, cy + r + 2 * mm)
            c.setDash()
            label = f"Выр.{i+1}: ⌀{cutout.radius*2:g}"
            edge_pt = (cx + r * 0.7, cy + r * 0.7)
        c.setStrokeColorRGB(0, 0, 0)
        # Выноски рисуем только для первых 6 вырезов - иначе на детали с 6+
        # вент. отверстиями лист превращается в кашу. Полные координаты ВСЕХ
        # вырезов всё равно есть в таблице ниже, так что данные не теряются.
        if i < 6:
            ly = leader_top - (i + 1) * 5.5 * mm
            _draw_leader(c, edge_pt[0], edge_pt[1], leader_x, ly, label)

    # --- Угловая релиз-прорезь: выноска с размером ---
    if corners:
        # Выноску ведём от БЛИЖАЙШЕГО К ТЕКСТУ угла (текст всегда справа).
        # Раньше брали corners[0] = 'bottom-left', а текст рисуется справа
        # вверху - выноска прочерчивала ДИАГОНАЛЬ ЧЕРЕЗ ВСЮ ДЕТАЛЬ, и цех
        # принимал её за линию реза. Берём правый верхний угол, если он есть.
        corner = next((k for k in ("top-right", "bottom-right",
                                   "top-left", "bottom-left") if k in corners),
                      corners[0])
        px = x0 + (notch if 'left' in corner else draw_w - notch)
        py = y0 + (notch if 'bottom' in corner else draw_h - notch)
        ly = leader_top - (min(len(part.cutouts), 6) + 1) * 5.5 * mm
        _draw_leader(c, px, py, leader_x, ly,
                     f"Релиз-прорезь {part.corner_relief:g}x{part.corner_relief:g} "
                     f"({len(corners)} угл.)")

    # --- Габаритные размеры РАЗВЁРТКИ ---
    draw_horizontal_dimension(c, x0, x0 + draw_w, y0, 9 * mm, f"{int(part.width)}")
    draw_vertical_dimension(c, y0, y0 + draw_h, x0, 9 * mm, f"{int(part.height)}")

    # ------------------------------------------------------------------
    # ЛЕГЕНДА ЛИНИЙ (правый верхний угол)
    # ------------------------------------------------------------------
    # Завод спросил: "пунктирная линия что показывает?" - и был прав:
    # пунктир на листе есть, а расшифровки не было. Цех не должен гадать,
    # что резать, а что гнуть: ошибка здесь = запоротая деталь.
    _draw_line_legend(c, page_w - margin_right - 52 * mm,
                      page_h - margin_top - 8 * mm,
                      has_bends=bool([b for b in part.bend_lines
                                      if b.direction != 'seam']),
                      has_cutouts=bool(part.cutouts))

    # ------------------------------------------------------------------
    # БЛОК ТЕХНИЧЕСКИХ ДАННЫХ (под чертежом, над штампом)
    # ------------------------------------------------------------------
    bx0 = margin_left
    bx1 = page_w - margin_right
    by_top = margin_bottom + title_h + DATA_BLOCK_H
    y = by_top

    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(bx0, y, bx1, y)

    y -= 5 * mm
    c.setFont(FONT_NAME, 7.5)
    c.setFillColorRGB(0, 0, 0)

    # Строка 1: размеры (развёртка / готовая деталь) + материал + допуск
    c.drawString(bx0 + 2 * mm, y,
                 f"Развёртка (заготовка): {int(part.flat_width)} x {int(part.flat_height)} мм")
    c.drawString(bx0 + 78 * mm, y,
                 f"Готовая деталь: {int(part.formed_width)} x {int(part.formed_height)} мм")
    c.drawString(bx0 + 148 * mm, y, f"S = {part.thickness} мм")
    y -= 4.5 * mm
    c.drawString(bx0 + 2 * mm, y,
                 "Допуск на линейные размеры ±0,5 мм; на отверстия под крепёж H12; "
                 "кромки без заусенцев")

    # Строка: направление проката (нерж. лист имеет направление шлифовки)
    y -= 4.5 * mm
    c.drawString(bx0 + 2 * mm, y,
                 "Направление шлифовки/волокна — вдоль длинной стороны заготовки "
                 "(если сталь шлифованная)")

    # --- Таблица гибов ---
    y -= 6 * mm
    bends = [b for b in part.bend_lines if b.direction != 'seam']
    seams = [b for b in part.bend_lines if b.direction == 'seam']

    if bends:
        c.setFont(FONT_NAME, 7)
        # Явно говорим, ОТ ЧЕГО отступ и что значит направление - завод
        # не должен додумывать.
        c.drawString(bx0 + 2 * mm, y,
                     "ГИБЫ (линия гиба — от кромки ЗАГОТОВКИ; борт после "
                     "гибки больше на вычет 2.2 мм):")
        # ОДНА колонка, не две. Раньше строки раскладывались в 2 колонки по
        # 88мм, но после уточнения формулировок строка выросла до ~95 знаков
        # и в колонку не влезала - соседние строки НАЛЕЗАЛИ ДРУГ НА ДРУГА,
        # таблицу нельзя было прочитать. Ширины листа хватает на одну
        # колонку с запасом, поэтому просто идём построчно.
        c.setFont(FONT_NAME, 6.5)
        yy = y - 3.8 * mm          # сдвиг от заголовка (раньше его не было,
                                   # и первая строка налезала на слово "ГИБЫ")
        for i, b in enumerate(bends):
            nom = (f", борт после гибки {b.nominal:g} мм"
                   if getattr(b, "nominal", 0) else "")
            c.drawString(bx0 + 4 * mm, yy,
                         f"{i+1}) кромка {EDGE_RU.get(b.edge, b.edge)}: "
                         f"линия гиба {b.offset:g} мм от кромки{nom}, "
                         f"угол {b.angle:.0f}°, отгиб "
                         f"{'вниз' if b.direction == 'down' else 'вверх'}"
                         + (f" — {b.note}" if b.note else ""))
            yy -= 3.8 * mm
        y = yy - 1.5 * mm
    if seams:
        c.setFont(FONT_NAME, 6.5)
        c.drawString(bx0 + 2 * mm, y, f"ШВЫ (сварка, не гнуть): {len(seams)} шт.")
        y -= 4 * mm

    # --- Таблица вырезов (координаты от левой нижней базовой кромки) ---
    if part.cutouts:
        c.setFont(FONT_NAME, 7)
        c.drawString(bx0 + 2 * mm, y, "ВЫРЕЗЫ (координаты центра от левой нижней кромки):")
        c.setFont(FONT_NAME, 6.5)
        yy = y
        for i, ct in enumerate(part.cutouts):
            col = i % 2
            if col == 0:
                yy -= 3.6 * mm
            xoff = 4 * mm + col * 88 * mm
            if ct.shape == 'rect':
                spec = f"{ct.width:g}x{ct.height:g} мм"
            else:
                spec = f"⌀{ct.radius*2:g} мм"
            c.drawString(bx0 + xoff, yy,
                         f"{i+1}) X={ct.x:g}  Y={ct.y:g}  {spec}"
                         + (f"  {ct.label}" if ct.label else ""))
        y = yy - 4.5 * mm

    # --- Угловые релиз-прорези ---
    if corners:
        c.setFont(FONT_NAME, 6.5)
        c.drawString(bx0 + 2 * mm, y,
                     f"УГЛОВЫЕ РЕЛИЗ-ПРОРЕЗИ: {part.corner_relief:g}x{part.corner_relief:g} мм "
                     f"в углах: {', '.join(corners)} — режутся вместе с контуром, "
                     f"разделяют смежные борта")
        y -= 4.5 * mm

    # --- Пояснение к детали ---
    if part.description:
        c.setFont(FONT_NAME, 7)
        c.drawString(bx0 + 2 * mm, y, "НАЗНАЧЕНИЕ:")
        c.setFont(FONT_NAME, 6.5)
        for line in _wrap(part.description, 145)[:2]:
            y -= 3.6 * mm
            c.drawString(bx0 + 4 * mm, y, line)
        y -= 4 * mm

    # --- Обязательная надпись о скрытости ---
    if part.is_hidden_in_assembly:
        c.setFont(FONT_NAME, 8)
        c.setFillColorRGB(0, 0, 0)
        notice_y = margin_bottom + title_h + 3 * mm
        c.setLineWidth(0.7)
        c.rect(bx0 + 2 * mm, notice_y - 1.5 * mm,
               bx1 - bx0 - 4 * mm, 6.5 * mm, fill=0, stroke=1)
        c.drawCentredString((bx0 + bx1) / 2, notice_y + 1 * mm, HIDDEN_NOTICE.upper())

    # --- Внешняя рамка листа (тоже часть ГОСТ-оформления) ---
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    # --- Штамп (правый нижний угол, точная сетка ГОСТ 2.104) ---
    stamp_x0 = page_w - margin_right - 185 * mm
    draw_title_block(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": part.name,
        "mass": f"{mass_kg:.2f}",
        "scale": f"1:{max(1, round(1/scale))}" if scale < 1 else "1:1",
        "qty": quantity,
        "material": f"сталь S={part.thickness}мм",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })


class TechnicalDrawingExporter:
    """
    Генерация комплекта конструкторской документации.

    ------------------------------------------------------------------
    СТРУКТУРА ДОКУМЕНТА (главное изменение)
    ------------------------------------------------------------------
    Раньше страницы выпускались двумя валами: сначала ВСЕ сборочные виды
    всех модулей, потом ВСЕ чертежи деталей всех модулей подряд, одним
    сплошным потоком из плоского списка module.parts. Из-за этого детали
    разных сборочных единиц перемежались, и по листу в середине документа
    было невозможно понять, к какому узлу он относится.

    Теперь документ строится РЕКУРСИВНО по дереву сборки (AssemblyNode),
    строго depth-first: render_assembly_section(node) полностью закрывает
    текущий узел - его разделитель, сборочные виды, ведомость, ВСЕ его
    подсборки (рекурсивно) и только затем ВСЕ его собственные детали -
    прежде чем начнётся следующий узел того же уровня.

    Порядок для комплекса из 2 секций:

        1  Общий вид комплекса (в сборе)
        2  Общий вид комплекса (разнесённые секции)
        3  Габаритный чертёж комплекса
        4  Спецификация комплекса
        --- РАЗДЕЛ 1 -------------------------------
        5  Разделитель: "Секция с ящиками"
        6  Разнесённый вид секции
        7  Сборочный чертёж секции
        8  Ведомость секции
        9..N  Чертежи деталей ТОЛЬКО этой секции
        --- РАЗДЕЛ 2 -------------------------------
        N+1  Разделитель: "Секция под мойку"
        ...  и так далее, ни одна деталь чужого узла сюда не попадёт
        --- ИТОГ -----------------------------------
        Сводная ведомость всех деталей комплекса (для раскроя/закупки)
    """

    @staticmethod
    def export(module, company_name="НПО «Кристалл»", code_prefix="К"):
        """
        Args:
            module: Module (одиночный модуль) или KitchenProject (комплекс)
            company_name: название компании для штампа
            code_prefix: префикс обозначения по ГОСТ (К -> К 01.02.00.005)

        Returns:
            путь к созданному PDF
        """
        _register_font()
        Config.init_dirs()
        version = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time()*1000) % 1000:03d}"
        filename = os.path.join(Config.REPORTS_DIR, f"chertezhi_{version}.pdf")

        root = build_assembly_tree(module)
        is_project = root.node_type == "complex"

        ctx = _RenderContext(
            canvas=pdfcanvas.Canvas(filename, pagesize=A4),
            company_name=company_name,
            code_prefix=code_prefix,
            total_pages=_count_pages(root, is_project),
        )

        if is_project:
            _render_complex_overview(ctx, root)
            for i, section in enumerate(root.children, 1):
                render_assembly_section(section, ctx, level=1, section_label=f"РАЗДЕЛ {i}")
            _render_summary_bom(ctx, root)
        else:
            # Одиночный модуль: раздел 1 "общий вид комплекса" не выпускается,
            # корнем документа становится сам модуль (требование: экспорт по
            # одному модулю отдельно, без обёртки уровня комплекса).
            render_assembly_section(root, ctx, level=0, section_label=None)

        ctx.canvas.save()
        return filename

    @staticmethod
    def export_module(module, company_name="НПО «Кристалл»", code_prefix="К"):
        """Явная точка входа "экспорт одного модуля" (алиас export для читаемости в UI)"""
        return TechnicalDrawingExporter.export(module, company_name, code_prefix)


class _RenderContext:
    """Общее состояние отрисовки: холст, счётчик страниц, реквизиты штампа"""

    def __init__(self, canvas, company_name, code_prefix, total_pages):
        self.c = canvas
        self.canvas = canvas
        self.company_name = company_name
        self.code_prefix = code_prefix
        self.total_pages = total_pages
        self.page_num = 0

    def next_page(self):
        self.page_num += 1
        return self.page_num

    def finish_page(self):
        self.c.showPage()


# --------------------------------------------------------------------------
# Подсчёт страниц заранее (нужен для графы "Листов" в штампе на КАЖДОМ листе:
# нельзя написать "лист 3 из ?", число должно быть известно до отрисовки)
# --------------------------------------------------------------------------

def _count_node_pages(node, level):
    """Сколько страниц займёт узел вместе со всеми подсборками и деталями"""
    n = 0
    if level > 0:
        n += 1                                  # разделитель раздела
    if node.is_cabinet_like():
        n += 3                                  # разнесённый вид + сборочный + ведомость
    else:
        n += 1                                  # только ведомость
    for child in node.children:
        n += _count_node_pages(child, level + 1)
    n += len(node.grouped_parts())
    n += len(node.grouped_tubes())
    return n


def _count_pages(root, is_project):
    if not is_project:
        return _count_node_pages(root, level=0)
    n = 4                                        # общий вид (сборка+разнос) + габарит + спец
    for section in root.children:
        n += _count_node_pages(section, level=1)
    n += 1                                       # сводная ведомость
    return n


# --------------------------------------------------------------------------
# Раздел 1: ОБЩИЙ ВИД КОМПЛЕКСА
# --------------------------------------------------------------------------

def _render_complex_overview(ctx, root):
    """
    1.1 общий вид в сборе, 1.2 вид с разнесёнными секциями (видно каркас),
    1.3 габаритный чертёж комплекса, 1.4 спецификация комплекса.
    """
    project = root.source
    blocks = build_project_scene(project, exploded=False)

    # 1.1 Общий вид в сборе
    page = ctx.next_page()
    draw_project_scene_page(
        ctx.c, blocks, A4, f"{root.name} — общий вид (в сборе)",
        ctx.company_name, root.code(ctx.code_prefix),
        sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
        font_name=FONT_NAME, title_block_fn=draw_title_block,
        show_positions=False, show_legend=False,
    )
    ctx.finish_page()

    # 1.2 Разнесённый вид секций (второй ракурс - видно скрытые элементы каркаса)
    page = ctx.next_page()
    blocks_exploded = build_project_scene(project, exploded=True)
    draw_project_scene_page(
        ctx.c, blocks_exploded, A4, f"{root.name} — разнесённый вид секций",
        ctx.company_name, root.code(ctx.code_prefix),
        sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
        font_name=FONT_NAME, title_block_fn=draw_title_block,
        show_positions=True, show_legend=True,
    )
    ctx.finish_page()

    # 1.3 Габаритный чертёж комплекса (длина/глубина/высота + разбивка по секциям)
    page = ctx.next_page()
    _draw_complex_outline_page(
        ctx.c, root, A4, f"{root.name} — габаритный чертёж",
        ctx.company_name, root.code(ctx.code_prefix),
        sheet_num=page, sheets_total=ctx.total_pages,
    )
    ctx.finish_page()

    # 1.4 Спецификация комплекса (список секций верхнего уровня)
    page = ctx.next_page()
    draw_project_spec_page(
        ctx.c, blocks, A4, f"{root.name} — спецификация комплекса",
        ctx.company_name, root.code(ctx.code_prefix),
        sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
        font_name=FONT_NAME, title_block_fn=draw_title_block,
        code_prefix=ctx.code_prefix,
    )
    ctx.finish_page()


def _draw_complex_outline_page(c, root, page_size, title, company_name, code,
                                sheet_num, sheets_total):
    """
    Габаритный чертёж комплекса: вид спереди, ряд секций в масштабе, с общей
    длиной, высотой, глубиной и разбивкой по каждой секции (какая секция
    какой ширины и где начинается) - чтобы монтажник понимал, что куда встаёт.
    """
    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    project = root.source
    modules = project.modules
    placements = getattr(project, "placements", None) or [None] * len(modules)

    # Габариты комплекса в мм (по фактическим позициям модулей)
    xs = []
    for m, pl in zip(modules, placements):
        x = getattr(pl, "x", 0) if pl is not None else 0
        xs.append((x, x + m.width))
    total_w = max(x2 for _, x2 in xs) - min(x1 for x1, _ in xs) if xs else 0
    x_origin = min(x1 for x1, _ in xs) if xs else 0
    total_h = max((m.height for m in modules), default=0)
    total_d = max((m.depth for m in modules), default=0)

    if total_w <= 0 or total_h <= 0:
        total_w = max(total_w, 1)
        total_h = max(total_h, 1)

    # Область под чертёж
    x0 = margin_left + 22 * mm
    y0 = margin_bottom + title_h + 34 * mm
    area_w = (page_w - margin_right - 12 * mm) - x0
    area_h = (page_h - margin_top - 22 * mm) - y0
    scale = min(area_w / total_w, area_h / total_h)

    c.setFont(FONT_NAME, 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left + 2 * mm, page_h - margin_top - 8 * mm, title)
    c.setFont(FONT_NAME, 8)
    c.drawString(margin_left + 2 * mm, page_h - margin_top - 14 * mm,
                 "Вид спереди. Размеры даны по наружным граням секций.")

    # --- Секции ---
    for i, (m, (mx1, mx2)) in enumerate(zip(modules, xs), 1):
        sx = x0 + (mx1 - x_origin) * scale
        sw = (mx2 - mx1) * scale
        sh = m.height * scale
        c.setLineWidth(0.7)
        c.setStrokeColorRGB(0, 0, 0)
        c.rect(sx, y0, sw, sh, fill=0, stroke=1)

        # номер позиции секции в кружке
        c.setFont(FONT_NAME, 8)
        cx_, cy_ = sx + sw / 2, y0 + sh / 2
        c.circle(cx_, cy_ + 6 * mm, 3.2 * mm, fill=0, stroke=1)
        c.drawCentredString(cx_, cy_ + 4.9 * mm, str(i))

        name = m.name if len(m.name) <= 22 else m.name[:20] + "…"
        c.setFont(FONT_NAME, 6.5)
        c.drawCentredString(cx_, cy_ - 2 * mm, name)
        c.drawCentredString(cx_, cy_ - 6 * mm, f"{m.width}x{m.depth}x{m.height}")

        # размер ширины каждой секции (разбивка)
        draw_horizontal_dimension(c, sx, sx + sw, y0, 9 * mm, f"{int(m.width)}")

    # --- Общие габариты ---
    draw_horizontal_dimension(c, x0, x0 + total_w * scale, y0, 22 * mm, f"{int(total_w)}")
    draw_vertical_dimension(c, y0, y0 + total_h * scale, x0, 10 * mm, f"{int(total_h)}")

    c.setFont(FONT_NAME, 8)
    c.drawString(x0, y0 + total_h * scale + 8 * mm, f"Глубина комплекса: {int(total_d)} мм")

    c.setLineWidth(1.0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    stamp_x0 = page_w - margin_right - 185 * mm
    draw_title_block(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": f"{root.name} — габаритный чертёж",
        "mass": f"{getattr(project, 'weight', 0):.1f}",
        "scale": f"1:{max(1, round(1/scale))}" if scale < 1 else "1:1",
        "qty": 1,
        "material": "сборочная единица",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": "A4",
    })


# --------------------------------------------------------------------------
# РЕКУРСИВНЫЙ РЕНДЕР УЗЛА - сердце новой структуры
# --------------------------------------------------------------------------

def render_assembly_section(node, ctx, level=1, section_label=None):
    """
    Полностью отрисовать раздел одной сборочной единицы и НЕ ВЫЙТИ из него,
    пока не закрыт весь узел. Порядок строго по требованию:

      1. разделитель раздела (крупный заголовок - явная граница узла)
      2. сборочный(е) чертёж(и) - изометрия + разнесённый вид
      3. ведомость (спецификация) узла
      4. РЕКУРСИЯ: то же самое для каждой подсборки, целиком
      5. и только теперь - чертежи листовых деталей ЭТОГО узла

    Пункт 5 идёт последним намеренно: пока не закрыты все подсборки, детали
    родителя не начинаются - иначе снова получится перемешивание.
    """
    c = ctx.c
    code = node.code(ctx.code_prefix)

    # --- 1. Разделитель раздела ---
    if section_label:
        page = ctx.next_page()
        draw_section_divider(
            c, node, A4, ctx.company_name, code,
            sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
            font_name=FONT_NAME, title_block_fn=draw_title_block,
            section_label=section_label,
        )
        ctx.finish_page()

    target = node.source

    # --- 2. Сборочные чертежи узла (если геометрия это позволяет) ---
    if node.is_cabinet_like():
        # Сцену строим ИЗ НАСТОЯЩИХ ДЕТАЛЕЙ модуля (module_scene), а не
        # синтезируем коробки из габаритов. Иначе на виде нет реальных
        # деталей (направляющих, накладок), а есть выдуманные - и всё
        # лежит в одной плоскости, наложенное друг на друга.
        from core.module_scene import build_module_scene
        try:
            plates, rods = build_module_scene(target, gap=210)
        except Exception:
            shelf_count = sum(p.quantity for p in node.parts if p.name.startswith("Полка"))
            door_count = sum(p.quantity for p in node.parts if p.name.startswith("Дверь"))
            plates, rods = build_cabinet_scene(
                target.height, target.width, target.depth,
                shelf_count=shelf_count, door_count=door_count,
                has_tubes=bool(node.tubes),
            )

        page = ctx.next_page()
        draw_exploded_view(
            c, plates, rods, A4, f"{node.name} — разнесённый вид",
            ctx.company_name, code,
            sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
            font_name=FONT_NAME, title_block_fn=draw_title_block,
        )
        ctx.finish_page()

        page = ctx.next_page()
        draw_assembly_views(
            c, target, A4, f"{node.name} — сборочный чертёж",
            ctx.company_name, code,
            sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
            font_name=FONT_NAME, title_block_fn=draw_title_block,
            dim_h_fn=draw_horizontal_dimension, dim_v_fn=draw_vertical_dimension,
        )
        ctx.finish_page()

        # --- 3. Ведомость узла ---
        page = ctx.next_page()
        draw_spec_page(
            c, target, A4, f"{node.name} — спецификация",
            ctx.company_name, code,
            sheet_num=page, sheets_total=ctx.total_pages, paper_format="A4",
            font_name=FONT_NAME, title_block_fn=draw_title_block,
            code_prefix=ctx.code_prefix,
        )
        ctx.finish_page()
    else:
        # Узел без "шкафной" геометрии (столешница, фартук) - изометрии нет,
        # но ведомость должна быть в любом случае: раздел не может состоять
        # из одних чертежей деталей без списка состава.
        page = ctx.next_page()
        _draw_flat_node_spec(ctx, node, page)
        ctx.finish_page()

    # --- 4. РЕКУРСИЯ по подсборкам (каждая закрывается ЦЕЛИКОМ) ---
    for i, child in enumerate(node.children, 1):
        child_label = f"{section_label}.{i}" if section_label else f"РАЗДЕЛ {i}"
        render_assembly_section(child, ctx, level=level + 1, section_label=child_label)

    # --- 5. Чертежи листовых деталей ТОЛЬКО этого узла ---
    from core.rules import Rules

    for idx, data in enumerate(node.grouped_parts(), 1):
        part = data["part"]
        qty = data["qty"]
        mass = part.area * qty * Rules.STEEL_DENSITY * part.thickness
        page = ctx.next_page()
        draw_part_page(
            c, part, A4, node.part_code(idx, ctx.code_prefix), qty, mass,
            ctx.company_name, sheet_num=page, sheets_total=ctx.total_pages,
            paper_format="A4",
        )
        ctx.finish_page()

    # --- 5b. Чертежи труб каркаса этого узла ---
    tube_index = len(node.grouped_parts())
    for data in node.grouped_tubes():
        tube = data["tube"]
        qty = data["qty"]
        tube_index += 1
        # Масса по точной площади сечения металла (наружная минус внутренняя
        # полость), не по приближению через периметр.
        outer = tube.profile_w * tube.profile_h
        inner_w = max(tube.profile_w - 2 * tube.wall, 0)
        inner_h = max(tube.profile_h - 2 * tube.wall, 0)
        metal_area = outer - inner_w * inner_h
        volume_m3 = (metal_area * tube.length) / 1e9
        mass = volume_m3 * Rules.STEEL_DENSITY * 1000 * qty

        page = ctx.next_page()
        draw_tube_page(
            c, tube, A4, node.part_code(tube_index, ctx.code_prefix), qty, mass,
            ctx.company_name, sheet_num=page, sheets_total=ctx.total_pages,
            paper_format="A4",
        )
        ctx.finish_page()


def _draw_flat_node_spec(ctx, node, page):
    """Ведомость для узла без изометрии (столешница и т.п.)"""
    c = ctx.c
    page_w, page_h = A4
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    title = f"{node.name} — спецификация"
    c.setFont(FONT_NAME, 13)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left, page_h - margin_top - 8 * mm, title)

    table_x0 = margin_left
    table_w = page_w - margin_left - margin_right
    col_widths = [16 * mm, 36 * mm, table_w - 16 * mm - 36 * mm - 18 * mm - 44 * mm,
                  18 * mm, 44 * mm]
    headers = ["Поз.", "Обозначение", "Наименование", "Кол.", "Примечание"]
    row_h = 7 * mm
    y = page_h - margin_top - 18 * mm

    def draw_row(y, values, header=False):
        x = table_x0
        c.setLineWidth(0.4)
        for i, (w, val) in enumerate(zip(col_widths, values)):
            c.rect(x, y - row_h, w, row_h, fill=0, stroke=1)
            c.setFont(FONT_NAME, 8 if header else 7.5)
            if i in (0, 3):
                c.drawCentredString(x + w / 2, y - row_h + 2 * mm, str(val))
            else:
                c.drawString(x + 2 * mm, y - row_h + 2 * mm, str(val))
            x += w
        return y - row_h

    y = draw_row(y, headers, header=True)
    for idx, data in enumerate(node.grouped_parts(), 1):
        p = data["part"]
        note = "СКРЫТА в сборке" if p.is_hidden_in_assembly else "Лист НЕРЖ"
        y = draw_row(y, [idx, node.part_code(idx, ctx.code_prefix),
                         p.name, data["qty"], note])
        if y < margin_bottom + title_h + 12 * mm:
            break

    c.setLineWidth(1.0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    stamp_x0 = page_w - margin_right - 185 * mm
    draw_title_block(c, stamp_x0, margin_bottom, {
        "code": node.code(ctx.code_prefix),
        "name": title,
        "mass": "-",
        "scale": "б/м",
        "qty": 1,
        "material": "спецификация",
        "company": ctx.company_name,
        "sheet": page,
        "sheets_total": ctx.total_pages,
        "format": "A4",
    })


# --------------------------------------------------------------------------
# Раздел 4: СВОДНАЯ СПЕЦИФИКАЦИЯ (плоский список для раскроя/закупки)
# --------------------------------------------------------------------------

def _render_summary_bom(ctx, root):
    """
    Итоговая сводная спецификация по всему комплексу: плоский список всех
    деталей с указанием, к какому модулю каждая относится - именно в таком
    виде она уходит в раскрой и в закупку металла.
    """
    c = ctx.c
    page = ctx.next_page()
    page_w, page_h = A4
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    title = f"{root.name} — сводная спецификация деталей"
    c.setFont(FONT_NAME, 13)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left, page_h - margin_top - 8 * mm, title)
    c.setFont(FONT_NAME, 7.5)
    c.drawString(margin_left, page_h - margin_top - 13 * mm,
                 "Плоский список всех деталей комплекса — для передачи в раскрой и закупку металла. "
                 "Размеры даны по РАЗВЁРТКЕ (заготовке).")

    table_x0 = margin_left
    table_w = page_w - margin_left - margin_right
    col_widths = [26 * mm, 34 * mm, table_w - 26 * mm - 34 * mm - 26 * mm - 12 * mm - 22 * mm,
                  26 * mm, 12 * mm, 22 * mm]
    headers = ["Модуль", "Обозначение", "Наименование", "Развёртка, мм", "Кол.", "Масса, кг"]
    row_h = 6.2 * mm
    y = page_h - margin_top - 18 * mm

    def draw_row(y, values, header=False):
        x = table_x0
        c.setLineWidth(0.4)
        for i, (w, val) in enumerate(zip(col_widths, values)):
            c.rect(x, y - row_h, w, row_h, fill=0, stroke=1)
            c.setFont(FONT_NAME, 7 if header else 6.5)
            if i in (4,):
                c.drawCentredString(x + w / 2, y - row_h + 2 * mm, str(val))
            else:
                c.drawString(x + 1.5 * mm, y - row_h + 2 * mm, str(val))
            x += w
        return y - row_h

    y = draw_row(y, headers, header=True)

    from core.rules import Rules
    total_mass = 0.0
    total_qty = 0
    overflow = False

    for section in root.children:
        for node in section.walk():
            for idx, data in enumerate(node.grouped_parts(), 1):
                if y < margin_bottom + title_h + 16 * mm:
                    overflow = True
                    break
                p = data["part"]
                qty = data["qty"]
                mass = p.area * qty * Rules.STEEL_DENSITY * p.thickness
                total_mass += mass
                total_qty += qty
                mod_name = node.name if len(node.name) <= 18 else node.name[:16] + "…"
                pname = p.name + (" (скрыта)" if p.is_hidden_in_assembly else "")
                y = draw_row(y, [
                    mod_name,
                    node.part_code(idx, ctx.code_prefix),
                    pname,
                    f"{int(p.flat_width)}x{int(p.flat_height)}",
                    qty,
                    f"{mass:.2f}",
                ])
            if overflow:
                break
        if overflow:
            break

    y -= 6 * mm
    c.setFont(FONT_NAME, 8)
    c.drawString(table_x0, y, f"ИТОГО деталей: {total_qty} шт.   Масса листового металла: {total_mass:.2f} кг")
    if overflow:
        y -= 5 * mm
        c.setFont(FONT_NAME, 7)
        c.drawString(table_x0, y,
                     "Список не поместился на лист целиком — полную сводку см. в Excel-выгрузке.")

    c.setLineWidth(1.0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    stamp_x0 = page_w - margin_right - 185 * mm
    draw_title_block(c, stamp_x0, margin_bottom, {
        "code": root.code(ctx.code_prefix),
        "name": "Сводная спецификация",
        "mass": f"{total_mass:.1f}",
        "scale": "б/м",
        "qty": 1,
        "material": "ведомость раскроя",
        "company": ctx.company_name,
        "sheet": page,
        "sheets_total": ctx.total_pages,
        "format": "A4",
    })
    ctx.finish_page()