# -*- coding: utf-8 -*-
"""
Шрифт обязан РИСОВАТЬ все русские буквы и чертёжные спецсимволы.

История бага: GOSTTypeA.ttf выглядел исправным - в его cmap были коды
всех 66 русских букв. Но cmap - это лишь "код -> ИМЯ глифа"; наличие
КОНТУРА она не гарантирует. У 19 символов контура не было: они были
замаплены на чужие пустые латинские глифы ('Ч' -> "multiply",
'Ё' -> "dieresis", '±' -> ...). reportlab честно рисовал пустоту.

В PDF это давало: "Развёртка" -> "Разв ртка", "НАЗНАЧЕНИЕ" -> "НАЗНА ЕНИЕ",
"±0,5" -> " 0,5", "⌀34" -> " 34". То есть пропадали не только буквы, но и
ДОПУСКИ С ДИАМЕТРАМИ - а это уже цена ошибки в цеху.

Поэтому проверяем именно КОНТУРЫ, а не присутствие в cmap.
"""
import os
import pytest

FONTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "fonts"
)
FIXED = os.path.join(FONTS, "GOSTTypeA-fixed.ttf")

RUS = ("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
       "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")
SPECIAL = "±°⌀×№«»—"

def _unrendered(path):
    """Символы, которые шрифт НЕ нарисует (нет контура)"""
    from fontTools.ttLib import TTFont
    f = TTFont(path)
    cmap = f.getBestCmap()
    glyf = f.get("glyf")
    bad = []
    for ch in RUS + SPECIAL:
        gn = cmap.get(ord(ch))
        if gn is None:
            bad.append(ch)
            continue
        if getattr(glyf[gn], "numberOfContours", 0) == 0:
            bad.append(ch)
    return bad


@pytest.mark.skipif(not os.path.exists(FIXED), reason="нет починенного шрифта")
class TestFont:

    def test_все_русские_буквы_рисуются(self):
        bad = [c for c in _unrendered(FIXED) if c in RUS]
        assert not bad, f"не нарисуются буквы: {''.join(bad)}"

    def test_чертёжные_спецсимволы_рисуются(self):
        # ± (допуск), ⌀ (диаметр), ° (угол), × (размер) - без них чертёж
        # уходит в цех с потерянными допусками.
        bad = [c for c in _unrendered(FIXED) if c in SPECIAL]
        assert not bad, f"не нарисуются спецсимволы: {''.join(bad)}"

    def test_проблемные_символы_из_багрепорта(self):
        # Ровно те, что заметил заказчик на своём PDF.
        bad = _unrendered(FIXED)
        for ch in "ёЧ":
            assert ch not in bad, f"{ch!r} снова не рисуется"

    def test_санитайзер_не_портит_хороший_текст(self):
        # Раньше sanitize() слепо менял «» и № на суррогаты, и в PDF
        # выходило 'Комплекс N1' и 'НПО "Кристалл"'. Теперь он спрашивает
        # у шрифта и не трогает то, что шрифт умеет.
        import core.technical_drawing as TD
        TD._FONT_REGISTERED = False
        TD._SUPPORTED = None
        TD._register_font()
        for txt in ("Развёртка", "НАЗНАЧЕНИЕ", "Допуск ±0,5 мм", "⌀34", "Комплекс №1"):
            assert TD.sanitize(txt) == txt, f"санитайзер испортил {txt!r}"


class TestDrawingLayout:
    """
    Геометрия листа: на чертеже ДЕТАЛИ не должно быть паразитных линий,
    а текст не должен налезать сам на себя.

    Баг из цеха: выноска релиз-прорези велась от угла 'bottom-left' к
    тексту, который рисуется СПРАВА ВВЕРХУ - через всю деталь шла жирная
    ДИАГОНАЛЬ. Завод принял её за линию реза. На изометрии (разнесённый
    вид) наклонные линии законны, а на развёртке детали - нет.
    """

    def _diagonals(self, page):
        import re
        try:
            txt = page.get_contents().get_data().decode('latin-1', errors='replace')
        except Exception:
            return 0
        n = 0
        for a, b, c, d in re.findall(r'([\d.]+) ([\d.]+) m\s+([\d.]+) ([\d.]+) l', txt):
            if abs(float(c) - float(a)) > 60 and abs(float(d) - float(b)) > 60:
                n += 1
        return n

    def test_на_чертежах_деталей_нет_диагоналей(self):
        import pytest
        pypdf = pytest.importorskip("pypdf") if hasattr(pytest, "importorskip") else None
        from pypdf import PdfReader
        from core import real_modules as R
        from core.technical_drawing import TechnicalDrawingExporter as T

        for key in R.REAL_MODULES:
            path = T.export(R.build(key))
            r = PdfReader(path)
            for i, pg in enumerate(r.pages, 1):
                t = pg.extract_text() or ''
                # Изометрия/разнесённый вид - там наклонные ЗАКОННЫ
                if 'разнес' in t.lower() or 'Позиции' in t or 'сборочный' in t.lower():
                    continue
                if 'Развёртка' not in t:
                    continue
                assert self._diagonals(pg) == 0, (
                    f"{key}, лист {i}: на развёртке детали есть диагональ - "
                    f"цех примет её за линию реза"
                )