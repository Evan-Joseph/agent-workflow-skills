# gpt-image2-ppt Workflow

本文件在用户确认要生成 PPT、需要写 slides plan、运行脚本、输出 HTML viewer/PPTX 或只生成部分页时读取。

## Skill 调用规范

当用户说“做一份 PPT”“生成幻灯片”“slides”“deck”时：

1. 先问三件事，不直接动手：
   - 内容、页数、观众是谁。
   - 风格偏好：按 `references/styles.md` 推荐 1-2 个，或使用用户上传的 `.pptx` 模板。
   - 是否需要先生成 1 页做冒烟测试。
2. 先写 `slides_plan.md` 给用户确认文案。Markdown 是 source of truth，方便 review 和 diff。
3. 用户确认后转 `slides_plan.json`：

```bash
python3 scripts/md_to_plan.py slides_plan.md -o slides_plan.json
```

4. 选择风格文件或模板克隆模式。
5. 先 `--slides 1` 出封面冒烟，效果 OK 后再跑全量。
6. 告知用户产物路径：`outputs/<timestamp>/index.html` 和 `<title>.pptx`。

## Slides Plan Markdown

示例：

```markdown
---
title: MediWise Health Suite 商业计划书
---

## 1. [cover] MediWise Health Suite
副标题：家庭健康管理智能平台
年份：2026

## 2. [content] 市场痛点：健康管理的两类割裂
痛点一：高频无深度
...

## 6. [data] 效率对比：使用 MediWise 前后
...
```

规则：

- H2 格式：`## N. [page_type, layout=layout-05] 本页标题行`。
- `N.` 可省，按出现顺序自动编号。
- `[page_type]` 可省，默认 `content`。
- `layout=` 只在模板克隆模式需要。
- `page_type` 支持 `cover`、`content`、`data`。
- H2 标题行会进入 JSON 的 `content` 第一行；下面正文进入正文。

## Built-In Style Flow

```bash
python3 scripts/generate_ppt.py --plan slides_plan.json --style styles/editorial-mono.md
```

产物位于 `<cwd>/outputs/<timestamp>/`：

- `images/slide-XX.png`：每页 PNG。
- `index.html`：HTML viewer，支持方向键翻页、空格自动播放、ESC 全屏。
- `prompts.json`：每页完整 prompt，便于复盘和二次微调。
- `<title>.pptx`：16:9 整页填充图片的 PPTX。

## Native image_generation Flow

如果当前 Agent 自带 `image_generation` tool，并且不需要手动配置 API key 就能出图，优先走原生路径。

流程：

1. 准备 `slides_plan.md` 和 `slides_plan.json`。
2. 读取 `styles/<id>.md` 的基础提示词模板。
3. 按页构造 prompt，强制 16:9 横版、简体中文和清晰字体。
4. 调用 `image_generation` 生成每页 PNG，保存到 `outputs/<timestamp>/images/slide-NN.png`。
5. 读取 `templates/viewer.html`，替换图片列表，写入 `outputs/<timestamp>/index.html`。
6. 需要 PPTX 时，用 `python-pptx` 将图片逐页填充到 16:9 幻灯片。

## Partial Generation

只生成部分页：

```bash
python3 scripts/generate_ppt.py --plan my_plan.json --style styles/dark-aurora.md --slides 1,3,5
```

同名 PNG 已存在时会自动跳过，方便逐页迭代。

## Runtime Outputs

调用时产生的运行时目录都在调用者当前工作区下：

```text
<your-project>/
|-- template_renders/<stem>/page-NN.png
|-- template_cache/<sha256>.json
`-- outputs/<timestamp>/
```

建议把 `template_renders/`、`template_cache/`、`outputs/` 加入项目 `.gitignore`。
