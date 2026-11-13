# Transitions.dev 32 款核心界面动效速查与应用决策

---

## 一、 动效决策树 (Decision Rules)

按用户界面的视觉元素与触发动作优先匹配：

| 触发场景 / 视觉元素 | 动效模式 | 推荐过渡 | 关键物理属性 |
| :--- | :--- | :--- | :--- |
| **触发器上浮现未读小红点 / 数字** | 徽标弹出 | `03-notification-badge` | 缩放弹跳 `--ease-bounce` + 45度斜向移出 |
| **点击后自触发器锚点生长出的浮层** | 下拉菜单 / Popover | `05-menu-dropdown` | `transform-origin` 贴合触发点 + 0.97 缩放 |
| **屏幕居中弹出的关键操作对话框** | 模态弹窗 | `06-modal` | 0.96 向上微弹 + 背景遮罩平滑淡入 |
| **屏幕边缘滑入的信息侧边栏** | 抽屉 / 面板揭示 | `07-panel-reveal` | X轴平移 + 2px 交叉微模糊滤镜 |
| **列表页 ↔ 详情页、向导步骤 1 ↔ 步骤 2** | 双页面左右滑动 | `08-page-side-by-side` | 视差偏移 (Parallax) + 3px 速度感模糊 |
| **容器尺寸随子内容动态自适应伸缩** | 卡片平滑重设尺寸 | `01-card-resize` | Grid `grid-template-rows: 0fr -> 1fr` |
| **按钮/卡片文字状态原位切换** | 文本翻转替换 | `04-text-states-swap` | 上升淡出 + 下方微模糊淡入 |
| **同一插槽内两种图标切换 (播放/暂停)** | 图标交叉变换 | `09-icon-swap` | 90度轻旋转 + 缩放淡入 |
| **操作成功 (支付完成/文件上传/复制)** | 成功对勾绘制 | `10-success-check` | SVG `stroke-dashoffset` 描边动态绘制 + 爆破感 |
| **表单校验未通过 / 密码错误** | 错误晃动 | `12-error-state-shake` | 左右衰减快速振荡 + 临时变红 |
| **搜索框内容一键清除** | 文本溶解飞散 | `13-input-clear-dissolve` | 文本逐字淡出 + 轻微右飞散 |
| **骨架屏加载完成替换真实内容** | 骨架平滑溶解 | `14-skeleton-reveal` | 灰条 Shimmer 淡出 + 真实 DOM 模糊显影 |
| **AI 生成中 / 文本加载状态** | 字体光泽扫描 | `15-shimmer-text` | `background-clip: text` 渐变横向匀速移动 |
| **分段控制器 / 选项卡切换** | 滑块指示器过渡 | `16-tabs-sliding` | 绝对定位胶囊滑块平滑插值移动 |
| **3D 视角与跟随鼠标光影** | 悬停卡片倾斜 | `19-card-tilt` | `perspective(1000px) rotateX/Y` + 径向渐变反射光斑 |
| **点赞 / 收藏交互** | 爱心粒子爆裂 | `23-like-button` | 心形缩放弹跳 + 环形扩散小圆点 |
| **数字滚动累加 / 计数更新** | 数字弹出 / 滚轮 | `02-number-pop-in`, `26-spinning-counter` | 垂直卷轴平移或逐位 Pop-in |
| **AI 思考展开 / 规划推理折叠** | 思考状态微光 | `28-thinking-states` | 状态标签呼吸扫描 + 下拉思考步骤平滑伸缩 |
| **大模型推理过程流式行向上滚动** | 推理流滚动 | `29-reasoning-stream` | 2行一组循环向上推移并自动淡出顶行 |
| **大模型打字机流式输出** | 流式文本渲染 | `30-streaming-text` | 新字词以 2px 模糊软粒子形态瞬时凝固显形 |

---

## 二、 重点动效核心代码模式

### 1. 模态框打开与关闭 (`06-modal`)
```css
.t-modal-backdrop {
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-smooth-out);
}
.t-modal-backdrop[data-state="open"] {
  opacity: 1;
}

.t-modal-content {
  opacity: 0;
  transform: scale(var(--scale-large)) translateY(8px);
  filter: blur(var(--blur-small));
  transition:
    opacity var(--duration-fast) var(--ease-smooth-out),
    transform var(--duration-fast) var(--ease-smooth-out),
    filter var(--duration-fast) var(--ease-smooth-out);
}
.t-modal-content[data-state="open"] {
  opacity: 1;
  transform: scale(1) translateY(0);
  filter: blur(0);
}
@media (prefers-reduced-motion: reduce) {
  .t-modal-content {
    transform: none !important;
    filter: none !important;
  }
}
```

### 2. 状态文本原位替换 (`04-text-states-swap`)
```css
.t-text-swap {
  display: inline-grid;
}
.t-text-swap > * {
  grid-area: 1 / 1;
  transition:
    opacity var(--duration-quick) var(--ease-in-out),
    transform var(--duration-quick) var(--ease-in-out),
    filter var(--duration-quick) var(--ease-in-out);
}
.t-text-swap > [data-active="false"] {
  opacity: 0;
  transform: translateY(-4px);
  filter: blur(2px);
  pointer-events: none;
}
.t-text-swap > [data-active="true"] {
  opacity: 1;
  transform: translateY(0);
  filter: blur(0);
}
```

### 3. 表单校验错误晃动 (`12-error-state-shake`)
```css
@keyframes t-shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(5px); }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(2px); }
}
.t-input-error {
  animation: t-shake 320ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}
```
