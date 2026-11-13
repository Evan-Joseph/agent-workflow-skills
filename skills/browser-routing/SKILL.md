---
name: browser-routing
description: "所有本机浏览器操作与自动化测试的前置路由总控。规范日常登录态 Chrome（Codex 官方扩展或 9223 持久守护中继）、Localhost Playwright 调试与 Camoufox 调研。强制零焦点抢占（自动化无头/后台静默创建/焦点仿真）、规范任务标签页分组复用与默认折叠、全生命周期一键清理与回读核验，彻底杜绝孤儿标签页与焦点打扰。"
metadata:
  short-description: 浏览器自动化路由、本地测试与生命周期总控
---

# Browser Routing & Testing Governance

所有涉及浏览器操作的任务前置守则。先路由、后操作，严格收敛生命周期。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：
  - Camoufox 管理脚本（`scripts/camoufox_profile.py`）：固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `camoufox` 专用运行时，内核 `v156.0.1-beta.36`）。
  - 人机验证 macOS 通知接力工具（[`scripts/notify_human_handoff.py`](./scripts/notify_human_handoff.py)，零第三方依赖标准库）：固定使用 `python3`（`homebrew-stdlib` 运行时），`--notifier-host auto` 默认使用独立签名宿主 `$HOME/.local/libexec/notifiers/AgentHandoffNotifier.app`（`3.1.0`，`Alerts` 常驻样式，带右侧蓝白校验盾徽章 `handoff-shield.png`，点击或完成/超时后自动清除）；纯知情自动收起横幅则使用 `$HOME/.local/libexec/notifiers/SMSNotifier.app`（`Banners` 样式，5s 自动收起，可通过 `--notifier-host sms` 显式指定或自动回退）。
- **执行命令范例与环境自检**：
  ```bash
  python3 -c "import camoufox; print('camoufox runtime ok')"
  python3 $HOME/.agents/skills/browser-routing/scripts/camoufox_profile.py status
  python3 $HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py --help
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。

## 一、 核心路由法则（唯一 Owner 原则）

1. **日常个人登录态 Chrome / 现有标签页**：
   - 唯一合法默认控制器：**Codex 官方 Chrome 扩展**。具体入口必须以当前会话实际提供的官方浏览器工具文档为准，不得假定 `agent.browsers` 一定存在。
   - 复用当前 Profile、Cookie、登录态与扩展，无需频繁弹框授权。
   - 严禁其他 Harness（如 Claude Code / Oh-My-Pi (omp / PI-Desktop) / Devin / Gemini / Antigravity 等）未经用户明确点名授权擅自并发附着主力 Chrome。
   - **CDP 自动化唯一合法中继：`${CDP_RELAY_URL}`（零弹窗持久守护中继）**：
     - **底层根因与防弹窗铁律**：Chrome 128+/144+ 开启远程调试后，**每一次外部新建 WebSocket 调试握手都会在 Chrome 前台强制弹出一次“Allow remote debugging connection?”确认框**。
     - **单一持久守护**：系统已部署标准基础服务 `com.agents.chrome-cdp-daemon`（基于 `$HOME/.agents/scripts/chrome_cdp_daemon.js`，开机常驻），维持与底层 Chrome 调试端点的**唯一单条持久 WebSocket 长连接**。
     - **严禁直连短脚本**：**严禁任何 Harness 编写短生命周期直连脚本（如 `node cdp.js`、`python -c "connect_over_cdp"`、每次动作 `ws.close()`）绕过 9223 直接拨号底层调试端口反复断连重连**！
     - **统一调用规范**：所有 Agent（Antigravity、Claude Code、Codex、Oh-My-Pi (omp / PI-Desktop)、Devin、ARTEX 等）如需通过 CDP 操作日常 Chrome 标签页，**一律统一调用本地守护 HTTP 接口（`${CDP_RELAY_HOST}`）**，零弹窗、零中断、微秒级响应：
       ```bash
       # 1. 服务健康度与连接状态探查
       curl -s ${CDP_RELAY_URL}/health

       # 2. 列出当前所有活动页面标签 (含 isAgentTab、task、group 追踪标记)
       curl -s ${CDP_RELAY_URL}/tabs

       # 3. 静默后台创建新标签页 (强制 background: true + 自动开启焦点仿真 + 自动归入 [Agent] 任务折叠标签组，支持 reuse:true 优先复用同任务页)
       curl -s -X POST ${CDP_RELAY_URL}/new -d '{"url":"https://target.com","task":"recon-demo","reuse":true}'

       # 4. 原地复用现有标签页 (支持 targetId、urlSub 或 task，未指定时仅复用/新建当前 task 受管页，绝不篡改用户个人标签页)
       curl -s -X POST ${CDP_RELAY_URL}/navigate -d '{"task":"recon-demo","url":"https://target.com/next"}'

       # 5. 显式关闭单一标签页 (支持 targetId 或 urlSub，彻底杜绝孤儿标签页)
       curl -s -X POST ${CDP_RELAY_URL}/close -d '{"urlSub":"target_domain"}'

       # 6. 任务级一键安全清理 (仅回收当前 Agent/任务创建的页面，严禁触碰用户个人标签)
       curl -s -X POST ${CDP_RELAY_URL}/cleanup -d '{"task":"recon-demo"}'

       # 7. 定位页面并执行 JavaScript (urlSub 匹配目标 URL 子串)
       curl -s -X POST ${CDP_RELAY_URL}/eval -d '{"urlSub":"target_domain","expression":"document.title"}'

       # 8. 极速提取页面正文纯文本 (innerText)
       curl -s -X POST ${CDP_RELAY_URL}/text -d '{"urlSub":"target_domain"}'

       # 9. 精准元素点击 (CSS 选择器)
       curl -s -X POST ${CDP_RELAY_URL}/click -d '{"urlSub":"target_domain","selector":"button.submit"}'

       # 10. 表单填写与回车提交
       curl -s -X POST ${CDP_RELAY_URL}/type -d '{"urlSub":"target_domain","selector":"input[name=q]","text":"query","submit":true}'

       # 11. 文件上传 (自动绑定 DOM.setFileInputFiles)
       curl -s -X POST ${CDP_RELAY_URL}/file -d '{"urlSub":"target_domain","selector":"input[type=file]","filePath":"/path/to/file"}'

       # 12. 原生转发任意 CDP 命令
       curl -s -X POST ${CDP_RELAY_URL}/cdp -d '{"method":"Page.captureScreenshot","params":{"format":"png"}}'
       ```
2. **Localhost 前端测试、交互调试与轻量免登网页快照 (Browser Testing & Isolated CLI)**：
   - **完整交互回归与调试沙盒**：使用 Playwright MCP（`@playwright/mcp` `v0.0.83`）或本地 Playwright 启动隔离调试沙盒，测试本地 Web 服务或执行破坏性回归测试，严禁混入真实日常 Chrome Profile（严禁私自启动挂载默认 User Data Dir 的后台 Chrome 抢占 `SingletonLock`）。
   - **交互状态机与多视口回归硬门禁**：前端验收时必须涵盖桌面（`1440×900`）、平板、手机竖屏（`390×844`）与**手机横屏（`844×390`）**，执行 `Collapsed -> Expanded -> Collapsed` 展开态裁切检测与开关按钮 `On -> Off -> On` 往返测试，确认 `#root` 实际渲染非空且压缩截图（`<150 KB` JPEG）经多模态 `read_file` 目检通过。
   - **网申/外部表单填报与众测报名防呆铁律**：网申存在多段项目/教育经历时必须点击页面 `+添加/新增` 按钮逐条填入（严禁把多个项目塞进同一文本框），必填项（`*`）缺失或遇短信验证码/人机阻断时必须保留页面并置顶提示用户接力完成提交，严禁脑补未获荣誉或擅自放弃投递；严禁将导师/合作者邮箱（如 `<ADVISOR_EMAIL>`）填入第三方 AI 审稿或外部工具网站。
   - **轻量极速语义快照与免登交互**：优先使用 Rust 原生 CLI `agent-browser`（`vercel-labs/agent-browser`，已全局安装；`v0.42+` 支持 **Saved Flows** 录制一次浏览器交互并按「直接 HTTP -> 页内 Fetch -> 命令重放」三级降级回放及按需引用加载）：
     - 打开并提取可交互元素引用：`agent-browser open <url> && agent-browser snapshot -i`（返回精简语义树与 `@e1`/`@e2` 引用，大幅节省上下文 Token）；
     - 交互与回收：`agent-browser click @e1`、`agent-browser fill @e2 "text"`，用完执行 `agent-browser close`。
3. **公开反爬、深度匿名调研**：
   - 路由至独立配置的 Camoufox 沙盒环境（专用运行时 `python3`，内核 `v156.0.1-beta.36`，管理脚本 [`scripts/camoufox_profile.py`](./scripts/camoufox_profile.py)）。
4. **性能追踪、Core Web Vitals (LCP)、无障碍 (A11y)、CSS 级联调试、Cookie 鉴权与内存泄漏诊断（`chrome-devtools-plugin` + `chrome-devtools` MCP 融合架构）**：
   - **双轨和谐共存机制（零焦点抢占、零 `9222` 弹窗冲突）**：
     1. **独立无头 DevTools / Lighthouse / Heap Snapshot 审计通道（`chrome-devtools` MCP，`chrome-cdp-mcp`）**：底层封装官方 `chrome-devtools-mcp`（支持 `lighthouse_audit`、`performance_start_trace`、`performance_stop_trace`、`performance_analyze_insight`、`take_heapsnapshot`、`get_css_styles`、`take_snapshot`、`list_network_requests`，以及 `v1.13+` 页级网络 Mock 与 DevTools Logpoints 等能力），默认以 `--headless --isolated --no-usage-statistics` 启动独立无头隔离沙盒，**绝不触碰日常 Chrome `SingletonLock`、绝不直连 `9222` 触发确认弹窗、绝不抢占 macOS 前台焦点**，与 `chrome-devtools-plugin` 的 7 项官方诊断技能（`debug-optimize-lcp`、`memory-leak-debugging`、`a11y-debugging`、`cookie-debugging`、`chrome-devtools`、`chrome-devtools-cli`、`troubleshooting`）100% 丝滑配合。
     2. **日常已登录 Chrome 诊断通道（`${CDP_RELAY_URL}`）**：当诊断目标依赖个人 Chrome 已登录会话时，统一通过 `${CDP_RELAY_HOST}` 持久守护中继（已同时支持 `/cdp` RPC 及标准 `/json/version`、`/json/list` 发现端点）执行；若需临时将 `chrome-devtools-mcp` 附着至指定调试端点，可通过环境变量 `CHROME_DEVTOOLS_MCP_BROWSER_URL` 显式传入。
   - 详细 LCP 四阶段（TTFB / Load Delay / Load Duration / Render Delay）拆解脚本、孤儿表单与热区检测、`HttpOnly` Cookie CDP 提取及三态 Heap Snapshot 内存泄漏排查流程，亦查阅 [`references/web-vitals-a11y-cookie-memory-debugging.md`](./references/web-vitals-a11y-cookie-memory-debugging.md)。

## 二、 零焦点抢占架构与静默运行准则 (Zero-Focus-Stealing Architecture)

参考 GitHub 顶尖自动化框架（`browser-use`、Playwright、Claude Extension）在焦点抢占治理中的工业级实践，**任何中断用户正在输入的活动窗口、抢占系统前台焦点（Focus Stealing）的行为均属严重事故**。必须严格执行以下防御体系：

1. **会话级焦点仿真 (Focus Emulation Over Focus Stealing)**：
   - 传统脚本常通过 `Target.activateTarget` 或 `page.bringToFront()` 让输入框获得焦点，这会直接触发 macOS WindowServer 将 Chrome 窗口强行置顶推向前台；
   - 守护中继（9223）在附着页面时，默认自动对该 CDP 会话下发 `Emulation.setFocusEmulationEnabled({ enabled: true })`。页面引擎在后台即判定自身拥有活动焦点，支持所有 `:focus` 伪类、输入事件与键盘监听，**完全不需要将 OS 窗口置顶，实现 100% 后台静默交互**。
2. **严禁调用窗口前置指令**：
   - 严禁调用 `Target.activateTarget`、`page.bringToFront()` 或操作系统的 `osascript` 激活窗口。所有 DOM 评估、事件派发和快照采集必须在后台会话中静默完成。
3. **静默后台创建 (Silent Background Creation)**：
   - 新建标签页强制指定 `background: true`（CDP `Target.createTarget { background: true }`，9223 守护进程 `/new` 端点强制注入），绝不在前台激活新标签页。
4. **无头优先 (Headless First)**：
   - 所有脚本化与非人工视觉任务（Playwright CLI、Puppeteer、爬虫脚本）**必须默认启用无头模式**（如 `playwright-cli open --headless`、Puppeteer `headless: true`）。
5. **原地复用优先 (In-place Tab Reuse)**：
   - **严禁无节制频繁创建新标签页**。Agent 必须优先调用 `GET /tabs` 检索已有标签页，通过 `POST /navigate` 在同一受管标签页中原地跳转复用，将标签页增量收敛至最小。
6. **有头 Chrome 移动端 Touch 仿真即用即清铁律（Touch Emulation Reset Gate，实战门禁 `Step 216` 教训）**：
   - 在通过 `${CDP_RELAY_HOST}` 调试日常有头 Chrome 时，若临时下发了 `Emulation.setTouchEmulationEnabled({ enabled: true })` 或移动端 `Emulation.setDeviceMetricsOverride`，**必须在单次操作收尾前立即下发 `Emulation.setTouchEmulationEnabled({ enabled: false })` 与 `Emulation.clearDeviceMetricsOverride` 还原桌面状态**，严禁遗留 Touch 仿真导致用户桌面网页手势锁死、无法滚动或点击失效。
7. **在线监考/测评防失焦页内 HUD 铁律（Proctored Exam Anti-Blur Gate，实战门禁 `Steps 12183–12256` 教训）**：
   - 针对北森（`ceping.com`）等带 `window.onblur` / `document.visibilitychange` 切屏失焦计数红线的在线测评与考试场景，**严禁设计需要切换窗口或标签页焦点的独立本地 Web 工作台（如 `<LOOPBACK_HOST>:8765`）**；必须采用通过 `Page.addScriptToEvaluateOnNewDocument` 注入目标页内的 **Closed Shadow DOM 隐形悬浮 HUD** 配合静默快捷键，确保全程零失焦事件触发。
8. **macOS 桌面通知与脚本唤起强制绑定 Chrome 铁律**：
   - 凡通过 `terminal-notifier`、AppleScript 或 Python 脚本向用户推送可点击网页通知或自动打开页面，必须显式绑定已持有登录态的 `Google Chrome.app`（如 `-execute '/usr/bin/open -a "Google Chrome" "<url>"'`），严禁使用系统默认 `open "<url>"` 误唤起未登录的 Safari。
9. **人机验证阻断（CAPTCHA）macOS 通知接力、超时清理与邮箱/短信 OTP 自动接管机制**：
   - **安全红线与最小打扰边界**：
     - 当 `:9223` 后台标签页遇到无法自动处理的**图形人机验证**（Cloudflare Turnstile、GoCaptcha、Geetest、hCaptcha、reCAPTCHA）时，**严禁尝试破解、代点或绕过验证码**，亦禁止未经通知直接放弃退出；
     - **邮箱/短信 OTP 全自动接管免打扰**：当流程含「图形验证 + 6 位邮箱/短信验证码」时，`notify_human_handoff.py` 通知文案**仅请用户点击过掉图形人机验证**，后续邮箱或短信验证码由 Agent 通过受管只读 IMAP 邮箱通道或短信转发通道自动提取并回填，不要求用户手动翻阅复制！
   - **统一接力入口（[`scripts/notify_human_handoff.py`](./scripts/notify_human_handoff.py)）**：
     - `--notifier-host auto` 默认使用 `AgentHandoffNotifier.app`（`3.1.0`，`Alerts` 常驻弹窗样式 + 右侧蓝白校验盾徽章 `handoff-shield.png`，确保用户未在桌面前时通知持续常驻不消失；纯知情横幅场景走 `SMSNotifier.app` `Banners` 样式 5s 自动收起，可通过 `--notifier-host sms` 显式切换或自动回退）；
     - **零焦点抢占 + 点击精准直达**：用户未点击通知前绝不激活窗口；用户点击通知横幅时，回调自动经 `:9223` 展开对应 `[Agent]` 标签组、激活目标 `targetId` 并调用 `/usr/bin/open -a "Google Chrome"` 切至前台（绝不误开 Safari）；
     - **静默只读轮询 + 完成即清 + 超时自清**：后台按只读条件轮询（默认 `--timeout 180` 秒）：
       - 用户在电脑前完成图形验证 -> 立即执行 `-remove <group>` 清除横幅并返回 `{"ok": true, "status": "completed"}`，调用方无缝继续自动拉取 邮箱/短信 OTP 回填及后续流程；
       - 用户不在电脑前导致超时 -> 立即执行 `-remove <group>` 清除过期横幅，按 `--on-timeout`（`collapse` 默认折叠回后台 | `close` 关闭单页 | `cleanup-task` 清理任务组 | `keep` 保留）收拢标签页并返回 `{"ok": false, "status": "timeout"}`，调用方优雅回退记为 `pending` 汇报。
   - **标准调用范式**：
     ```bash
     # 1. 按域名子串或 targetId 发起人机验证接力（等待验证挑战消失或 URL 跳转，默认 180s 超时自动清通知并折叠标签组）
     python3 $HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py \
       --url-sub "aiapi.codes" \
       --title "AIAPI 登录需人工点选验证" \
       --message "点击横幅直达 Chrome 验证标签页，点选通过后自动继续。" \
       --wait-url-not-contains "/login" \
       --timeout 180 \
       --on-timeout collapse

     # 2. 等待特定验证码 DOM 选择器消失，若用户不在电脑前超时则自动关闭临时受管页
     python3 $HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py \
       --target-id "<TARGET_ID>" \
       --wait-selector-gone ".cf-turnstile" \
       --wait-selector-gone "[class*='gocaptcha']" \
       --timeout 180 \
       --on-timeout close
     ```

## 三、 自动化会话命名、分组与防叠窗规范 (`chrome_cdp_daemon.js` v3 Deterministic Governance)

- **`chrome_cdp_daemon.js` v3 六层确定性守护特性**：
  1. **macOS 锁屏/休眠零握手护栏（`503 screen_locked_cdp_deferred`）**：启动按需惰性连接（`lazyConnect=true`），并通过 `ioreg -n Root -d1 -a`（`2s` 缓存）检测 `CGSSessionScreenIsLocked`；锁屏或离线控制台期间绝不向 `:9222` 发起新 WebSocket 握手，直接快返 `HTTP 503 screen_locked_cdp_deferred`。
  2. **严格单次授权熔断锁（`AUTH_PENDING_LATCH` -> `503 cdp_remote_debugging_approval_pending`）**：对同一 Chrome `:9222` 监听指纹（`DevToolsActivePort` / `lsof p<pid>:f<fd>`）至多仅发起 **1 次**上游 WS 握手；若等待用户点击「允许远程调试？」模态框超时或被拒，立即闩锁 `AUTH_BACKOFF`，后续所有并发/后台请求 `<1ms` 快返 `503 cdp_remote_debugging_approval_pending`（从数学上杜绝 2 层及以上叠窗抢焦点），直至用户点击允许、Chrome 监听指纹更新或显式调用 `POST /reconnect`。
  3. **10 大常驻高频站点折叠复用池（`[Agent] 常驻复用`）**：访问 `yuanbao.tencent.com`、`mp.weixin.qq.com`、`xiaohongshu.com`、`bilibili.com`、`52pojie.cn`、`douyin.com`、`zhihu.com`、`linux.do`、`sogou.com`、`x.com` 这 10 个内置域名时，守护进程优先复用折叠态 `[Agent] 常驻复用` 组内的既有受管标签页，避免重复开关与频繁过盾。
  4. **任务分组自动归拢与折叠（`groupAndCollapseTab`）**：非常驻临时任务调用 `/new` 或 `/navigate` 时，自动经由扩展 `agent-tab-grouper` 调用 `chrome.tabs.group` 与 `chrome.tabGroups.update({ title: "[Agent] <task>", color: "blue", collapsed: true })` 归入折叠标签组，全程零焦点抢占。
  5. **临时受管页 `60s` TTL 自动回收**：临时抓取页支持 `ttlSec: 60`（及 `60s` 后台 Reaper 巡检）到期自动关闭并清理空分组，根除遗忘孤儿标签页。
  6. **个人标签页 `HTTP 403` 硬隔离保护**：对非 Agent 创建的用户个人标签页调用 `/close`、`/navigate` 覆写或越权清理时，`:9223` 守护直接拦截返回 `HTTP 403`，100% 保护用户日常浏览现场。
- **命名规范**：创建标签页前，若当前浏览器工具提供会话命名接口，必须统一定义为 `[Agent] 任务名` 格式（如 `[Agent] SRC-Recon`）。
- **优先复用既有分组**：在新建标签页前，先检查是否存在当前任务的标签页分组。若已存在，**必须优先将页面归入已有分组**，严禁分散创建多个同名冗余分组。
- **默认折叠收缩 (Collapsed by Default)**：为了不干扰用户的视觉焦点与标签栏布局，Agent 创建的任务分组在非交互巡检状态下应保持折叠（`collapsed: true`）。
- **严禁散落未分组标签页**：所有受管标签页必须处于规范分组中，严禁在用户主标签栏肆意散落未分组标签页。
- **尊重用户既有状态**：接管用户已有页面时，尊重原有的分组与顺序，严禁擅自移动、拆散或重命名用户自己的分组。

## 四、 全生命周期闭环与防孤儿契约 (Lifecycle & Anti-Orphan Contract)

- **全量标签元数据跟踪**：9223 中继内置 Agent 标签注册表，记录每个受管页面的 `targetId`、所属任务 `task`、分组 `group` 与创建时间，将 Agent 页面与用户个人页面严格隔离。
- **用完即关**：中间搜索页、重定向页、临时快照页一旦提取完证据或数据，立即显式调用 `POST /close` 销毁。
- **任务级一键清理 (`POST /cleanup`)**：任务结束或遇到异常退出时，Agent 必须调用 `curl -X POST ${CDP_RELAY_URL}/cleanup -d '{"task":"<任务名>"}'` 一键销毁该任务下的全部受管页面，绝不误伤用户个人标签。
- **销毁回读核验**：清理后必须调用 `GET /tabs` 回读，**核验目标 targetId 已彻底从列表中注销且 `agentTabsCount` 已归零**，禁止仅调用关闭而未验证结果。
- **收尾复核**：
  - 仅将用户明确要求的交付页标记为 `deliverable` 并通知用户；
  - 仅将正在等待用户人工验证/支付的页面标记为 `handoff`；
  - 自动化结束且无需用户接管时，**必须关闭所有 Agent 新建标签页并销毁空任务分组，严禁残留任何孤儿标签页**。
