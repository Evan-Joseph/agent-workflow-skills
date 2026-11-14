---
name: awesome-ppt
description: "用于图片模型渲染式 PPT 制作与可编辑重构。Use when the user invokes $awesome-ppt, asks to make polished slides/decks via gpt-image/imagegen, needs a PPTX assembled from rendered slide images, or explicitly requests editable PPT reconstruction."
metadata:
  short-description: 图片模型生成PPT与原生可编辑重构工作流
---

# Awesome PPT

通过「叙事规划 -> 逐页完整文案生图 -> PPTX 组装 ->（可选）原生可编辑重构」生成高质感演示文稿。

## 运行时契约 (Runtime Contract)

- 固定使用 `python3`（`miniconda-agent-general`，预装 `python-pptx`、`Pillow`、`playwright`），严禁自建 `venv` 或执行 `pip install`。
- 图像生成底层统一复用 `$HOME/.agents/skills/image-generation/scripts/grsai_generate.py`（批量生图前先估算张数获用户确认）。

## 模式与参数契约

```text
$awesome-ppt-std <prompt> [--pages N] [--ratio 16:9|4:3|1:1] [--lang zh|en] [--style "..."] [--out deck.pptx]
$awesome-ppt-editable <prompt> [--pages N] [--ratio 16:9|4:3|1:1] [--lang zh|en] [--style "..."] [--out deck.pptx]
```

- **`$awesome-ppt-std`（默认标准模式）**：每页可见标题、正文、标签完整写入 `rendered_text` 与生图 Prompt，由图像模型一次性渲染整页画面并组装为 `.pptx`（禁止生成空白底图后靠文本框凑主内容）。
- **`$awesome-ppt-editable`（可编辑重构模式）**：**必须先完成标准图片版 PPTX**，再调用 `export_ppt_master_handoff.py` / `html_slides_to_pptx.py` 重建原生可编辑形状与文本节点，并用 `inspect_pptx_package.py` 校验页数、原生文本节点与配色。
- 指定 `--pages N` 时，最终 `slide_count`、图片张数与 PPT 页数必须严格等于 `N`（未指定时默认按叙事推断，缺省 `8` 页）。

## 标准执行流水线

1. **素材盘点与风格匹配**：提取源材料核心论点与数据；查阅 [`references/theme-style-prompt-library.md`](./references/theme-style-prompt-library.md) 选定最贴合受众的视觉基调（用户显式指定 `--style` 时以用户为准）。
2. **编写 `deck.json` 与生图 Prompt**：按 [`references/slide-spec-schema.md`](./references/slide-spec-schema.md) 与 [`references/image-prompting.md`](./references/image-prompting.md) 为每页定义完整精确的 `rendered_text`（单页文案精炼，过密拆页而非缩字；严格合规/财务精确表格场景提前说明不适用纯生图模式）。
3. **生图与逐页文字核验**：输出至 `awesome-ppt-output/<slug>/images/slide-XX.png`；若标题或汉字存在错漏乱码，收紧 Prompt 单页重绘后再组装。
4. **校验、组装与受众视角审图（必做）**：
   ```bash
   PY=python3
   SKILL=$HOME/.agents/skills/awesome-ppt
   $PY $SKILL/scripts/validate_deck.py awesome-ppt-output/my-deck/deck.json
   $PY $SKILL/scripts/build_deck.py awesome-ppt-output/my-deck/deck.json --out awesome-ppt-output/my-deck/my-deck.pptx
   ```
   导出 `<150 KB` JPEG 缩略图并亲自调 `read_file` 逐页审视，确认零边缘裁切、零中文乱码与留白均衡。
5. **可编辑重构（仅 `$awesome-ppt-editable` 或显式 `--editable` 时执行）**：
   - 参阅 [`references/editability-policy.md`](./references/editability-policy.md) 与 [`references/ppt-master-integration.md`](./references/ppt-master-integration.md)，在全新重构目录运行（禁复用旧缓存）：
   ```bash
   $PY $SKILL/scripts/export_ppt_master_handoff.py awesome-ppt-output/my-deck/deck.json
   $PY $SKILL/scripts/html_slides_to_pptx.py slides.html --out awesome-ppt-output/my-deck/my-deck-editable.pptx
   $PY $SKILL/scripts/inspect_pptx_package.py awesome-ppt-output/my-deck/my-deck-editable.pptx --expect-slides 8 --expect-native-text
   ```
- **模板克隆扩展**：当用户要求克隆既有 `.pptx` 模板或使用 `gpt-image2-ppt` 子流时，先读 [`references/components/gpt-image2-ppt/guide.md`](./references/components/gpt-image2-ppt/guide.md)。
