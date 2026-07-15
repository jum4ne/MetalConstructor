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

2. Вырез в углу - НЕ квадрат на всю глубину загиба, а тонкая прорезь
   ~2.5-3мм, только чтобы механически отделить два смежных борта друг
   от друга. Вырезать целый квадрат 32x32мм - огромный перерасход металла
   на каждую деталь, реальные мастера так не делают.

Этот модуль исправлен под то, что реально видно на профессиональных
чертежах - не выдумано с нуля и не собрано второпях.
"""
from dataclasses import replace
from core.models import BendLine

FLANGE_DEPTH = 20    # мм - загиб, даёт жёсткость (подтверждено чертежами: 17.8-20мм)

# Ширина разделительной прорези в углу - НЕ размер выреза на всю глубину
# загиба, а тонкая щель, чтобы два смежных борта могли гнуться независимо.
# Взято по образцу реальных чертежей (там было ~2.5мм).
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


def build_outline_points(x, y, w, h, corners, notch):
    """
    Построить контур детали (список точек замкнутой полилинии) - обычный
    прямоугольник, если corners пуст, иначе с тонкими разделительными
    прорезями notch x notch мм в указанных углах.

    Обходим прямоугольник против часовой стрелки, начиная от нижнего левого
    угла: низ -> право -> верх -> лево -> назад к началу. В каждом отмеченном
    углу вместо одной точки-угла делаем маленькую "ступеньку" внутрь на
    notch мм (это и есть разделительная прорезь).

    Args:
        x, y: координаты нижнего левого угла детали на листе
        w, h: размеры детали (ширина, высота)
        corners: подмножество {'bottom-left','bottom-right','top-right','top-left'}
        notch: размер прорези (мм) - маленькое число (~3мм), НЕ глубина загиба

    Returns:
        список точек (x,y) - замкнутый контур (последняя точка = первая)
    """
    x0, y0 = x, y
    x1, y1 = x + w, y + h
    n = notch

    points = []

    if 'bottom-left' in corners:
        points.append((x0, y0 + n))
        points.append((x0 + n, y0 + n))
        points.append((x0 + n, y0))
    else:
        points.append((x0, y0))

    if 'bottom-right' in corners:
        points.append((x1 - n, y0))
        points.append((x1 - n, y0 + n))
        points.append((x1, y0 + n))
    else:
        points.append((x1, y0))

    if 'top-right' in corners:
        points.append((x1, y1 - n))
        points.append((x1 - n, y1 - n))
        points.append((x1 - n, y1))
    else:
        points.append((x1, y1))

    if 'top-left' in corners:
        points.append((x0 + n, y1))
        points.append((x0 + n, y1 - n))
        points.append((x0, y1 - n))
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