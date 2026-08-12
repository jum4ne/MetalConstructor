# -*- coding: utf-8 -*-
"""
Дочинить чертёжный шрифт GOSTTypeA-fixed.ttf: у него отсутствуют контуры
у части пунктуации ( [ ] { } < > / \ ; · и др. — из-за этого в PDF
пропадали открывающие скобки и слэши во всём комплекте чертежей.

Скрипт КОПИРУЕТ недостающие глифы из полноценного шрифта-донора (Arial),
масштабируя их под unitsPerEm ГОСТ-шрифта, и НЕ трогает остальные глифы —
внешний вид «под ГОСТ» сохраняется. Идемпотентен.
"""
import os
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen

FONTS = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
TARGET = os.path.normpath(os.path.join(FONTS, "GOSTTypeA-fixed.ttf"))
DONOR = "C:/Windows/Fonts/arial.ttf"

# Пунктуация/символы, которые ДОЛЖНЫ рисоваться в чертёжных надписях.
CANDIDATES = "()[]{}<>/\|;·%&@#+=_~^*!?\"'"


def has_contour(font, cp):
    cmap = font.getBestCmap()
    if cp not in cmap:
        return False
    glyf = font.get("glyf")
    if glyf is None:
        return True
    g = glyf[cmap[cp]]
    return getattr(g, "numberOfContours", 0) != 0


def main():
    tgt = TTFont(TARGET)
    don = TTFont(DONOR)
    t_upm = tgt["head"].unitsPerEm
    d_upm = don["head"].unitsPerEm
    scale = t_upm / d_upm
    d_cmap = don.getBestCmap()
    d_gs = don.getGlyphSet()
    glyf = tgt["glyf"]
    hmtx = tgt["hmtx"]
    order = tgt.getGlyphOrder()

    added = []
    for ch in CANDIDATES:
        cp = ord(ch)
        if has_contour(tgt, cp):
            continue
        if cp not in d_cmap:
            continue
        gname = d_cmap[cp]
        pen = TTGlyphPen(None)
        d_gs[gname].draw(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        glyph = pen.glyph()
        newname = "uniFIX%04X" % cp
        glyf[newname] = glyph
        adv = int(round(don["hmtx"][gname][0] * scale))
        hmtx[newname] = (adv, 0)
        if newname not in order:
            order.append(newname)
        for tbl in tgt["cmap"].tables:
            if tbl.isUnicode() or tbl.platformID == 3:
                tbl.cmap[cp] = newname
        added.append(ch)

    tgt.setGlyphOrder(order)
    # Пересобрать, чтобы обновились maxp.numGlyphs и т.п.
    tgt.save(TARGET)
    print("Добавлены глифы:", " ".join(added) if added else "(нет — уже целый)")


if __name__ == "__main__":
    main()
