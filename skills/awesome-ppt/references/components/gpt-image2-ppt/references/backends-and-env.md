# Backends And Environment

本文件在需要选择原生 image_generation、Grsai/OpenAI API、Codex CLI 后端，或检查环境变量时读取。

## Backend Priority

1. 当前 Agent 自带 `image_generation` 工具且可用登录态时，优先走原生路径，不运行 `generate_ppt.py`。
2. 没有原生出图工具，但已配置 `OPENAI_API_KEY` 或 `GRSAI_API_KEY` 时，走 `generate_ppt.py` 默认 API 后端。
3. 没有 API key，但本机 Codex CLI 已登录且用户接受慢速路径时，走 `--backend codex`。

## Grsai / OpenAI Compatible API

默认本机私有配置文件：

- `~/.config/gpt-image2-ppt/gpt-image2-ppt.env`：本 Skill 的首选
  `OPENAI_*` / `GPT_IMAGE_*` 配置。
- `~/.config/grsai/grsai.env`：共享 Grsai 配置兜底，可提供
  `GRSAI_API_KEY` 和 `GRSAI_BASE_URL`。
- `GPT_IMAGE2_PPT_ENV=/path/to/file.env`：显式覆盖，优先级最高。

推荐环境变量：

```bash
OPENAI_BASE_URL=https://grsaiapi.com
GRSAI_API_KEY=sk-...
GPT_IMAGE_MODEL_NAME=gpt-image-2
GPT_IMAGE_QUALITY=high
GPT_IMAGE_ENDPOINT=grsai
```

国内节点：

```bash
OPENAI_BASE_URL=https://grsai.dakka.com.cn
GRSAI_API_KEY=sk-...
```

兼容变量：

- `OPENAI_API_KEY`：旧脚本兼容变量。
- `GPT_IMAGE_ENDPOINT=auto|images|chat|grsai`。
- `GPT_IMAGE_MODEL_NAME=gpt-image-2|gpt-image-2-vip`。
- `GPT_IMAGE_QUALITY=low|medium|high|auto`。

安全规则：

- 不读取用户项目目录里的 `.env`。
- 脚本只从显式 `GPT_IMAGE2_PPT_ENV`、用户私有配置目录和 legacy Skill
  安装位置加载凭据。
- 不把 API key 写入 slides plan、prompts、HTML、PPTX 或报告。

## Grsai Native API

当前 Grsai native 图片/视频接口：

- 生成：`POST /v1/api/generate`
- 异步查询：`GET /v1/api/result?id=<task_id>`

旧的 `/v1/draw/*` 路径不要再用。

模型约束：

- `gpt-image-2`：支持比例，例如 `"16:9"`，也支持像素值，例如 `"1024x1024"`。
- `gpt-image-2-vip`：仅支持像素值，不支持比例。
- `gpt-image-2-vip` 的最大边长不超过 3840px，两边都是 16 的倍数，长边:短边不超过 3:1，总像素在 655,360 到 8,294,400 之间。

`replyType`：

- `json`：同步返回完整结果。
- `stream`：流式返回。
- `async`：异步模式，需轮询查询结果。

## Vision Backend For Template Analysis

模板克隆时，vision 分析和图片生成各自按本机真源路由：

- 如果当前 Agent 自己具备多模态看图能力，可直接读取模板页 PNG 并写入 `template_cache/<sha256>.json`。
- 当脚本自动执行模板视觉剖析（`scripts/template_analyzer.py`）时，默认直连本机唯一模型网关 **MagPie `${OPENAI_COMPAT_BASE_URL}`**（确定性组 `VISION_MODEL_NAME=group/carbon`），自动只读加载 `~/.agents/config/magpie-ops-probe.json` 或 `VISION_API_KEY` / `MAGPIE_API_KEY` 环境变量（本地回环请求强制旁路代理，严禁硬编码旧密钥）。
- Grsai 生图通道（`scripts/image_generator.py`）直接委托复用 `$HOME/.agents/skills/image-generation/scripts/grsai_generate.py` 的核心实现与 `~/.config/grsai/grsai.env`。

## Codex CLI Backend

当前 Agent 没有原生出图工具、又不想配 API key 时，可以借用已登录的 Codex CLI：

```bash
python3 scripts/generate_ppt.py --plan slides_plan.json --style styles/editorial-mono.md --backend codex
```

Tradeoffs：

- 不需要在 Skill 里配置 `OPENAI_API_KEY`。
- 慢，每页可能 30-60 秒以上。
- 计费仍按图片模型调用计算。
- aspect ratio、quality、reference image 依赖自然语言 relay，稳定性弱于原生工具和 API 后端。

可选环境变量：

```bash
CODEX_CMD="codex exec --full-auto"
CODEX_IMAGE_MODEL=gpt-image-2
CODEX_TIMEOUT_SECS=900
GPT_IMAGE_BACKEND=codex
```
