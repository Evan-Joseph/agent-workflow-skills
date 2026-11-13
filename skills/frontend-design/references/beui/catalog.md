# beUI 核心组件清单与安装调用指南

---

## 一、 Agent 安装调用流 (Agent Integration Flow)

在向用户工程添加 beUI 组件时，推荐标准化执行：
1. **查询端点**：读取 `https://beui.dev/r/{slug}` 获取组件的完整文件结构与依赖关系。
2. **下载或生成**：
   - 使用 shadcn CLI：`npx shadcn@latest add https://beui.dev/r/{slug}`
   - 或直接拉取代码放至 `@/components/motion/{slug}.tsx`
3. **外部依赖声明**：通常需要安装 `motion`（或 `framer-motion`）与 `clsx`, `tailwind-merge`。

---

## 二、 重点组件应用决策

| 场景需求 | 对应 beUI 组件 | 特征与参数 |
| :--- | :--- | :--- |
| **产品功能亮点展示卡片** | `tilt-card` | 鼠标悬停 3D 俯仰，随光标移动投射径向反射高光（Glare） |
| **移动端底部抽屉与筛选** | `bottom-sheet` | 惯性滑动、多挡吸附点（Snap points）、磨砂毛玻璃底衬 |
| **移动端/长列表触顶刷新** | `pull-to-refresh` | 真实阻尼感拉伸、阈值触感反馈、异步加载完成回弹 |
| **紧凑型刻度导航 (Codex 同款)** | `preview-rail` | 鼠标滑过连续刻度形成金字塔放大效应，浮动显示目标页面缩略图 |
| **页面流光与动态背景** | `shader-background` | WebGL Canvas 着色器（Mesh Gradient, Voronoi, Waves, Grain） |
| **数字累加与统计面板** | `number` | 滚动跑马灯式数字跳变，支持数字平滑 Roll 动 |
| **全屏主题昼夜模式切换** | `theme-toggle` | 基于原生 View Transition API，圆形剪裁或横向百叶窗全屏扩散 |
| **多页面视图弹窗展开** | `morphing-modal` | 弹窗在内部多步骤切换时，面板高度与宽度自动弹簧拉伸，内容交叉淡入 |
| **大模型对话自动滚屏** | `message-scroller` | 智能视口：流式输出时自动钉紧底部；用户向上翻阅时自动脱钩，防止抢夺焦点 |

---

## 三、 典型代码示例：3D 悬停倾斜卡片 (`TiltCard`)

```tsx
"use client";

import React, { useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

export function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 300, damping: 30 });
  const mouseYSpring = useSpring(y, { stiffness: 300, damping: 30 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ["12deg", "-12deg"]);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ["-12deg", "12deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    x.set(mouseX / width - 0.5);
    y.set(mouseY / height - 0.5);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={`relative rounded-2xl border border-line bg-surface p-6 shadow-card transition-shadow duration-300 hover:shadow-2xl ${className}`}
    >
      <div style={{ transform: "translateZ(30px)" }}>{children}</div>
    </motion.div>
  );
}
```
