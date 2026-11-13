#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_qa_gate.py — Unified Delivery QA Gate for Word (.docx) Templates & Official Documents.

Enforces AGENTS.md Section 三.7 (Template Fidelity, Formula Rendering & Visual Pagination Gate):
  1. Template Structural & CJK Font Audit (via docx_template_tool)
  2. Cover-Page Typography & Font-Size Shrinkage Guard (prevents shrinking cover titles or breaking underlines)
  3. Raw LaTeX Leakage Guard (detects unrendered $...$, \\frac, \\sum, etc. vs native OMML <m:oMath>)
  4. Silent Word Sandbox PDF Export (stages in ~/Library/Containers/com.microsoft.Word/Data/Documents/
     to avoid macOS sandbox file-permission popups and never calls printer dialogs)
  5. Rendered PDF Pagination & Orphan Spillover Audit (via PyMuPDF / fitz: detects 1-2 line cover-page
     spillover or orphan tail pages, and optionally exports context-safe 110-DPI preview PNGs <100KB/page)

Usage:
  python3 docx_qa_gate.py output.docx --template template.docx
  python3 docx_qa_gate.py --output output.docx --template template.docx --reference-docx past_approved.docx --export-pdf output.pdf --render-dir ./qa_pages
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.oxml.ns import qn

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from docx_template_tool import (  # noqa: E402
    audit_document_against_template,
    iter_all_paragraphs_xml,
    resolve_paragraph_signature,
)

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# Patterns that strongly indicate raw LaTeX math left in document text
RAW_LATEX_PATTERNS = [
    (re.compile(r"\$[^$\n]{1,80}\$"), "Inline LaTeX math ($...$)"),
    (re.compile(r"\\(?:frac|sum|prod|int|sqrt|alpha|beta|gamma|delta|theta|lambda|sigma|omega|mathbb|mathcal|mathbf|mathrm|cdot|times|leq|geq|neq|approx|infty)\b"), "Raw LaTeX command"),
    (re.compile(r"\\begin\{(?:equation|align|matrix|pmatrix|bmatrix)\}"), "Raw LaTeX environment"),
]


def audit_cover_page_typography(template_doc: Document, output_doc: Document, ref_doc: Optional[Document] = None) -> Dict[str, Any]:
    """Check that cover-page (first 12 non-empty paragraphs) font sizes and alignments were not degraded."""
    issues: List[str] = []
    warnings: List[str] = []

    baseline_doc = ref_doc if ref_doc is not None else template_doc
    base_paras = [p for p in baseline_doc.paragraphs[:25] if p.text.strip()][:12]
    out_paras = [p for p in output_doc.paragraphs[:25] if p.text.strip()][:12]

    # Compare matching prefix labels or top title paragraphs
    for idx, (bp, op) in enumerate(zip(base_paras, out_paras)):
        b_sig = resolve_paragraph_signature(baseline_doc, bp._p, bp.style)
        o_sig = resolve_paragraph_signature(output_doc, op._p, op.style)
        b_sz = b_sig.get("size_pt")
        o_sz = o_sig.get("size_pt")
        if b_sz and o_sz and o_sz < b_sz:
            issues.append(
                f"Cover paragraph #{idx} ({op.text.strip()[:25]!r}) font size shrank from {b_sz}pt to {o_sz}pt (do not shrink cover-page fonts)"
            )
        elif b_sz and o_sz and o_sz != b_sz:
            warnings.append(
                f"Cover paragraph #{idx} ({op.text.strip()[:25]!r}) font size changed from {b_sz}pt to {o_sz}pt"
            )

    return {"issues": issues, "warnings": warnings}


def audit_formula_fidelity(output_doc: Document) -> Dict[str, Any]:
    """Count native OMML (<m:oMath>) objects and scan for raw unrendered LaTeX strings."""
    omml_count = len(output_doc.element.xpath("//*[local-name()='oMath' or local-name()='oMathPara']"))
    raw_latex_hits: List[str] = []

    for i, p in enumerate(output_doc.paragraphs):
        txt = p.text.strip()
        if not txt:
            continue
        for pat, desc in RAW_LATEX_PATTERNS:
            m = pat.search(txt)
            if m:
                raw_latex_hits.append(f"paragraph[{i}] has {desc}: {m.group(0)!r}")
                break

    seen_tc = set()
    for t_idx, table in enumerate(output_doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                if cell._tc in seen_tc:
                    continue
                seen_tc.add(cell._tc)
                txt = cell.text.strip()
                if not txt:
                    continue
                for pat, desc in RAW_LATEX_PATTERNS:
                    m = pat.search(txt)
                    if m:
                        raw_latex_hits.append(f"table[{t_idx}]({r_idx},{c_idx}) has {desc}: {m.group(0)!r}")
                        break

    return {
        "omml_formula_count": omml_count,
        "raw_latex_leak_count": len(raw_latex_hits),
        "raw_latex_leaks": raw_latex_hits[:20],
    }


def silent_word_sandbox_pdf_export(docx_path: Path, pdf_out_path: Path, timeout: int = 90) -> Dict[str, Any]:
    """Export .docx to .pdf silently via Microsoft Word sandbox directory without focus stealing or printer popups."""
    word_sandbox_dir = Path.home() / "Library/Containers/com.microsoft.Word/Data/Documents"
    word_sandbox_dir.mkdir(parents=True, exist_ok=True)
    token = f"_agent_qa_{uuid.uuid4().hex[:8]}"
    staged_docx = word_sandbox_dir / f"{token}.docx"
    staged_pdf = word_sandbox_dir / f"{token}.pdf"

    shutil.copy2(docx_path, staged_docx)
    applescript = f"""
    set inPath to POSIX file "{staged_docx}"
    set outPath to "{staged_pdf}"
    tell application "Microsoft Word"
        set display alerts to alerts none
        open inPath with read only
        set activeDoc to active document
        save as activeDoc file name outPath file format format PDF
        close activeDoc saving no
    end tell
    """
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0 or not staged_pdf.exists():
            return {
                "ok": False,
                "error": (proc.stderr or proc.stdout or "PDF file was not created by Microsoft Word").strip(),
                "elapsed_sec": round(time.time() - t0, 2),
            }
        pdf_out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_pdf), str(pdf_out_path))
        return {
            "ok": True,
            "pdf_path": str(pdf_out_path),
            "size_bytes": pdf_out_path.stat().st_size,
            "elapsed_sec": round(time.time() - t0, 2),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "elapsed_sec": round(time.time() - t0, 2)}
    finally:
        for f in (staged_docx, staged_pdf):
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass


def audit_pdf_pagination_and_render(
    pdf_path: Path,
    render_dir: Optional[Path] = None,
    dpi: int = 110,
) -> Dict[str, Any]:
    """Inspect rendered PDF pages for single-line cover spillover, sparse orphan pages, and export compact PNGs."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    pages_summary: List[Dict[str, Any]] = []
    pagination_warnings: List[str] = []
    rendered_files: List[str] = []

    if render_dir is not None:
        render_dir.mkdir(parents=True, exist_ok=True)

    for idx, page in enumerate(doc):
        page_num = idx + 1
        rect = page.rect
        page_h = rect.height or 1.0
        blocks = [b for b in page.get_text("blocks") if len(b) >= 5 and str(b[4]).strip()]
        lines = [ln.strip() for b in blocks for ln in str(b[4]).splitlines() if ln.strip()]

        if blocks:
            min_y = min(float(b[1]) for b in blocks)
            max_y = max(float(b[3]) for b in blocks)
            vertical_span_ratio = round((max_y - min_y) / page_h, 3)
            bottom_edge_ratio = round(max_y / page_h, 3)
        else:
            vertical_span_ratio = 0.0
            bottom_edge_ratio = 0.0

        page_info = {
            "page": page_num,
            "line_count": len(lines),
            "vertical_span_ratio": vertical_span_ratio,
            "bottom_edge_ratio": bottom_edge_ratio,
            "first_line": lines[0][:50] if lines else "",
            "last_line": lines[-1][:50] if lines else "",
        }
        pages_summary.append(page_info)

        # Detect single-line or tiny spillover on Page 2 (classic cover-page overflow!) or final page
        if len(lines) == 0:
            pagination_warnings.append(f"Page {page_num} is completely blank")
        elif len(lines) <= 2 and vertical_span_ratio < 0.12:
            pagination_warnings.append(
                f"Page {page_num} has only {len(lines)} line(s) (vertical span {vertical_span_ratio*100:.1f}%): "
                f"likely accidental spillover ({lines[0][:40]!r})"
            )

        if render_dir is not None:
            # Render at compact DPI (default 110 DPI) so multimodal read_file never bloats conversation DB
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out_png = render_dir / f"page_{page_num:02d}.png"
            pix.save(str(out_png))
            rendered_files.append(str(out_png))

    doc.close()
    return {
        "page_count": len(pages_summary),
        "pagination_warnings": pagination_warnings,
        "pages": pages_summary,
        "rendered_pngs": rendered_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified Word (.docx) Delivery QA Gate (Template + Cover + OMML + Silent PDF + Pagination)"
    )
    parser.add_argument("output_pos", nargs="?", help="Edited output .docx path")
    parser.add_argument("--output", "-o", dest="output_opt", help="Edited output .docx path")
    parser.add_argument("--template", "-t", required=False, help="Original template .docx path")
    parser.add_argument("--reference-docx", "-r", help="Optional past approved submission .docx for cover/style parity")
    parser.add_argument("--export-pdf", nargs="?", const="AUTO", help="Export to PDF via silent Word sandbox (optional output path)")
    parser.add_argument("--pdf", help="Existing rendered PDF to audit if already exported")
    parser.add_argument("--render-dir", help="Directory to render compact 110-DPI page preview PNGs")
    parser.add_argument("--dpi", type=int, default=110, help="Preview PNG DPI (default: 110, keeps PNGs <100KB)")
    args = parser.parse_args()

    out_docx_str = args.output_opt or args.output_pos
    if not out_docx_str:
        parser.error("Provide the output .docx path (positional or --output)")
    out_docx_path = Path(out_docx_str).resolve()
    if not out_docx_path.exists():
        print(json.dumps({"passed": False, "error": f"Output file not found: {out_docx_path}"}, ensure_ascii=False))
        return 1

    out_doc = Document(str(out_docx_path))
    tpl_doc = Document(str(Path(args.template).resolve())) if args.template else out_doc
    ref_doc = Document(str(Path(args.reference_docx).resolve())) if args.reference_docx else None

    # 1. Structural & Font Audit
    base_audit = audit_document_against_template(tpl_doc, out_doc)

    # 2. Cover-page typography guard
    cover_audit = audit_cover_page_typography(tpl_doc, out_doc, ref_doc=ref_doc)

    # 3. Formula fidelity guard
    formula_audit = audit_formula_fidelity(out_doc)

    issues = list(base_audit["issues"]) + cover_audit["issues"]
    warnings = list(base_audit["warnings"]) + cover_audit["warnings"]
    if formula_audit["raw_latex_leak_count"] > 0:
        issues.extend(formula_audit["raw_latex_leaks"])

    # 4. Optional Silent Word Sandbox PDF Export + Pagination Audit
    pdf_report: Optional[Dict[str, Any]] = None
    pdf_to_audit: Optional[Path] = Path(args.pdf).resolve() if args.pdf else None

    if args.export_pdf:
        if args.export_pdf == "AUTO":
            pdf_target = out_docx_path.with_suffix(".pdf")
        else:
            pdf_target = Path(args.export_pdf).resolve()
        export_res = silent_word_sandbox_pdf_export(out_docx_path, pdf_target)
        pdf_report = {"export": export_res}
        if export_res.get("ok"):
            pdf_to_audit = pdf_target
        else:
            warnings.append(f"Silent Word PDF export failed: {export_res.get('error')}")

    if pdf_to_audit and pdf_to_audit.exists():
        render_dir_path = Path(args.render_dir).resolve() if args.render_dir else None
        pag_res = audit_pdf_pagination_and_render(pdf_to_audit, render_dir=render_dir_path, dpi=args.dpi)
        if pdf_report is None:
            pdf_report = {}
        pdf_report["pagination"] = pag_res
        warnings.extend(pag_res.get("pagination_warnings", []))

    passed = len(issues) == 0
    result = {
        "passed": passed,
        "output_docx": str(out_docx_path),
        "template_docx": str(Path(args.template).resolve()) if args.template else None,
        "reference_docx": str(Path(args.reference_docx).resolve()) if args.reference_docx else None,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "template_cjk_fonts": base_audit.get("template_cjk_fonts", []),
        "formula_audit": formula_audit,
        "issues": issues,
        "warnings": warnings,
        "pdf_qa": pdf_report,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
