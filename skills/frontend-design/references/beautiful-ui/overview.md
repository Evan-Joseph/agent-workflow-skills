# Beautiful UI — AI 原生交互原语体系

> 官方源：[beautifului.dev](https://beautifului.dev) | 创作者：Turbo Design Studio | 理念：Crafted Primitives for AI-Native Interfaces

---

## 一、 为什么需要 AI 原生交互原语

传统的 Web UI 组件库（Bootstrap、Ant Design、常规 Element）是围绕“人点按、人输入、人浏览”设计的。
随着大模型 Agent、自主编码、自动化审批与流式推理的普及，用户界面面临全新的人机协同需求：
1. **非阻塞等待与思考展开 (Thinking & Reasoning Traces)**：模型在后台进行多步推理、工具调用、代码修改时，用户需要清楚看到进度（不是干等全局 Spinner，而是可折叠展开的推理流）。
2. **人机协同审批卡片 (Human-in-the-Loop Approvals)**：Agent 准备执行不可逆操作（写库、扣费、对外发信、覆盖本地文件）前，需要一种体验优雅、支持单选/多选/自定义输入、支持一键跳过或确认的专用卡片。
3. **流式 Markdown 与行内实体对齐 (Streaming with Grounded Sources)**：文字流式显形、行内引用标签（带域名 Favicon 堆叠）、追问引导按钮（Follow-ups）。
4. **工具调用芯片与差量审查 (Tool Chips & Diff Tables)**：将长篇终端日志收敛为紧凑的状态芯片，点击展开带行号与高亮的分屏/统一代码差异对比。

---

## 二、 核心原语组件库概览

| 组件分类 | 代表原语 | 交互特征 |
| :--- | :--- | :--- |
| **状态呈现** | `Loading State`, `Thinking State` | 像素网格装载器（Drive/Dots/Orbit/Surfer 变体）、耗时统计秒数、Thinking 微光与 4 阶段（Steps / Reasoning / Search / Coding）折叠展开 |
| **流式交互** | `Streaming Text`, `Chat Composer`, `Prompt Bar` | 文字柔和模糊显影、行内数据源堆叠药丸、点赞/复制/重新生成底部工具条、输入框自增高与模型选择 |
| **人类把关** | `Approval Card`, `Selection Actions` | 滑块式选项菜单（Glide Menu）、手写补充建议框、题目分页指示器（如 `1 / 3`）、一键 Skip 与 Submit |
| **执行监控** | `Tool Chips`, `Task Rows` | 工具调用状态胶囊（成功/运行中/失败）、任务行（带动态进度圆环与详细日志二级抽屉） |
| **结构化输出** | `Diff Table`, `Records Table`, `Filter Table`, `Context Cards` | 带有增删行标记的代码对比、轻量化数据库记录检视、实体卡片推荐 |

---

## 三、 依赖与技术栈约定

- **框架**：React 19 / Next.js (App Router, Client Components)
- **样式**：Tailwind CSS (v3 / v4)
- **动效**：原生 CSS 关键帧 + CSS 变量过渡；复杂高度自适应采用 `grid-template-rows: 0fr -> 1fr`
- **图标**：Lucide React
- **色彩 Token**：语义化变量 `--ink`, `--ink-2`, `--ink-3`, `--canvas`, `--surface`, `--hover`, `--line`
