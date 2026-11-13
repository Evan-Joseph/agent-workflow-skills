---
name: linuxdo
description: "LinuxDO 社区数据检索、话题深度读取、热榜追踪与会话交互中枢。原生集成独立会话授权机制（Discourse one_time_password OTP）与 Cloudflare 静默过盾策略，支持全量搜索、指定楼层精准阅读、用户信息查询与板块浏览，不干扰日常桌面浏览器使用。"
metadata:
  short-description: LinuxDO 社区独立会话检索、话题读取与热榜追踪中枢
---

# LinuxDO 社区检索与交互中枢 (linuxdo)

本 Skill 为全 Harness 体系（Antigravity、Codex、Claude Code、Oh-My-Pi (omp / PI-Desktop)、ARTEX、Devin）提供标准化、高稳定性的 LinuxDO 论坛数据检索与内容读取能力。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器与工具链**：本技能通过全局 CLI 软链 `linuxdo`（指向 `scripts/linuxdo_cli.py`）运行，底层固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `linuxdo-runtime` 运行时，内置 `linuxdo-mcp` 核心库、`curl_cffi` 与 `pycookiecheat`；注：原无状态包装 `linuxdo` MCP 已收敛下线，统一收口为确定性 CLI）。
- **Agent 防呆红线**：
  - 严禁自作主张创建临时虚拟环境或修改系统 Python；
  - 严禁直接复制或共享桌面浏览器的 `_t` Session Cookie（必须使用 OTP 独立会话 `~/.cache/linuxdo-mcp/session.json`）。

## 一、 核心架构与运行规范

1. **独立会话隔离（红线禁令：严禁直接窃取或共享桌面浏览器的 `_t` Cookie）**：
   - LinuxDO 基于 Discourse 架构，服务端大约每 10 分钟轮换一次 `_t` Session Cookie。若 Agent 与桌面浏览器共用同一个 `_t`，任何一方发起请求都会导致新 `_t` 发放，进而在 1 分钟内将对方会话踢下线（Session Invalidation）。
   - 本机制通过 Discourse 官方支持的 `one_time_password` (OTP) 机制，在用户授权后一次性换取全新的独立会话，落盘于 `~/.cache/linuxdo-mcp/session.json`。
   - Agent 与日常浏览器的会话彻底解耦，互不顶号、互不干扰。

2. **静默过盾与透明继承**：
   - LinuxDO 启用了高防 Cloudflare WAF 与 Turnstile 挑战。
   - 本工具链在底层通过 `pycookiecheat` 从 Chrome 只读读取信任度极高的 `cf_clearance`（不读且不碰 `_t`），配合对应的 User-Agent 与 `curl_cffi` 进行 TLS 指纹仿真（`impersonate="chrome"`），实现毫秒级快速通关。
   - 若遇到盾失效，自动回退到已配置的 `${CDP_RELAY_HOST}` 持久化 CDP 守护进程进行后台焦点仿真刷新；若仍遇 Turnstile 图形人机挑战阻断，调用 `$HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py` 发送 macOS 横幅请用户点击直达 Chrome 标签页过盾，严禁直接破解或抢占焦点。

3. **确定性 CLI 统一入口**：
   - 全 Harness 统一直接调用 `linuxdo`（即 `$HOME/.agents/skills/linuxdo/scripts/linuxdo_cli.py`），零常驻 MCP 进程开销、零重复工具 Schema 占用。

---

## 二、 CLI 命令全集与调用规范

统一通过 `linuxdo`（或完整路径 `$HOME/.agents/skills/linuxdo/scripts/linuxdo_cli.py`）执行：

```bash
# 1. 检查当前独立 OTP 会话身份
linuxdo whoami

# 2. 搜索话题（支持 order:latest、#分类、@用户 等 Discourse 语法；支持 Markdown 或 --json）
linuxdo search "Gemini 4 Carbon"
linuxdo search "Sub-Store" --json

# 3. 精准读取话题正文与指定楼层（支持 topic / read / view / get_topic，支持 URL 或数字 ID，start 为 1-based 楼层号）
linuxdo read 3034696 --limit 5
linuxdo topic "https://linux.do/t/topic/3034696" --start 6 --posts 5

# 4. 浏览最新话题与热门榜单（支持 --limit 精确截断条数）
linuxdo latest --page 1 --limit 15
linuxdo top --period weekly --limit 15

# 5. 分类板块与标签话题流浏览
linuxdo categories
linuxdo category-topics 4 --page 1 --limit 15
linuxdo tags
linuxdo tag-topics claude --page 1 --limit 15

# 6. 用户画像与最近动态查询
linuxdo user neo
linuxdo user-actions neo --limit 10

# 7. 首次独立会话授权登录 / 注销
linuxdo login
linuxdo logout
```

---

## 三、 认证与授权流程（初次配置）

1. **URL Scheme 注册**：
   - 依赖 `~/Applications/linuxdo-mcp-auth.app` 处理 `discourse://auth_redirect` 协议回调。
   - 若系统丢失关联，运行 `linuxdo-mcp install-handler` 重新注册。

2. **零焦点抢占授权交互步骤**：
   - 终端或 Agent 执行 `linuxdo login`；
   - 底层统一经 `POST ${CDP_RELAY_URL}/new` 在 Chrome `AI` 标签组静默打开 LinuxDO 授权确认页（严禁使用未指定浏览器的 `open` 误唤起未登录的 Safari，严禁带 URL 调 `open -g` 触发前台置顶），并联动 `$HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py` 推送 macOS 横幅；
   - 用户点击通知横幅直达 Chrome 页面点击「授权」按钮（若遇 Cloudflare Turnstile 一并点选通过）；
   - 浏览器自动触发 `linuxdo-mcp-auth.app` 将授权 OTP 写入本地管道；
   - 底层自动完成 OTP 换取独立会话，并在 LinuxDO 账户设置中即时注销一次性 API Key，完成落盘收尾。

---

## 四、 检索最佳实践与社区只读安全红线（源自全量历史复盘）

1. **短词精准检索优先（防 Discourse 布尔语法失效）**：
   - Discourse 搜索接口对超长布尔表达式（如 `(A OR B OR C) (D OR E)`）支持不佳，极易返回 `0` 条结果；调用 `search` 时应使用 **2–3 个核心关键词短语**（如 `"CrossOver 试用"`、`"Sub-Store 链式代理"`）分次检索，再按 `topic_id` 精读高赞楼层。
2. **严格只读与防风控红线**：
   - 默认仅执行检索与阅读操作，严禁未经用户明确指令自动发帖、回帖、点赞或高频并发刷接口触发 Cloudflare 429 质询。
