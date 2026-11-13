# beUI — 高质感 Motion 动效与组件生态

> 官方源：[beui.dev](https://beui.dev) | 创作者：Saurabh | 理念：Animated Components for React & Next.js · Built with Motion & Tailwind

---

## 一、 核心架构与定位

1. **Motion 驱动的物理弹簧质感**：
   - 深度基于 `framer-motion`（或全新轻量级 `motion` 库），组件拥有惯性、阻尼回弹（Spring Physics）、手势拖拽（Drag Inertia）与共享布局连续性（Shared Layout `layoutId`）。
2. **shadcn CLI 深度兼容与 Open Registry**：
   - 采用标准 shadcn Registry 规范。可通过 CLI 直接一键安装或拉取组件源码：
     - **Registry Index**: `https://beui.dev/r`
     - **单个组件 JSON**: `https://beui.dev/r/{slug}`
     - **纯文本源码**: `https://beui.dev/r/{slug}/raw`
     - **Markdown 规范**: `https://beui.dev/components/{category}/{slug}.md`
     - **AI 上下文规范**: `https://beui.dev/llms.txt`
3. **极佳的性能与无障碍兜底**：
   - 每一个 Motion 组件均内置 `useReducedMotion` 监听。当系统开启减弱动画时，组件自动剥离激进的 3D 旋转与大范围滑移，转为沉稳的透明度淡入淡出（Calm Opacity Pulse）。

---

## 二、 核心组件三大版块

1. **Motion Primitives (基础动效原语)**：
   - **卡片与容器**：Tilt Card (3D 悬停倾斜与光斑跟随)、Center Morph Modal (从中心向四周如折纸般展开)、Bottom Sheet (仿 iOS 弹力抽屉与吸附点)、Cylinder Carousel (3D 滚筒圆柱旋转轮播)、Shader Background (原生 Canvas WebGL 梯度/波纹/网格/流体着色器背景)。
   - **交互控件**：Spring Button (含 Stateful / Magnetic / Metallic 三种变体)、Adaptive Stepper (数字卷轴滚动步进器)、Preview Rail (Codex 同款悬停金字塔刻度导航轨)、Dock (macOS 风格弹性动作坞)、iOS 滚轮选择器 (Wheel Picker)、动态标签页 (Morphing Tabs & Expandable Tabs)。
2. **Agent Primitives (对话与智能体工程原语)**：
   - **消息与阅读流**：Message Scroller (具备读者意识的会话视口，自动贴合最新流式边缘，用户回滚时主动释放锁定)、Message Bubble (独立气泡编组与新增行微弹动画)。
   - **执行与审查**：File Diff (带行号的平滑语法高亮差量对比)、Tool Result (终端输出执行结果折叠卡片)、Todo List (带状态变形动画的 Agent 执行规划清单)、Citations (内嵌引用角标与可折叠参考资料库)。
3. **Interactive Blocks (复合界面功能块)**：
   - **动态岛 (Dynamic Island)**：仿 iOS 灵动岛药丸，在后台任务、音频播放、审批状态间平滑拉伸变形。
   - **指令面板 (Command Palette)**：⌘K 快速启动面板，带模糊匹配过滤与磨砂玻璃质感。
   - **开花菜单 (Bloom Menu)**：按钮在点击时由中心向四周径向绽放展开网格选项。
   - **404 创意页**：故障打乱 (Glitch Scramble)、磁性数字、聚光灯追踪等多种高审美缺省页。
