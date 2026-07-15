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
from core.rules import Rules
from core.part_splitter import split_part_if_needed
from core.nesting import pack_parts
from core.sheet_metal import get_corners_needing_relief, build_outline_points, rotate_corners


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

        version = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(Config.DXF_DIR, f"{module.module_type}_{version}.dxf")

        # Версия формата R2000 (AC1015) и кодовая страница ANSI_1251 - взято
        # НЕ из памяти, а напрямую из заголовка реального референсного DXF
        # (проверено построчным разбором $ACADVER/$DWGCODEPAGE). До формата
        # R2007 включительно DXF хранит текст через кодовую страницу, а не
        # через UTF-8 - отсюда и cp1251 у референсных файлов.
        doc = ezdxf.new("R2000", setup=True)
        doc.header['$DWGCODEPAGE'] = 'ANSI_1251'
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

        doc.saveas(filename)

        report = DXFExporter._create_report(filename, module, sheets_data)

        report_path = os.path.join(Config.REPORTS_DIR, f"report_{version}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        DXFExporter._print_report(report)

        return {
            'dxf_path': filename,
            'report_path': report_path,
            'report': report
        }

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
        if rotated and corners:
            corners = rotate_corners(corners)

        if corners:
            outline = build_outline_points(x, y, w, h, corners, part.corner_relief)
        else:
            outline = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]

        msp.add_lwpolyline(outline, dxfattribs={'layer': 'Системный слой', 'color': 7})

        # Название детали
        label = f"{part_number}. {part.name}"
        if rotated:
            label += " ↻"

        msp.add_text(
            label, dxfattribs={'layer': 'TEXT', 'height': 15, 'color': 7}
        ).set_placement((x + 10, y + h - 25))

        # Размеры
        msp.add_text(
            f"{int(w)}×{int(h)} мм",
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
                msp.add_lwpolyline(
                    [
                        (cx - hw, cy - hh), (cx + hw, cy - hh),
                        (cx + hw, cy + hh), (cx - hw, cy + hh),
                        (cx - hw, cy - hh)
                    ],
                    dxfattribs={'layer': 'CUTOUT', 'color': 6}
                )
            elif cutout.shape == 'circle':
                msp.add_circle((cx, cy), cutout.radius, dxfattribs={'layer': 'CUTOUT', 'color': 6})

            if cutout.label:
                msp.add_text(
                    cutout.label,
                    dxfattribs={'layer': 'TEXT', 'height': 8, 'color': 6}
                ).set_placement((cx, cy - 6), align=TextEntityAlignment.MIDDLE_CENTER)

            # Размеры выреза (мм) - отдельной строкой под названием. Раньше
            # тут был только текстовый ярлык ("Вырез под мойку") без цифр,
            # и резчику приходилось самому измерять прямоугольник на глаз.
            if cutout.shape == 'rect':
                dims_text = f"{int(cw)}×{int(ch)} мм"
            else:  # circle
                dims_text = f"⌀{int(cutout.radius * 2)} мм"

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
                    bend.note,
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