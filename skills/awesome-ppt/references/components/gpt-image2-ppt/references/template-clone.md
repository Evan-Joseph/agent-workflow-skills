# Template Clone Mode

本文件在用户提供 `.pptx` 模板、要求仿模板、需要渲染模板页、选择模板 layout 或检查 layout 复用时读取。

## Basic Command

```bash
python3 scripts/generate_ppt.py \
  --plan slides_plan.json \
  --template-pptx ./company-template.pptx \
  --template-strict
```

`--template-strict` 表示每页都把模板对应页作为 image reference 喂给 `gpt-image-2`，仿真度最高。

## Template Rendering

`scripts/render_template.py` 会把 `.pptx` 自动渲染成每页 PNG，存到 `<cwd>/template_renders/<stem>/page-NN.png`。

后端优先级：

1. 本机 `libreoffice` / `soffice` 命令。
2. 本机 Docker + `linuxserver/libreoffice` 镜像。
3. PDF -> PNG 走 `pymupdf`，没有就用 `pdf2image` + poppler。

手动预渲染：

```bash
python3 scripts/render_template.py company-template.pptx
```

如果 LibreOffice 和 Docker 都不可用，让用户从 PowerPoint/Keynote/WPS 导出每页 PNG，命名为 `page-01.png` 起按字典序对应页码。

## Cache Layers

| 资料 | 路径 | 用途 |
| --- | --- | --- |
| 模板每页 PNG | `<cwd>/template_renders/<stem>/page-NN.png` | LibreOffice 一次渲染长期复用 |
| Vision 风格分析 | `<cwd>/template_cache/<sha256>.json` | 多模态分析一次长期复用 |
| 生成产物 | `<cwd>/outputs/<timestamp>/` | 每次新跑都新目录 |

## Template Clone Flow

1. 拿到模板 `.pptx`。
2. 大模板超过 15 页时，先 `python3 scripts/render_template.py xxx.pptx`，从 `template_renders/<stem>/` 里挑 8-12 张代表页复制到 curated 目录供 vision 分析。
3. 写 `slides_plan.md` 并转 `slides_plan.json`。想精准对位时，在 H2 标题里加 `layout=layout-NN`。
4. 先跑单页：

```bash
python3 scripts/generate_ppt.py \
  --plan slides_plan.json \
  --template-pptx xxx.pptx \
  --template-images template_renders/xxx_curated \
  --template-strict --slides 1
```

5. 封面或关键页效果 OK 后再跑全量。

## Layout Reuse Rules

核心原则：尽量做到 1 page : 1 layout。同一个独特 layout 反复出现，观众会感到明显重复。

vision 分析会给每个 layout 标记 `reuse_friendly`：

| reuse_friendly | 典型 layout | 多次使用的代价 |
| --- | --- | --- |
| `false` | 封面、具名角色插画、独特场景图、复杂流程页、novelty 数据装置 | 重复非常明显 |
| `true` | 纯文字、卡片网格、通用列表、章节标题 | 可复用，但仍建议错开 |

执行策略：

1. 优先把模板里不同 layout 分配给不同 slide。
2. 内容结构相似时，先尝试改写内容结构，而不是复用同一个独特 layout。
3. 冒烟后查看 `Layout 复用检测` 输出：`(!)` 必须改，`(i)` 看情况改。
4. 看 cache JSON 选 layout：

```bash
cat <cwd>/template_cache/<sha256>.json | jq '.layouts[] | {id, page_type, reuse_friendly, summary}'
```
