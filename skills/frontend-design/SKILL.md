---
name: frontend-design
description: "用于直接在代码中构建、重塑或高保真审计生产级 Web 与移动端 UI/UX（含在线测评防失焦 Closed Shadow DOM 悬浮 HUD 与交付前受众自审门禁）。深度集成 Mobbin（60万+ 真实上线 App/Web 界面与交互流对标）、Awwwards SOTM/SOTY（月度/年度标杆站点排版张力与动效 DNA 逆向拆解）、shadcn/ui、transitions.dev、beautifului.dev、beui.dev、rareui.com、ui-ux-pro-max（192 类行业规则 + 79 种风格）与 Impeccable 视觉系统审计。"
metadata:
  short-description: 生产级现代前端架构、高质感界面设计、受众自审与动效中枢
---

# Frontend Design & System Crafting

统一前端工程与高审美界面中枢：将原型、需求或概念直接转化为生产级、高审美、强触感、高可访问性的代码产物。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：本技能内部脚本（`references/components/ui-ux-design/scripts/search.py` 等）：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `homebrew-stdlib` 运行时，标准库实现）。
- **执行命令范例**：
  ```bash
  # 1. 生成完整行业级设计系统推荐（192 类产品规则 + 配色 + 字体配对 + 反模式清单）
  python3 $HOME/.agents/skills/frontend-design/references/components/ui-ux-design/scripts/search.py "AI SaaS dashboard" --design-system
  # 2. 按领域检索（style / color / typography / ux / landing / chart / product）
  python3 $HOME/.agents/skills/frontend-design/references/components/ui-ux-design/scripts/search.py "glassmorphism card" --domain style
  # 3. 检索 Chrome 官方现代 Web API 最佳实践（零鉴权免费 CLI）
  npx -y modern-web-guidance@latest search "light dismiss dialog"
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。

---

## 一、 现代前端五维支柱参考体系 (5-Pillar Modern UI System)

在实现或改造界面时，根据任务场景选择最契合的现代化参考源：

| 支柱维度 | 核心参考源 | 核心定位与技术底座 | 典型代表原语与适用场景 | 参考文档 |
| :--- | :--- | :--- | :--- | :--- |
| **1. 架构与工程底座** | [ui.shadcn.com](https://ui.shadcn.com) | 源码所有权、Radix/Base UI 无障碍、Tailwind CSS、语义化 Tokens (`oklch`) | 按钮、卡片、表单（`FieldGroup`/`Field`）、弹窗、下拉菜单、数据表格、侧边栏导航 | [shadcn/overview.md](./references/shadcn/overview.md)<br>[shadcn/rules.md](./references/shadcn/rules.md) |
| **2. 纯 CSS 微交互过渡** | [transitions.dev](https://transitions.dev) | 零依赖纯 CSS、`t-*` 命名空间、`_root.css` 语义化动效令牌、强减弱动效守卫 | 模态弹窗开合、选项卡平滑滑块、数字跳变、成功对勾绘制、表单错误晃动、纯 CSS 文字光泽扫描 | [transitions/overview.md](./references/transitions/overview.md)<br>[transitions/catalog.md](./references/transitions/catalog.md) |
| **3. AI 原生人机交互原语** | [beautifului.dev](https://beautifului.dev) | 针对 Agent 与大模型人机协同特化、思考展开、流式追问、人机把关 | 深度思考折叠轨迹 (`ThinkingState`)、人类审批卡片 (`ApprovalCard`)、带引用源的流式问答 (`StreamingText`)、动态任务行 (`TaskRows`)、工具芯片 (`ToolChips`) | [beautiful-ui/overview.md](./references/beautiful-ui/overview.md)<br>[beautiful-ui/primitives.md](./references/beautiful-ui/primitives.md) |
| **4. 流畅物理动效与手势** | [beui.dev](https://beui.dev) | Motion / Framer Motion 弹簧力学、手势惯性吸附、共享布局 (`layoutId`)、Open Registry | 3D 悬停卡片 (`TiltCard`)、移动端弹性抽屉 (`BottomSheet`)、刻度预览轨 (`PreviewRail`)、中心折纸弹窗、着色器背景 (`ShaderBackground`)、智能对话视口 (`MessageScroller`) | [beui/overview.md](./references/beui/overview.md)<br>[beui/catalog.md](./references/beui/catalog.md) |
| **5. 稀缺触感与高记忆点** | [rareui.com](https://rareui.com) | 稀缺独特交互形态、单文件即用、shadcn CLI 分发、打破同质化模板感 | 有机发光球体 (`FluidOrb`)、矩阵点阵球 (`MatrixOrb`)、物理重力掉落字母 (`GravityLetters`)、仪表盘时长选择器 (`DurationPicker`)、扇形文件层叠 (`FolderComponent`) | [rare-ui/overview.md](./references/rare-ui/overview.md)<br>[rare-ui/catalog.md](./references/rare-ui/catalog.md) |

---

## 二、 任务场景选型与路由决策 (Decision Matrix)

1. **企业级控制台 / 业务表单 / 数据管理页**：
   - 以 `ui.shadcn.com` 为主干框架。
   - 表单严格执行 `FieldGroup` + `Field` 模式；弹窗包含 Accessible Title；表格与分页按 shadcn Table/DataTable 组织。
2. **需要轻量、丝滑的微交互（不想引入复杂 JS 动画包）**：
   - 采用 `transitions.dev` 的语义化 CSS 类与 `_root.css` 变量。
   - 弹窗增加软缩放与微模糊 (`06-modal`)，按钮文字切换使用原位翻转 (`04-text-states-swap`)，表单校验失败使用阻尼晃动 (`12-error-state-shake`)。
3. **AI 智能体 / 对话助手 / 自主执行工作流**：
   - 状态展示优先选用 `beautifului.dev` 与 `beui.dev` 的 Agent 原语。
   - 步骤推理采用带展开轨迹的 `ThinkingState`；不可逆写操作前必须弹出 `ApprovalCard`（支持单选自动步进与手写输入）；流式文本嵌入域名 Favicon 堆叠数据源。
4. **展示型落地页 (Landing Page) / 个人作品集 / 深度交互原型**：
   - 结合 `beui.dev` 与 `rareui.com` 注入独特的物理质感；打造旗舰品牌官网或个人学术/工程作品集时，按 [`references/awwwards-reverse-learning.md`](./references/awwwards-reverse-learning.md) 拆解 2–3 个同调性 Awwwards SOTM/SOTY 获奖站点的流体排版比例与非对称缓动曲线。
   - 核心特性展示卡片使用 `tilt-card`；AI 助手入口使用 `fluid-orb`；附件库展示使用 `folder-component`；验证码使用 `otp-input` 老虎机式滚轴翻转。

---

## 三、 组件安装与工程分发协议

在真实项目中接入组件时，支持以下开箱即用方式：

```bash
# 1. 基础 shadcn/ui 组件安装
npx shadcn@latest add button card dialog dropdown-menu form input tabs

# 2. Rare UI 单文件组件安装 (基于 shadcn 官方生态)
npx shadcn@latest add swamimalode07/rare-ui/fluid-orb
npx shadcn@latest add swamimalode07/rare-ui/folder-component
npx shadcn@latest add swamimalode07/rare-ui/duration-picker
npx shadcn@latest add swamimalode07/rare-ui/otp-input

# 3. beUI 开放 Registry 安装
npx shadcn@latest add https://beui.dev/r/tilt-card
npx shadcn@latest add https://beui.dev/r/bottom-sheet
npx shadcn@latest add https://beui.dev/r/message-scroller

# 4. Transitions.dev 动效注入
# 将 references/transitions/overview.md 中的 _root.css 变量与类名注入 globals.css，即插即用
```

---

## 四、 审美与工程铁律

1. **语义化色彩与亮暗色自适应**：
   - 永远使用语义色彩变量（`bg-background`, `text-foreground`, `bg-primary`, `text-muted-foreground`），严禁硬编码原始十六进制或 `bg-blue-500` 等死色。
   - 严禁手动硬编码 `dark:` 分支覆盖默认组件样式。
2. **布局纯净性**：
   - `className` 仅用于外部布局与间距，严禁篡改组件内建结构。
   - 绝不使用 `space-x-*` / `space-y-*`，一律使用 Flexbox/Grid 配合 `gap-*`。
   - 宽高相等元素一律简写为 `size-*`。
3. **严格的无障碍规范 (A11y)**：
   - 模态框必须具备 Title（视觉无需展示时加 `className="sr-only"`）。
   - 自定义触发器必须使用 `asChild` 避免双层 button 语法错误。
   - 每一个动效均需保障 `@media (prefers-reduced-motion: reduce)` 平稳回退。
4. **多级权威设计参考源与正交双轨对标（Mobbin Team 商业产品流 + Awwwards SOTM/SOTY 审美上限拆解 + GitHub `>1,000 ⭐` 开源基座 + Impeccable）**：
   - **第一层 A（商业产品流与信息架构真凭实据 — Mobbin 官方插件与 MCP，已激活 Team 年卡无限额度）**：
     - 本机已通过 `mobbin-mcp` 打通 **Mobbin Team Plan (`<USER_EMAIL>`)** 自动续期 OAuth 通道。凡涉及真实产品形态改造、Paywall/Onboarding/Dashboard 交互流设计或界面重构，**必须第一时间实际调用 `mobbin` MCP（`search_screens`、`search_flows`、`search_sections`）** 与 `redesign-screen` 技能（本地完整方法论归档于 [`references/mobbin-redesign/mobbin-redesign-workflow.md`](./references/mobbin-redesign/mobbin-redesign-workflow.md) 及 [`references/mobbin-redesign/references/taste.md`](./references/mobbin-redesign/references/taste.md)），确保每一处结构调整均有 2 个以上真实头部产品（如 Linear、Stripe、Airbnb、Apple、Revolut、Wise、Notion）的界面证据支撑，严禁因任何借口跳过 `mobbin` 调用或凭空臆造“大多数 App 都这么做”；构建管理控制台、软路由仪表盘或远控界面时，必须先查 GitHub `>1,000 ⭐` 头部开源基座（如 `tabler/tabler`、`shadcn/ui`）直接复用成熟组件体系，严禁从零手搓简陋 HTML。
   - **第一层 B（品牌叙事、流体排版与动效审美上限对标 — Awwwards SOTM / SOTY 逆向拆解）**：
     - 针对旗舰产品官网、个人作品集与高记忆点叙事页，按 [`references/awwwards-reverse-learning.md`](./references/awwwards-reverse-learning.md) 直解 `awwwards.com/websites/sites_of_the_month/` 与 `sites_of_the_year/` 的真实上线外链、四维评审分（Design / Usability / Creativity / Content）及 Developer 六维分，并在 `:9223` 静默后台页运行只读探针提取真实流体字号公式（Fluid `clamp()`）、`cubic-bezier` 阻尼曲线、`Lenis + ScrollTrigger` 节奏与 `View-Transitions` 转场；严守反模式防火墙（严禁将展示站 Preloader 遮罩、滚轮阻尼劫持或自定义光标搬进高频后台工具与表单页面）。
   - **第二层：头部科技品牌设计令牌与真实矢量品牌资产**：
     - 对标特定大厂风格时，结合 [`references/stitch/`](./references/stitch/)（或归档库 `$HOME/.agents/skills-archive/20260704-governance-pass1/design-md/`）；涉及真实品牌 Logo 时优先从 `https://api.svgl.app?search=<brand>` 或 `https://cdn.simpleicons.org/<slug>` 拉取官方矢量 SVG，严禁手写简陋 `<svg>` 几何图形冒充品牌标志。
   - **第三层：行业设计系统生成与 Impeccable 深度视觉审计**：
     - 调用 `search.py --design-system` 生成行业规则与配色字体方案；显式调用 `$impeccable` 或执行交付前自检时，读取 [`references/impeccable/`](./references/impeccable/)，启动对比度、对齐韵律与反 AI Slop 深度核验。
5. **严禁“贴标签式假重构”、视觉残缺与孤字小尾巴门禁（Anti-Cosmetic-Slapping, Zero-Truncation & Anti-Widow Gate）**：
   - **严禁伪控件与字符凑数**：严禁在旧列表上仅修改标题文字（如硬塞开源项目名称）充当重构；严禁使用 `[切换]`、`[切温控]` 等方括号纯文本或 ASCII 字符（`↓` `↑` `▸`）冒充交互按钮与图标，必须使用标准原子组件（`SegmentedControl`、`Switch`、`Sheet`）与纯净 SVG / `VectorDrawable` 矢量图标。
   - **同心圆角与零截断铁律**：内外容器严格遵循同心圆角公式 $R_{\text{outer}} = R_{\text{inner}} + \text{Padding}$；交付前必须检查真实渲染截图，确保零省略号恶意截断（`...`）、零横向溢出、零底部导航栏或边框 `1px` 裁切、零无条件渐变遮罩（`mask-image`）切碎末行文字。
   - **零孤字小尾巴折行铁律（Zero Short-Tail / Widow Wrap Law）**：
     - 严禁单行文本因多出几个字符被迫换行、在第 2 行留下 1–5 个字符的“小尾巴”（如选择题 13–16 字选项因右侧状态胶囊过宽折出 `来源`/`提高` 两字尾巴、底栏提示折出 `答案` 两字、侧栏导航折出 `（APK）`、统计卡或副标题把括号/词组拦腰拆成两行、卡片顶栏徽标差 `15px` 掉成两行）。
     - **治理手段**：① 顶栏徽标组、侧栏菜单项、底部单行提示栏、统计卡次要注记一律精炼文案并配合 `whitespace-nowrap` 与紧凑内边距保持严格单行；② 移动端选择题选项适当收紧水平内边距、题号徽标尺寸与右侧正误角标宽度，确保常见单句选项（12–18 字）在 `390px` 竖屏下 100% 单行容纳；③ 多行题干与说明段落统一施加 `text-wrap: pretty`（标题施加 `text-wrap: balance`），并在 Playwright 几何脚本中用 `Range.getClientRects()` 检测末行宽度占比（当 `rects.length >= 2` 且末行宽度 `< 22%` 首行宽度时视为孤字小尾巴告警并针对性收敛）。
6. **Stitch 设计工作流**：
   - 涉及设计系统约束或 Stitch 原型转代码时，参考 `references/stitch/`。
7. **应试者防失焦视角（Closed Shadow DOM 隐形悬浮 HUD）**：
   - 面对带 `window.onblur` / `visibilitychange` 切屏检测红线的在线测评页面（如北森 `ceping.com`），严禁设计需切换焦点的独立 Web 工作台或弹窗；必须采用页内 **Closed Shadow DOM 隐形悬浮 HUD** 与静默键盘快捷键交互。
8. **中文输入法安全回车守卫（CJK IME-Safe Enter Guard）**：
   - 任何监听 `keydown` 提交对话、搜索或表单的 `Enter` 快捷键处理器，**必须同时校验 `!e.isComposing && e.keyCode !== 229`（React 中校验 `!e.nativeEvent.isComposing && e.keyCode !== 229`）**，确保用户在中文/日韩输入法（IME）候选词上屏按回车时绝不会误触发半截拼音或未完成消息提前发送。
9. **行业匹配着色器门禁与一屏一主叙事铁律（Industry-Matched Shader & One-Narrative-Per-Viewport Gate — `taste-skill`）**：
   - **行业匹配着色器门禁**：WebGL / GLSL Shader 发光球体（Glowing Orbs）、粒子流体与暗黑科幻背景**仅允许**用于 AI 产品、开发者工具、游戏娱乐或硬件极客页面；在医疗健康、教育教学、政务公共服务、财务台账或餐饮零售页面上**绝对禁用**暗黑发光球与重度科幻着色器。
   - **`1440×900` 一屏一主叙事（One Primary Narrative Per Viewport）**：桌面端 `1440×900` 标准视口内每个纵向分屏（Section）严格聚焦单一主视觉叙事与核心行动点，严禁在同一视口内堆叠多个竞争性主标题、双层轮播或不等宽的左右失衡留白。

---

## 五、 工程交付与受众自审门禁 (Delivery & Pre-Delivery Audience Self-Review Gate — P1-1)

0. **交付前受众自审四步闭环（Pre-Delivery Audience Self-Review Gate，必做）**：
   - 任何前端界面或组件向用户交付前，必须依次执行：
     1. **真实渲染**：在本地服务或预览环境中完整加载页面；
     2. **控制台与计算样式核查**：检查浏览器 Console 零报错/零资源 404，并通过 `getComputedStyle` / `getBoundingClientRect` 核对关键容器尺寸、圆角与溢出状态；
     3. **多视口 `<150 KB` 真 JPEG/PNG 截图**：截取桌面（`1440×900`）与移动（`390×844` / `844×390`）视口渲染图，经 `ffmpeg` 或 `sips` 压缩为 `<150 KB` 的真实 Baseline JPEG（`\xff\xd8\xff`）或 PNG（`\x89PNG`）；
     4. **亲自调 `read_file` 从受众视角审图**：亲自调用 `read_file` 查看截图，站在真实用户视角核对信息层级、同心圆角、对齐韵律与零孤字小尾巴折行，清零瑕疵后再交付。

1. **既有项目设计一致性**：
   - 进入已有代码库时，先探查现有包管理、构建脚本、样式方案与组件体系；优先尊重已有设计令牌，禁止在未授权情况下随意破坏既有主题系统。
2. **动效性能与收敛**：
   - 严禁滥用 `transition: all` 或 `will-change: all`；仅对实际发生变化的视觉属性（如 `transform`, `opacity`）添加过渡。
   - 微细节打磨（手感迟滞、点击反馈不灵动、同心圆角错位、文字排版截断）：查阅 `references/components/ui-ux-design/references/ui-polish-microdetails.md`（若需执行组件检索脚本 `references/components/ui-ux-design/scripts/search.py`，固定使用 `python3`）。
   - 复杂时间轴与滚动视差联动：按需启用 `references/components/gsap-core/`、`gsap-react/`、`gsap-scrolltrigger/`，并参考 [`references/awwwards-reverse-learning.md`](./references/awwwards-reverse-learning.md) 的 `:9223` 静默探针实测提取线上标杆站点的 `cubic-bezier`、CSS 变量与 `Lenis` 参数。
3. **真实渲染、多模态肉眼看图与独立 `reviewer` 挑刺门禁（Multimodal Eyes-On & Reviewer Critique Gate）**：
   - 优先通过 `browser-routing`（Playwright 无头隔离沙箱或接管主力 Chrome `${CDP_RELAY_HOST}` 持久守护中继，强制后台静默标签页与焦点仿真）验证组件实际视觉呈现、控制台报错与响应式断点；严禁直连 `9222` 反复断连重连，严禁使用 Computer Use 像素模拟或系统辅助功能脚本控制。
   - **强制用多模态视觉亲自看图，严禁仅靠 DOM 数值断言交差**：代码断言（如 `scrollWidth <= clientWidth`）无法发现“内层按钮圆角过尖扎出外层圆润容器”、“只拆文件但界面还是老样子”、“控件悬空不吸附/对齐错位”、“被迫换行留 2 字小尾巴”等视觉缺陷。每次 UI 改动后，必须截取多视口及关键交互态（选中态、揭晓态、抽屉展开态、深浅色）的真实渲染截图（JPEG `<150 KB`），**亲自调用 `read_file` 逐张观察画面**（必要时委派独立 `reviewer` 子代理对截图进行零偏误挑刺），发现任何审美、对齐或折行小尾巴瑕疵立即当回合返工，直至肉眼审视完美。
   - **四项强制交互态与渲染核验门禁（Interactive & Formula Verification Gates）**：
     1. **交互展开态裁切门禁（Interactive Expansion Clipping Gate）**：严禁只测静态首屏！必须模拟点击选中/展开所有选项、手风琴卡片与抽屉，遍历所有 `overflow: hidden/clip` 容器断言展开或 `scale` 膨胀后无左/右/底边缘被裁切（`el.scrollHeight <= el.clientHeight + 1` 且选中态 `outline`/`ring`/`scale` 不超出父容器裁剪边界）；
     2. **开关往返与副作用门禁（Toggle Roundtrip & Side-Effect Gate）**：所有开关按钮（如通知/震动/静音/主题切换）必须执行 `On -> Off -> On` 往返点击实测，不仅检查 UI 状态变化，还必须验证底层副作用（如关闭提醒/震动后倒计时与点击绝对不再触发 `navigator.vibrate` 或声音）；
     3. **全视口矩阵（含手机横屏 `844×390`）与零裸露公式门禁**：验收视口必须同时覆盖桌面（`1440×900`）、平板（`768×1024` / `1024×768`）、手机竖屏（`390×844`）与**手机横屏（`844×390`）**，核验横屏双栏顶底对齐；凡含数学公式的题库/卡片，**严禁使用字符串长度启发式（如 `length <= 16`）跳过 `<MathText />` 渲染器**，严禁在 `$...$` 外裸露 `\qquad`/`\texttt` 或在 `\text{}` 内写中文间隔号 `·`；
     4. **真实根节点非空与线上缓存刷新门禁**：前端服务或 Cloudflare Pages 部署后，严禁仅凭 `curl -I` 返回 `HTTP 200` 宣称就绪，必须验证线上 `#root`/`#app` 子节点非空（防 JS/CSS 哈希 404 导致整屏蓝黑空白）并同步递增 `sw.js` Service Worker 缓存版本。
