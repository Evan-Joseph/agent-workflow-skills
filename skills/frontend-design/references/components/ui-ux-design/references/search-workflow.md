# UI/UX Search Workflow

本文件在需要用 `scripts/search.py` 生成设计系统、查询设计资料、持久化设计系统或获取技术栈建议时读取。

## Prerequisite

检查 Python：

```bash
python3 --version || python --version
```

如果 Python 缺失，停止并告诉用户对应系统的安装方式；不要擅自修改全局环境。

## Design System First

当用户请求 UI/UX 设计、实现、评审、修复或改进时，先抽取：

- 产品类型：SaaS、e-commerce、portfolio、dashboard、landing page 等。
- 风格关键词：minimal、playful、professional、elegant、dark mode 等。
- 行业：healthcare、fintech、gaming、education 等。
- 技术栈：React、Vue、Next.js；未指定时默认 `html-tailwind`。

优先生成完整设计系统：

```bash
python3 <skill-dir>/scripts/search.py "<product_type> <industry> <keywords>" --design-system [-p "Project Name"]
```

示例：

```bash
python3 <skill-dir>/scripts/search.py "beauty spa wellness service" --design-system -p "Serenity Spa"
```

该命令会并行搜索 product、style、color、landing、typography 五类数据，并结合 `ui-reasoning.csv` 输出 pattern、style、colors、typography、effects 和 anti-patterns。

## Persisted Design System

需要跨会话复用时，加 `--persist`：

```bash
python3 <skill-dir>/scripts/search.py "<query>" --design-system --persist -p "Project Name"
```

产物：

- `design-system/MASTER.md`：全局设计规则。
- `design-system/pages/`：页面级 override。

页面级 override：

```bash
python3 <skill-dir>/scripts/search.py "<query>" --design-system --persist -p "Project Name" --page "dashboard"
```

检索顺序：

1. 构建特定页面时，先查 `design-system/pages/<page>.md`。
2. 如果页面文件存在，其规则覆盖 `MASTER.md`。
3. 如果不存在，只使用 `design-system/MASTER.md`。

## Domain Searches

设计系统生成后，按需补充单域搜索：

```bash
python3 <skill-dir>/scripts/search.py "<keyword>" --domain <domain> [-n <max_results>]
```

| Need | Domain | Example |
|------|--------|---------|
| More style options | `style` | `--domain style "glassmorphism dark"` |
| Chart recommendations | `chart` | `--domain chart "real-time dashboard"` |
| UX best practices | `ux` | `--domain ux "animation accessibility"` |
| Alternative fonts | `typography` | `--domain typography "elegant luxury"` |
| Landing structure | `landing` | `--domain landing "hero social-proof"` |

## Stack Guidelines

未指定 stack 时默认 `html-tailwind`：

```bash
python3 <skill-dir>/scripts/search.py "<keyword>" --stack html-tailwind
```

可用 stack：

- `html-tailwind`
- `react`
- `nextjs`
- `vue`
- `svelte`
- `swiftui`
- `react-native`
- `flutter`
- `shadcn`
- `jetpack-compose`

## Available Domains

| Domain | Use For | Example Keywords |
|--------|---------|------------------|
| `product` | Product type recommendations | SaaS, e-commerce, portfolio, healthcare, beauty, service |
| `style` | UI styles, colors, effects | glassmorphism, minimalism, dark mode, brutalism |
| `typography` | Font pairings, Google Fonts | elegant, playful, professional, modern |
| `color` | Color palettes by product type | saas, ecommerce, healthcare, beauty, fintech, service |
| `landing` | Page structure, CTA strategies | hero, hero-centric, testimonial, pricing, social-proof |
| `chart` | Chart types, library recommendations | trend, comparison, timeline, funnel, pie |
| `ux` | Best practices, anti-patterns | animation, accessibility, z-index, loading |
| `react` | React/Next.js performance | waterfall, bundle, suspense, memo, rerender, cache |
| `web` | Web interface guidelines | aria, focus, keyboard, semantic, virtualize |
| `prompt` | AI prompts, CSS keywords | style names |

## Output Formats

```bash
python3 <skill-dir>/scripts/search.py "fintech crypto" --design-system
python3 <skill-dir>/scripts/search.py "fintech crypto" --design-system -f markdown
```

Use the Markdown format when the design system should be committed or shared.
