"""
Чтение эталонных развёрток мастера (DXF из КОМПАС) для АВТОПРОВЕРКИ.

Этот модуль НЕ участвует в производстве документации. Его единственная
задача - служить эталоном в тестах: программа генерит деталь по своему
правилу, а тест сверяет её с DXF мастера. Совпало - правило верное.

Почему не ezdxf: он тянется из сети, а на проде может не быть интернета.
Формат DXF - это просто пары (код, значение), парсер занимает 60 строк
и не имеет зависимостей.
"""
import math
import os


def _pairs(path):
    txt = open(path, 'rb').read().decode('cp1251', errors='replace')
    lines = txt.split('\n')
    i = 0
    while i + 1 < len(lines):
        c = lines[i].strip()
        if not c or not c.lstrip('-').isdigit():
            i += 1
            continue
        v = lines[i + 1].strip()
        i += 2
        yield int(c), v


def read_entities(path):
    """Сущности из секции ENTITIES"""
    ents, cur, insec = [], None, False
    seq = list(_pairs(path))
    for k, (code, val) in enumerate(seq):
        if code == 2 and val == 'ENTITIES':
            insec = True
            continue
        if code == 0 and val == 'ENDSEC' and insec:
            if cur:
                ents.append(cur)
            cur, insec = None, False
            continue
        if not insec:
            continue
        if code == 0:
            if cur:
                ents.append(cur)
            cur = {'type': val, 'raw': {}}
            continue
        if cur is not None:
            cur['raw'].setdefault(code, []).append(val)
    if cur:
        ents.append(cur)
    return ents


def _num(e, code, i=0):
    v = e['raw'].get(code)
    if not v or i >= len(v):
        return None
    try:
        return float(v[i])
    except ValueError:
        return None


def read_flat_pattern(path):
    """
    Прочитать развёртку: габарит, отрезки, дуги, набор характерных длин.

    Возвращает dict:
        width, height  - габарит заготовки (bbox), мм
        lines          - [(x1,y1,x2,y2)]
        arcs           - [(cx,cy,r,a1,a2)]
        lengths        - Counter длин отрезков (округл. до 0.01)
    """
    ents = read_entities(path)
    xs, ys, lines, arcs = [], [], [], []

    for e in ents:
        t = e['type']
        if t == 'LINE':
            x1, y1 = _num(e, 10), _num(e, 20)
            x2, y2 = _num(e, 11), _num(e, 21)
            if None not in (x1, y1, x2, y2):
                lines.append((x1, y1, x2, y2))
                xs += [x1, x2]
                ys += [y1, y2]
        elif t == 'ARC':
            cx, cy, r = _num(e, 10), _num(e, 20), _num(e, 40)
            a1, a2 = _num(e, 50), _num(e, 51)
            if None not in (cx, cy, r):
                arcs.append((cx, cy, r, a1, a2))
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]

    from collections import Counter
    lengths = Counter(
        round(math.hypot(x2 - x1, y2 - y1), 2) for x1, y1, x2, y2 in lines
    )

    return {
        'width': (max(xs) - min(xs)) if xs else 0.0,
        'height': (max(ys) - min(ys)) if ys else 0.0,
        'lines': lines,
        'arcs': arcs,
        'lengths': lengths,
        'name': os.path.basename(path).replace('.dxf', ''),
    }


def load_all(folder):
    """Прочитать все эталонные развёртки из папки"""
    out = {}
    if not os.path.isdir(folder):
        return out
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith('.dxf'):
            continue
        fp = read_flat_pattern(os.path.join(folder, fn))
        # Ключ - обозначение вида "К 01.01.01.007"
        code = fn.split(' - ')[0].strip()
        out[code] = fp
    return out