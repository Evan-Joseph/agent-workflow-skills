#!/usr/bin/env python3
"""300-DPI exam sheet & handwritten answer cropper for safe multimodal review.

Renders a PDF page at 300 DPI (via PyMuPDF `fitz`) or loads an existing image
(via Pillow `PIL`), crops single questions by `--bbox x0,y0,x1,y1` (normalized
`0..1` or pixel coordinates) or `--grid rows,cols`, and adaptively compresses
each output slice into a `<150KB` standard Baseline JPEG (`\\xff\\xd8\\xff` magic
bytes, `progressive=False`) ready for `read_file` multimodal blind transcription.

Strictly avoid `paddleocr` / `tesseract` on handwritten math or 408 exam sheets.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

JPEG_MAGIC = b"\xff\xd8\xff"
HARD_MAX_BYTES = 150 * 1024  # Strict < 150 KB ceiling for conversation DB safety
DEFAULT_TARGET_KB = 145      # Default safety margin (< 145 KB < 150 KB)
PDF_EXTS = {".pdf"}


def render_input_page(input_path: Path, page_num: int = 1, dpi: int = 300) -> Image.Image:
    """Load an image or rasterize 1-based `page_num` of a PDF at `dpi` into RGB."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if dpi < 72 or dpi > 600:
        raise ValueError(f"--dpi must be in [72, 600], got {dpi}")

    if input_path.suffix.lower() in PDF_EXTS:
        if page_num < 1:
            raise ValueError(f"--page is 1-based and must be >= 1, got {page_num}")
        with fitz.open(input_path) as doc:
            if page_num > len(doc):
                raise ValueError(f"Requested --page {page_num}, but PDF has {len(doc)} page(s)")
            page = doc[page_num - 1]
            scale = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    with Image.open(input_path) as raw:
        raw.load()
        return _to_rgb_white_bg(raw)


def _to_rgb_white_bg(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img.copy()
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[3])
        return canvas
    return img.convert("RGB")


def parse_bbox(spec: str, width: int, height: int, coords_mode: str = "auto") -> tuple[int, int, int, int]:
    """Parse `x0,y0,x1,y1` as normalized [0..1] or pixel coordinates."""
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if len(parts) != 4:
        raise ValueError(f"Invalid --bbox '{spec}': expected 'x0,y0,x1,y1'")
    vals = [float(v) for v in parts]
    x0, y0, x1, y1 = vals

    if coords_mode == "auto":
        is_norm = all(0.0 <= v <= 1.0 for v in vals) and (x1 <= 1.0 and y1 <= 1.0)
    elif coords_mode == "norm":
        is_norm = True
    elif coords_mode == "px":
        is_norm = False
    else:
        raise ValueError(f"Unsupported coords_mode: {coords_mode}")

    if is_norm:
        px0 = int(round(x0 * width))
        py0 = int(round(y0 * height))
        px1 = int(round(x1 * width))
        py1 = int(round(y1 * height))
    else:
        px0 = int(round(x0))
        py0 = int(round(y0))
        px1 = int(round(x1))
        py1 = int(round(y1))

    px0 = max(0, min(px0, width - 1))
    py0 = max(0, min(py0, height - 1))
    px1 = max(px0 + 1, min(px1, width))
    py1 = max(py0 + 1, min(py1, height))
    if px1 - px0 < 8 or py1 - py0 < 8:
        raise ValueError(f"Cropped region too small ({px1 - px0}x{py1 - py0}) from --bbox '{spec}'")
    return (px0, py0, px1, py1)


def build_grid_boxes(
    width: int,
    height: int,
    rows: int,
    cols: int,
    overlap: float = 0.02,
) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    """Split `(width, height)` into `(row_idx_1based, col_idx_1based, (x0,y0,x1,y1))`."""
    if rows < 1 or cols < 1 or rows > 20 or cols > 20:
        raise ValueError(f"Invalid --grid '{rows},{cols}': rows and cols must be in 1..20")
    if not (0.0 <= overlap <= 0.25):
        raise ValueError(f"--overlap must be in [0.0, 0.25], got {overlap}")

    cell_w = width / cols
    cell_h = height / rows
    pad_x = int(round(cell_w * overlap))
    pad_y = int(round(cell_h * overlap))

    tiles: list[tuple[int, int, tuple[int, int, int, int]]] = []
    for r in range(rows):
        for c in range(cols):
            x0 = max(0, int(round(c * cell_w)) - pad_x)
            y0 = max(0, int(round(r * cell_h)) - pad_y)
            x1 = min(width, int(round((c + 1) * cell_w)) + pad_x)
            y1 = min(height, int(round((r + 1) * cell_h)) + pad_y)
            tiles.append((r + 1, c + 1, (x0, y0, x1, y1)))
    return tiles


def build_auto_band_boxes(
    img: Image.Image,
    max_bands: int = 6,
    min_band_frac: float = 0.12,
    pad_frac: float = 0.012,
) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Split an exam page into natural horizontal bands along whitespace projection valleys.

    Uses horizontal pixel transition energy + dark-pixel density (immune to faint horizontal
    ruled lines on answer sheets) so multi-line math equations are never sliced mid-line.
    """
    w, h = img.size
    if h < 120 or max_bands <= 1:
        return [(1, (0, 0, w, h))]

    gray = img.convert("L")
    sample_w = min(w, 800)
    sample_img = gray.resize((sample_w, h), Image.Resampling.BILINEAR) if sample_w < w else gray
    raw = sample_img.tobytes()

    # Ignore 4% left/right page borders (scanner edges / binding shadows)
    x_start = max(1, int(sample_w * 0.04))
    x_end = max(x_start + 2, int(sample_w * 0.96))
    span_w = max(1, x_end - x_start)

    row_energy: list[float] = []
    for y in range(h):
        row_off = y * sample_w
        dark = 0
        grad = 0
        prev = raw[row_off + x_start]
        for x in range(x_start + 1, x_end):
            px = raw[row_off + x]
            if px < 222:
                dark += 1
            diff = px - prev
            grad += diff if diff >= 0 else -diff
            prev = px
        # Faint ruled lines have near-zero horizontal `grad`; handwriting/printed text has strong `grad`
        energy = (grad / (span_w * 255.0)) * 0.75 + (dark / float(span_w)) * 0.25
        row_energy.append(energy)

    # Smooth 1D energy profile over ~7 rows
    win = max(3, min(11, h // 350) | 1)
    half = win // 2
    smoothed: list[float] = []
    running = sum(row_energy[:win])
    for y in range(h):
        y0 = max(0, y - half)
        y1 = min(h, y + half + 1)
        if y == 0 or y1 - y0 != win:
            smoothed.append(sum(row_energy[y0:y1]) / float(y1 - y0))
        else:
            running += row_energy[y1 - 1] - row_energy[y0 - 1]
            smoothed.append(running / float(win))

    sorted_e = sorted(smoothed)
    quiet_thresh = max(sorted_e[int(len(sorted_e) * 0.35)] * 1.35, 0.0045)
    min_valley_px = max(6, int(round(h * 0.008)))
    min_band_px = max(64, int(round(h * max(0.06, min(min_band_frac, 0.45)))))
    target_max_band_px = max(min_band_px * 2, int(round(h * 0.40)))

    # Collect interior quiet valleys [vy0, vy1)
    valleys: list[tuple[int, int, float]] = []
    in_v = False
    v_start = 0
    margin_y = int(round(h * 0.07))
    for y in range(margin_y, h - margin_y):
        if smoothed[y] <= quiet_thresh:
            if not in_v:
                in_v = True
                v_start = y
        else:
            if in_v:
                if y - v_start >= min_valley_px:
                    mean_e = sum(smoothed[v_start:y]) / float(y - v_start)
                    valleys.append((v_start, y, mean_e))
                in_v = False
    if in_v and (h - margin_y) - v_start >= min_valley_px:
        mean_e = sum(smoothed[v_start : h - margin_y]) / float((h - margin_y) - v_start)
        valleys.append((v_start, h - margin_y, mean_e))

    def _split_interval(y_top: int, y_bot: int, budget: int) -> list[tuple[int, int]]:
        if budget <= 1 or (y_bot - y_top) <= target_max_band_px:
            if budget <= 1 or (y_bot - y_top) < min_band_px * 2:
                return [(y_top, y_bot)]
        # Pick best valley inside [y_top + min_band_px, y_bot - min_band_px]
        candidates: list[tuple[float, int]] = []
        for vy0, vy1, ve in valleys:
            mid = (vy0 + vy1) // 2
            if y_top + min_band_px <= mid <= y_bot - min_band_px:
                width_score = (vy1 - vy0) / float(h)
                center_bias = 1.0 - 0.35 * abs(((mid - y_top) / float(y_bot - y_top)) - 0.5)
                score = (width_score / (ve + 0.001)) * center_bias
                candidates.append((score, mid))

        if not candidates:
            if (y_bot - y_top) <= target_max_band_px:
                return [(y_top, y_bot)]
            # Fallback: pick minimum smoothed energy row inside central legal zone
            lo = y_top + min_band_px
            hi = y_bot - min_band_px
            if lo >= hi:
                return [(y_top, y_bot)]
            best_y = min(range(lo, hi + 1), key=lambda r: smoothed[r])
            cut_y = best_y
        else:
            # Only split bands <= target_max_band_px when there is a genuinely wide whitespace gap
            candidates.sort(reverse=True)
            best_score, cut_y = candidates[0]
            if (y_bot - y_top) <= target_max_band_px and best_score < 2.2:
                return [(y_top, y_bot)]

        left_budget = max(1, round(budget * (cut_y - y_top) / float(y_bot - y_top)))
        left_budget = min(budget - 1, left_budget)
        right_budget = budget - left_budget
        return _split_interval(y_top, cut_y, left_budget) + _split_interval(cut_y, y_bot, right_budget)

    intervals = _split_interval(0, h, max(1, min(max_bands, 15)))
    pad_px = max(4, int(round(h * pad_frac)))
    bands: list[tuple[int, tuple[int, int, int, int]]] = []
    for idx, (by0, by1) in enumerate(intervals, start=1):
        y0 = 0 if idx == 1 else max(0, by0 - pad_px)
        y1 = h if idx == len(intervals) else min(h, by1 + pad_px)
        bands.append((idx, (0, y0, w, y1)))
    return bands


def verify_baseline_jpeg_bytes(data: bytes, max_bytes: int = HARD_MAX_BYTES) -> dict[str, Any]:
    """Verify strict `< max_bytes`, `\\xff\\xd8\\xff` magic header, and Baseline SOF0."""
    if len(data) < 4 or not data.startswith(JPEG_MAGIC):
        raise AssertionError("Output does not start with JPEG magic bytes \\xff\\xd8\\xff")
    if len(data) >= max_bytes:
        raise AssertionError(f"Output size {len(data)} bytes exceeds strict < {max_bytes} bytes gate")
    with Image.open(io.BytesIO(data)) as check_img:
        if check_img.format != "JPEG":
            raise AssertionError(f"Decoded format is {check_img.format}, expected JPEG")
        if bool(check_img.info.get("progressive", 0)):
            raise AssertionError("JPEG is progressive; strict Baseline JPEG required")
        w, h = check_img.size
    return {"bytes": len(data), "kb": round(len(data) / 1024.0, 2), "width": w, "height": h}


def encode_safe_baseline_jpeg(
    img: Image.Image,
    max_bytes: int = DEFAULT_TARGET_KB * 1024,
) -> tuple[bytes, int, tuple[int, int]]:
    """Adaptively compress `img` into a `< max_bytes` Baseline JPEG."""
    limit = min(max_bytes, HARD_MAX_BYTES - 512)
    work = _to_rgb_white_bg(img)

    # Cap extreme single-slice pixel edge so handwriting stays sharp while fitting <150KB
    max_edge = max(work.size)
    if max_edge > 2600:
        ratio = 2600.0 / max_edge
        work = work.resize(
            (max(16, int(round(work.width * ratio))), max(16, int(round(work.height * ratio)))),
            Image.Resampling.LANCZOS,
        )

    qualities = (88, 82, 76, 70, 64, 58, 52, 46)
    for scale_step in range(12):
        for q in qualities:
            buf = io.BytesIO()
            work.save(
                buf,
                format="JPEG",
                quality=q,
                optimize=True,
                progressive=False,
                subsampling=2 if q < 76 else 1,
            )
            payload = buf.getvalue()
            if len(payload) < limit:
                verify_baseline_jpeg_bytes(payload, HARD_MAX_BYTES)
                return payload, q, work.size

        # Still above budget: gently step down resolution by 12% and retry
        new_w = max(64, int(round(work.width * 0.88)))
        new_h = max(64, int(round(work.height * 0.88)))
        if (new_w, new_h) == work.size:
            break
        work = work.resize((new_w, new_h), Image.Resampling.LANCZOS)

    raise RuntimeError(f"Failed to compress crop below {limit} bytes after adaptive downscaling")


def crop_and_save(
    source_img: Image.Image,
    box: tuple[int, int, int, int],
    out_path: Path,
    max_bytes: int,
) -> dict[str, Any]:
    cropped = source_img.crop(box)
    jpeg_bytes, quality, final_size = encode_safe_baseline_jpeg(cropped, max_bytes=max_bytes)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(jpeg_bytes)
    meta = verify_baseline_jpeg_bytes(out_path.read_bytes(), HARD_MAX_BYTES)
    return {
        "path": str(out_path.resolve()),
        "crop_box_px": list(box),
        "source_crop_size": [box[2] - box[0], box[3] - box[1]],
        "output_size": list(final_size),
        "quality": quality,
        "bytes": meta["bytes"],
        "kb": meta["kb"],
        "magic_hex": out_path.read_bytes()[:3].hex(),
        "baseline_jpeg": True,
    }


def run_self_test() -> int:
    """Synthesize a 300-DPI PDF + dense image, verify bbox/grid slicing & <150KB Baseline JPEG."""
    with tempfile.TemporaryDirectory(prefix="crop_exam_selftest_") as tmp:
        tmp_dir = Path(tmp)
        pdf_path = tmp_dir / "mock_22408_sheet.pdf"

        # 1. Build synthetic A4 PDF exam sheet
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((48, 60), "22408 Mock Exam Answer Sheet - Page 1", fontsize=16)
        for idx in range(1, 22):
            y = 95 + idx * 32
            page.draw_line((45, y + 6), (550, y + 6), color=(0.75, 0.75, 0.75), width=0.5)
            page.insert_text(
                (52, y),
                f"Q{idx}. lim_(x->0) (sin x - x) / x^3 = -1/6 ; T(n) = 2T(n/2) + O(n log n)",
                fontsize=11,
            )
        doc.save(pdf_path)
        doc.close()

        rendered = render_input_page(pdf_path, page_num=1, dpi=300)
        assert rendered.width > 2000 and rendered.height > 3000, f"Unexpected 300-DPI size: {rendered.size}"

        # Test A: Normalized --bbox on PDF
        box_norm = parse_bbox("0.05,0.05,0.95,0.48", rendered.width, rendered.height, "auto")
        out_a = crop_and_save(rendered, box_norm, tmp_dir / "q1_norm.jpg", DEFAULT_TARGET_KB * 1024)

        # Test B: Pixel --bbox on PDF
        box_px = parse_bbox("100,1500,2350,3200", rendered.width, rendered.height, "auto")
        out_b = crop_and_save(rendered, box_px, tmp_dir / "q2_px.jpg", DEFAULT_TARGET_KB * 1024)

        # Test C: Dense high-frequency synthetic ink image + --grid 2,2 stress test
        rng = random.Random(22408)
        dense = Image.new("RGB", (2480, 3508), (252, 251, 247))
        draw = ImageDraw.Draw(dense)
        for _ in range(1800):
            x0 = rng.randint(0, 2400)
            y0 = rng.randint(0, 3420)
            x1 = min(2479, x0 + rng.randint(15, 180))
            y1 = min(3507, y0 + rng.randint(15, 180))
            col = (rng.randint(10, 90), rng.randint(10, 90), rng.randint(20, 120))
            draw.line((x0, y0, x1, y1), fill=col, width=2)
        png_path = tmp_dir / "dense_handwriting.png"
        dense.save(png_path, format="PNG")

        loaded_png = render_input_page(png_path, dpi=300)
        grid_tiles = build_grid_boxes(loaded_png.width, loaded_png.height, 2, 2, overlap=0.02)
        grid_outputs = [
            crop_and_save(loaded_png, gbox, tmp_dir / f"tile_r{r}_c{c}.jpg", DEFAULT_TARGET_KB * 1024)
            for r, c, gbox in grid_tiles
        ]

        # Test D: --auto-bands horizontal projection valley splitting on multi-problem PDF page
        doc_bands = fitz.open()
        bpage = doc_bands.new_page(width=595, height=842)
        for prob_idx, top_pt in enumerate((65, 330, 595), start=1):
            for ln in range(5):
                bpage.insert_text(
                    (52, top_pt + ln * 22),
                    f"Problem {prob_idx} Step {ln + 1}: int_0^1 x^2 dx = 1/3, rank(A) = n - dim N(A)",
                    fontsize=11,
                )
        bands_pdf = tmp_dir / "multi_problem_sheet.pdf"
        doc_bands.save(bands_pdf)
        doc_bands.close()
        rendered_bands = render_input_page(bands_pdf, page_num=1, dpi=300)
        auto_boxes = build_auto_band_boxes(rendered_bands, max_bands=5)
        assert len(auto_boxes) >= 2, f"Expected >=2 auto bands, got {len(auto_boxes)}"
        band_outputs = [
            crop_and_save(rendered_bands, bbox, tmp_dir / f"band_{bidx:02d}.jpg", DEFAULT_TARGET_KB * 1024)
            for bidx, bbox in auto_boxes
        ]

        all_items = [out_a, out_b, *grid_outputs, *band_outputs]
        for item in all_items:
            assert 0 < item["bytes"] < HARD_MAX_BYTES, f"Size violation: {item}"
            assert item["magic_hex"] == "ffd8ff", f"Magic byte violation: {item}"
            assert item["baseline_jpeg"] is True, f"Baseline JPEG violation: {item}"

        print(
            json.dumps(
                {
                    "ok": True,
                    "self_test": "passed",
                    "slices_verified": len(all_items),
                    "max_bytes_observed": max(i["bytes"] for i in all_items),
                    "hard_ceiling_bytes": HARD_MAX_BYTES,
                    "magic_bytes": "ffd8ff",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render PDF/image exam sheets at 300 DPI and crop single questions to <150KB Baseline JPEG."
    )
    parser.add_argument("input", nargs="?", help="Input PDF or raster image path")
    parser.add_argument("--page", type=int, default=1, help="1-based PDF page number (default: 1)")
    parser.add_argument("--dpi", type=int, default=300, help="PDF rasterization DPI (default: 300)")
    parser.add_argument(
        "--bbox",
        action="append",
        default=[],
        help="Crop box 'x0,y0,x1,y1' (normalized 0..1 or pixel coords; repeatable for multiple questions)",
    )
    parser.add_argument(
        "--coords",
        choices=("auto", "norm", "px"),
        default="auto",
        help="Coordinate mode for --bbox (default: auto)",
    )
    parser.add_argument(
        "--grid",
        default="",
        help="Slice page into 'rows,cols' grid tiles (e.g. '2,1' or '3,2')",
    )
    parser.add_argument(
        "--auto-bands",
        action="store_true",
        help="Automatically split page along horizontal grayscale projection whitespace valleys without slicing equations mid-line",
    )
    parser.add_argument(
        "--max-bands",
        type=int,
        default=6,
        help="Maximum horizontal bands when using --auto-bands (default: 6)",
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.02,
        help="Fractional overlap [0..0.25] around --grid tiles so strokes on seams stay intact (default: 0.02)",
    )
    parser.add_argument("--out", default="", help="Exact output .jpg path (when producing a single slice)")
    parser.add_argument("--out-dir", default="./exam_crops", help="Output directory for slices (default: ./exam_crops)")
    parser.add_argument("--prefix", default="", help="Filename prefix inside --out-dir (default: input stem + page)")
    parser.add_argument(
        "--max-kb",
        type=int,
        default=DEFAULT_TARGET_KB,
        help=f"Target max KB <= 149 (default: {DEFAULT_TARGET_KB}, strictly < 150 KB)",
    )
    parser.add_argument("--self-test", action="store_true", help="Run built-in synthetic PDF/image self-test and exit")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.input:
        parser.error("the following arguments are required: input (unless --self-test is passed)")
    mode_count = sum(bool(x) for x in (args.bbox, args.grid, args.auto_bands))
    if mode_count > 1:
        parser.error("pass at most one of --bbox, --grid, or --auto-bands")
    if args.max_kb < 20 or args.max_kb >= 150:
        parser.error("--max-kb must be between 20 and 149 to guarantee strict <150KB output")

    in_path = Path(args.input).expanduser()
    src_img = render_input_page(in_path, page_num=args.page, dpi=args.dpi)
    max_bytes = min(args.max_kb * 1024, HARD_MAX_BYTES - 512)
    stem = args.prefix.strip() or (
        f"{in_path.stem}_p{args.page:02d}" if in_path.suffix.lower() in PDF_EXTS else in_path.stem
    )
    out_dir = Path(args.out_dir).expanduser()

    tasks: list[tuple[tuple[int, int, int, int], Path]] = []
    if args.bbox:
        for idx, spec in enumerate(args.bbox, start=1):
            box = parse_bbox(spec, src_img.width, src_img.height, coords_mode=args.coords)
            if args.out and len(args.bbox) == 1:
                dest = Path(args.out).expanduser()
            else:
                dest = out_dir / f"{stem}_q{idx:02d}.jpg"
            tasks.append((box, dest))
    elif args.grid:
        parts = [p.strip() for p in args.grid.split(",") if p.strip()]
        if len(parts) != 2:
            parser.error("--grid expects 'rows,cols', e.g. --grid 3,1")
        rows, cols = int(parts[0]), int(parts[1])
        tiles = build_grid_boxes(src_img.width, src_img.height, rows, cols, overlap=args.overlap)
        for r, c, box in tiles:
            if args.out and len(tiles) == 1:
                dest = Path(args.out).expanduser()
            else:
                dest = out_dir / f"{stem}_r{r:02d}_c{c:02d}.jpg"
            tasks.append((box, dest))
    elif args.auto_bands:
        bands = build_auto_band_boxes(src_img, max_bands=max(2, min(args.max_bands, 15)))
        for bidx, box in bands:
            if args.out and len(bands) == 1:
                dest = Path(args.out).expanduser()
            else:
                dest = out_dir / f"{stem}_band{bidx:02d}.jpg"
            tasks.append((box, dest))
    else:
        full_box = (0, 0, src_img.width, src_img.height)
        dest = Path(args.out).expanduser() if args.out else (out_dir / f"{stem}_full.jpg")
        tasks.append((full_box, dest))

    outputs = [crop_and_save(src_img, box, dest, max_bytes=max_bytes) for box, dest in tasks]
    print(
        json.dumps(
            {
                "ok": True,
                "input": str(in_path.resolve()),
                "page": args.page if in_path.suffix.lower() in PDF_EXTS else None,
                "dpi": args.dpi if in_path.suffix.lower() in PDF_EXTS else None,
                "rendered_size": [src_img.width, src_img.height],
                "count": len(outputs),
                "slices": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
