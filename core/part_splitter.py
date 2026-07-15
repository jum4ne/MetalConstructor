"""
Разбивка детали, которая не влезает ни на один лист целиком,
на 2 части со швом (для последующей сварки на месте).
"""
from dataclasses import replace
from core.models import BendLine


def split_part_if_needed(part, sheet_w, sheet_h, margin, seam_overlap=20):
    """
    Если деталь не влезает ни в одной ориентации на лист (с учётом отступов от края) -
    разбить её на 2 части по длинной стороне, с нахлёстом seam_overlap мм под сварной шов.
    Иначе вернуть деталь как есть.
    """
    usable_w = sheet_w - 2 * margin
    usable_h = sheet_h - 2 * margin

    fits_normal = part.width <= usable_w and part.height <= usable_h
    fits_rotated = part.height <= usable_w and part.width <= usable_h

    if fits_normal or fits_rotated:
        return [part]

    if part.cutouts:
        # Деталь с вырезом (мойка/гриль) разбивать на 2 части автоматически нельзя -
        # вырез окажется непредсказуемо на одной или обеих половинах.
        # Пусть основной раскрой выдаст понятную ошибку, и оператор решит вручную.
        return [part]

    max_usable = max(usable_w, usable_h)
    min_usable = min(usable_w, usable_h)

    if part.width > max_usable and part.height <= min_usable:
        axis = 'width'
        long_dim = part.width
    elif part.height > max_usable and part.width <= min_usable:
        axis = 'height'
        long_dim = part.height
    else:
        # деталь слишком велика по ОБЕИМ осям сразу - разбивкой на 2 части не решить,
        # вернуть как есть, дальше основной раскрой сам сообщит понятную ошибку
        return [part]

    half = round(long_dim / 2 + seam_overlap / 2)

    if axis == 'width':
        part1 = replace(part, name=f"{part.name} (часть 1/2, шов)", width=half,
                         bend_lines=list(part.bend_lines), cutouts=list(part.cutouts))
        part2 = replace(part, name=f"{part.name} (часть 2/2, шов)", width=half,
                         bend_lines=list(part.bend_lines), cutouts=list(part.cutouts))
        part1.bend_lines.append(BendLine(edge='right', offset=seam_overlap, angle=0,
                                          direction='seam', note='ШОВ - сварить со 2-й частью'))
        part2.bend_lines.append(BendLine(edge='left', offset=seam_overlap, angle=0,
                                          direction='seam', note='ШОВ - сварить с 1-й частью'))
    else:
        part1 = replace(part, name=f"{part.name} (часть 1/2, шов)", height=half,
                         bend_lines=list(part.bend_lines), cutouts=list(part.cutouts))
        part2 = replace(part, name=f"{part.name} (часть 2/2, шов)", height=half,
                         bend_lines=list(part.bend_lines), cutouts=list(part.cutouts))
        part1.bend_lines.append(BendLine(edge='top', offset=seam_overlap, angle=0,
                                          direction='seam', note='ШОВ - сварить со 2-й частью'))
        part2.bend_lines.append(BendLine(edge='bottom', offset=seam_overlap, angle=0,
                                          direction='seam', note='ШОВ - сварить с 1-й частью'))

    return [part1, part2]