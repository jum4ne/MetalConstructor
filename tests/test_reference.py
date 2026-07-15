# -*- coding: utf-8 -*-
"""
АВТОТЕСТ ПРОТИВ ЭТАЛОНА МАСТЕРА.

Смысл: программа НЕ копирует DXF мастера, она генерит геометрию сама
по своему правилу. Этот тест сверяет её результат с настоящими
развёртками из КОМПАС. Совпало - правило верное и можно менять размеры.
Не совпало - правило неверное, в цех такое отдавать нельзя.

Эталон лежит в reference/dxf/ (37 развёрток комплекса К 01.00.00.000).
Если папки нет - тесты пропускаются (эталон не обязан быть на проде).
"""
import os
import math
import pytest

from core.geometry import bend_deduction, flat_length
from core import reference_dxf

REF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'reference', 'dxf'
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(REF_DIR),
    reason="нет папки с эталонными развёртками мастера"
)


class TestBendRule:
    """Правило гиба - самое дорогое в программе. Ошибка = брак в цеху."""

    def test_вычет_на_гиб_совпадает_с_чертежом_мастера(self):
        # На чертеже К 01.01.01.007 - Дно мастер САМ напечатал: 2,2
        # (в таблице гибов рядом с "S 1,0"). Это не наша подгонка.
        assert bend_deduction(1.0, 90) == pytest.approx(2.2, abs=0.01)

    def test_борт_20_даёт_плоский_участок_17_8(self):
        # Ключевое следствие: номинальный борт 20мм в развёртке = 17.8мм.
        # Эта длина встречается в развёртках мастера 26 раз.
        flat = 20.0 - bend_deduction(1.0, 90)
        assert flat == pytest.approx(17.8, abs=0.01)

    def test_17_8_реально_есть_в_развёртках_мастера(self):
        refs = reference_dxf.load_all(REF_DIR)
        assert refs, "эталоны не прочитались"
        hits = sum(1 for r in refs.values() if 17.8 in r['lengths'])
        assert hits >= 5, f"плоский борт 17.8 найден лишь в {hits} деталях"

    def test_старая_наивная_формула_ошибается(self):
        # Регресс-защита: если кто-то вернёт "развёртка = габарит + борт + борт",
        # этот тест обязан упасть.
        naive = 457.0 + 20 + 20                       # 497.0
        correct = flat_length([20, 457.0, 20], 1.0)   # 492.6
        assert abs(naive - correct) > 4.0, \
            "наивное сложение и честный расчёт совпали - значит BD потерян"


class TestReferenceGeometry:
    """Сверка габаритов заготовок с DXF мастера."""

    def test_дно_секции_с_ящиками(self):
        refs = reference_dxf.load_all(REF_DIR)
        dno = refs.get('К 01.01.01.007')
        assert dno, "эталон Дно не найден"
        # Габарит развёртки по мастеру
        assert dno['width'] == pytest.approx(495.0, abs=0.2)
        assert dno['height'] == pytest.approx(571.3, abs=0.2)

    def test_ширина_дна_раскладывается_на_язычок_корпус_язычок(self):
        # 19 (язычок) + 457 (корпус, труба L=458) + 19 (язычок) = 495
        assert 19.0 + 457.0 + 19.0 == pytest.approx(495.0, abs=0.1)

    def test_все_эталоны_читаются(self):
        refs = reference_dxf.load_all(REF_DIR)
        assert len(refs) >= 30, f"прочитано лишь {len(refs)} эталонов"
        for code, r in refs.items():
            assert r['width'] > 0 and r['height'] > 0, f"{code}: нулевой габарит"

    def test_ни_одна_настоящая_деталь_не_прямоугольник(self):
        # Обоснование отказа от старой модели Part(w,h): среди настоящих
        # деталей мастера нет НИ ОДНОГО простого прямоугольника (4 отрезка).
        refs = reference_dxf.load_all(REF_DIR)
        rects = [c for c, r in refs.items() if len(r['lines']) <= 4]
        assert not rects, f"вдруг нашлись прямоугольники: {rects}"


class TestRealModules:
    """
    Секция с выдвижными ящиками, сгенерированная программой, обязана
    совпасть с развёртками мастера. Это главный тест точности:
    расходится - в цех отдавать нельзя.
    """

    MAP = {
        'Дно': 'К 01.01.01.007',
        'Боковая панель': 'К 01.01.01.005',
        'Задняя стенка': 'К 01.01.01.006',
        'Направляющая': 'К 01.01.01.004',
        'Корпус ящика': 'К 01.01.02.001',
        'Панель ящик выдвижной': 'К 01.01.02.002',
        'Декоративная накладка на панель для ящика выдвижного': 'К 01.01.02.003',
    }

    def _all_parts(self, m):
        parts = list(m.parts)
        if m.subassemblies:
            parts += list(m.subassemblies[0].parts)
        return parts

    def test_все_детали_совпали_с_эталоном(self):
        from core.real_modules import SectionDrawers
        refs = reference_dxf.load_all(REF_DIR)
        m = SectionDrawers.build()

        checked = 0
        for p in self._all_parts(m):
            code = self.MAP.get(p.name)
            if not code or code not in refs:
                continue
            r = refs[code]
            mine = sorted([p.width, p.height])
            ref = sorted([r['width'], r['height']])
            assert mine[0] == pytest.approx(ref[0], abs=1.5), \
                f"{p.name}: {mine} vs эталон {ref}"
            assert mine[1] == pytest.approx(ref[1], abs=1.5), \
                f"{p.name}: {mine} vs эталон {ref}"
            checked += 1

        assert checked >= 7, f"сверено лишь {checked} деталей"

    def test_направляющая_есть_и_её_8_штук(self):
        # Именно этой детали не было в прошлой версии - ящики "висели в воздухе".
        from core.real_modules import SectionDrawers
        m = SectionDrawers.build()
        rails = [p for p in m.parts if p.name == 'Направляющая']
        assert rails, "направляющей нет"
        assert rails[0].quantity == 8, f"направляющих {rails[0].quantity}, у мастера 8"

    def test_каркас_совпадает_с_excel_мастера(self):
        from core.real_modules import SectionDrawers
        m = SectionDrawers.build(width=500, depth=600, height=820)
        lens = sorted(t.length for t in m.tubes)
        # Excel мастера: L=820 (стойка), L=458 (пояс Ш), L=493 (пояс Г)
        assert 820 in lens
        assert 458 in lens
        assert 493 in lens

    def test_каркас_параметричен(self):
        # Правило пояс = W - 42 проверено на двух секциях мастера:
        # W=500 -> 458 (ящики), W=1000 -> 958 (мойка)
        from core.real_modules import SectionDrawers
        m = SectionDrawers.build(width=1000)
        lens = [t.length for t in m.tubes]
        assert 958 in lens, "при W=1000 пояс должен стать 958 (как у секции под мойку)"


class TestAllFiveModules:
    """
    ВСЕ 5 модулей комплекса К 01.00.00.000, сгенерированные программой,
    обязаны совпасть с развёртками мастера. Это главный приёмочный тест.
    """

    DNO = {'section_drawers': 'К 01.01.01.007',
           'section_sink': 'К 01.02.01.006',
           'section_grill': 'К 01.03.01.011'}
    BACK = {'section_sink': 'К 01.02.01.007',
            'section_grill': 'К 01.03.01.012'}
    MAP = {
        'Панель боковая': 'К 01.02.01.005',
        'Направляющая': 'К 01.01.01.004',
        'Боковая панель': 'К 01.01.01.005',
        'Задняя стенка': 'К 01.01.01.006',
        'Корпус ящика': 'К 01.01.02.001',
        'Панель ящик выдвижной': 'К 01.01.02.002',
        'Декоративная накладка на панель для ящика выдвижного': 'К 01.01.02.003',
        'Панель на фасад с ручкой': 'К 01.02.02.001',
        'Панель декоративная на фасад': 'К 01.02.02.002',
        'Панель боковая правая': 'К 01.03.01.010',
        'Панель боковая левая': 'К 01.03.01.010-01',
        'Декоративная накладка': 'К 01.03.02.001',
        'Корпус для золы. Задняя часть': 'К 01.03.03.001',
        'Корпус для золы. Боковая правая': 'К 01.03.03.002',
        'Корпус для золы. Боковая левая': 'К 01.03.03.002-01',
        'Корпус для золы. Передняя часть': 'К 01.03.03.003',
        'Корпус ящика для золы': 'К 01.03.04.001',
        'Фасад выдвижного ящика для золы': 'К 01.03.04.002',
        'Продольная направляющая': 'К 01.03.05.001',
        'Поперечная направляющая': 'К 01.03.05.002',
        'Боковая стенка мангала': 'К 01.03.05.003',
        'Передняя стенка мангала': 'К 01.03.05.004',
        'Накладка': 'К 01.03.06.001',
        'Стенка мангала': 'К 01.03.06.002',
        'Стенка мангала №2': 'К 01.03.06.002-01',
        'Защитный фартук': 'К 01.04.00.001',
        'Проушина для крепления. S=2мм': 'К 01.04.00.004',
        'Деталь №1. S=1. Передняя': 'К 01.05.00.001',
        'Деталь №2. S=1. Левая': 'К 01.05.00.002',
        'Деталь №2. S=1. Правая': 'К 01.05.00.002-01',
        'Деталь №3. S=1. Задняя': 'К 01.05.00.003',
        'Деталь №4': 'К 01.05.00.004',
    }

    def _code(self, key, part):
        if part.name == 'Дно':
            return self.DNO.get(key)
        if part.name == 'Панель задняя':
            return self.BACK.get(key)
        return self.MAP.get(part.name)

    def test_все_детали_всех_модулей_совпали(self):
        from core import real_modules as R
        refs = reference_dxf.load_all(REF_DIR)
        checked = 0
        for key in R.REAL_MODULES:
            m = R.build(key)
            parts = list(m.parts) + [p for s in m.subassemblies for p in s.parts]
            for p in parts:
                code = self._code(key, p)
                if not code or code not in refs:
                    continue
                r = refs[code]
                mine = sorted([p.width, p.height])
                ref = sorted([r['width'], r['height']])
                assert mine[0] == pytest.approx(ref[0], abs=1.5), \
                    f"{key}/{p.name}: {mine} vs эталон {ref}"
                assert mine[1] == pytest.approx(ref[1], abs=1.5), \
                    f"{key}/{p.name}: {mine} vs эталон {ref}"
                checked += 1
        assert checked >= 40, f"сверено лишь {checked} деталей"

    def test_все_пять_модулей_собираются(self):
        from core import real_modules as R
        assert len(R.REAL_MODULES) == 5
        for key in R.REAL_MODULES:
            m = R.build(key)
            assert m.parts, f"{key}: нет деталей"

    def test_каркас_мангала_на_стойках_40х40(self):
        # Мангал несёт гранит и огонь -> стойки толще, и вычет другой:
        # 2*40+2 = 82, поэтому пояс 1000-82 = 918 (а не 958, как у мойки).
        from core import real_modules as R
        m = R.build('section_grill')
        posts = [t for t in m.tubes if 'стойка' in (t.note or '')]
        assert posts and posts[0].profile_w == 40 and posts[0].profile_h == 40
        assert any(t.length == 918 for t in m.tubes), "пояс мангала должен быть 918"

    def test_каркас_мойки_совпал_с_excel(self):
        from core import real_modules as R
        m = R.build('section_sink')
        lens = [t.length for t in m.tubes]
        assert 958 in lens and 493 in lens and 820 in lens

    def test_фартук_скрыт_как_на_чертеже_мастера(self):
        # На сборочном мастера ПРЯМО написано:
        # "Деталь К 01.04.00.001 - Защитный фартук - Скрыта"
        from core import real_modules as R
        m = R.build('apron')
        panel = [p for p in m.parts if p.name == 'Защитный фартук'][0]
        assert panel.is_hidden_in_assembly is True


class TestParametric:
    """
    ГЛАВНОЕ, ЗАЧЕМ НУЖНА ПРОГРАММА: модуль под заказ клиента.
    Меняем Ш/Г/В - размеры деталей и труб ОБЯЗАНЫ пересчитаться.

    Был баг: размеры деталей стояли КОНСТАНТАМИ с эталона, и при смене
    габаритов файлы выходили одинаковые. Эти тесты его ловят.
    """

    # Детали фиксированного размера - они НЕ должны меняться за габаритом:
    # это фурнитура/узлы, у мастера они тоже одинаковые в любой секции.
    FIXED = {
        'Проушина для крепления. S=2мм',
        'Корпус для золы. Задняя часть', 'Корпус для золы. Боковая правая',
        'Корпус для золы. Боковая левая', 'Корпус для золы. Передняя часть',
        'Корпус ящика для золы', 'Фасад выдвижного ящика для золы',
        'Продольная направляющая', 'Боковая стенка мангала',
    }

    def test_смена_ширины_меняет_детали(self):
        from core import real_modules as R
        for key in R.REAL_MODULES:
            a = R.build(key)
            b = R.build(key, width=a.width + 300)
            pa = {p.name: (p.width, p.height) for p in a.parts}
            pb = {p.name: (p.width, p.height) for p in b.parts}
            movable = [n for n in pa if n not in self.FIXED]
            changed = [n for n in movable if pa[n] != pb[n]]
            assert changed, (
                f"{key}: при смене ширины НИ ОДНА деталь не изменилась - "
                f"значит размеры захардкожены"
            )

    def test_смена_глубины_меняет_детали(self):
        from core import real_modules as R
        for key in ('section_drawers', 'section_sink', 'section_grill'):
            a = R.build(key)
            b = R.build(key, depth=a.depth + 100)
            pa = {p.name: (p.width, p.height) for p in a.parts}
            pb = {p.name: (p.width, p.height) for p in b.parts}
            changed = [n for n in pa if n not in self.FIXED and pa[n] != pb[n]]
            assert changed, f"{key}: глубина не влияет на детали"

    def test_смена_высоты_меняет_стойки(self):
        from core import real_modules as R
        for key in ('section_drawers', 'section_sink', 'section_grill'):
            a = R.build(key)
            b = R.build(key, height=a.height + 80)
            la = sorted(t.length for t in a.tubes)
            lb = sorted(t.length for t in b.tubes)
            assert la != lb, f"{key}: высота не влияет на каркас"

    def test_каркас_пересчитывается_по_формуле(self):
        # пояс = W - 2*стойка - 2 (проверено на трёх секциях мастера)
        from core import real_modules as R
        m = R.build('section_drawers', width=900)
        assert 900 - 2 * 20 - 2 in [t.length for t in m.tubes]   # 858
        g = R.build('section_grill', width=1200)
        assert 1200 - 2 * 40 - 2 in [t.length for t in g.tubes]  # 1118

    def test_развёртка_дна_следует_формуле(self):
        # развёртка = корпус + 2*борт; проверено: 457+38=495, 956+40=996, 916+80=996
        from core.real_modules import SectionDrawers, SectionSink, SectionGrill
        assert SectionDrawers.SCHEME.blank_w(500) == 495
        assert SectionSink.SCHEME.blank_w(1000) == 996
        assert SectionGrill.SCHEME.blank_w(1000) == 996

    def test_фартук_сохраняет_свою_высоту(self):
        # Был баг: build() навязывал height=820 (высоту секции), затирая
        # родную высоту фартука 750.
        from core import real_modules as R
        m = R.build('apron')
        assert m.height == 750, "фартуку навязали чужую высоту"


class TestBendSemantics:
    """
    offset линии гиба - это ПОЗИЦИЯ ЛИНИИ НА РАЗВЁРТКЕ, а не высота борта.

    Был баг: местами в offset клали номинал (20), местами позицию (17.8).
    Цех, прочитав "отступ 20 мм", отмерил бы 20 от кромки и загнул бы не
    там - борт вышел бы 22.2 вместо 20. Запоротая деталь.
    """

    def test_offset_это_позиция_линии_а_не_борт(self):
        from core import real_modules as R
        from core.geometry import bend_deduction
        BD = bend_deduction(1.0, 90)
        for key in R.REAL_MODULES:
            m = R.build(key)
            parts = list(m.parts) + [p for s in m.subassemblies for p in s.parts]
            for p in parts:
                for b in p.bend_lines:
                    if b.direction == 'seam' or not getattr(b, 'nominal', 0):
                        continue
                    bd = bend_deduction(p.thickness, b.angle)
                    assert b.offset == pytest.approx(b.nominal - bd, abs=0.05), (
                        f"{key}/{p.name}/{b.edge}: offset={b.offset} "
                        f"не равен nominal({b.nominal}) - вычет({bd})"
                    )

    def test_борт_20_гнётся_по_линии_17_8(self):
        from core import real_modules as R
        m = R.build('section_drawers')
        dno = [p for p in m.parts if p.name == 'Дно'][0]
        tops = [b for b in dno.bend_lines if b.edge == 'top']
        assert tops, "нет верхнего гиба"
        b = tops[0]
        assert b.nominal == 20.0
        assert b.offset == pytest.approx(17.8, abs=0.05), (
            "линия гиба должна стоять на 17.8, иначе цех загнёт не там"
        )