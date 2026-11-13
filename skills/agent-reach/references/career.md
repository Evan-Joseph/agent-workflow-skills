# 职场招聘

LinkedIn、Boss直聘。

## LinkedIn

```bash
# 获取个人资料
mcporter call linkedin.get_person_profile linkedin_username="username" sections="experience,education"

# 搜索人才
mcporter call linkedin.search_people keywords="AI engineer" location="Shanghai"

# 获取公司资料
mcporter call linkedin.get_company_profile company_name="openai" sections="posts,jobs"

# 搜索职位
mcporter call linkedin.search_jobs keywords="software engineer" location="Remote" max_pages=2
```

> **需要登录**: 首次使用前运行 `uvx mcp-server-linkedin@latest --login`，保存有效登录态。

### Fallback 方案

如果 MCP 不可用，可以用 Jina Reader：

```bash
curl -s "https://r.jina.ai/https://linkedin.com/in/username"
```

## Boss直聘

当用户说“帮我配 Boss直聘”时，按本节复用本机 `${CDP_RELAY_HOST}` 持久化 CDP 守护进程、引导用户登录并完成验证。不要把底层调试端口细节先甩给用户，也不要替用户输入账号、扫码或破解滑块。

> **关键区分：登录门槛 ≠ 反爬安全校验。** zhipin.com 落地后可能停在三种页面：
> 已登录的 `web/geek/job`、未登录的 `web/user/`（扫码登录/手机号登录）、以及
> 反爬的**安全校验页**（URL 含 `security-check` / `zhipin-security` /
> `_security_check`）。安全校验页与登录无关：**已登录也会出现**。绝不用当前页 URL 判断登录态。

> **双登录态存储（existing-browser 严格 CDP 模式下以浏览器为准）。** 存在两个凭据存储，
> **都不能删**，但认证的是不同通道：
>
> | 存储 | 角色 |
> |---|---|
> | `~/.boss-agent/auth/session.enc` | ① 硬性门槛：`_get_browser()` 无条件 `get_token()`，读不到直接 `AuthRequired`，CDP 搜索会在连浏览器前就失败；② **不是**搜索的认证凭据：CDP 复用真 Chrome 的 `contexts[0]` 时，它的 cookies 只在「无 context」分支注入，实际从未生效；③ httpx 通道（低危 op：`status`/`detail`/`cities`/`job_card_httpx`）真用它的 cookies + stoken，code 37 的 `force_refresh()` 也回写它 |
> | Chrome 内的浏览器 cookie | CDP 模式下 search/greet 等高危 op 实际携带的凭据 |
>
> **`boss status` / `status --live` 只校验 session.enc**——即使报
> `logged_in: true`，也不代表 CDP 浏览器已登录。所以：
> 1. 首次接入前先确认 `${CDP_RELAY_HOST}` 对应 Chrome 内已登录 Boss直聘（右上角有头像），确认后才允许执行搜索；
> 2. 探测浏览器内有无 `wt2` cookie，以浏览器内真实状态为准；
> 3. **`AUTH_EXPIRED` 是 ground truth**：搜索报它就直接走登录 runbook
>    （用户在 Chrome 登录 → `login --cdp`），禁止再往「安全校验」方向解释；
>    `_security_check` 页面只在 `AUTH_EXPIRED` 不存在时才按滑块处理（调用 `notify_human_handoff.py`）。
> 4. 不要为了「清理旧凭据」删除 session.enc；要刷新它就跑 `login --cdp`。

> **依赖状态**：所需公开 strict-CDP API 来自 boss-agent-cli 后继拆分 PR #403–#407
> （#402/#382 已按维护者意见拆分），已全部合并入上游 master。安装时锁定
> 上游固定提交
> `4c991b77086a203173bf08a4cb64a23af6514fe6`，而不是会移动的 branch；上游发布正式版后
> 应把安装器切回版本约束。

体检（无副作用，不搜索）：

```bash
agent-reach doctor --json   # 核验 cdp-9223 与各通道连通状态
```

搜索 + JD 使用公开 API（`browser_source` / `job_card_browser` / `JobItem.lid`），统一连接本机持久守护 `${CDP_RELAY_URL}`（严禁直连底层浏览器调试端口触发授权弹窗）：

```bash
uv run --isolated --no-project \
  --with 'git+https://github.com/can4hou6joeng4/boss-agent-cli.git@4c991b77086a203173bf08a4cb64a23af6514fe6' \
  python - <<'PY'
from pathlib import Path

from boss_agent_cli.api.client import AccountRiskError, BossClient, EnvironmentRiskError
from boss_agent_cli.auth.manager import AuthManager
from boss_agent_cli.platforms.zhipin import BossPlatform

auth = AuthManager(Path.home() / ".boss-agent")

# 严格 CDP 模式：统一复用本机 ${CDP_RELAY_HOST} 持久中继、CDP 失败立即抛错
with BossClient(
    auth,
    cdp_url="${CDP_RELAY_URL}",
    browser_source="existing-browser",
) as boss:
    raw = boss.search_jobs("大模型", city="深圳", page=1)
    if raw.get("code") != 0:
        code, message = BossPlatform(boss).parse_error(raw)
        raise RuntimeError(f"{code}: {message}")
    items = raw.get("zpData", {}).get("jobList", [])
    for item in items:
        card = boss.job_card_browser(item["securityId"], item["lid"])
        post_desc = card.get("zpData", {}).get("jobCard", {}).get(
            "postDescription", ""
        )
        print(item.get("jobName"), post_desc)

# AccountRiskError / EnvironmentRiskError → 立即停止，不自动重试；
# 明确 token/stoken 过期的 code 37 由 BossClient 最多刷新并重试一次。
PY
```

### 环境体检与恢复（抓取前必查）

搜索前按下面 runbook 排查，严禁私自新开带调试端口的 Chrome 实例：

1. **`${CDP_RELAY_HOST}` 持久中继通不通**：
   ```bash
   curl -s ${CDP_RELAY_URL}/health         # ok=true & connected=true = 守护在线
   curl -s ${CDP_RELAY_URL}/json/version   # 有 Browser 字段 = CDP 转发就绪
   ```

2. **后台静默打开受管标签页**：由系统常驻服务 `com.agents.chrome-cdp-daemon` 维护唯一持久长连接，通过 `:9223` 后台创建标签页（零焦点抢占）：
   ```bash
   curl -s -X POST ${CDP_RELAY_URL}/new \
     -d '{"url":"https://www.zhipin.com/web/geek/job","task":"boss-recon","reuse":true}'
   ```

3. **用户手动登录或安全校验接力（`notify_human_handoff.py`）**：
   - 若浏览器未登录（无 `wt2` cookie）或停在安全校验页（`security-check` / `zhipin-security` / `_security_check`），**严禁绕过或破解滑块**，调用统一通知接力脚本发出 macOS 横幅请用户点击直达对应 Chrome 标签页完成扫码或滑块验证：
   ```bash
   python3 $HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py \
     --url-sub "zhipin.com" \
     --title "Boss直聘需人工登录或点选验证" \
     --message "点击横幅直达 Chrome 验证页，完成后自动继续。" \
     --wait-url-not-contains "security-check" \
     --timeout 180 \
     --on-timeout collapse
   ```
   - 用户登录完成后，同步刷新本地 CDP 登录态：
   ```bash
   boss --cdp-url ${CDP_RELAY_URL} login --cdp
   ```

4. **登录态与任务收尾清理**：
   ```bash
   boss status            # 只反映本地 session.enc，仅作参考
   # 任务完成后务必回收临时受管标签页
   curl -s -X POST ${CDP_RELAY_URL}/cleanup -d '{"task":"boss-recon"}'
   ```

5. **错误码处置**（搜索/取 JD 时）：
   - `AUTH_EXPIRED`（用户未登录）→ **ground truth**：CDP 浏览器未登录（不管
     `boss status` 说什么），直接走第 3 步登录流程 + `login --cdp`，禁止往
     「安全校验」方向解释；
   - code 36（ACCOUNT_RISK）→ 立即停，手动到 BOSS 页面处理，不可自动重试；
   - code 9（RATE_LIMITED）→ 冷却后重试；
   - code 37 + `环境存在异常` → `ENVIRONMENT_RISK`，立即停止，不刷新 Token、不重新登录、不自动重试；
   - 只有文案明确表示 token/stoken 过期的 code 37 才是 `TOKEN_REFRESH_FAILED`；客户端最多自动刷新并重试一次，仍失败再重新登录。

用户要求开始搜索时，Agent 必须指定严格 CDP 模式并指向 `${CDP_RELAY_URL}`（全局选项放在子命令之前）：

```bash
boss --browser-source existing-browser --cdp-url ${CDP_RELAY_URL} search "大模型" --city 广州 --page 1
```

不要无提示连续翻页。boss-agent-cli PR #383 为跨 CLI 进程的普通搜索增加持久
5–10 秒列表预算；该 PR 合并发布前，Agent 仍应主动串行、降频调用。

> **等待属预期，不是卡死**：连续搜索命中节流时，boss-agent-cli 会静默等待 5–10 秒
> （TTY 下会显示「节流等待 Ns…」提示；Agent Reach 以 `--json` 调用，看不到该提示）。
> 等待窗口内不要重试、不要拉起新浏览器、不要切换 profile。
