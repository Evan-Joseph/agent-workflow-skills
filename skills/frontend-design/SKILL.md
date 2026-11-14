---
name: frontend-design
description: "用于直接在代码中构建、重塑或高保真审计生产级 Web 与移动端 UI/UX。深度集成 Mobbin（真实商业产品交互流对标）、Awwwards SOTM/SOTY（排版张力与动效 DNA 拆解）、shadcn/ui、transitions.dev、beautifului.dev、beui.dev、rareui.com 与 Impeccable 视觉系统审计。"
metadata:
  short-description: 生产级现代前端架构、Mobbin+Awwwards对标与受众自审中枢
---

# Frontend Design & System Crafting

将原型或需求直接转化为结构克制、触感细腻、无障碍完备的生产级前端界面。组件安装与微观几何检查细则见 [`references/ui-craft-and-qa-gates.md`](./references/ui-craft-and-qa-gates.md)。

## 运行时契约 (Runtime Contract)

- 行业设计系统检索脚本（`references/components/ui-ux-design/scripts/search.py`）：固定使用 `python3`（`homebrew-stdlib`），严禁自建 `venv` 或执行 `pip install`。
  ```bash
  python3 $HOME/.agents/skills/frontend-design/references/components/ui-ux-design/scripts/search.py "AI SaaS dashboard" --design-system
  npx -y modern-web-guidance@latest search "light dismiss dialog"
  ```

## 一、 五维现代前端参考体系与选型

| 维度 | 参考源 | 适用场景 | 本地参考 |
| :--- | :--- | :--- | :--- |
| **工程组件底座** | `ui.shadcn.com` | 控制台、数据表、`FieldGroup` 表单、无障碍弹窗（语义化 `oklch` 令牌） | [`references/shadcn/overview.md`](./references/shadcn/overview.md)、[`rules.md`](./references/shadcn/rules.md) |
| **纯 CSS 微交互** | `transitions.dev` | 零 JS 依赖弹窗缩放、文字原位翻转、错误晃动、`prefers-reduced-motion` | [`references/transitions/overview.md`](./references/transitions/overview.md)、[`catalog.md`](./references/transitions/catalog.md) |
| **AI 原生原语** | `beautifului.dev` | `ThinkingState` 折叠轨迹、`ApprovalCard` 人工确认、带引用流式问答 | [`references/beautiful-ui/overview.md`](./references/beautiful-ui/overview.md)、[`primitives.md`](./references/beautiful-ui/primitives.md) |
| **物理弹簧动效** | `beui.dev` | `TiltCard`、`BottomSheet`、`layoutId` 共享布局与手势吸附 | [`references/beui/overview.md`](./references/beui/overview.md)、[`catalog.md`](./references/beui/catalog.md) |
| **稀缺记忆点原语** | `rareui.com` | 落地页与作品集点睛交互（`FluidOrb`、`FolderComponent`、`DurationPicker`） | [`references/rare-ui/overview.md`](./references/rare-ui/overview.md)、[`catalog.md`](./references/rare-ui/catalog.md) |

## 二、 双轨真实标杆对标（拒绝闭门手搓）

1. **商业产品流与信息架构 — 实调 `mobbin` MCP**：
   - 构建或重构真实产品页、Dashboard、Onboarding、Paywall 前，先调用 `mobbin` MCP（`search_screens` / `search_flows` / `search_sections`）及 [`references/mobbin-redesign/mobbin-redesign-workflow.md`](./references/mobbin-redesign/mobbin-redesign-workflow.md) 对标 2 个以上头部上线产品（Linear、Stripe、Apple、Notion、Wise 等）；管理后台优先复用 GitHub `>1,000` Stars 成熟组件库，不手搓简陋 HTML。
2. **品牌叙事与动效上限 — `Awwwards SOTM/SOTY` 拆解**：
   - 打造旗舰官网或个人作品集时，按 [`references/awwwards-reverse-learning.md`](./references/awwwards-reverse-learning.md) 在 `:9223` 后台页提取标杆站点的 `clamp()` 流体字号、`cubic-bezier` 曲线与滚动节奏（严禁把展示站 Preloader 遮罩、滚轮劫持或自定义光标搬进高频工具与表单页）。
3. **真实品牌图标与深度审计**：真实品牌 Logo 从 `api.svgl.app` 或 `cdn.simpleicons.org` 拉取官方 SVG；大厂令牌参考 [`references/stitch/`](./references/stitch/)，反 AI Slop 视觉审计参考 [`references/impeccable/`](./references/impeccable/)。

## 三、 核心工程与审美红线

1. **语义令牌与纯净布局**：统一用语义色（`bg-background`、`text-foreground`）自适应亮暗色；用 `flex/grid + gap-*` 替代 `space-x/y-*`；等宽高写 `size-*`；仅对 `transform`/`opacity` 加过渡（禁 `transition: all`）。
2. **同心圆角、零截断与零孤字小尾巴**：满足 $R_{\text{outer}} = R_{\text{inner}} + \text{Padding}$；禁止用 `[切换]` 等方括号文本冒充按钮；确保徽标、菜单与移动端选项不因差几像素折出 1–4 字“小尾巴”（标题 `text-wrap: balance`，正文 `text-wrap: pretty`）。
3. **行业匹配着色器与一屏一主叙事**：暗黑 WebGL 发光球仅限 AI/开发者/游戏页面，医疗、教育、政务、财务页面严禁滥用；`1440×900` 单屏聚焦单一核心叙事。
4. **中文输入法安全回车与测评防失焦**：`Enter` 提交强制校验 `!e.isComposing && e.keyCode !== 229`；带 `onblur` 切屏检测的在线测评统一采用页内 **Closed Shadow DOM 隐形悬浮 HUD**。

## 四、 交付前受众自审四步闭环（必做）

每次 UI 交付前必须完整执行：
1. **真实渲染**：在本地服务或无头 Playwright / `:9223` 后台页加载真实页面；
2. **控制台与交互检查**：确认 Console 零报错/零 404，实测展开态无裁切、开关 `On -> Off -> On` 往返生效；
3. **多视口 `<150 KB` 截图**：截取桌面（`1440×900`）与移动端（`390×844` / `844×390`）压缩为 `<150 KB` 真实 JPEG/PNG；
4. **亲自调 `read_file` 肉眼审图**：站在首次访问的用户视角逐张审视对齐、圆角、留白与换行（细则见 [`references/ui-craft-and-qa-gates.md`](./references/ui-craft-and-qa-gates.md)），清零瑕疵后再交付。
