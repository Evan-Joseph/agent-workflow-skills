---
name: agent-reach
description: "全网公开与社交平台内容抓取、检索与定向研学中枢。支持通过 Agent Reach (`reach-hub` / `omnireach` / `opencli`) 本地工具链获取微信公众号、抖音（视频搜索/博主作品库/高赞评论）、知乎、小红书（XiaoHongShu/RedNote）、Bilibili（搜索/评论/字幕）、Twitter/X、Reddit、V2EX、YouTube 字幕、Jina Reader 网页正文及 8 平台实时热榜雷达。在需要全网跨平台抓取、多源舆情与社区调研时使用。"
metadata:
  short-description: 全网社交与内容平台免密/长效抓取与热榜雷达中枢
---

# Agent Reach & Multi-Platform Harvesting (`reach-hub` + `omnireach` + `opencli`)

赋予 Agent 访问主流中文与国际社交平台、社区论坛、视频字幕/高赞评论及跨平台实时热榜的只读检索能力。零 API 费用、本地受管 CLI 优先、严格遵守 `browser-routing` 零焦点打扰规范（`${CDP_RELAY_HOST}` 持久守护后台静默建页 + 自动 `/cleanup`）。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器与受管 CLI 入口**：
  - 核心 Python 运行时：固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `research-search` 运行时，已锁定集成 `Daily-AC/omnireach`、跨平台聚合引擎 `reach_hub.py`、`xhs_research.py` 与 `opencli_cdp.py`）；
  - 统一聚合 CLI：`reach-hub`（-> `scripts/reach_hub.py`）、`omnireach`、`opencli`（-> `scripts/opencli_cdp.py`，基于 `${CDP_RELAY_HOST}` 持久守护的受管桥接，无需加载历史 `opencli-extension`）；
  - 小红书专职采集引擎：已全面升级为 `${CDP_RELAY_HOST}` 页内原生 `window.__INITIAL_STATE__` 引擎（吸收 `xpzouying/xiaohongshu-mcp` 与 `white0dew/XiaohongshuSkills` 架构），彻底淘汰并卸载了因跨进程盗取 Cookie + 过期 Python `X-s` 签名重放而频繁引发服务端踢下线的旧版 `xiaohongshu-cli` (`xhs-uv-tool`) 与 Camoufox 临时扫码流。
- **执行命令范例**：
  ```bash
  agent-reach doctor --json
  reach-hub auth-status
  reach-hub hotlist --platform all --limit 10
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。

## 1. 环境诊断与跨平台实时热榜雷达 (`reach-hub hotlist`)

`agent-reach` CLI（`agent-reach`）负责 9 通道健康探测（`omnireach`、`opencli`、`reach-hub`、`xhs`、`bili`、`yt-dlp`、`gh`、`curl-jina`、`cdp-9223`）：

```bash
# 1. 检查全部 9 个渠道实时可用性与活跃后端
agent-reach doctor --json

# 2. 跨平台实时热榜雷达（支持 all / weibo / douyin / zhihu / xiaohongshu / bilibili / baidu / v2ex / hackernews，及 --keyword 正则过滤与 --rerank 本地 :3425 Qwen3-Reranker-4B 语义重排）
reach-hub hotlist --platform all --limit 10
reach-hub hotlist --platform all --keyword "AI|模型|芯片" --rerank "大语言模型与算力动态" --limit 10
reach-hub hotlist --platform douyin --limit 15
```

## 2. 微信公众号、抖音、知乎与全平台深度检索 (`reach-hub` & `omnireach`)

```bash
# 1. 微信公众号与腾讯「元宝搜索」(so.qq.com) 免登录纯 HTTP 双引擎（~1s 直出 100% 永久 __biz= 直链 + AI SSE 微信搜一搜长尾召回 + :9223 搜狗/元宝降级 + 自动过滤“该公众号已迁移”死号 + 秒级 var ct 发布时间校准；零 Google 伪回退）
reach-hub wechat search "Claude Code MCP" --limit 5
reach-hub wechat search "DeepSeek Super-agent" --deep --limit 8
reach-hub wechat search "信息茧房" --limit 5 --with-body
reach-hub wechat read "https://mp.weixin.qq.com/s?..."
# 腾讯元宝搜索 (so.qq.com) 多垂类免密直查（支持 --tab all|weixin_article|media|gov|xueshu 与 --time all|1h|1d|1w|1m|1y，以及 ai 模式早停提取引用）
reach-hub so-qq search "Agent 架构" --tab media --time 1w --limit 8
reach-hub so-qq ai "MCP 协议安全" --limit 8
omnireach search "信息茧房" --on wechat --limit 5

# 2. 抖音 (Douyin)：原生 :9223 搜索、指定博主作品库按点赞/时间排序 (author)、视频高赞评论与 iesdouyin 官方热榜（未登录/滑块阻断时诚实返回 ok:false, error:AUTH_REQUIRED）
reach-hub douyin search "信息茧房" --limit 5
reach-hub douyin author "@差评君" --limit 10 --order likes
reach-hub douyin comments "7699811641772617866" --limit 20
omnireach author "@差评君" --limit 10 --order likes

# 3. 知乎 (Zhihu)：已登录 :9223 api/v4/search_v3 与原生问题/专栏检索、全文 Markdown 提取（Jina 主通道 + 9223 兜底）、评论区提取
reach-hub zhihu search "信息茧房" --limit 5
reach-hub zhihu read "https://zhuanlan.zhihu.com/p/663050853"
reach-hub zhihu comments "https://zhuanlan.zhihu.com/p/663050853" --limit 15

# 4. B站 (Bilibili) 与 YouTube：一手 API / yt-dlp 视频检索、热门评论与楼中楼回复提取、CC/VTT 字幕提取
bili search "信息茧房" --type video -n 5
reach-hub bilibili comments "BV16Bnh6gEAp" --limit 15
opencli bilibili subtitle "BV16Bnh6gEAp"
reach-hub youtube search "Andrej Karpathy LLM" --limit 5
reach-hub youtube subtitle "7xTGNNLPyMI"

# 5. Twitter/X、Reddit、V2EX 与 52pojie：一手接口/页内检索与评论树直读（零 Google 伪回退，严格校验目标域名，未登录时诚实返回 AUTH_REQUIRED）
reach-hub twitter search "@karpathy" --limit 5
reach-hub twitter read "1483718581875527685"
reach-hub reddit search "Claude Code" --limit 5
reach-hub reddit read "11vs6x8" --limit 15
reach-hub v2ex search "Claude Code" --limit 5
reach-hub 52pojie search "frida hook" --limit 5
```

## 3. 小红书 (XiaoHongShu / RedNote) 页内 `__INITIAL_STATE__` 原生引擎与零互踢登录

通过 `reach-hub xiaohongshu` 与 `scripts/xhs_research.py` 直接在 Chrome `${CDP_RELAY_HOST}` 后台静默标签页读取 `window.__INITIAL_STATE__`（`search.feeds` / `feed.feeds` / `note.noteDetailMap`）。请求签名（`X-s` / `X-t` / `sec_poison_id`）100% 由 Chrome 页内原生 WASM/JS 引擎生成，不导出 Cookie、不跨进程伪造签名，彻底根除双指纹互踢与 `-104` 掉线：

```bash
# 1. 检查全平台 Chrome 9223 登录态与剩余有效期
reach-hub auth-status
python3 $HOME/.agents/skills/agent-reach/scripts/xhs_research.py status

# 2. 检索笔记（已登录走 __INITIAL_STATE__.search.feeds；未登录诚实返回 ok:false, error:AUTH_REQUIRED，绝不伪造外站结果）、首页推荐流、笔记正文与评论区
python3 $HOME/.agents/skills/agent-reach/scripts/xhs_research.py search "信息茧房" --limit 5
reach-hub xiaohongshu feed --limit 10
reach-hub xiaohongshu read "<note_url_with_xsec_token>" --limit 20

# 3. 零互踢页内扫码登录（直接在 Chrome 9223 内提取二维码供扫码，会话直接持久化于日常 Chrome）
reach-hub xiaohongshu login
```

## 4. 按需参考路由 (Progressive Disclosure)

| 平台或场景 | 参考文档 |
| :--- | :--- |
| Exa 语义与代码检索 | [`references/search.md`](./references/search.md) |
| 通用网页 (Jina Reader) 与 RSS | [`references/web.md`](./references/web.md) |
| GitHub CLI 检索 | [`references/dev.md`](./references/dev.md) |
| YouTube、Bilibili、小宇宙播客 | [`references/video.md`](./references/video.md) |
| 小红书、Twitter/X、Reddit、V2EX | [`references/social.md`](./references/social.md) |
| 小红书内容质量与互动分析规范 | [`references/xiaohongshu/engagement.md`](./references/xiaohongshu/engagement.md) |
| LinkedIn 职业信息 | [`references/career.md`](./references/career.md) |
| 本机安装状态与 OpenCLI 9223 桥接说明 | [`references/install-notes.md`](./references/install-notes.md) |

## 5. 边界与隐私规则

- **默认只读**：严禁自动点赞、收藏、关注、发帖、回复或发送私信。
- **零焦点打扰**：所有经由 `${CDP_RELAY_HOST}` 的采集必须使用 `background: true` 静默标签页并在 `finally` 中调用 `/cleanup`，任务收尾后确保 `agentTabsCount == 0`。
- **凭据保护**：严禁将包含真实身份的 Cookie 字符串打印在终端或输出给用户。
- **反爬拦截与风控页面识别门禁（Anti-Bot & Challenge Page Gate，实战门禁 / `019fa7c6` 血泪教训）**：当 Jina Reader、高校官网或社交平台返回 `Just a moment...`、`403 Forbidden`、验证码拦截页或空白壳页面时，必须如实标记为“源站触发反爬/WAF 拦截，正文未获取”，严禁将拦截页文本当作正文摘要，亦严禁在未获正文时凭印象脑补高校招生简章、名额或政策细则。
- **抖音图文作品（`aweme_type=68`）区分与多模态防 `INVALID_MEDIA (2011)` 铁律**：
  - 抖音 Web 接口中，当作品为图文（`aweme_type == 68` 或 `duration_ms == 0` / `images` 非空）时，原始 `video.play_addr` 存放的是 **`.m4a` 背景音乐音频流（`ftypM4A `）**，真实图片在 `images[*].url_list`（通常为 `.webp`）；`reach_hub.py` 已统一输出 `media_type`（`"video"` / `"image_note"`）、`play_url`（仅视频有值）、`bgm_url` 与 `image_urls`；
  - **严禁直接将 URL 下载并硬编码 `.jpg`/`.png` 扩展名后直接喂给 Antigravity 原生 `read_file` 工具**：`read_file` 仅按扩展名标记 `mime_type`（如 `image/jpeg`），若底层字节实为 `.m4a`、`.webp`、`.png` 或 HTML 错误页，会直接将毒化载荷写入 `conversations/<cid>.db` 的 `steps.step_payload`，触发 `cloudcode-pa.googleapis.com` `HTTP 400 INVALID_MEDIA (error_number: 2011)` 并永久锁死该会话；
  - 所有供 `read_file` 查看的图片必须先经 `ffmpeg -y -i <input> -vf "scale='min(960,iw)':-1" -frames:v 1 -q:v 6 <out.jpg>` 转码为真实 Baseline JPEG（魔数 `\xff\xd8\xff` 且 `<150 KB`）；若会话不慎触发 `2011 INVALID_MEDIA`，立即运行 `python3 $HOME/.agents/scripts/fix_agy_invalid_media.py --write` 自动清洗 `.db` 毒化步骤并热重载 `language_server` 内存缓存。
- **垂直检索与安全逆向社区边界**：对于结构化公司、法规、专利、金融行业检索，优先走 `anysearch`；对于学术论文走 `academic-literature-search`；对于 GitHub/StackOverflow/HF 优先走 `developer-resource-search`；对于桌面/移动端协议逆向、脱壳调试与国产软件排障，联合 `linuxdo` 与**吾爱破解（`52pojie.cn`）**——因瑞数动态 WAF 且实测 `so.qq.com` 对 `site:52pojie.cn` 多词查询无召回，统一采用「`anysearch` `site:52pojie.cn <关键词>` 定位帖子 URL -> `${CDP_RELAY_HOST}` 已登录 Chrome（已登录账号，`UID: community-user`）静默读取正文并自动 `/cleanup`」（遇图形验证挑战时调用 `$HOME/.agents/skills/browser-routing/scripts/notify_human_handoff.py` 通知用户点选过盾），严禁编写高频抓取循环冲击瑞数 WAF。
