"""
Страница-разделитель раздела (обложка сборочной единицы).

Ключевое требование к документу: переход от одного модуля к другому должен
БРОСАТЬСЯ В ГЛАЗА. Раньше чертежи деталей "Секции с ящиками" и "Секции под
мойку" шли подряд без всякой границы, и, открыв документ на середине, было
невозможно понять, к какому узлу относится текущий лист.

Здесь - отдельный лист перед каждым разделом: крупный номер раздела,
название узла, его обозначение по ГОСТ и краткий состав (сколько деталей,
сколько подсборок, сколько труб). Дальше до следующего такого листа идёт
ТОЛЬКО этот узел.
"""
from reportlab.lib.units import mm


def draw_section_divider(c, node, page_size, company_name, code,
                         sheet_num, sheets_total, paper_format, font_name,
                         title_block_fn, section_label):
    """
    Args:
        node: AssemblyNode - узел, чей раздел открывается
        section_label: подпись раздела, напр. "РАЗДЕЛ 2" или "РАЗДЕЛ 2.1"
    """
    page_w, page_h = page_size
    margin_left, margin_right = 20 * mm, 5 * mm
    margin_top, margin_bottom = 5 * mm, 5 * mm
    title_h = 55 * mm

    cx = margin_left + (page_w - margin_left - margin_right) / 2
    # Центр свободного поля листа (между верхом рамки и верхом штампа)
    field_top = page_h - margin_top
    field_bottom = margin_bottom + title_h
    cy = (field_top + field_bottom) / 2

    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)

    # --- Крупная подпись раздела ---
    c.setFont(font_name, 20)
    c.drawCentredString(cx, cy + 42 * mm, section_label)

    # --- Жирная линейка на всю ширину поля (визуальный "стоп") ---
    c.setLineWidth(1.6)
    c.line(margin_left + 15 * mm, cy + 34 * mm,
           page_w - margin_right - 15 * mm, cy + 34 * mm)

    # --- Название узла (крупно) ---
    name = node.name
    size = 26 if len(name) <= 28 else (20 if len(name) <= 42 else 15)
    c.setFont(font_name, size)
    c.drawCentredString(cx, cy + 16 * mm, name)

    # --- Обозначение по ГОСТ ---
    c.setFont(font_name, 15)
    c.drawCentredString(cx, cy + 2 * mm, code)

    c.setLineWidth(0.8)
    c.line(margin_left + 15 * mm, cy - 6 * mm,
           page_w - margin_right - 15 * mm, cy - 6 * mm)

    # --- Состав раздела ---
    part_kinds = len(node.grouped_parts())
    part_total = sum(p.quantity for p in node.parts)
    tube_kinds = len(node.grouped_tubes())
    tube_total = sum(t.quantity for t in node.tubes)

    lines = []
    if node.children:
        lines.append(f"Подсборок в составе: {len(node.children)}")
    if part_kinds:
        lines.append(f"Деталей: {part_kinds} наим. / {part_total} шт.")
    if tube_kinds:
        lines.append(f"Труб каркаса: {tube_kinds} наим. / {tube_total} шт.")
    hidden = sum(1 for p in node.parts if p.is_hidden_in_assembly)
    if hidden:
        lines.append(f"из них скрыто в собранном изделии: {hidden} наим.")

    c.setFont(font_name, 11)
    y = cy - 18 * mm
    for line in lines:
        c.drawCentredString(cx, y, line)
        y -= 7 * mm

    c.setFont(font_name, 9)
    c.drawCentredString(
        cx, y - 6 * mm,
        "Далее до следующего разделителя — документы только этой сборочной единицы"
    )

    # --- Рамка листа + штамп ---
    c.setLineWidth(1.0)
    c.rect(margin_left, margin_bottom, page_w - margin_left - margin_right,
           page_h - margin_bottom - margin_top, fill=0, stroke=1)

    stamp_x0 = page_w - margin_right - 185 * mm
    title_block_fn(c, stamp_x0, margin_bottom, {
        "code": code,
        "name": f"{node.name} — заглавный лист",
        "mass": "-",
        "scale": "б/м",
        "qty": 1,
        "material": "сборочная единица",
        "company": company_name,
        "sheet": sheet_num,
        "sheets_total": sheets_total,
        "format": paper_format,
    })