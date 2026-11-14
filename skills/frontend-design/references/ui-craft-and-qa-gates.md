# 前端组件分发命令与渲染自审细则 (`ui-craft-and-qa-gates.md`)

## 1. 组件 Registry 开箱安装命令

```bash
# 基础 shadcn/ui 组件
npx shadcn@latest add button card dialog dropdown-menu form input tabs

# Rare UI 单文件高触感组件
npx shadcn@latest add swamimalode07/rare-ui/fluid-orb
npx shadcn@latest add swamimalode07/rare-ui/folder-component
npx shadcn@latest add swamimalode07/rare-ui/duration-picker
npx shadcn@latest add swamimalode07/rare-ui/otp-input

# beUI 物理弹簧交互组件
npx shadcn@latest add https://beui.dev/r/tilt-card
npx shadcn@latest add https://beui.dev/r/bottom-sheet
npx shadcn@latest add https://beui.dev/r/message-scroller
```

## 2. 排版微细节与孤字小尾巴（Widow Wrap）治理细则

1. **同心圆角**：外层卡片与内嵌按钮/图片的圆角满足 $R_{\text{outer}} = R_{\text{inner}} + \text{Padding}$，避免尖角内层扎出圆润外框。
2. **零孤字小尾巴折行**：
   - 顶栏徽标、侧栏菜单项、底部单行提示栏与统计卡次要注记精炼文案并配合 `whitespace-nowrap` 保持单行；
   - 移动端（`390px`）选择题选项适度收紧水平内边距与右侧状态角标宽度，确保常规单句（12–18 字）单行容纳，避免第 2 行仅剩 1–4 个字；
   - 多行正文施加 `text-wrap: pretty`，标题施加 `text-wrap: balance`；必要时在 Playwright 中用 `Range.getClientRects()` 检查多行文本末行宽度占比（末行 `< 22%` 首行宽度时优化措辞或间距）。
3. **禁止贴标签式假重构**：严禁使用 `[切换]`、`↓`、`↑` 等纯文本方括号或 ASCII 符号冒充按钮与图标，一律使用原子交互组件（`SegmentedControl`、`Switch`、`Sheet`）与纯净矢量 SVG。

## 3. 四项交互态回归检查单

1. **展开态零裁切**：模拟点击展开手风琴、下拉项与抽屉，核对 `overflow: hidden/clip` 容器内选中态 `ring` / `scale` 未被边缘截断。
2. **开关往返与副作用**：对静音、震动、通知、深浅色等开关执行 `On -> Off -> On` 往返实测，确认底层副作用同步生效。
3. **多视口与数学公式渲染**：覆盖桌面（`1440×900`）、平板（`768×1024`）、手机竖屏（`390×844`）与手机横屏（`844×390`）；含公式文本统一走公式渲染组件，禁止用字符串长度阈值跳过短公式，禁止裸露 `\qquad` / `\texttt`。
4. **线上部署根节点核验**：部署后确认 `#root` / `#app` 实际挂载非空（防静态资源哈希 404 白屏）并同步递增 `sw.js` 缓存版本。
