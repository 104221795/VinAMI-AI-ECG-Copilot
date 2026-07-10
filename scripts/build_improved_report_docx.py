from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Research" / "VinStroke_ECG_ConvNeXtV2_Report_Improved.md"
OUTPUT = ROOT / "Research" / "VinStroke_ECG_ConvNeXtV2_Report_Improved.docx"


def set_cell_shading(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def set_repeat_table_header(row) -> None:
    properties = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    properties.append(header)


def set_table_borders(table, color: str = "B7C8CA") -> None:
    table_xml = table._tbl
    table_pr = table_xml.tblPr
    borders = table_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        table_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), color)


def add_inline_text(paragraph, text: str) -> None:
    chunks = re.split(r"(\*\*.*?\*\*)", text)
    for chunk in chunks:
        if not chunk:
            continue
        run = paragraph.add_run(chunk[2:-2] if chunk.startswith("**") and chunk.endswith("**") else chunk)
        run.bold = chunk.startswith("**") and chunk.endswith("**")


def add_markdown_table(document: Document, rows: list[list[str]]) -> None:
    if not rows:
        return
    width = max(len(row) for row in rows)
    table = document.add_table(rows=0, cols=width)
    table.style = "Table Grid"
    table.autofit = True
    for index, values in enumerate(rows):
        cells = table.add_row().cells
        for col, value in enumerate(values):
            paragraph = cells[col].paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(value)
            run.font.name = "Times New Roman"
            run.font.size = Pt(8.5)
            if index == 0:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                set_cell_shading(cells[col], "007F86")
        if index == 0:
            set_repeat_table_header(table.rows[0])
    set_table_borders(table)
    document.add_paragraph()


def build_document() -> Document:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for name, size, color in [("Heading 1", 15, "075D63"), ("Heading 2", 13, "075D63"), ("Heading 3", 11.5, "18363A")]:
        style = document.styles[name]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)

    if "Figure Placeholder" not in document.styles:
        figure_style = document.styles.add_style("Figure Placeholder", WD_STYLE_TYPE.PARAGRAPH)
        figure_style.font.name = "Times New Roman"
        figure_style.font.size = Pt(10)
        figure_style.font.italic = True
        figure_style.font.color.rgb = RGBColor(89, 103, 107)
        figure_style.paragraph_format.left_indent = Cm(0.4)
        figure_style.paragraph_format.space_before = Pt(5)
        figure_style.paragraph_format.space_after = Pt(8)

    return document


def convert_markdown(document: Document, markdown: str) -> None:
    lines = markdown.splitlines()
    index = 0
    title_written = False
    in_code = False
    code_lines: list[str] = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.left_indent = Cm(0.5)
                paragraph.paragraph_format.space_after = Pt(7)
                run = paragraph.add_run("\n".join(code_lines))
                run.font.name = "Consolas"
                run.font.size = Pt(9)
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not stripped:
            index += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                candidate = lines[index].strip()
                cells = [cell.strip() for cell in candidate.strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                    rows.append(cells)
                index += 1
            add_markdown_table(document, rows)
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1 and not title_written:
                paragraph = document.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_after = Pt(14)
                run = paragraph.add_run(text)
                run.bold = True
                run.font.name = "Times New Roman"
                run.font.size = Pt(19)
                run.font.color.rgb = RGBColor(7, 93, 99)
                title_written = True
            else:
                style = "Heading 1" if level == 2 else "Heading 2"
                document.add_paragraph(text, style=style)
            index += 1
            continue

        if stripped.startswith(">"):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.5)
            paragraph.paragraph_format.right_indent = Cm(0.3)
            paragraph.paragraph_format.space_after = Pt(8)
            run = paragraph.add_run(stripped.lstrip("> "))
            run.italic = True
            run.font.color.rgb = RGBColor(112, 83, 26)
            index += 1
            continue

        if stripped.startswith("[Chèn Hình"):
            document.add_paragraph(stripped, style="Figure Placeholder")
            index += 1
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if bullet or numbered:
            paragraph = document.add_paragraph(style="List Bullet" if bullet else "List Number")
            add_inline_text(paragraph, (bullet or numbered).group(1))
            index += 1
            continue

        paragraph = document.add_paragraph()
        add_inline_text(paragraph, stripped)
        index += 1


def add_footer(document: Document) -> None:
    for section in document.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("VinStroke-ECG | Research prototype | AI-assisted ECG interpretation")
        run.font.name = "Times New Roman"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(96, 118, 122)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source: {SOURCE}")
    document = build_document()
    convert_markdown(document, SOURCE.read_text(encoding="utf-8"))
    add_footer(document)
    document.core_properties.title = "VinStroke-ECG: CWT 12-Lead ConvNeXtV2 Report"
    document.core_properties.subject = "Multi-label ECG diagnostic superclass interpretation on PTB-XL"
    document.core_properties.author = "VinStroke-ECG Research Project"
    document.save(OUTPUT)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
