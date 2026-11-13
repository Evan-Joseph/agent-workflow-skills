# Rare UI 核心组件目录与安装速查

---

## 一、 一键安装对照表

| 组件名称 | CLI 安装指令 | 典型应用场景 |
| :--- | :--- | :--- |
| **Fluid Orb** | `npx shadcn@latest add swamimalode07/rare-ui/fluid-orb` | AI 语音助手呼吸态、实时音频对话球、Agent 激活视觉中枢 |
| **Matrix Orb** | `npx shadcn@latest add swamimalode07/rare-ui/matrix-orb` | 数字矩阵科技感球体、后台集群监控中心 |
| **Folder Component** | `npx shadcn@latest add swamimalode07/rare-ui/folder-component` | 知识库、附件集、多文件归档的扇形展开预览 |
| **Duration Picker** | `npx shadcn@latest add swamimalode07/rare-ui/duration-picker` | 倒计时、专注时长设定、精密时间跨度调节 |
| **OTP Input** | `npx shadcn@latest add swamimalode07/rare-ui/otp-input` | 短信/邮箱验证码输入，单格槽位滚轮翻转显号 |
| **Gravity Letters** | `npx shadcn@latest add swamimalode07/rare-ui/gravity-letters` | 标题特效、创意品牌展示、物理重力弹跳文字 |
| **Proximity Sidebar** | `npx shadcn@latest add swamimalode07/rare-ui/proximity-sidebar` | 磁吸边缘导航栏，随鼠标接近产生距离形变吸附 |
| **Hook Sidebar** | `npx shadcn@latest add swamimalode07/rare-ui/hook-sidebar` | 悬挂式拉钩折叠侧栏 |
| **Gooey Nav** | `npx shadcn@latest add swamimalode07/rare-ui/gooey-nav` | 液体黏连果冻菜单，滑块切换产生水滴拉扯效果 |
| **Delete Button** | `npx shadcn@latest add swamimalode07/rare-ui/delete-button` | 具备危险确认形态变形与垃圾桶盖弹开动画的删除按钮 |
| **Notification Bell** | `npx shadcn@latest add swamimalode07/rare-ui/notification-bell` | 带有拟真左右轻摇晃与小红点 pop-in 的通知铃铛 |

---

## 二、 核心组件技术实现要点

### 1. 流体光球 (`Fluid Orb`)
- **实现原理**：基于 WebGL/Canvas 或多重滤镜组合（`mix-blend-mode`, `blur(30px)`, `hue-rotate` 动画），使用噪声函数（Simplex / Perlin Noise）驱动球体边缘不规则蠕动。
- **状态联动**：
  - `idle`：温和呼吸缩放（1.0 ~ 1.05），慢速渐变旋转；
  - `listening`：根据输入音量分贝振幅动态放大形变系数与色彩饱和度；
  - `thinking`：快速相位流动与多色环形交替。

### 2. 交互式文件夹展开 (`Folder Component`)
- **实现原理**：在 CSS 3D 变换空间内（`perspective: 1200px`），卡片外壳应用 `rotateX(-15deg)`，内部卡片依次施加 `translateY(-30px) rotate(-6deg)` 与 `translateY(-50px) rotate(6deg)`，形成自然的档案袋扇面散开效果。
