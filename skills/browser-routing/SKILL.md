---
name: browser-routing
description: "所有本机浏览器操作与自动化测试的前置路由总控。规范日常登录态 Chrome（:9223 v4 持久守护中继 + cdp-ctl 语义分组）、Localhost Playwright 调试与 Camoufox 调研。强制零焦点抢占、大模型按任务语义自拟折叠标签组、openerId 子弹窗自动继承与收尾零残留。"
metadata:
  short-description: 浏览器自动化路由、:9223 v4语义分组与零残留总控
---

# Browser Routing & `:9223` v4 Governance

所有浏览器任务先选对通道，严守**零焦点抢占**与**收尾零孤儿标签**两条铁律。

## 运行时契约 (Runtime Contract)

- **`:9223` 持久守护控制与人机接力**（`homebrew-stdlib` -> `python3`）：
  - 统一入口：`cdp-ctl`（[`scripts/cdp_ctl.py`](./scripts/cdp_ctl.py)，自动同步 `0600` `DevToolsActivePort` 规避 `com.apple.macl` 弹窗）；
  - 图形验证通知接力：[`scripts/notify_human_handoff.py`](./scripts/notify_human_handoff.py)（默认 `AgentHandoffNotifier.app` `Alerts` 常驻样式，点击精准展开对应 Chrome 标签页）。
- **匿名反爬沙盒**（`camoufox` -> `python3`）：[`scripts/camoufox_profile.py`](./scripts/camoufox_profile.py)。
- **防呆红线**：严禁自建临时 `venv` 或随意 `pip install`。

## 一、 四通道选型路由

| 场景需求 | 唯一通道 | 关键边界 |
| :--- | :--- | :--- |
| **需要日常 Chrome 已登录态**（社媒、教务、控制台） | `${CDP_RELAY_URL}`（首选 `cdp-ctl`） | **严禁直连 `:9222`**（触发远程调试弹窗）；**严禁裸调 `open` 或 `open -g -a "Google Chrome"`**（产生脱离分组的孤儿页且易误开 Safari） |
| **Localhost 前端验收 / 破坏性交互回归** | 无头 Playwright / `@playwright/mcp` | 隔离沙盒运行，禁止挂载日常 Chrome 默认 User Data Dir 抢占 `SingletonLock` |
| **免登录公开页极速语义快照** | `agent-browser` CLI（`open` -> `snapshot -i` -> `close`） | 精简语义树节省上下文，用毕立即 `close` |
| **LCP / Heap / CSS / A11y 深度性能诊断** | `chrome-devtools` MCP（`~/.local/bin/chrome-cdp-mcp`）或 `:9223` | 默认 `--headless --isolated`；详细诊断流程见 [`references/web-vitals-a11y-cookie-memory-debugging.md`](./references/web-vitals-a11y-cookie-memory-debugging.md) |

## 二、 `:9223` v4 语义标签组与全生命周期零残留规范

登录态持久保存在 Chrome Profile 的 Cookie / IndexedDB 中，**绝不需要靠挂着“常驻标签页”保活**。`chrome_cdp_daemon.js` v4 采用语义任务分组与全自动衍生页回收（完整 HTTP 协议速查见 [`references/cdp-9223-v4-protocol.md`](./references/cdp-9223-v4-protocol.md)）：

1. **大模型按任务语义自拟简洁组名（默认折叠）**：
   - 打开页面统一调用 `cdp-ctl open --url "<URL>" --task "<task-id>" --group "<2-8字任务语义名>" --reuse`（如 `--group "推免名册"`、`--group "小红书检索"`、`--group "论文状态"`），不加生硬的机械前缀，绝不建“常驻复用”垃圾桶分组。
   - 多步长流程若需延长空闲存活（2h TTL），传 `--resident`——**`resident` 仅是该标签的生命周期属性，页面依然待在所属的任务语义分组内**。
2. **子弹窗、附件下载页与 `brain/` 工件页自动继承（`openerId` Inheritance）**：
   - 在受管标签页内点击链接弹出的新标签/附件下载页（带 `openerId`）以及 `file:///.../.gemini/antigravity/brain/` 本地工件页，v4 守护自动将其收养进父标签所属的同一折叠语义分组。
3. **收尾一键清零（`0` 残留硬门禁）**：
   - 除非明确需要将最终交付页留给用户审阅（显式传 `--keep-for-user`），任务一旦结束必须在 `finally` 中调用 `cdp-ctl cleanup --task "<task-id>"`，连同所有衍生子页一并 `about:blank -> close` 清空，并通过 `cdp-ctl tabs` 确认 `agentTabsCount == 0`。

## 三、 零焦点抢占与特殊交互红线

1. **焦点仿真替代窗口置顶**：`:9223` 自动对后台标签启用 `Emulation.setFocusEmulationEnabled({ enabled: true })`，严禁调用 `Target.activateTarget`、`Page.bringToFront` 或 `osascript` 抢占用户前台窗口。
2. **移动端 Touch 仿真即用即清**：在有头 Chrome 临时启用 `setTouchEmulationEnabled` 或 `setDeviceMetricsOverride` 后，单步结束前必须立即关闭并 `clearDeviceMetricsOverride`，防止锁死用户桌面滚轮与点击。
3. **在线测评防失焦 HUD**：面对带 `onblur` / `visibilitychange` 切屏计数的测评页，禁止打开独立外部工作台，统一在页内注入 **Closed Shadow DOM 隐形悬浮 HUD**。
4. **前端多视口真图自审**：UI 验收须覆盖桌面（`1440×900`）、手机竖屏（`390×844`）与手机横屏（`844×390`），验证展开态无裁切、开关往返有效，并截取 `<150 KB` JPEG 亲自调 `read_file` 目检。

## 四、 图形人机验证通知接力 + 邮箱/短信 OTP 自动接管

当 `:9223` 后台页遇到 Turnstile / GoCaptcha / hCaptcha 等**图形验证**时，**严禁破解绕过，亦不直接退出**：
- 调用 `python3 $HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py --task "<task-id>" --title "<简短标题>" --message "点击直达 Chrome 点选图形验证，通过后自动继续" --wait-selector-gone ".cf-turnstile" --timeout 180 --on-timeout collapse`（定时签到等后台无人值守场景必加 `--keep-notification-on-timeout`，使轮询超时后保留 macOS 提醒与折叠标签页 4h 租约，仅在验证完成或点击后自动消通知）；
- 用户点击通知时才展开对应标签组并切至 Chrome，交互式会话未加 `--keep-notification-on-timeout` 时超时自动清通知并收拢回退为 `pending`；
- **最小打扰原则**：用户 Gmail 与教育邮已全量转发至 `<USER_EMAIL>`，后续 **6 位邮箱或短信验证码必须由 Agent 自动轮询本地 imap-mail IMAP 或 `device-mesh-relay` 短信通道只读提取回填**，严禁让用户手动翻邮箱/手机复制验证码。
