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

        # столешница и подобные плоские модули (height=толщина, не настоящая
        # высота) - для сцены кухни целиком их пропускаем (они не шкафообразные,
        # добавлять их в общую 3D-сцену как "шкаф" было бы некорректно)
        # Настоящие детали мастера называются "Панель боковая"/"Боковая панель",
        # а не "Боковина". Старый фильтр их не узнавал -> ВСЕ модули комплекса
        # отсеивались, и сцена кухни выходила пустой (min() of empty sequence).
        SIDE_PREFIXES = ("Боковина", "Боковая", "Панель боковая")
        if not any(p.name.startswith(SIDE_PREFIXES) for p in module.parts):
            continue

        # Сцену строим ИЗ НАСТОЯЩИХ ДЕТАЛЕЙ модуля. Старый build_cabinet_scene
        # синтезировал коробки из габаритов и с реальными деталями связан не был.
        try:
            from core.module_scene import build_module_scene
            plates, rods = build_module_scene(module, gap=0)
        except Exception:
            shelf_count = sum(p.quantity for p in module.parts if p.name.startswith("Полка"))
            door_count = sum(p.quantity for p in module.parts if p.name.startswith("Дверь"))
            plates, rods = build_cabinet_scene(
                module.height, module.width, module.depth,
                shelf_count=shelf_count, door_count=door_count,
                has_tubes=bool(getattr(module, 'tubes', None))
            )

        if not plates and not rods:
            continue

        gap_x = i * gap_mm if exploded else 0

        def transform_point(pt):
            x, y, z = pt
            rx, ry = _rotate_xy(x, y, placement.angle)
            return (rx + placement.x + gap_x, ry + placement.y, z)

        # трансформируем углы каждой панели/трубы в мировые координаты
        # (используем ассемблированное положение, factor=0 - без внутреннего
        # разнесения деталей внутри модуля, т.к. это уже отдельная страница)
        world_plates = []
        for p in plates:
            world_corners = [transform_point(pt) for pt in p.corners_3d]
            new_p = type(p)(world_corners, p.pos_num, p.label, explode_dir=(0, 0, 0))
            world_plates.append(new_p)

        world_rods = []
        for r in rods:
            wp1 = transform_point(r.p1)
            wp2 = transform_point(r.p2)
            new_r = type(r)(wp1, wp2, r.pos_num, r.label, explode_dir=(0, 0, 0))
            world_rods.append(new_r)

        all_pts = [pt for p in world_plates for pt in p.corners_3d] + \
                   [pt for r in world_rods for pt in (r.p1, r.p2)]
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        zs = [p[2] for p in all_pts]
        bbox = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

        blocks.append(ModuleBlock(len(blocks) + 1, module.name, world_plates, world_rods, bbox))

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

    # находим 2D-габариты сцены В ПРОЕКЦИИ (не в 3D) для масштабирования
    xs2d, ys2d = [], []
    for b in blocks:
        for p in b.plates:
            for pt in p.corners_3d:
                sx, sy = iso_project(*pt)
                xs2d.append(sx); ys2d.append(sy)
        for r in b.rods:
            for pt in (r.p1, r.p2):
                sx, sy = iso_project(*pt)
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

    for b in blocks:
        # Соседние модули красим чуть по-разному (темнее/светлее), иначе
        # два одинаковых типа деталей (например боковины соседних шкафов)
        # сливаются в одно бесформенное пятно на общем виде кухни.
        brightness = 1.0 if b.pos_num % 2 == 1 else 0.82

        c.setLineWidth(1.2)
        c.setStrokeColorRGB(0.35, 0.35, 0.35)
        for r in b.rods:
            x1, y1 = to_paper(*r.p1)
            x2, y2 = to_paper(*r.p2)
            c.line(x1, y1, x2, y2)

        for p in b.plates:
            pts2d = [to_paper(*pt) for pt in p.corners_3d]
            path = c.beginPath()
            path.moveTo(*pts2d[0])
            for pt in pts2d[1:]:
                path.lineTo(*pt)
            path.close()
            color = shade_color(get_panel_color(p.label), brightness)
            c.setFillColorRGB(*color)
            try:
                c.setFillAlpha(0.88)  # лёгкая прозрачность - видно, где панели перекрываются
            except Exception:
                pass  # на случай если версия reportlab не поддерживает alpha
            c.setStrokeColorRGB(0.1, 0.1, 0.1)
            c.setLineWidth(0.6)
            c.drawPath(path, fill=1, stroke=1)
            try:
                c.setFillAlpha(1.0)
            except Exception:
                pass

        if show_positions:
            cx3, cy3, cz3 = b.center_3d()
            px, py = to_paper(cx3, cy3, cz3)
            c.setFillColorRGB(1, 1, 1)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.7)
            c.circle(px, py, 4.5 * mm, fill=1, stroke=1)
            c.setFont(font_name, 9)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(px, py - 3, str(b.pos_num))

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