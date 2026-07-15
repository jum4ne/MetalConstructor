"""
Страница-ведомость (спецификация) внутри самого PDF - таблица "из чего
состоит этот узел", как в разделе "Документация / Детали" настоящего
комплекта чертежей. Раньше у нас такая таблица была только в отдельном
Excel-файле - здесь она встроена прямо в комплект чертежей, между
разнесённым видом и сборочным чертежом, как и в референсе.

Номера позиций берутся из build_cabinet_scene - те же самые, что и на
странице разнесённого вида и сборочного чертежа этого же модуля, чтобы
по всему документу нумерация была одна и та же.
"""
from reportlab.lib.units import mm
from core.exploded_view import build_cabinet_scene


def _group_by_label(items):
    """Группирует детали по названию (одинаковые полки/пояса каркаса и т.п.
    сводятся в одну строку с диапазоном позиций и количеством)"""
    groups = {}
    order = []
    for item in items:
        if item.label not in groups:
            groups[item.label] = []
            order.append(item.label)
        groups[item.label].append(item.pos_num)
    return [(label, groups[label]) for label in order]


def draw_project_spec_page(c, blocks, page_size, title, company_name, code,
                            sheet_num, sheets_total, paper_format, font_name, title_block_fn,
                            code_prefix="К"):
    """
    Ведомость верхнего уровня для всего проекта кухни - список "Сборочные
    единицы" (секций/модулей), как на первых страницах референса, а не
    отдельных деталей (детали каждой секции - в её собственной ведомости).
    """
    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    table_x0 = margin_left
    table_w = page_w - margin_left - margin_right
    y = page_h - margin_top - 15 * mm

    col_widths = [16 * mm, 30 * mm, table_w - 16 * mm - 30 * mm - 20 * mm, 20 * mm]
    headers = ["Поз.", "Обозначение", "Наименование", "Кол."]
    row_h = 8 * mm

    c.setFont(font_name, 13)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left, page_h - margin_top - 8 * mm, title)

    c.setFont(font_name, 9)
    c.drawString(table_x0, y + 3 * mm, "Сборочные единицы")

    def draw_row(y, values, header=False):
        x = table_x0
        c.setLineWidth(0.4)
        for i, (w, val) in enumerate(zip(col_widths, values)):
            c.rect(x, y - row_h, w, row_h, fill=0, stroke=1)
            c.setFont(font_name, 8.5 if header else 8)
            align = "center" if i in (0, 3) else "left"
            if align == "center":
                c.drawCentredString(x + w / 2, y - row_h + 2.5 * mm, str(val))
            else:
                c.drawString(x + 2 * mm, y - row_h + 2.5 * mm, str(val))
            x += w
        return y - row_h

    y = draw_row(y, headers, header=True)
    for b in blocks:
        code_str = f"{code_prefix} 00.{b.pos_num:02d}.00.000"
        y = draw_row(y, [b.pos_num, code_str, b.name, 1])

    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    stamp_x0 = page_w - margin_right - 185 * mm
    title_block_fn(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": title,
        "mass": "-",
        "scale": "б/м",
        "qty": 1,
        "material": "ведомость проекта",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })


def draw_spec_page(c, module, page_size, title, company_name, code,
                    sheet_num, sheets_total, paper_format, font_name, title_block_fn,
                    code_prefix="К"):
    """
    Нарисовать страницу-ведомость: таблица Поз./Обозначение/Наименование/
    Кол-во/Примечание для всех деталей и труб этого модуля.
    """
    shelf_count = sum(p.quantity for p in module.parts if p.name.startswith("Полка"))
    door_count = sum(p.quantity for p in module.parts if p.name.startswith("Дверь"))
    plates, rods = build_cabinet_scene(
        module.height, module.width, module.depth,
        shelf_count=shelf_count, door_count=door_count,
        has_tubes=bool(getattr(module, 'tubes', None))
    )

    plate_groups = _group_by_label(plates)
    rod_groups = _group_by_label(rods)

    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    table_x0 = margin_left
    table_w = page_w - margin_left - margin_right
    table_y_top = page_h - margin_top - 15 * mm

    col_widths = [16 * mm, 30 * mm, table_w - 16 * mm - 30 * mm - 20 * mm - 60 * mm, 20 * mm, 60 * mm]
    headers = ["Поз.", "Обозначение", "Наименование", "Кол.", "Примечание"]
    row_h = 7 * mm

    c.setFont(font_name, 13)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(margin_left, page_h - margin_top - 8 * mm, title)

    def draw_row(y, values, header=False):
        x = table_x0
        c.setLineWidth(0.4)
        for i, (w, val) in enumerate(zip(col_widths, values)):
            c.rect(x, y - row_h, w, row_h, fill=0, stroke=1)
            c.setFont(font_name, 8 if header else 7.5)
            align = "center" if i in (0, 3) else "left"
            pad = w / 2 if align == "center" else 2 * mm
            if align == "center":
                c.drawCentredString(x + pad, y - row_h + 2 * mm, str(val))
            else:
                c.drawString(x + pad, y - row_h + 2 * mm, str(val))
            x += w
        return y - row_h

    y = table_y_top
    c.setFont(font_name, 9)
    c.drawString(table_x0, y + 3 * mm, "Детали")
    y = draw_row(y, headers, header=True)

    pos_counter = 1
    entry_num = 0
    for label, positions in plate_groups:
        entry_num += 1
        qty = len(positions)
        pos_str = ", ".join(str(p) for p in positions) if qty <= 4 else f"{positions[0]}-{positions[-1]}"
        code_str = f"{code_prefix} {sheet_num:02d}.{entry_num:02d}"
        y = draw_row(y, [pos_str, code_str, label, qty, "Лист НЕРЖ"])
        if y < margin_bottom + title_h + 15 * mm:
            break  # защита от переполнения страницы (простое ограничение)

    if rod_groups:
        y -= 9 * mm
        c.setFont(font_name, 9)
        c.drawString(table_x0, y + 3 * mm, "Трубы (каркас)")
        y = draw_row(y, headers, header=True)
        for label, positions in rod_groups:
            entry_num += 1
            qty = len(positions)
            pos_str = ", ".join(str(p) for p in positions) if qty <= 4 else f"{positions[0]}-{positions[-1]}"
            code_str = f"{code_prefix} {sheet_num:02d}.{entry_num:02d}"
            y = draw_row(y, [pos_str, code_str, label, qty, "профиль"])
            if y < margin_bottom + title_h + 15 * mm:
                break

    # --- Внешняя рамка листа ---
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    # --- Штамп ---
    stamp_x0 = page_w - margin_right - 185 * mm
    title_block_fn(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": title,
        "mass": "-",
        "scale": "б/м",
        "qty": 1,
        "material": "ведомость (см. детали далее)",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })