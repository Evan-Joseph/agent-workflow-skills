#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_template_tool.py — Template-First, Format-Preserving OOXML (.docx) Engine.

Designed to solve the 5 classic failure modes when AI Agents edit Word (.docx) templates:
  1. Font corruption (losing w:eastAsia CJK font, or overwriting w:eastAsia with w:ascii)
  2. Direct-formatting destruction (using paragraph.text = ... or cell.text = ..., which wipes <w:rPr> and <w:pPr>)
  3. Blind editing without template understanding (missing <w:pPr><w:rPr> on empty cells, merged cells gridSpan/vMerge, underlined blanks, or <w:sdt> controls)
  4. Multi-line layout breakage (dumping '\\n' into a single <w:t> instead of cloning <w:pPr> per paragraph)
  5. Fragmented runs (Word splitting placeholders/keywords across multiple <w:r> elements due to rsid/proofErr)

Subcommands:
  inspect       Deeply inspect a .docx template (sections, styles, paragraphs, tables, merged cells, fonts, blanks)
  merge-runs    Strip proofErr/rsid and coalesce adjacent runs with identical <w:rPr>
  replace       Cross-run format-preserving text replacement (body, tables, headers/footers, SDT controls)
  set-para      Format-preserving paragraph edit by index (supports multi-line cloning & underlined-blank fill)
  set-cell      Format-preserving table cell edit by (table, row, col) with merge safety & neighbor rPr inheritance
  fill          Batch fill paragraphs, table cells, underlined blanks, and placeholders from a JSON spec
  build         Build a new .docx from scratch via JSON spec (margins, CJK/Latin fonts, headings, paragraphs, tables, page breaks)
  audit         Compare an edited .docx against its template to detect font drift, layout damage, or leftover placeholders
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

RSID_ATTRS = (
    qn("w:rsidR"),
    qn("w:rsidRPr"),
    qn("w:rsidRDefault"),
    qn("w:rsidP"),
    qn("w:rsidDel"),
    qn("w:rsidSect"),
    qn("w:rsidTr"),
)


# ---------------------------------------------------------------------------
# 1. XML & Font Inspection / Extraction Helpers
# ---------------------------------------------------------------------------

def _attr(el, local_name: str) -> Optional[str]:
    if el is None:
        return None
    return el.get(qn(f"w:{local_name}")) or el.get(local_name)


def extract_rpr_signature(rpr) -> Dict[str, Any]:
    """Extract human/agent-readable typography signature from a <w:rPr> element."""
    if rpr is None:
        return {}
    sig: Dict[str, Any] = {}
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is not None:
        ea = _attr(rfonts, "eastAsia")
        ascii_f = _attr(rfonts, "ascii")
        hansi_f = _attr(rfonts, "hAnsi")
        if ea:
            sig["eastAsia"] = ea
        if ascii_f:
            sig["ascii"] = ascii_f
        elif hansi_f:
            sig["ascii"] = hansi_f
    sz = rpr.find(qn("w:sz"))
    if sz is not None and _attr(sz, "val"):
        try:
            sig["size_pt"] = int(_attr(sz, "val")) / 2.0
        except ValueError:
            pass
    b = rpr.find(qn("w:b"))
    if b is not None:
        val = _attr(b, "val")
        sig["bold"] = val not in ("0", "false", "off")
    i = rpr.find(qn("w:i"))
    if i is not None:
        val = _attr(i, "val")
        sig["italic"] = val not in ("0", "false", "off")
    u = rpr.find(qn("w:u"))
    if u is not None:
        val = _attr(u, "val")
        if val and val != "none":
            sig["underline"] = val
    color = rpr.find(qn("w:color"))
    if color is not None and _attr(color, "val"):
        sig["color"] = _attr(color, "val")
    return sig


def resolve_style_signature(doc: Document, style_obj) -> Dict[str, Any]:
    """Walk style inheritance chain + docDefaults to get baseline font signature."""
    sig: Dict[str, Any] = {}
    # 1. Start from docDefaults
    try:
        styles_el = doc.styles.element
        doc_defaults = styles_el.find(qn("w:docDefaults"))
        if doc_defaults is not None:
            rpr_def = doc_defaults.find(f".//{qn('w:rPr')}")
            sig.update(extract_rpr_signature(rpr_def))
    except Exception:
        pass

    # 2. Walk style chain from base to current
    chain = []
    curr = style_obj
    seen = set()
    while curr is not None and getattr(curr, "style_id", None) not in seen:
        seen.add(getattr(curr, "style_id", None))
        chain.append(curr)
        curr = getattr(curr, "base_style", None)

    for st in reversed(chain):
        try:
            rpr = st.element.find(qn("w:rPr"))
            sig.update(extract_rpr_signature(rpr))
        except Exception:
            pass
    return sig


def resolve_paragraph_signature(doc: Document, p_el, style_obj=None) -> Dict[str, Any]:
    """Resolve effective font signature of a paragraph (<w:p>) from runs -> pPr/rPr -> style."""
    sig = resolve_style_signature(doc, style_obj) if style_obj is not None else {}
    ppr = p_el.find(qn("w:pPr"))
    if ppr is not None:
        ppr_rpr = ppr.find(qn("w:rPr"))
        sig.update(extract_rpr_signature(ppr_rpr))
    # Check non-empty runs first, fallback to any run
    runs = p_el.findall(qn("w:r"))
    chosen_rpr = None
    for r in runs:
        t_text = "".join((t.text or "") for t in r.findall(qn("w:t")))
        if t_text.strip() and r.find(qn("w:rPr")) is not None:
            chosen_rpr = r.find(qn("w:rPr"))
            break
    if chosen_rpr is None:
        for r in runs:
            if r.find(qn("w:rPr")) is not None:
                chosen_rpr = r.find(qn("w:rPr"))
                break
    if chosen_rpr is not None:
        sig.update(extract_rpr_signature(chosen_rpr))
    return sig


def extract_paragraph_layout(p_el) -> Dict[str, Any]:
    """Extract alignment, indentation, and spacing from <w:pPr>."""
    info: Dict[str, Any] = {}
    ppr = p_el.find(qn("w:pPr"))
    if ppr is None:
        return info
    jc = ppr.find(qn("w:jc"))
    if jc is not None and _attr(jc, "val"):
        info["align"] = _attr(jc, "val")
    ind = ppr.find(qn("w:ind"))
    if ind is not None:
        ind_map = {}
        for k in ("firstLine", "firstLineChars", "left", "leftChars", "hanging", "right"):
            v = _attr(ind, k)
            if v is not None:
                ind_map[k] = v
        if ind_map:
            info["indent"] = ind_map
    spacing = ppr.find(qn("w:spacing"))
    if spacing is not None:
        sp_map = {}
        for k in ("before", "after", "line", "lineRule"):
            v = _attr(spacing, k)
            if v is not None:
                sp_map[k] = v
        if sp_map:
            info["spacing"] = sp_map
    return info


def detect_underlined_blank(p_el) -> Optional[Dict[str, Any]]:
    """Detect if a paragraph has a 'Label：______' structure (non-underlined prefix + underlined blank/placeholder run)."""
    runs = p_el.findall(qn("w:r"))
    if not runs:
        return None
    underlined_indices = []
    for idx, r in enumerate(runs):
        rpr = r.find(qn("w:rPr"))
        u = rpr.find(qn("w:u")) if rpr is not None else None
        u_val = _attr(u, "val") if u is not None else None
        t_text = "".join((t.text or "") for t in r.findall(qn("w:t")))
        if (u_val and u_val != "none") or (t_text and set(t_text.strip()) <= {"_", "＿"} and len(t_text.strip()) >= 2):
            underlined_indices.append(idx)
    if not underlined_indices:
        return None
    first_u = underlined_indices[0]
    prefix_text = "".join(
        "".join((t.text or "") for t in runs[i].findall(qn("w:t")))
        for i in range(first_u)
    )
    blank_text = "".join(
        "".join((t.text or "") for t in runs[i].findall(qn("w:t")))
        for i in underlined_indices
    )
    if prefix_text.strip():
        return {
            "label_prefix": prefix_text,
            "blank_Indices": underlined_indices,
            "current_blank_text": blank_text,
        }
    return None


# ---------------------------------------------------------------------------
# 2. Best-Effort <w:rPr> Template Resolution (The Core Anti-Font-Corruption Logic)
# ---------------------------------------------------------------------------

def _sanitize_rpr(rpr, *, strip_bold: bool = False, strip_underline: bool = False):
    """Deep-copy a <w:rPr> element and clean transient/revision attributes."""
    if rpr is None:
        return None
    cloned = copy.deepcopy(rpr)
    for attr_name in list(cloned.attrib.keys()):
        if "rsid" in attr_name.lower():
            del cloned.attrib[attr_name]
    for rev_tag in ("w:rPrChange", "w:ins", "w:del"):
        for child in cloned.findall(qn(rev_tag)):
            cloned.remove(child)
    if strip_bold:
        for b_tag in ("w:b", "w:bCs"):
            for child in cloned.findall(qn(b_tag)):
                cloned.remove(child)
    if strip_underline:
        for child in cloned.findall(qn("w:u")):
            cloned.remove(child)
    return cloned


def extract_best_rpr_for_paragraph(
    p_el,
    *,
    fallback_p_elements: Optional[List[Any]] = None,
    strip_fallback_bold: bool = False,
):
    """Find the most faithful <w:rPr> to apply when setting text on `p_el`.

    Priority:
      1. Existing non-empty <w:r><w:rPr> inside `p_el`
      2. Any <w:r><w:rPr> inside `p_el`
      3. Paragraph mark <w:pPr><w:rPr> inside `p_el` (Word stores empty cell/paragraph fonts here!)
      4. Neighboring/fallback paragraphs' <w:r><w:rPr> or <w:pPr><w:rPr>
    """
    # 1. Existing non-whitespace run with rPr
    for r in p_el.findall(qn("w:r")):
        t_text = "".join((t.text or "") for t in r.findall(qn("w:t")))
        rpr = r.find(qn("w:rPr"))
        if t_text.strip() and rpr is not None:
            return _sanitize_rpr(rpr)

    # 2. Any run with rPr
    for r in p_el.findall(qn("w:r")):
        rpr = r.find(qn("w:rPr"))
        if rpr is not None:
            return _sanitize_rpr(rpr)

    # 3. Paragraph mark <w:pPr><w:rPr>
    ppr = p_el.find(qn("w:pPr"))
    if ppr is not None:
        ppr_rpr = ppr.find(qn("w:rPr"))
        if ppr_rpr is not None and len(ppr_rpr) > 0:
            return _sanitize_rpr(ppr_rpr)

    # 4. Fallback paragraphs (e.g., cell above, label cell to the left, or adjacent body paragraph)
    if fallback_p_elements:
        for fb_p in fallback_p_elements:
            if fb_p is None:
                continue
            for r in fb_p.findall(qn("w:r")):
                rpr = r.find(qn("w:rPr"))
                if rpr is not None and len(rpr) > 0:
                    return _sanitize_rpr(
                        rpr,
                        strip_bold=strip_fallback_bold,
                        strip_underline=True,
                    )
            fb_ppr = fb_p.find(qn("w:pPr"))
            if fb_ppr is not None:
                fb_rpr = fb_ppr.find(qn("w:rPr"))
                if fb_rpr is not None and len(fb_rpr) > 0:
                    return _sanitize_rpr(
                        fb_rpr,
                        strip_bold=strip_fallback_bold,
                        strip_underline=True,
                    )
    return None


def apply_dual_cjk_font_to_rpr(
    rpr,
    *,
    cn_font: Optional[str] = None,
    en_font: Optional[str] = None,
    size_pt: Optional[float] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    underline: Optional[bool] = None,
    color_hex: Optional[str] = None,
):
    """Safely update a <w:rPr> element with explicit CJK/Latin fonts without clobbering w:eastAsia."""
    if rpr is None:
        rpr = OxmlElement("w:rPr")
    if cn_font or en_font:
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        if cn_font:
            rfonts.set(qn("w:eastAsia"), cn_font)
            if not en_font and not rfonts.get(qn("w:ascii")):
                rfonts.set(qn("w:ascii"), cn_font)
                rfonts.set(qn("w:hAnsi"), cn_font)
        if en_font:
            rfonts.set(qn("w:ascii"), en_font)
            rfonts.set(qn("w:hAnsi"), en_font)
        # Strip theme font overrides so explicit font takes effect in Word/WPS
        for theme_attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if qn(theme_attr) in rfonts.attrib:
                del rfonts.attrib[qn(theme_attr)]

    if size_pt is not None:
        half_pt = str(int(round(size_pt * 2)))
        for sz_tag in ("w:sz", "w:szCs"):
            sz_el = rpr.find(qn(sz_tag))
            if sz_el is None:
                sz_el = OxmlElement(sz_tag)
                rpr.append(sz_el)
            sz_el.set(qn("w:val"), half_pt)

    if bold is not None:
        for b_tag in ("w:b", "w:bCs"):
            existing = rpr.find(qn(b_tag))
            if bold:
                if existing is None:
                    rpr.append(OxmlElement(b_tag))
                else:
                    existing.attrib.pop(qn("w:val"), None)
            elif existing is not None:
                rpr.remove(existing)

    if italic is not None:
        existing = rpr.find(qn("w:i"))
        if italic:
            if existing is None:
                rpr.append(OxmlElement("w:i"))
        elif existing is not None:
            rpr.remove(existing)

    if underline is not None:
        existing = rpr.find(qn("w:u"))
        if underline:
            if existing is None:
                existing = OxmlElement("w:u")
                rpr.append(existing)
            existing.set(qn("w:val"), "single")
        elif existing is not None:
            rpr.remove(existing)

    if color_hex is not None:
        clean_hex = color_hex.lstrip("#").upper()
        c_el = rpr.find(qn("w:color"))
        if c_el is None:
            c_el = OxmlElement("w:color")
            rpr.append(c_el)
        c_el.set(qn("w:val"), clean_hex)
        c_el.attrib.pop(qn("w:themeColor"), None)

    return rpr


# ---------------------------------------------------------------------------
# 3. Run Coalescing & Cross-Run Format-Preserving Replacement
# ---------------------------------------------------------------------------

def _rpr_canonical_xml(rpr) -> bytes:
    if rpr is None:
        return b""
    cleaned = _sanitize_rpr(rpr)
    return cleaned.xml.encode("utf-8") if hasattr(cleaned, "xml") else b""


def _run_is_pure_text(r_el) -> bool:
    """Return True if <w:r> only contains <w:rPr> and <w:t> (no drawings, fldChar, tab, br)."""
    for child in r_el:
        if child.tag not in (qn("w:rPr"), qn("w:t")):
            return False
    return True


def merge_runs_in_paragraph(p_el) -> int:
    """Strip w:proofErr and rsid attributes, and merge adjacent <w:r> elements with identical <w:rPr>."""
    # Remove proofErr markers that split runs
    for pe in p_el.findall(qn("w:proofErr")):
        p_el.remove(pe)
    for attr in RSID_ATTRS:
        p_el.attrib.pop(attr, None)

    merged_count = 0
    children = list(p_el)
    prev_run = None
    prev_sig = None

    for child in children:
        if child.tag != qn("w:r"):
            # Bookmarks or proofErr or other non-run breaks adjacency unless it's bookmarkStart/End
            if child.tag not in (qn("w:bookmarkStart"), qn("w:bookmarkEnd")):
                prev_run = None
                prev_sig = None
            continue

        for attr in RSID_ATTRS:
            child.attrib.pop(attr, None)

        if not _run_is_pure_text(child):
            prev_run = None
            prev_sig = None
            continue

        curr_sig = _rpr_canonical_xml(child.find(qn("w:rPr")))
        if prev_run is not None and curr_sig == prev_sig:
            # Merge text into prev_run
            prev_t_list = prev_run.findall(qn("w:t"))
            curr_t_list = child.findall(qn("w:t"))
            prev_text = "".join((t.text or "") for t in prev_t_list)
            curr_text = "".join((t.text or "") for t in curr_t_list)
            combined = prev_text + curr_text
            if prev_t_list:
                first_t = prev_t_list[0]
                for extra_t in prev_t_list[1:]:
                    prev_run.remove(extra_t)
            else:
                first_t = OxmlElement("w:t")
                prev_run.append(first_t)
            first_t.text = combined
            if combined.startswith(" ") or combined.endswith(" ") or "  " in combined:
                first_t.set(XML_SPACE, "preserve")
            p_el.remove(child)
            merged_count += 1
        else:
            prev_run = child
            prev_sig = curr_sig

    return merged_count


def iter_all_paragraphs_xml(doc: Document, *, include_headers_footers: bool = True):
    """Yield every <w:p> element across body, tables, SDT content controls, and headers/footers (deduplicating merged cells)."""
    seen_p = set()

    def _yield_from_root(root_el):
        if root_el is None:
            return
        for p_el in root_el.iter(qn("w:p")):
            if p_el not in seen_p:
                seen_p.add(p_el)
                yield p_el

    yield from _yield_from_root(doc.element.body)

    if include_headers_footers:
        for section in doc.sections:
            for hf in (
                section.header,
                section.first_page_header,
                section.even_page_header,
                section.footer,
                section.first_page_footer,
                section.even_page_footer,
            ):
                try:
                    if hf is not None and not hf.is_linked_to_previous:
                        yield from _yield_from_root(hf._element)
                except Exception:
                    pass


def merge_runs_in_document(doc: Document) -> int:
    total = 0
    for p_el in iter_all_paragraphs_xml(doc, include_headers_footers=True):
        total += merge_runs_in_paragraph(p_el)
    return total


def replace_text_in_paragraph_xml(p_el, old_text: str, new_text: str) -> int:
    """Replace `old_text` with `new_text` across <w:r> boundaries while preserving <w:rPr> and non-text elements."""
    if not old_text:
        return 0

    merge_runs_in_paragraph(p_el)

    # Collect all <w:t> elements inside <w:r> children of p_el
    t_nodes = []
    for r_el in p_el.findall(qn("w:r")):
        for t_el in r_el.findall(qn("w:t")):
            t_nodes.append((r_el, t_el))

    if not t_nodes:
        return 0

    full_text = "".join((t.text or "") for _, t in t_nodes)
    if old_text not in full_text:
        return 0

    starts = []
    cursor = 0
    while True:
        pos = full_text.find(old_text, cursor)
        if pos < 0:
            break
        starts.append(pos)
        cursor = pos + len(old_text)

    # Replace from back to front so earlier character offsets remain valid
    for start in reversed(starts):
        end = start + len(old_text)
        offset = 0
        first_hit = True
        for r_el, t_el in t_nodes:
            txt = t_el.text or ""
            t_start = offset
            t_end = offset + len(txt)
            overlap_start = max(start, t_start)
            overlap_end = min(end, t_end)
            if overlap_start < overlap_end:
                local_s = overlap_start - t_start
                local_e = overlap_end - t_start
                if first_hit:
                    first_hit = False
                    updated = txt[:local_s] + new_text + txt[local_e:]
                else:
                    updated = txt[:local_s] + txt[local_e:]
                t_el.text = updated
                if updated.startswith(" ") or updated.endswith(" ") or "  " in updated:
                    t_el.set(XML_SPACE, "preserve")
            offset = t_end

    # Clean up empty pure-text runs left behind by multi-run span replacement
    for r_el in list(p_el.findall(qn("w:r"))):
        if _run_is_pure_text(r_el):
            txt = "".join((t.text or "") for t in r_el.findall(qn("w:t")))
            if txt == "" and len(p_el.findall(qn("w:r"))) > 1:
                p_el.remove(r_el)

    return len(starts)


def replace_text_in_document_xml(
    doc: Document,
    old_text: str,
    new_text: str,
    *,
    include_headers_footers: bool = True,
) -> Dict[str, Any]:
    """Perform cross-run format-preserving text replacement across the entire document."""
    total_occurrences = 0
    locations: List[Dict[str, Any]] = []

    # 1. Body paragraphs
    for i, para in enumerate(doc.paragraphs):
        before = para.text
        if old_text in before:
            cnt = replace_text_in_paragraph_xml(para._p, old_text, new_text)
            if cnt > 0:
                total_occurrences += cnt
                locations.append({
                    "type": "paragraph",
                    "index": i,
                    "count": cnt,
                    "before": before,
                    "after": para.text,
                })

    # 2. Tables (deduplicating merged _tc cells)
    seen_tc = set()
    for t_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                tc_el = cell._tc
                if tc_el in seen_tc:
                    continue
                seen_tc.add(tc_el)
                cell_cnt = 0
                before_cell = cell.text
                if old_text in before_cell:
                    for para in cell.paragraphs:
                        cell_cnt += replace_text_in_paragraph_xml(para._p, old_text, new_text)
                if cell_cnt > 0:
                    total_occurrences += cell_cnt
                    locations.append({
                        "type": "table_cell",
                        "table_index": t_idx,
                        "row": r_idx,
                        "col": c_idx,
                        "count": cell_cnt,
                        "before": before_cell,
                        "after": cell.text,
                    })

    # 3. Remaining paragraphs (inside <w:sdt> content controls, textboxes, headers, footers)
    body_and_table_p = {p._p for p in doc.paragraphs}
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    body_and_table_p.add(p._p)

    for p_el in iter_all_paragraphs_xml(doc, include_headers_footers=include_headers_footers):
        if p_el in body_and_table_p:
            continue
        before_txt = "".join((t.text or "") for t in p_el.iter(qn("w:t")))
        if old_text in before_txt:
            cnt = replace_text_in_paragraph_xml(p_el, old_text, new_text)
            if cnt > 0:
                after_txt = "".join((t.text or "") for t in p_el.iter(qn("w:t")))
                total_occurrences += cnt
                locations.append({
                    "type": "sdt_or_header_footer",
                    "count": cnt,
                    "before": before_txt,
                    "after": after_txt,
                })

    return {
        "total_occurrences": total_occurrences,
        "location_count": len(locations),
        "locations": locations,
    }


# ---------------------------------------------------------------------------
# 4. Format-Preserving Paragraph & Cell Setters (Multi-line & Blank-Aware)
# ---------------------------------------------------------------------------

def _populate_single_p_with_rpr(p_el, text: str, template_rpr) -> None:
    """Clear only <w:r> / <w:proofErr> / <w:hyperlink> children from `p_el` (preserving <w:pPr>) and add a styled run."""
    for child in list(p_el):
        if child.tag != qn("w:pPr"):
            p_el.remove(child)

    r_el = OxmlElement("w:r")
    if template_rpr is not None:
        r_el.append(copy.deepcopy(template_rpr))
    t_el = OxmlElement("w:t")
    t_el.text = text
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        t_el.set(XML_SPACE, "preserve")
    r_el.append(t_el)
    p_el.append(r_el)


def set_paragraph_text_preserving_format(
    doc: Document,
    para_index: int,
    text: str,
    *,
    preserve_label_blank: bool = True,
) -> Dict[str, Any]:
    """Set text of `doc.paragraphs[para_index]` while preserving 100% of <w:pPr> and <w:rPr>.

    Features:
      - If the paragraph has 'Label：______' structure and `preserve_label_blank=True`:
        keeps the non-underlined label intact and writes the value into the underlined blank run!
      - If `text` has multiple lines ('\\n'), splits into multiple paragraphs, each cloning <w:pPr> and <w:rPr>.
      - If the target paragraph is initially empty, inherits <w:rPr> from <w:pPr><w:rPr> or adjacent body paragraphs.
    """
    paras = doc.paragraphs
    if para_index < 0 or para_index >= len(paras):
        raise IndexError(f"Paragraph index {para_index} out of range (0..{len(paras) - 1})")

    target_p = paras[para_index]._p

    # Check if this paragraph is a 'Label：______' fill-in-the-blank line
    if preserve_label_blank and "\n" not in text:
        blank_info = detect_underlined_blank(target_p)
        if blank_info is not None:
            prefix = blank_info["label_prefix"]
            # If caller passed "Label：Value", strip the duplicate prefix
            fill_val = text
            if fill_val.startswith(prefix):
                fill_val = fill_val[len(prefix):]
            elif "：" in prefix and "：" in fill_val:
                p_head = prefix.split("：", 1)[0].strip()
                f_head, f_tail = fill_val.split("：", 1)
                if p_head == f_head.strip():
                    fill_val = f_tail

            runs = target_p.findall(qn("w:r"))
            u_indices = blank_info["blank_Indices"]
            orig_blank_len = len(blank_info["current_blank_text"])
            # Pad with spaces if original blank had padding spaces so underline stays aesthetically wide
            if orig_blank_len > len(fill_val) and set(blank_info["current_blank_text"].strip()) == set():
                pad_total = max(2, orig_blank_len - len(fill_val) * 2)
                pad_left = " " * (pad_total // 2)
                pad_right = " " * (pad_total - len(pad_left))
                final_blank = f"{pad_left}{fill_val}{pad_right}"
            else:
                final_blank = f" {fill_val} " if fill_val else ""

            first_u_run = runs[u_indices[0]]
            # Ensure underline is present on first_u_run
            rpr = first_u_run.find(qn("w:rPr"))
            if rpr is None:
                rpr = OxmlElement("w:rPr")
                first_u_run.insert(0, rpr)
            if rpr.find(qn("w:u")) is None:
                u_el = OxmlElement("w:u")
                u_el.set(qn("w:val"), "single")
                rpr.append(u_el)

            # Set text on first underlined run and remove extra underlined runs
            t_list = first_u_run.findall(qn("w:t"))
            if t_list:
                t_list[0].text = final_blank
                t_list[0].set(XML_SPACE, "preserve")
                for extra_t in t_list[1:]:
                    first_u_run.remove(extra_t)
            else:
                t_el = OxmlElement("w:t")
                t_el.text = final_blank
                t_el.set(XML_SPACE, "preserve")
                first_u_run.append(t_el)

            for rm_idx in reversed(u_indices[1:]):
                target_p.remove(runs[rm_idx])

            return {
                "mode": "underlined_blank_fill",
                "paragraph_index": para_index,
                "label_preserved": prefix,
                "filled_value": fill_val,
            }

    # Gather fallback body paragraphs (neighbors that aren't headings)
    fallbacks = []
    for offset in (1, -1, 2, -2):
        nb_idx = para_index + offset
        if 0 <= nb_idx < len(paras):
            nb_p = paras[nb_idx]
            st_name = (nb_p.style.name or "").lower() if nb_p.style else ""
            if "heading" not in st_name and "标题" not in st_name and "title" not in st_name:
                fallbacks.append(nb_p._p)

    best_rpr = extract_best_rpr_for_paragraph(target_p, fallback_p_elements=fallbacks)
    template_ppr = copy.deepcopy(target_p.find(qn("w:pPr")))

    lines = text.split("\n") if text else [""]
    _populate_single_p_with_rpr(target_p, lines[0], best_rpr)

    anchor_p = target_p
    for extra_line in lines[1:]:
        new_p = OxmlElement("w:p")
        if template_ppr is not None:
            new_p.append(copy.deepcopy(template_ppr))
        _populate_single_p_with_rpr(new_p, extra_line, best_rpr)
        anchor_p.addnext(new_p)
        anchor_p = new_p

    return {
        "mode": "paragraph_set",
        "paragraph_index": para_index,
        "lines_written": len(lines),
        "rpr_preserved": best_rpr is not None,
    }


def compute_table_merge_map(table) -> Dict[Tuple[int, int], Tuple[int, int]]:
    """Map every (row, col) in `table` to its canonical origin (origin_row, origin_col) based on `_tc` identity."""
    tc_to_origin: Dict[Any, Tuple[int, int]] = {}
    coord_to_origin: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            tc_el = cell._tc
            if tc_el not in tc_to_origin:
                tc_to_origin[tc_el] = (r_idx, c_idx)
            coord_to_origin[(r_idx, c_idx)] = tc_to_origin[tc_el]
    return coord_to_origin


def set_cell_text_preserving_format(
    doc: Document,
    table_index: int,
    row_index: int,
    col_index: int,
    text: str,
    *,
    allow_overwrite_merged_label: bool = False,
) -> Dict[str, Any]:
    """Set text of `doc.tables[table_index].cell(row_index, col_index)` while preserving <w:tcPr>, <w:pPr>, and <w:rPr>."""
    if table_index < 0 or table_index >= len(doc.tables):
        raise IndexError(f"Table index {table_index} out of range (0..{len(doc.tables) - 1})")
    table = doc.tables[table_index]
    if row_index < 0 or row_index >= len(table.rows):
        raise IndexError(f"Row index {row_index} out of range (0..{len(table.rows) - 1})")
    if col_index < 0 or col_index >= len(table.columns):
        raise IndexError(f"Col index {col_index} out of range (0..{len(table.columns) - 1})")

    merge_map = compute_table_merge_map(table)
    origin_r, origin_c = merge_map.get((row_index, col_index), (row_index, col_index))
    is_merged_continuation = (origin_r, origin_c) != (row_index, col_index)

    target_cell = table.cell(row_index, col_index)
    existing_text = target_cell.text.strip()

    # Guard against accidentally writing into a merged continuation cell that shares _tc with a non-empty label cell!
    if is_merged_continuation and origin_c < col_index and existing_text and not allow_overwrite_merged_label:
        # Check if there is an unmerged empty cell further right in the same row
        suggestion = None
        for probe_c in range(col_index + 1, len(table.columns)):
            if merge_map.get((row_index, probe_c)) == (row_index, probe_c):
                suggestion = (row_index, probe_c)
                break
        raise ValueError(
            f"Cell ({row_index}, {col_index}) in table {table_index} is merged with non-empty cell "
            f"({origin_r}, {origin_c}) containing {existing_text!r}. Writing here would clobber that cell! "
            + (f"Did you mean cell ({suggestion[0]}, {suggestion[1]})?" if suggestion else "Pass allow_overwrite_merged_label=True if intentional.")
        )

    # Ensure at least one <w:p> exists in <w:tc>
    if not target_cell.paragraphs:
        target_cell._tc.append(OxmlElement("w:p"))

    first_p = target_cell.paragraphs[0]._p
    template_ppr = copy.deepcopy(first_p.find(qn("w:pPr")))

    # Collect fallback paragraphs for rPr inheritance if target cell has no explicit rPr:
    # Priority 1: Data cell directly above (row_index - 1, col_index) if row_index > 1 (or row_index == 1 and not header)
    # Priority 2: Data cell below (row_index + 1, col_index)
    # Priority 3: Adjacent label cell (row_index, col_index - 1) with bold stripped
    data_fallbacks = []
    label_fallbacks = []
    if row_index > 0:
        above_tc = table.cell(row_index - 1, col_index)._tc
        if above_tc is not target_cell._tc:
            above_p_list = above_tc.findall(qn("w:p"))
            if above_p_list:
                if row_index > 1:
                    data_fallbacks.append(above_p_list[0])
                else:
                    label_fallbacks.append(above_p_list[0])
    if row_index + 1 < len(table.rows):
        below_tc = table.cell(row_index + 1, col_index)._tc
        if below_tc is not target_cell._tc:
            below_p_list = below_tc.findall(qn("w:p"))
            if below_p_list:
                data_fallbacks.append(below_p_list[0])
    if col_index > 0:
        left_tc = table.cell(row_index, col_index - 1)._tc
        if left_tc is not target_cell._tc:
            left_p_list = left_tc.findall(qn("w:p"))
            if left_p_list:
                label_fallbacks.append(left_p_list[0])

    best_rpr = extract_best_rpr_for_paragraph(first_p, fallback_p_elements=data_fallbacks, strip_fallback_bold=False)
    if best_rpr is None and label_fallbacks:
        best_rpr = extract_best_rpr_for_paragraph(first_p, fallback_p_elements=label_fallbacks, strip_fallback_bold=True)

    # Also ensure <w:pPr><w:rPr> on template_ppr has best_rpr so Word GUI keeps the font if the user edits later
    if best_rpr is not None:
        if template_ppr is None:
            template_ppr = OxmlElement("w:pPr")
            first_p.insert(0, copy.deepcopy(template_ppr))
        if template_ppr.find(qn("w:rPr")) is None:
            template_ppr.append(copy.deepcopy(best_rpr))

    # Remove extra paragraphs in the cell
    for extra_para in list(target_cell.paragraphs[1:]):
        extra_para._p.getparent().remove(extra_para._p)

    lines = str(text).split("\n") if text is not None else [""]
    _populate_single_p_with_rpr(first_p, lines[0], best_rpr)

    anchor_p = first_p
    for extra_line in lines[1:]:
        new_p = OxmlElement("w:p")
        if template_ppr is not None:
            new_p.append(copy.deepcopy(template_ppr))
        _populate_single_p_with_rpr(new_p, extra_line, best_rpr)
        anchor_p.addnext(new_p)
        anchor_p = new_p

    return {
        "table_index": table_index,
        "row": row_index,
        "col": col_index,
        "canonical_coord": [origin_r, origin_c],
        "lines_written": len(lines),
        "rpr_preserved": best_rpr is not None,
    }


def clone_table_row_preserving_format(
    doc: Document,
    table_index: int,
    data: Optional[List[str]] = None,
    *,
    source_row_index: int = -1,
) -> Dict[str, Any]:
    """Append a new row to `doc.tables[table_index]` by deep-cloning a template row's <w:trPr>, <w:tcPr>, <w:pPr>, and <w:rPr>."""
    if table_index < 0 or table_index >= len(doc.tables):
        raise IndexError(f"Table index {table_index} out of range (0..{len(doc.tables) - 1})")
    table = doc.tables[table_index]
    if not table.rows:
        raise ValueError(f"Table {table_index} has no rows to clone")

    src_idx = source_row_index if source_row_index >= 0 else len(table.rows) + source_row_index
    src_idx = max(0, min(len(table.rows) - 1, src_idx))
    src_tr = table.rows[src_idx]._tr

    new_tr = copy.deepcopy(src_tr)
    # Strip vertical merge continuations on the cloned row so it acts as a fresh row
    for tcPr in new_tr.findall(f".//{qn('w:tcPr')}"):
        vmerge = tcPr.find(qn("w:vMerge"))
        if vmerge is not None:
            tcPr.remove(vmerge)

    table._tbl.append(new_tr)
    new_row_idx = len(table.rows) - 1

    # Clear text in all cells of the new row while preserving their rPr/pPr
    seen_tc = set()
    for c_idx, cell in enumerate(table.rows[new_row_idx].cells):
        tc_el = cell._tc
        if tc_el in seen_tc:
            continue
        seen_tc.add(tc_el)
        val = str(data[c_idx]) if (data and c_idx < len(data)) else ""
        set_cell_text_preserving_format(
            doc,
            table_index,
            new_row_idx,
            c_idx,
            val,
            allow_overwrite_merged_label=True,
        )

    return {
        "table_index": table_index,
        "new_row_index": new_row_idx,
        "cloned_from_row": src_idx,
    }


def _detect_heading_tier(text: str, style_name: str) -> Optional[int]:
    """Detect structural heading tier (1=highest, 4=lowest) from style name or Chinese/numeric prefix."""
    s_low = (style_name or "").lower()
    m_h = re.search(r"(?:heading|标题)\s*(\d+)", s_low)
    if m_h:
        return int(m_h.group(1))
    stripped = text.strip()
    if not stripped or len(stripped) > 80:
        return None
    if re.match(r"^(?:第[一二三四五六七八九十百]+[章节部分篇]|[一二三四五六七八九十百]+、)", stripped):
        return 1
    if re.match(r"^[（(][一二三四五六七八九十百]+[）)]", stripped):
        return 2
    if re.match(r"^\d+[\.．、]\s*\S", stripped) and not re.search(r"[。；！？]$", stripped):
        return 3
    if re.match(r"^[（(]\d+[）)]", stripped) and not re.search(r"[。；！？]$", stripped):
        return 4
    return None


def replace_section_preserving_format(
    doc: Document,
    section_title: str,
    new_paragraphs: List[str],
    *,
    preserve_title: bool = True,
) -> Dict[str, Any]:
    """Find heading containing `section_title` and replace its body paragraphs up to the next sibling/parent heading."""
    paras = doc.paragraphs
    title_index = -1
    for i, p in enumerate(paras):
        if section_title in p.text:
            title_index = i
            break
    if title_index == -1:
        raise ValueError(f"Section title not found: {section_title!r}")

    title_p = paras[title_index]
    title_style_name = title_p.style.name if title_p.style else "Normal"
    title_tier = _detect_heading_tier(title_p.text, title_style_name)
    title_sig = resolve_paragraph_signature(doc, title_p._p, title_p.style)

    # Determine end_index (stop before next heading of same or higher tier)
    end_index = len(paras)
    for i in range(title_index + 1, len(paras)):
        cand = paras[i]
        cand_txt = cand.text.strip()
        if not cand_txt:
            continue
        cand_style = cand.style.name if cand.style else "Normal"
        cand_tier = _detect_heading_tier(cand_txt, cand_style)
        if cand_tier is not None:
            if title_tier is not None and cand_tier <= title_tier:
                end_index = i
                break
            elif title_tier is None and cand_tier <= 2:
                end_index = i
                break
        # Also check if candidate has identical bold heading font when body had smaller/non-bold font
        if i > title_index + 1 and title_sig.get("bold"):
            cand_sig = resolve_paragraph_signature(doc, cand._p, cand.style)
            if (
                cand_sig.get("bold")
                and cand_sig.get("eastAsia") == title_sig.get("eastAsia")
                and cand_sig.get("size_pt") == title_sig.get("size_pt")
                and len(cand_txt) <= 40
            ):
                end_index = i
                break

    start_delete = title_index + (1 if preserve_title else 0)

    # Extract body template <w:pPr> and <w:rPr> from the first existing body paragraph in [title_index+1 .. end_index)
    body_template_ppr = None
    body_best_rpr = None
    if title_index + 1 < end_index:
        first_body_p = paras[title_index + 1]._p
        body_template_ppr = copy.deepcopy(first_body_p.find(qn("w:pPr")))
        body_best_rpr = extract_best_rpr_for_paragraph(first_body_p)
    if body_best_rpr is None:
        # Fallback to other non-heading body paragraphs in document, or title with bold stripped
        fallback_ps = [
            p._p for idx, p in enumerate(paras)
            if idx != title_index and _detect_heading_tier(p.text, p.style.name if p.style else "") is None and p.text.strip()
        ]
        body_best_rpr = extract_best_rpr_for_paragraph(
            title_p._p, fallback_p_elements=fallback_ps, strip_fallback_bold=True
        )
        if body_best_rpr is not None:
            body_best_rpr = _sanitize_rpr(body_best_rpr, strip_bold=True, strip_underline=True)

    # Flatten any multi-line strings in new_paragraphs
    expanded_lines: List[str] = []
    for item in new_paragraphs:
        expanded_lines.extend(str(item).split("\n"))

    # Anchor element to insert after
    anchor_el = title_p._p if preserve_title else (paras[title_index - 1]._p if title_index > 0 else None)

    # Remove old paragraphs in [start_delete .. end_index)
    for i in range(end_index - 1, start_delete - 1, -1):
        p_el = paras[i]._p
        p_el.getparent().remove(p_el)

    # Insert new paragraphs with cloned body <w:pPr> and <w:rPr>
    curr_anchor = anchor_el
    for line_text in expanded_lines:
        new_p = OxmlElement("w:p")
        if body_template_ppr is not None:
            new_p.append(copy.deepcopy(body_template_ppr))
        _populate_single_p_with_rpr(new_p, line_text, body_best_rpr)
        if curr_anchor is not None:
            curr_anchor.addnext(new_p)
        else:
            doc.element.body.insert(0, new_p)
        curr_anchor = new_p

    return {
        "section_title": section_title,
        "title_index": title_index,
        "replaced_range": [start_delete, end_index],
        "paragraphs_written": len(expanded_lines),
        "rpr_preserved": body_best_rpr is not None,
    }


# ---------------------------------------------------------------------------
# 5. Deep Template Inspection, Batch Fill, and Post-Edit Audit
# ---------------------------------------------------------------------------

def inspect_document_blueprint(doc: Document, path: str = "", max_len: int = 120) -> Dict[str, Any]:
    """Produce a comprehensive structural & typographic blueprint of a .docx template."""
    # 1. Sections
    sections_info = []
    for idx, sec in enumerate(doc.sections):
        sec_item: Dict[str, Any] = {
            "index": idx,
            "width_cm": round(sec.page_width.cm, 2) if sec.page_width else None,
            "height_cm": round(sec.page_height.cm, 2) if sec.page_height else None,
            "margins_cm": {
                "top": round(sec.top_margin.cm, 2) if sec.top_margin else None,
                "bottom": round(sec.bottom_margin.cm, 2) if sec.bottom_margin else None,
                "left": round(sec.left_margin.cm, 2) if sec.left_margin else None,
                "right": round(sec.right_margin.cm, 2) if sec.right_margin else None,
            },
        }
        try:
            hdr_txt = " | ".join(p.text.strip() for p in sec.header.paragraphs if p.text.strip())
            if hdr_txt:
                sec_item["header_text"] = hdr_txt[:80]
        except Exception:
            pass
        try:
            ftr_txt = " | ".join(p.text.strip() for p in sec.footer.paragraphs if p.text.strip())
            if ftr_txt:
                sec_item["footer_text"] = ftr_txt[:80]
        except Exception:
            pass
        sections_info.append(sec_item)

    # 2. Paragraphs
    paragraphs_info = []
    placeholder_hits = []
    placeholder_re = re.compile(r"(\{\{[^{}]+\}\}|【[^【】]{1,30}】|\$[A-Za-z0-9_]+\$)")

    for i, para in enumerate(doc.paragraphs):
        raw_text = para.text
        disp_text = (raw_text[:max_len] + "...") if (max_len and len(raw_text) > max_len) else raw_text
        font_sig = resolve_paragraph_signature(doc, para._p, para.style)
        layout_sig = extract_paragraph_layout(para._p)
        blank_info = detect_underlined_blank(para._p)

        p_entry: Dict[str, Any] = {
            "index": i,
            "style": para.style.name if para.style else "Normal",
            "text": disp_text,
            "is_empty": raw_text.strip() == "",
            "font": font_sig,
        }
        if layout_sig:
            p_entry["layout"] = layout_sig
        if blank_info:
            p_entry["underlined_blank"] = {
                "label_prefix": blank_info["label_prefix"],
                "blank_width": len(blank_info["current_blank_text"]),
            }
        paragraphs_info.append(p_entry)

        for m in placeholder_re.findall(raw_text):
            placeholder_hits.append({"location": f"paragraph[{i}]", "placeholder": m})

    # 3. Tables (with merged-cell topology & cell font signatures)
    tables_info = []
    for t_idx, table in enumerate(doc.tables):
        merge_map = compute_table_merge_map(table)
        rows_data = []
        merged_ranges = []
        for r_idx, row in enumerate(table.rows):
            row_cells = []
            for c_idx, cell in enumerate(row.cells):
                origin_r, origin_c = merge_map[(r_idx, c_idx)]
                is_merged = (origin_r, origin_c) != (r_idx, c_idx)
                raw_c = cell.text.strip()
                disp_c = (raw_c[:max_len] + "...") if (max_len and len(raw_c) > max_len) else raw_c
                first_p = cell.paragraphs[0] if cell.paragraphs else None
                cell_font = (
                    resolve_paragraph_signature(doc, first_p._p, first_p.style)
                    if first_p is not None
                    else {}
                )
                c_entry: Dict[str, Any] = {
                    "coord": f"{r_idx},{c_idx}",
                    "text": disp_c,
                    "is_empty": raw_c == "",
                    "font": cell_font,
                }
                if is_merged:
                    c_entry["merged_into"] = f"{origin_r},{origin_c}"
                    merged_ranges.append(f"({r_idx},{c_idx})->({origin_r},{origin_c})")
                else:
                    for m in placeholder_re.findall(raw_c):
                        placeholder_hits.append({"location": f"table[{t_idx}]({r_idx},{c_idx})", "placeholder": m})
                row_cells.append(c_entry)
            rows_data.append(row_cells)

        tables_info.append({
            "index": t_idx,
            "rows": len(table.rows),
            "cols": len(table.columns),
            "merged_cells_count": len(merged_ranges),
            "cells": rows_data,
        })

    # 4. SDT Content Controls (<w:sdt>)
    sdt_controls = []
    for sdt_idx, sdt in enumerate(doc.element.body.findall(f".//{qn('w:sdt')}")):
        sdt_pr = sdt.find(qn("w:sdtPr"))
        alias_el = sdt_pr.find(qn("w:alias")) if sdt_pr is not None else None
        tag_el = sdt_pr.find(qn("w:tag")) if sdt_pr is not None else None
        sdt_text = "".join((t.text or "") for t in sdt.findall(f".//{qn('w:t')}")).strip()
        sdt_controls.append({
            "index": sdt_idx,
            "alias": _attr(alias_el, "val"),
            "tag": _attr(tag_el, "val"),
            "text": sdt_text[:max_len] if max_len else sdt_text,
        })

    return {
        "path": os.path.abspath(path) if path else "",
        "section_count": len(doc.sections),
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "sdt_control_count": len(sdt_controls),
        "placeholders_detected": placeholder_hits,
        "sections": sections_info,
        "paragraphs": paragraphs_info,
        "tables": tables_info,
        "sdt_controls": sdt_controls,
    }


def format_blueprint_markdown(bp: Dict[str, Any]) -> str:
    """Format the document blueprint as a compact, Agent-friendly Markdown report."""
    lines = [
        f"# DOCX 模板结构与字体蓝图: `{bp.get('path', '')}`",
        f"- **节数 (Sections)**: {bp['section_count']} | **正文段落数**: {bp['paragraph_count']} | **表格数**: {bp['table_count']} | **SDT 内容控件数**: {bp['sdt_control_count']}",
    ]
    if bp.get("sections"):
        s0 = bp["sections"][0]
        m = s0.get("margins_cm", {})
        lines.append(
            f"- **页面尺寸**: {s0.get('width_cm')}×{s0.get('height_cm')} cm | "
            f"**页边距 (上/下/左/右)**: {m.get('top')}/{m.get('bottom')}/{m.get('left')}/{m.get('right')} cm"
        )
        if s0.get("header_text"):
            lines.append(f"- **页眉**: `{s0['header_text']}`")
        if s0.get("footer_text"):
            lines.append(f"- **页脚**: `{s0['footer_text']}`")

    if bp.get("placeholders_detected"):
        lines.append(f"\n## 发现的显式占位符 ({len(bp['placeholders_detected'])} 处)")
        for ph in bp["placeholders_detected"][:30]:
            lines.append(f"- `{ph['location']}`: `{ph['placeholder']}`")

    lines.append("\n## 正文段落结构与字体签名 (Paragraphs)")
    for p in bp["paragraphs"]:
        f = p.get("font", {})
        f_str = f"{f.get('eastAsia') or f.get('ascii') or '默认'}/{f.get('size_pt') or '?'}pt"
        if f.get("bold"):
            f_str += "/B"
        if f.get("underline"):
            f_str += "/U"
        blank_tag = ""
        if p.get("underlined_blank"):
            blank_tag = f" [下划线填空: 前缀={p['underlined_blank']['label_prefix']!r}]"
        elif p.get("is_empty"):
            blank_tag = " [空段落占位]"
        txt_preview = p["text"].replace("\n", "⏎")
        lines.append(f"- `[{p['index']}]` (style=`{p['style']}`, font=`{f_str}`){blank_tag}: {txt_preview}")

    for t in bp["tables"]:
        lines.append(f"\n## 表格 {t['index']} ({t['rows']} 行 × {t['cols']} 列, 合并延续格: {t['merged_cells_count']})")
        for r_idx, row in enumerate(t["cells"]):
            cell_strs = []
            for c in row:
                if "merged_into" in c:
                    cell_strs.append(f"`({c['coord']})` ↳合并至`({c['merged_into']})`")
                else:
                    f = c.get("font", {})
                    f_short = f"{f.get('eastAsia') or f.get('ascii') or '默认'}:{f.get('size_pt') or '?'}pt"
                    val = c["text"].replace("\n", "⏎") if not c["is_empty"] else "<空>"
                    cell_strs.append(f"`({c['coord']})` [{f_short}] {val}")
            lines.append(f"  - Row {r_idx}: " + " | ".join(cell_strs))

    return "\n".join(lines)


def fill_template_from_spec(doc: Document, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Batch fill a template .docx from a declarative spec while preserving 100% of formatting.

    Supported keys in `spec`:
      - "merge_runs": true/false (optional, default true)
      - "replacements": {"{{name}}": "张三", "旧文本": "新文本"}
      - "paragraphs": {"5": "段落文本...", "8": "多行1\\n多行2"} OR [{"index": 5, "text": "..."}]
      - "cells": {"0": {"0,1": "张三"}} OR [{"table": 0, "row": 0, "col": 1, "text": "张三"}]
      - "append_rows": {"0": [["行1列1", "行1列2"]]} OR [{"table": 0, "rows": [["行1列1", "行1列2"]]}]
    """
    summary: Dict[str, Any] = {
        "replacements": {},
        "paragraphs_filled": [],
        "cells_filled": [],
        "rows_appended": [],
        "errors": [],
    }

    if spec.get("merge_runs", True):
        merge_runs_in_document(doc)

    # 1. Cross-run replacements
    for old_txt, new_txt in spec.get("replacements", {}).items():
        res = replace_text_in_document_xml(doc, str(old_txt), str(new_txt))
        summary["replacements"][old_txt] = res["total_occurrences"]

    # 2. Paragraphs (process in descending index order so multi-line paragraph insertions don't shift earlier indices!)
    para_items: List[Tuple[int, str, bool]] = []
    raw_paras = spec.get("paragraphs", {})
    if isinstance(raw_paras, dict):
        for k, v in raw_paras.items():
            try:
                para_items.append((int(k), str(v), True))
            except ValueError:
                summary["errors"].append(f"Invalid paragraph index key: {k!r}")
    elif isinstance(raw_paras, list):
        for item in raw_paras:
            if isinstance(item, dict) and "index" in item and "text" in item:
                para_items.append((
                    int(item["index"]),
                    str(item["text"]),
                    bool(item.get("preserve_label_blank", item.get("preserve_prefix_before_colon", True))),
                ))

    for p_idx, p_text, keep_blank in sorted(para_items, key=lambda x: x[0], reverse=True):
        try:
            res = set_paragraph_text_preserving_format(
                doc, p_idx, p_text, preserve_label_blank=keep_blank
            )
            summary["paragraphs_filled"].append(res)
        except Exception as exc:
            summary["errors"].append(f"Paragraph [{p_idx}]: {exc}")

    # 3. Table cells
    raw_cells = spec.get("cells", {})
    if isinstance(raw_cells, dict):
        for t_str, cell_map in raw_cells.items():
            try:
                t_idx = int(t_str)
            except ValueError:
                summary["errors"].append(f"Invalid table index key: {t_str!r}")
                continue
            if not isinstance(cell_map, dict):
                summary["errors"].append(f"Table {t_idx} cells spec must be an object mapping 'row,col' -> text")
                continue
            for coord_str, c_text in cell_map.items():
                try:
                    r_str, c_str = [x.strip() for x in coord_str.split(",", 1)]
                    r_idx, c_idx = int(r_str), int(c_str)
                    res = set_cell_text_preserving_format(doc, t_idx, r_idx, c_idx, str(c_text))
                    summary["cells_filled"].append(res)
                except Exception as exc:
                    summary["errors"].append(f"Table {t_idx} cell ({coord_str}): {exc}")
    elif isinstance(raw_cells, list):
        for item in raw_cells:
            if isinstance(item, dict):
                try:
                    t_idx = int(item.get("table", item.get("table_index", 0)))
                    r_idx = int(item["row"])
                    c_idx = int(item["col"])
                    c_text = str(item.get("text", ""))
                    res = set_cell_text_preserving_format(doc, t_idx, r_idx, c_idx, c_text)
                    summary["cells_filled"].append(res)
                except Exception as exc:
                    summary["errors"].append(f"Table cell {item}: {exc}")

    # 4. Append table rows
    raw_append = spec.get("append_rows", {})
    if isinstance(raw_append, dict):
        for t_str, rows_list in raw_append.items():
            try:
                t_idx = int(t_str)
                for row_vals in rows_list:
                    res = clone_table_row_preserving_format(doc, t_idx, [str(x) for x in row_vals])
                    summary["rows_appended"].append(res)
            except Exception as exc:
                summary["errors"].append(f"Table {t_str} append_rows: {exc}")
    elif isinstance(raw_append, list):
        for item in raw_append:
            if isinstance(item, dict):
                try:
                    t_idx = int(item.get("table", item.get("table_index", 0)))
                    src_row = int(item.get("template_row", item.get("source_row_index", -1)))
                    for row_vals in item.get("rows", []):
                        res = clone_table_row_preserving_format(
                            doc, t_idx, [str(x) for x in row_vals], source_row_index=src_row
                        )
                        summary["rows_appended"].append(res)
                except Exception as exc:
                    summary["errors"].append(f"Table append_rows {item}: {exc}")

    return summary


def audit_document_against_template(template_doc: Document, output_doc: Document) -> Dict[str, Any]:
    """Compare an edited document against its reference template to catch structural or font regressions."""
    issues: List[str] = []
    warnings: List[str] = []

    # 1. Section & Page Setup check
    if len(template_doc.sections) != len(output_doc.sections):
        issues.append(
            f"Section count changed: template has {len(template_doc.sections)}, output has {len(output_doc.sections)}"
        )
    else:
        for idx, (s_tpl, s_out) in enumerate(zip(template_doc.sections, output_doc.sections)):
            if s_tpl.page_width != s_out.page_width or s_tpl.page_height != s_out.page_height:
                issues.append(f"Section {idx} page dimensions altered from template")
            if s_tpl.left_margin != s_out.left_margin or s_tpl.top_margin != s_out.top_margin:
                issues.append(f"Section {idx} page margins altered from template")

    # 2. Table count & column structure check
    if len(template_doc.tables) != len(output_doc.tables):
        issues.append(
            f"Table count changed: template has {len(template_doc.tables)}, output has {len(output_doc.tables)}"
        )
    else:
        for t_idx, (t_tpl, t_out) in enumerate(zip(template_doc.tables, output_doc.tables)):
            if len(t_tpl.columns) != len(t_out.columns):
                issues.append(
                    f"Table {t_idx} column count changed: template has {len(t_tpl.columns)}, output has {len(t_out.columns)}"
                )

    # 3. Collect allowed CJK fonts from template
    tpl_cjk_fonts = set()
    for p_el in iter_all_paragraphs_xml(template_doc):
        sig = resolve_paragraph_signature(template_doc, p_el)
        if sig.get("eastAsia"):
            tpl_cjk_fonts.add(sig["eastAsia"])

    # 4. Scan output document for font contamination (e.g., Times New Roman in w:eastAsia, or unexpected default fonts)
    latin_only_fonts = {"times new roman", "arial", "calibri", "consolas", "courier new", "helvetica"}
    font_anomalies = []
    for i, para in enumerate(output_doc.paragraphs):
        if not para.text.strip():
            continue
        sig = resolve_paragraph_signature(output_doc, para._p, para.style)
        ea = sig.get("eastAsia")
        if ea and ea.lower() in latin_only_fonts:
            font_anomalies.append(f"paragraph[{i}] has Latin font {ea!r} set in w:eastAsia (CJK font slot)")
        elif tpl_cjk_fonts and ea and ea not in tpl_cjk_fonts:
            warnings.append(f"paragraph[{i}] uses CJK font {ea!r} not seen in template ({sorted(tpl_cjk_fonts)})")

    seen_tc = set()
    for t_idx, table in enumerate(output_doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                tc_el = cell._tc
                if tc_el in seen_tc:
                    continue
                seen_tc.add(tc_el)
                if not cell.text.strip():
                    continue
                first_p = cell.paragraphs[0] if cell.paragraphs else None
                if first_p is not None:
                    sig = resolve_paragraph_signature(output_doc, first_p._p, first_p.style)
                    ea = sig.get("eastAsia")
                    if ea and ea.lower() in latin_only_fonts:
                        font_anomalies.append(
                            f"table[{t_idx}]({r_idx},{c_idx}) has Latin font {ea!r} in w:eastAsia"
                        )
                    elif tpl_cjk_fonts and not ea and any("\u4e00" <= ch <= "\u9fff" for ch in cell.text):
                        warnings.append(
                            f"table[{t_idx}]({r_idx},{c_idx}) contains Chinese text but has no resolved w:eastAsia font"
                        )

    issues.extend(font_anomalies)

    # 5. Check for unreplaced placeholders in output
    out_bp = inspect_document_blueprint(output_doc)
    leftover = out_bp.get("placeholders_detected", [])
    if leftover:
        warnings.append(f"Found {len(leftover)} unreplaced placeholder(s): {leftover[:10]}")

    return {
        "passed": len(issues) == 0,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "template_cjk_fonts": sorted(tpl_cjk_fonts),
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 5b. From-Scratch Document Builder (`build --spec <spec.json>`)
# ---------------------------------------------------------------------------

def _set_table_borders_xml(table, mode: str = "grid") -> None:
    """Apply clean OOXML table borders ('three-line' academic style or 'grid' full borders)."""
    tbl_pr = table._tbl.tblPr
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)
    if mode == "none":
        xml = (
            f'<w:tblBorders {nsdecls("w")}>'
            '<w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/>'
            '<w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/>'
            "</w:tblBorders>"
        )
    elif mode in ("three-line", "three_line", "academic"):
        xml = (
            f'<w:tblBorders {nsdecls("w")}>'
            '<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
            '<w:left w:val="none"/>'
            '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
            '<w:right w:val="none"/>'
            '<w:insideH w:val="none"/>'
            '<w:insideV w:val="none"/>'
            "</w:tblBorders>"
        )
    else:
        xml = (
            f'<w:tblBorders {nsdecls("w")}>'
            '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            "</w:tblBorders>"
        )
    tbl_pr.append(parse_xml(xml))
    if mode in ("three-line", "three_line", "academic") and len(table.rows) >= 1:
        for cell in table.rows[0].cells:
            tc_pr = cell._tc.get_or_add_tcPr()
            old_b = tc_pr.find(qn("w:tcBorders"))
            if old_b is not None:
                tc_pr.remove(old_b)
            tc_pr.append(
                parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>'
                    '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
                    "</w:tcBorders>"
                )
            )


def _apply_paragraph_layout_xml(p_el, block: Dict[str, Any], *, is_body_default: bool = False) -> None:
    ppr = p_el.get_or_add_pPr()
    align = str(block.get("align", "")).strip().lower()
    if align in ("left", "center", "right", "both", "justify"):
        jc_val = "both" if align == "justify" else align
        jc = ppr.find(qn("w:jc"))
        if jc is None:
            jc = OxmlElement("w:jc")
            ppr.append(jc)
        jc.set(qn("w:val"), jc_val)

    first_line_chars = block.get("first_line_chars", 200 if is_body_default else None)
    if first_line_chars is not None:
        ind = ppr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            ppr.append(ind)
        if int(first_line_chars) > 0:
            ind.set(qn("w:firstLineChars"), str(int(first_line_chars)))
        else:
            ind.attrib.pop(qn("w:firstLineChars"), None)
            ind.set(qn("w:firstLine"), "0")

    line_pt = block.get("line_spacing_pt")
    space_before_pt = block.get("space_before_pt")
    space_after_pt = block.get("space_after_pt")
    if any(v is not None for v in (line_pt, space_before_pt, space_after_pt)):
        sp = ppr.find(qn("w:spacing"))
        if sp is None:
            sp = OxmlElement("w:spacing")
            ppr.append(sp)
        if line_pt is not None:
            sp.set(qn("w:line"), str(int(round(float(line_pt) * 20))))
            sp.set(qn("w:lineRule"), "exact")
        if space_before_pt is not None:
            sp.set(qn("w:before"), str(int(round(float(space_before_pt) * 20))))
        if space_after_pt is not None:
            sp.set(qn("w:after"), str(int(round(float(space_after_pt) * 20))))


def build_document_from_spec(spec: Dict[str, Any]) -> Tuple[Document, Dict[str, Any]]:
    """Build a clean, dual-font CJK/Latin .docx document from scratch using a declarative JSON spec."""
    doc = Document()
    section = doc.sections[0]
    page_cfg = spec.get("page") or {}
    section.page_width = Cm(float(page_cfg.get("width_cm", 21.0)))
    section.page_height = Cm(float(page_cfg.get("height_cm", 29.7)))
    margins = spec.get("margins") or page_cfg.get("margins_cm") or {}
    section.top_margin = Cm(float(margins.get("top_cm", margins.get("top", 2.54))))
    section.bottom_margin = Cm(float(margins.get("bottom_cm", margins.get("bottom", 2.54))))
    section.left_margin = Cm(float(margins.get("left_cm", margins.get("left", 3.18))))
    section.right_margin = Cm(float(margins.get("right_cm", margins.get("right", 3.18))))

    defaults = spec.get("defaults") or {}
    default_cn = defaults.get("cn_font", "宋体")
    default_en = defaults.get("en_font", "Times New Roman")
    default_sz = float(defaults.get("size_pt", 12.0))
    default_indent = int(defaults.get("first_line_chars", 200))

    # Set Normal style baseline with dual CJK/Latin slots
    normal_style = doc.styles["Normal"]
    normal_rpr = normal_style.element.get_or_add_rPr()
    apply_dual_cjk_font_to_rpr(
        normal_rpr,
        cn_font=default_cn,
        en_font=default_en,
        size_pt=default_sz,
    )

    header_text = spec.get("header")
    if header_text:
        hp = section.header.paragraphs[0]
        hp.text = ""
        hr = hp.add_run(str(header_text))
        apply_dual_cjk_font_to_rpr(hr._r.get_or_add_rPr(), cn_font=default_cn, en_font=default_en, size_pt=9.0)
        _apply_paragraph_layout_xml(hp._p, {"align": "center", "first_line_chars": 0})

    footer_text = spec.get("footer")
    if footer_text:
        fp = section.footer.paragraphs[0]
        fp.text = ""
        fr = fp.add_run(str(footer_text))
        apply_dual_cjk_font_to_rpr(fr._r.get_or_add_rPr(), cn_font=default_cn, en_font=default_en, size_pt=9.0)
        _apply_paragraph_layout_xml(fp._p, {"align": "center", "first_line_chars": 0})

    blocks = spec.get("blocks") or []
    counts = {"headings": 0, "paragraphs": 0, "tables": 0, "page_breaks": 0}
    heading_sizes = {0: 22.0, 1: 16.0, 2: 14.0, 3: 12.0, 4: 12.0}

    if spec.get("title"):
        title_block = {
            "type": "heading",
            "level": 0,
            "text": str(spec["title"]),
            "align": "center",
            "cn_font": spec.get("title_cn_font", "黑体"),
            "size_pt": float(spec.get("title_size_pt", 18.0)),
            "bold": True,
            "first_line_chars": 0,
            "space_after_pt": 12.0,
        }
        blocks = [title_block] + list(blocks)

    for blk in blocks:
        btype = str(blk.get("type", "paragraph")).strip().lower()
        if btype in ("page_break", "page-break", "break"):
            doc.add_page_break()
            counts["page_breaks"] += 1
            continue

        if btype == "heading":
            lvl = max(0, min(int(blk.get("level", 1)), 4))
            p = doc.add_heading(level=lvl)
            p.text = ""
            txt = str(blk.get("text", ""))
            r = p.add_run(txt)
            apply_dual_cjk_font_to_rpr(
                r._r.get_or_add_rPr(),
                cn_font=blk.get("cn_font", "黑体"),
                en_font=blk.get("en_font", default_en),
                size_pt=float(blk.get("size_pt", heading_sizes.get(lvl, 14.0))),
                bold=bool(blk.get("bold", True)),
                color_hex=blk.get("color", "000000"),
            )
            h_cfg = dict(blk)
            h_cfg.setdefault("first_line_chars", 0)
            if lvl == 0:
                h_cfg.setdefault("align", "center")
            _apply_paragraph_layout_xml(p._p, h_cfg, is_body_default=False)
            counts["headings"] += 1
            continue

        if btype == "table":
            headers = blk.get("headers") or []
            rows_data = blk.get("rows") or []
            all_rows = ([headers] if headers else []) + list(rows_data)
            if not all_rows:
                continue
            n_cols = max(len(r) for r in all_rows)
            tbl = doc.add_table(rows=len(all_rows), cols=n_cols)
            border_style = str(blk.get("border", "three-line")).lower()
            _set_table_borders_xml(tbl, border_style)
            tbl_cn = blk.get("cn_font", default_cn)
            tbl_en = blk.get("en_font", default_en)
            tbl_sz = float(blk.get("size_pt", 10.5))
            col_widths_cm = blk.get("col_widths_cm")
            for r_i, row_vals in enumerate(all_rows):
                is_hdr = bool(headers) and r_i == 0
                for c_i in range(n_cols):
                    val = str(row_vals[c_i]) if c_i < len(row_vals) else ""
                    cell = tbl.cell(r_i, c_i)
                    if col_widths_cm and c_i < len(col_widths_cm):
                        cell.width = Cm(float(col_widths_cm[c_i]))
                    cp = cell.paragraphs[0]
                    cp.text = ""
                    cr = cp.add_run(val)
                    apply_dual_cjk_font_to_rpr(
                        cr._r.get_or_add_rPr(),
                        cn_font="黑体" if is_hdr else tbl_cn,
                        en_font=tbl_en,
                        size_pt=tbl_sz,
                        bold=True if is_hdr else bool(blk.get("bold", False)),
                    )
                    _apply_paragraph_layout_xml(
                        cp._p,
                        {"align": blk.get("cell_align", "center" if is_hdr else "left"), "first_line_chars": 0},
                        is_body_default=False,
                    )
            counts["tables"] += 1
            continue

        # Default: paragraph (split multi-line text into proper <w:p> nodes)
        raw_text = str(blk.get("text", ""))
        lines = raw_text.split("\n") if raw_text else [""]
        for line in lines:
            p = doc.add_paragraph()
            if line:
                r = p.add_run(line)
                apply_dual_cjk_font_to_rpr(
                    r._r.get_or_add_rPr(),
                    cn_font=blk.get("cn_font", default_cn),
                    en_font=blk.get("en_font", default_en),
                    size_pt=float(blk.get("size_pt", default_sz)),
                    bold=blk.get("bold"),
                    italic=blk.get("italic"),
                    underline=blk.get("underline"),
                    color_hex=blk.get("color"),
                )
            p_cfg = dict(blk)
            p_cfg.setdefault("first_line_chars", default_indent)
            _apply_paragraph_layout_xml(p._p, p_cfg, is_body_default=True)
            counts["paragraphs"] += 1

    return doc, counts


# ---------------------------------------------------------------------------
# 6. CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Template-First, Format-Preserving OOXML (.docx) Engine"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # inspect
    p_ins = sub.add_parser("inspect", help="Inspect .docx template structure, fonts, merged cells, and blanks")
    p_ins.add_argument("input", help="Input .docx path")
    p_ins.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_ins.add_argument("--max-len", type=int, default=120)

    # merge-runs
    p_mr = sub.add_parser("merge-runs", help="Coalesce fragmented runs with identical <w:rPr>")
    p_mr.add_argument("input", help="Input .docx path")
    p_mr.add_argument("-o", "--output", help="Output .docx path (default: in-place if --in-place else <name>_merged.docx)")
    p_mr.add_argument("--in-place", action="store_true")

    # replace
    p_rep = sub.add_parser("replace", help="Cross-run format-preserving text replacement")
    p_rep.add_argument("input", help="Input .docx path")
    p_rep.add_argument("--old", required=True, help="Text to find")
    p_rep.add_argument("--new", required=True, help="Replacement text")
    p_rep.add_argument("-o", "--output", help="Output .docx path")
    p_rep.add_argument("--in-place", action="store_true")

    # set-para
    p_sp = sub.add_parser("set-para", help="Set paragraph text by index while preserving <w:pPr> and <w:rPr>")
    p_sp.add_argument("input", help="Input .docx path")
    p_sp.add_argument("--index", type=int, required=True, help="Paragraph index (0-based)")
    p_sp.add_argument("--text", required=True, help="New text (use \\n for multiple paragraphs)")
    p_sp.add_argument("-o", "--output", help="Output .docx path")
    p_sp.add_argument("--in-place", action="store_true")

    # set-cell
    p_sc = sub.add_parser("set-cell", help="Set table cell text while preserving <w:tcPr>, <w:pPr>, and <w:rPr>")
    p_sc.add_argument("input", help="Input .docx path")
    p_sc.add_argument("--table", type=int, required=True, help="Table index (0-based)")
    p_sc.add_argument("--row", type=int, required=True, help="Row index (0-based)")
    p_sc.add_argument("--col", type=int, required=True, help="Col index (0-based)")
    p_sc.add_argument("--text", required=True, help="New cell text")
    p_sc.add_argument("-o", "--output", help="Output .docx path")
    p_sc.add_argument("--in-place", action="store_true")

    # fill
    p_fill = sub.add_parser("fill", help="Batch fill template from JSON spec")
    p_fill.add_argument("input", help="Input .docx template path")
    p_fill.add_argument("--spec", required=True, help="Path to JSON spec file or inline JSON string")
    p_fill.add_argument("-o", "--output", help="Output .docx path")
    p_fill.add_argument("--in-place", action="store_true")

    # build
    p_bld = sub.add_parser("build", help="Build a new .docx from scratch via JSON spec")
    p_bld.add_argument("--spec", required=True, help="Path to JSON spec file or inline JSON string")
    p_bld.add_argument("-o", "--output", required=True, help="Output .docx path")

    # audit
    p_aud = sub.add_parser("audit", help="Audit edited .docx against original template .docx")
    p_aud.add_argument("--template", required=True, help="Original template .docx")
    p_aud.add_argument("--output", required=True, help="Edited output .docx")

    args = parser.parse_args()

    if args.cmd == "build":
        if os.path.exists(args.spec):
            spec_data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        else:
            spec_data = json.loads(args.spec)
        built_doc, counts = build_document_from_spec(spec_data)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        built_doc.save(args.output)
        print(json.dumps({"status": "ok", "output": args.output, "counts": counts}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "audit":
        tpl_doc = Document(args.template)
        out_doc = Document(args.output)
        res = audit_document_against_template(tpl_doc, out_doc)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["passed"] else 2

    if not os.path.exists(args.input):
        print(json.dumps({"error": f"File not found: {args.input}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    doc = Document(args.input)

    if args.cmd == "inspect":
        bp = inspect_document_blueprint(doc, path=args.input, max_len=args.max_len)
        if args.format == "json":
            print(json.dumps(bp, ensure_ascii=False, indent=2))
        else:
            print(format_blueprint_markdown(bp))
        return 0

    # Resolve output path for write commands
    out_path = args.input if getattr(args, "in_place", False) else getattr(args, "output", None)
    if not out_path:
        stem, ext = os.path.splitext(args.input)
        out_path = f"{stem}_edited{ext or '.docx'}"

    if args.cmd == "merge-runs":
        merged = merge_runs_in_document(doc)
        doc.save(out_path)
        print(json.dumps({"status": "ok", "merged_runs": merged, "output": out_path}, ensure_ascii=False))
        return 0

    if args.cmd == "replace":
        res = replace_text_in_document_xml(doc, args.old, args.new)
        doc.save(out_path)
        res["output"] = out_path
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "set-para":
        res = set_paragraph_text_preserving_format(doc, args.index, args.text)
        doc.save(out_path)
        res["output"] = out_path
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "set-cell":
        res = set_cell_text_preserving_format(doc, args.table, args.row, args.col, args.text)
        doc.save(out_path)
        res["output"] = out_path
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "fill":
        if os.path.exists(args.spec):
            spec_data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        else:
            spec_data = json.loads(args.spec)
        tpl_copy = Document(args.input)
        res = fill_template_from_spec(doc, spec_data)
        doc.save(out_path)
        audit_res = audit_document_against_template(tpl_copy, Document(out_path))
        res["output"] = out_path
        res["audit"] = audit_res
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if not res["errors"] and audit_res["passed"] else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
