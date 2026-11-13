# 代码驱动视频、Remotion 与艺术歌词 MV 生态架构与工程规范

> **定位**：本文档沉淀 Antigravity 官方插件市场、Remotion 官方及社区技能矩阵、以及代码驱动艺术歌词 MV / 零配音视觉短片（UNRAVEL STUDIO 主线）的完整技术选型、确定性时钟契约、分镜隐喻门禁与自动化质检标准。
> - **本地上游参考仓库仓（已克隆）**：[`$WORKSPACE_DIR`]($WORKSPACE_PATH)（本地保留 `lemo-opuscar`、`huashu-art-motion`、`awesome-opus5-5-videos`；`mv-director` 与 `lqiaoqing/agent-skills` 直连上游 GitHub 仓库参考）
> - **全局索引对照**：[`$WORKSPACE_DIR`]($WORKSPACE_PATH)

---

## 1. 生态分类与工具路由裁决矩阵（SaaS 云端时间线 vs 确定性代码渲染）

在接到视频创作需求时，第一步必须区分**「云端 NLE 模板 / Stock 素材拼接流水线」**与**「确定性代码渲染（Deterministic Code Video / Mathematical Shaders）」**两条截然不同的技术路线：

| 维度 | 确定性代码渲染工作流（本机主力路线）<br>`Remotion` / `WebGL & Three.js` / `Canvas 2D` / `p5.brush` / `HyperFrames` | Antigravity 插件市场云端 SaaS 工作流<br>`invideo` (`invideoio/skills`) / `canva` |
| :--- | :--- | :--- |
| **底层渲染机制** | 暴露确定性时间函数 `window.seek(t)` / `window.render(t)` / `useCurrentFrame()`，由无头 Chromium 逐帧光栅化 + 本地 FFmpeg 高码率压制 | 调用远程 MCP (`https://mcp.invideo.io/mcp`) 或 CLI 操作云端多轨剪辑器、Stock 素材库、SaaS 模板与云端生成式 AI 接口 |
| **核心代表生态** | 1. [`remotion-dev/skills`](https://github.com/remotion-dev/skills) (`v4.0.541`, 6.5k Stars)<br>2. [`lemomo-ai/lemo-opuscar`](https://github.com/lemomo-ai/lemo-opuscar) (13.1k Stars, 66 套导演风格)<br>3. [`alchaincyf/huashu-art-motion`](https://github.com/alchaincyf/huashu-art-motion) (6.4k Stars, 53 张艺术风格卡)<br>4. [`Yari-tuber/mv-director`](https://github.com/Yari-tuber/mv-director) + [`lqiaoqing/agent-skills`](https://github.com/lqiaoqing/agent-skills) (`kinetic-lyric-mv` / `painted-mv` / `paper-story`)<br>5. [`heygen-com/hyperframes`](https://github.com/heygen-com/hyperframes) (77.1k Stars) | 1. `antigravity-plugins-partners/plugin/invideo`（含 `/invideo`, `/invideo-timeline`, `/invideo-media`, `/invideo-generate`, `/hyperframes-to-invideo` 等 7 个子技能）<br>2. `antigravity-plugins-partners/plugin/canva`（Canva Connect MCP 静态/轻量版式设计） |
| **音画同步与视觉上限** | **帧级确定性（`<1.5f` 误差）**：支持 HPSS 鼓点/能量包络直接驱动 GLSL Raymarching 着色器、Three.js 粒子场、水墨/水彩动态笔触（`p5.brush`）、闭合阻尼弹簧与 $4\times$ 子帧快门运动模糊 | 仅支持轨道级剪辑（`roll`/`slip_clip`）、LUT 滤镜、预设转场与关键帧；**无法直接运行自定义 Shader、物理弹簧或代码粒子**（连其自带的 `hyperframes-to-invideo` 都要求先在本地将代码渲染为 MP4 再上传至云端当普通视频轨道切） |
| **算力与资金成本** | **100% 本地零边际成本**：本地音频分析 + 唯一本地网关 MagPie（`${OPENAI_COMPAT_BASE_URL}`，脚本规划与代码生成走 `group/opus`、多模态视觉审美走 `group/carbon`）+ 本地无头 Chrome / FFmpeg 渲染 | 时间线剪辑免费，但 `/invideo-generate`（调用 `seedance_2_5`、`nanobanana_pro`、`elevenlabs` 等）持续消耗 InVideo 付费订阅 Credits |
| **路由裁决结论** | **强制用于**：艺术歌词 MV（如 EP03《精卫》）、零配音深度视觉论文（如 EP01《信息茧房》、EP02《超级个体》）、算法/数学可视化、Apple Keynote 级产品宣传片 | **不纳入代码 MV 主线**；仅当用户明确要求“使用云端 Stock 实拍素材/数字人拼装商业口播广告，且需要在浏览器 GUI 时间线手动拖拽精修”时按需选用 `invideo` |

---

## 2. 确定性代码渲染通用时钟与工程契约（Deterministic Clock Contract）

无论底层采用原生 HTML Canvas、Three.js WebGL、SVG+GSAP、`p5.brush` 还是 Remotion，所有代码生成视频必须严守以下 5 条物理工程契约：

1. **纯函数式时间驱动（Pure Function of Time `t`）**：
   - 画面在任意时刻 $t$（秒）或帧号 $f = \lfloor t \times \text{fps} \rfloor$ 的像素状态，必须 **100% 唯一取决于输入参数 $t$**。
   - 严禁使用 `Math.random()`（必须替换为确定性种子伪随机数生成器 `mulberry32(seed)`）、`Date.now()`、`performance.now()`、未绑定的 `requestAnimationFrame` 自增状态或 CSS `transition` / `animation`。
   - **标准暴露接口**：
     - **`mv-director` / `kinetic-lyric-mv` / `painted-mv` 规范**：`window.Duration = <秒>`, `window.FPS = 30`, `window.seek = function(t) { ... }`；
     - **`lemo-opuscar` / `huashu-art-motion` 规范**：`window.DUR = <秒>`, `window.render = function(t) { ... }`, `window.READY = true`, `window.EV = [...]`, `window.TEXTS = function(t) { ... }`。
2. **闭式阻尼弹簧与非对称物理加减速（Closed-Form Damped Spring）**：
   - 严禁使用呆板的 `linear` 线性插值。镜头推拉、元素入场与鼓点脉冲统一使用解析闭式阻尼弹簧：
     $$\text{spring}(t, \omega, \zeta) = 1 - e^{-\zeta \omega t}\left(\cos(\omega_d t) + \frac{\zeta \omega}{\omega_d}\sin(\omega_d t)\right), \quad \omega_d = \omega\sqrt{1-\zeta^2}$$
   - 冲击动作遵循 `Anticipation（预备反向蓄力 3–5 帧） -> Action（主动作爆发） -> Follow-through（惯性过冲与微颤回落）`。
3. **自适应子帧快门运动模糊（Adaptive Sub-Frame Shutter Blur）**：
   - 在高速甩镜（`whipPan`）、穿越推镜（`pushThrough`）或大字重锤砸落（`slam`）帧段，采用 $4\times \sim 8\times$ 子帧过采样（在 $[t - \frac{\text{shutter}}{2\cdot\text{fps}}, t + \frac{\text{shutter}}{2\cdot\text{fps}}]$ 区间内按高斯权重累加子帧），彻底消除代码动画的“电子生硬塑料感”。
4. **五层电影级视觉纵深栈（5-Layer Visual Depth Stack）**：
   - 每一帧由下至上强制构建 5 个深度层：
     - `Layer 1`：物理肌理底板（宣纸纤维、粗麻画布、暗房微网格或深海噪波，严禁纯色死黑 `#000000` 或纯白 `#FFFFFF`）；
     - `Layer 2`：远景视差环境层（`0.35x` 相机位移速率，承载氛围光晕、水墨远山或星云流场）；
     - `Layer 3`：核心叙事主体与具象隐喻装置（`1.0x` 速率，承载随音频能量演化的主视觉与动态排印）；
     - `Layer 4`：前景快速掠影层（`1.4x` 速率 + 景深虚化，制造强烈空间穿梭感）；
     - `Layer 5`：全局胶片颗粒（FFmpeg 后期 `noise=c0s=5:c0f=t+u` 或 SVG `feTurbulence`）+ 暗角遮罩（`vignette`）+ 柔和色彩分级。
5. **原曲母带直通与响度标准化（Master Audio Pass-Through & `-14 LUFS`）**：
   - 艺术歌词 MV 必须 100% 挂载原曲无损/高码率母带，严禁二次有损重采样或叠加破坏原曲混音的廉价电子音效；
   - 旁白解说或自合成音轨统一执行 FFmpeg 两遍 `loudnorm=I=-14:TP=-1.5:LRA=11` 响度标准化，并携带 `-pix_fmt yuv420p -movflags +faststart`。

---

## 3. 代码驱动艺术歌词 MV 四大引擎与五步工业流水线

针对《精卫》及后续音乐 MV / 艺术短片创作，本机已集成 `mv-director`、`kinetic-lyric-mv`、`painted-mv`、`paper-story`、`lemo-opuscar` 与 `huashu-art-motion` 完整方法论：

### 3.1 四大专项 MV 渲染引擎选型表

| 引擎名称 | 上游仓库 | 核心技术栈 | 最佳适用曲风与视觉母题 |
| :--- | :--- | :--- | :--- |
| **`mv-director`**（导演总控与歌词卡点管线） | [`Yari-tuber/mv-director`](https://github.com/Yari-tuber/mv-director) | `listen.py` (`librosa` + `demucs` + 词级强制对齐) -> `cues.json` (`says`/`see`/`keys`) -> `cue_lint.py` -> `check.py` | **所有歌词 MV 的前置声学解构、逐句分镜设计与同步率机器验收总控** |
| **`kinetic-lyric-mv`**（3D/GLSL 高动能排版 MV） | [`lqiaoqing/agent-skills` (`skills/kinetic-lyric-mv`)](https://github.com/lqiaoqing/agent-skills/tree/main/skills/kinetic-lyric-mv) | Three.js WebGL2 + GLSL Raymarching / 版画排线着色器 + Bloom + CJK 逐字格点引擎 (`NotoSansSC`, `isCJK()`) | 摇滚、电子、先锋实验、强烈情绪爆发曲目（如《精卫》副歌怒海填石、工业/哲思摇滚） |
| **`painted-mv`**（手绘水墨/水彩艺术 MV） | [`lqiaoqing/agent-skills` (`skills/painted-mv`)](https://github.com/lqiaoqing/agent-skills/tree/main/skills/painted-mv) | `p5.brush`（12fps 手绘抖动墨线 Boiling Line + 水彩晕染 Fill/Hatch/Flowfield）+ `Ma Shan Zheng` 书法双语卡拉 OK | 国风、民谣、古典诗词、东方神话、抒情叙事曲目（如《精卫》古风叙事段、敦煌/水墨长卷） |
| **`paper-story`**（多层剪纸木偶戏剧 MV） | [`lqiaoqing/agent-skills` (`skills/paper-story`)](https://github.com/lqiaoqing/agent-skills/tree/main/skills/paper-story) | Canvas 2D 关节木偶骨骼（Articulated Puppet Rig）+ 多层纸雕投影视差 + 6 秒分块断点续传渲染 | 寓言故事、童话暗黑叙事、皮影/剪纸民俗风格短片 |

### 3.2 艺术歌词 MV 五步标准工序（5-Stage Pipeline）

1. **Stage 1 — 多维声学解构与逐字强制对齐（Acoustic & Word-Level Alignment）**：
   - 运行 `listen.py audio.mp3 --lyrics lyrics.lrc --demucs -o work/`，分离人声干声（Vocals）与伴奏（Drums / Bass / Other），生成：
     - `song.json`：包含精确 BPM、`beats`、`downbeats`、`bars`（小节时间表）、`kick` / `snare` 瞬态峰值、逐帧 `energy` 曲线，以及精确到**每个汉字起止毫秒**的 `words` 时间数组；
     - `song.md` & `songmap.png`：全曲结构热力图与小节对照表。
2. **Stage 2 — 剧本分镜与具象视觉隐喻契约（Storyboard & `says/see/keys` Gate）**：
   - 严禁把歌词 MV 做成“背景放个无关紧要的抽象万花筒 + 屏幕中间排歌词”的劣质 KTV 字幕片！
   - 每一句歌词在 `cues.json` 中必须填写三个字段并通过 `cue_lint.py` 校验：
     - `says`：这句歌词的字面文本与潜台词；
     - `see`：**如果遮住所有字幕，观众在画面上看到什么具象物体发生了什么具体动作，从而立刻听懂这句歌词？**（例如唱“你我生来像纸一样”，画面必须真有一张白纸被折出折痕、浸水晕开或被火苗舔舐，绝不允许画抽象圆圈）；
     - `keys`：该句中承担情绪重音的 1–2 个核心词（采用字重加粗、字号放大 `1.3x–1.8x`、朱砂印章色 `#C83E31` 或物理碎裂动效突出，**中文字体严禁使用伪斜体 faux-italic**）。
   - **一镜到底世界观（One World + Continuous Camera / `long_scroll`）**：全曲建立一个连续演进的视觉世界（如《精卫》从枯枝微光 -> 坠海化鸟 -> 衔木投石 -> 怒海焚天），镜头以 `barN`（第 N 小节首拍）或 `lineM@关键词` 为符号锚点平滑推拉横移，杜绝每句歌词硬切一个毫无关联的背景。
3. **Stage 3 — 15–30 秒高潮样片先行与三阶网格看片（Sample First & Grid Preview）**：
   - 在铺开全曲 3–4 分钟代码前，先用 `render.py lines`（每句歌词中心帧生成一张带歌词标注的 4K/1080p 网格图）与 `render.py bars`（前奏+第一段主副歌 30 秒样片）验证画风、字号与鼓点响应。
   - **审美红线（`film_gate.py` 机器门禁）**：
     - 严禁 AI 廉价蓝紫霓虹配色（`#6630F8` / `#00FFFF` 占比 `>30%` 直接拦截）；
     - 严禁画面静止超过 `1.0s` 的死帧（器乐间奏段必须安排镜头穿行或意象演变）；
     - 严禁顶部/左上角挂常驻章节药丸、页码或底部进度条。
4. **Stage 4 — 全片确定性帧捕获与高码率压制（Deterministic Frame Capture）**：
   - 多 Worker 并行开启无头浏览器页面，逐帧调用 `window.seek(f / fps)` 截屏并通过管道喂给 FFmpeg（`libx264 -crf 16 -preset slow -pix_fmt yuv420p`），直接复用原曲音频流生成成片。
5. **Stage 5 — 机器同步率审计与受众视角终审（`check.py` & Audience Gate）**：
   - 运行 `check.py` 校验四项硬指标：
     1. **歌词登场窗口**：每句首字视觉显现时间落在人声发音前 `[-0.35s, +0.15s]` 区间内（略早于人声半拍最符合人类视听预期）；
     2. **小节重拍命中率**：视觉大动作与镜头切换落在 `downbeats` 小节首拍的比例 `>= 70%`；
     3. **阅读驻留时长（`readcheck.mjs`）**：中文字幕有效驻留时长 $\ge \frac{\text{字数}}{4.5} + 1.5\text{s}$；
     4. **情绪能量相关系数**：画面帧间像素运动量曲线与音频 RMS `energy` 曲线的皮尔逊相关系数 `>= 0.40`。
   - 最后抽取 `<150 KB` 关键帧拼图调用 `read_file` 完成受众视角人工终审。

---

## 4. Remotion 官方最佳实践精要（`remotion-dev/skills` v4.0.541）

当项目采用 React + Remotion 架构时，除遵守上述通用契约外，须执行以下官方核心规范：

1. **将 `useCurrentFrame()` 严格下沉至叶子组件（Leaf Isolation）**：
   - 顶层 `<Scene>` 或包含重型 Canvas / Three.js / 地图的父组件严禁直接调用 `useCurrentFrame()`，否则每一帧都会触发整棵虚拟 DOM 树重渲染；应将随帧变化的样式或位移封装在最末端的 `<AnimatedTransform>` 叶子组件内。
2. **全量基于 `useVideoConfig().fps` 计算时序**：
   - `<Sequence from={Math.round(2.5 * fps)} durationInFrames={Math.round(4.0 * fps)}>` 与 `<Audio trimBefore={...}>` 必须乘以动态 `fps`，严禁硬编码 `30` 或 `60` 帧号，以便在 `30fps` 预览与 `60fps` 母带间无缝切换。
3. **字体、纹理与 3D 资产的帧阻塞加载（`delayRender` / `continueRender`）**：
   - 本地大字体（如思源宋体、马善政毛笔体）、Three.js 纹理或复杂 SVG 必须通过 `@remotion/google-fonts`、`<Img>` 或 `delayRender()` 阻塞到 100% 就绪后再开始截帧，彻底杜绝首帧字体闪烁（FOUT）或白块。
