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
3. **真实品牌图标与 Hallmark 反 AI Slop 硬门禁（必过 `sloplint`）**：真实品牌 Logo 从 `api.svgl.app` 或 `cdn.simpleicons.org` 拉取官方 SVG；大厂令牌参考 [`references/stitch/`](./references/stitch/)，反 AI Slop 视觉审计参考 [`references/impeccable/`](./references/impeccable/) 与 **GitHub 高星 `Nutlope/hallmark` 硬门禁细则 [`references/hallmark/anti-slop-and-artifacts-governance.md`](./references/hallmark/anti-slop-and-artifacts-governance.md)**（内置零依赖静态扫描器 `scripts/sloplint.mjs`，涵盖网页、Sidecar 面板、`<agent-embed>` 生成式 UI 与 MagPie Artifacts）。

## 三、 核心工程与审美红线（含 Hallmark 五大禁令）

1. **语义令牌与纯净布局**：统一收口令牌于 `:root` 与 `[data-theme="dark"]`（禁在令牌块外散落裸色值与裸字体，Gate 48）；`html, body` 设 `overflow-x: clip`（禁 `hidden` 与 `100vw`，Gate 34）；仅对 `transform`/`opacity` 加过渡并配 `prefers-reduced-motion`（禁 `transition: all` 与动画 `width`/`height`，进度条统一用 `transform: scaleX()`，Gate 10a/27）；全部交互控件具备瞬时 `:focus-visible`（Gate 26a）。
2. **砍绝五大 AI Slop 视觉指纹（Floor 铁律）**：① 禁大写加字距眉标（`<=15px` 禁 `uppercase` 与 `letter-spacing > 0.03em`，Gate 54/67）；② 禁发光呼吸状态点、`✦` 装饰符与 Emoji 充当图标（Gate 30a/63）；③ 禁 `·` 中点串糖葫芦元数据（`>=2` 个中点直接 `FAIL`，Gate 63）与顶栏自嗨口号横幅；④ 禁卡片套卡片（Gate 4）与满屏高饱和圆角彩色胶囊汤；⑤ 禁紫蓝渐变（Gate 2a）。工具/侧栏界面默认采用 Linear / VS Code 式单色克制排版、`tabular-nums` 等宽数字对齐与 `1px` 细分割线，仅在异常/告警时着色。
3. **同心圆角、零截断与零孤字小尾巴**：满足 $R_{\text{outer}} = R_{\text{inner}} + \text{Padding}$；禁止用 `[切换]` 等方括号文本冒充按钮；确保徽标、菜单与移动端选项不因差几像素折出 1–4 字“小尾巴”（标题 `text-wrap: balance`，正文 `text-wrap: pretty`）。
4. **行业匹配着色器与一屏一主叙事**：暗黑 WebGL 发光球仅限 AI/开发者/游戏页面，医疗、教育、政务、财务页面严禁滥用；`1440×900` 单屏聚焦单一核心叙事。
5. **中文输入法安全回车与测评防失焦**：`Enter` 提交强制校验 `!e.isComposing && e.keyCode !== 229`；带 `onblur` 切屏检测的在线测评统一采用页内 **Closed Shadow DOM 隐形悬浮 HUD**。
6. **个人单机工具零登录墙准则**：面向个人本机使用的刷题器、看板、检索器与效率小工具，严禁画蛇添足设计多用户注册、登录页或口令墙，必须打开即用（状态落本地存储/SQLite 即可）。
7. **HTML 可视化可直点交付与 MagPie Artifacts 阅后即焚准则**：交付 HTML 可视化优先用 `<agent-embed src="file:///...">` 内联渲染（紧凑组件 `<=450px` 高，冲洗式无外框，遵循 `sloplint --scope component`）；仅跨天高频复用的交互工作台方可发布至 `magpie-artifacts`（强制按 **`【领域】简洁名称`** 命名，更新时传原 `id` 保全 `data.db`；单次巡检报告与一次性偏好问卷严禁常驻托管，详见 [`references/hallmark/anti-slop-and-artifacts-governance.md`](./references/hallmark/anti-slop-and-artifacts-governance.md)）。

## 四、 交付前 `sloplint` + 受众自审五步闭环（必做）

每次 UI（含生成式 UI 与 Sidecar）交付前必须完整执行：
1. **`sloplint` 静态硬门禁清零**：执行 `/opt/homebrew/bin/node $HOME/.agents/skills/frontend-design/scripts/sloplint.mjs <target> [--scope page|app|component]`，确保 **`0 FAIL, 0 REFLEX`**；
2. **真实渲染**：在本地服务或无头 Chrome / Playwright / `:9223` 后台页加载真实页面；
3. **控制台与交互检查**：确认 Console 零报错/零 404，实测展开态无裁切、开关 `On -> Off -> On` 与亮/暗双色切换生效；
4. **多视口 / 亮暗双色 `<150 KB` 截图**：截取桌面/侧栏真实尺寸与亮暗双色模式 PNG/JPEG；
5. **亲自调 `read_file` 肉眼审图**：站在首次访问的用户视角逐张审视对齐、圆角、留白与换行（细则见 [`references/ui-craft-and-qa-gates.md`](./references/ui-craft-and-qa-gates.md)），清零瑕疵后再交付。

## 五、 零现金高审美直出与防锚定污染铁律（已彻底弃用 Arena.ai 网页盲测抽卡）

1. **严禁低档模型搭骨架**：严禁“先用低档模型写粗糙 HTML/CSS 骨架、再交旗舰模型精修”（必引发不可逆的审美锚定污染），亦严禁给强模型投喂残缺伪代码、半成品占位或篡改后的设计原典；同时严禁回退调用已上线积分墙并封禁教育邮的 `Arena.ai`（WebDev Arena / LMArena）网页盲测。
2. **本机单栈一次成型**：日常高审美 Web/App 界面直接由原厂 `Antigravity` 搭载 **`Gemini 4 Carbon`**（视觉审美与排版张力）+ **`Gemini 4 Neon`**（复杂交互工程）端到端一次直出，按需结合 `Mobbin` 真机交互流对标；仅旗舰级门面或用户点名任务方经批准点射 `claude-magpie -p`（`group/opus` / `group/fable`）。
