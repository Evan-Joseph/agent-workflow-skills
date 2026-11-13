---
name: awesome-ppt
description: "用于图片模型渲染式 PPT 制作。Use when the user invokes $awesome-ppt, asks to make polished slides/decks via gpt-image/imagegen, needs a PPTX assembled from rendered slide images, or explicitly requests editable PPT reconstruction."
metadata:
  short-description: 图片模型生成PPT工作流
---

# Awesome PPT

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时，包含 `python-pptx`, `Pillow` 等）。
- **执行命令范例与环境自检**：
  ```bash
  python3 -c "import pptx; print('ppt runtime ok')"
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **模板克隆与依赖降级**：模板克隆路径依赖 `python-pptx` 读取 `.pptx` 元数据；缺少依赖时以 `status=degraded` 明确记录，严禁将降级画像冒充完整克隆。

## Overview

Build a PPTX by planning the deck, generating one complete slide image per page with `imagegen`, then assembling those rendered slide images into PowerPoint.

V1 is image-model-first: every visible title, subtitle, bullet, label, caption, and callout must be included verbatim in the image prompt and rendered by the image model. Do not create a blank/background image and add the main content later as PowerPoint text.

The first assembled PPTX is editable at the slide/image object level. Native editable text overlays are optional helper layers only; they are not the source of visible content in the default image-first workflow.

When the user wants a fully editable deck, prefer the `$awesome-ppt-editable` command. It runs the editable reconstruction pass after the image-first PPTX is built. `scripts/export_ppt_master_handoff.py` exports a standalone editable handoff bundle (`ppt-master-brief.md`, `ppt-master-request.md`, and reference `images/`) using the Grsai gpt-image-2 slide images as visual references and `rendered_text` as the exact editable content source. This standalone bundle can be reconstructed directly into a native editable `.pptx` via `python-pptx` in `python3` without requiring a separate `$ppt-master` skill directory (while remaining compatible with `ppt-master` SVG scripts if installed). Do not claim that raster screenshots are automatically or losslessly converted into editable objects.

Do not skip the image generation stage for an editable request. The correct full flow is: select the theme style prompt, write per-slide content/style/layout image prompts, generate slide images, build the image-first PPTX, then run the `ppt-master` editable reconstruction pass.

## Command Shape

Accept free-form prompts after the skill name:

```text
$awesome-ppt-std <deck prompt> [--pages N] [--ratio 16:9|4:3|1:1] [--lang zh|en|...] [--style "..."] [--out deck.pptx]
$awesome-ppt-editable <deck prompt> [--pages N] [--ratio 16:9|4:3|1:1] [--lang zh|en|...] [--style "..."] [--out deck.pptx]
$awesome-ppt <deck prompt> [--pages N] [--ratio 16:9|4:3|1:1] [--lang zh|en|...] [--style "..."] [--editable] [--out deck.pptx]
```

Command modes:

- `$awesome-ppt-std`: stable standard mode. Generate images and assemble the image-first PPTX. Never run `ppt-master`.
- `$awesome-ppt-editable`: experimental editable mode. Always complete standard mode first, then run the `ppt-master` native editable reconstruction pass.
- `$awesome-ppt`: legacy compatibility mode. Default to standard mode; run editable mode only when the user supplies `--editable`, `--native`, "fully editable", or "ppt-master".

Parameters:

- `--pages N`: requested slide count. If missing, infer from the narrative; default to 8 when the request is underspecified.
- `--ratio`: slide aspect ratio. Default to `16:9`.
- `--lang`: deck language. Infer from the user prompt when missing.
- `--style`: visual direction, brand mood, or reference style.
- `--editable` / `--native`: legacy `$awesome-ppt` option. Prefer `$awesome-ppt-editable` for explicit editable runs.
- `--out`: output PPTX path. Default to a descriptive slug in the working directory.

If `--pages N` is supplied, the final `slide_count`, number of generated images, and number of PPT slides must all equal `N`.

## Workflow

1. Parse the request and options. Identify audience, goal, language, slide count, ratio, visual tone, output path, and attached/source files.
2. Inspect source files before planning. Extract only the content that supports the deck: thesis, evidence, quotes, data, images, brand assets, and constraints.
3. Identify the closest theme style from the user's topic, audience, and requested mood. Read `references/theme-style-prompt-library.md`, select the nearest style prompt, then adapt it to the user's specific request instead of copying it mechanically.
4. Create a compact deck brief with `slide_count`, narrative arc, selected theme style, adapted design system, content density, and image text-rendering policy.
5. Create one slide spec per slide using `references/slide-spec-schema.md`.
6. For every slide, define `rendered_text`: the complete visible text that must appear inside the generated image.
7. For every slide, write an `imagegen` prompt from `references/image-prompting.md`. The prompt must include every `rendered_text` item verbatim, plus layout instructions for where each text item appears and the adapted theme style.
8. Generate slide images with the `imagegen` skill/tool. Save each final slide image into a project-local folder such as `awesome-ppt-output/<deck-slug>/images/`.
9. Inspect generated images for text fidelity. If title/body text is missing, misspelled, or replaced with gibberish, regenerate that slide with a tighter prompt before assembling the deck.
10. Run `scripts/validate_deck.py` against the deck spec before building.
11. Run `scripts/build_deck.py` to create the image-first PPTX.
12. Render-check the result by exporting slides to `<150KB` JPEG thumbnails and inspecting every slide via `read_file` (Multimodal Eyes-On Gate) to verify zero right-edge overflow (`scrollWidth <= clientWidth`), zero garbled Chinese characters, and balanced whitespace before delivery.
13. If mode is editable, or legacy `$awesome-ppt` received `--editable`, `--native`, "fully editable", or "ppt-master": run `scripts/export_ppt_master_handoff.py` against `deck.json`. The exported `ppt-master-handoff/` directory is a standalone editable handoff bundle that can be reconstructed directly with `python-pptx` (via `python3`) without requiring a separate `$ppt-master` skill directory, or passed to `ppt-master` if present. Treat this as a second-stage optimization after the pure image-first PPTX exists; never substitute a direct SVG-only build for the image-first deck.
14. Run the editable reconstruction in a fresh rebuild folder. Do not reuse an old `svg_output/`, `svg_final/`, or previous exported PPTX when testing a new deck.
15. After exporting the editable PPTX, run `scripts/inspect_pptx_package.py` on the native PPTX. For decks that should be fully native, verify the expected slide count, native text nodes, low or zero full-slide media usage, required text strings, and no unexpected black fallback colors.

## Planning Rules

- Start from the story, not the image prompts. Each slide needs one job and one dominant read.
- Always identify the user's presentation theme before writing slide specs. Use `references/theme-style-prompt-library.md` as a style baseline, but optimize it for the specific audience, topic, language, and constraints.
- If the user gives an explicit style, it wins over automatic theme matching. Use the library only to sharpen palette, layout, typography, and visual vocabulary.
- Use `--pages` as a hard constraint. If the requested content cannot fit, ask before changing the page count.
- Keep slide text short enough for the image model to render accurately. Split crowded slides instead of shrinking text.
- Put all visible content text into `rendered_text` and the image prompt.
- Keep `rendered_text` exact and complete because it becomes the source text for the `ppt-master` editable reconstruction pass.
- Use `editable_text` only when explicitly requested as an auxiliary mirror layer for later manual editing. Do not use it to supply missing visible content after image generation.
- For charts and tables, include the exact visible labels/values in `rendered_text` and the image prompt. Avoid dense spreadsheet-like tables in v1 because rendered text fidelity becomes the bottleneck.
- If exact legal, financial, or compliance text must be perfectly editable and auditable, pause and explain that the image-first workflow is the wrong default for that slide.

## File Outputs

Recommended run folder:

```text
awesome-ppt-output/<deck-slug>/
  deck.json
  images/
    slide-01.png
    slide-02.png
  <deck-slug>.pptx
  ppt-master-handoff/
    ppt-master-brief.md
    ppt-master-request.md
    images/
      slide-01.png
  ppt-master-rebuild/
  <deck-slug>-editable.pptx
```

The `deck.json` file is the source of truth for assembly. Use relative image paths from the JSON file location when possible.

The `ppt-master-handoff/`, `ppt-master-rebuild/`, and editable PPTX output are created only when running `$awesome-ppt-editable` or legacy `$awesome-ppt --editable`. The handoff is the source package for `ppt-master`; it should preserve reference images and exact text so `ppt-master` can rebuild the deck as native editable elements.

## Scripts

- `scripts/validate_deck.py`: validate slide count, required fields, `rendered_text`, prompt coverage, image existence, and image aspect ratios.
- `scripts/build_deck.py`: assemble a PPTX from a validated `deck.json`. The standard-library v1 builder writes one full-slide image per slide and can optionally add editable text boxes if `editable_text` is present.
- `scripts/export_ppt_master_handoff.py`: export a standalone editable reconstruction handoff bundle (`ppt-master-brief.md`, `ppt-master-request.md`, and reference `images/`) from `deck.json`. It can be reconstructed directly via `python-pptx` in the managed Miniconda runtime without requiring a separate `$ppt-master` skill directory.
- `scripts/html_slides_to_pptx.py`: deterministic HTML/JSON slide geometry -> native editable `python-pptx` converter (measures real DOM bounding boxes via headless Playwright or reads structured slide geometry JSON and maps text/cards/shapes/images 1:1 into editable PPTX shapes).
- `scripts/inspect_pptx_package.py`: inspect a PPTX package for slide count, media count, native text nodes, required text, and suspicious black fallback colors.
- `scripts/requirements.txt`: reserved for future optional Python dependencies. V1 scripts use only the Python standard library.

No dependency installation is required for the image-first v1 path. If future
optional dependencies are added, first register a managed runtime in
`~/.agents/config/python-runtimes.json`; do not install them into
whichever `python` happens to be on `PATH`.

```bash
python3 -c "import sys; print(sys.version)"
```

Validate and build:

```bash
python3 $HOME/.agents/skills/awesome-ppt/scripts/validate_deck.py awesome-ppt-output/my-deck/deck.json
python3 $HOME/.agents/skills/awesome-ppt/scripts/build_deck.py awesome-ppt-output/my-deck/deck.json --out awesome-ppt-output/my-deck/my-deck.pptx
python3 $HOME/.agents/skills/awesome-ppt/scripts/export_ppt_master_handoff.py awesome-ppt-output/my-deck/deck.json
python3 $HOME/.agents/skills/awesome-ppt/scripts/html_slides_to_pptx.py slides.html --out awesome-ppt-output/my-deck/my-deck-editable.pptx
python3 $HOME/.agents/skills/awesome-ppt/scripts/inspect_pptx_package.py awesome-ppt-output/my-deck/my-deck-editable.pptx --expect-slides 5 --expect-native-text --require-text "Transformer"
```

## References

- Read `references/slide-spec-schema.md` before creating `deck.json`.
- Read `references/theme-style-prompt-library.md` before creating the deck brief or image prompts.
- Read `references/image-prompting.md` before generating slide images.
- Read `references/editability-policy.md` when deciding whether any optional editable helper layer is appropriate.
- Read `references/ppt-master-integration.md` before running the editable reconstruction optimization.

## Integrated Backend Mode

The default owner is `awesome-ppt`. When the user explicitly requires the
gpt-image-2/Grsai backend, the imported template-clone workflow, or the legacy
`gpt-image2-ppt` commands, first read
`references/components/gpt-image2-ppt/guide.md`. Its `references/components/gpt-image2-ppt/scripts/image_generator.py`
delegates Grsai generation directly to canonical
`$HOME/.agents/skills/image-generation/scripts/grsai_generate.py`, and
`references/components/gpt-image2-ppt/scripts/template_analyzer.py` routes template vision analysis through local
MagPie `${OPENAI_COMPAT_BASE_URL}` (`group/carbon`). Do not create a second PPT
Skill or install dependencies into system Python. Keep the image-first deck
contract above as the shared acceptance gate.
