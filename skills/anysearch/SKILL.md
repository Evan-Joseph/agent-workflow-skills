---
name: anysearch
description: "通过 AnySearch 搜索公开、非敏感的实时信息和跨领域结构化资料。适用于普通网页结果不足，或需要企业、法律、专利、金融、旅行、能源、农业、影视、游戏及跨来源检索时；不用于未发表论文、私有项目、个人数据、凭据或商业秘密。学术论文、GitHub/开发资源和特定平台内容优先使用本机专用 Skills。"
metadata:
  short-description: 跨领域公开信息与垂直行业检索
---

# AnySearch

把 AnySearch 作为公开信息补充检索层。它不接管所有搜索，也不替代本机专用检索 Skill。

## 运行时契约与环境约束

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py search "query" --max_results 5
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **凭据与网络安全**：网络请求继承标准代理环境变量；不得在日志或错误信息中输出凭据；CLI 直接调用官方 REST 端点，不走已废弃的 JSON-RPC 通道。

## 路由

优先使用现有专用能力：

- 学术论文、引用关系和开放全文：`academic-literature-search`
- GitHub、Issue、Stack Overflow、Hacker News、Hugging Face：`developer-resource-search`
- 多平台公开内容（含小红书、抖音、知乎、B站）、微信公众号永久直链与腾讯元宝搜索（`so.qq.com` `media`/`gov`/`weixin_article`/`xueshu`）：`agent-reach`（`reach-hub wechat search` / `reach-hub xiaohongshu` / `reach-hub so-qq`）
- 用户登录态、已有 Chrome 标签或交互网页：`browser-routing`

AnySearch 自身不应打开浏览器标签页。若核验原始来源必须升级到浏览器，先加载
`browser-routing`，执行零焦点抢占规范（无头或静默后台创建），在命名任务分组（`[Agent] 任务名`）内创建并默认折叠，优先原地复用，用完立即显式关闭中间页，最终只保留明确的 deliverable 或等待用户操作的 handoff，收尾执行清理回读杜绝孤儿标签页。

使用 AnySearch 的典型情况：

- 需要企业、法律、专利、金融、旅行等垂直来源
- **吾爱破解（`52pojie.cn`）帖子 URL 定位**：因瑞数动态 WAF 拦截普通爬虫且实测 `so.qq.com` 对 `site:52pojie.cn` 多词查询无召回，统一使用 `anysearch` 执行 `site:52pojie.cn <关键词>` 定位帖子 URL，再交由 `${CDP_RELAY_HOST}` 已登录 Chrome 静默读取正文并自动 `/cleanup`
- 需要把多个公开来源放在同一次结构化检索中
- 现有专用 Skill 无结果、结果太窄或需要第二通道交叉核验
- 用户明确指定 AnySearch

详细边界见 [路由与隐私](references/routing-and-privacy.md)。

## 隐私门

调用前先检查查询文本。以下内容不得发送：

- API Key、Cookie、Token、密码、私有 URL
- 未发表论文正文、未公开实验结果、审稿材料
- 私有代码、内部项目名、客户数据、合同原文
- 身份证号、手机号、住址、病历等个人数据

如果公开检索确实需要项目背景，先改写成不含专有名词和内部细节的通用问题。拿不准时不用 AnySearch。

## 命令

### 通用检索（多源阶梯路由）

默认自动按阶梯降级策略调度（一级 DeepSeek/博查 → 二级 AnySearch/Tavily → 三级 Bing RSS 兜底）：

```bash
# 默认分层路由（高信噪比 Markdown 格式）
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py search "query" --max_results 5

# 指定返回机器友好的结构化 JSON
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py search "query" --max_results 5 --json

# 显式指定搜索源通道（auto | deepseek | bocha | anysearch | bing）
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py search "query" --provider bocha --max_results 5
```

### 垂直领域检索（AnySearch 专有能力）

垂直检索前先查看子域：

```bash
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py get_sub_domains --domain legal
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py search "query" --tag <sub-domain> --params key=value --max_results 5
```

`--domain --sub_domain --sdp` 仍可兼容旧调用；新调用优先使用 `--tag --params`。`--zone cn|intl` 和 `--language zh-CN` 可按检索需求补充。

### 页面正文抓取（DeepSeek Fetch → `r.jina.ai` 降级 + 反爬壳检测）

自动识别并拦截 Cloudflare `Just a moment...` 等反爬空壳页面，优先走 DeepSeek Fetch，失败或遇空壳自动降级至 `https://r.jina.ai/<url>` 与 `/v1/extract`（通用检索 `--max_results` 上限支持至 `20`）：

```bash
python3 $HOME/.agents/skills/anysearch/scripts/anysearch_cli.py extract "https://example.com/page"
```

## 输出处理

1. 保留标题、URL、来源机构和时间信息。
2. 区分搜索结果、原始来源和模型推断。
3. 对关键事实打开原始来源或用第二通道核验。
4. 厂商基准、营销案例和评分不能作为独立证据。
5. 不因结果结构化就默认其准确、完整或法律有效。

## 凭据管理与零配置保障

1. **博查（Bocha）**：读取环境变量、`~/.config/anysearch/anysearch.env` 中的 `BOCHA_API_KEY`，或 macOS Keychain（`bocha-api-key`）。
2. **DeepSeek**：读取环境变量 `DEEPSEEK_API_KEY`、`anysearch.env` 或 macOS Keychain（`deepseek-api-key`）。
3. **AnySearch / Tavily**：读取 `~/.config/anysearch/anysearch.env` 或 `--api_key`。
4. **Bing RSS**：纯净直出，零凭据、零速率限制、高可用。

不得把 Key 写进 Skill 目录、命令历史、报告或日志。不得自动注册账号或自动创建 Key。

上游和本地补丁见 [上游说明](references/upstream.md)。
