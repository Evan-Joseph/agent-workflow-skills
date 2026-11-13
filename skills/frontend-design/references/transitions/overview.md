# Transitions.dev 动效体系与语义化令牌

> 官方源：[transitions.dev](https://transitions.dev) | 仓库：`Jakubantalik/transitions.dev` | 理念：Zero-dependency Pure CSS · Namespaced (`t-*`) · Accessible

---

## 一、 核心设计定位

1. **纯 CSS 零运行时开销**：
   - 不依赖 JS 动画库（Framer Motion、GSAP），仅依靠浏览器原生 GPU 加速属性（`transform`, `opacity`, `filter: blur()`, `clip-path`）完成高保真过渡。
2. **命名空间与自包含 (`t-*`)**：
   - 所有类名与关键帧采用 `t-*` 命名空间，杜绝与 Tailwind 或项目业务样式冲突。
3. **强制无障碍守卫 (Reduced Motion Guard)**：
   - 每个动效片段必须包含 `@media (prefers-reduced-motion: reduce)` 分支，在系统开启减弱动态效果时平稳退化为即时切换或轻微透明度过渡。

---

## 二、 全局语义化动效令牌 (`_root.css`)

在项目全局 CSS（如 `app/globals.css` 或 `index.css`）中注入一次统一动效尺度：

```css
:root {
  /* ── 时长尺度 (Durations) ── */
  --duration-stagger: 40ms;     /* 列表项交错递进偏移 */
  --duration-micro: 80ms;       /* Tooltip 延迟、晃动段落、微反馈 */
  --duration-quick: 150ms;      /* 浮层关闭、文本切换、轻量展开 */
  --duration-fast: 250ms;       /* 按钮图标切换、下拉展开、Tab 滑块、页面平移 */
  --duration-medium: 350ms;     /* 抽屉收起、Toast 退出 */
  --duration-slow: 400ms;       /* 抽屉滑入、骨架屏消隐换入、输入框清除 */
  --duration-very-slow: 500ms;  /* 强调仪式感瞬间、成功对勾绘制、大卡片翻转 */

  /* ── 缓动曲线 (Easings) ── */
  --ease-smooth-out: cubic-bezier(0.22, 1, 0.36, 1);  /* 现代阻尼感，最常用的开合与滑动 */
  --ease-in-out: ease-in-out;                         /* 对称状态翻转 (图标、文本) */
  --ease-out: ease-out;                               /* 轻量提示框浮现 */
  --ease-linear: linear;                              /* 骨架屏扫描、文字微光 Shimmer */
  --ease-bounce: cubic-bezier(0.34, 1.36, 0.64, 1);   /* 徽标弹跳进入 */
  --ease-bounce-strong: cubic-bezier(0.34, 3.85, 0.64, 1); /* 强回弹悬浮 */

  /* ── 物理距离 (Distances) ── */
  --distance-micro: 4px;        /* 文本上下微翻转 */
  --distance-small: 6px;        /* 表单校验轻微晃动 */
  --distance-base: 8px;         /* 徽标对角线浮现、页面轻滑动 */
  --distance-medium: 12px;      /* 文本段落错落浮现 */
  --distance-large: 30px;       /* 大卡片进入 */

  /* ── 缩放尺度 (Scales) ── */
  --scale-large: 0.96;          /* 模态框打开起始缩放 */
  --scale-medium: 0.97;         /* 下拉菜单打开起始缩放 */
  --scale-small: 0.98;          /* Tooltip 打开起始缩放 */
  --scale-tiny: 0.99;           /* 下拉菜单关闭微缩 */

  /* ── 运动模糊 (Motion Blur) ── */
  --blur-small: 2px;            /* 面板浮现、文本切换、数字跳变 */
  --blur-medium: 3px;           /* 页面切换跨步模糊 */
  --blur-large: 8px;            /* 成功勋章弹出光晕 */
}
```

---

## 三、 工程应用模式

当任务需要添加界面微交互时：
1. **优先提取语义需求**（例如：模态框需要打开缩放、数字变更需要滚动跳变、按钮点击后需要成功绘制对勾）。
2. **查阅 `catalog.md` 选取对应编号的实现模板**。
3. **保持属性只驱动 `transform`, `opacity`, `filter`**，杜绝触发布局重排（Reflow）的 `width`, `height`, `top`, `left` 暴力过渡。
