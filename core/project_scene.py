"""
Сцена всей кухни целиком (уровень "Комплекс" в документации) - собирает
3D-сцены всех модулей вместе, с учётом позиции (x,y) и угла поворота
каждого модуля (ModulePlacement), для построения:
  - общего вида кухни в сборе (титульная страница проекта)
  - общего вида с разъехавшимися друг от друга секциями (не отдельными
    панелями внутри модуля - это уже показано на странице каждого модуля
    отдельно, а именно целыми модулями/секциями)
  - ведомости "из каких секций состоит комплекс"

Здесь модуль/секция - это позиция верхнего уровня (как "Сборочные единицы"
в референсе), не отдельная деталь - поэтому у каждого МОДУЛЯ один номер
позиции, а не у каждой панели внутри него.
"""
import math
from core.exploded_view import build_cabinet_scene, get_panel_color, shade_color


def _rotate_xy(x, y, angle_deg):
    a = math.radians(angle_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


class ModuleBlock:
    """Один модуль в сцене всей кухни - его собственные панели+каркас,
    уже трансформированные в мировые координаты проекта, плюс номер позиции
    и название (как единая позиция в ведомости верхнего уровня)."""
    def __init__(self, pos_num, name, plates, rods, bbox):
        self.pos_num = pos_num
        self.name = name
        self.plates = plates
        self.rods = rods
        self.bbox = bbox  # (xmin,xmax,ymin,ymax,zmin,zmax) в мировых координатах

    def center_3d(self):
        xmin, xmax, ymin, ymax, zmin, zmax = self.bbox
        return ((xmin+xmax)/2, (ymin+ymax)/2, (zmin+zmax)/2)


def build_project_scene(project, gap_mm=250, exploded=False):
    """
    Собрать сцену всей кухни: список ModuleBlock, по одному на модуль
    проекта, с учётом его размещения (placement.x/y/angle).

    Args:
        project: KitchenProject
        gap_mm: доп. зазор между модулями при exploded=True (мм)
        exploded: раздвинуть модули друг от друга (True) или показать
                  как они реально стоят в сборе, встык (False)

    Returns:
        список ModuleBlock
    """
    blocks = []
    placements = getattr(project, 'placements', None) or [None] * len(project.modules)

    for i, (module, placement) in enumerate(zip(project.modules, placements)):
        if placement is None:
            placement = type('P', (), {'x': 0, 'y': 0, 'angle': 0})()

        # Для ОБЩЕГО вида комплекса каждый модуль — это ОДНА чистая коробка по
        # его габариту (Ш×Г×В), а не россыпь панелей внутри. Поэтому больше НЕ
        # фильтруем модули по типу деталей и НЕ строим полную сцену панелей:
        # раньше фартук и вытяжка отсеивались (нет «боковой» панели) и в общий
        # вид/спецификацию не попадали — комплекс выходил неполным.
        gap_x = i * gap_mm if exploded else 0
        w = module.width
        d = getattr(module, 'depth', 600) or 600
        h = getattr(module, 'height', 0) or 0
        ang = int(getattr(placement, 'angle', 0)) % 180
        if ang == 90:            # поворот на 90° меняет ширину и глубину местами
            w, d = d, w
        x0 = getattr(placement, 'x', 0) + gap_x
        y0 = getattr(placement, 'y', 0)
        bbox = (x0, x0 + w, y0, y0 + d, 0, max(h, 1))

        blocks.append(ModuleBlock(len(blocks) + 1, module.name, [], [], bbox))

    return blocks


def _bounding_box_all(blocks):
    xs, ys, zs = [], [], []
    for b in blocks:
        xmin, xmax, ymin, ymax, zmin, zmax = b.bbox
        xs += [xmin, xmax]; ys += [ymin, ymax]; zs += [zmin, zmax]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def draw_project_scene_page(c, blocks, page_size, title, company_name, code,
                             sheet_num, sheets_total, paper_format, font_name,
                             title_block_fn, show_positions=True, show_legend=True):
    """
    Нарисовать страницу со сценой всей кухни (изометрия) - либо в сборе
    (title-страница проекта), либо с разъехавшимися друг от друга модулями
    (show_positions=True добавляет номер+легенду по каждому модулю/секции).
    """
    from reportlab.lib.units import mm
    from core.exploded_view import iso_project

    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm
    legend_w = 55 * mm if show_legend else 0

    draw_x0 = margin_left
    draw_y0 = margin_bottom + title_h + 10 * mm
    draw_x1 = page_w - margin_right - legend_w
    draw_y1 = page_h - margin_top - 12 * mm

    x_min, x_max, y_min, y_max, z_min, z_max = _bounding_box_all(blocks)

    # находим 2D-габариты сцены В ПРОЕКЦИИ (не в 3D) для масштабирования —
    # по 8 углам коробки каждого модуля.
    xs2d, ys2d = [], []
    for b in blocks:
        bx0, bx1, by0, by1, bz0, bz1 = b.bbox
        for cxp in (bx0, bx1):
            for cyp in (by0, by1):
                for czp in (bz0, bz1):
                    sx, sy = iso_project(cxp, cyp, czp)
                    xs2d.append(sx); ys2d.append(sy)

    scene_w = max(xs2d) - min(xs2d)
    scene_h = max(ys2d) - min(ys2d)
    avail_w = draw_x1 - draw_x0
    avail_h = draw_y1 - draw_y0
    scale = min(avail_w / (scene_w * mm), avail_h / (scene_h * mm))

    cx = (min(xs2d) + max(xs2d)) / 2
    cy = (min(ys2d) + max(ys2d)) / 2
    origin_x = draw_x0 + avail_w / 2
    origin_y = draw_y0 + avail_h / 2

    def to_paper(x, y, z):
        sx, sy = iso_project(x, y, z)
        return origin_x + (sx - cx) * scale * mm, origin_y + (sy - cy) * scale * mm

    # --- Каждый модуль = ЧИСТАЯ изометрическая коробка (по своему габариту),
    #     а не куча полупрозрачных цветных панелей внутри. Три видимые грани
    #     заливаем градацией серого (сверху светлее, справа темнее) — это даёт
    #     аккуратный технический объём без цветовой каши. ---
    def _box_faces(bbox):
        x0, x1, y0, y1, z0, z1 = bbox
        return {
            'front': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            'right': [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            'top':   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        }
    FACE_SHADE = {'top': 0.97, 'front': 0.88, 'right': 0.78}

    # Painter's algorithm: дальние коробки рисуем первыми, ближние перекрывают.
    # Камера смотрит с (+x,-y,+z), поэтому «ближе» = больше (x - y).
    ordered = sorted(blocks, key=lambda b: (b.center_3d()[0] - b.center_3d()[1]))

    for b in ordered:
        faces = _box_faces(b.bbox)
        for fname in ('front', 'right', 'top'):
            pts2d = [to_paper(*pt) for pt in faces[fname]]
            path = c.beginPath()
            path.moveTo(*pts2d[0])
            for pt in pts2d[1:]:
                path.lineTo(*pt)
            path.close()
            g = FACE_SHADE[fname]
            c.setFillColorRGB(g, g, g)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.9)
            c.drawPath(path, fill=1, stroke=1)

    # --- Номера позиций: кружок НАД модулем + выноска к верхней грани ---
    if show_positions:
        c.setFont(font_name, 9)
        for b in blocks:
            x0, x1, y0, y1, z0, z1 = b.bbox
            tx, ty = to_paper((x0 + x1) / 2, y0, z1)   # верх-перед модуля
            nx, ny = tx, ty + 13 * mm
            c.setLineWidth(0.4)
            c.setStrokeColorRGB(0, 0, 0)
            c.line(tx, ty, nx, ny)
            c.setFillColorRGB(1, 1, 1)
            c.setLineWidth(0.7)
            c.circle(nx, ny, 4.5 * mm, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(nx, ny - 3, str(b.pos_num))

    # --- Габариты комплекса подписью (длина × глубина × высота) ---
    L = int(round(x_max - x_min))
    D = int(round(y_max - y_min))
    H = int(round(z_max - z_min))
    c.setFont(font_name, 8.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left + 3 * mm, page_h - margin_top - 14 * mm,
                 f"Габариты комплекса: длина {L} × глубина {D} × высота {H} мм")

    if show_legend:
        legend_x = page_w - margin_right - legend_w + 3 * mm
        legend_y = page_h - margin_top - 10 * mm
        c.setFont(font_name, 9)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(legend_x, legend_y, "Сборочные единицы:")
        legend_y -= 6 * mm
        for b in blocks:
            c.setFont(font_name, 7.5)
            c.drawString(legend_x, legend_y, f"{b.pos_num}")
            c.drawString(legend_x + 8 * mm, legend_y, b.name[:26])
            legend_y -= 4.5 * mm

    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    c.setFont(font_name, 11)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left + 3 * mm, page_h - margin_top - 8 * mm, title)

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