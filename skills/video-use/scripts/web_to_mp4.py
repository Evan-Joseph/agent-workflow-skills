#!/usr/bin/env python3
"""Apple Silicon Full-Throttle Parallel Hardware Code-Video Renderer (`web_to_mp4.py`).

Renders deterministic HTML / CSS / SVG / Canvas 2D / Three.js WebGL2 / GLSL animations
into broadcast-ready H.264 (`bt709`, `yuv420p`, `+faststart`) MP4 at 10x+ realtime speed on Apple M1 Pro.

Architecture:
1. `cdp-metal` (Default — Universal DOM + CSS + SVG + WebGL2):
   - Serves local directory over a multi-threaded `127.0.0.1` HTTP server (avoids `file://` CORS/SecureContext traps).
   - Launches ONE headless Chrome instance pinned to Apple Metal (`--use-gl=angle --use-angle=metal
     --enable-gpu-rasterization --enable-zero-copy`) and verifies `WEBGL_debug_renderer_info` hits Metal (not SwiftShader).
   - Fans out `N` isolated `BrowserContext` shards (`--workers 8`, 8 parallel Renderer processes sharing 1 Metal GPU process).
   - Captures frames via raw CDP `Page.captureScreenshot(format="jpeg", quality=95, optimizeForSpeed=True)` with zero
     Playwright stability-wait stalls and zero disk image files, streaming frames through async background queues
     into `N` parallel `h264_videotoolbox` hardware encoder processes (`-frames_before` / `-frames_after`), followed by
     sub-second lossless `ffmpeg -f concat -c copy` + AAC 320k master audio muxing.

2. `webcodecs` (Pure Single-Canvas Zero-Copy Hardware Path):
   - Uses `http://127.0.0.1` SecureContext native `VideoEncoder` (`avc1.640028` / `avc1.640033`,
     `hardwareAcceleration: "prefer-hardware"`, `avc: { format: "annexb" }`) directly on `<canvas>` to encode H.264
     on Apple VideoToolbox without GPU->CPU JPEG readback.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import functools
import http.server
import json
import mimetypes
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from typing import Any

from playwright.async_api import async_playwright

ASPECT_PRESETS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
}

METAL_CHROME_ARGS = [
    "--headless=new",
    "--use-gl=angle",
    "--use-angle=metal",
    "--enable-webgl",
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--ignore-gpu-blocklist",
    "--no-proxy-server",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--renderer-process-limit=24",
    "--mute-audio",
    "--hide-scrollbars",
]


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **mimetypes.types_map,
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".wasm": "application/wasm",
        ".woff2": "font/woff2",
        ".glsl": "text/plain; charset=utf-8",
    }

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


class _HighBacklogHTTPServer(http.server.ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True
    allow_reuse_address = True


class LocalStaticServer:
    """Multi-threaded 127.0.0.1 HTTP server for zero-CORS, SecureContext parallel shard loading."""

    def __init__(self, root_dir: pathlib.Path) -> None:
        self.root_dir = root_dir.resolve()
        handler = functools.partial(_QuietStaticHandler, directory=str(self.root_dir))
        self.httpd = _HighBacklogHTTPServer(("127.0.0.1", 0), handler)
        self.port = int(self.httpd.server_address[1])
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="web-to-mp4-static", daemon=True)

    def __enter__(self) -> "LocalStaticServer":
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def probe_media_duration(media_path: pathlib.Path) -> float | None:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return float(res.stdout.strip())
        except ValueError:
            return None
    return None


def append_query(base_url: str, extra_query: str) -> str:
    if not extra_query:
        return base_url
    parsed = urllib.parse.urlsplit(base_url)
    existing = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    added = urllib.parse.parse_qsl(extra_query.lstrip("?"), keep_blank_values=True)
    existing_keys = {k for k, _ in existing}
    merged = list(existing) + [(k, v) for k, v in added if k not in existing_keys]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(merged), parsed.fragment)
    )


def build_shard_ffmpeg_cmd(
    out_shard: pathlib.Path,
    *,
    fps: float,
    img_format: str,
    encoder: str,
    bitrate: str,
    maxrate: str,
    bufsize: str,
    crf: int,
    preset: str,
    shard_idx: int,
    num_shards: int,
) -> list[str]:
    vcodec_in = "mjpeg" if img_format == "jpeg" else "png"
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        vcodec_in,
        "-framerate",
        f"{fps:g}",
        "-i",
        "-",
    ]
    if img_format == "jpeg":
        cmd.extend(
            [
                "-vf",
                "scale=in_range=pc:out_range=tv:in_color_matrix=bt709:out_color_matrix=bt709,format=yuv420p",
            ]
        )
    else:
        cmd.extend(["-vf", "format=yuv420p"])

    if encoder == "videotoolbox":
        cmd.extend(
            [
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                bitrate,
                "-maxrate",
                maxrate,
                "-bufsize",
                bufsize,
                "-profile:v",
                "high",
                "-allow_sw",
                "1",
                "-spatial_aq",
                "1",
            ]
        )
        if shard_idx > 0:
            cmd.extend(["-frames_before", "1"])
        if shard_idx < num_shards - 1:
            cmd.extend(["-frames_after", "1"])
    else:
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-x264-params",
                "aq-mode=3:aq-strength=0.9",
            ]
        )

    cmd.extend(
        [
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-video_track_timescale",
            "90000",
            str(out_shard),
        ]
    )
    return cmd


class _PipeEncoderWorker:
    """Dedicated background thread draining encoded frame bytes into shard FFmpeg stdin without blocking asyncio."""

    def __init__(self, cmd: list[str]) -> None:
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=4 * 1024 * 1024,
        )
        self.q: queue.Queue[bytes | None] = queue.Queue(maxsize=24)
        self.exc: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self.proc.stdin is not None
        try:
            while True:
                item = self.q.get()
                if item is None:
                    break
                self.proc.stdin.write(item)
        except BaseException as exc:  # noqa: BLE001
            self.exc = exc
        finally:
            try:
                self.proc.stdin.close()
            except Exception:
                pass

    async def write(self, data: bytes) -> None:
        if self.exc is not None:
            raise RuntimeError(f"FFmpeg shard pipe failed: {self.exc}") from self.exc
        while True:
            try:
                self.q.put_nowait(data)
                return
            except queue.Full:
                await asyncio.sleep(0.002)

    async def finish(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._finish_blocking)

    def _finish_blocking(self) -> None:
        self.q.put(None)
        self._thread.join()
        stderr_bytes = self.proc.stderr.read() if self.proc.stderr else b""
        rc = self.proc.wait()
        if self.exc is not None:
            raise RuntimeError(f"FFmpeg shard pipe write error: {self.exc} | stderr={stderr_bytes.decode('utf-8', 'replace')}")
        if rc != 0:
            raise RuntimeError(f"FFmpeg shard exited with code {rc}: {stderr_bytes.decode('utf-8', 'replace')}")

    def abort(self) -> None:
        try:
            self.proc.kill()
        except Exception:
            pass


def build_page_init_js(aspect: str | None, custom_seek_expr: str | None) -> str:
    aspect_json = json.dumps(aspect)
    custom_expr_json = json.dumps(custom_seek_expr or "")
    return f"""(async () => {{
      const aspect = {aspect_json};
      const customExpr = {custom_expr_json};

      // Pause any auto-playing HTMLMediaElement or animations that might race with deterministic seek
      try {{
        document.querySelectorAll('audio, video').forEach(el => {{ try {{ el.pause(); }} catch (_) {{}} }});
      }} catch (_) {{}}

      if (aspect) {{
        try {{
          if (typeof window.setAspect === 'function') {{
            window.setAspect(aspect);
          }} else if (document.body) {{
            document.body.setAttribute('data-aspect', aspect);
          }}
        }} catch (_) {{}}
      }}

      if (document.fonts && document.fonts.ready) {{
        try {{ await document.fonts.ready; }} catch (_) {{}}
      }}

      const imgs = Array.from(document.images || []);
      await Promise.all(imgs.map(img => {{
        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
        if (typeof img.decode === 'function') return img.decode().catch(() => {{}});
        return new Promise(res => {{
          img.addEventListener('load', res, {{ once: true }});
          img.addEventListener('error', res, {{ once: true }});
          setTimeout(res, 3000);
        }});
      }}));

      // Wait up to 3s if page uses lemo-opuscar / huashu `window.READY === false` gate or async script init
      for (let waitIter = 0; waitIter < 100; waitIter++) {{
        const hasFn = (
          Boolean(customExpr) ||
          typeof window.seek === 'function' ||
          typeof window.__seekTo === 'function' ||
          typeof window.render === 'function' ||
          typeof window.setFrame === 'function'
        );
        const readyOk = !('READY' in window && window.READY === false);
        if (hasFn && readyOk) break;
        await new Promise(r => setTimeout(r, 30));
      }}

      if (customExpr) {{
        window.__agyCustomSeekFn = new Function('t', 'frame', 'fps', customExpr);
        window.__agySeekFrame = (t, frame, fps) => window.__agyCustomSeekFn(t, frame, fps);
      }} else if (typeof window.seek === 'function') {{
        window.__agySeekFrame = (t) => window.seek(t);
      }} else if (typeof window.__seekTo === 'function') {{
        window.__agySeekFrame = (t) => window.__seekTo(t);
      }} else if (typeof window.render === 'function') {{
        window.__agySeekFrame = (t) => window.render(t);
      }} else if (typeof window.setFrame === 'function') {{
        window.__agySeekFrame = (_t, frame) => window.setFrame(frame);
      }} else {{
        throw new Error(
          'Page exposes none of window.seek(t), window.__seekTo(t), window.render(t), or window.setFrame(frame); pass --seek-expr.'
        );
      }}

      const probe = window.__agySeekFrame(0, 0, 30);
      const isAsyncSeek = Boolean(probe && typeof probe.then === 'function');
      if (isAsyncSeek) await probe;

      const pageDuration = Number(window.Duration ?? window.DUR ?? window.DURATION ?? 0) || null;
      const pageFps = Number(window.FPS ?? window.fps ?? 0) || null;

      let glVendor = null;
      let glRenderer = null;
      try {{
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl2') || c.getContext('webgl');
        if (gl) {{
          const dbg = gl.getExtension('WEBGL_debug_renderer_info');
          glVendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
          glRenderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
          gl.getExtension('WEBGL_lose_context')?.loseContext();
        }}
      }} catch (_) {{}}

      return {{
        isAsyncSeek,
        pageDuration,
        pageFps,
        glVendor,
        glRenderer,
        isSecureContext: Boolean(window.isSecureContext),
        hasVideoEncoder: typeof window.VideoEncoder === 'function',
      }};
    }})()"""


async def launch_metal_browser(pw: Any) -> Any:
    try:
        return await pw.chromium.launch(channel="chrome", headless=True, args=METAL_CHROME_ARGS)
    except Exception:
        return await pw.chromium.launch(headless=True, args=METAL_CHROME_ARGS)


async def run_cdp_metal_shard(
    browser: Any,
    target_url: str,
    shard_out: pathlib.Path,
    *,
    shard_idx: int,
    num_shards: int,
    start_frame: int,
    end_frame: int,
    fps: float,
    width: int,
    height: int,
    dpr: float,
    aspect: str | None,
    seek_expr: str | None,
    warmup_ms: int,
    img_format: str,
    jpeg_quality: int,
    encoder: str,
    bitrate: str,
    maxrate: str,
    bufsize: str,
    crf: int,
    preset: str,
    progress_cb: Any,
) -> int:
    shard_url = append_query(target_url, f"t={start_frame / fps:.5f}")
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=dpr,
    )
    ffmpeg_cmd = build_shard_ffmpeg_cmd(
        shard_out,
        fps=fps,
        img_format=img_format,
        encoder=encoder,
        bitrate=bitrate,
        maxrate=maxrate,
        bufsize=bufsize,
        crf=crf,
        preset=preset,
        shard_idx=shard_idx,
        num_shards=num_shards,
    )
    pipe_worker = _PipeEncoderWorker(ffmpeg_cmd)
    try:
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)
        await cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": dpr,
                "mobile": False,
            },
        )
        await page.goto(shard_url, wait_until="load", timeout=45_000)
        init_info = await page.evaluate(build_page_init_js(aspect, seek_expr))
        is_async_seek = bool(init_info.get("isAsyncSeek"))
        if warmup_ms > 0:
            await page.wait_for_timeout(warmup_ms)

        shot_params: dict[str, Any] = {
            "format": img_format,
            "optimizeForSpeed": True,
            "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
        }
        if img_format == "jpeg":
            shot_params["quality"] = jpeg_quality

        count = 0
        for f in range(start_frame, end_frame):
            t = f / fps
            await cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"window.__agySeekFrame({t:.6f},{f},{fps:g})",
                    "awaitPromise": is_async_seek,
                    "returnByValue": False,
                },
            )
            shot = await cdp.send("Page.captureScreenshot", shot_params)
            raw_bytes = base64.b64decode(shot["data"])
            await pipe_worker.write(raw_bytes)
            count += 1
            if count % 60 == 0:
                progress_cb(60)
        rem = count % 60
        if rem:
            progress_cb(rem)

        await pipe_worker.finish()
        return count
    except BaseException:
        pipe_worker.abort()
        raise
    finally:
        await context.close()


def parse_bitrate_bps(bitrate_str: str) -> int:
    s = bitrate_str.strip().upper()
    if s.endswith("M"):
        return int(float(s[:-1]) * 1_000_000)
    if s.endswith("K"):
        return int(float(s[:-1]) * 1_000)
    return int(float(s))


async def run_webcodecs_shard(
    browser: Any,
    target_url: str,
    shard_out: pathlib.Path,
    *,
    shard_idx: int,
    start_frame: int,
    end_frame: int,
    fps: float,
    width: int,
    height: int,
    dpr: float,
    aspect: str | None,
    seek_expr: str | None,
    canvas_selector: str,
    warmup_ms: int,
    bitrate: str,
    progress_cb: Any,
) -> int:
    shard_url = append_query(target_url, f"t={start_frame / fps:.5f}")
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=dpr,
    )
    h264_path = shard_out.with_suffix(f".shard{shard_idx:02d}.h264")
    try:
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)
        await cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": dpr,
                "mobile": False,
            },
        )
        with h264_path.open("wb") as h264_fh:

            def _on_chunk(_source: Any, b64_payload: str) -> None:
                h264_fh.write(base64.b64decode(b64_payload))

            await page.expose_binding("__agyPushAnnexB", _on_chunk)
            await page.goto(shard_url, wait_until="load", timeout=45_000)
            init_info = await page.evaluate(build_page_init_js(aspect, seek_expr))
            if not init_info.get("hasVideoEncoder"):
                raise RuntimeError("WebCodecs VideoEncoder unavailable in current browser context; use --mode cdp-metal.")
            if warmup_ms > 0:
                await page.wait_for_timeout(warmup_ms)

            out_w = int(round(width * dpr))
            out_h = int(round(height * dpr))
            avc_codec = "avc1.640033" if (out_w * out_h > 1920 * 1088 or fps > 30) else "avc1.640028"
            bitrate_bps = parse_bitrate_bps(bitrate)

            encoded_count = await page.evaluate(
                """async (cfg) => {
                  const canvas = document.querySelector(cfg.canvasSelector);
                  if (!canvas) throw new Error('Canvas not found for selector: ' + cfg.canvasSelector);
                  let encError = null;
                  let pendingChunks = [];
                  let pendingBytes = 0;

                  const flushBatch = async () => {
                    if (!pendingChunks.length) return;
                    const merged = new Uint8Array(pendingBytes);
                    let off = 0;
                    for (const u8 of pendingChunks) {
                      merged.set(u8, off);
                      off += u8.byteLength;
                    }
                    pendingChunks = [];
                    pendingBytes = 0;
                    let bin = '';
                    const step = 0x8000;
                    for (let i = 0; i < merged.length; i += step) {
                      bin += String.fromCharCode.apply(null, merged.subarray(i, i + step));
                    }
                    await window.__agyPushAnnexB(btoa(bin));
                  };

                  const encoder = new VideoEncoder({
                    output: (chunk) => {
                      const buf = new Uint8Array(chunk.byteLength);
                      chunk.copyTo(buf);
                      pendingChunks.push(buf);
                      pendingBytes += buf.byteLength;
                    },
                    error: (e) => { encError = e; },
                  });

                  encoder.configure({
                    codec: cfg.codec,
                    width: canvas.width || cfg.width,
                    height: canvas.height || cfg.height,
                    bitrate: cfg.bitrateBps,
                    framerate: cfg.fps,
                    hardwareAcceleration: 'prefer-hardware',
                    avc: { format: 'annexb' },
                    latencyMode: 'quality',
                  });

                  const keyInterval = Math.max(1, Math.round(cfg.fps * 2));
                  let done = 0;
                  for (let f = cfg.startFrame; f < cfg.endFrame; f++) {
                    if (encError) throw encError;
                    const t = f / cfg.fps;
                    const r = window.__agySeekFrame(t, f, cfg.fps);
                    if (r && typeof r.then === 'function') await r;

                    const localIdx = f - cfg.startFrame;
                    const tsUs = Math.round((localIdx * 1_000_000) / cfg.fps);
                    const durUs = Math.round(1_000_000 / cfg.fps);
                    const vf = new VideoFrame(canvas, { timestamp: tsUs, duration: durUs });
                    encoder.encode(vf, { keyFrame: localIdx % keyInterval === 0 });
                    vf.close();

                    while (encoder.encodeQueueSize > 10) {
                      await new Promise(res => setTimeout(res, 1));
                    }
                    if (pendingBytes >= 2 * 1024 * 1024) {
                      await flushBatch();
                    }
                    done++;
                  }
                  await encoder.flush();
                  encoder.close();
                  if (encError) throw encError;
                  await flushBatch();
                  return done;
                }""",
                {
                    "canvasSelector": canvas_selector,
                    "codec": avc_codec,
                    "width": out_w,
                    "height": out_h,
                    "bitrateBps": bitrate_bps,
                    "fps": fps,
                    "startFrame": start_frame,
                    "endFrame": end_frame,
                },
            )
            progress_cb(int(encoded_count))

        # Remux Annex-B H.264 stream into exact-timescale MP4 shard
        remux_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-fflags",
            "+genpts",
            "-r",
            f"{fps:g}",
            "-f",
            "h264",
            "-i",
            str(h264_path),
            "-c:v",
            "copy",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-video_track_timescale",
            "90000",
            str(shard_out),
        ]
        subprocess.run(remux_cmd, stdin=subprocess.DEVNULL, check=True, timeout=60)
        h264_path.unlink(missing_ok=True)
        return int(encoded_count)
    finally:
        h264_path.unlink(missing_ok=True)
        await context.close()


def concat_shards_and_mux_audio(
    shards: list[pathlib.Path],
    output_mp4: pathlib.Path,
    *,
    audio_path: pathlib.Path | None,
    audio_offset: float,
    video_duration: float,
    loudnorm: bool,
) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_list = shards[0].parent / "concat_list.txt"
    concat_lines = [f"file '{s.as_posix()}'" for s in shards]
    concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
    ]
    if audio_path:
        if audio_offset > 0:
            cmd.extend(["-ss", f"{audio_offset:.4f}"])
        cmd.extend(["-i", str(audio_path)])

    cmd.extend(["-map", "0:v:0", "-c:v", "copy"])
    if audio_path:
        cmd.extend(["-map", "1:a:0", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"])
        if loudnorm:
            cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
        cmd.extend(["-t", f"{video_duration:.4f}"])

    cmd.extend(["-movflags", "+faststart", str(output_mp4)])
    subprocess.run(cmd, stdin=subprocess.DEVNULL, check=True, timeout=180)


async def orchestrate_render(args: argparse.Namespace) -> dict[str, Any]:
    t_wall_start = time.perf_counter()
    raw_target = args.input.strip()
    is_remote_url = raw_target.startswith(("http://", "https://"))

    static_ctx: LocalStaticServer | None = None
    if is_remote_url:
        base_url = raw_target
    else:
        p = pathlib.Path(raw_target).expanduser().resolve()
        if p.is_dir():
            html_file = p / "index.html"
            if not html_file.is_file():
                raise FileNotFoundError(f"No index.html inside directory: {p}")
            serve_root = p
            rel_html = "index.html"
        elif p.is_file():
            # Serve parent (or project root if assets are referenced via ../)
            serve_root = p.parent
            rel_html = p.name
        else:
            raise FileNotFoundError(f"Input target does not exist: {p}")
        static_ctx = LocalStaticServer(serve_root)
        static_ctx.__enter__()
        base_url = f"http://127.0.0.1:{static_ctx.port}/{urllib.parse.quote(rel_html)}"

    query_str = "" if args.no_pure_query else args.query
    target_url = append_query(base_url, query_str)

    if args.width and args.height:
        width, height = int(args.width), int(args.height)
        aspect_tag = args.aspect if args.aspect in ASPECT_PRESETS else None
    else:
        aspect_tag = args.aspect
        width, height = ASPECT_PRESETS[aspect_tag]

    audio_path = pathlib.Path(args.audio).expanduser().resolve() if args.audio else None
    if audio_path and not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_mp4 = pathlib.Path(args.output).expanduser().resolve()

    try:
        async with async_playwright() as pw:
            browser = await launch_metal_browser(pw)
            try:
                # 1) Preflight GPU Metal & page contract probe
                probe_ctx = await browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=args.dpr,
                )
                probe_page = await probe_ctx.new_page()
                await probe_page.goto(target_url, wait_until="load", timeout=45_000)
                probe_info = await probe_page.evaluate(build_page_init_js(aspect_tag, args.seek_expr))
                await probe_ctx.close()

                gl_renderer = str(probe_info.get("glRenderer") or "unknown")
                gl_vendor = str(probe_info.get("glVendor") or "unknown")
                if "swiftshader" in gl_renderer.lower() and not args.allow_software_gl:
                    raise RuntimeError(
                        f"Software WebGL fallback detected ({gl_renderer}); refusing slow render without Apple Metal."
                    )

                fps = float(args.fps or probe_info.get("pageFps") or 30.0)
                duration = args.duration
                if duration is None:
                    duration = probe_info.get("pageDuration")
                if duration is None and audio_path:
                    aud_dur = probe_media_duration(audio_path)
                    if aud_dur:
                        duration = max(0.1, aud_dur - args.start)
                if not duration or duration <= 0:
                    raise ValueError("Could not infer video duration from page or --audio; pass --duration <seconds>.")

                start_frame = int(round(args.start * fps))
                total_frames = max(1, int(round(duration * fps)))
                end_frame = start_frame + total_frames
                workers = max(1, min(int(args.workers), total_frames))

                print(
                    f"[web_to_mp4] mode={args.mode} encoder={args.encoder} workers={workers} "
                    f"res={width}x{height}@{fps:g}fps frames={total_frames} ({duration:.2f}s) "
                    f"GPU='{gl_renderer}'",
                    flush=True,
                )

                t_render_start = time.perf_counter()
                with tempfile.TemporaryDirectory(prefix="web_to_mp4_") as tmp_dir_str:
                    tmp_dir = pathlib.Path(tmp_dir_str)
                    shards: list[pathlib.Path] = []
                    tasks = []
                    chunk = (total_frames + workers - 1) // workers
                    completed_frames = 0
                    last_log_pct = -10

                    def _on_progress(delta: int) -> None:
                        nonlocal completed_frames, last_log_pct
                        completed_frames += delta
                        pct = int((completed_frames * 100) / total_frames)
                        if pct >= last_log_pct + 20 or completed_frames == total_frames:
                            last_log_pct = pct
                            elapsed = max(1e-3, time.perf_counter() - t_render_start)
                            print(
                                f"  [progress] {completed_frames}/{total_frames} frames ({pct}%) | "
                                f"{completed_frames / elapsed:.1f} fps",
                                flush=True,
                            )

                    actual_shard_specs: list[tuple[int, int, int, pathlib.Path]] = []
                    for w_idx in range(workers):
                        sf = start_frame + w_idx * chunk
                        ef = min(end_frame, start_frame + (w_idx + 1) * chunk)
                        if sf >= ef:
                            continue
                        shard_path = tmp_dir / f"shard_{len(actual_shard_specs):02d}.mp4"
                        actual_shard_specs.append((len(actual_shard_specs), sf, ef, shard_path))
                        shards.append(shard_path)

                    num_shards = len(actual_shard_specs)
                    for s_idx, sf, ef, shard_path in actual_shard_specs:
                        if args.mode == "webcodecs":
                            tasks.append(
                                run_webcodecs_shard(
                                    browser,
                                    target_url,
                                    shard_path,
                                    shard_idx=s_idx,
                                    start_frame=sf,
                                    end_frame=ef,
                                    fps=fps,
                                    width=width,
                                    height=height,
                                    dpr=args.dpr,
                                    aspect=aspect_tag,
                                    seek_expr=args.seek_expr,
                                    canvas_selector=args.canvas_selector,
                                    warmup_ms=args.warmup_ms,
                                    bitrate=args.bitrate,
                                    progress_cb=_on_progress,
                                )
                            )
                        else:
                            tasks.append(
                                run_cdp_metal_shard(
                                    browser,
                                    target_url,
                                    shard_path,
                                    shard_idx=s_idx,
                                    num_shards=num_shards,
                                    start_frame=sf,
                                    end_frame=ef,
                                    fps=fps,
                                    width=width,
                                    height=height,
                                    dpr=args.dpr,
                                    aspect=aspect_tag,
                                    seek_expr=args.seek_expr,
                                    warmup_ms=args.warmup_ms,
                                    img_format=args.format,
                                    jpeg_quality=args.jpeg_quality,
                                    encoder=args.encoder,
                                    bitrate=args.bitrate,
                                    maxrate=args.maxrate,
                                    bufsize=args.bufsize,
                                    crf=args.crf,
                                    preset=args.preset,
                                    progress_cb=_on_progress,
                                )
                            )

                    rendered_counts = await asyncio.gather(*tasks)
                    t_capture_encode = time.perf_counter() - t_render_start

                    t_mux_start = time.perf_counter()
                    eff_audio_offset = args.audio_offset + (args.start if args.sync_audio_to_start else 0.0)
                    concat_shards_and_mux_audio(
                        shards,
                        output_mp4,
                        audio_path=audio_path,
                        audio_offset=eff_audio_offset,
                        video_duration=total_frames / fps,
                        loudnorm=args.loudnorm,
                    )
                    t_mux = time.perf_counter() - t_mux_start

                total_elapsed = time.perf_counter() - t_wall_start
                effective_fps = total_frames / total_elapsed
                capture_fps = total_frames / max(1e-6, t_capture_encode)
                size_mb = output_mp4.stat().st_size / (1024 * 1024)

                summary = {
                    "ok": True,
                    "output": str(output_mp4),
                    "mode": args.mode,
                    "encoder": "webcodecs_videotoolbox" if args.mode == "webcodecs" else args.encoder,
                    "gpuVendor": gl_vendor,
                    "gpuRenderer": gl_renderer,
                    "workers": num_shards,
                    "width": int(round(width * args.dpr)),
                    "height": int(round(height * args.dpr)),
                    "fps": fps,
                    "frames": sum(rendered_counts),
                    "durationSec": round(total_frames / fps, 3),
                    "captureEncodeSec": round(t_capture_encode, 2),
                    "muxSec": round(t_mux, 2),
                    "totalElapsedSec": round(total_elapsed, 2),
                    "captureEncodeFps": round(capture_fps, 2),
                    "effectiveFps": round(effective_fps, 2),
                    "realtimeMultiplier": round(effective_fps / fps, 2),
                    "sizeMB": round(size_mb, 2),
                }
                print(
                    f"[web_to_mp4] DONE -> {output_mp4} ({size_mb:.2f} MB) | "
                    f"elapsed={total_elapsed:.2f}s (capture+hwenc={t_capture_encode:.2f}s, mux={t_mux:.2f}s) | "
                    f"effective={effective_fps:.1f} fps ({effective_fps / fps:.2f}x realtime)",
                    flush=True,
                )
                if args.json_report:
                    pathlib.Path(args.json_report).expanduser().write_text(
                        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                return summary
            finally:
                await browser.close()
    finally:
        if static_ctx is not None:
            static_ctx.__exit__(None, None, None)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Apple Silicon parallel Metal + VideoToolbox deterministic HTML/WebGL/Canvas video renderer."
    )
    p.add_argument("input", help="Path to HTML file, project directory with index.html, or http://127.0.0.1 URL")
    p.add_argument("-o", "--output", required=True, help="Output MP4 file path")
    p.add_argument("--duration", type=float, default=None, help="Duration in seconds (auto-detected from window.Duration/DUR or --audio if omitted)")
    p.add_argument("--start", type=float, default=0.0, help="Start offset in seconds (default: 0.0)")
    p.add_argument("--fps", type=float, default=None, help="Frames per second (default: window.FPS or 30)")
    p.add_argument("--aspect", choices=tuple(ASPECT_PRESETS.keys()), default="16:9", help="Viewport aspect preset: 16:9 (1920x1080), 9:16 (1080x1920), 1:1, 4:3")
    p.add_argument("--width", type=int, default=None, help="Explicit viewport width override")
    p.add_argument("--height", type=int, default=None, help="Explicit viewport height override")
    p.add_argument("--dpr", type=float, default=1.0, help="Device scale factor (default: 1.0)")

    p.add_argument("--mode", choices=("cdp-metal", "webcodecs"), default="cdp-metal", help="Render pipeline: 'cdp-metal' (full DOM/CSS/SVG/WebGL) or 'webcodecs' (single-canvas zero-copy)")
    p.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 8), help="Parallel BrowserContext shards (default: 8 on M1 Pro)")
    p.add_argument("--encoder", choices=("videotoolbox", "libx264"), default="videotoolbox", help="Video encoder in cdp-metal mode (default: videotoolbox hardware ASIC)")
    p.add_argument("--bitrate", default="22M", help="Target H.264 bitrate for videotoolbox/webcodecs (default: 22M)")
    p.add_argument("--maxrate", default="30M", help="Max H.264 bitrate for videotoolbox (default: 30M)")
    p.add_argument("--bufsize", default="48M", help="VBV buffer size for videotoolbox (default: 48M)")
    p.add_argument("--crf", type=int, default=16, help="CRF when --encoder libx264 is selected (default: 16)")
    p.add_argument("--preset", default="fast", help="x264 preset when --encoder libx264 is selected (default: fast)")
    p.add_argument("--format", choices=("jpeg", "png"), default="jpeg", help="CDP capture format in cdp-metal mode (default: jpeg)")
    p.add_argument("--jpeg-quality", type=int, default=95, help="CDP JPEG quality 1-100 (default: 95)")

    p.add_argument("--seek-expr", default=None, help="Custom JS body receiving (t, frame, fps), e.g. 'window.myRender(t)'")
    p.add_argument("--canvas-selector", default="canvas", help="Canvas CSS selector for --mode webcodecs (default: 'canvas')")
    p.add_argument("--query", default="pure=1", help="Query string appended to URL (default: 'pure=1' to hide HUD controls)")
    p.add_argument("--no-pure-query", action="store_true", help="Do not append default ?pure=1 query string")
    p.add_argument("--warmup-ms", type=int, default=120, help="Post-load warmup settle time in ms per shard (default: 120)")
    p.add_argument("--allow-software-gl", action="store_true", help="Allow rendering even if WebGL falls back to SwiftShader")

    p.add_argument("--audio", default=None, help="Master audio file (.mp3/.wav/.m4a/.flac) to mux into output MP4")
    p.add_argument("--audio-offset", type=float, default=0.0, help="Seek offset into --audio in seconds (default: 0.0)")
    p.add_argument("--sync-audio-to-start", action="store_true", help="Automatically add --start offset to --audio-offset")
    p.add_argument("--loudnorm", action="store_true", help="Apply EBU R128 loudnorm (-16 LUFS) to audio track (use for voiceover, omit for master MV)")
    p.add_argument("--json-report", default=None, help="Optional path to write JSON benchmark/telemetry report")
    return p


def main(argv: list[str] | None = None) -> int:
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg not found on PATH", file=sys.stderr)
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    asyncio.run(orchestrate_render(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
