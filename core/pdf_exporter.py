"""
Экспорт спецификации в PDF — красивый документ для начальника / клиента.
Требует: pip install reportlab
"""
import os
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import Config
from core.order_paths import order_file


class PDFExporter:

    FONT_NAME = "Helvetica"  # заменится на кириллический шрифт, если он найдётся в системе

    @staticmethod
    def export(module, report=None):
        Config.init_dirs()
        version = time.strftime("%Y%m%d_%H%M%S")
        filename = order_file(module, "Спецификация.pdf")

        # Если отчёт о раскрое не передан снаружи (например, пользователь жмёт
        # "Экспорт PDF" до того, как посчитал DXF) - считаем его сами.
        # Иначе секция "Итоги раскроя" (стоимость, отходы, использование) не
        # попадёт в PDF, и клиент увидит только спецификацию без сметы.
        if report is None:
            try:
                from core.dxf_exporter import DXFExporter
                sheets = DXFExporter._optimize_layout(module.parts)
                report = DXFExporter._create_report(filename, module, sheets)
            except Exception:
                # если что-то пошло не так (например, деталь не помещается) -
                # PDF всё равно выпустим, просто без секции итогов
                report = None

        PDFExporter._register_font()

        doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TitleRu", parent=styles["Title"], fontName=PDFExporter.FONT_NAME)
        h3_style = ParagraphStyle("H3Ru", parent=styles["Heading3"], fontName=PDFExporter.FONT_NAME)
        normal_style = ParagraphStyle("NormalRu", parent=styles["Normal"], fontName=PDFExporter.FONT_NAME)

        elements = []
        elements.append(Paragraph(f"Спецификация: {module.name}", title_style))

        if hasattr(module, 'modules'):  # это KitchenProject
            elements.append(Paragraph(f"Клиент: {getattr(module, 'client', '-') or '-'}", normal_style))
            elements.append(Paragraph(f"Состав проекта: {len(module.modules)} модулей", normal_style))
            for m in module.modules:
                elements.append(Paragraph(
                    f"• {m.name} ({m.module_type}) — {m.width}×{m.depth}×{m.height} мм, t={m.thickness} мм",
                    normal_style
                ))
        else:
            elements.append(Paragraph(f"Тип модуля: {getattr(module, 'module_type', '-')}", normal_style))
            elements.append(Paragraph(
                f"Габариты: {module.width}×{module.depth}×{module.height} мм, "
                f"толщина металла: {module.thickness} мм",
                normal_style
            ))
        elements.append(Spacer(1, 8 * mm))

        data = [["№", "Деталь", "Ш, мм", "В, мм", "Кол-во", "Площадь, м²", "Примечания"]]
        for i, part in enumerate(module.parts, 1):
            notes = []
            if getattr(part, 'cutouts', None):
                notes.append(f"вырезов: {len(part.cutouts)}")
            if getattr(part, 'bend_lines', None):
                notes.append(f"гибов: {len(part.bend_lines)}")
            data.append([
                str(i), part.name, str(part.width), str(part.height),
                str(part.quantity), f"{part.area * part.quantity:.3f}",
                ", ".join(notes) if notes else "-"
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), PDFExporter.FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
        ]))
        elements.append(table)

        if report:
            elements.append(Spacer(1, 8 * mm))
            elements.append(Paragraph("Итоги раскроя:", h3_style))
            summary_lines = [
                f"Листов металла: {report['sheets_count']}",
                f"Деталей всего: {report['parts_count']}",
                f"Использование материала: {report['usage_percent']:.2f}%",
                f"Отходы: {report['waste_percent']:.2f}%",
                f"Стоимость металла: {report['metal_cost_rub']:.2f} руб",
                f"Стоимость работ: {report['work_cost_rub']:.2f} руб",
                f"ИТОГО: {report['total_cost_rub']:.2f} руб",
            ]
            for line in summary_lines:
                elements.append(Paragraph(line, normal_style))

        doc.build(elements)
        return filename

    @staticmethod
    def _register_font():
        """Подключить шрифт с кириллицей, иначе русский текст в PDF не отобразится."""
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont("CyrillicFont", path))
                    PDFExporter.FONT_NAME = "CyrillicFont"
                    return
                except Exception:
                    continue
        # Если ни один шрифт не найден - останется Helvetica (кириллица не отобразится,
        # нужно будет вручную положить .ttf шрифт рядом и прописать путь выше)

    @staticmethod
    def export_bend_map(module):
        """
        Карта гибки — отдельный документ для оператора гибочного станка:
        список всех линий гиба по всем деталям, с углом, кромкой, отступом и порядком.
        Швы (стыки для сварки) показаны отдельной пометкой, не как гиб.
        """
        Config.init_dirs()
        version = time.strftime("%Y%m%d_%H%M%S")
        filename = order_file(module, "Карта гибки.pdf")

        PDFExporter._register_font()

        doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("TitleRu", parent=styles["Title"], fontName=PDFExporter.FONT_NAME)
        normal_style = ParagraphStyle("NormalRu", parent=styles["Normal"], fontName=PDFExporter.FONT_NAME)

        elements = [Paragraph(f"Карта гибки: {module.name}", title_style), Spacer(1, 6 * mm)]

        edge_names = {'left': 'левая', 'right': 'правая', 'top': 'верхняя', 'bottom': 'нижняя'}

        rows = [["№", "Деталь", "Толщина", "Кромка", "Отступ, мм", "Угол", "Тип", "Примечание"]]
        bend_num = 0
        has_any = False

        for part in module.parts:
            for bend in getattr(part, 'bend_lines', []):
                has_any = True
                is_seam = bend.direction == 'seam'
                if not is_seam:
                    bend_num += 1
                rows.append([
                    str(bend_num) if not is_seam else "-",
                    part.name,
                    f"{part.thickness} мм",
                    edge_names.get(bend.edge, bend.edge),
                    str(bend.offset),
                    f"{bend.angle:.0f}°" if not is_seam else "-",
                    "ШОВ (сварка)" if is_seam else "Гиб",
                    bend.note or "-",
                ])

        if not has_any:
            elements.append(Paragraph("У деталей этого изделия нет линий гиба.", normal_style))
        else:
            table = Table(rows, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), PDFExporter.FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 6 * mm))
            elements.append(Paragraph(
                "Порядок гибки: начинать с меньших отступов от края к большим на одной детали, "
                "чтобы предыдущий гиб не мешал станку зажать следующую линию.",
                normal_style
            ))

        doc.build(elements)
        return filename