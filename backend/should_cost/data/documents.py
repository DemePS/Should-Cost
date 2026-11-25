"""Document parsing for material-folder documents: drawings, BOMs, RFQs, specs.

Dispatches by extension. Legacy ``.xls`` is converted to ``.xlsx`` via LibreOffice headless
first (SKILL.md: "LibreOffice headless for legacy .xls conversion"), then parsed the same
way as a native ``.xlsx``.

Drawing text boxes: engineering drawings are frequently authored as an Excel sheet with
DrawingML text-box shapes (title block, dimensions, BOM) rather than cell values —
openpyxl does not expose shape text, so ``_extract_drawingml_text`` reads the
``xl/drawings/drawingN.xml`` parts directly out of the xlsx zip (SKILL.md: "parse_document
... including text boxes in drawing XML of xls/xlsx").
"""

from __future__ import annotations

import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

import pdfplumber
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pptx import Presentation
from pyxlsb import open_workbook as open_xlsb

# openpyxl's streaming/read-only mode is used for anything over this size, per the task
# brief ("stream to disk, read-only mode") — small files still benefit from eager mode
# for comment/drawing access, which read_only mode does not support.
LARGE_FILE_READ_ONLY_THRESHOLD_BYTES = 5 * 1024 * 1024

_DRAWINGML_TEXT_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"


@dataclass
class ParsedDocument:
    text: str
    tables: list[list[list[str | None]]] = field(default_factory=list)
    sheet_names: list[str] | None = None
    warnings: list[str] = field(default_factory=list)


def _extract_drawingml_text(xlsx_path: str) -> list[str]:
    texts: list[str] = []
    with zipfile.ZipFile(xlsx_path) as zf:
        drawing_parts = [n for n in zf.namelist() if n.startswith("xl/drawings/") and n.endswith(".xml")]
        for part in drawing_parts:
            try:
                root = ElementTree.fromstring(zf.read(part))
            except ElementTree.ParseError:
                continue
            for node in root.iter(_DRAWINGML_TEXT_TAG):
                if node.text and node.text.strip():
                    texts.append(node.text.strip())
    return texts


def _parse_xlsx(path: str) -> ParsedDocument:
    size = Path(path).stat().st_size
    read_only = size > LARGE_FILE_READ_ONLY_THRESHOLD_BYTES
    wb = load_workbook(path, data_only=True, read_only=read_only)
    tables: list[list[list[str | None]]] = []
    cell_lines: list[str] = []
    for ws in wb.worksheets:
        grid: list[list[str | None]] = []
        for row in ws.iter_rows(values_only=True):
            str_row = [None if v is None else str(v) for v in row]
            grid.append(str_row)
            cell_lines.extend(v for v in str_row if v)
        tables.append(grid)

        if not read_only:
            for row in ws.iter_rows():
                for cell in row:
                    comment = getattr(cell, "comment", None)
                    if comment and comment.text:
                        cell_lines.append(f"[comment {cell.coordinate}] {comment.text}")

    drawing_texts = _extract_drawingml_text(path)
    cell_lines.extend(drawing_texts)

    warnings = []
    if read_only:
        warnings.append(f"File > {LARGE_FILE_READ_ONLY_THRESHOLD_BYTES} bytes: opened read-only, comments skipped.")

    return ParsedDocument(
        text="\n".join(cell_lines),
        tables=tables,
        sheet_names=wb.sheetnames,
        warnings=warnings,
    )


def _parse_xlsb(path: str) -> ParsedDocument:
    tables: list[list[list[str | None]]] = []
    cell_lines: list[str] = []
    sheet_names: list[str] = []
    with open_xlsb(path) as wb:
        for sheet_name in wb.sheets:
            sheet_names.append(sheet_name)
            grid: list[list[str | None]] = []
            with wb.get_sheet(sheet_name) as sheet:
                for row in sheet.rows():
                    str_row = [None if c.v is None else str(c.v) for c in row]
                    grid.append(str_row)
                    cell_lines.extend(v for v in str_row if v)
            tables.append(grid)
    return ParsedDocument(
        text="\n".join(cell_lines),
        tables=tables,
        sheet_names=sheet_names,
        warnings=["xlsb: formulas and drawing text boxes are not extractable (pyxlsb limitation)."],
    )


def _convert_xls_to_xlsx(xls_path: str, out_dir: str) -> str:
    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            out_dir,
            xls_path,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion of {xls_path!r} failed: {result.stderr}")
    converted = Path(out_dir) / (Path(xls_path).stem + ".xlsx")
    if not converted.exists():
        raise RuntimeError(f"LibreOffice did not produce {converted} for input {xls_path!r}")
    return str(converted)


def _parse_pdf(path: str) -> ParsedDocument:
    lines: list[str] = []
    tables: list[list[list[str | None]]] = []
    warnings: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if not page_text.strip():
                warnings.append(f"Page {page.page_number}: no extractable text (possibly scanned — needs OCR).")
            lines.append(page_text)
            for table in page.extract_tables():
                tables.append(table)
    return ParsedDocument(text="\n".join(lines), tables=tables, warnings=warnings)


def _parse_docx(path: str) -> ParsedDocument:
    doc = DocxDocument(path)
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    tables = [[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
    return ParsedDocument(text="\n".join(lines), tables=tables)


def _parse_pptx(path: str) -> ParsedDocument:
    prs = Presentation(path)
    lines: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                lines.append(shape.text_frame.text)
    return ParsedDocument(text="\n".join(lines))


def parse_document(path: str) -> ParsedDocument:
    """Parse a single document by extension. Raises ``ValueError`` for an unsupported
    extension rather than guessing a format (SKILL.md: 'Do not guess').
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix == ".pptx":
        return _parse_pptx(path)
    if suffix == ".xlsx":
        return _parse_xlsx(path)
    if suffix == ".xlsb":
        return _parse_xlsb(path)
    if suffix == ".xls":
        with tempfile.TemporaryDirectory() as tmp:
            converted_path = _convert_xls_to_xlsx(path, tmp)
            result = _parse_xlsx(converted_path)
            result.warnings.append(f"Converted from legacy .xls via LibreOffice: {Path(path).name}")
            return result
    raise ValueError(f"Unsupported document type: {path!r} (extension {suffix!r})")
