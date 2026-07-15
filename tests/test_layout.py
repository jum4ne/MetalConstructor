# -*- coding: utf-8 -*-
"""
ВЁРСТКА ЛИСТА: текст не должен налезать сам на себя.

Заказчик прислал скрин: строки таблицы гибов наехали друг на друга,
номера позиций на разнесённом виде слиплись в кашу. Глазами это видно
сразу, а тестами не ловилось - вот и тест.

Как работает: подменяем drawString/drawCentredString у reportlab и
собираем ПРЯМОУГОЛЬНИКИ всех строк. Важно: учитываем translate/rotate,
иначе повёрнутый текст (вертикальные размеры) выглядит как куча строк
в одной точке и даёт ложные срабатывания.
"""
import math
import pytest

from reportlab.pdfgen import canvas as pc
import core.technical_drawing as TD


def _mul(a, b):
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


class _Recorder:
    """Перехватывает вывод текста и запоминает его реальные габариты"""

    def __init__(self):
        self.pages = []
        self.cur = []
        self.ctm = [(1, 0, 0, 1, 0, 0)]
        self.stack = []
        self._orig = {}

    def __enter__(self):
        r = self
        self._orig = {
            'save': pc.Canvas.saveState, 'rest': pc.Canvas.restoreState,
            'tr': pc.Canvas.translate, 'rot': pc.Canvas.rotate,
            'ds': pc.Canvas.drawString, 'dc': pc.Canvas.drawCentredString,
            'sp': pc.Canvas.showPage,
        }
        o = self._orig

        def saveState(self):
            r.stack.append(r.ctm[-1]); return o['save'](self)

        def restoreState(self):
            if r.stack: r.ctm[-1] = r.stack.pop()
            return o['rest'](self)

        def translate(self, dx, dy):
            r.ctm[-1] = _mul((1, 0, 0, 1, dx, dy), r.ctm[-1])
            return o['tr'](self, dx, dy)

        def rotate(self, ang):
            a = math.radians(ang); c, s = math.cos(a), math.sin(a)
            r.ctm[-1] = _mul((c, s, -s, c, 0, 0), r.ctm[-1])
            return o['rot'](self, ang)

        def rec(canv, x, y, t, centred):
            if not t or not str(t).strip():
                return
            w = canv.stringWidth(str(t), canv._fontname, canv._fontsize)
            h = canv._fontsize
            x0 = x - w / 2 if centred else x
            a, b, c, d, e, f = r.ctm[-1]
            pts = [(x0, y), (x0 + w, y), (x0 + w, y + h), (x0, y + h)]
            gx = [a * px + c * py + e for px, py in pts]
            gy = [b * px + d * py + f for px, py in pts]
            r.cur.append((min(gx), min(gy), max(gx), max(gy), str(t)))

        def ds(self, x, y, t, *a, **k):
            rec(self, x, y, t, False); return o['ds'](self, x, y, t, *a, **k)

        def dc(self, x, y, t, *a, **k):
            rec(self, x, y, t, True); return o['dc'](self, x, y, t, *a, **k)

        def sp(self, *a, **k):
            r.pages.append(r.cur); r.cur = []
            return o['sp'](self, *a, **k)

        pc.Canvas.saveState = saveState
        pc.Canvas.restoreState = restoreState
        pc.Canvas.translate = translate
        pc.Canvas.rotate = rotate
        pc.Canvas.drawString = ds
        pc.Canvas.drawCentredString = dc
        pc.Canvas.showPage = sp
        return self

    def __exit__(self, *exc):
        o = self._orig
        pc.Canvas.saveState = o['save']
        pc.Canvas.restoreState = o['rest']
        pc.Canvas.translate = o['tr']
        pc.Canvas.rotate = o['rot']
        pc.Canvas.drawString = o['ds']
        pc.Canvas.drawCentredString = o['dc']
        pc.Canvas.showPage = o['sp']

    def overlaps(self, pad=0.5):
        def ov(a, b):
            return not (a[2] <= b[0] + pad or b[2] <= a[0] + pad or
                        a[3] <= b[1] + pad or b[3] <= a[1] + pad)
        out = []
        for i, pg in enumerate(self.pages, 1):
            for j in range(len(pg)):
                for k in range(j + 1, len(pg)):
                    if ov(pg[j], pg[k]):
                        out.append((i, pg[j][4], pg[k][4]))
        return out


class TestLayout:

    def test_текст_нигде_не_налезает_сам_на_себя(self):
        from core import real_modules as R
        from core.technical_drawing import TechnicalDrawingExporter as T

        with _Recorder() as rec:
            for key in R.REAL_MODULES:
                T.export(R.build(key))

        bad = rec.overlaps()
        if bad:
            sample = "; ".join(f"стр.{p}: {a[:24]!r}><{b[:24]!r}"
                               for p, a, b in bad[:4])
            pytest.fail(f"наложений текста: {len(bad)}. {sample}")

    def test_текст_не_вылезает_за_рамку_листа(self):
        from reportlab.lib.units import mm
        from core import real_modules as R
        from core.technical_drawing import TechnicalDrawingExporter as T

        W, H = 595.27, 841.89
        L, Rt, B, Tp = 20 * mm, W - 5 * mm, 5 * mm, H - 5 * mm

        with _Recorder() as rec:
            for key in R.REAL_MODULES:
                T.export(R.build(key))

        out = []
        for i, pg in enumerate(rec.pages, 1):
            for x0, y0, x1, y1, t in pg:
                if x0 < L - 2 or x1 > Rt + 2 or y0 < B - 2 or y1 > Tp + 2:
                    out.append((i, t))
        assert not out, f"текст за рамкой: {out[:4]}"