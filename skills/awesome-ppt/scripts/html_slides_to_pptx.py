#!/usr/bin/env python3
"""Deterministic HTML / JSON slide geometry to native editable PPTX converter.

Converts either:
1. Structured slide geometry JSON (`slides.json` with pixel bounding boxes), or
2. HTML slide file(s) (`.html` or directory of `.html` files) measured headlessly
   via Playwright (`getBoundingClientRect` + `getComputedStyle`, zero focus steal)

into native editable `python-pptx` shapes, cards, images, and textboxes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

EMU_PER_INCH = 914400
ASPECT_INCHES: dict[str, tuple[float, float]] = {
    "16:9": (13.333333, 7.5),
    "4:3": (10.0, 7.5),
    "1:1": (7.5, 7.5),
}
DEFAULT_VIEWPORTS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "4:3": (1440, 1080),
    "1:1": (1080, 1080),
}
RGB_FUNC_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([0-9.]+))?\s*\)")
HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

MEASURE_DOM_JS = """
() => {
  const roots = Array.from(document.querySelectorAll('[data-ppt-slide], .ppt-slide, .slide, section.slide'));
  const slideNodes = roots.length ? roots : [document.body];
  const isTransparent = (c) => !c || c === 'transparent' || c === 'rgba(0, 0, 0, 0)';
  const hasDirectText = (el) => Array.from(el.childNodes).some(
    (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0
  );

  return slideNodes.map((slideEl, idx) => {
    const sRect = slideEl.getBoundingClientRect();
    const sStyle = window.getComputedStyle(slideEl);
    const sw = Math.max(1, sRect.width || window.innerWidth);
    const sh = Math.max(1, sRect.height || window.innerHeight);
    const elements = [];

    const all = Array.from(slideEl.querySelectorAll('*'));
    for (const el of all) {
      const tag = el.tagName.toLowerCase();
      if (['script', 'style', 'noscript', 'meta', 'link', 'svg', 'path'].includes(tag)) continue;
      const st = window.getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity || '1') === 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;

      const x = r.left - sRect.left;
      const y = r.top - sRect.top;
      const bg = st.backgroundColor;
      const bw = parseFloat(st.borderTopWidth || '0') || 0;
      const bc = st.borderTopColor;
      const br = parseFloat(st.borderTopLeftRadius || '0') || 0;

      if (tag === 'img' && el.getAttribute('src')) {
        elements.push({
          kind: 'image',
          src: el.getAttribute('src'),
          x, y, width: r.width, height: r.height
        });
        continue;
      }

      const explicitShape = el.hasAttribute('data-ppt-shape') || el.hasAttribute('data-ppt-card');
      if (explicitShape || !isTransparent(bg) || (bw >= 1 && !isTransparent(bc))) {
        elements.push({
          kind: 'shape',
          x, y, width: r.width, height: r.height,
          fill_color: isTransparent(bg) ? '' : bg,
          border_color: bw >= 1 && !isTransparent(bc) ? bc : '',
          border_width_px: bw,
          border_radius_px: br
        });
      }

      const leafTextTag = ['h1','h2','h3','h4','h5','h6','p','li','td','th','blockquote','figcaption'].includes(tag);
      const explicitText = el.hasAttribute('data-ppt-text');
      const childBlocks = el.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,div,section,table');
      if (explicitText || (leafTextTag && childBlocks.length === 0) || hasDirectText(el)) {
        const text = (el.innerText || el.textContent || '').trim();
        if (text) {
          const fwNum = parseInt(st.fontWeight || '400', 10);
          elements.push({
            kind: 'text',
            x, y, width: r.width, height: r.height,
            text,
            font_size_px: parseFloat(st.fontSize || '20') || 20,
            font_family: (st.fontFamily || '').split(',')[0].replace(/['"]/g, '').trim(),
            bold: fwNum >= 600 || st.fontWeight === 'bold',
            italic: st.fontStyle === 'italic',
            color: st.color || '#111827',
            align: st.textAlign || 'left',
            bullet: tag === 'li'
          });
        }
      }
    }

    return {
      slide_number: idx + 1,
      viewport_width: sw,
      viewport_height: sh,
      background_color: isTransparent(sStyle.backgroundColor) ? '#FFFFFF' : sStyle.backgroundColor,
      elements
    };
  });
}
"""


def parse_color(raw: str | None) -> RGBColor | None:
    if not raw:
        return None
    val = raw.strip()
    if not val or val.lower() in {"transparent", "none"}:
        return None
    m_hex = HEX_COLOR_RE.match(val)
    if m_hex:
        h = m_hex.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        elif len(h) == 8:
            if int(h[6:8], 16) == 0:
                return None
            h = h[:6]
        return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m_rgb = RGB_FUNC_RE.match(val)
    if m_rgb:
        alpha = float(m_rgb.group(4)) if m_rgb.group(4) is not None else 1.0
        if alpha <= 0.01:
            return None
        return RGBColor(
            min(255, int(m_rgb.group(1))),
            min(255, int(m_rgb.group(2))),
            min(255, int(m_rgb.group(3))),
        )
    return None


def map_align(raw: str | None) -> PP_ALIGN:
    val = (raw or "left").strip().lower()
    if val in {"center", "middle"}:
        return PP_ALIGN.CENTER
    if val in {"right", "end"}:
        return PP_ALIGN.RIGHT
    if val == "justify":
        return PP_ALIGN.JUSTIFY
    return PP_ALIGN.LEFT


def map_valign(raw: str | None) -> MSO_ANCHOR:
    val = (raw or "top").strip().lower()
    if val in {"middle", "center"}:
        return MSO_ANCHOR.MIDDLE
    if val == "bottom":
        return MSO_ANCHOR.BOTTOM
    return MSO_ANCHOR.TOP


def measure_html_files(html_paths: list[Path], viewport: tuple[int, int]) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            f"Playwright is required to measure HTML slides ({exc}). "
            "Pass structured JSON geometry or run with python3"
        ) from exc

    slides: list[dict[str, Any]] = []
    vw, vh = viewport
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception:
            browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": vw, "height": vh}, device_scale_factor=1)
            for html_file in html_paths:
                page.goto(html_file.resolve().as_uri(), wait_until="load", timeout=30000)
                page.wait_for_timeout(120)
                measured = page.evaluate(MEASURE_DOM_JS)
                for item in measured:
                    item["_base_dir"] = str(html_file.resolve().parent)
                    slides.append(item)
        finally:
            browser.close()
    return slides


def load_spec(input_path: Path, aspect_ratio: str, viewport: tuple[int, int]) -> tuple[str, list[dict[str, Any]]]:
    if input_path.is_dir():
        html_files = sorted(input_path.glob("*.html"))
        if not html_files:
            raise SystemExit(f"No .html files found in directory: {input_path}")
        return aspect_ratio, measure_html_files(html_files, viewport)

    suffix = input_path.suffix.lower()
    if suffix == ".json":
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            slides = raw
            ar = aspect_ratio
            vp = viewport
        elif isinstance(raw, dict):
            ar = str(raw.get("aspect_ratio") or aspect_ratio)
            vp_obj = raw.get("viewport") or {}
            vp = (
                int(vp_obj.get("width") or viewport[0]),
                int(vp_obj.get("height") or viewport[1]),
            )
            slides = list(raw.get("slides") or [])
        else:
            raise SystemExit("JSON slide spec must be an object or array.")
        for s in slides:
            s.setdefault("viewport_width", vp[0])
            s.setdefault("viewport_height", vp[1])
            s.setdefault("_base_dir", str(input_path.resolve().parent))
        return ar, slides

    if suffix in {".html", ".htm"}:
        return aspect_ratio, measure_html_files([input_path], viewport)

    raise SystemExit(f"Unsupported input {input_path}: expected .html, directory of .html, or .json")


def render_pptx(
    slides_data: list[dict[str, Any]],
    out_path: Path,
    *,
    aspect_ratio: str = "16:9",
    default_font: str = "PingFang SC",
) -> dict[str, Any]:
    if aspect_ratio not in ASPECT_INCHES:
        raise SystemExit(f"Unsupported aspect ratio '{aspect_ratio}'. Choose from {sorted(ASPECT_INCHES)}.")
    if not slides_data:
        raise SystemExit("No slides found to convert.")

    win_in, hin_in = ASPECT_INCHES[aspect_ratio]
    slide_w_emu = int(round(win_in * EMU_PER_INCH))
    slide_h_emu = int(round(hin_in * EMU_PER_INCH))

    prs = Presentation()
    prs.slide_width = Emu(slide_w_emu)
    prs.slide_height = Emu(slide_h_emu)
    blank_layout = prs.slide_layouts[6]

    total_shapes = 0
    total_textboxes = 0

    for slide_spec in slides_data:
        slide = prs.slides.add_slide(blank_layout)
        vw = float(slide_spec.get("viewport_width") or DEFAULT_VIEWPORTS[aspect_ratio][0])
        vh = float(slide_spec.get("viewport_height") or DEFAULT_VIEWPORTS[aspect_ratio][1])
        base_dir = Path(str(slide_spec.get("_base_dir") or ".")).resolve()

        def px_x(val: float) -> Emu:
            return Emu(max(0, int(round((float(val) / vw) * slide_w_emu))))

        def px_y(val: float) -> Emu:
            return Emu(max(0, int(round((float(val) / vh) * slide_h_emu))))

        def px_pt(val: float) -> Pt:
            # 1 inch = 72 pt; slide_h_in = hin_in
            inches = (float(val) / vh) * hin_in
            return Pt(max(6.0, round(inches * 72.0, 1)))

        bg_rgb = parse_color(slide_spec.get("background_color"))
        if bg_rgb is not None:
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = bg_rgb

        bg_img = slide_spec.get("background_image")
        if isinstance(bg_img, str) and bg_img.strip():
            img_p = (base_dir / bg_img).resolve() if not Path(bg_img).is_absolute() else Path(bg_img)
            if img_p.is_file():
                slide.shapes.add_picture(str(img_p), Emu(0), Emu(0), width=Emu(slide_w_emu), height=Emu(slide_h_emu))
                total_shapes += 1

        for el in slide_spec.get("elements") or []:
            kind = str(el.get("kind") or "text").lower()
            left = px_x(el.get("x", 0))
            top = px_y(el.get("y", 0))
            width = px_x(max(4.0, float(el.get("width", 100))))
            height = px_y(max(4.0, float(el.get("height", 32))))

            if kind == "image":
                src = str(el.get("src") or "").strip()
                if not src or src.startswith(("http://", "https://", "data:")):
                    continue
                clean_src = src.removeprefix("file://")
                img_path = Path(clean_src) if Path(clean_src).is_absolute() else (base_dir / clean_src).resolve()
                if img_path.is_file():
                    slide.shapes.add_picture(str(img_path), left, top, width=width, height=height)
                    total_shapes += 1
                continue

            if kind in {"shape", "card", "rect"}:
                radius_px = float(el.get("border_radius_px") or 0.0)
                shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius_px >= 4.0 else MSO_SHAPE.RECTANGLE
                shp = slide.shapes.add_shape(shape_type, left, top, width, height)
                if shape_type == MSO_SHAPE.ROUNDED_RECTANGLE and min(float(el.get("width", 1)), float(el.get("height", 1))) > 0:
                    adj = min(0.5, radius_px / max(1.0, min(float(el.get("width", 1)), float(el.get("height", 1)))))
                    try:
                        shp.adjustments[0] = adj
                    except Exception:
                        pass
                fill_rgb = parse_color(el.get("fill_color"))
                if fill_rgb is not None:
                    shp.fill.solid()
                    shp.fill.fore_color.rgb = fill_rgb
                else:
                    shp.fill.background()

                border_rgb = parse_color(el.get("border_color"))
                bw_px = float(el.get("border_width_px") or 0.0)
                if border_rgb is not None and bw_px > 0:
                    shp.line.color.rgb = border_rgb
                    shp.line.width = px_pt(max(1.0, bw_px))
                else:
                    shp.line.fill.background()
                total_shapes += 1
                if not el.get("text"):
                    continue

            text_val = str(el.get("text") or "").strip()
            if not text_val:
                continue

            # Add slight horizontal headroom (4%) to prevent PowerPoint word-wrap clipping
            padded_w = Emu(min(slide_w_emu - int(left), int(int(width) * 1.04) + int(0.05 * EMU_PER_INCH)))
            tb = slide.shapes.add_textbox(left, top, padded_w, height)
            tb.fill.background()
            tb.line.fill.background()
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = Emu(0)
            tf.margin_right = Emu(0)
            tf.margin_top = Emu(0)
            tf.margin_bottom = Emu(0)
            tf.vertical_anchor = map_valign(el.get("valign"))

            lines = text_val.splitlines() or [text_val]
            font_pt = Pt(float(el["font_size_pt"])) if "font_size_pt" in el else px_pt(float(el.get("font_size_px") or 20.0))
            font_name = str(el.get("font_family") or default_font).strip() or default_font
            text_rgb = parse_color(el.get("color")) or RGBColor(0x11, 0x18, 0x27)
            align = map_align(el.get("align"))
            is_bold = bool(el.get("bold", False))
            is_italic = bool(el.get("italic", False))
            prefix = "• " if el.get("bullet") and not lines[0].lstrip().startswith(("•", "-", "▪")) else ""

            for idx, ln in enumerate(lines):
                p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                p.alignment = align
                run = p.add_run()
                run.text = (prefix + ln) if idx == 0 else ln
                run.font.size = font_pt
                run.font.name = font_name
                run.font.bold = is_bold
                run.font.italic = is_italic
                run.font.color.rgb = text_rgb
            total_textboxes += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return {
        "ok": True,
        "output": str(out_path.resolve()),
        "aspect_ratio": aspect_ratio,
        "slides": len(slides_data),
        "shapes": total_shapes,
        "editable_textboxes": total_textboxes,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert HTML slide deck(s) or structured slide geometry JSON into native editable python-pptx PPTX."
    )
    p.add_argument("input", type=Path, help="Input .html file, directory of .html files, or structured .json geometry spec")
    p.add_argument("--out", "-o", type=Path, required=True, help="Output .pptx path")
    p.add_argument("--aspect-ratio", choices=sorted(ASPECT_INCHES), default="16:9", help="Slide aspect ratio (default: 16:9)")
    p.add_argument("--viewport-width", type=int, default=0, help="Override measurement viewport width in px (default: 1920 for 16:9)")
    p.add_argument("--viewport-height", type=int, default=0, help="Override measurement viewport height in px (default: 1080 for 16:9)")
    p.add_argument("--default-font", default="PingFang SC", help="Fallback font family for editable text runs (default: PingFang SC)")
    p.add_argument("--export-geometry", type=Path, help="Optional path to dump measured slide geometry JSON for inspection")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input path not found: {args.input}", file=sys.stderr)
        return 2
    def_vw, def_vh = DEFAULT_VIEWPORTS[args.aspect_ratio]
    viewport = (args.viewport_width or def_vw, args.viewport_height or def_vh)
    aspect_ratio, slides = load_spec(args.input, args.aspect_ratio, viewport)
    if args.export_geometry:
        args.export_geometry.parent.mkdir(parents=True, exist_ok=True)
        clean_slides = [{k: v for k, v in s.items() if not k.startswith("_")} for s in slides]
        args.export_geometry.write_text(
            json.dumps({"aspect_ratio": aspect_ratio, "slides": clean_slides}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    summary = render_pptx(slides, args.out, aspect_ratio=aspect_ratio, default_font=args.default_font)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
