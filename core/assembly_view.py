"""
2D сборочный чертёж - три вида (спереди/сверху/сбоку) на весь собранный
модуль, с общими габаритами и номерами позиций - те же номера, что и на
странице разнесённого вида (build_cabinet_scene переиспользуется напрямую,
чтобы номера позиций совпадали по всему комплекту документации).

В отличие от разнесённого вида (изометрия, для наглядности "что куда
крепится"), здесь - плоские ортогональные проекции с проставленными
размерами, как в разделе "Сборочный чертёж" настоящей конструкторской
документации.

Важно про видимость: одна и та же деталь выглядит по-разному в разных
видах. Боковина видна СБОКУ целиком (сплошной прямоугольник), а СПЕРЕДИ -
только тонким ребром (вертикальная линия). Крыша/Дно видны СВЕРХУ целиком,
а СПЕРЕДИ/СБОКУ - только ребром (горизонтальная линия). Это не ошибка
проекции, а нормальная механика ортогональных видов - здесь она сделана
осознанно по типу детали, а не "в лоб" проекцией 3D-точек (это дало бы
неразличимые наложенные прямоугольники там, где деталь видна с ребра).
"""
from reportlab.lib.units import mm
from core.exploded_view import build_cabinet_scene


def _find_positions(plates, prefix):
    """Список (pos_num, label) деталей, чьё название начинается с prefix"""
    return [(p.pos_num, p.label) for p in plates if p.label.startswith(prefix)]


def _draw_pos_circle(c, x, y, pos_num, font_name, radius=3.0 * mm):
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.circle(x, y, radius, fill=1, stroke=1)
    c.setFont(font_name, 6.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(x, y - 2.1, str(pos_num))


def draw_assembly_views(c, module, page_size, title, company_name, code,
                         sheet_num, sheets_total, paper_format, font_name,
                         title_block_fn, dim_h_fn, dim_v_fn):
    """
    Нарисовать страницу с тремя видами (спереди/сверху/сбоку) собранного
    модуля + штамп. Номера позиций берутся из build_cabinet_scene - те же,
    что и на странице разнесённого вида этого же модуля.
    """
    W, D, H = module.width, module.depth, module.height

    shelf_count = sum(p.quantity for p in module.parts if p.name.startswith("Полка"))
    door_count = sum(p.quantity for p in module.parts if p.name.startswith("Дверь"))
    plates, rods = build_cabinet_scene(H, W, D, shelf_count=shelf_count,
                                        door_count=door_count, has_tubes=False)

    boковины = _find_positions(plates, "Боковина")
    dвери = _find_positions(plates, "Дверь")
    крыша = _find_positions(plates, "Крыша")
    дно = _find_positions(plates, "Дно")
    полки = [p for p in plates if p.label.startswith("Полка")]

    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    # Общая рабочая область над штампом, делим на 2 колонки x 2 ряда:
    # спереди (крупно, слева сверху), сверху (слева снизу), сбоку (справа)
    work_x0 = margin_left + 10 * mm
    work_y0 = margin_bottom + title_h + 15 * mm
    work_x1 = page_w - margin_right - 10 * mm
    work_y1 = page_h - margin_top - 12 * mm
    work_w = work_x1 - work_x0
    work_h = work_y1 - work_y0

    # Зоны: спереди+сверху делят левые 60% ширины (спереди сверху, сверху снизу),
    # сбоку - правые 35% ширины, на всю высоту
    col_split = work_x0 + work_w * 0.62
    front_zone = (work_x0, work_y0 + work_h * 0.42, col_split - work_x0, work_h * 0.58 - 15 * mm)
    top_zone = (work_x0, work_y0, col_split - work_x0, work_h * 0.42 - 5 * mm)
    side_zone = (col_split + 10 * mm, work_y0, work_x1 - col_split - 10 * mm, work_h - 5 * mm)

    def fit_scale(zone, w_mm, h_mm, air=8 * mm):
        zx, zy, zw, zh = zone
        return min((zw - air) / w_mm, (zh - air) / h_mm, 1.0)

    c.setFont(font_name, 9)

    # ============ ВИД СПЕРЕДИ ============
    zx, zy, zw, zh = front_zone
    scale = fit_scale(front_zone, W, H)
    dw, dh = W * scale, H * scale
    fx0 = zx + (zw - dw) / 2
    fy0 = zy + (zh - dh) / 2

    c.setLineWidth(0.8)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(fx0, fy0, dw, dh, fill=0, stroke=1)

    # разделительная линия дверей по центру (если 2 двери)
    if door_count == 2:
        c.setLineWidth(0.5)
        c.line(fx0 + dw / 2, fy0, fx0 + dw / 2, fy0 + dh)

    c.setFont(font_name, 8)
    c.drawString(zx, zy + zh + 3 * mm, "Вид спереди")

    dim_h_fn(c, fx0, fx0 + dw, fy0, 8 * mm, f"{int(W)}")
    dim_v_fn(c, fy0, fy0 + dh, fx0, 8 * mm, f"{int(H)}")

    # номера: боковины по краям, двери в центре половин
    if len(boковины) == 2:
        _draw_pos_circle(c, fx0 + 4 * mm, fy0 + dh / 2, boковины[0][0], font_name)
        _draw_pos_circle(c, fx0 + dw - 4 * mm, fy0 + dh / 2, boковины[1][0], font_name)
    if len(dвери) == 2:
        _draw_pos_circle(c, fx0 + dw * 0.25, fy0 + dh / 2, dвери[0][0], font_name)
        _draw_pos_circle(c, fx0 + dw * 0.75, fy0 + dh / 2, dвери[1][0], font_name)
    if крыша:
        _draw_pos_circle(c, fx0 + dw / 2, fy0 + dh + 4 * mm, крыша[0][0], font_name)
    if дно:
        _draw_pos_circle(c, fx0 + dw / 2, fy0 - 12 * mm, дно[0][0], font_name)

    # ============ ВИД СВЕРХУ ============
    zx, zy, zw, zh = top_zone
    scale2 = fit_scale(top_zone, W, D)
    dw2, dh2 = W * scale2, D * scale2
    tx0 = zx + (zw - dw2) / 2
    ty0 = zy + (zh - dh2) / 2

    c.setLineWidth(0.8)
    c.rect(tx0, ty0, dw2, dh2, fill=0, stroke=1)
    c.setFont(font_name, 8)
    c.drawString(zx, zy + zh + 3 * mm, "Вид сверху")
    dim_h_fn(c, tx0, tx0 + dw2, ty0, 8 * mm, f"{int(W)}")
    dim_v_fn(c, ty0, ty0 + dh2, tx0, 8 * mm, f"{int(D)}")
    if крыша:
        _draw_pos_circle(c, tx0 + dw2 / 2, ty0 + dh2 / 2, крыша[0][0], font_name)
    if len(boковины) == 2:
        _draw_pos_circle(c, tx0 + 4 * mm, ty0 + dh2 / 2, boковины[0][0], font_name)
        _draw_pos_circle(c, tx0 + dw2 - 4 * mm, ty0 + dh2 / 2, boковины[1][0], font_name)

    # ============ ВИД СБОКУ ============
    zx, zy, zw, zh = side_zone
    scale3 = fit_scale(side_zone, D, H)
    dw3, dh3 = D * scale3, H * scale3
    sx0 = zx + (zw - dw3) / 2
    sy0 = zy + (zh - dh3) / 2

    c.setLineWidth(0.8)
    c.rect(sx0, sy0, dw3, dh3, fill=0, stroke=1)
    c.setFont(font_name, 8)
    c.drawString(zx, zy + zh + 3 * mm, "Вид сбоку")
    dim_h_fn(c, sx0, sx0 + dw3, sy0, 8 * mm, f"{int(D)}")
    dim_v_fn(c, sy0, sy0 + dh3, sx0, 8 * mm, f"{int(H)}")

    # линии полок (видны сбоку как горизонтальные линии внутри контура,
    # штрихпунктир - деталь "скрыта" внутри корпуса, стандартное обозначение
    # невидимых линий в черчении)
    c.setDash(3, 2)
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    for shelf in полки:
        z_shelf = shelf.corners_3d[0][2]  # z-координата полки (все 4 угла на одной высоте)
        y_paper = sy0 + (z_shelf / H) * dh3
        c.line(sx0, y_paper, sx0 + dw3, y_paper)
        _draw_pos_circle(c, sx0 + dw3 + 6 * mm, y_paper, shelf.pos_num, font_name, radius=2.6 * mm)
    c.setDash()
    c.setStrokeColorRGB(0, 0, 0)

    if len(boковины) >= 1:
        _draw_pos_circle(c, sx0 + dw3 / 2, sy0 + dh3 / 2, boковины[0][0], font_name)
    if крыша:
        _draw_pos_circle(c, sx0 + dw3 / 2, sy0 + dh3 + 4 * mm, крыша[0][0], font_name)
    if дно:
        _draw_pos_circle(c, sx0 + dw3 / 2, sy0 - 12 * mm, дно[0][0], font_name)

    # --- Внешняя рамка листа ---
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    c.setFont(font_name, 11)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left + 3 * mm, page_h - margin_top - 8 * mm, title)

    # --- Штамп ---
    stamp_x0 = page_w - margin_right - 185 * mm
    title_block_fn(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": title,
        "mass": "-",
        "scale": "б/м",
        "qty": 1,
        "material": "сборка (см. спецификацию)",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })