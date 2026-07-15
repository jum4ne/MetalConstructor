"""
3D-сцена из НАСТОЯЩИХ деталей модуля (а не из выдуманных коробок).

==========================================================================
ЧТО БЫЛО НЕ ТАК
==========================================================================
Старый build_cabinet_scene(height, width, depth, shelf_count, door_count)
СИНТЕЗИРОВАЛ сцену: брал габариты и счётчики полок/дверей и лепил из них
прямоугольники. Со списком настоящих Part он связан НЕ БЫЛ. Поэтому:

  - на виде не было деталей, которые реально есть (направляющие, накладки)
  - были детали, которых нет
  - размеры панелей не соответствовали развёрткам
  - всё лежало в одной плоскости и накладывалось друг на друга

Здесь сцена строится ИЗ module.parts: каждая деталь получает своё место
в 3D по своей РОЛИ в сборке, и разносится вдоль своей оси монтажа.
Соответствие "деталь <-> плита на виде" теперь однозначное, поэтому
номера позиций на выноске совпадают со спецификацией.

Порядок отрисовки - от дальних к ближним (художников алгоритм), иначе
без z-буфера передние детали затираются задними.
"""
from core.exploded_view import Plate3D, Rod3D


# Роль детали -> (ось разноса, порядок слоя, цвет)
# Ось разноса - куда деталь "отъезжает" на разнесённом виде. Она совпадает
# с направлением реального монтажа: дно опускается вниз, боковины
# разъезжаются вбок, задняя стенка уходит назад.
ROLE_LAYOUT = {
    "дно":            dict(axis=(0, 0, -1), layer=0, color=(0.30, 0.55, 0.82)),
    "боковая панель": dict(axis=(-1, 0, 0), layer=2, color=(0.75, 0.88, 0.55)),
    "задняя стенка":  dict(axis=(0, 1, 0), layer=1, color=(0.55, 0.20, 0.55)),
    "направляющая":   dict(axis=(0, 0, 1), layer=3, color=(0.95, 0.65, 0.20)),
    "корпус ящика":   dict(axis=(0, -1, 0), layer=4, color=(0.85, 0.85, 0.90)),
    "панель":         dict(axis=(0, -1, 0), layer=5, color=(0.92, 0.87, 0.62)),
    "декоративная":   dict(axis=(0, -1, 0), layer=6, color=(0.35, 0.35, 0.40)),
    "столешница":     dict(axis=(0, 0, 1), layer=7, color=(0.40, 0.42, 0.45)),
}
DEFAULT_LAYOUT = dict(axis=(0, 0, 1), layer=5, color=(0.85, 0.90, 0.95))


def _layout_for(name):
    n = name.lower()
    for key, cfg in ROLE_LAYOUT.items():
        if n.startswith(key):
            return cfg
    return DEFAULT_LAYOUT


def _plate(x0, y0, z0, dx, dy, dz, pos, label, axis, gap):
    """Прямоугольная плита, лежащая в одной из трёх плоскостей"""
    if dx == 0:      # плоскость YZ (боковина)
        corners = [(x0, y0, z0), (x0, y0 + dy, z0),
                   (x0, y0 + dy, z0 + dz), (x0, y0, z0 + dz)]
    elif dy == 0:    # плоскость XZ (задняя стенка / фасад)
        corners = [(x0, y0, z0), (x0 + dx, y0, z0),
                   (x0 + dx, y0, z0 + dz), (x0, y0, z0 + dz)]
    else:            # плоскость XY (дно / полка / столешница)
        corners = [(x0, y0, z0), (x0 + dx, y0, z0),
                   (x0 + dx, y0 + dy, z0), (x0, y0 + dy, z0)]
    ex = tuple(a * gap for a in axis)
    return Plate3D(corners, pos, label, explode_dir=ex)


def build_module_scene(module, gap=180):
    """
    Собрать 3D-сцену из настоящих деталей модуля.

    module: Module (его .parts и .tubes)
    gap:    насколько детали разъезжаются на разнесённом виде, мм

    Возвращает (plates, rods), отсортированные от дальних к ближним.
    """
    W, D, H = module.width, module.depth, module.height
    plates, rods = [], []
    pos = 0

    # --- Каркас: 4 стойки + пояса ---
    posts = [(0, 0), (W, 0), (0, D), (W, D)]
    for (px, py) in posts:
        pos += 1
        rods.append(Rod3D((px, py, 0), (px, py, H), pos, "стойка каркаса",
                          explode_dir=(0, 0, 0)))

    for z in (60, H - 60):
        for (y0, y1) in ((0, 0), (D, D)):
            pos += 1
            rods.append(Rod3D((0, y0, z), (W, y1, z), pos, "пояс каркаса",
                              explode_dir=(0, 0, 0)))

    # --- Листовые детали: каждая по своей роли ---
    items = []
    for p in module.parts:
        cfg = _layout_for(p.name)
        items.append((cfg["layer"], p, cfg))
    items.sort(key=lambda t: t[0])

    for layer, p, cfg in items:
        pos += 1
        name = p.name.lower()
        axis = cfg["axis"]

        if name.startswith("дно"):
            plates.append(_plate(0, 0, 0, W, D, 0, pos, p.name, axis, gap))

        elif name.startswith("боковая панель"):
            # 2 шт: слева и справа, разъезжаются в РАЗНЫЕ стороны
            plates.append(_plate(0, 0, 0, 0, D, H, pos, p.name + " (лев.)",
                                 (-1, 0, 0), gap))
            pos += 1
            plates.append(_plate(W, 0, 0, 0, D, H, pos, p.name + " (прав.)",
                                 (1, 0, 0), gap))

        elif name.startswith("задняя стенка"):
            plates.append(_plate(0, D, 0, W, 0, H, pos, p.name, axis, gap))

        elif name.startswith("направляющая"):
            # 8 шт = по 2 на каждый из 4 ящиков, по высоте равномерно.
            # Раньше их не было на виде вообще - ящики "висели в воздухе".
            n_pairs = max(1, p.quantity // 2)
            for i in range(n_pairs):
                z = 80 + i * (H - 160) / max(1, n_pairs)
                for side, sx in (("лев.", 0), ("прав.", W)):
                    rods.append(Rod3D((sx, 0, z), (sx, D, z), pos,
                                      f"направляющая ({side})",
                                      explode_dir=(0, 0, gap * 0.15)))
                pos += 1
            pos -= 1

        elif name.startswith("столешница"):
            plates.append(_plate(0, 0, H, W, D, 0, pos, p.name, axis, gap))

        else:
            # Прочее (фасады, накладки). КАЖДАЯ получает свой вынос вперёд и
            # свою высоту, иначе все лягут в одну плоскость и наложатся -
            # ровно это и делало старый вид "плоским и непонятным".
            other_idx = sum(1 for q in plates if q.label not in
                            ("Дно",) and 'панел' in q.label.lower())
            depth_step = 1.0 + 0.55 * other_idx      # разный вынос
            z = H * (0.18 + 0.20 * other_idx)        # разная высота
            plates.append(_plate(0, 0, z, W, 0, H * 0.30, pos, p.name,
                                 (0, -depth_step, 0), gap))

    # --- Ящики-подсборки: показываем выдвинутыми вперёд ---
    for i, sub in enumerate(getattr(module, "subassemblies", []) or []):
        pos += 1
        z = 100 + i * (H - 200) / max(1, len(module.subassemblies))
        dw = W * 0.85
        plates.append(_plate(W * 0.075, -gap * 0.35, z, dw, 0, 140, pos,
                             sub.name, (0, -1, 0), gap * 0.5))

    # Художников алгоритм: дальние (больше x+y) рисуются первыми
    plates.sort(key=lambda p: -(sum(c[0] + c[1] for c in p.corners_3d) / 4))
    return plates, rods