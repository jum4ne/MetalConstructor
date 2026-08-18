"""
ПОЖАРНЫЙ ШКАФ (навесной) — параметрический билдер по ТОЧНЫМ контурам эталона.

Контуры всех 8 деталей сняты с эталона пожарный.dxf (внешний контур со всеми
скруглениями/полками/ступеньками через bulge-дуги, внутренние вырезы, отверстия)
и линии гиба — из нового эталона от цеха (штрих-пунктир). Данные в
core/fire_contours.json (генерируются трассировщиком, не вручную).

Габарит эталона: 540 (Ш) x 655 (В) x 200 (Г). Состав — 8 деталей:
    Дверь с окном, Дверь глухая (520x628.5)   — 2 варианта на одном чертеже
    Корпус (1013x650)                          — задняя+боковины+возвраты, 7 гибов
    Крышка верх, Крышка низ (556.5x258)        — скруглённые, борта
    Панель малая (130x190), Косынка (350x252), Планка боковая (160x635)

Детали параметрические: контур масштабируется под габарит (при 540x655x200 —
точно эталон). Bulge относительный к хорде, поэтому дуги остаются круговыми
при масштабе. Модель гиба аддитивная (радиус станка 1.2, мин. полка 10).
"""
import os
import json
from core.models import Part, BendLine, Cutout
from core.module import Module

_DATA = json.load(open(os.path.join(os.path.dirname(__file__), "fire_contours.json"),
                      encoding="utf-8"))

# Как каждая деталь эталона тянется за габаритом (ref = 540x655x200).
# kind: 'edge' — краевые борта (уголки/пунктир), 'inner' — внутренние сгибы
# корпуса, None — без гибов. sx/sy — функции (W,H,D).
def _spec(W, H, D):
    return {
        "ДВЕРЬ-окно":   ("Дверь с окном",   (W - 20) / 520.0, (H - 26.5) / 628.5, "edge", False),
        "ДВЕРЬ-глухая": ("Дверь глухая",    (W - 20) / 520.0, (H - 26.5) / 628.5, "edge", False),
        "КОРПУС":       ("Корпус",          (W + 2 * D + 73) / 1013.0, (H - 5) / 650.0, "inner", True),
        "КРЫШКА-1":     ("Крышка верхняя",  (W + 16) / 556.5, (D + 58) / 258.1, "edge", True),
        "КРЫШКА-2":     ("Крышка нижняя",   (W + 16) / 556.5, (D + 58) / 258.1, "edge", True),
        "ПАНЕЛЬ-малая": ("Панель малая",    1.0, 1.0, None, True),
        "КОСЫНКА":      ("Косынка",         1.0, 1.0, None, True),
        "ПЛАНКА-бок":   ("Планка боковая",  1.0, (H - 20) / 635.0, None, True),
    }


def _bends(kind, raw, w, h, sx, sy):
    """Преобразовать снятые линии гиба [orient,pos] в BendLine с учётом масштаба."""
    seen = set()
    out = []
    for orient, pos in raw:
        if kind == "inner":            # корпус — внутренние вертикальные сгибы
            key = ("L", round(pos, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append(BendLine("left", round(pos * sx, 1), 90, "inner", note="гиб"))
            continue
        # edge: краевой борт — привязать к ближайшей кромке
        if orient == "V":
            edge = "left" if pos < w / 2 else "right"
            off = pos if edge == "left" else (w - pos)
            off *= sx
        else:
            edge = "bottom" if pos < h / 2 else "top"
            off = pos if edge == "bottom" else (h - pos)
            off *= sy
        key = (edge, round(off, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append(BendLine(edge, round(off, 1), 90, "down", nominal=round(off, 1), note="борт"))
    return out


def _build(name, W, H, D, thickness):
    d = _DATA[name]
    part_name, sx, sy, kind, hidden = _spec(W, H, D)[name]
    w0, h0 = d["w"], d["h"]
    part = Part(part_name, int(round(w0 * sx)), int(round(h0 * sy)), 1, thickness)
    part.outline = [(round(x * sx, 2), round(y * sy, 2), b) for x, y, b in d["outline"]]
    part.extra_cuts = [([(round(x * sx, 2), round(y * sy, 2), b) for x, y, b in cut], True)
                       for cut in d["cutouts"]]
    for hx, hy, r in d["holes"]:
        part.cutouts.append(Cutout("circle", hx * sx, hy * sy, radius=r))
    part.bend_lines = _bends(kind, d.get("bends", []), w0, h0, sx, sy) if kind else []
    part.is_hidden_in_assembly = hidden
    return part


class FireCabinet:
    """Пожарный шкаф (навесной). Один чертёж-раскрой = 8 деталей (2 двери на
    выбор: с окном / глухая). Точные контуры с эталона."""
    CODE = "ПШ"

    ORDER = ["КОРПУС", "КРЫШКА-1", "КРЫШКА-2", "ПЛАНКА-бок", "КОСЫНКА",
             "ПАНЕЛЬ-малая", "ДВЕРЬ-окно", "ДВЕРЬ-глухая"]

    @staticmethod
    def build(width=540, height=655, depth=200, thickness=1.2):
        m = Module(name=f"Пожарный шкаф {width}x{height}x{depth}",
                   module_type="Пожарный шкаф",
                   height=height, width=width, depth=depth, thickness=thickness)
        for name in FireCabinet.ORDER:
            m.add_part(_build(name, width, height, depth, thickness))
        m.cut_layout = True
        return m
