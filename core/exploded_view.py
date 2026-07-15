"""
Разнесённый изометрический вид сборки (аналог "Разнесен" из референсного
комплекта чертежей) - показывает, как детали собираются в готовое изделие,
со стрелками-выносками "деталь №N крепится сюда".

У нас нет настоящей 3D-модели (в отличие от референса, где есть STEP-файл
из КОМПАС-3D) - здесь лёгкая изометрическая проекция плоских деталей
и трубного каркаса, этого достаточно для наглядной схемы сборки, но не
заменяет точную 3D CAD-модель.

Система координат: x = ширина (влево-вправо), y = глубина (перед-зад),
z = высота (низ-верх). Изометрия 30° - стандартный инженерный угол.
"""
import math

ISO_ANGLE = math.radians(30)


def iso_project(x, y, z):
    """3D точка -> 2D точка на бумаге (изометрическая проекция)"""
    sx = (x - y) * math.cos(ISO_ANGLE)
    sy = (x + y) * math.sin(ISO_ANGLE) + z
    return sx, sy


# Цвета по типу детали - как в референсных 3D-превью стороннего производителя
# (боковины светло-зелёные, двери коричневые/дерево, задняя стенка фиолетовая,
# дно синее) - это то, что реально даёт читаемость сложной сборки, вместо
# одного и того же цвета на все панели подряд.
PANEL_COLORS = {
    "Боковина": (0.75, 0.88, 0.55),   # светло-зелёный
    "Дверь": (0.68, 0.52, 0.35),       # коричневый (дерево/фасад)
    "Крыша": (0.62, 0.80, 0.90),       # голубой
    "Дно": (0.30, 0.55, 0.82),         # синий
    "Полка": (0.92, 0.87, 0.62),       # светло-жёлтый
    "Задняя": (0.55, 0.20, 0.55),      # фиолетовый
}
DEFAULT_PANEL_COLOR = (0.85, 0.90, 0.95)  # светло-голубой - для всего остального


def get_panel_color(label):
    """Цвет заливки панели по названию (проверяем по префиксу, т.к. имена
    вида 'Боковина (лев.)', 'Полка 2' и т.п. должны попадать в свою группу)"""
    for prefix, color in PANEL_COLORS.items():
        if label.startswith(prefix):
            return color
    return DEFAULT_PANEL_COLOR


def shade_color(color, factor):
    """Осветлить/затемнить цвет (factor<1 темнее, factor>1 светлее, с зажимом
    в [0,1]) - используется, чтобы соседние модули в общей сцене кухни
    отличались друг от друга даже при одинаковом типе детали (два бока
    соседних шкафов не сливались в одно бесформенное зелёное пятно)."""
    return tuple(max(0.0, min(1.0, c * factor)) for c in color)


class Plate3D:
    """Плоская деталь в 3D - прямоугольник, заданный 4 углами + номер позиции"""
    def __init__(self, corners_3d, pos_num, label, explode_dir=(0, 0, 0)):
        """
        corners_3d: список 4 точек (x,y,z) по контуру прямоугольника
        pos_num: номер позиции для выноски (как в спецификации)
        label: название детали
        explode_dir: направление и величина смещения при разнесении (dx,dy,dz), мм
        """
        self.corners_3d = corners_3d
        self.pos_num = pos_num
        self.label = label
        self.explode_dir = explode_dir

    def exploded_corners(self, factor=1.0):
        dx, dy, dz = self.explode_dir
        return [(x + dx * factor, y + dy * factor, z + dz * factor) for (x, y, z) in self.corners_3d]

    def center_3d(self, factor=1.0):
        pts = self.exploded_corners(factor)
        n = len(pts)
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


class Rod3D:
    """Труба каркаса в 3D - отрезок между двумя точками + номер позиции"""
    def __init__(self, p1, p2, pos_num, label, explode_dir=(0, 0, 0)):
        self.p1 = p1
        self.p2 = p2
        self.pos_num = pos_num
        self.label = label
        self.explode_dir = explode_dir

    def exploded_points(self, factor=1.0):
        dx, dy, dz = self.explode_dir
        p1 = (self.p1[0]+dx*factor, self.p1[1]+dy*factor, self.p1[2]+dz*factor)
        p2 = (self.p2[0]+dx*factor, self.p2[1]+dy*factor, self.p2[2]+dz*factor)
        return p1, p2

    def center_3d(self, factor=1.0):
        p1, p2 = self.exploded_points(factor)
        return tuple((a+b)/2 for a, b in zip(p1, p2))


def build_cabinet_scene(height, width, depth, shelf_count=0, door_count=2, has_tubes=True):
    """
    Строит 3D-сцену шкафа: список Plate3D (панели) + список Rod3D (каркас),
    с направлением "разнесения" для каждой детали (куда она отъезжает при
    экспоненте explode factor > 0).

    Возвращает (plates, rods) - в порядке отрисовки "от задних к передним"
    (важно для правильного вида в изометрии без z-буфера).
    """
    W, D, H = width, depth, height
    EXP = 0.35  # доля от габарита, на которую разъезжается деталь при разнесении

    plates = []
    pos = 1

    # Дно (низ) - разъезжается вниз
    plates.append(Plate3D(
        [(0, 0, 0), (W, 0, 0), (W, D, 0), (0, D, 0)],
        pos, "Дно", explode_dir=(0, 0, -H * EXP)
    ))
    pos += 1

    # Боковины - разъезжаются в стороны (влево/вправо)
    plates.append(Plate3D(
        [(0, 0, 0), (0, D, 0), (0, D, H), (0, 0, H)],
        pos, "Боковина (лев.)", explode_dir=(-W * EXP, 0, 0)
    ))
    pos += 1
    plates.append(Plate3D(
        [(W, 0, 0), (W, D, 0), (W, D, H), (W, 0, H)],
        pos, "Боковина (прав.)", explode_dir=(W * EXP, 0, 0)
    ))
    pos += 1

    # Полки - разъезжаются вверх, каждая чуть сильнее следующей (чтобы не слипались)
    for i in range(shelf_count):
        z_shelf = H * (i + 1) / (shelf_count + 1)
        plates.append(Plate3D(
            [(0, 0, z_shelf), (W, 0, z_shelf), (W, D, z_shelf), (0, D, z_shelf)],
            pos, f"Полка {i+1}", explode_dir=(0, 0, H * EXP * (0.5 + 0.3 * i))
        ))
        pos += 1

    # Крыша (верх) - разъезжается вверх сильнее всех горизонтальных
    plates.append(Plate3D(
        [(0, 0, H), (W, 0, H), (W, D, H), (0, D, H)],
        pos, "Крыша", explode_dir=(0, 0, H * EXP * 1.6)
    ))
    pos += 1

    # Двери - разъезжаются вперёд (к зрителю, -y)
    if door_count == 2:
        plates.append(Plate3D(
            [(0, 0, 0), (W/2, 0, 0), (W/2, 0, H), (0, 0, H)],
            pos, "Дверь (лев.)", explode_dir=(0, -D * EXP * 2, 0)
        ))
        pos += 1
        plates.append(Plate3D(
            [(W/2, 0, 0), (W, 0, 0), (W, 0, H), (W/2, 0, H)],
            pos, "Дверь (прав.)", explode_dir=(0, -D * EXP * 2, 0)
        ))
        pos += 1

    rods = []
    if has_tubes:
        # 4 угловые стойки каркаса - остаются на месте (это "скелет", вокруг
        # которого разъезжаются панели)
        corners_xy = [(0, 0), (W, 0), (W, D), (0, D)]
        for (x, y) in corners_xy:
            rods.append(Rod3D((x, y, 0), (x, y, H), pos, "стойка каркаса", explode_dir=(0, 0, 0)))
            pos += 1
        # пояса низ/верх
        for z in (0, H):
            rods.append(Rod3D((0, 0, z), (W, 0, z), pos, "пояс каркаса", explode_dir=(0, 0, 0)))
            pos += 1
            rods.append(Rod3D((W, 0, z), (W, D, z), pos, "пояс каркаса", explode_dir=(0, 0, 0)))
            pos += 1
            rods.append(Rod3D((W, D, z), (0, D, z), pos, "пояс каркаса", explode_dir=(0, 0, 0)))
            pos += 1
            rods.append(Rod3D((0, D, z), (0, 0, z), pos, "пояс каркаса", explode_dir=(0, 0, 0)))
            pos += 1

    return plates, rods


def _bounding_box_2d(plates, rods, factor):
    """Вычислить 2D-габариты всей сцены в проекции (для масштабирования на лист)"""
    xs, ys = [], []
    for p in plates:
        for pt in p.exploded_corners(factor):
            sx, sy = iso_project(*pt)
            xs.append(sx)
            ys.append(sy)
    for r in rods:
        for pt in r.exploded_points(factor):
            sx, sy = iso_project(*pt)
            xs.append(sx)
            ys.append(sy)
    return min(xs), max(xs), min(ys), max(ys)


def draw_exploded_view(c, plates, rods, page_size, title, company_name,
                        code, sheet_num=1, sheets_total=1, paper_format="A4",
                        font_name="Helvetica", title_block_fn=None):
    """
    Нарисовать страницу с разнесённым изометрическим видом сборки:
    панели+каркас в проекции, номера позиций у каждой детали, легенда
    (номер -> название), штамп.
    """
    from reportlab.lib.units import mm

    page_w, page_h = page_size
    # Те же отступы, что и на остальных страницах документа (draw_part_page/
    # draw_tube_page) - иначе штамп (который всегда рассчитан на 20мм слева/
    # 5мм с остальных сторон) не совпадает с рамкой этой конкретной страницы.
    margin_left = 20 * mm
    margin_right = 5 * mm
    margin_top = 5 * mm
    margin_bottom = 5 * mm
    title_h = 55 * mm
    legend_w = 55 * mm  # полоса легенды справа

    draw_x0 = margin_left
    draw_y0 = margin_bottom + title_h + 10 * mm
    draw_x1 = page_w - margin_right - legend_w
    draw_y1 = page_h - margin_top - 10 * mm

    x_min, x_max, y_min, y_max = _bounding_box_2d(plates, rods, factor=1.0)
    scene_w = x_max - x_min
    scene_h = y_max - y_min

    avail_w = draw_x1 - draw_x0
    avail_h = draw_y1 - draw_y0
    scale = min(avail_w / (scene_w * mm), avail_h / (scene_h * mm))

    # центрируем сцену в отведённой области
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    origin_x = draw_x0 + avail_w / 2
    origin_y = draw_y0 + avail_h / 2

    def to_paper(x, y, z):
        sx, sy = iso_project(x, y, z)
        return origin_x + (sx - cx) * scale * mm, origin_y + (sy - cy) * scale * mm

    c.setFont(font_name, 8)

    # --- Каркас (трубы) - тонкие линии, серый цвет ---
    c.setLineWidth(1.4)
    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    for r in rods:
        p1, p2 = r.exploded_points(1.0)
        x1, y1 = to_paper(*p1)
        x2, y2 = to_paper(*p2)
        c.line(x1, y1, x2, y2)

    # --- Панели - заливка по типу детали + контур ---
    for p in plates:
        pts3d = p.exploded_corners(1.0)
        pts2d = [to_paper(*pt) for pt in pts3d]

        path = c.beginPath()
        path.moveTo(*pts2d[0])
        for pt in pts2d[1:]:
            path.lineTo(*pt)
        path.close()
        c.setFillColorRGB(*get_panel_color(p.label))
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        c.setLineWidth(0.7)
        c.drawPath(path, fill=1, stroke=1)

    # --- Номера позиций (кружок с номером в центре каждой детали) ---
    #
    # РАЗВЕДЕНИЕ КРУЖКОВ. Раньше кружок ставился ровно в центр детали. На
    # секции с мангалом (18+ деталей) центры лежат близко, и номера
    # СЛИПАЛИСЬ в нечитаемую кашу - поймано автотестом на пересечение
    # текста. Теперь, если кружок налезает на уже поставленный, он
    # отодвигается по спирали до свободного места, а к детали от него
    # проводится тонкая линия-привязка (чтобы было видно, чей это номер).
    all_items = list(plates) + list(rods)
    seen_labels = {}
    placed = []          # уже занятые кружками точки
    r = 3.2 * mm
    min_dist = 2 * r + 0.6 * mm

    def _free_spot(px, py):
        """Найти свободное место рядом с (px,py)"""
        import math
        if all((px - qx) ** 2 + (py - qy) ** 2 >= min_dist ** 2
               for qx, qy in placed):
            return px, py
        for ring in range(1, 7):
            step = min_dist * ring
            for k in range(12):
                a = math.radians(k * 30)
                nx, ny = px + step * math.cos(a), py + step * math.sin(a)
                if all((nx - qx) ** 2 + (ny - qy) ** 2 >= min_dist ** 2
                       for qx, qy in placed):
                    return nx, ny
        return px, py

    for item in all_items:
        cx3, cy3, cz3 = item.center_3d(1.0)
        ax, ay = to_paper(cx3, cy3, cz3)      # точка НА детали (якорь)
        px, py = _free_spot(ax, ay)           # куда реально встанет кружок
        placed.append((px, py))

        # линия-привязка от кружка к детали, если кружок отъехал
        if (px - ax) ** 2 + (py - ay) ** 2 > (1 * mm) ** 2:
            c.setStrokeColorRGB(0.45, 0.45, 0.45)
            c.setLineWidth(0.25)
            c.line(ax, ay, px, py)

        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.6)
        c.circle(px, py, r, fill=1, stroke=1)
        c.setFont(font_name, 7)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(px, py - 2.2, str(item.pos_num))

        if item.label not in seen_labels:
            seen_labels[item.label] = []
        seen_labels[item.label].append(item.pos_num)

    # --- Легенда справа (номер/номера -> название) ---
    legend_x = page_w - margin_right - legend_w + 3 * mm
    legend_y = page_h - margin_top - 10 * mm
    c.setFont(font_name, 9)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(legend_x, legend_y, "Позиции:")
    legend_y -= 6 * mm
    for label, nums in seen_labels.items():
        nums_str = ", ".join(str(n) for n in nums) if len(nums) <= 4 else f"{nums[0]}-{nums[-1]}"
        c.setFont(font_name, 7.5)
        c.drawString(legend_x, legend_y, f"{nums_str}")
        c.drawString(legend_x + 16 * mm, legend_y, label[:22])
        legend_y -= 4.5 * mm

    # --- Внешняя рамка листа (те же отступы, что и на остальных страницах) ---
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    c.setFont(font_name, 11)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left + 3 * mm, page_h - margin_top - 8 * mm, title)

    # --- Штамп ---
    if title_block_fn:
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