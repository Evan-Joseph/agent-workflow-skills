---
name: developer-resource-search
description: "搜索开发者资源，包括GitHub仓库/Issue/代码、Stack Overflow问答、Hacker News讨论和HuggingFace模型/数据集/Space。适用于查开源实现、技术问答、模型资源、代码样例和社区讨论。"
metadata:
  short-description: 开发者资源搜索
---

# Developer Resource Search

Use this skill when a coding task benefits from targeted searches across
developer platforms instead of general web search.

## Sources

- GitHub repositories and issues work without a token; GitHub code search uses
  `--token`, `GITHUB_TOKEN`, `GH_TOKEN`, or the existing `gh auth token` login.
- Stack Overflow search works without an API key; `SO_API_KEY` only increases quota.
- Hacker News search works without an API key.
- HuggingFace model/dataset/Space search works without a token; `HF_TOKEN` only increases quota.
- **吾爱破解 (`52pojie.cn`, )**：涉及桌面端/Android 协议逆向、壳特征分析、国产客户端排障与安全工具调研时，与 GitHub、LinuxDO 并列作为标准信源；**检索方式**：因瑞数动态 WAF 且实测 `so.qq.com` 对 `site:52pojie.cn` 多词查询无召回，统一先通过 `anysearch` 执行 `site:52pojie.cn <关键词>` 定向定位帖子 URL，确需阅读正文/隐藏楼层时再经 `${CDP_RELAY_HOST}` 已登录 Chrome 静默读取并自动 `/cleanup`（遇图形验证调 `$HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py`），**严禁使用无头爬虫高频并发扫站触发瑞数动态 WAF 伤号**。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `research-search` 锁定运行时）。
- **执行命令范例与自检**：
  ```bash
  python3 -c "import httpx, socksio; print('research-search ok')"
  python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "query" --type repositories --limit 5
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，统一通过 `/opt/homebrew/bin/uv sync --project ~/.agents/runtimes/research-search` 修复受管运行时，严禁改动系统 Python 或向用户汇报。
- **代理兼容性**：网络请求继承环境变量代理；锁定的 `httpx[socks]` 支持本地 Clash SOCKS 代理。

## Commands

```bash
python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "query" --type repositories --sort stars --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "query" --type issues --sort updated --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "query" --type code --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "owner/repo" --type releases --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/github_search.py "query or owner/repo" --type commits --sort updated --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/stackoverflow_search.py "query" --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/hackernews_search.py "query" --limit 5
python3 $HOME/.agents/skills/developer-resource-search/scripts/huggingface_search.py "query" --type models --limit 5
```

## Rules

- Prefer official docs and primary repositories for implementation decisions.
- Use platform search to find candidates, then inspect primary sources before giving technical recommendations.
- Do not expose tokens in commands shown to the user; use environment variables.
