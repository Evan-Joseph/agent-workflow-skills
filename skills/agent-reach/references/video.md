# 视频/播客

YouTube、B站、小宇宙播客的字幕和转录。

## YouTube (yt-dlp)

### 获取视频元数据

```bash
yt-dlp --dump-json "URL"
```

### 下载字幕

```bash
# 下载字幕 (不下载视频)
yt-dlp --write-sub --write-auto-sub --sub-lang "zh-Hans,zh,en" --skip-download -o "/tmp/%(id)s" "URL"

# 然后读取 .vtt 文件
cat /tmp/VIDEO_ID.*.vtt
```

### 获取评论

```bash
# 提取评论（best-effort，不保证完整）
yt-dlp --write-comments --skip-download --write-info-json \
  --extractor-args "youtube:max_comments=20" \
  -o "/tmp/%(id)s" "URL"
# 评论在 .info.json 的 comments 字段中
```

### 搜索视频

```bash
yt-dlp --dump-json "ytsearch5:query"
```

> **字幕注意**: 手动上传的字幕提取可靠；自动生成字幕可能存在行间重复，需后处理。
> **评论注意**: `--write-comments` 基于网页抓取（非 YouTube Data API），部分评论可能丢失。

### 无字幕兜底：提取音频转写

```bash
# 视频没有原生字幕时：先用 yt-dlp 仅下载低码率音频流，再交由 video-use 技能的 ASR 转录流水线处理
yt-dlp --js-runtimes node -x --audio-format mp3 -o "/tmp/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=VIDEO_ID"
```

## B站 / Bilibili（bili-cli 为主，OpenCLI 补字幕）

> **不要用 yt-dlp 读 B站**：B站风控已全面 412 拦截 yt-dlp（实测最新版、直连/代理/带 Cookie 全部无效）。yt-dlp 只用于 YouTube。

### 视频详情/搜索/热门/排行 (`bili`，只读无需登录)

```bash
# 视频详情（标题/UP主/时长/播放互动数据/字幕可用性）
bili video BVxxx

# 搜索视频
bili search "query" --type video -n 5

# 热门视频 / 排行榜
bili hot -n 10
bili rank -n 10

# 下载音频并切分为 ASR-ready WAV（无 CC 字幕时供本地 ASR 转写）
bili audio BVxxx
```

### 字幕 (`opencli` 9223 桥接)

```bash
# 字幕逐句带时间轴（自动经 ${CDP_RELAY_HOST} 持久守护静默获取）
opencli bilibili subtitle BVxxx

# OpenCLI 搜索/读视频元数据（备选）
opencli bilibili search "query" -f yaml
opencli bilibili video BVxxx -f yaml
```

### 零配置兜底：搜索 API 直连

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
curl -s -c /tmp/bili_ck.txt -o /dev/null -A "$UA" "https://www.bilibili.com/"
curl -s -b /tmp/bili_ck.txt -A "$UA" -e "https://www.bilibili.com/" \
  "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=QUERY&page=1"
```

## 小宇宙播客 / Xiaoyuzhou Podcast

> 说明：旧版外部播客脚本及 `configure/install` 子命令已随 `2026-11-01` 架构收敛下线（现 `agent-reach` 专司 `doctor` 9 通道健康检查）。

### 提取单集 Show Notes 与音源直链

```bash
# 1. 读取单集标题、时间轴与 Show Notes 正文
curl -s "https://r.jina.ai/https://www.xiaoyuzhoufm.com/episode/EPISODE_ID"

# 2. 提取单集原始音频直链（og:audio，通常为 media.xyzcdn.net/*.m4a）并按需下载切片转写
curl -sL "https://www.xiaoyuzhoufm.com/episode/EPISODE_ID" \
  | grep -oE 'https://media\.xyzcdn\.net/[^"'\'']+\.(m4a|mp3)' | head -n 1
```

下载 `.m4a`/`.mp3` 至 `/tmp/` 后，统一调用 `ffmpeg` 预处理并交由 `video-use` 技能的语音转录流程生成带时间戳文稿，收尾清理 `/tmp/` 临时音频文件。

### 检查本机通道健康状态

```bash
agent-reach doctor --json
```

## 选择指南

| 场景 | 推荐工具 |
|-----|---------|
| YouTube 字幕 | `yt-dlp --js-runtimes node` |
| B站视频详情/搜索 | `bili` |
| B站字幕 | `opencli bilibili subtitle` |
| 小宇宙播客 Show Notes / 音源提取 | `r.jina.ai` + `og:audio` 直链提取（ASR 交 `video-use`） |
| 无字幕音视频转写 | `yt-dlp -x` 或 `bili audio` 提取音频后交 `video-use` |
