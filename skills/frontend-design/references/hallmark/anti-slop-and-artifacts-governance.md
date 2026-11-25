# Hallmark 反 AI 味硬门禁（`sloplint`）与生成式 UI / Artifacts 治理细则

本文件融合 GitHub 高星标杆 `Nutlope/hallmark`（`The Floor` + 零依赖静态/渲染门禁 `scripts/sloplint.mjs`）与本机原生桌面工具审美标准，约束所有 Web 页面、插件侧栏（Sidecar Web UI）、`<agent-embed>` 生成式 UI 与 MagPie Artifacts。

## 一、 交付前强制静态门禁命令（`sloplint.mjs`）

所有新建或重构的 `.html` / `.css` / `.jsx` / `.tsx` / `.vue` / `.svelte` 产物在进入无头浏览器截图自审前，必须先通过零外部依赖的 `sloplint.mjs` 扫描，达到 **`0 FAIL, 0 REFLEX`**：

```bash
# 营销页 / 独立站点 / 叙事报告
/opt/homebrew/bin/node $HOME/.agents/skills/frontend-design/scripts/sloplint.mjs <file-or-dir> --genre modern-minimal

# 工具台 / 侧栏面板 / 刷题器 / 管理后台（自动豁免营销首屏与字数预算门禁，聚焦控件密度与状态）
/opt/homebrew/bin/node $HOME/.agents/skills/frontend-design/scripts/sloplint.mjs <file-or-dir> --scope app

# 独立原子组件 / 内联小挂件（<agent-embed>）
/opt/homebrew/bin/node $HOME/.agents/skills/frontend-design/scripts/sloplint.mjs <file-or-dir> --scope component
```

- 样式表第 1 行须声明结构化头部注释（Gate 20）：
  - 工具/应用界面：`/* Hallmark · shape: app screen · genre: modern-minimal · theme: native-monochrome · built: SuperAgent · v2.0.0 */`
  - 存量页面去 AI 味精修：`/* Hallmark · checked: 2026-11-25 · shape: app screen · genre: modern-minimal · built: the project · redesign: polish · v2.0.0 */`

## 二、 五大 AI Slop 视觉指纹禁令（不可豁免的 Floor 红线）

1. **禁大写加字距眉标（Gate 54 & 67）**：
   - 严禁在标题上方放置无实质信息的装饰性短词眉标（如 `OVERVIEW`、`PANORAMA SANDBOX`、`SYSTEM STATUS`）；
   - `<= 15px` 的标签、表头、徽标、导航项严禁设置 `text-transform: uppercase`、`small-caps` 或 `letter-spacing > 0.03em`。一律使用正文字体、正常大小写、降一档字号。
2. **禁发光呼吸状态点、伪星号与 Emoji 图标（Gate 29, 30a & 63）**：
   - 严禁在标题旁放置无真实实时连接语义的发光圆点（`box-shadow: 0 0 8px ...`）、`✦` / `✨` 装饰符，或用 Emoji 充当 UI 图标；一律使用干净矢量 SVG 或纯文字排版。
3. **禁 `·` 串糖葫芦元数据与自嗨口号横幅（Gate 19 & 63）**：
   - 严禁使用两个及以上中点拼接元数据（`A · B · C · D` 会直接触发 Gate 63 `FAIL`），改用列对齐、细分割线或独立字段；
   - 严禁在工具顶栏写自吹口号或机制标语（如“原厂零改包雷达”“免手动护航已启用”“全自动赋能”），真实专业工具顶栏只展示工具名、数据维度与操作控件。
4. **禁卡片套卡片与彩虹胶囊汤（Gate 3 & 4）**：
   - 严禁在 `.card` 容器内部再嵌套一层带边框/底色的子 `.card`（Gate 4 `card-inside-a-card` 直接 `FAIL`）；同级分区优先用 `1px` 低对比细分割线（hairline divider）与留白切分；
   - 严禁满屏堆砌五颜六色的 `border-radius: 999px` 高饱和度圆角徽章（rainbow pill soup）。
5. **禁紫蓝渐变与布局/动画反模式（Gate 2a, 10a, 26a, 27, 34, 48）**：
   - 严禁紫蓝/紫粉渐变（Gate 2a）；
   - 严禁所有颜色与字体字面量散落在令牌块外（Gate 48：统一收口于 `:root` 与 `[data-theme="dark"]` / `:root:not([data-theme="light"])`，注意属性名为 `data-theme`、`data-mode` 或 `data-scheme`）；
   - 严禁 `transition: all` 或对 `width`、`height`、`top`、`left` 做动画（Gate 10a：进度条统一用 `transform: scaleX(...)` + `transform-origin: left`），且任何动画必须配 `@media (prefers-reduced-motion: reduce)` 降级（Gate 27）；
   - `html, body` 统一用 `overflow-x: clip`（Gate 34：严禁 `overflow-x: hidden` 破坏 `sticky` 或用 `100vw`）；
   - 所有可交互控件必须具备瞬时 `:focus-visible` 焦点环（Gate 26a，对比度 `>= 3:1`）。

## 三、 原生工具级审美基准（Linear / VS Code / Raycast 范式）

- **克制单色层级**：全屏仅设 1 个克制主强调色（仅用于当前选中态、主操作或焦点环）；状态色（琥珀黄、告警红）仅在指标真正越过预警阈值时点亮，健康常态一律使用中性前景色/次要色，降低视觉噪音。
- **数字等宽对齐**：所有 Token 计数、百分比、耗时（`ms`/`s`）、题号与金额强制启用 `font-variant-numeric: tabular-nums`。
- **表格与行优先于网格卡片**：展示多会话列表、工具耗时排行、模型配额时，优先采用紧凑行列表（row list / flat table）而非厚重圆角卡片堆叠。

## 四、 MagPie Artifacts（`:3425/a/...`）命名、归口与阅后即焚规范

1. **统一命名规范**：`<title>` 与 `meta.json` 标题统一采用 **`【领域】简洁名称`**（`<= 14` 字，禁口号副标题与 `·` 串词），例如 `【考研】27肖八刷题器`、`【视频】不在画下选片室`。
2. **准入与阅后即焚边界**：
   - **允许常驻**：仅限跨天高频复用的交互工作台（如挂载 `data.db` 双向同步的刷题器、待拍板选片期的样片放映室）；阶段任务结束后先归档至 `~/.Trash/` 再执行 `magpie artifacts delete <id>` 释放空间。
   - **严禁常驻**：单次巡检快照报告、一次性偏好采集问卷严禁长期挂在 MagPie Artifacts 或后台守护进程的常驻 HTTP 端口（偶发配置页必须改为 `--serve-*` 按需临时拉起，采集落盘 JSON 后即停）。
3. **零破坏版本演进**：对含 `data.db` 的在役 Artifact 升级 UI 时，必须通过 `publish_artifact` 传入原 `id` 与原 `capabilities`（如 `{"db": {}}`），严禁新建随机 ID 破坏既有 URL 或触碰 `data.db` / `data.db-wal`。
4. **日常自动巡检**：由 `com.developer.auth-keepalive` 每日只读扫描 `~/.config/magpie/artifacts/`，对不符合 `【领域】` 命名规范、体积超标或超过 14 天未更新的无 `data.db` 静态快照发出治理提醒。
