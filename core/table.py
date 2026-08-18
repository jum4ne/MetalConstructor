"""
СТОЛ — билдер по ТОЧНЫМ контурам эталона (стол.dxf от цеха).

Контуры всех 10 деталей сняты трассировщиком с эталона (внешний контур со
скруглениями через bulge, внутренние вырезы, отверстия) — в
core/table_contours.json. Выгрузка единым раскроем (2 файла: уголки/пунктир),
как у электро- и пожарного шкафов.

ВНИМАНИЕ: габаритной привязки (Ш×В×Г → размеры деталей) от цеха пока нет,
поэтому геометрия воспроизводится ТОЧНО ПО ЭТАЛОНУ (1:1). Когда придут
размеры стола и правило их пересчёта — добавим параметрику, как у шкафов.
"""
import os
import json
from core.models import Part, Cutout
from core.module import Module

_DATA = json.load(open(os.path.join(os.path.dirname(__file__), "table_contours.json"),
                      encoding="utf-8"))


def _build(name, thickness):
    d = _DATA[name]
    part = Part(f"{name} ({int(d['w'])}x{int(d['h'])})", int(round(d["w"])), int(round(d["h"])),
                1, thickness)
    part.outline = [(x, y, b) for x, y, b in d["outline"]]
    part.extra_cuts = [([(x, y, b) for x, y, b in cut], True) for cut in d["cutouts"]]
    for hx, hy, r in d["holes"]:
        part.cutouts.append(Cutout("circle", hx, hy, radius=r))
    part.is_hidden_in_assembly = False
    return part


class Table:
    """Стол. Один чертёж-раскрой = 10 деталей (точные контуры с эталона).
    Геометрия 1:1 по эталону; параметрика — после габаритов от цеха."""
    CODE = "СТ"

    @staticmethod
    def build(width=None, height=None, depth=None, thickness=1.2):
        m = Module(name="Стол", module_type="Стол",
                   height=height or 0, width=width or 0, depth=depth or 0,
                   thickness=thickness)
        for name in _DATA:
            m.add_part(_build(name, thickness))
        m.cut_layout = True
        return m
