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
        # Пять модулей кухонного комплекса К 01.00 (сверх них в реестре могут
        # быть другие изделия, напр. электрошкафы — их проверяем ниже отдельно).
        KITCHEN = {"section_drawers", "section_sink", "section_grill", "apron", "hood"}
        assert KITCHEN <= set(R.REAL_MODULES), "пропал модуль кухонного комплекса"
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
            # Электрошкаф — другой производитель/станок: аддитивная модель гиба
            # (вычет ≈ 0, offset == nominal), калибровка по своему эталону
            # (см. core/electrical_cabinet). Инвариант кухонного цеха к нему
            # не применяется — правится, когда придут параметры станка.
            if key.startswith("ecab"):
                continue
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


class TestElectricalCabinet:
    """
    Электрошкаф 400x445x150 (1.2мм) — калибровка по эталону мастера
    400х445.dxf. Дверь-развёртка эталона = 430.5 x 471 (все три варианта).
    Тест держит совпадение размеров при будущих правках.
    """

    def test_шкаф_собирается_из_10_деталей(self):
        # Единое изделие: 7 общих деталей + 3 двери = 10 (как в эталоне).
        from core import real_modules as R
        m = R.build("ecab")
        assert getattr(m, "cut_layout", False), "должен быть флаг единого раскроя"
        assert len(m.parts) == 10, f"ожидалось 10 деталей, получено {len(m.parts)}"
        names = [p.name for p in m.parts]
        assert any("Корпус" in n for n in names)
        assert any("Монтажная" in n for n in names)
        assert sum("Дверь" in n for n in names) == 3, "должно быть 3 двери на выбор"
        assert sum("Крышка" in n for n in names) == 2
        assert sum("Полоска" in n for n in names) == 2

    def test_развёртка_двери_совпадает_с_эталоном(self):
        # Эталон мастера: дверь 430.5 x 471. Аддитивная модель даёт 431 x 471.
        from core.electrical_cabinet import build_door
        for dt in ("blank", "small", "big"):
            d = build_door(400, 445, 1.2, dt)
            assert d.width == pytest.approx(430.5, abs=1.0), \
                f"дверь[{dt}] ширина {d.width} != эталон 430.5"
            assert d.height == pytest.approx(471.0, abs=1.0), \
                f"дверь[{dt}] высота {d.height} != эталон 471.0"

    def test_большое_окно_270x330(self):
        # Эталон большого окна: вырез ~270 x 330 при типовом шкафе.
        from core.electrical_cabinet import build_door
        d = build_door(400, 445, 1.2, "big")
        rects = [c for c in d.cutouts if c.shape == "rect"]
        assert rects, "у двери с большим окном нет прямоугольного выреза"
        win = rects[0]
        assert win.width == pytest.approx(270, abs=2)
        assert win.height == pytest.approx(330, abs=2)

    def test_малое_окно_квадратное_точки_по_серединам(self):
        # Эталон: малое окно КВАДРАТНОЕ, 4 отверстия на серединах граней
        # (а не прямоугольник с точками по углам). Проверяем на вытянутом шкафе.
        from core.electrical_cabinet import build_door
        d = build_door(200, 300, 1.2, "small")
        win = [c for c in d.cutouts if c.shape == "rect"][0]
        assert win.width == pytest.approx(win.height, abs=0.5), "малое окно должно быть квадратным"
        holes = [c for c in d.cutouts if c.shape == "circle"]
        assert len(holes) == 4
        # Каждое отверстие лежит на оси окна (X=центр ИЛИ Y=центр) -> середина грани
        for c in holes:
            on_v = abs(c.x - win.x) < 0.5      # на вертикальной оси (верх/низ)
            on_h = abs(c.y - win.y) < 0.5      # на горизонтальной оси (лево/право)
            assert on_v or on_h, "отверстие окна должно быть на середине грани, не в углу"

    def test_окно_не_вылезает_за_дверь(self):
        # Баг-регресс: на мелком шкафу окно должно уменьшаться и помещаться
        # внутрь двери с отступом от краёв, а не быть больше двери.
        from core.electrical_cabinet import build_door
        for W, H in [(200, 300), (250, 350), (400, 445)]:
            for dt in ("big", "small"):
                d = build_door(W, H, 1.2, dt)
                for c in d.cutouts:
                    if c.shape == "rect":
                        assert c.x - c.width / 2 >= 5, f"{W}x{H}/{dt}: окно за левым краем"
                        assert c.x + c.width / 2 <= d.width - 5, f"{W}x{H}/{dt}: окно за правым краем"
                        assert c.y - c.height / 2 >= 5, f"{W}x{H}/{dt}: окно за низом"
                        assert c.y + c.height / 2 <= d.height - 5, f"{W}x{H}/{dt}: окно за верхом"

    def test_экспорт_обходит_занятый_файл(self, tmp_path):
        # Если Раскрой.dxf открыт в АвтоКАД (Permission denied) — экспорт не
        # падает, а сохраняет копию с меткой времени.
        import os
        from core.dxf_exporter import DXFExporter

        class FakeDoc:
            def saveas(self, fn):
                if os.path.basename(fn) == "Раскрой.dxf":
                    raise PermissionError("файл открыт")
                open(fn, "w").close()

        target = str(tmp_path / "Раскрой.dxf")
        out = DXFExporter._safe_saveas(FakeDoc(), target)
        assert out != target, "должен сохранить под другим именем"
        assert out.endswith(".dxf") and os.path.exists(out)

    def test_отверстия_панели_внутри_детали(self):
        # Баг-регресс: отверстия монт. панели не должны уезжать за материал
        # (в угловые лапки) на маленьком шкафу.
        from core.electrical_cabinet import build_panel
        for W, H in [(200, 300), (250, 350), (400, 445)]:
            p = build_panel(W, H, 1.2)
            for c in p.cutouts:
                assert c.radius <= c.x <= p.width - c.radius, \
                    f"{W}x{H}: отверстие по X вне детали ({c.x})"
                assert c.radius <= c.y <= p.height - c.radius, \
                    f"{W}x{H}: отверстие по Y вне детали ({c.y})"

    def test_раскрой_в_формате_мастера(self, tmp_path):
        # Единый DXF-раскрой: голая геометрия на слое "0" + метки гиба на
        # тонком слое, БЕЗ текста/размеров/рамки (как эталон мастера).
        import ezdxf
        from core.electrical_cabinet import ElectricalCabinet
        from core.dxf_exporter import DXFExporter

        parts = ElectricalCabinet.showcase_parts(400, 445, 150, 1.2)
        # 7 общих деталей (корпус, 2 крышки, панель, 2 полоски, кронштейн) + 3 двери
        assert len(parts) == 10, "showcase = 7 общих деталей + 3 двери"

        path = str(tmp_path / "раскрой.dxf")
        DXFExporter.export_cut_layout(parts, path)
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()

        layers = {e.dxf.layer for e in msp}
        assert "0" in layers, "контур реза должен быть на слое 0"
        assert DXFExporter.THIN_BEND_LAYER in layers, "нет тонкого слоя гиба"

        # Рез на слое "0" — только геометрия, БЕЗ текста и размеров (чистый рез)
        cut = [e for e in msp if e.dxf.layer == "0"]
        cut_types = {e.dxftype() for e in cut}
        assert "TEXT" not in cut_types and "MTEXT" not in cut_types, \
            "на слое реза не должно быть текста"
        assert "DIMENSION" not in cut_types, "на слое реза не должно быть размеров"

        # Подписи размеров — есть, но на ОТДЕЛЬНОМ слое (человеку, не станку)
        labels = [e for e in msp if e.dxf.layer == "ПОДПИСИ"]
        assert labels and all(e.dxftype() == "TEXT" for e in labels), \
            "подписи деталей должны быть на слое ПОДПИСИ"

        # Без аннотаций слой ПОДПИСИ не создаётся (рез абсолютно голый)
        path2 = str(tmp_path / "раскрой_голый.dxf")
        DXFExporter.export_cut_layout(parts, path2, annotate=False)
        doc2 = ezdxf.readfile(path2)
        assert not any(e.dxftype() in ("TEXT", "MTEXT") for e in doc2.modelspace()), \
            "annotate=False -> раскрой без текста вообще"