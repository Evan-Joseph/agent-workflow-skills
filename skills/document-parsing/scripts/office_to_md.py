#!/usr/bin/env python3
"""100% Local Zero-Network Structured Markdown + Table Extractor (office_to_md.py).

Extracts structured Markdown (preserving reading order, headings, tables, worksheet names,
and PDF page provenance) locally without uploading any bytes over the network:
  - `.docx` via `python-docx` (interleaved body paragraphs + tables in exact XML order)
  - `.xlsx` / `.xlsm` via `openpyxl` (`data_only=True`, trimmed Markdown tables per sheet)
  - `.pdf` via PyMuPDF `fitz` (`page.find_tables()` + non-overlapping `get_text("blocks")`)

Designed for private contracts, transcripts, rosters, financial ledgers, and unpublished
materials where external cloud OCR upload is prohibited.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import docx
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
import fitz  # PyMuPDF
import openpyxl


def _escape_md_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).replace("\r\n", "\n").replace("\r", "\n").strip()
    s = re.sub(r"\s*\n\s*", "<br>", s)
    return s.replace("|", "\\|")


def _rows_to_md_table(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    col_count = max((len(r) for r in rows), default=0)
    if col_count == 0:
        return ""
    norm: list[list[str]] = []
    for r in rows:
        cells = [_escape_md_cell(c) for c in r] + [""] * (col_count - len(r))
        if any(cells):
            norm.append(cells)
    if not norm:
        return ""
    header = norm[0]
    sep = ["---"] * col_count
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in norm[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extract_docx_to_md(path: Path) -> tuple[str, dict[str, Any]]:
    doc: DocxDocument = docx.Document(str(path))
    parts: list[str] = [f"# {path.name}", ""]
    para_count = 0
    table_count = 0

    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            p = DocxParagraph(child, doc)
            txt = (p.text or "").strip()
            if not txt:
                continue
            para_count += 1
            style_name = (p.style.name if p.style else "") or ""
            m_head = re.match(r"Heading\s*(\d+)", style_name, re.I)
            if m_head:
                lvl = min(6, max(1, int(m_head.group(1)) + 1))
                parts.extend([f"{'#' * lvl} {txt}", ""])
            elif style_name.lower() == "title":
                parts.extend([f"## {txt}", ""])
            elif "list" in style_name.lower():
                parts.append(f"- {txt}")
            else:
                parts.extend([txt, ""])
        elif isinstance(child, CT_Tbl):
            tbl = DocxTable(child, doc)
            rows_data: list[list[str]] = []
            for row in tbl.rows:
                # Deduplicate horizontally merged cells sharing the same underlying _tc
                row_vals: list[str] = []
                last_tc = None
                for cell in row.cells:
                    if cell._tc is last_tc:
                        row_vals.append("")
                    else:
                        row_vals.append(cell.text.strip())
                        last_tc = cell._tc
                rows_data.append(row_vals)
            md_tbl = _rows_to_md_table(rows_data)
            if md_tbl:
                table_count += 1
                parts.extend(["", md_tbl, ""])

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    return md, {"format": "docx", "paragraphs": para_count, "tables": table_count}


def extract_xlsx_to_md(path: Path, max_rows: int = 2000) -> tuple[str, dict[str, Any]]:
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    parts: list[str] = [f"# {path.name}", ""]
    sheet_summaries: list[dict[str, Any]] = []

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            raw_rows: list[list[Any]] = []
            truncated = False
            for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if idx > max_rows:
                    truncated = True
                    break
                vals = list(row)
                while vals and (vals[-1] is None or str(vals[-1]).strip() == ""):
                    vals.pop()
                if any(v is not None and str(v).strip() != "" for v in vals):
                    raw_rows.append(vals)

            parts.append(f"## Sheet: {sheet_name}")
            parts.append("")
            if raw_rows:
                md_tbl = _rows_to_md_table(raw_rows)
                parts.append(md_tbl)
                if truncated:
                    parts.append(f"\n> *(Truncated at `--max-rows {max_rows}`)*")
            else:
                parts.append("*(Empty sheet)*")
            parts.append("")
            sheet_summaries.append({"sheet": sheet_name, "non_empty_rows": len(raw_rows), "truncated": truncated})
    finally:
        wb.close()

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    return md, {"format": "xlsx", "sheets": len(sheet_summaries), "sheet_details": sheet_summaries}


def _bbox_overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float], ratio_thresh: float = 0.45) -> bool:
    ix0 = max(a[0], b[0])
    iy0 = max(a[1], b[1])
    ix1 = min(a[2], b[2])
    iy1 = min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return False
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    return (inter / area_a) >= ratio_thresh


def extract_pdf_to_md(path: Path, page_range: tuple[int, int] | None = None) -> tuple[str, dict[str, Any]]:
    parts: list[str] = [f"# {path.name}", ""]
    total_tables = 0
    total_blocks = 0
    raster_only_pages: list[int] = []

    with fitz.open(str(path)) as doc:
        p_start = page_range[0] if page_range else 1
        p_end = min(len(doc), page_range[1]) if page_range else len(doc)
        for pno in range(p_start, p_end + 1):
            page = doc[pno - 1]
            elements: list[tuple[float, float, str]] = []
            table_bboxes: list[tuple[float, float, float, float]] = []

            try:
                with contextlib.redirect_stdout(sys.stderr):
                    finder = page.find_tables()
                    tables = list(finder.tables) if finder else []
            except Exception:
                tables = []

            for tbl in tables:
                tb = tuple(float(v) for v in tbl.bbox)
                rows = tbl.extract() or []
                md_tbl = _rows_to_md_table(rows)
                if md_tbl:
                    table_bboxes.append(tb)  # type: ignore[arg-type]
                    elements.append((tb[1], tb[0], md_tbl))
                    total_tables += 1

            for blk in page.get_text("blocks"):
                # blk: (x0, y0, x1, y1, text, block_no, block_type)
                if len(blk) >= 7 and blk[6] != 0:
                    continue
                bb = (float(blk[0]), float(blk[1]), float(blk[2]), float(blk[3]))
                if any(_bbox_overlaps(bb, tb) for tb in table_bboxes):
                    continue
                txt = str(blk[4] or "").strip()
                if not txt:
                    continue
                clean_txt = re.sub(r"[ \t]+\n", "\n", txt)
                elements.append((bb[1], bb[0], clean_txt))
                total_blocks += 1

            elements.sort(key=lambda item: (round(item[0] / 6.0), item[1]))
            parts.append(f"## Page {pno}")
            parts.append("")
            if elements:
                for _, _, content in elements:
                    parts.append(content)
                    parts.append("")
            else:
                raster_only_pages.append(pno)
                parts.append("*(No embedded text/tables on this page — use `crop_exam_sheet.py` for offline visual inspection)*")
                parts.append("")

        page_count = len(doc)

    md = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip() + "\n"
    return md, {
        "format": "pdf",
        "page_count": page_count,
        "text_blocks": total_blocks,
        "tables": total_tables,
        "raster_only_pages": raster_only_pages,
    }


def _parse_pages_spec(spec: str) -> tuple[int, int]:
    s = spec.strip()
    if "-" in s:
        a, b = s.split("-", 1)
        p0, p1 = int(a.strip()), int(b.strip())
    else:
        p0 = p1 = int(s)
    if p0 < 1 or p1 < p0:
        raise ValueError(f"Invalid --pages '{spec}': expected 1-based 'start-end' or 'N'")
    return p0, p1


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="office_to_md_selftest_") as tmp:
        tdir = Path(tmp)

        # 1. Synthetic .docx
        docx_path = tdir / "sample.docx"
        d = docx.Document()
        d.add_heading("Private Roster & Contract", level=1)
        d.add_paragraph("Clause 1: Strictly confidential local processing.")
        t = d.add_table(rows=2, cols=2)
        t.cell(0, 0).text = "Field"
        t.cell(0, 1).text = "Value"
        t.cell(1, 0).text = "Amount"
        t.cell(1, 1).text = "12,500 CNY"
        d.save(str(docx_path))
        md_docx, meta_docx = extract_docx_to_md(docx_path)
        assert "| Field | Value |" in md_docx and meta_docx["tables"] == 1

        # 2. Synthetic .xlsx
        xlsx_path = tdir / "ledger.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Q4_Ledger"
        ws.append(["Item", "Cost"])
        ws.append(["Server", 320])
        wb.save(str(xlsx_path))
        md_xlsx, meta_xlsx = extract_xlsx_to_md(xlsx_path)
        assert "## Sheet: Q4_Ledger" in md_xlsx and "| Item | Cost |" in md_xlsx and meta_xlsx["sheets"] == 1

        # 3. Synthetic .pdf with table
        pdf_path = tdir / "report.pdf"
        pdoc = fitz.open()
        page = pdoc.new_page(width=595, height=842)
        page.insert_text((50, 60), "Offline PDF Extraction Test", fontsize=14)
        for r in range(3):
            y0 = 100 + r * 28
            y1 = y0 + 28
            page.draw_rect(fitz.Rect(50, y0, 200, y1))
            page.draw_rect(fitz.Rect(200, y0, 360, y1))
            page.insert_text((58, y0 + 18), f"Key_{r}", fontsize=10)
            page.insert_text((208, y0 + 18), f"Val_{r}", fontsize=10)
        pdoc.save(str(pdf_path))
        pdoc.close()
        md_pdf, meta_pdf = extract_pdf_to_md(pdf_path)
        assert "Offline PDF Extraction Test" in md_pdf and meta_pdf["page_count"] == 1

        print(json.dumps({"ok": True, "self_test": "passed", "formats_verified": ["docx", "xlsx", "pdf"]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="100% local zero-network structured Markdown + table extractor for private .docx, .xlsx, and .pdf files."
    )
    parser.add_argument("input", nargs="?", help="Input .docx, .xlsx/.xlsm, or .pdf file path")
    parser.add_argument("-o", "--out", default="", help="Optional output Markdown file path (prints to stdout if omitted)")
    parser.add_argument("--pages", default="", help="Optional 1-based page range for PDF, e.g. '1-5' or '3'")
    parser.add_argument("--max-rows", type=int, default=2000, help="Max rows per Excel worksheet (default: 2000)")
    parser.add_argument("--json", action="store_true", help="Emit JSON envelope containing metadata + markdown")
    parser.add_argument("--self-test", action="store_true", help="Run built-in offline docx/xlsx/pdf self-test and exit")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.input:
        parser.error("the following arguments are required: input (unless --self-test is passed)")

    in_path = Path(args.input).expanduser().resolve()
    if not in_path.is_file():
        print(f"Error: Input file not found: {in_path}", file=sys.stderr)
        return 1

    ext = in_path.suffix.lower()
    if ext == ".docx":
        markdown_text, meta = extract_docx_to_md(in_path)
    elif ext in (".xlsx", ".xlsm"):
        markdown_text, meta = extract_xlsx_to_md(in_path, max_rows=max(1, args.max_rows))
    elif ext == ".pdf":
        pr = _parse_pages_spec(args.pages) if args.pages else None
        markdown_text, meta = extract_pdf_to_md(in_path, page_range=pr)
    else:
        print(
            f"Error: Unsupported extension '{ext}' (supported offline formats: .docx, .xlsx, .xlsm, .pdf)",
            file=sys.stderr,
        )
        return 1

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown_text, encoding="utf-8")
        meta["output_path"] = str(out_path)

    if args.json:
        print(json.dumps({"ok": True, "input": str(in_path), **meta, "markdown": markdown_text}, ensure_ascii=False, indent=2))
    elif args.out:
        print(json.dumps({"ok": True, "input": str(in_path), **meta}, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(markdown_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
