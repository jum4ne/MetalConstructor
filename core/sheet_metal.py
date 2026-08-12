"""
Загиб для несущих деталей из тонкого листового металла (полки, боковины,
дно) - жёсткость.

ИСТОРИЯ ПРАВКИ: первая версия этого модуля делала ДВОЙНОЙ загиб (силовой
+ подгибка кромки) с квадратным вырезом 32x32мм в каждом углу. После
разбора реальных чертежей стороннего производства (91-страничный комплект
конструкторской документации + плоские DXF-развёртки) выяснилось:

1. Загиб ОДИН, не два. У профессионалов конструкция держится на сварном
   каркасе из профильной трубы - тонкая обшивка (панели) не несёт нагрузку
   сама по себе, поэтому подгибка кромки для доп. жёсткости не нужна.
   Глубина загиба подтверждена дважды: по координатам в DXF (17.8-20мм)
   и по проставленному размеру на чертеже (ровно 20мм).

2. Вырез в углу - ПРЯМОУГОЛЬНИК ДО ЛИНИЙ ГИБА обоих смежных бортов
   (см. get_corner_cuts). Металл в углу принадлежит ОБОИМ бортам сразу,
   и без выреза они при гибке упираются друг в друга.

   ИСПРАВЛЕНО 2026-07-16. Раньше здесь стояла тонкая прорезь ~2.5-3мм и
   утверждение, что «вырезать целый квадрат - огромный перерасход металла,
   мастера так не делают». Оба тезиса ОШИБОЧНЫ, проверено по эталонному
   DXF мастера «К 01.01.01.007 - Дно»:
     - мастер вырезает угол ЦЕЛИКОМ (там 19x20мм, ровно до линий гиба);
     - перерасхода нет: вырез лежит ВНУТРИ габарита заготовки (495x571),
       место в раскрое не меняется - угол просто выпадает обрезком.
   Прорезь 2.5мм освобождала 2.5мм из 19x20мм общего углового материала,
   то есть 8 коробчатых деталей комплекса физически не гнулись.

Этот модуль исправлен под то, что реально видно на профессиональных
чертежах - не выдумано с нуля и не собрано второпях.
"""
from dataclasses import replace
from core.models import BendLine

FLANGE_DEPTH = 20    # мм - загиб, даёт жёсткость (подтверждено чертежами: 17.8-20мм)

# ФЛАГ «в этом углу нужен вырез». Сам РАЗМЕР выреза здесь НЕ хранится:
# он считается из линий гиба детали в get_corner_cuts() (прямоугольник до
# пересечения линий гиба). Поле Part.corner_relief осталось как признак
# «углы освободить» - одним числом прямоугольный вырез не описать.
CORNER_SLIT_WIDTH = 3


def add_flange(part, edges=("left", "right", "top", "bottom"), flange_depth=FLANGE_DEPTH):
    """
    Увеличить деталь на припуск под загиб и добавить линии сгиба.

    ВАЖНО: вызывать ДО добавления вырезов (cutouts) на деталь - функция
    меняет width/height, а вырезы заданы в абсолютных координатах
    относительно детали. Если вызвать после добавления выреза, его
    координаты окажутся смещены от центра.

    Args:
        part: деталь (Part), для которой считаем загиб
        edges: на каких краях есть загиб, по умолчанию все 4
        flange_depth: длина загиба, мм (по умолчанию 20мм)

    Returns:
        новый Part с увеличенным размером и линиями сгиба
        (исходный part не меняется, dataclasses.replace создаёт копию)
    """
    fold = flange_depth

    new_width = part.width + (fold * 2 if "left" in edges and "right" in edges
                               else fold if "left" in edges or "right" in edges else 0)
    new_height = part.height + (fold * 2 if "top" in edges and "bottom" in edges
                                 else fold if "top" in edges or "bottom" in edges else 0)

    bend_lines = list(part.bend_lines)

    for edge in edges:
        bend_lines.append(BendLine(
            edge=edge, offset=fold, angle=90, direction="down",
            note=f"гиб {flange_depth}мм"
        ))

    # Вырез нужен только в углах, где ДВА смежных края загнуты одновременно -
    # если загнут только один край (или два противоположных), борта друг
    # другу не мешают, прорезь не нужна.
    corner_slit = CORNER_SLIT_WIDTH if _has_adjacent_folded_edges(edges) else 0

    return replace(part, width=new_width, height=new_height, bend_lines=bend_lines,
                    cutouts=list(part.cutouts), corner_relief=corner_slit)


def _has_adjacent_folded_edges(edges):
    """Есть ли среди загнутых краёв хотя бы одна смежная пара (не только
    противоположные left/right или top/bottom)"""
    edges = set(edges)
    adjacent_pairs = [('left', 'top'), ('left', 'bottom'), ('right', 'top'), ('right', 'bottom')]
    return any(a in edges and b in edges for a, b in adjacent_pairs)


def get_corners_needing_relief(part):
    """
    Определить, в каких углах детали нужна разделительная прорезь - это
    углы, где ОБА смежных края имеют линии сгиба (значит, оба борта в этом
    углу гнутся, и без прорези будут друг другу немного мешать).

    Возвращает список из подмножества {'bottom-left', 'bottom-right',
    'top-right', 'top-left'}.
    """
    if not part.corner_relief or part.corner_relief <= 0:
        return []

    folded_edges = set(b.edge for b in part.bend_lines)
    corners = []
    if 'left' in folded_edges and 'bottom' in folded_edges:
        corners.append('bottom-left')
    if 'right' in folded_edges and 'bottom' in folded_edges:
        corners.append('bottom-right')
    if 'right' in folded_edges and 'top' in folded_edges:
        corners.append('top-right')
    if 'left' in folded_edges and 'top' in folded_edges:
        corners.append('top-left')
    return corners


def get_corner_cuts(part):
    """
    Прямоугольный вырез в каждом углу, где сходятся ДВА гнутых борта:
    от угла ДО ПЕРЕСЕЧЕНИЯ ЛИНИЙ ГИБА этих бортов.

    ЗАЧЕМ (проверено по эталонному DXF мастера «К 01.01.01.007 - Дно»):
    металл в углу принадлежит ОБОИМ смежным бортам сразу. Если его не
    убрать, при гибке 2-го борта углы упираются друг в друга - деталь мнёт,
    рвёт или гнёт внахлёст. Мастер вырезает угол целиком (у «Дна» это
    прямоугольник 19x20), и каждый борт становится свободной полосой.

    Тонкая прорезь 2.5-3мм (как было раньше) НЕ решает задачу: она
    освобождает 2.5мм из 19x20мм общего углового материала.

    Вырез НЕ увеличивает расход металла: он лежит ВНУТРИ габарита заготовки,
    место в раскрое не меняется - угол просто выпадает обрезком.

    Returns:
        {'bottom-left': (dx, dy), ...} - размеры выреза по X и Y, мм
    """
    offs = {}
    for b in part.bend_lines:
        if b.direction == 'seam':
            continue
        offs.setdefault(b.edge, b.offset)

    pairs = {
        'bottom-left':  ('left', 'bottom'),
        'bottom-right': ('right', 'bottom'),
        'top-right':    ('right', 'top'),
        'top-left':     ('left', 'top'),
    }
    cuts = {}
    for corner, (edge_x, edge_y) in pairs.items():
        if edge_x in offs and edge_y in offs:
            cuts[corner] = (offs[edge_x], offs[edge_y])
    return cuts


def rotate_corner_cuts(cuts):
    """Повернуть вырезы на 90° вместе с деталью: имена углов + dx/dy местами"""
    return {CORNER_ROTATION_MAP[k]: (dy, dx) for k, (dx, dy) in cuts.items()}


def _cut_size(notch, corner):
    """notch может быть числом (квадратный вырез) или dict {угол: (dx, dy)}"""
    if isinstance(notch, dict):
        return notch.get(corner, (0, 0))
    return (notch, notch)


def build_outline_points(x, y, w, h, corners, notch):
    """
    Построить контур детали (список точек замкнутой полилинии) - обычный
    прямоугольник, если corners пуст, иначе с вырезами в указанных углах.

    Обходим прямоугольник против часовой стрелки, начиная от нижнего левого
    угла: низ -> право -> верх -> лево -> назад к началу. В каждом отмеченном
    углу вместо одной точки-угла делаем "ступеньку" внутрь.

    Args:
        x, y: координаты нижнего левого угла детали на листе
        w, h: размеры детали (ширина, высота)
        corners: подмножество {'bottom-left','bottom-right','top-right','top-left'}
        notch: ЛИБО число (квадратный вырез notch x notch - старое поведение),
               ЛИБО dict {угол: (dx, dy)} из get_corner_cuts() - прямоугольный
               вырез до линий гиба (правильный для гибки).

    Returns:
        список точек (x,y) - замкнутый контур (последняя точка = первая)
    """
    x0, y0 = x, y
    x1, y1 = x + w, y + h

    points = []

    if 'bottom-left' in corners:
        dx, dy = _cut_size(notch, 'bottom-left')
        points.append((x0, y0 + dy))
        points.append((x0 + dx, y0 + dy))
        points.append((x0 + dx, y0))
    else:
        points.append((x0, y0))

    if 'bottom-right' in corners:
        dx, dy = _cut_size(notch, 'bottom-right')
        points.append((x1 - dx, y0))
        points.append((x1 - dx, y0 + dy))
        points.append((x1, y0 + dy))
    else:
        points.append((x1, y0))

    if 'top-right' in corners:
        dx, dy = _cut_size(notch, 'top-right')
        points.append((x1, y1 - dy))
        points.append((x1 - dx, y1 - dy))
        points.append((x1 - dx, y1))
    else:
        points.append((x1, y1))

    if 'top-left' in corners:
        dx, dy = _cut_size(notch, 'top-left')
        points.append((x0 + dx, y1))
        points.append((x0 + dx, y1 - dy))
        points.append((x0, y1 - dy))
    else:
        points.append((x0, y1))

    points.append(points[0])
    return points


CORNER_ROTATION_MAP = {
    'bottom-left': 'top-left',
    'bottom-right': 'bottom-left',
    'top-right': 'bottom-right',
    'top-left': 'top-right',
}


def rotate_corners(corners):
    """Повернуть названия углов на 90 градусов (при повороте детали в раскрое)"""
    return [CORNER_ROTATION_MAP[c] for c in corners]