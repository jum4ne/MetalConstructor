"""
Генератор сварного каркаса из профильной трубы - несущая часть модуля.

Разобрано по референсному комплекту чертежей: конструкция держится на
сварном каркасе (профильная труба), а листовые панели - это обшивка на
каркас, не несущий элемент сама по себе. Здесь - базовая, упрощённая, но
реалистичная схема каркаса: 4 вертикальные стойки по углам + нижний и
верхний прямоугольный пояс. Это не точный сварочный чертёж (не показывает
точки прихватки/сварных швов), а достаточно для списка деталей и метража
трубы в спецификации.

Профили взяты из референсного Excel ("Труба 40х20х1" - основной профиль
несущих стоек и поясов).
"""
from core.models import TubePart

# Профиль стоек и поясов - как в референсном комплекте (вкладка "Трубы")
POST_PROFILE = (40, 20, 1.0)   # (ширина, высота, толщина стенки) мм
RAIL_PROFILE = (40, 20, 1.0)


def build_frame(height, width, depth, note_prefix=""):
    """
    Построить базовый каркас для прямоугольного модуля (шкаф/тумба).

    Длины горизонтальных поясов уменьшены на 2×ширину профиля стойки -
    приближение под сборку встык между стойками (труба пояса режется по
    месту между двумя стойками, а не проходит через них). Это достаточно
    точно для списка деталей и метража, но не заменяет точный сварочный
    чертёж с точками прихватки - его цех делает по месту.

    Args:
        height, width, depth: габариты модуля, мм
        note_prefix: префикс для поля note (напр. название модуля)

    Returns:
        список TubePart: 4 стойки, нижний пояс (2+2), верхний пояс (2+2)
    """
    pw, ph, wall = POST_PROFILE
    rw, rh, rwall = RAIL_PROFILE
    prefix = f"{note_prefix} " if note_prefix else ""

    tubes = []

    # 4 вертикальные стойки по углам
    tubes.append(TubePart(pw, ph, wall, height, quantity=4, note=f"{prefix}стойка".strip()))

    # Пояса встык между стойками - длина уменьшена на профиль стоек с двух концов
    rail_width_len = max(int(width - 2 * pw), 0)
    rail_depth_len = max(int(depth - 2 * ph), 0)

    if rail_width_len > 0:
        tubes.append(TubePart(rw, rh, rwall, rail_width_len, quantity=2, note=f"{prefix}нижний пояс".strip()))
        tubes.append(TubePart(rw, rh, rwall, rail_width_len, quantity=2, note=f"{prefix}верхний пояс".strip()))
    if rail_depth_len > 0:
        tubes.append(TubePart(rw, rh, rwall, rail_depth_len, quantity=2, note=f"{prefix}нижний пояс".strip()))
        tubes.append(TubePart(rw, rh, rwall, rail_depth_len, quantity=2, note=f"{prefix}верхний пояс".strip()))

    return tubes