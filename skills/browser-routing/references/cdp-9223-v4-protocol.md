# `:9223` Chrome CDP 持久守护 v4 协议端点速查 (`cdp-9223-v4-protocol.md`)

> 守护进程源码：`$HOME/.agents/scripts/chrome_cdp_daemon.js`（v4，LaunchAgent `com.agents.chrome-cdp-daemon`）
> 受管同步与控制 CLI：`cdp-ctl`（`$HOME/.agents/skills/browser-routing/scripts/cdp_ctl.py`）

## 1. 推荐首选：`cdp-ctl` 受管命令行

`cdp-ctl` 在每次调用前自动将 `~/Library/Application Support/Google/Chrome/DevToolsActivePort` 同步至 `0600` `~/.local/state/chrome-cdp-daemon/DevToolsActivePort` 并注入 `/endpoint`，避免 `launchd` 下 `com.apple.macl` 权限隔离与裸端口 404：

```bash
# 健康检查与当前页面列表
cdp-ctl health
cdp-ctl tabs

# 后台静默打开标签页并归入语义化折叠分组（大模型按当前任务自拟 2–8 字简洁组名）
cdp-ctl open --url "https://target.com" --task "baoyan-roster" --group "推免名册" --reuse

# 跨步长流程延长空闲 TTL（2h），仍留在同一语义任务组内（绝不单列“常驻组”）
cdp-ctl open --url "https://target.com" --task "paper-status" --group "论文状态" --resident

# 明确需要留给用户查看的交付物页面（/cleanup 默认保留）
cdp-ctl open --url "http://<LOOPBACK_HOST>:4173" --task "ui-preview" --group "界面预览" --keep-for-user

# 页内导航、JS 求值与正文提取
cdp-ctl navigate --task "baoyan-roster" --url "https://target.com/page2"
cdp-ctl eval --task "baoyan-roster" --expression "document.title"
cdp-ctl text --task "baoyan-roster"

# 任务收尾一键清零（连同页面内点击触发的 openerId 衍生弹窗/下载页一并销毁，0 残留）
cdp-ctl cleanup --task "baoyan-roster"
```

## 2. 底层 HTTP JSON 端点（`${CDP_RELAY_URL}`）

```bash
curl -s ${CDP_RELAY_URL}/health
curl -s ${CDP_RELAY_URL}/tabs
curl -s -X POST ${CDP_RELAY_URL}/new -d '{"url":"https://target.com","task":"xhs-query","group":"小红书检索","reuse":true}'
curl -s -X POST ${CDP_RELAY_URL}/navigate -d '{"task":"xhs-query","url":"https://target.com/next"}'
curl -s -X POST ${CDP_RELAY_URL}/eval -d '{"task":"xhs-query","expression":"document.title"}'
curl -s -X POST ${CDP_RELAY_URL}/text -d '{"task":"xhs-query"}'
curl -s -X POST ${CDP_RELAY_URL}/click -d '{"task":"xhs-query","selector":"button.submit"}'
curl -s -X POST ${CDP_RELAY_URL}/type -d '{"task":"xhs-query","selector":"input[name=q]","text":"query","submit":true}'
curl -s -X POST ${CDP_RELAY_URL}/file -d '{"task":"xhs-query","selector":"input[type=file]","filePath":"/path/to/file"}'
curl -s -X POST ${CDP_RELAY_URL}/cdp -d '{"method":"Page.captureScreenshot","params":{"format":"jpeg","quality":75}}'
curl -s -X POST ${CDP_RELAY_URL}/close -d '{"targetId":"<TARGET_ID>"}'
curl -s -X POST ${CDP_RELAY_URL}/cleanup -d '{"task":"xhs-query"}'
```

## 3. v4 核心保障机制

1. **锁屏零握手（`503 screen_locked_cdp_deferred`）**：`ioreg` 检测到 `CGSSessionScreenIsLocked` 时拒绝发起新 WebSocket 握手，防止唤醒瞬间弹窗。
2. **单次授权熔断锁（`AUTH_PENDING_LATCH` -> `503 cdp_remote_debugging_approval_pending`）**：同一 `DevToolsActivePort` 指纹仅发 1 次上游握手；等待用户点击允许期间拒绝并发重拨，根除远程调试确认框层层叠窗。
3. **`openerId` 衍生页与 `brain/` 工件页自动收养**：通过上游 `Target.setDiscoverTargets({ discover: true })` 实时监听；凡受管页点击弹出的外链/附件下载新标签（`openerId` 指向受管页）或 `file://$HOME/.gemini/antigravity/brain/` 本地工件页，自动继承父任务的 `task` 与 `groupId` 归入同一折叠分组，并在 `/cleanup` 时连根回收。
4. **`about:blank` 预清空防阻塞关闭 + 末页保窗**：销毁受管标签前先导航至 `about:blank` 解除 `beforeunload` 阻塞；若即将关闭 Chrome 最后一个页面，自动后台补建 1 个干净 `chrome://newtab/` 防止关闭整个浏览器窗口。
5. **个人标签 `HTTP 403` 硬隔离**：非受管的用户个人标签与个人标签组严禁被 `/navigate`、`/close` 或 `/cleanup` 篡改或关闭。
