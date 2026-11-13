# UI Polish Microdetails

本文件用于把「make interfaces feel better」一类 UI 微质感经验落地为本机可执行检查规则。来源参考：

- Jakub Krehel, Details That Make Interfaces Feel Better: https://jakub.kr/writing/details-that-make-interfaces-feel-better
- Agent Skill: https://github.com/jakubkrehel/make-interfaces-feel-better
- React Native adaptation: https://github.com/andersendank/make-rn-interfaces-feel-better

采用原则：吸收完整主题域，按本机工作流重写为可审查、可实现、可验证的规则；不整包复制外部文本。

## When To Load

读取本文件当任务涉及：

- 用户说界面粗糙、不顺、廉价、AI 感、像 demo、缺质感、交互生硬、动画难受。
- 用户要求 polish、micro-interaction、hover/press 状态、UI feels better、make it feel better。
- 正在实现按钮、卡片、导航、表格、图片、动态数字、切换态、进入/退出动画。
- 交付前做视觉细节审查、响应式检查或深浅色模式检查。
- React Native、Expo 或移动端 UI 需要 polish、Pressable 反馈、hitSlop、safe-area、Android elevation、Reanimated 等平台细节。

## Typography

### Text Wrapping

- 标题、短促标题组、卡片标题默认考虑 `text-wrap: balance` 或 Tailwind `text-balance`。
- 段落、说明文字、caption、列表项等短到中等长度正文默认考虑 `text-wrap: pretty` 或 Tailwind `text-pretty`。
- 超长正文、代码块、预格式化文本不要强行使用 `balance`；让浏览器默认换行即可。
- 中文标题也要检查孤行、挤压和断句；不要只因为英文规则存在就机械套用。

### Font Smoothing

- Web 项目可在根节点应用 macOS 抗锯齿，例如 Tailwind `antialiased`。
- 不要在零散元素上分别设置字体平滑，避免同一页面字重观感不一致。

### Tabular Numbers

- 动态计数、价格、倒计时、表格数值、仪表盘指标、排行榜分数使用 `font-variant-numeric: tabular-nums` 或 Tailwind `tabular-nums`。
- 静态装饰数字、版本号、电话号码、邮编不默认使用。
- 使用 Inter 等字体时要看一眼数字 `1` 的观感，确认等宽数字没有破坏视觉平衡。

## Surfaces

### Concentric Radius

- 嵌套圆角元素靠得很近时，外层半径应等于内层半径加两者之间的间距。
- 示例关系：内层 `8px`，间距 `8px`，外层通常取 `16px`。
- 如果间距大于约 `24px`，可把两层看作独立表面，不必硬套同心圆角。
- 同一张卡片里父子元素都用同一个 `rounded-xl` 是常见粗糙来源，审查时优先检查。

### Optical Alignment

- 图标和文字共存时，不只看几何居中，要看视觉重心。
- 文字加右侧箭头的按钮，图标侧 padding 可比文字侧少约 `2px`，再截图确认。
- 播放三角、箭头、星形等非对称图标可轻微偏移；最好修 SVG viewBox/path，其次才用 margin。
- 对齐修正必须服务观感，不要把每个图标都机械偏移。

### Icons

- 图标描边粗细要与相邻文字字重和控件视觉密度协调，避免细线图标贴着粗体文字或反过来。
- 图标默认继承 `currentColor`，让 hover、disabled、selected 和主题切换由控件状态统一驱动。
- 同一控件的未选中/选中状态优先使用同一图标家族的 outline/fill 变体，不混用不同图标库制造形状和 viewBox 漂移。
- 带方向语义的箭头、返回、前进图标在 RTL 布局中要翻转；播放、下载、勾选等无方向语义图标不要机械翻转。

### Shadows And Borders

- 卡片、按钮、弹层、下拉框等需要深度的容器，优先考虑透明阴影或 shadow ring，而不是硬边框。
- 需要自然深度时优先叠加多层低透明阴影，不要用一条硬边框假装层级。
- 分割线、表格边界、输入框可访问性描边、密集列表分隔仍可使用 border。
- 浅色模式可用多层低透明黑色阴影形成 1px 视觉边和轻微抬升。
- 深色模式中复杂黑色阴影通常不可见，优先用低透明白色 ring。
- hover 只改变需要变化的属性，如 `box-shadow`、`background-color`、`opacity`、`transform`。

### Image Outlines

- 图片、截图、封面图在浅色模式下可加 `outline: 1px solid rgba(0, 0, 0, 0.1)`。
- 深色模式下可加 `rgba(255, 255, 255, 0.1)`。
- 使用 inset outline 或 `outline-offset: -1px`，避免改变布局尺寸。
- 不要用 slate、zinc、neutral 等带色相的近黑/近白描边给图片收边，容易显脏。

### Hit Areas

- 交互元素目标区域至少接近 `40x40px`；移动端和重要控件优先按 `44x44px` 检查。
- 视觉尺寸较小的 checkbox、icon button、slider thumb 可用伪元素扩展命中区域。
- 扩展命中区域不能和相邻可点击元素重叠。

## Animations

### Interruptible Interaction

- hover、press、toggle、drawer open/close 等响应用户意图的状态变化，用 CSS transition 或可中断 motion。
- keyframes 适合一次性编排，例如页面入场、加载提示、庆祝动效；不要用它驱动可反复打断的交互状态。
- 动画过程中用户反向操作时，界面应平滑转向新状态，不应重播、闪断或跳变。

### Enter Animations

- 入场动画不要只包一个大容器一起动。按标题、说明、按钮、列表项等语义块拆开。
- 常用组合：`opacity`、小幅 `translateY`、轻微 `blur`。
- 块之间 stagger 控制在约 `80-120ms`；标题拆词时可更短。
- 企业后台、数据密集界面要克制，优先服务可扫描性。

### Exit Animations

- 退出动效应比入场短、轻、少抢注意力。
- 常用方式：小幅固定 `translateY` 或只用 `opacity + blur`。
- 不要用全高度飞出、大比例缩放或过长退出动画处理普通列表项和弹层内容。
- 真正表达空间关系的场景，例如抽屉回收、卡片回到列表，才使用更完整的空间位移。

### Contextual Icon Animation

- hover 后出现的操作图标、状态切换图标、播放/暂停、收藏/已收藏等，优先用 `opacity + scale + blur` 过渡，不要硬切显示。
- 若项目已有 `motion` 或 `framer-motion`，可用现有库；不要为单个图标动效新增依赖。
- 无 motion 依赖时，可把两个状态图标都留在 DOM 中，一个绝对定位叠放，通过 CSS 交叉淡入淡出。
- 常用尺度：进入从 `scale(0.25)` 到 `1`，`opacity` 从 `0` 到 `1`，模糊从约 `4px` 收到 `0`，持续约 `300ms`，不要明显反弹。
- 使用 Framer Motion 时，图标切换默认用 `transition: { type: "spring", duration: 0.3, bounce: 0 }`。没有 motion 依赖时，CSS 交叉淡入淡出可用 `cubic-bezier(0.2, 0, 0, 1)`。
- 默认态元素首屏不应无故播放切换动画；使用 AnimatePresence 时可按场景考虑 `initial={false}`。

### First-Mount Animation

- 默认已经处于页面初始状态的元素，不要在首屏加载时播放“状态切换”动画。
- Framer Motion / AnimatePresence 中，非 hero 的默认态图标、toggle、tab、segmented control 可用 `initial={false}` 或挂载标记跳过首挂载动画。
- 真正有叙事作用的 hero、标题组或首屏入场可以保留入场编排，但要截图确认没有抢内容、遮挡或延迟可读性。

### Scale On Press

- 普通按钮可用轻微按压反馈，例如 `active:scale-[0.96]`。
- 不要低于 `0.95`，否则像玩具化夸张反馈。
- 需要严肃、稳定或 motion 会干扰阅读的控件，提供关闭按压缩放的路径。

### Reduced Motion

- 所有非必要 motion 都要考虑 `prefers-reduced-motion`。
- 用户要求极简、严肃、专业、可访问性优先时，少用进入编排，多用明确状态、对比和布局。

## Performance

### No `transition: all`

- 禁用 `transition: all` 和 Tailwind 泛化 `transition` 来偷懒。
- 精确写变化属性，例如 `transition-[opacity,transform]`、`transition-colors`、`transition-[box-shadow]`。
- 原因：避免无关属性参与动画、避免意外过渡、降低浏览器优化成本。

### `will-change`

- 只在发现首帧卡顿时添加，不要预防性铺满。
- 可考虑的属性：`transform`、`opacity`、`filter`、`clip-path`。
- 不要写 `will-change: all`。
- 大量 `will-change` 会增加合成层和内存压力；动画结束后能移除就移除。

## React Native And Mobile Appendix

仅在 React Native、Expo 或移动端 UI 项目中应用本节。不要把 RN 规则机械套到 Web 项目。

### Preflight

- 先确认平台目标：是否真的发布 Android。看真实 `android/` 目录、EAS/构建配置和项目说明；不要只凭 `app.json` 里的 `android` 字段判断。
- 先读设计 token：radius、shadow、spacing、font、color、platform override。token 明确时，token 优先；紧贴嵌套元素仍要检查同心圆角。

### Surfaces

- iOS 阴影用 `shadowColor`、`shadowOffset`、`shadowOpacity`、`shadowRadius`；Android 深度用 `elevation`。如果 Android 是发布目标，普通卡片/按钮应同时考虑两套。
- 如果项目是 iOS-only，不要因为缺少 `elevation` 报问题。先看真实 `android/` 目录、EAS/构建配置和项目说明。
- `elevation` 不能表达方向性阴影，也不能可靠表达透明 alpha 形状的 silhouette shadow；这类场景接受跨平台差异或调整实现。
- Silhouette shadow 场景中，iOS 可让容器 `backgroundColor: 'transparent'`，让阴影跟随透明素材或异形内容的 alpha 轮廓；Android `elevation` 不等价，不能硬套。
- 真正分割线用 `StyleSheet.hairlineWidth`，不要用 `1` 造成高密度屏粗线；但拟物 bevel、inset、深度边不是普通 divider，不要误改成 hairline。
- RN 没有 Web `outline`。图片描边可用 `borderWidth`，会影响布局；不能改变尺寸时用绝对定位 overlay。
- 透明/异形图片不要套矩形描边，优先通过 silhouette shadow 或素材本身处理深度。

### Touch And Platform Feedback

- 小图标和 checkbox 用 `hitSlop` 扩展触控区域，目标接近 iOS `44x44`、Android `48dp`。
- `hitSlop` 不影响布局，但不能和相邻控件命中区域重叠。
- 使用 `Pressable` 的 `style={({ pressed }) => ...}`、`android_ripple`、`onPressIn/onPressOut`、`pressRetentionOffset`，不要把 Web hover 语义硬搬到移动端。
- Android 常用 ripple，iOS 常用 opacity 或轻微 scale。一个界面内按压反馈应统一。
- 不要硬编码刘海、状态栏、home indicator 的 padding；用 `react-native-safe-area-context` 的 `useSafeAreaInsets()` 或带明确 `edges` 的 `SafeAreaView`。

### Motion And Performance

- RN 没有 `transition: all`，但同样要精确指定动画值。优先动画 `transform` 和 `opacity`。
- 不要用每帧动画驱动 `width`、`height`、`flex`、`margin`、`padding`、`top`、`left` 等布局属性；需要尺寸变化时优先用 scale 或先定最终布局再做视觉过渡。
- 交互动画优先用 Reanimated shared values、`withTiming`、`withSpring`、`useAnimatedStyle`，让帧在 UI thread 上计算。
- 旧 `Animated` API 必须确认 `useNativeDriver: true` 可用；它只适合 `transform` 和 `opacity` 等属性。
- `react-native-svg` 在部分新架构版本下不能直接由 Reanimated props 驱动；连续复杂动画优先考虑 Skia，低频动画可用 `requestAnimationFrame + setState`，并按项目版本验证。
- chrome、toggle、tab 等界面控件默认避免明显 overshoot；拖拽释放、手势跟随才更适合弹簧感。
- Reanimated layout `entering` 默认首挂载会播放；默认状态元素要避免每次启动都乱入场，真正的 hero 首屏入场除外。

### Typography

- RN 没有 `text-wrap: balance` / `pretty`，不要承诺自动消除孤行。可用 `numberOfLines`、`adjustsFontSizeToFit`、手动换行或 Android `textBreakStrategy` 做有限处理。
- RN 没有 `-webkit-font-smoothing`。自定义字体要用 `expo-font` 或 bare workflow 字体配置，并在字体加载完成前控制首屏渲染。
- 动态数字用 `fontVariant: ['tabular-nums']`；如果该数字使用 monospace 字体则通常不需要。

## Review Output Contract

审查 UI 微质感时，输出必须可执行，不写泛泛建议。

推荐表格：

| Principle | Before | After | Evidence |
|---|---|---|---|
| Concentric radius | 父子元素同为 `rounded-xl` | 外层按内层半径加 padding 调整 | 文件、组件或截图位置 |

规则：

- 只列真实发现或真实修改，不放空表。
- 每行聚焦一个差异，避免一行混多个改动。
- 能指向文件、组件、CSS 属性或截图位置时必须指向。
- 如果是实现任务，最终说明改了哪些文件、跑了什么验证。
- 如果只是建议任务，给可直接交给实现者的 CSS/组件约束。

## Pre-Delivery Gate

交付前至少检查：

- 标题和短正文没有难看的孤行、挤压和横向滚动。
- 动态数字不会因为数字宽度变化导致布局跳动。
- 嵌套圆角符合视觉关系。
- 图标按钮、播放按钮、箭头等视觉重心没有偏。
- 卡片、按钮、图片的边缘在浅色和深色模式下都干净。
- hover、press、focus、disabled、loading、active 状态齐全。
- 动画能被打断，退出动画短于入场动画。
- 没有 `transition: all`、`will-change: all`。
- 小控件命中区域足够，命中区域不互相覆盖。
- 在 375px、768px、1024px、1440px 视口下没有文本溢出、遮挡和横向滚动。

React Native/Expo 额外检查：

- Android 发布目标下普通阴影有对应 `elevation`，但 silhouette/directional shadow 不硬套。
- 分割线使用 `StyleSheet.hairlineWidth`，拟物深度边不误改。
- 小控件用 `hitSlop`，且命中区域不重叠。
- safe-area 由 `useSafeAreaInsets()` 或明确 `edges` 管理。
- Pressable 反馈符合平台习惯，Android ripple/iOS opacity 或 scale 不混乱。
- 动画在 UI thread 上驱动，避免每帧布局动画。
- RN 文本换行和字体平滑按平台能力处理，不套 Web 专属规则。
