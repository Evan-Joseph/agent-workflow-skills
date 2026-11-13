---
name: video-use
description: "音视频工程、剪辑成片与格式转码中枢。支持基于 ffmpeg 的音视频格式转换、拼接、压缩、GIF 制作、音频提取，以及 Agent 驱动的素材盘点、语音转录、字幕生成、EDL 剪辑、调色与最终成片自检。在需要视频制作、音视频格式转换或媒体素材处理时使用。"
metadata:
  short-description: 音视频处理、格式转码与Agent视频剪辑成片
---

# Video Engineering & Production

统一管理本地媒体文件处理与全流程视频剪辑工程。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/video-use/scripts/transcribe.py input.mp4 --edit-dir ./edit
  python3 $HOME/.agents/skills/video-use/scripts/timeline_view.py input.mp4 0 15 -o timeline.jpg
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **底层媒体工具与凭据**：必须使用系统安装的 `ffmpeg` 与 `ffprobe` CLI；`scripts/transcribe.py` 支持 `--backend {auto,mlx,whisper-cli,elevenlabs}`（`auto` 优先使用零成本本地 Apple Silicon `mlx_whisper` / `whisper-cli` 离线词级转录，云端 ElevenLabs Scribe 自动读取 `~/.config/elevenlabs/elevenlabs.env` 中的 `ELEVENLABS_API_KEY`）。

## 1. 基础音频/视频处理速查 (FFmpeg CLI)

涉及音视频单步转码、压缩、截取或提取时，直接调用本地 ffmpeg CLI：

```bash
# 格式转码与压制（强制携带 -pix_fmt yuv420p -movflags +faststart 保障 macOS QuickTime / Safari / Web <video> 首帧流式兼容）
ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium -movflags +faststart -c:a aac output.mp4

# 快速提取音频
ffmpeg -i input.mp4 -vn -c:a copy output.m4a

# 生成高清动图 GIF
ffmpeg -i input.mp4 -vf "fps=15,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" output.gif

# 视频无损裁切
ffmpeg -ss 00:00:10 -to 00:00:30 -i input.mp4 -c copy cut.mp4
```

## 2. Agent 驱动的智能剪辑流水线 (Video Production)

当任务涉及从一段或多段长视频素材制作成片时：
1. **素材盘点与语音识别**：提取音轨并结合转录脚本生成带时间戳的字幕与词级对齐文件（详情参阅 [`references/transcription-and-privacy.md`](./references/transcription-and-privacy.md)）：
   ```bash
   SKILL_DIR=$HOME/.agents/skills/video-use
   PY=python3
   # 单文件或批量转录与打包（--backend auto 默认优先本地 mlx_whisper/whisper-cli 离线转录，亦支持 --backend elevenlabs）
   $PY $SKILL_DIR/scripts/transcribe.py input.mp4 --backend auto --edit-dir ./edit
   $PY $SKILL_DIR/scripts/transcribe_batch.py ./footage_dir --edit-dir ./edit
   $PY $SKILL_DIR/scripts/pack_transcripts.py --edit-dir ./edit
   ```
2. **EDL (Edit Decision List) 剪辑决策与时间线预览**：按主题逻辑裁剪无效段落，生成结构化时间线与胶片波形图（规范参阅 [`references/edl-and-rendering.md`](./references/edl-and-rendering.md)）：
   ```bash
   $PY $SKILL_DIR/scripts/timeline_view.py input.mp4 0 15 -o timeline.jpg
   ```
3. **调色、响度归一化、BGM 闪避与最终渲染**：应用预设/自动调色与压制成片，**成片交付强制执行响度归一化（`-af "loudnorm=I=-16:TP=-1.5:LRA=11"`），含口播 + BGM 混音时强制叠加侧链自动闪避（`sidechaincompress`）防 BGM 盖过人声**（FFmpeg 高级配方参阅 [`references/ffmpeg/recipes.md`](./references/ffmpeg/recipes.md) 与 [`references/ffmpeg/local-transcription-api.md`](./references/ffmpeg/local-transcription-api.md)）：
   ```bash
   $PY $SKILL_DIR/scripts/grade.py input.mp4 --preset warm_cinematic -o graded.mp4
   $PY $SKILL_DIR/scripts/render.py project.edl.json -o raw_final.mp4
   ffmpeg -y -i raw_final.mp4 -c:v copy -af "loudnorm=I=-16:TP=-1.5:LRA=11" -movflags +faststart final.mp4
   ```
4. **交付前受众视角自审与抽帧防爆库门禁（Pre-Delivery Audience Self-Review Gate — P1-1）**：
   - **纯 BGM 无配音视频排版规范**：无口播配音的纯 BGM 宣传片/展示片严禁保留底部字幕条撕裂画面视线，统一采用穿插式杂志大字报（Interstitial Kinetic Typography）排版；特定单期选题（如“信息茧房”）定制脚本留在对应项目工作区内，不混入全局 `video-use` Skill；音视频素材去重必须结合 `ffmpeg` 音频波形互相关（Cross-Correlation）与多模态抽帧核验。
   - **受众视角自审闭环（必做）**：成片交付前，必须抽取关键叙事节点与转场帧并压缩为 `<150 KB` 真实 JPEG/PNG（多帧拼图须校验各帧哈希互不相同，严禁同一帧贴三次），亲自调用 `read_file` 结合音轨时长从**首次观看的受众视角**完整审视一遍，核对黑帧、音画同步、信息停留时长与叙事逻辑是否清晰顺畅。

## 3. 代码驱动视频、Remotion 与艺术歌词 MV 工程矩阵 (Code-Driven Video & MV Production)

When tasks involve **code-generated video (HTML Canvas 2D / Three.js WebGL / GLSL Shaders / `p5.brush` ink & watercolor / Remotion)**, **artistic lyric MVs**, or **voiceover-free visual essays**, read [`references/code-video-and-mv-ecosystem.md`](./references/code-video-and-mv-ecosystem.md) first and follow these architectural rules:

1. **工具路由裁决（确定性代码渲染 vs 云端 SaaS 插件）**：
   - **主线强制走本地确定性代码渲染**：暴露纯函数时间接口 `window.seek(t)` / `window.render(t)` / `useCurrentFrame()`，配合 `mulberry32` 确定性随机种子、闭式阻尼弹簧、自适应子帧快门运动模糊与本地 FFmpeg 高码率压制；
   - **排除云端模板插件混入代码 MV 主线**：Antigravity 插件市场中的 `invideo` (`invideoio/skills` + `https://mcp.invideo.io/mcp`) 与 `canva` 属于云端 SaaS 多轨剪辑/模板工具，不支持自定义 Shader、物理弹簧与帧级确定性代码渲染，且调用生成接口消耗付费 Credits，仅在用户明确需要云端 Stock 素材拼接或人工浏览器时间线粗剪时按需选用。
2. **四大代码 MV 引擎与上游标杆仓库（本地克隆目录索引见 [`references/code-video-and-mv-ecosystem.md`](./references/code-video-and-mv-ecosystem.md)，本地模型调用统一经唯一网关 MagPie `${OPENAI_COMPAT_BASE_URL}`：脚本与代码规划 `group/opus`、视觉审美 `group/carbon`）**：
   - **声学解构与导演总控（[`Yari-tuber/mv-director`](https://github.com/Yari-tuber/mv-director)）**：`listen.py --demucs` 分离人声与伴奏、提取小节/鼓点/逐字时间戳 `song.json` -> `cues.json` 编写 `says / see / keys` 具象视觉隐喻分镜（遮住字幕仍能看懂歌词） -> `cue_lint.py` 静态检查 -> `check.py` 机器审计（首字显现窗口 `[-0.35s, +0.15s]`、小节重拍命中率 `>=70%`、零 `>1s` 死帧、音画能量相关系数 `>=0.40`）；
   - **专项渲染引擎**：[`lqiaoqing/agent-skills`](https://github.com/lqiaoqing/agent-skills) 下的 `kinetic-lyric-mv`（Three.js/GLSL 3D 高动能排版与 CJK 逐字格点，禁伪斜体）、`painted-mv`（`p5.brush` 12fps 手绘抖动墨线 + 水彩晕染 + 书法双语卡拉 OK）、`paper-story`（Canvas 2D 多层剪纸木偶骨骼视差），以及 `lemo-opuscar`（66 套导演风格卡 + `readcheck.mjs` 中文阅读驻留校验）、`huashu-art-motion`（53 张艺术风格卡 + `long_scroll` 横向一镜到底长卷 + `film_gate.py` 反 PPT / 反蓝紫 AI 塑料感门禁）；
   - **Remotion 官方规范（`remotion-dev/skills` v4.0.541）**：将 `useCurrentFrame()` 下沉至叶子组件隔离重渲染，所有时序参数乘以 `useVideoConfig().fps`，严禁 CSS/Tailwind 动画。
