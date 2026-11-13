# Rare UI — 稀缺触感交互组件库

> 官方源：[rareui.com](https://rareui.com) | 创作者：Swami Malode | 理念：Rare & Tactile Animated React Components · Single File Ownership

---

## 一、 核心特色与理念

1. **打破同质化模板感 (Distinct & Playful)**：
   - 传统组件库大多停留在规整的矩形按钮与常规模态框。Rare UI 专注提供极具视觉辨识度、物理质感与微反馈的“高记忆点”组件。
   - 典型案例：拟态流体发光球体 (Fluid Orb)、矩阵点阵球 (Matrix Orb)、物理重力掉落字母 (Gravity Letters)、触感滚轮时长选择器 (Duration Picker)、交互式文件夹折叠散开 (Folder Component)。
2. **单文件即用与零膨胀 (Single-File Ownership)**：
   - 每一个组件就是一个自包含的独立文件，不强加复杂的庞大 monorepo 运行包。
3. **shadcn CLI 标准分发生态**：
   - 直接通过官方推荐命令一键拉取进用户工程：
     ```bash
     npx shadcn@latest add swamimalode07/rare-ui/<component-name>
     ```

---

## 二、 组件矩阵与适用场景

- **AI 与生动状态类 (AI Kit)**：
  - `fluid-orb`：声波/呼吸自适应形变的有机发光球体，极度适合作为 AI 语音助手、实时对话监听或计算中状态的核心视觉锚点。
  - `matrix-orb`：基于数字化点阵的旋转三维球体，适合科技感、密码学或底层计算基础设施场景。
  - `grid-reveal`：网格扫描显隐过渡。
- **物理与趣味展示类 (Display)**：
  - `gravity-letters`：页面加载或悬停时文字拆解为具备物理刚体碰撞重力的自由掉落字母。
  - `folder-component`：点击文件夹封面，内部文档以扇形层叠滑出展开。
  - `step-player`：分步操作引导动画控制器。
  - `github-activity`：仿 GitHub 贡献热力图的轻量交互组件。
- **触感控制与输入类 (Inputs & Navigation)**：
  - `duration-picker`：仿精密机械仪表的时长微调滚轮。
  - `proximity-sidebar`：光标靠近边缘时，侧边栏图标自动向光标产生磁性距离引力（Distance-sensitive proximity）。
  - `gooey-nav`：液态果冻黏连拉丝的导航滑块。
  - `otp-input`：验证码输入框，每一位输入时伴随老虎机式数字垂直弹动与对勾绘制。
