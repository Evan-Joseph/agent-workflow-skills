# Agent Reach 本机安装与受管桥接备注 (2026-11-01 架构收敛更新)

- **统一诊断入口**：`~/.local/bin/agent-reach` 软链接指向 `$HOME/.agents/skills/agent-reach/scripts/doctor.py`，覆盖全部 9 个核心通道（`omnireach`、`opencli`、`reach-hub`、`xhs-research`、`bili`、`yt-dlp`、`gh`、`curl-jina`、`cdp-9223`）。
- **核心受管运行时 (`research-search`)**：
  - 位于 `~/.agents/runtimes/research-search`（由 `pyproject.toml` + `uv.lock` 锁定，`/opt/homebrew/bin/uv sync` 管理）；
  - 已集成 [`Daily-AC/omnireach`](https://github.com/Daily-AC/omnireach)（`~/.local/bin/omnireach`）及 `omnireach_9223_hook.py`；
  - 已集成全平台只读采集、登录态治理（`reach-hub auth-status`）与 8 平台热榜雷达中枢 `$HOME/.agents/skills/agent-reach/scripts/reach_hub.py`（软链接至 `~/.local/bin/reach-hub`）。
- **淘汰旧版 `xiaohongshu-cli` (`xhs-uv-tool`) 与孤岛 Cookie 方案**：
  - 原因：上游 `jackwener/xiaohongshu-cli` (`0.6.4`) 自 2026-03-21 起停更，采用外部 Python 重放 Cookie (`~/.xiaohongshu-cli/cookies.json`) + 旧版纯 Python `X-s` 签名，且配合临时 Firefox `Camoufox` 扫码，与日常 Chrome (`${CDP_RELAY_HOST}`) 产生严重的双端指纹与签名版本冲突，导致小红书 `shield` 服务端频繁吊销 `0400` 登录态（降级为 `0300` 访客）；
  - 现行唯一真源：吸收 `xpzouying/xiaohongshu-mcp` 与 `white0dew/XiaohongshuSkills` 架构，100% 统一在 Chrome `${CDP_RELAY_HOST}` 页内通过 `window.__INITIAL_STATE__` 读取数据并执行页内扫码登录（`reach-hub xiaohongshu login`）。旧 `xiaohongshu-cli` uv tool 已卸载，历史 `~/.xiaohongshu-cli`、`~/.agent-reach-venv`、`~/.agent-reach` 已安全移入 `~/.Trash/agent-reach-legacy-20261101/`。
- **OpenCLI 受管 9223 桥接 (`~/.local/bin/opencli`)**：
  - 由 `$HOME/.agents/skills/agent-reach/scripts/opencli_cdp.py`（版本 `1.1.0-cdp9223`）驱动，直接复用本机 `${CDP_RELAY_HOST}` 后台静默标签页与 `reach_hub.py`，严格保证 `agentTabsCount == 0` 零焦点打扰。
- **`yt-dlp` 配置**：调用 YouTube 字幕时使用 `--js-runtimes node`。
