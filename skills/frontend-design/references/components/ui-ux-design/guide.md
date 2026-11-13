---
name: ui-ux-design
description: 用于UI/UX设计方向、设计系统、视觉风格、配色、字体、布局模式、UI polish、微交互、hover/press 状态、动画质感、光学对齐、界面粗糙/feels off/make it feel better 等面向实现的设计建议和审查。
metadata:
  short-description: UI设计检索与设计系统生成
---

# UI/UX Design

先用本 skill 的结构化搜索数据确定设计方向，再只加载实现所需的 domain、stack 和交付检查规则。它适合在实现前生成设计系统，也适合对已有 UI 做视觉和交互审查。

## 路由边界

| 任务 | 默认入口 |
|---|---|
| 只要设计方向、设计系统、视觉审查、UI polish 清单 | `ui-ux-design` |
| 需要直接改代码实现页面、组件或动效 | `frontend-design` |
| 已有项目整套前端翻新、原型接入、真实联调、回归验收 | `project-frontend-refresh` |
| Stitch 原型、Stitch prompt、Stitch 到 React 的交接 | `stitch-design` / `stitch-workflow` / `react-components` |
| GSAP 专项动画 API、React GSAP、ScrollTrigger | `gsap-core` / `gsap-react` / `gsap-scrolltrigger` 作为参考 |

不要把设计建议写成空泛风格词。每条建议都要能落到组件、CSS、状态、布局或验收检查。

## When To Use

- 用户要求 UI/UX 设计建议、视觉方向、配色、字体、布局模式或设计系统。
- 任务需要贴近具体技术栈，例如 React、Next.js、Vue、SwiftUI、Tailwind。
- 开发前需要可复用的 design-system 输出。
- 交付前需要检查 UI 是否显得粗糙、低对比、图标不统一、交互反馈不足或响应式不稳。
- 用户要求 polish、微交互、hover/press 状态、动画更顺、界面更有质感，或说 UI feels off / make it feel better。

## Core Workflow

1. 抽取产品类型、行业、风格关键词和技术栈。
2. 先生成设计系统：

```bash
python3 <skill-dir>/scripts/search.py "<product_type> <industry> <keywords>" --design-system [-p "Project Name"]
```

3. 需要跨会话复用时加 `--persist`，生成 `design-system/MASTER.md` 和页面级 overrides。
4. 按需做单域补充搜索，例如 style、chart、ux、typography、landing。
5. 未指定 stack 时默认 `html-tailwind`，再按实际栈读取 stack guidance。
6. 实现或审查前读取交付检查清单；涉及 polish、微交互、动画、圆角、阴影、动态数字或“界面不顺”时，同时读取 [references/ui-polish-microdetails.md](references/ui-polish-microdetails.md)。

完整命令、domain/stack 表、persist 规则和输出格式见 [references/search-workflow.md](references/search-workflow.md)。

## Search Commands

生成设计系统：

```bash
python3 <skill-dir>/scripts/search.py "healthcare SaaS dashboard professional" --design-system -p "HealthOps"
```

持久化设计系统：

```bash
python3 <skill-dir>/scripts/search.py "beauty spa wellness service elegant" --design-system --persist -p "Serenity Spa"
```

单域补充：

```bash
python3 <skill-dir>/scripts/search.py "animation accessibility" --domain ux
python3 <skill-dir>/scripts/search.py "elegant luxury serif" --domain typography
python3 <skill-dir>/scripts/search.py "layout responsive form" --stack html-tailwind
```

## Design Synthesis Rules

- 先给设计系统，再给组件或页面实现建议。
- 设计建议要落到颜色、字体、间距、布局、组件状态、可访问性和响应式策略。
- 不要只堆风格词；每个设计判断都要能转化成 CSS、组件约束或页面结构。
- 对业务工具、SaaS、CRM、后台系统，优先安静、密集、可扫描、可重复操作的界面，不做营销式 hero 堆叠。
- 对 landing、品牌页和作品页，视觉要服务首屏识别和转化路径，避免泛化渐变和空洞装饰。

## Professional UI Gate

交付前检查：

- 不用 emoji 当图标；优先 Heroicons、Lucide 或 Simple Icons。
- 点击元素有 cursor、hover、focus 状态，hover 不造成布局位移。
- 浅色和深色模式都有足够对比；透明和 glass 元素在浅色模式下仍可见。
- 固定导航和浮动元素不会遮挡内容。
- 375px、768px、1024px、1440px 下没有文字溢出和横向滚动。
- UI 微质感检查覆盖文字换行、同心圆角、光学对齐、阴影/描边、图片边缘、命中区域、可中断动画、入场/退出节奏、动态图标、动态数字、`transition` 和 `will-change`。

完整交付检查表见 [references/professional-ui-checklist.md](references/professional-ui-checklist.md)。
UI 微质感细则见 [references/ui-polish-microdetails.md](references/ui-polish-microdetails.md)。
