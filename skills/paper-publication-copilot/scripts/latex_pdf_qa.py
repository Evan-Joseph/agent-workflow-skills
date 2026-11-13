#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
latex_pdf_qa.py — Automated LaTeX Manuscript PDF & Log Layout Auditor.

Audits compiled academic manuscript PDFs and LaTeX .log files for:
  1. LaTeX compilation warnings: Overfull \\hbox / \\vbox, undefined citations, undefined references, multiply-defined labels.
  2. Paragraph Last-Line Fill Ratio ("小尾巴" / Orphan Tail Detection):
     Uses PyMuPDF (fitz) block/line bounding boxes to measure the width fill ratio of the last line
     of every multi-line body paragraph (>= 3 lines) relative to the column width.
     Flags short orphan tails (< 35% width) and reports paragraphs outside the 75%-100% target zone.
  3. Horizontal Margin / Column Overflow Detection:
     Detects text lines or tables extending past the established body text right margin.
  4. Context-Safe Downsampled Page Rendering (--render-dir, default 110 DPI, <100KB/page).

Usage:
  python3 latex_pdf_qa.py Main.pdf --log Main.log
  python3 latex_pdf_qa.py Main.pdf --log Main.log --tail-threshold 0.40 --render-dir ./pdf_qa
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF


def parse_latex_log(log_path: Optional[Path]) -> Dict[str, Any]:
    """Parse LaTeX .log file for Overfull hbox/vbox, undefined citations/refs, and rerun-needed label warnings."""
    if not log_path or not log_path.exists():
        return {
            "log_found": False,
            "overfull_hbox": [],
            "overfull_vbox": [],
            "undefined_citations": [],
            "undefined_refs": [],
            "labels_may_have_changed": False,
            "rerun_warnings": [],
        }

    text = log_path.read_text(encoding="utf-8", errors="replace")
    overfull_h = re.findall(r"(Overfull \\hbox \([0-9.]+pt too wide\) in paragraph at lines [0-9\-]+)", text)
    overfull_v = re.findall(r"(Overfull \\vbox \([0-9.]+pt too high\)[^\n]*)", text)
    undef_cit = re.findall(r"LaTeX Warning: Citation `([^']+)' on page [0-9]+ undefined", text)
    undef_ref = re.findall(r"LaTeX Warning: Reference `([^']+)' on page [0-9]+ undefined", text)
    label_changed_matches = re.findall(
        r"(LaTeX Warning: Label\(s\) may have changed\.[^\n]*)",
        text,
    )
    rerun_matches = re.findall(
        r"(?:LaTeX|Package [A-Za-z0-9_-]+) Warning: [^\n]*Rerun to get [^\n]+",
        text,
    )

    return {
        "log_found": True,
        "log_path": str(log_path),
        "overfull_hbox_count": len(overfull_h),
        "overfull_hbox": overfull_h[:30],
        "overfull_vbox_count": len(overfull_v),
        "overfull_vbox": overfull_v[:20],
        "undefined_citations": sorted(set(undef_cit)),
        "undefined_refs": sorted(set(undef_ref)),
        "labels_may_have_changed": len(label_changed_matches) > 0,
        "rerun_warnings": sorted(set(label_changed_matches + rerun_matches)),
    }


def parse_bibtex_blg(blg_path: Optional[Path]) -> Dict[str, Any]:
    """Parse BibTeX .blg file for empty journal/booktitle/year/pages/author warnings."""
    if not blg_path or not blg_path.exists():
        return {
            "blg_found": False,
            "empty_field_count": 0,
            "empty_fields": [],
            "other_warnings": [],
        }

    text = blg_path.read_text(encoding="utf-8", errors="replace")
    empty_matches = re.findall(r"Warning--empty\s+([a-zA-Z0-9_-]+)\s+in\s+([^\s\n]+)", text)
    empty_items = [{"field": field, "citekey": key} for field, key in empty_matches]
    other_warns = [
        m.strip()
        for m in re.findall(r"(Warning--(?!empty\s+)[^\n]+)", text)
    ]
    return {
        "blg_found": True,
        "blg_path": str(blg_path),
        "empty_field_count": len(empty_items),
        "empty_fields": empty_items[:50],
        "other_warning_count": len(other_warns),
        "other_warnings": other_warns[:30],
    }


def audit_pdf_layout(
    pdf_path: Path,
    tail_threshold: float = 0.35,
    render_dir: Optional[Path] = None,
    dpi: int = 110,
) -> Dict[str, Any]:
    """Audit PDF paragraph last-line fill ratios ('小尾巴') and margin overflows using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    short_tails: List[Dict[str, Any]] = []
    sub80_tails: List[Dict[str, Any]] = []
    margin_overflows: List[Dict[str, Any]] = []
    type3_fonts: List[Dict[str, Any]] = []
    seen_type3: set[tuple[int, str]] = set()
    pages_summary: List[Dict[str, Any]] = []
    rendered_pngs: List[str] = []

    if render_dir is not None:
        render_dir.mkdir(parents=True, exist_ok=True)

    total_body_paras = 0
    ideal_80_100_paras = 0

    for idx, page in enumerate(doc):
        page_num = idx + 1
        for f_entry in page.get_fonts(full=False):
            # f_entry: (xref, ext, font_type, basefont, name, encoding)
            ftype = str(f_entry[2] if len(f_entry) > 2 else "")
            basefont = str(f_entry[3] if len(f_entry) > 3 and f_entry[3] else (f_entry[4] if len(f_entry) > 4 else "unknown"))
            if ftype.lower().replace(" ", "") == "type3":
                key = (page_num, basefont)
                if key not in seen_type3:
                    seen_type3.add(key)
                    type3_fonts.append({
                        "page": page_num,
                        "font_type": ftype,
                        "basefont": basefont,
                        "name": str(f_entry[4] if len(f_entry) > 4 else ""),
                    })
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)
        page_dict = page.get_text("dict")
        text_blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0 and b.get("lines")]

        # Estimate full line width(s) on this page from paragraphs with >=3 lines
        line_widths: List[float] = []
        right_edges: List[float] = []
        for b in text_blocks:
            lines = b.get("lines", [])
            if len(lines) >= 3:
                # Use non-final lines to measure standard justified column width
                for ln in lines[:-1]:
                    bbox = ln.get("bbox", [0, 0, 0, 0])
                    w = float(bbox[2]) - float(bbox[0])
                    if w > page_w * 0.28:
                        line_widths.append(w)
                        right_edges.append(float(bbox[2]))

        if line_widths:
            line_widths.sort()
            # Median justified line width on this page (works for both 1-col and 2-col!)
            col_width = line_widths[int(len(line_widths) * 0.75)]
            normal_right = sorted(right_edges)[int(len(right_edges) * 0.85)]
        else:
            col_width = page_w * 0.75
            normal_right = page_w * 0.88

        page_short_tails = 0
        for b in text_blocks:
            lines = b.get("lines", [])
            if len(lines) < 3:
                continue
            # Skip headers/footers (top 7% or bottom 7% of page)
            b_bbox = b.get("bbox", [0, 0, 0, 0])
            if float(b_bbox[1]) < page_h * 0.06 or float(b_bbox[3]) > page_h * 0.93:
                continue

            # Check non-final lines to verify this block is a justified prose paragraph (not an equation/table/caption)
            non_final_widths = [float(ln["bbox"][2]) - float(ln["bbox"][0]) for ln in lines[:-1]]
            max_non_final = max(non_final_widths) if non_final_widths else 0.0
            if max_non_final < col_width * 0.85:
                continue

            last_ln = lines[-1]
            last_bbox = last_ln.get("bbox", [0, 0, 0, 0])
            last_w = float(last_bbox[2]) - float(last_bbox[0])
            last_text = "".join(sp.get("text", "") for sp in last_ln.get("spans", [])).strip()
            if not last_text:
                continue
            # Skip display math equation numbers like "(1)" or "[12]"
            if re.fullmatch(r"[\(\[\d\.\)\]]+", last_text):
                continue

            fill_ratio = round(min(1.0, last_w / max_non_final), 3)
            total_body_paras += 1
            if fill_ratio >= 0.78:
                ideal_80_100_paras += 1
            else:
                first_ln_text = "".join(sp.get("text", "") for sp in lines[0].get("spans", [])).strip()
                item = {
                    "page": page_num,
                    "lines_in_para": len(lines),
                    "fill_ratio": fill_ratio,
                    "fill_pct": f"{fill_ratio * 100:.1f}%",
                    "para_start": first_ln_text[:45],
                    "last_line_text": last_text[:60],
                }
                sub80_tails.append(item)
                if fill_ratio < tail_threshold:
                    short_tails.append(item)
                    page_short_tails += 1

            # Check horizontal right-margin overflow (> 6pt past normal right edge)
            for ln in lines:
                lb = ln.get("bbox", [0, 0, 0, 0])
                if float(lb[2]) > normal_right + 6.0 and float(lb[2]) > page_w * 0.90:
                    ln_txt = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
                    margin_overflows.append({
                        "page": page_num,
                        "overflow_pt": round(float(lb[2]) - normal_right, 1),
                        "line_text": ln_txt[:60],
                    })

        pages_summary.append({
            "page": page_num,
            "col_width_pt": round(col_width, 1),
            "short_tails_on_page": page_short_tails,
        })

        if render_dir is not None:
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out_png = render_dir / f"page_{page_num:02d}.png"
            pix.save(str(out_png))
            rendered_pngs.append(str(out_png))

    doc.close()
    return {
        "page_count": len(pages_summary),
        "total_body_paragraphs": total_body_paras,
        "ideal_80_100_count": ideal_80_100_paras,
        "ideal_80_100_ratio": round(ideal_80_100_paras / total_body_paras, 3) if total_body_paras else 1.0,
        "short_tail_threshold": tail_threshold,
        "short_tail_count": len(short_tails),
        "short_tails": short_tails,
        "sub80_tail_count": len(sub80_tails),
        "sub80_tails": sub80_tails[:40],
        "margin_overflow_count": len(margin_overflows),
        "margin_overflows": margin_overflows[:25],
        "type3_font_count": len(type3_fonts),
        "type3_fonts": type3_fonts,
        "type3_remediation": (
            "Set matplotlib.rcParams['pdf.fonttype'] = 42 and matplotlib.rcParams['ps.fonttype'] = 42 "
            "(or export vector PDF/SVG with TrueType/Type 1 fonts) before regenerating figures."
            if type3_fonts
            else None
        ),
        "rendered_pngs": rendered_pngs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated LaTeX PDF, Log & BibTeX QA Gate (Type 3 Fonts, Rerun Labels, BibTeX Empty Fields, Orphan Tails '小尾巴', Overfull hbox)"
    )
    parser.add_argument("pdf", help="Compiled manuscript PDF path")
    parser.add_argument("--log", help="Optional LaTeX .log file path (auto-detected alongside PDF if omitted)")
    parser.add_argument("--blg", help="Optional BibTeX .blg file path (auto-detected alongside PDF if omitted)")
    parser.add_argument(
        "--tail-threshold",
        type=float,
        default=0.35,
        help="Minimum acceptable last-line fill ratio before flagging as a short orphan tail '小尾巴' (default: 0.35)",
    )
    parser.add_argument("--render-dir", help="Optional directory to export compact 110-DPI page PNGs (<100KB/page)")
    parser.add_argument("--dpi", type=int, default=110, help="Preview PNG DPI (default: 110)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(json.dumps({"passed": False, "error": f"PDF not found: {pdf_path}"}, ensure_ascii=False))
        return 1

    log_path = Path(args.log).resolve() if args.log else pdf_path.with_suffix(".log")
    blg_path = Path(args.blg).resolve() if args.blg else pdf_path.with_suffix(".blg")
    render_dir = Path(args.render_dir).resolve() if args.render_dir else None

    log_audit = parse_latex_log(log_path)
    blg_audit = parse_bibtex_blg(blg_path)
    pdf_audit = audit_pdf_layout(pdf_path, tail_threshold=args.tail_threshold, render_dir=render_dir, dpi=args.dpi)

    issues: List[str] = []
    if log_audit.get("undefined_citations"):
        issues.append(f"Undefined citations: {log_audit['undefined_citations']}")
    if log_audit.get("undefined_refs"):
        issues.append(f"Undefined references: {log_audit['undefined_refs']}")
    if log_audit.get("labels_may_have_changed") or log_audit.get("rerun_warnings"):
        issues.append(f"LaTeX log indicates cross-reference rerun needed: {log_audit['rerun_warnings']}")
    if log_audit.get("overfull_hbox_count", 0) > 0:
        issues.append(f"LaTeX log reports {log_audit['overfull_hbox_count']} Overfull \\hbox warning(s)")
    if blg_audit.get("empty_field_count", 0) > 0:
        sample_empty = [f"{it['citekey']}({it['field']})" for it in blg_audit["empty_fields"][:8]]
        issues.append(
            f"BibTeX .blg reports {blg_audit['empty_field_count']} empty bibliography field warning(s): {', '.join(sample_empty)}"
        )
    if pdf_audit["type3_font_count"] > 0:
        pages_hit = sorted({it["page"] for it in pdf_audit["type3_fonts"]})
        issues.append(
            f"Detected {pdf_audit['type3_font_count']} Type 3 bitmap font occurrence(s) on page(s) {pages_hit} "
            "(fix via matplotlib.rcParams['pdf.fonttype'] = 42)"
        )
    if pdf_audit["margin_overflow_count"] > 0:
        issues.append(f"Detected {pdf_audit['margin_overflow_count']} horizontal margin overflow line(s)")
    if pdf_audit["short_tail_count"] > 0:
        issues.append(
            f"Detected {pdf_audit['short_tail_count']} paragraph(s) with short orphan tail ('小尾巴' < {args.tail_threshold*100:.0f}% width)"
        )

    result = {
        "passed": len(issues) == 0,
        "pdf_path": str(pdf_path),
        "issues": issues,
        "log_audit": log_audit,
        "blg_audit": blg_audit,
        "pdf_audit": pdf_audit,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if len(issues) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
