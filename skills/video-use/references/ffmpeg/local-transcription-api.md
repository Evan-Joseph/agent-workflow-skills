# Canonical Transcription Workflow (`video-use`)

本机音视频转录统一通过 `video-use/scripts/` 下的标准脚本完成（底层使用 `ffmpeg` 提取 16kHz 单声道音频并调用 ElevenLabs Scribe 词级时间戳接口），不依赖任何外部私有端口或未托管的本地 HTTP 守护进程。

## 1. 运行时与凭据

- **统一解释器**：`python3`
- **凭据文件**：`~/.config/elevenlabs/elevenlabs.env`（环境变量 `ELEVENLABS_API_KEY`）
- **隐私与授权**：详见 [`../transcription-and-privacy.md`](../transcription-and-privacy.md)

## 2. 标准命令

### 单文件转录 (`transcribe.py`)

```bash
python3 $HOME/.agents/skills/video-use/scripts/transcribe.py input.mp4 --edit-dir ./edit
```

可选参数：
- `--language zh` / `--language en`：指定语言代码（默认自动检测）
- `--num-speakers 2`：指定说话人数量以优化说话人分离（Diarization）
- `--force`：忽略已有缓存强制重新转录

### 目录批量并发转录 (`transcribe_batch.py`)

```bash
python3 $HOME/.agents/skills/video-use/scripts/transcribe_batch.py ./footage_dir --edit-dir ./edit --workers 2
```

### 词级转录打包为短语级时间线 (`pack_transcripts.py`)

```bash
python3 $HOME/.agents/skills/video-use/scripts/pack_transcripts.py --edit-dir ./edit
```

## 3. 产物结构说明

1. **原始词级 JSON (`<edit-dir>/transcripts/<stem>.json`)**：
   - `text`：完整转录文本
   - `words`：包含 `word`、`spacing`、`audio_event` 三类词元及精确 `start`、`end`、`speaker_id`
2. **剪辑决策短语索引 (`<edit-dir>/takes_packed.md`)**：
   - 按静音阈值（默认 `>= 0.5s`）或说话人切换自动分句，并对中文字符执行无空格拼接，供生成 EDL 与 `render.py --build-subtitles` 直接消费。
