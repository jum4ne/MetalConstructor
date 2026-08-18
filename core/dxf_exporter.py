"""
Экспорт в DXF с улучшенным раскроем.
Работает с любым модулем (Cabinet, Tumba, SinkCabinet, GrillCabinet, Countertop),
т.к. все они — наследники/экземпляры Module с одинаковым интерфейсом .parts
"""
import ezdxf
from ezdxf.enums import TextEntityAlignment
import os
import time
import json
from config import Config
from core.order_paths import order_file
from core.rules import Rules
from core.part_splitter import split_part_if_needed
from core.nesting import pack_parts
from core.sheet_metal import (get_corners_needing_relief, build_outline_points,
                              rotate_corners, get_corner_cuts, rotate_corner_cuts)


# Символы вне cp1251 в DXF R2000 превращаются в escape \U+XXXX и читаются в
# CAM цеха как мусор. Текст в модель попадает из билдеров (метки вырезов,
# примечания к гибам), поэтому чистим ЛЮБОЙ текст перед записью в DXF.
_DXF_REPL = {
    '×': 'x', '⌀': 'диам.', '↻': '(поворот 90)',
    '—': '-', '–': '-', '−': '-', '…': '...',
}


def _dxf_safe(s):
    """cp1251-безопасный текст для DXF R2000 (без escape-последовательностей)."""
    if not isinstance(s, str):
        return s
    for k, v in _DXF_REPL.items():
        s = s.replace(k, v)
    # Страховка: всё, что не влезает в cp1251, заменяем на '?', а не на escape.
    return s.encode('cp1251', 'replace').decode('cp1251')


class DXFExporter:
    """Экспорт чертежей в AutoCAD DXF"""

    def __init__(self):
        Config.init_dirs()

    @staticmethod
    def export(module, optimize=True):
        """
        Экспорт модуля в DXF

        Args:
            module: объект Module (или Cabinet) с деталями
            optimize: использовать оптимизацию раскроя
        """
        Config.init_dirs()

        # Электрошкаф (и любой модуль с флагом cut_layout) выгружается ЕДИНЫМ
        # раскроем в формате мастера (голая геометрия всех деталей в ряд на
        # слое "0" + метки гиба), а НЕ кухонной раскладкой на лист.
        if getattr(module, "cut_layout", False):
            return DXFExporter._export_cut_layout_order(module)

        # Всё по заказу - в одну папку cad/orders/дата_заказчик_изделие/
        version = time.strftime("%Y%m%d_%H%M%S")
        filename = order_file(module, "Раскрой.dxf")

        # Версия формата R2000 (AC1015) и кодовая страница ANSI_1251 - взято
        # НЕ из памяти, а напрямую из заголовка реального референсного DXF
        # (проверено построчным разбором $ACADVER/$DWGCODEPAGE). До формата
        # R2007 включительно DXF хранит текст через кодовую страницу, а не
        # через UTF-8 - отсюда и cp1251 у референсных файлов.
        doc = ezdxf.new("R2000", setup=True)
        # Кириллица в DXF R2000 хранится в кодовой странице, а не в UTF-8.
        # МАЛО поставить только заголовок $DWGCODEPAGE: ezdxf кэширует
        # encoding отдельно и без явного doc.encoding='cp1251' пишет текст в
        # cp1252, а кириллицу — как escape-последовательности \U+04XX. Тогда
        # CAM-софт цеха показывает имена слоёв/деталей как "\U+0421..." вместо
        # «Системный слой». Ставим ОБА, чтобы файл был байт-в-байт как у мастера.
        doc.header['$DWGCODEPAGE'] = 'ANSI_1251'
        doc.encoding = 'cp1251'
        msp = doc.modelspace()

        # Слои
        doc.layers.add("SHEET", color=1)      # красный - контур листа
        # "Системный слой" - имя, цвет (7) и тип линии (Continuous) взяты
        # напрямую из референсного DXF (не выдумано) - это слой основного
        # контура реза детали, совместимый с тем, что ожидает раскройщик/
        # CAM-система, уже знакомая с файлами от стороннего производителя.
        doc.layers.add("Системный слой", color=7, linetype="CONTINUOUS")
        doc.layers.add("TEXT", color=7)       # белый - текст (доп. слой сверх референса)
        doc.layers.add("DIMENSIONS", color=3) # зелёный - размеры (доп. слой сверх референса)
        doc.layers.add("CUTOUT", color=6)     # маджента - вырезы (мойка, гриль, вентиляция)
        doc.layers.add("BEND", color=4)       # голубой - линии гиба (доп. слой сверх референса -
                                               # в самом референсе линии гиба на DXF не показаны)

        if optimize:
            sheets_data = DXFExporter._optimize_layout(module.parts)
        else:
            sheets_data = DXFExporter._simple_layout(module.parts)

        y_sheet_offset = 0

        for sheet_num, sheet in enumerate(sheets_data, 1):
            sheet_w = sheet['width']
            sheet_h = sheet['height']

            msp.add_lwpolyline(
                [
                    (0, y_sheet_offset),
                    (sheet_w, y_sheet_offset),
                    (sheet_w, y_sheet_offset + sheet_h),
                    (0, y_sheet_offset + sheet_h),
                    (0, y_sheet_offset)
                ],
                dxfattribs={'layer': 'SHEET', 'color': 1}
            )

            msp.add_text(
                f"ЛИСТ {sheet_num}",
                dxfattribs={'layer': 'TEXT', 'height': 50, 'color': 7}
            ).set_placement((sheet_w / 2, y_sheet_offset + sheet_h + 100),
                          align=TextEntityAlignment.MIDDLE_CENTER)

            for i, part_data in enumerate(sheet['parts'], 1):
                DXFExporter._draw_part(msp, part_data, offset_y=y_sheet_offset, part_number=i)

            y_sheet_offset += sheet_h + 300

        # Обойти занятый файл, если DXF открыт в АвтоКАД (Permission denied).
        filename = DXFExporter._safe_saveas(doc, filename)

        report = DXFExporter._create_report(filename, module, sheets_data)

        report_path = order_file(module, "Отчёт раскроя.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        DXFExporter._print_report(report)

        return {
            'dxf_path': filename,
            'report_path': report_path,
            'report': report
        }

    @staticmethod
    def _export_cut_layout_order(module):
        """Выгрузка электрошкафа единым раскроем + отчёт, совместимый с UI."""
        Config.init_dirs()
        parts = list(module.parts)
        # Два раскроя на выбор оператора: с пунктиром линий гиба (как просит
        # цех) и с уголками-метками (как эталон мастера). Рез (слой 0) в обоих
        # одинаковый — различаются только метки гиба на тонком слое.
        # export_cut_layout сам обходит занятый файл и возвращает реальный путь.
        f_dash = DXFExporter.export_cut_layout(
            parts, order_file(module, "Раскрой (пунктир линий гиба).dxf"),
            bend_style='dashed')
        f_corn = DXFExporter.export_cut_layout(
            parts, order_file(module, "Раскрой (уголки-метки).dxf"),
            bend_style='corners')
        filename = f_dash   # основной для отчёта/истории

        report = DXFExporter._cut_layout_report(filename, module, parts)
        report['dxf_files'] = [f_dash, f_corn]
        report_path = order_file(module, "Отчёт раскроя.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except PermissionError:
            report_path = ""   # отчёт занят — не критично, DXF уже сохранён
        DXFExporter._print_report(report)
        return {'dxf_path': filename, 'report_path': report_path, 'report': report}

    @staticmethod
    def _cut_layout_report(filename, module, parts, gap=40):
        """Отчёт для единого раскроя (нет листов — «виртуальный лист» = габарит
        раскладки). Ключи те же, что ждёт UI/история заказов."""
        parts_count = sum(p.quantity for p in parts)
        parts_area = sum(p.area * p.quantity for p in parts)

        total_w = sum(p.width for p in parts) + gap * max(len(parts) - 1, 0)
        max_h = max((p.height for p in parts), default=0)
        sheet_area = total_w * max_h / 1_000_000 if max_h else 0
        usage = (parts_area / sheet_area * 100) if sheet_area else 0

        metal_cost = parts_area * Rules.METAL_PRICE_PER_M2
        work_cost = parts_count * Rules.WORK_PRICE_PER_PART

        agg = {}
        for p in parts:
            key = (p.name, p.width, p.height, p.thickness)
            agg[key] = agg.get(key, 0) + p.quantity

        return {
            'filename': filename,
            'module_name': module.name,
            'module_type': getattr(module, 'module_type', ''),
            'sheets_count': 1,
            'parts_count': parts_count,
            'split_parts_count': 0,
            'sheet_area_m2': round(sheet_area, 3),
            'parts_area_m2': round(parts_area, 3),
            'usage_percent': round(usage, 2),
            'waste_percent': round(100 - usage, 2),
            'metal_cost_rub': round(metal_cost, 2),
            'work_cost_rub': round(work_cost, 2),
            'total_cost_rub': round(metal_cost + work_cost, 2),
            'parts': [
                {'name': k[0], 'width': k[1], 'height': k[2], 'thickness': k[3], 'quantity': v}
                for k, v in agg.items()
            ],
        }

    @staticmethod
    def export_parts_separately(module, out_dir=None):
        """
        Отдельный DXF на КАЖДУЮ деталь - как поставляет мастер (папка
        «развертки dxf»: один файл = одна деталь).

        В отличие от общего раскроя, здесь файл содержит ТОЛЬКО геометрию
        реза (контур + отверстия) на слое «Системный слой», без текста,
        линий гиба и рамки листа - точно как в эталонных файлах мастера.
        Такой файл можно отдать в CAM как есть.

        Returns: {'dir': путь_к_папке, 'files': [пути], 'count': N}
        """
        Config.init_dirs()
        if out_dir is None:
            # Развёртки кладём подпапкой внутрь папки заказа, рядом с раскроем
            out_dir = order_file(module, "Развёртки")
        os.makedirs(out_dir, exist_ok=True)

        parts = getattr(module, "all_parts", None) or module.parts
        files = []
        for idx, part in enumerate(parts, 1):
            doc = ezdxf.new("R2000", setup=True)
            doc.header['$DWGCODEPAGE'] = 'ANSI_1251'
            doc.encoding = 'cp1251'          # см. комментарий в export()
            doc.layers.add("Системный слой", color=7, linetype="CONTINUOUS")
            msp = doc.modelspace()

            # Контур (со скруглениями/надрезами, если заданы) + вырезы + доп.
            # прорези — общий рисовальщик. Слой реза "Системный слой" (формат
            # per-part файлов кухонного мастера), без меток гиба (как было).
            DXFExporter._draw_bare_part(msp, part, 0, 0, with_bend_marks=False,
                                        cut_layer="Системный слой")

            fname = _dxf_safe(f"{idx:02d} - {part.name}")
            fname = "".join(ch for ch in fname if ch not in '\\/:*?"<>|').strip()
            path = os.path.join(out_dir, f"{fname}.dxf")
            doc.saveas(path)
            files.append(path)

        return {'dir': out_dir, 'files': files, 'count': len(files)}

    @staticmethod
    def _safe_saveas(doc, filename):
        """
        Сохранить DXF, а если файл ЗАНЯТ (открыт в АвтоКАД/КОМПАС — самая
        частая причина Permission denied при повторном раскрое) — записать
        рядом копию с меткой времени, чтобы экспорт не падал. Возвращает
        путь, по которому файл реально сохранён.
        """
        try:
            doc.saveas(filename)
            return filename
        except PermissionError:
            base, ext = os.path.splitext(filename)
            alt = f"{base}_{time.strftime('%H%M%S')}{ext}"
            doc.saveas(alt)
            return alt

    # Тонкий слой меток гиба — имя ровно как в эталонных DXF мастера
    # (проверено разбором 400х445.dxf/пожарный.dxf: слой "7-ТОНКАЯ-ТЕКСТ-02",
    # на нём короткие L-штрихи гиба в углах). Контур реза — на слое "0".
    THIN_BEND_LAYER = "7-ТОНКАЯ-ТЕКСТ-02"

    @staticmethod
    def export_cut_layout(parts, filename, gap=40, with_bend_marks=True,
                          annotate=True, bend_style='dashed'):
        """
        Единый DXF-раскрой В ФОРМАТЕ МАСТЕРА: голая геометрия всех деталей,
        разложенных в ряд, на слое "0" (контур+вырезы) + метки гиба на тонком
        слое. Рез — только на слоях "0"/тонком (как эталоны мастера).

        annotate=True — добавить подписи (имя детали + габарит) над каждой
        деталью на ОТДЕЛЬНОМ слое "ПОДПИСИ". Это удобно человеку (видно, что
        за деталь и её размер), а для станка слой можно погасить/не резать —
        рез остаётся чистым на слое "0".

        parts:    список Part (напр. ElectricalCabinet.showcase_parts()).
        filename: куда сохранить .dxf.
        Возвращает путь к файлу.
        """
        Config.init_dirs()
        doc = ezdxf.new("R2000", setup=True)
        doc.header['$DWGCODEPAGE'] = 'ANSI_1251'
        doc.encoding = 'cp1251'          # см. комментарий в export()
        # Масштаб штрихов, чтобы пунктир линий гиба был виден на деталях в сотни мм.
        doc.header['$LTSCALE'] = 10
        if DXFExporter.THIN_BEND_LAYER not in doc.layers:
            doc.layers.add(DXFExporter.THIN_BEND_LAYER, color=7,
                           linetype="CONTINUOUS")
        if annotate and "ПОДПИСИ" not in doc.layers:
            doc.layers.add("ПОДПИСИ", color=3)   # зелёный, отдельно от реза
        msp = doc.modelspace()

        x = 0.0
        for part in parts:
            DXFExporter._draw_bare_part(msp, part, x, 0.0, with_bend_marks,
                                        bend_style=bend_style)
            if annotate:
                # Имя + габарит развёртки над деталью, на отдельном слое.
                label = _dxf_safe(f"{part.name}  {int(part.width)}x{int(part.height)}")
                msp.add_text(
                    label, dxfattribs={'layer': 'ПОДПИСИ', 'height': 12, 'color': 3}
                ).set_placement((x, part.height + 15))
            x += part.width + gap

        return DXFExporter._safe_saveas(doc, filename)

    @staticmethod
    def _draw_bends(msp, part, ox, oy, style='dashed'):
        """
        Нарисовать линии гиба на тонком слое в одном из двух стилей:
          'dashed'  — полные ПУНКТИРНЫЕ линии по всем сгибам (как просит цех)
          'corners' — короткие УГОЛКИ-метки в углах краевых бортов (как эталон
                      мастера); внутренние сгибы корпуса ('inner') всё равно
                      рисуются полной линией — уголками их не показать.
        """
        THIN = DXFExporter.THIN_BEND_LAYER
        W, H = part.width, part.height
        bl = [b for b in getattr(part, 'bend_lines', []) if b.direction != 'seam']

        def full(b, dashed):
            if b.edge == 'left':
                p1, p2 = (ox + b.offset, oy), (ox + b.offset, oy + H)
            elif b.edge == 'right':
                p1, p2 = (ox + W - b.offset, oy), (ox + W - b.offset, oy + H)
            elif b.edge == 'top':
                p1, p2 = (ox, oy + H - b.offset), (ox + W, oy + H - b.offset)
            else:
                p1, p2 = (ox, oy + b.offset), (ox + W, oy + b.offset)
            attr = {'layer': THIN}
            if dashed:
                attr['linetype'] = 'DASHED'
            try:
                msp.add_line(p1, p2, dxfattribs=attr)
            except Exception:
                msp.add_line(p1, p2, dxfattribs={'layer': THIN})

        if style == 'dashed':
            for b in bl:
                full(b, True)
            return

        # style == 'corners': внутренние сгибы корпуса НЕ рисуем линией —
        # уголок гиба (полукруглый надрез) уже врезан в контур на кромке
        # (см. _body_outline), как в эталоне. Сплошная линия через деталь была
        # бы неправильной.
        # краевые борта — уголки-метки в углах, где сходятся два борта (эталон)
        off = {b.edge: b.offset for b in bl if b.direction in ('up', 'down')}
        corners_spec = [
            (ox, oy, 1, 1, 'left', 'bottom'), (ox + W, oy, -1, 1, 'right', 'bottom'),
            (ox + W, oy + H, -1, -1, 'right', 'top'), (ox, oy + H, 1, -1, 'left', 'top'),
        ]
        for cx, cy, sx, sy, ex, ey in corners_spec:
            if ex in off and ey in off:
                fx, fy = off[ex], off[ey]
                msp.add_line((cx, cy + sy * fy), (cx + sx * fx, cy + sy * fy),
                             dxfattribs={'layer': THIN})
                msp.add_line((cx + sx * fx, cy), (cx + sx * fx, cy + sy * fy),
                             dxfattribs={'layer': THIN})

    @staticmethod
    def _draw_bare_part(msp, part, ox, oy, with_bend_marks=True, cut_layer='0',
                        bend_style='dashed'):
        """
        Нарисовать одну деталь голой геометрией, как у мастера: контур
        (с угловыми вырезами/скруглениями, если есть) и вырезы на слое реза,
        метки гиба короткими L-штрихами в углах на тонком слое.

        cut_layer — слой контура/вырезов ("0" у электрошкафа, "Системный слой"
        у кухонного комплекта — так у разных мастеров).
        """
        # Приоритет: явный контур детали (со скруглениями/надрезами) ->
        # угловые релиз-вырезы -> простой прямоугольник.
        if getattr(part, 'outline', None):
            pts = [(ox + p[0], oy + p[1], p[2] if len(p) > 2 else 0)
                   for p in part.outline]
            msp.add_lwpolyline(pts, format='xyb', close=True,
                               dxfattribs={'layer': cut_layer, 'color': 7})
        else:
            corners = get_corners_needing_relief(part)
            cuts = get_corner_cuts(part) if corners else {}
            if corners:
                outline = build_outline_points(ox, oy, part.width, part.height, corners, cuts)
            else:
                outline = [(ox, oy), (ox + part.width, oy),
                           (ox + part.width, oy + part.height),
                           (ox, oy + part.height), (ox, oy)]
            msp.add_lwpolyline(outline, dxfattribs={'layer': cut_layer, 'color': 7})

        # Доп. вырезы сложной формы (пазы, прорези): полилинии на слое реза
        for ec in getattr(part, 'extra_cuts', []):
            ec_pts, ec_closed = (ec if isinstance(ec, tuple) else (ec, False))
            pp = [(ox + p[0], oy + p[1], p[2] if len(p) > 2 else 0) for p in ec_pts]
            msp.add_lwpolyline(pp, format='xyb', close=ec_closed,
                               dxfattribs={'layer': cut_layer, 'color': 7})

        # Вырезы (окно, замок, кабельные вводы) — тоже рез, на слое реза
        for ct in getattr(part, 'cutouts', []):
            cx, cy = ox + ct.x, oy + ct.y
            if ct.shape == 'rect':
                hw, hh = ct.width / 2, ct.height / 2
                msp.add_lwpolyline(
                    [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh),
                     (cx - hw, cy + hh), (cx - hw, cy - hh)],
                    dxfattribs={'layer': cut_layer, 'color': 7})
            else:  # circle
                msp.add_circle((cx, cy), ct.radius,
                               dxfattribs={'layer': cut_layer, 'color': 7})

        # Линии гиба на тонком слое (стиль: 'dashed' пунктир / 'corners' уголки).
        if with_bend_marks:
            DXFExporter._draw_bends(msp, part, ox, oy, bend_style)

    @staticmethod
    def _draw_part(msp, part_data, offset_y=0, part_number=1):
        """Нарисовать одну деталь: контур, текст, вырезы, линии гиба"""

        x = part_data['x']
        y = part_data['y'] + offset_y
        w = part_data['width']
        h = part_data['height']
        part = part_data['part']
        rotated = part_data.get('rotated', False)

        # Контур детали. Если у детали есть угловые вырезы (corner_relief) -
        # рисуем не простой прямоугольник, а контур со срезанными углами,
        # там где два смежных загнутых борта иначе мешали бы друг другу.
        corners = get_corners_needing_relief(part)
        cuts = get_corner_cuts(part) if corners else {}
        if rotated and corners:
            corners = rotate_corners(corners)
            cuts = rotate_corner_cuts(cuts)

        if corners:
            # Вырез в углу — прямоугольник до линий гиба смежных бортов:
            # без него борта при гибке упираются друг в друга (проверено по
            # эталону мастера). Габарит заготовки от этого не меняется.
            outline = build_outline_points(x, y, w, h, corners, cuts)
        else:
            outline = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]

        msp.add_lwpolyline(outline, dxfattribs={'layer': 'Системный слой', 'color': 7})

        # Название детали. ВНИМАНИЕ: символы вне cp1251 (↻, ×, ⌀) в DXF R2000
        # превращаются в escape \U+XXXX и в CAM цеха читаются как мусор,
        # поэтому в подписях используем только cp1251-безопасные символы.
        label = f"{part_number}. {part.name}"
        if rotated:
            label += " (поворот 90)"

        msp.add_text(
            _dxf_safe(label), dxfattribs={'layer': 'TEXT', 'height': 15, 'color': 7}
        ).set_placement((x + 10, y + h - 25))

        # Размеры (× заменён на латинскую x — вне cp1251 × даёт escape)
        msp.add_text(
            f"{int(w)}x{int(h)} мм",
            dxfattribs={'layer': 'TEXT', 'height': 12, 'color': 3}
        ).set_placement((x + 10, y + h - 45))

        # Толщина металла
        msp.add_text(
            f"t={part.thickness}мм",
            dxfattribs={'layer': 'TEXT', 'height': 10, 'color': 8}
        ).set_placement((x + 10, y + 10))

        # --- Вырезы (мойка, гриль, вентиляция) ---
        # Координаты выреза заданы относительно НЕповёрнутой детали
        # (в исходной системе координат: 0..part.width по X, 0..part.height по Y).
        # Если деталь при раскрое была повёрнута на 90° по часовой (rotated=True),
        # координаты нужно преобразовать: x' = y, y' = part.width - x.
        # Размеры прямоугольного выреза при повороте меняются местами.
        orig_w = part.width
        orig_h = part.height

        for cutout in getattr(part, 'cutouts', []):
            if rotated:
                cx = x + cutout.y
                cy = y + (orig_w - cutout.x)
            else:
                cx = x + cutout.x
                cy = y + cutout.y

            if cutout.shape == 'rect':
                if rotated:
                    # При повороте на 90° ширина и высота выреза меняются местами
                    cw, ch = cutout.height, cutout.width
                else:
                    cw, ch = cutout.width, cutout.height
                hw, hh = cw / 2, ch / 2
                # Вырезы/отверстия — это ТОЖЕ рез, поэтому кладём их на слой
                # реза «Системный слой» вместе с контуром: команда «резать
                # Системный слой» даёт готовую деталь с отверстиями, ничего
                # не теряется. Раньше они лежали на отдельном слое CUTOUT, и
                # при резке одного контура отверстия можно было пропустить.
                msp.add_lwpolyline(
                    [
                        (cx - hw, cy - hh), (cx + hw, cy - hh),
                        (cx + hw, cy + hh), (cx - hw, cy + hh),
                        (cx - hw, cy - hh)
                    ],
                    dxfattribs={'layer': 'Системный слой', 'color': 7}
                )
            elif cutout.shape == 'circle':
                msp.add_circle((cx, cy), cutout.radius,
                               dxfattribs={'layer': 'Системный слой', 'color': 7})

            if cutout.label:
                msp.add_text(
                    _dxf_safe(cutout.label),
                    dxfattribs={'layer': 'TEXT', 'height': 8, 'color': 6}
                ).set_placement((cx, cy - 6), align=TextEntityAlignment.MIDDLE_CENTER)

            # Размеры выреза (мм) - отдельной строкой под названием. Раньше
            # тут был только текстовый ярлык ("Вырез под мойку") без цифр,
            # и резчику приходилось самому измерять прямоугольник на глаз.
            if cutout.shape == 'rect':
                dims_text = f"{int(cw)}x{int(ch)} мм"
            else:  # circle — «диам.» вместо ⌀ (⌀ вне cp1251)
                dims_text = f"диам.{int(cutout.radius * 2)} мм"

            msp.add_text(
                dims_text,
                dxfattribs={'layer': 'TEXT', 'height': 7, 'color': 6}
            ).set_placement((cx, cy + 6), align=TextEntityAlignment.MIDDLE_CENTER)

        # --- Линии гиба (отбортовка) ---
        # При повороте детали на 90° по часовой кромки тоже меняются:
        # left -> bottom, bottom -> right, right -> top, top -> left
        rotation_map = {'left': 'bottom', 'bottom': 'right', 'right': 'top', 'top': 'left'}
        for bend in getattr(part, 'bend_lines', []):
            edge = rotation_map[bend.edge] if rotated else bend.edge
            if edge == 'left':
                p1, p2 = (x + bend.offset, y), (x + bend.offset, y + h)
            elif edge == 'right':
                p1, p2 = (x + w - bend.offset, y), (x + w - bend.offset, y + h)
            elif edge == 'top':
                p1, p2 = (x, y + h - bend.offset), (x + w, y + h - bend.offset)
            else:  # bottom
                p1, p2 = (x, y + bend.offset), (x + w, y + bend.offset)

            try:
                msp.add_line(p1, p2, dxfattribs={'layer': 'BEND', 'color': 4, 'linetype': 'DASHED'})
            except Exception:
                # если линтайп DASHED не подгрузился - рисуем сплошной, чтобы не падать
                msp.add_line(p1, p2, dxfattribs={'layer': 'BEND', 'color': 4})

            if bend.note:
                mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                msp.add_text(
                    _dxf_safe(bend.note),
                    dxfattribs={'layer': 'BEND', 'height': 8, 'color': 4}
                ).set_placement(mid)

    @staticmethod
    def _optimize_layout(parts):
        sheet_w = Rules.SHEET_WIDTH
        sheet_h = Rules.SHEET_HEIGHT
        margin = Rules.MIN_EDGE_DISTANCE
        gap = Rules.CUT_TOLERANCE

        # Детали, которые не влезают ни на один лист целиком (например, длинная
        # столешница 2.5-3м), автоматически разбиваем на 2 части со швом под сварку.
        expanded_parts = []
        for part in parts:
            expanded_parts.extend(split_part_if_needed(part, sheet_w, sheet_h, margin))

        # MaxRects — пробует 4 эвристики и выбирает лучший результат
        # (замена старому шелф-раскрою, который терял до 30% материала на
        # смешанных размерах деталей).
        return pack_parts(expanded_parts, sheet_w, sheet_h, margin, gap)

    @staticmethod
    def _try_place(sheet, part, w, h, margin, rotated=False):
        if not sheet['rows']:
            sheet['rows'].append({'x': margin, 'y': margin, 'width': 0, 'height': 0})

        for row in sheet['rows']:
            if (row['x'] + w <= sheet['width'] - margin and
                row['y'] + h <= sheet['height'] - margin):

                sheet['parts'].append({
                    'part': part, 'x': row['x'], 'y': row['y'],
                    'width': w - Rules.CUT_TOLERANCE, 'height': h - Rules.CUT_TOLERANCE,
                    'rotated': rotated
                })
                row['x'] += w
                row['height'] = max(row['height'], h)
                return True

        last_row = sheet['rows'][-1]
        new_y = last_row['y'] + last_row['height']

        # ВАЖНО: проверяем и высоту, и ширину. Раньше здесь проверялась только
        # высота нового ряда, из-за чего деталь шире листа всё равно "размещалась"
        # и рисовалась с выходом за правый край листа.
        fits_height = new_y + h <= sheet['height'] - margin
        fits_width = margin + w <= sheet['width'] - margin

        if fits_height and fits_width:
            sheet['rows'].append({'x': margin + w, 'y': new_y, 'width': w, 'height': h})
            sheet['parts'].append({
                'part': part, 'x': margin, 'y': new_y,
                'width': w - Rules.CUT_TOLERANCE, 'height': h - Rules.CUT_TOLERANCE,
                'rotated': rotated
            })
            return True

        return False

    @staticmethod
    def _simple_layout(parts):
        return DXFExporter._optimize_layout(parts)

    @staticmethod
    def _create_report(filename, module, sheets):
        sheet_area = Rules.SHEET_WIDTH * Rules.SHEET_HEIGHT / 1_000_000
        total_sheet_area = len(sheets) * sheet_area

        # ВАЖНО: считаем по РЕАЛЬНО размещённым деталям (sheets), а не по module.parts.
        # Если деталь была разбита на 2 части со швом, module.parts всё ещё содержит
        # исходную "виртуальную" деталь, а sheets - уже 2 физических куска, которые
        # реально режутся и свариваются. Смета и количество должны считаться по факту.
        placed_parts = [pd['part'] for sheet in sheets for pd in sheet['parts']]

        parts_area = sum(p.width * p.height / 1_000_000 for p in placed_parts)
        parts_count = len(placed_parts)

        usage = (parts_area / total_sheet_area) * 100 if total_sheet_area > 0 else 0
        waste = 100 - usage

        metal_cost = parts_area * Rules.METAL_PRICE_PER_M2
        work_cost = parts_count * Rules.WORK_PRICE_PER_PART
        total_cost = metal_cost + work_cost

        # Сгруппировать физические детали по (имя, размер, толщина) для читаемого списка
        agg = {}
        for p in placed_parts:
            key = (p.name, p.width, p.height, p.thickness)
            agg[key] = agg.get(key, 0) + 1

        split_parts_count = sum(1 for p in placed_parts if 'шов' in p.name.lower())

        return {
            'filename': filename,
            'module_name': module.name,
            'module_type': getattr(module, 'module_type', ''),
            'sheets_count': len(sheets),
            'parts_count': parts_count,
            'split_parts_count': split_parts_count,
            'sheet_area_m2': round(total_sheet_area, 3),
            'parts_area_m2': round(parts_area, 3),
            'usage_percent': round(usage, 2),
            'waste_percent': round(waste, 2),
            'metal_cost_rub': round(metal_cost, 2),
            'work_cost_rub': round(work_cost, 2),
            'total_cost_rub': round(total_cost, 2),
            'parts': [
                {'name': k[0], 'width': k[1], 'height': k[2], 'thickness': k[3], 'quantity': v}
                for k, v in agg.items()
            ]
        }

    @staticmethod
    def _print_report(report):
        print("\n" + "=" * 50)
        print("📊 ОТЧЁТ О РАСКРОЕ")
        print("=" * 50)
        print(f"📁 Файл: {os.path.basename(report['filename'])}")
        print(f"📦 Изделие: {report['module_name']} ({report['module_type']})")
        print(f"📄 Листов: {report['sheets_count']}")
        print(f"🔩 Деталей (физических кусков): {report['parts_count']}")
        if report.get('split_parts_count'):
            print(f"⚠️  Из них требуют сварного шва: {report['split_parts_count']}")
        print(f"📐 Площадь деталей: {report['parts_area_m2']:.3f} м²")
        print(f"📏 Площадь листов: {report['sheet_area_m2']:.3f} м²")
        print(f"✅ Использование: {report['usage_percent']:.2f}%")
        print(f"❌ Отходы: {report['waste_percent']:.2f}%")
        print("-" * 50)
        print(f"💰 Металл: {report['metal_cost_rub']:.2f} руб")
        print(f"🔧 Работа: {report['work_cost_rub']:.2f} руб")
        print(f"💵 ИТОГО: {report['total_cost_rub']:.2f} руб")
        print("=" * 50 + "\n")