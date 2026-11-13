#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpt-image-2 图片生成器（统一委托复用 image-generation/scripts/grsai_generate.py 核心逻辑）

默认优先复用 `$HOME/.agents/skills/image-generation/scripts/grsai_generate.py`
的凭据加载、自动画质档位、POST /v1/api/generate 与异步轮询逻辑，消除两套 Grsai 客户端双头维护；
当显式指定 `GPT_IMAGE_ENDPOINT=images|chat` 时，仍兼容标准 OpenAI Images / Chat Completions 接口。
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import struct
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

GRSAI_CORE_PATH = Path("~/.agents/skills/image-generation/scripts/grsai_generate.py").expanduser()


def _load_grsai_core():
    if not GRSAI_CORE_PATH.is_file():
        raise RuntimeError(f"Missing canonical Grsai helper: {GRSAI_CORE_PATH}")
    spec = importlib.util.spec_from_file_location("_canonical_grsai_generate", GRSAI_CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load canonical Grsai helper: {GRSAI_CORE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_grsai_core = _load_grsai_core()

ASPECT_TO_SIZE = {
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "1:1": "1024x1024",
}

REQUEST_TIMEOUT_SECS = 600
MAX_RETRIES = 3
RETRY_DELAY_SECS = 5
MAX_ASPECT_RETRIES = 2
ASPECT_TOLERANCE = 0.15

ASPECT_RATIO_VALUES = {
    "16:9": 16 / 9,
    "9:16": 9 / 16,
    "1:1": 1.0,
}


def read_png_dimensions(path: str) -> tuple[int, int]:
    """从 PNG header 读宽高，不依赖 PIL。失败返回 (0, 0)。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return 0, 0
        width, height = struct.unpack(">II", head[16:24])
        return width, height
    except Exception:
        return 0, 0


def aspect_acceptable(width: int, height: int, target: str, tolerance: float = ASPECT_TOLERANCE) -> bool:
    """检查实际宽高比是否在目标比例的容差范围内。"""
    if not (width and height):
        return True
    expected = ASPECT_RATIO_VALUES.get(target)
    if expected is None:
        return True
    actual = width / height
    deviation = abs(actual - expected) / expected
    return deviation <= tolerance


class GptImage2Generator:
    """gpt-image-2 图片生成器（Grsai 通道直接委托复用 grsai_generate.py）。"""

    def __init__(self, aspect_ratio: str = "16:9") -> None:
        grsai_cfg = _grsai_core.load_config_file()
        raw_endpoint = os.getenv("GPT_IMAGE_ENDPOINT", "").strip().lower()
        explicit_base = (os.getenv("OPENAI_BASE_URL") or os.getenv("GRSAI_BASE_URL") or "").strip().rstrip("/")
        grsai_key = os.getenv("GRSAI_API_KEY") or grsai_cfg.get("GRSAI_API_KEY") or ""
        openai_key = os.getenv("OPENAI_API_KEY") or grsai_cfg.get("OPENAI_API_KEY") or ""

        if raw_endpoint == "grsai" or ("grsai" in explicit_base.lower()) or (not raw_endpoint and grsai_key and not explicit_base):
            self.endpoint = "grsai"
            self.base_url = explicit_base or _grsai_core.default_base_url().rstrip("/")
            self.api_key = grsai_key or openai_key
        else:
            self.endpoint = raw_endpoint or "auto"
            self.base_url = explicit_base or "https://api.openai.com"
            self.api_key = openai_key or grsai_key

        self.model_name = os.getenv("GPT_IMAGE_MODEL_NAME", "gpt-image-2")
        env_quality = os.getenv("GPT_IMAGE_QUALITY", "").strip()
        self.quality = _grsai_core.resolve_quality(self.model_name, env_quality) or "high"

        if not self.api_key:
            raise ValueError("缺少 GRSAI_API_KEY 或 OPENAI_API_KEY，请检查 ~/.config/grsai/grsai.env 或私有 env 配置")

        self.aspect_ratio = aspect_ratio
        self.default_size = ASPECT_TO_SIZE.get(aspect_ratio, "1536x1024")
        print(
            f"🎨 初始化 gpt-image-2 生成器 "
            f"(model={self.model_name}, size={self.default_size}, "
            f"quality={self.quality}, endpoint={self.endpoint})"
        )

    # ---------- 落盘辅助 ----------

    def _save_b64(self, b64: str, output_path: str) -> None:
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(b64))

    def _download_url(self, url: str, output_path: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"拒绝下载非 http(s) 协议的 URL: {parsed.scheme}")
        print(f"📥 下载图片 host={parsed.netloc} path={parsed.path[:80]}")
        resp = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_SECS)
        resp.raise_for_status()
        MAX_BYTES = 50 * 1024 * 1024
        written = 0
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_BYTES:
                    f.close()
                    os.remove(output_path)
                    raise ValueError(f"下载超过 {MAX_BYTES} 字节上限，已丢弃 {url[:80]}")
                f.write(chunk)

    def _save_payload(self, payload: str, output_path: str) -> None:
        if payload.startswith("data:image/") or (len(payload) > 200 and "/" not in payload[:200]):
            self._save_b64(payload, output_path)
        elif payload.startswith("http"):
            self._download_url(payload, output_path)
        else:
            self._save_b64(payload, output_path)

    # ---------- Grsai 委托通道（复用 image-generation/scripts/grsai_generate.py）----------

    def _grsai_aspect_ratio(self, size: str) -> str:
        if size and size not in ("auto", self.default_size) and "x" in size:
            return size
        return {
            "16:9": "3840x2160",
            "9:16": "2160x3840",
            "1:1": "2048x2048",
        }.get(self.aspect_ratio, self.aspect_ratio or "16:9")

    def _request_via_grsai(self, prompt: str, size: str, reference_image_path: Optional[str] = None) -> str:
        """委托调用 canonical grsai_generate.py 的请求、解包与轮询方法。"""
        base = self.base_url.rstrip("/")
        url = f"{base}/v1/api/generate"
        aspect_ratio = self._grsai_aspect_ratio(size)
        fallback_ratio = self.aspect_ratio or "16:9"
        images = [_grsai_core.image_arg(reference_image_path)] if (reference_image_path and os.path.exists(reference_image_path)) else []
        quality = _grsai_core.resolve_quality(self.model_name, os.getenv("GPT_IMAGE_QUALITY", "").strip()) or self.quality

        ratios_to_try = [aspect_ratio]
        if fallback_ratio and fallback_ratio != aspect_ratio:
            ratios_to_try.append(fallback_ratio)

        # 临时注入当前实例选定的 GRSAI_API_KEY 以确保与 find_and_load_env 作用域一致
        prev_key = os.environ.get("GRSAI_API_KEY")
        os.environ["GRSAI_API_KEY"] = self.api_key
        try:
            last_exc: Optional[BaseException] = None
            for idx, candidate_ratio in enumerate(ratios_to_try):
                payload: Dict[str, Any] = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "images": images,
                    "aspectRatio": candidate_ratio,
                    "replyType": "json",
                }
                if quality:
                    payload["quality"] = quality

                print(f"🔗 [grsai_generate core] POST {url} aspectRatio={candidate_ratio} quality={quality} refs={len(images)}")
                try:
                    data = _grsai_core.request_json("POST", url, json=payload)
                    status = str(data.get("status") or "").lower()
                    if (
                        status in {"running", "pending", "processing", "queued"}
                        or (data.get("id") and not _grsai_core.extract_urls(data) and status not in {"failed", "violation"})
                    ):
                        task_id = data.get("id")
                        if not task_id:
                            raise RuntimeError(f"grsai 异步响应缺少 id: {str(data)[:300]}")
                        data = _grsai_core.poll(base, str(task_id), interval=3.0, timeout=float(REQUEST_TIMEOUT_SECS))
                        status = str(data.get("status") or "").lower()
                    if status in {"failed", "violation"}:
                        raise RuntimeError(f"grsai 任务失败 ({status}): {str(data)[:300]}")
                    urls = _grsai_core.extract_urls(data)
                    if not urls:
                        raise RuntimeError(f"grsai 未返回图片 URL: {str(data)[:300]}")
                    return urls[0]
                except BaseException as exc:
                    last_exc = exc
                    if idx + 1 < len(ratios_to_try):
                        print(f"(!) grsai aspectRatio={candidate_ratio} 失败 ({str(exc)[:140]})，回退 {ratios_to_try[idx + 1]}")
                        continue
                    raise RuntimeError(f"grsai 调用失败: {exc}") from exc
            raise RuntimeError(f"grsai 调用失败: {last_exc}")
        finally:
            if prev_key is None:
                os.environ.pop("GRSAI_API_KEY", None)
            else:
                os.environ["GRSAI_API_KEY"] = prev_key

    # ---------- 兼容端点: /v1/images/generations & /v1/chat/completions ----------

    def _extract_from_text(self, text: str) -> Optional[str]:
        for pat, grp in (
            (r"data:image/[\w]+;base64,[A-Za-z0-9+/=]+", 0),
            (r"!\[.*?\]\((https?://[^\)\s]+)\)", 1),
            (r"(https?://[^\s\)]+\.(?:png|jpg|jpeg|webp|gif))", 1),
            (r"(https?://[^\s\)]+)", 1),
        ):
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(grp)
        return None

    def _request_via_images(self, prompt: str, size: str) -> str:
        url = f"{self.base_url}/v1/images/generations"
        payload = {"model": self.model_name, "prompt": prompt, "n": 1, "size": size, "quality": self.quality}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECS)
        if resp.status_code != 200:
            raise RuntimeError(f"images 调用失败 (status={resp.status_code}): {resp.text[:500]}")
        data = (resp.json().get("data") or [{}])[0]
        if data.get("b64_json"):
            return f"data:image/png;base64,{data['b64_json']}"
        if data.get("url"):
            return data["url"]
        raise RuntimeError(f"images 响应缺少 b64_json/url: {str(data)[:300]}")

    def _request_via_chat(self, prompt: str, size: str, reference_image_path: Optional[str] = None) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        aspect_hint = (
            "\n\n【画面比例 -- 强制】严格按 9:16 竖版生成。"
            if self.aspect_ratio == "9:16"
            else ("\n\n【画面比例 -- 强制】1:1 方图。" if self.aspect_ratio == "1:1" else "\n\n【画面比例 -- 强制】16:9 横版宽屏。")
        )
        full_prompt = f"{prompt}{aspect_hint}"
        if reference_image_path and os.path.exists(reference_image_path):
            ref_data_url = _grsai_core.image_arg(reference_image_path)
            user_content: Any = [
                {"type": "image_url", "image_url": {"url": ref_data_url}},
                {"type": "text", "text": "请以上图作为视觉风格参考生成全新 PPT 页，不复制原图文字。\n\n" + full_prompt},
            ]
        else:
            user_content = full_prompt
        payload = {"model": self.model_name, "messages": [{"role": "user", "content": user_content}], "stream": True, "temperature": 0.7}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=REQUEST_TIMEOUT_SECS)
        if resp.status_code != 200:
            raise RuntimeError(f"chat 调用失败 (status={resp.status_code}): {resp.text[:500]}")
        chunks = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                obj = json.loads(data_str)
            except Exception:
                continue
            choices = obj.get("choices") or []
            if choices:
                delta_c = (choices[0].get("delta") or {}).get("content")
                if delta_c:
                    chunks.append(delta_c)
        merged = "".join(chunks)
        found = self._extract_from_text(merged)
        if not found:
            raise RuntimeError(f"流式响应未找到图片 URL/base64：{merged[:300]}")
        return found

    # ---------- 对外入口 ----------

    def generate_scene_image(
        self,
        scene_data: Dict[str, Any],
        output_path: str,
        size: str = "auto",
        reference_image_path: Optional[str] = None,
    ) -> str:
        scene_index = scene_data.get("index", 0)
        prompt = scene_data.get("image_prompt", "")
        if not prompt:
            raise ValueError(f"场景 {scene_index} 缺少 image_prompt")

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        target_size = self.default_size if size == "auto" else size
        for ratio_attempt in range(MAX_ASPECT_RETRIES + 1):
            last_err = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    if self.endpoint == "grsai":
                        payload = self._request_via_grsai(prompt, target_size, reference_image_path)
                    elif self.endpoint == "images":
                        payload = (
                            self._request_via_chat(prompt, target_size, reference_image_path)
                            if reference_image_path
                            else self._request_via_images(prompt, target_size)
                        )
                    elif self.endpoint == "chat":
                        payload = self._request_via_chat(prompt, target_size, reference_image_path)
                    else:
                        try:
                            payload = (
                                self._request_via_chat(prompt, target_size, reference_image_path)
                                if reference_image_path
                                else self._request_via_images(prompt, target_size)
                            )
                        except Exception:
                            payload = self._request_via_chat(prompt, target_size, reference_image_path)
                    self._save_payload(payload, output_path)
                    break
                except Exception as e:
                    last_err = e
                    msg = str(e)[:200]
                    transient = any(s in msg for s in ("524", "502", "503", "504", "timeout", "Read timed out", "Connection aborted", "RemoteDisconnected"))
                    if attempt < MAX_RETRIES and transient:
                        time.sleep(RETRY_DELAY_SECS)
                        continue
                    raise
            else:
                raise RuntimeError(f"重试 {MAX_RETRIES} 次仍失败: {last_err}")

            w, h = read_png_dimensions(output_path)
            if aspect_acceptable(w, h, self.aspect_ratio):
                print(f"[OK] 已保存: {output_path}  ({w}x{h})")
                return output_path
            if ratio_attempt < MAX_ASPECT_RETRIES:
                try:
                    os.remove(output_path)
                except OSError:
                    pass
                continue
            return output_path
        return output_path
