#!/usr/bin/env python3
"""Render a .pptx or .pdf template to per-page PNGs.

Backends:
  PPTX -> PDF: Microsoft PowerPoint (macOS AppleScript) or direct .pdf input
  PDF -> PNG:  pymupdf > pdf2image (needs poppler)

Default output: <cwd>/template_renders/<pptx_stem>/page-NN.png
Intermediate PDF goes to <out_dir>/_source.pdf and is left in place
for inspection (gitignored under template_renders/).
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Optional


DEFAULT_RENDERS_DIR_NAME = "template_renders"
POWERPOINT_APP = Path("/Applications/Microsoft PowerPoint.app")


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", name).strip("_")
    return cleaned[:80] or "template"


def default_out_dir(pptx_path: Path) -> Path:
    return Path.cwd() / DEFAULT_RENDERS_DIR_NAME / _safe_stem(pptx_path.stem)


def render_pptx_to_pngs(
    pptx_path: str | Path,
    out_dir: Optional[Path] = None,
    dpi: int = 144,
    force: bool = False,
) -> Path:
    """Render every slide of pptx/pdf to PNGs. Returns the directory containing PNGs."""
    pptx_path = Path(pptx_path).resolve()
    if not pptx_path.exists():
        raise FileNotFoundError(f"Template not found: {pptx_path}")

    if out_dir is None:
        out_dir = default_out_dir(pptx_path)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not force:
        existing = sorted(out_dir.glob("page-*.png"))
        if existing:
            print(f"📦 已渲染 {len(existing)} 页 -> {out_dir}（用 --force 强制重渲）")
            return out_dir

    if pptx_path.suffix.lower() == ".pdf":
        pdf_path = pptx_path
    else:
        pdf_path = out_dir / "_source.pdf"
        print(f"🖨️  PPTX -> PDF：{pptx_path.name}")
        _convert_pptx_to_pdf(pptx_path, pdf_path)

    print(f"🖼️  PDF -> PNG（dpi={dpi}）...")
    n = _rasterize_pdf(pdf_path, out_dir, dpi=dpi)
    print(f"[OK] 渲染 {n} 页 -> {out_dir}")
    return out_dir


def _convert_pptx_to_pdf(pptx_path: Path, out_pdf: Path) -> None:
    if POWERPOINT_APP.exists():
        script = (
            "on run argv\n"
            "  set inFile to POSIX file (item 1 of argv)\n"
            "  set outPath to (item 2 of argv)\n"
            '  tell application "Microsoft PowerPoint"\n'
            "    open inFile\n"
            "    save active presentation in (POSIX file outPath) as save as PDF\n"
            "    close active presentation saving no\n"
            "  end tell\n"
            "end run\n"
        )
        res = subprocess.run(
            ["osascript", "-", str(pptx_path), str(out_pdf)],
            input=script,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if res.returncode == 0 and out_pdf.exists():
            return
        detail = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(
            f"Microsoft PowerPoint 导出 PDF 失败：{detail or 'unknown error'}\n"
            "可先在 PowerPoint / Keynote 中手动导出 PDF 再传入 render_template.py <template.pdf>，"
            "或直接导出每页 PNG（命名 page-01.png 起按字典序对应页码）。"
        )

    raise RuntimeError(
        "未检测到 Microsoft PowerPoint.app。\n"
        "请先从 PowerPoint / Keynote 导出 PDF 并直接传入 render_template.py <template.pdf>，\n"
        "或直接导出每页 PNG（命名 page-01.png 起按字典序对应页码）。"
    )


def _rasterize_pdf(pdf_path: Path, out_dir: Path, dpi: int = 144) -> int:
    pymupdf = None
    try:
        import pymupdf as _m  # type: ignore
        pymupdf = _m
    except ImportError:
        try:
            import fitz as _m  # type: ignore
            pymupdf = _m
        except ImportError:
            pass

    if pymupdf is not None:
        zoom = dpi / 72.0
        mat = pymupdf.Matrix(zoom, zoom)
        doc = pymupdf.open(str(pdf_path))
        n = len(doc)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(out_dir / f"page-{i+1:02d}.png"))
        doc.close()
        return n

    try:
        from pdf2image import convert_from_path  # type: ignore
    except ImportError:
        raise RuntimeError(
            "PDF -> PNG 缺少受管运行时依赖 pymupdf/pdf2image；"
            "请检查 python3 受管环境依赖"
        )
    images = convert_from_path(str(pdf_path), dpi=dpi)
    for i, img in enumerate(images):
        img.save(str(out_dir / f"page-{i+1:02d}.png"), "PNG")
    return len(images)


def _cli() -> None:
    p = argparse.ArgumentParser(description="Render .pptx or .pdf -> per-page PNGs")
    p.add_argument("pptx", help="path to .pptx or .pdf file")
    p.add_argument("-o", "--out", help="output directory (default: <cwd>/template_renders/<stem>/)")
    p.add_argument("--dpi", type=int, default=144, help="PNG dpi (default: 144)")
    p.add_argument("--force", action="store_true", help="re-render even if PNGs exist")
    args = p.parse_args()
    out_dir = render_pptx_to_pngs(
        args.pptx, Path(args.out) if args.out else None,
        dpi=args.dpi, force=args.force,
    )
    print()
    print(f"模板渲染目录：{out_dir}")
    print(f"喂给 generate_ppt.py：")
    print(f"  --template-pptx {args.pptx} \\")
    print(f"  --template-images {out_dir}")


if __name__ == "__main__":
    _cli()
