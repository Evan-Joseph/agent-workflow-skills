---
name: image-generation
description: "跨 Harness 的通用图像生成、编辑与本地位图处理中心。原生集成 Grsai API（支持 gpt-image-2, nano-banana 等模型），并包含本地 ImageMagick 格式转换/缩放与系统截图能力。在需要生图、配图、图像尺寸调整或截图取证时使用。"
metadata:
  short-description: AI图像生成、图像编辑与本地位图处理
---

# Image Generation & Processing

统一管理生图模型调用与本地位图处理流水线。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/image-generation/scripts/grsai_generate.py config
  python3 $HOME/.agents/skills/image-generation/scripts/grsai_generate.py generate --prompt "描述" --model gpt-image-2 --aspect-ratio "16:9" --prefix slide-01 --out-dir .
  ```
- **脚本入口职责划分**：
  - **主力入口 (`scripts/grsai_generate.py`)**：默认唯一优先通道，直连 Grsai `/v1/api/generate`，自动读取 `~/.config/grsai/grsai.env`（亦作为 `awesome-ppt` 内置 `image_generator.py` 委托复用的唯一生图真源）。
  - **兜底入口 (`scripts/generate.py`)**：仅当用户显式要求使用厂商直连 API Key（OpenAI `gpt-image-2`、Gemini `gemini-nano-banana-2.1` / `gemini-3-pro-image`、Volcengine Seedream、DashScope Qwen、MiniMax、LinkAI）且不走 Grsai 时作为回退使用。
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **Grsai 凭据与本地依赖**：自动读取 `~/.config/grsai/grsai.env`（`GRSAI_API_KEY` 与 `GRSAI_BASE_URL`，统一登记于 `~/.config/ai-relays/credentials.json` 的 `tool_apis.grsai` 指针台账），严禁在代码或输出中打印 Key；本地位图依赖 ImageMagick CLI (`magick`) 与 macOS 系统截图 (`screencapture`)。

## 1. AI 生图（Grsai 专职主力通道）

当前本机默认使用 `scripts/grsai_generate.py` 作为主力图像生成通道（`scripts/generate.py` 仅作厂商直连 Key 备选兜底）。

- **凭据位置**：`~/.config/grsai/grsai.env`（环境变量 `GRSAI_API_KEY` 与 `GRSAI_BASE_URL`）。
- **执行脚本**：
  ```bash
  # 检查凭据配置
  python3 $HOME/.agents/skills/image-generation/scripts/grsai_generate.py config

  # 执行生图（必须带 generate 子命令；多图连续生成务必指定 --prefix 防止覆盖 grsai-result-01.png）
  python3 $HOME/.agents/skills/image-generation/scripts/grsai_generate.py generate \
    --prompt "描述" --model gpt-image-2 --aspect-ratio "16:9" --prefix scene-01 --out-dir .
  ```
- **自动最高画质与防覆盖参数**：
  - **自动最高 `quality`**：Grsai 按次计费仅由**模型名称（`model`）**决定，分辨率（`aspectRatio`）与质量（`quality`）选项不影响计费。未显式传入 `--quality` 时，`grsai_generate.py` 会按模型自动填充最高档位（`gpt-image-2.5-sunburst` 自动设为 `"max"`，`gpt-image-2` / `gpt-image-2-symmetry` / `gpt-image-2.5*` 自动设为 `"high"`）。
  - **输出文件名前缀 (`--prefix`)**：默认值为 `grsai-result`（产出 `<out-dir>/<prefix>-01.png`）。在同一目录批量或多轮生图时，务必传入不同的 `--prefix`（如 `--prefix slide-01`），避免覆盖前序结果。
  - **多帧参考图一致性控制 (`--ref-image` / `--image` -> `images` / `image_urls`)**：制作多页 PPT、连续分镜或产品多角度渲染时，支持重复传入 `--ref-image <本地图片路径或URL>`（或 `--image`），脚本自动将本地图片编码为 `data:image/...;base64,...` 注入请求体 `images` 数组（`--dry-run` 时自动脱敏显示 `<data-url>`），锁死画风、角色与配色一致性：
    ```bash
    python3 $HOME/.agents/skills/image-generation/scripts/grsai_generate.py generate \
      --prompt "保持参考图极简几何视觉语言，绘制架构部署视图" \
      --ref-image ./slide-01.png --model gpt-image-2.5-sunburst --aspect-ratio "16:9" --prefix slide-02 --out-dir .
    ```
- **常用模型**：
  - `gpt-image-2.5-sunburst`（¥0.12/次）：支持 1K/2K/4K 分辨率（如 `2336x3504`、`2448x3264`、`3840x2160`）及 `max` 质量，适合极高精度排版与细节渲染。
  - `gpt-image-2.5-flare`（¥0.10/次）：支持 1K/2K/4K 分辨率及 `high` 质量。
  - `gpt-image-2.5` / `gpt-image-2`（¥0.03/次）：支持常见比例（16:9, 1:1, 4:3）或 1K，适合快速概念设计。
  - `gpt-image-2-vip`（¥0.10/次）：高分辨率模式（2048x2048, 3840x2160），适合海报、PPT 背景大图。
  - `nano-banana` / `nano-banana-fast`（¥0.022/次）：轻量超快速生图，适合草图、图标探索。

## 2. 本地位图转换 (ImageMagick)

涉及已落盘图片的格式转换、批处理、压缩或缩略图生成时，直接通过本地 CLI 处理：

```bash
# 格式与质量优化
magick input.png -quality 85 output.webp
# 尺寸缩放
magick input.png -resize 1200x800 output.png
# 批量缩图
mogrify -resize 50% *.jpg
# 纯色背景一键抠图转透明 PNG（图标/徽章/白底商品素材后处理，-fuzz 6%~12% 消除边缘抗锯齿白边）
magick input.png -alpha set -fuzz 8% -transparent "#FFFFFF" output_transparent.png
# 深色纯底转透明并自动裁切多余透明留白
magick input_dark.png -alpha set -fuzz 8% -transparent "#000000" -trim +repage icon_clean.png
```

## 3. 系统截图能力与防爆库铁律 (Screenshot & Anti-DB-Bloat Gate)

当任务明确需要对 macOS 窗口、桌面或无法直接抓取 DOM 的本地应用进行取证时：
- 调用系统自带的 `screencapture -x /tmp/raw_cap.png` 获取截图后，**严禁直接调用 `read_file` 读取数 MB 的 Retina 原始 PNG**（会永久写入 `conversations/*.db` 引发膨胀卡死）；必须先用 `magick /tmp/raw_cap.png -resize 1280x1280\> -quality 80 /tmp/cap_preview.jpg` 压缩至 `<150 KB` JPEG 再调用 `read_file` 审视，用毕即清 `/tmp/raw_cap.png`。
- 凡生成用于 GitHub README、论文插图或简历头像的图片，必须调用 `read_file` 目检确认无文案越界、无描边裁切溢出、无大片异常留白。
