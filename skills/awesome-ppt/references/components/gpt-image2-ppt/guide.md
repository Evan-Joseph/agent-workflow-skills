---
name: gpt-image2-ppt
description: "用于明确指定 gpt-image-2、Grsai、图片模型后端或模板克隆方式生成图片式 PPT。普通 PPT/幻灯片制作默认先用 awesome-ppt；需要本 Skill 的脚本、后端环境或模板缓存时再使用。"
metadata:
  short-description: gpt-image-2图片式PPT后端
---

# gpt-image2-ppt

把 Markdown 大纲或 `slides_plan.json` 加一种视觉风格，生成每页 PNG，再拼成键盘可翻页的 HTML viewer 和 16:9 PPTX。支持内置风格、用户 PPTX 模板克隆、原生 `image_generation`、Grsai/OpenAI 兼容 API 和 Codex CLI 后端。

## Runtime Contract

- 本机脚本固定使用 `python3`；依赖合同由 `~/.agents/config/python-runtimes.json` 审计。
- 缺少解释器或核心模块时停止并报告具体缺项，不向系统 Python 安装包，也不为单次任务创建临时 venv。
- 模板分析结果带有 status 字段：ok 表示 pptx 元数据和图片分析均可用；degraded 或 incomplete 表示只完成部分分析。template-strict 下不得接受后两种状态。
- 模板视觉分析（`scripts/template_analyzer.py`）默认走本机唯一模型网关 MagPie `${OPENAI_COMPAT_BASE_URL}`（`group/carbon`，自动读取 `~/.agents/config/magpie-ops-probe.json` 或 `VISION_*` 环境变量）；Grsai 图像生成（`scripts/image_generator.py`）直接委托复用 `$HOME/.agents/skills/image-generation/scripts/grsai_generate.py`。

## Boundary

普通“帮我做 PPT / slides / deck”默认先走 `awesome-ppt`，由它确定叙事、视觉和是否需要可编辑重建。本 Skill 是图片式 PPT 的专项后端入口，只在这些情况下直接使用：

- 用户明确点名 `gpt-image-2`、Grsai、OpenAI 兼容图片生成后端或本 Skill。
- 需要复用本 Skill 的 `slides_plan.md`/`slides_plan.json`、内置 styles、模板克隆缓存或批量生成脚本。
- 已有 `awesome-ppt` 规划结果，需要用这里的后端脚本执行生成或复跑局部页面。

不要把本 Skill 当成所有 PPT 请求的默认 owner。若用户要求 fully editable、母版、原生文本框、复杂图表或正式模板精修，优先转 `presentations`、Office 工作流或 `awesome-ppt` 的 editable 路线。

默认凭据不放在 Skill 目录。脚本优先读取私有文件
`~/.config/gpt-image2-ppt/gpt-image2-ppt.env`，并可回退到
`~/.config/grsai/grsai.env`。

## When To Use

当用户要求：

- 明确用 `gpt-image-2`、Grsai 或图片模型后端做一份 PPT、幻灯片、slides、deck。
- 把大纲、报告、课程材料、商业计划或技术方案转成可展示的幻灯片。
- 用本 Skill 的脚本渲染整页 PPT。
- 复用已有 `.pptx` 模板的视觉风格。

不要用于需要全量可编辑文本框、母版、动画和复杂原生图表的精修 PPT；这种场景优先用 `presentations` 或 `office-docx`/Office 工作流。

## First Questions

开始前先确认三件事：

1. 内容、页数、观众是谁。
2. 风格偏好：按 [references/styles.md](references/styles.md) 推荐 1-2 个，或使用用户上传的 `.pptx` 模板。
3. 是否需要先生成 1 页做效果测试。

## Core Flow

1. 写 `slides_plan.md` 给用户确认文案；Markdown 是 source of truth。
2. 用户确认后转 `slides_plan.json`：

```bash
python3 scripts/md_to_plan.py slides_plan.md -o slides_plan.json
```

3. 选择内置风格或模板克隆路径。
4. 先跑 `--slides 1` 冒烟。
5. 效果 OK 后跑全量，产物放在 `<cwd>/outputs/<timestamp>/`。
6. 交付 `index.html` 和 `<title>.pptx` 路径。

完整生成流程、slides plan 语法、原生 `image_generation` 路径和部分页生成见 [references/workflow.md](references/workflow.md)。

## Reference Routing

- 风格选择、10 套内置风格和 prompt 构造：读 [references/styles.md](references/styles.md)。
- 原生 `image_generation`、Grsai/OpenAI API、Codex CLI 后端和环境变量：读 [references/backends-and-env.md](references/backends-and-env.md)。
- `slides_plan.md`、生成命令、产物目录、HTML viewer 和 PPTX 输出：读 [references/workflow.md](references/workflow.md)。
- `.pptx` 模板渲染、template cache、layout 选择和复用检测：读 [references/template-clone.md](references/template-clone.md)。

## Built-In Style Command

```bash
python3 scripts/generate_ppt.py --plan slides_plan.json --style styles/editorial-mono.md
```

只生成部分页：

```bash
python3 scripts/generate_ppt.py --plan slides_plan.json --style styles/dark-aurora.md --slides 1,3,5
```

## Template Clone Command

```bash
python3 scripts/generate_ppt.py \
  --plan slides_plan.json \
  --template-pptx ./company-template.pptx \
  --template-strict --slides 1
```

## Output Contract

最终交付时说明：

- `outputs/<timestamp>/index.html`：可翻页 HTML viewer。
- `outputs/<timestamp>/<title>.pptx`：16:9 整页图片 PPTX。
- `outputs/<timestamp>/images/slide-XX.png`：每页 PNG。
- `outputs/<timestamp>/prompts.json`：每页 prompt，便于复盘和二次微调。

License: Apache License 2.0.
