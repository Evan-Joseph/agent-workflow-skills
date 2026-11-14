---
name: agent-reach
description: "全网公开与社交平台内容抓取、检索与定向研学中枢。支持通过 Agent Reach (`reach-hub` / `omnireach` / `opencli`) 本地工具链获取微信公众号、抖音（视频搜索/博主作品库/高赞评论）、知乎、小红书（XiaoHongShu/RedNote）、Bilibili（搜索/评论/字幕）、Twitter/X、Reddit、V2EX、YouTube 字幕、Jina Reader 网页正文及 8 平台实时热榜雷达。"
metadata:
  short-description: 全网社交与内容平台真实检索、字幕评论提取与热榜雷达
---

# Agent Reach & Multi-Platform Harvesting (`reach-hub` + `omnireach` + `opencli`)

提供主流中文与国际内容平台的只读检索、正文/字幕/评论提取与实时热榜能力。严守**零伪造搜索回退**（未登录诚实返回 `AUTH_REQUIRED`）与 **`:9223` v4 语义分组收尾零残留**。

## 运行时契约 (Runtime Contract)

- Python 运行时：`python3`（`research-search`，严禁自建 `venv` 或执行 `pip install`）。
- 受管全局 CLI：`agent-reach`（9 通道体检）、`reach-hub`（主力聚合引擎）、`omnireach`、`opencli`（`:9223` 字幕桥接）。

## 一、 健康诊断与 8 平台实时热榜雷达

```bash
agent-reach doctor --json
reach-hub auth-status
# 支持 all / weibo / douyin / zhihu / xiaohongshu / bilibili / baidu / v2ex / hackernews + 本地 Qwen3-Reranker-4B 重排
reach-hub hotlist --platform all --keyword "AI|模型|芯片" --rerank "大语言模型与算力动态" --limit 10
```

## 二、 分平台核心检索命令

```bash
# 1. 微信公众号 & 腾讯元宝搜索 (so.qq.com)：免登 ~1s 直出永久 __biz= 直链 + AI SSE 长尾召回 + 自动过滤已迁移死号
reach-hub wechat search "Claude Code MCP" --limit 5 --with-body
reach-hub wechat read "https://mp.weixin.qq.com/s?..."
reach-hub so-qq search "Agent 架构" --tab media --time 1w --limit 8

# 2. 小红书：:9223 页内原生 window.__INITIAL_STATE__ 引擎（零导出 Cookie、零跨进程伪造 X-s 签名防互踢掉线）
python3 $HOME/.agents/skills/agent-reach/scripts/xhs_research.py search "关键词" --limit 5
reach-hub xiaohongshu feed --limit 10
reach-hub xiaohongshu read "<note_url_with_xsec_token>" --limit 20
reach-hub xiaohongshu login

# 3. 抖音 & 知乎（未登录或触发滑块时诚实返回 ok:false, error:AUTH_REQUIRED）
reach-hub douyin search "关键词" --limit 5
reach-hub douyin author "@差评君" --limit 10 --order likes
reach-hub douyin comments "<aweme_id>" --limit 20
reach-hub zhihu search "关键词" --limit 5
reach-hub zhihu read "https://zhuanlan.zhihu.com/p/663050853"

# 4. Bilibili、YouTube、Twitter/X、Reddit、V2EX、吾爱破解 (52pojie)
bili search "关键词" --type video -n 5
opencli bilibili subtitle "BV16Bnh6gEAp"
reach-hub youtube subtitle "7xTGNNLPyMI"
reach-hub twitter search "@karpathy" --limit 5
reach-hub reddit search "Claude Code" --limit 5
reach-hub 52pojie search "frida hook" --limit 5
reach-hub 52pojie read "<tid_or_url>"
```

## 三、 按需参考导航

- 语义/网页/开发检索：[`references/search.md`](./references/search.md) · [`references/web.md`](./references/web.md) · [`references/dev.md`](./references/dev.md)
- 视频/社媒/职场专项：[`references/video.md`](./references/video.md) · [`references/social.md`](./references/social.md) · [`references/xiaohongshu/engagement.md`](./references/xiaohongshu/engagement.md) · [`references/career.md`](./references/career.md) · [`references/install-notes.md`](./references/install-notes.md)

## 四、 安全、反爬识别与防毒化媒体红线

1. **只读与零残留**：严禁自动点赞/发帖/私信；所有 `:9223` 后台采集自动归入简洁中文语义组并在 `finally` 中调用 `/cleanup` 清零（`agentTabsCount == 0`）；严禁回显真实 Cookie。
2. **反爬壳诚实披露**：遇到 `Just a moment...`、`403` 或验证码壳页时如实标记“正文未获取”，严禁将拦截页当正文或脑补招生简章/政策数字。
3. **抖音图文区分与防 `2011 INVALID_MEDIA` 铁律**：抖音图文（`aweme_type=68`）的 `video.play_addr` 实为 `.m4a` 音频，真实图片在 `image_urls`；任何下载文件喂给 `read_file` 前必须经 `ffmpeg -y -i <in> -vf "scale='min(960,iw)':-1" -frames:v 1 -q:v 6 <out.jpg>` 转为 `<150 KB` 真实 Baseline JPEG（`\xff\xd8\xff`），误触报错时立即调 `fix_agy_invalid_media.py --write`。
4. **相邻技能分工**：结构化企业/法规/专利查 `anysearch`；学术文献查 `academic-literature-search`；GitHub/HF 查 `developer-resource-search`；逆向工程联合 `linuxdo` 与 `52pojie` 低频单帖精读。
