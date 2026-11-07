"""Read uploaded CSV/XLSX tables and write XLSX workbooks safely.

Uploads: values only. Formulas are never evaluated; for a formula cell the value
Excel last saved is used. Downloads: text that a spreadsheet would treat as a
formula is written as plain text."""
import csv
import io
import zipfile
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from fastapi import HTTPException
from openpyxl.utils.exceptions import InvalidFileException

MAX_BYTES = 3 * 1024 * 1024
MAX_ROWS = 3000
MAX_COLUMNS = 60


def text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_table(data: bytes, filename: str):
    """Return (header, rows) where header is a list of names and rows are lists of strings."""
    name = filename.lower()
    try:
        if name.endswith('.csv'):
            records = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
        elif name.endswith('.xlsx'):
            from openpyxl import load_workbook
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if len(archive.infolist()) > 300 or sum(f.file_size for f in archive.infolist()) > 30 * 1024 * 1024:
                    raise ValueError('Workbook too large')
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
            try:
                sheet = book.worksheets[0]
                records = []
                for cells in sheet.iter_rows(max_row=MAX_ROWS + 2, max_col=MAX_COLUMNS + 1, values_only=True):
                    records.append([text(v) for v in cells])
            finally:
                book.close()
        else:
            raise ValueError('Use a CSV or Excel (.xlsx) file')
    except (ValueError, UnicodeError, csv.Error, zipfile.BadZipFile, KeyError, OSError, ParseError, DefusedXmlException, InvalidFileException) as exc:
        raise HTTPException(422, f'Cannot read this file: {exc}')
    records = [[c.strip() for c in row] for row in records]
    for row in records:
        while row and row[-1] == '':
            row.pop()
    records = [r for r in records if any(r)]
    if len(records) < 2:
        raise HTTPException(422, 'The file needs a header row and at least one student')
    if len(records) > MAX_ROWS + 1:
        raise HTTPException(422, f'Upload at most {MAX_ROWS} rows at a time')
    header = records[0]
    if len(header) > MAX_COLUMNS:
        raise HTTPException(422, f'Use at most {MAX_COLUMNS} columns')
    if any(not h for h in header) or len({h.lower() for h in header}) != len(header):
        raise HTTPException(422, 'Every column needs a distinct name in the first row')
    return header, [r + [''] * (len(header) - len(r)) for r in records[1:]]


def safe(value):
    """Keep a downloaded value from being read as a formula."""
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


def workbook_bytes(sheets):
    """sheets: list of (title, rows, column_widths). Bold first row, frozen header."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    book = Workbook()
    book.remove(book.active)
    used = set()
    for title, rows, widths in sheets:
        clean = ''.join(ch for ch in title if ch not in '[]:*?/\\')[:31] or 'Sheet'
        base, n = clean, 2
        while clean.lower() in used:
            clean = f'{base[:28]} {n}'; n += 1
        used.add(clean.lower())
        sheet = book.create_sheet(clean)
        for row in rows:
            sheet.append([safe(v) for v in row])
        for cell in sheet[1] if rows else []:
            cell.font = Font(bold=True)
        sheet.freeze_panes = 'C2' if rows and len(rows[0]) > 2 else 'A2'
        for index, width in enumerate(widths or [], start=1):
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
