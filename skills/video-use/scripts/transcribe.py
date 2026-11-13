#!/usr/bin/env python3
"""Transcribe a video via offline Apple Silicon MLX / whisper-cli or ElevenLabs Scribe.

Supports `--backend {auto,mlx,whisper-cli,elevenlabs}`:
  - `auto` (default): prefers zero-cost offline `mlx_whisper` (Apple Silicon Metal) ->
    `whisper-cli` (`whisper.cpp`) when installed locally, falling back to ElevenLabs Scribe.
  - `mlx`: local Python `mlx_whisper` module or `mlx_whisper` CLI (`whisper-large-v3-turbo`).
  - `whisper-cli`: local `whisper-cli` / `whisper-cpp` binary (`-ojf` full JSON with word timestamps).
  - `elevenlabs`: cloud ElevenLabs Scribe v1 with diarization & word-level timestamps.

Extracts mono 16kHz audio via ffmpeg and writes normalized JSON (`text`, `words`, `segments`)
to `<edit_dir>/transcripts/<video_stem>.json`. Cached if output file already exists.
"""

from __future__ import annotations

import argparse
import array
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import requests


SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
PRIVATE_ENV_FILE = Path.home() / ".config" / "elevenlabs" / "elevenlabs.env"
DEFAULT_MLX_MODEL = os.environ.get("MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")


def load_api_key() -> str:
    v = os.environ.get("ELEVENLABS_API_KEY", "")
    if v:
        return v

    if PRIVATE_ENV_FILE.exists():
        for line in PRIVATE_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, value = line.split("=", 1)
            if k.strip() == "ELEVENLABS_API_KEY":
                value = value.strip().strip('"').strip("'")
                if value:
                    return value

    for candidate in [Path(__file__).resolve().parent.parent / ".env", Path(".env")]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, value = line.split("=", 1)
                if k.strip() == "ELEVENLABS_API_KEY":
                    value = value.strip().strip('"').strip("'")
                    if value:
                        return value

    sys.exit(
        f"ELEVENLABS_API_KEY not found in environment, {PRIVATE_ENV_FILE}, or .env"
    )


def count_audio_tracks(video_path: Path) -> int:
    """How many audio streams the container holds."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    return len([ln for ln in out.stdout.splitlines() if ln.strip()])


def peak_dbfs(wav_path: Path) -> float:
    """Peak level of a 16-bit PCM wav, in dBFS. -inf for digital silence."""
    peak = 0
    with wave.open(str(wav_path), "rb") as w:
        # A chunk at a time: batch mode runs several of these at once, and a two-hour
        # take is 230 MB of 16 kHz mono before the array copy doubles it.
        while frames := w.readframes(1 << 16):
            samples = array.array("h", frames)
            peak = max(peak, max(samples), -min(samples))
    return 20 * math.log10(peak / 32768) if peak > 0 else float("-inf")


def extract_audio(video_path: Path, dest: Path, audio_track: int = 0) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-map", f"0:a:{audio_track}",
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
) -> dict:
    data: dict[str, str] = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")

    payload = resp.json()
    if isinstance(payload, dict):
        payload.setdefault("backend", "elevenlabs")
    return payload


def _has_mlx_whisper() -> tuple[bool, str]:
    if importlib.util.find_spec("mlx_whisper") is not None:
        return True, "module"
    cli = shutil.which("mlx_whisper") or "/opt/homebrew/bin/mlx_whisper"
    if cli and Path(cli).is_file():
        return True, cli
    return False, ""


def _find_whisper_cli() -> str | None:
    for name in ("whisper-cli", "whisper-cpp", "/opt/homebrew/bin/whisper-cli", "/opt/homebrew/bin/whisper-cpp"):
        resolved = name if name.startswith("/") else shutil.which(name)
        if resolved and Path(resolved).is_file():
            return resolved
    return None


def resolve_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    has_mlx, _ = _has_mlx_whisper()
    if has_mlx:
        return "mlx"
    if _find_whisper_cli():
        return "whisper-cli"
    return "elevenlabs"


def _normalize_whisper_segments_to_scribe(
    raw: dict[str, Any],
    backend_name: str,
    fallback_lang: str | None = None,
) -> dict[str, Any]:
    """Normalize Whisper / mlx_whisper / whisper.cpp output into Scribe-compatible word-level JSON."""
    words: list[dict[str, Any]] = []
    segments_out: list[dict[str, Any]] = []
    raw_segments = raw.get("segments") or raw.get("transcription") or []
    full_text_parts: list[str] = []

    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        seg_text = str(seg.get("text") or "").strip()
        if seg_text:
            full_text_parts.append(seg_text)
        s_start = float(seg.get("start") if seg.get("start") is not None else (seg.get("offsets", {}).get("from", 0) / 1000.0))
        s_end = float(seg.get("end") if seg.get("end") is not None else (seg.get("offsets", {}).get("to", 0) / 1000.0))
        segments_out.append({"start": round(s_start, 3), "end": round(s_end, 3), "text": seg_text})

        raw_words = seg.get("words") or seg.get("tokens") or []
        extracted_seg_words = 0
        for w in raw_words:
            if not isinstance(w, dict):
                continue
            w_txt = str(w.get("word") or w.get("text") or "").strip()
            if not w_txt or (w_txt.startswith("[_") and w_txt.endswith("]")):
                continue
            w_start = w.get("start")
            w_end = w.get("end")
            if w_start is None and isinstance(w.get("offsets"), dict):
                w_start = w["offsets"].get("from", 0) / 1000.0
                w_end = w["offsets"].get("to", 0) / 1000.0
            if w_start is not None and w_end is not None:
                words.append({
                    "text": w_txt,
                    "start": round(float(w_start), 3),
                    "end": round(float(w_end), 3),
                    "type": "word",
                })
                extracted_seg_words += 1

        if extracted_seg_words == 0 and seg_text:
            tokens = seg_text.split()
            dur = max(0.05, s_end - s_start)
            step = dur / max(1, len(tokens))
            for idx, tok in enumerate(tokens):
                words.append({
                    "text": tok,
                    "start": round(s_start + idx * step, 3),
                    "end": round(s_start + (idx + 1) * step, 3),
                    "type": "word",
                })

    text_val = str(raw.get("text") or " ".join(full_text_parts)).strip()
    lang_val = str(
        raw.get("language")
        or (raw.get("result") or {}).get("language")
        or fallback_lang
        or "auto"
    )
    return {
        "backend": backend_name,
        "language_code": lang_val,
        "text": text_val,
        "words": words,
        "segments": segments_out,
    }


def call_mlx_whisper(audio_path: Path, language: str | None = None, model: str = DEFAULT_MLX_MODEL) -> dict[str, Any]:
    has_mlx, mode = _has_mlx_whisper()
    if not has_mlx:
        raise RuntimeError(
            "Local `mlx_whisper` backend is not installed in the active runtime; use `--backend auto` or `--backend elevenlabs`."
        )
    if mode == "module":
        import mlx_whisper  # type: ignore[import-not-found]
        kwargs: dict[str, Any] = {"path_or_hf_repo": model, "word_timestamps": True}
        if language:
            kwargs["language"] = language
        raw = mlx_whisper.transcribe(str(audio_path), **kwargs)
        return _normalize_whisper_segments_to_scribe(raw, backend_name="mlx", fallback_lang=language)

    with tempfile.TemporaryDirectory(prefix="mlx_whisper_out_") as out_tmp:
        cmd = [mode, str(audio_path), "--model", model, "--output-format", "json", "--word-timestamps", "True", "--output-dir", out_tmp]
        if language:
            cmd.extend(["--language", language])
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
        json_out = Path(out_tmp) / f"{audio_path.stem}.json"
        raw = json.loads(json_out.read_text(encoding="utf-8"))
        return _normalize_whisper_segments_to_scribe(raw, backend_name="mlx", fallback_lang=language)


def call_whisper_cli(audio_path: Path, language: str | None = None, model_path: str | None = None) -> dict[str, Any]:
    cli = _find_whisper_cli()
    if not cli:
        raise RuntimeError(
            "Local `whisper-cli` (`whisper.cpp`) binary not found in PATH; use `--backend auto` or `--backend elevenlabs`."
        )
    resolved_model = (
        model_path
        or os.environ.get("WHISPER_CPP_MODEL")
        or next(
            (
                str(p)
                for p in (
                    Path.home() / ".cache/whisper/ggml-large-v3-turbo.bin",
                    Path.home() / ".cache/whisper/ggml-base.bin",
                    Path("/opt/homebrew/share/whisper-cpp/ggml-base.bin"),
                )
                if p.is_file()
            ),
            None,
        )
    )
    if not resolved_model:
        raise RuntimeError(
            "whisper-cli found, but no GGML model file located (set WHISPER_CPP_MODEL or pass --whisper-model)."
        )
    with tempfile.TemporaryDirectory(prefix="whisper_cli_out_") as out_tmp:
        out_prefix = Path(out_tmp) / "result"
        cmd = [cli, "-m", resolved_model, "-f", str(audio_path), "-ojf", "-of", str(out_prefix)]
        if language:
            cmd.extend(["-l", language])
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
        json_file = Path(f"{out_prefix}.json")
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        return _normalize_whisper_segments_to_scribe(raw, backend_name="whisper-cli", fallback_lang=language)


def transcript_path(edit_dir: Path, video: Path, audio_track: int = 0) -> Path:
    """Where a video's transcript lands.

    The track belongs in the name, or a rerun with --audio-track hands back the transcript of
    the track it is meant to replace. Track 0 keeps the plain name, so transcripts made before
    the flag existed stay valid. Batch mode tests its cache with this too — one function, so
    the two cannot drift apart.
    """
    suffix = "" if audio_track == 0 else f".track{audio_track}"
    return edit_dir / "transcripts" / f"{video.stem}{suffix}.json"


def transcribe_one(
    video: Path,
    edit_dir: Path,
    api_key: str | None = None,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
    audio_track: int = 0,
    backend: str = "elevenlabs",
    whisper_model: str | None = None,
) -> Path:
    """Transcribe a single video. Returns path to transcript JSON.

    Cached: returns existing path immediately if the transcript already exists.
    """
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcript_path(edit_dir, video, audio_track)

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path.name}")
        return out_path

    chosen_backend = resolve_backend(backend)
    if chosen_backend == "elevenlabs" and not api_key:
        api_key = load_api_key()

    if verbose:
        print(f"  extracting audio from {video.name} (backend={chosen_backend})", flush=True)

    n_tracks = count_audio_tracks(video)
    if n_tracks > 1 and verbose:
        print(f"  note: {video.name} has {n_tracks} audio tracks, using track "
              f"{audio_track + 1} (--audio-track to change)", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"{video.stem}.wav"
        extract_audio(video, audio, audio_track)

        peak = peak_dbfs(audio)
        if peak < -60.0:
            raise RuntimeError(
                f"track {audio_track + 1} of {video.name} is silent "
                f"(peak {peak:.1f} dBFS) - aborting transcription. "
                + (f"The file has {n_tracks} audio tracks; try --audio-track "
                   + " or ".join(str(i) for i in range(n_tracks) if i != audio_track) + "."
                   if n_tracks > 1 else "Check the source audio.")
            )

        size_mb = audio.stat().st_size / (1024 * 1024)
        if chosen_backend == "mlx":
            if verbose:
                print(f"  transcribing locally via mlx_whisper ({size_mb:.1f} MB)", flush=True)
            payload = call_mlx_whisper(audio, language=language, model=whisper_model or DEFAULT_MLX_MODEL)
        elif chosen_backend == "whisper-cli":
            if verbose:
                print(f"  transcribing locally via whisper-cli ({size_mb:.1f} MB)", flush=True)
            payload = call_whisper_cli(audio, language=language, model_path=whisper_model)
        else:
            if verbose:
                print(f"  uploading {video.stem}.wav ({size_mb:.1f} MB) to ElevenLabs Scribe", flush=True)
            payload = call_scribe(audio, api_key or "", language, num_speakers)

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path.name} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Transcribe a video via offline Apple Silicon (mlx_whisper / whisper-cli) or ElevenLabs Scribe"
    )
    ap.add_argument("video", type=Path, help="Path to video file")
    ap.add_argument(
        "--backend",
        choices=["auto", "mlx", "whisper-cli", "elevenlabs"],
        default="auto",
        help="Transcription backend: auto (prefer local mlx_whisper -> whisper-cli -> elevenlabs), mlx, whisper-cli, or elevenlabs",
    )
    ap.add_argument(
        "--whisper-model",
        type=str,
        default=None,
        help="Optional HuggingFace repo for mlx_whisper or GGML model path for whisper-cli",
    )
    ap.add_argument(
        "--edit-dir",
        type=Path,
        default=None,
        help="Edit output directory (default: <video_parent>/edit)",
    )
    ap.add_argument(
        "--language",
        type=str,
        default=None,
        help="Optional ISO language code (e.g., 'en', 'zh'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Optional number of speakers when known (ElevenLabs Scribe diarization).",
    )
    ap.add_argument(
        "--audio-track",
        type=int,
        default=0,
        help="Zero-based audio track to transcribe. OBS writes the game on track 0 "
             "and the mic on track 1; without this ffmpeg applies its default audio "
             "stream selection, which picks the track with the most channels.",
    )
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.exists():
        sys.exit(f"video not found: {video}")

    edit_dir = (args.edit_dir or (video.parent / "edit")).resolve()
    chosen = resolve_backend(args.backend)
    api_key = load_api_key() if chosen == "elevenlabs" else None

    transcribe_one(
        video=video,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
        audio_track=args.audio_track,
        backend=chosen,
        whisper_model=args.whisper_model,
    )


if __name__ == "__main__":
    main()
