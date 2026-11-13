# gpt-image2-ppt Styles

内置风格文件位于 `styles/<id>.md`。选择风格时优先按观众、内容类型和展示场景匹配，不要只按个人喜好。

| 风格 ID | 一句话定位 | 适用场景 |
| --- | --- | --- |
| `gradient-glass` | Apple Vision OS / Spatial Glass | AI 产品发布、技术分享、创意提案 |
| `clean-tech-blue` | Stripe / Linear 级蓝白 | 融资路演、商业计划书、企业战略 |
| `vector-illustration` | 复古矢量插画 + 黑描边 | 教育培训、品牌故事、社区分享 |
| `editorial-mono` | Kinfolk / Monocle 编辑设计 | 品牌发布、文化访谈、读书分享 |
| `dark-aurora` | Linear / Vercel 深色霓虹 | AI 产品、开发者工具、技术分享 |
| `risograph` | Riso 双套色印刷 + 网点纹理 | 创意工作室、文创品牌、独立 zine |
| `japanese-wabi` | 无印 / 原研哉式侘寂 | 茶道、生活方式、奢侈品、文化讲座 |
| `swiss-grid` | Bauhaus / Vignelli 国际主义网格 | 学术报告、博物馆展陈、严肃汇报 |
| `hand-sketch` | Sketchnote / 白板手绘 | 工作坊、产品 brainstorming、培训 |
| `y2k-chrome` | Y2K 千禧液态金属 + 蝴蝶贴纸 | 潮牌、文娱、品牌联名、Z 世代营销 |

选择原则：

- 技术类首选 `dark-aurora` / `gradient-glass`。
- 商务类首选 `clean-tech-blue` / `editorial-mono`。
- 文化生活类首选 `japanese-wabi` / `vector-illustration`。
- 潮文娱类首选 `risograph` / `y2k-chrome`。
- 学术类首选 `swiss-grid`。
- 工作坊与早期创意类首选 `hand-sketch`。

## Prompt Construction

构造每页 prompt 时，先读取所选 `styles/<id>.md` 的 `## 基础提示词模板`，再拼入当前页内容和强制要求。

关键规则：

- 封面页：标题/副标题为视觉焦点。
- 数据页：突出关键数字、对比或结论。
- 内容页：按层级、对齐、留白结构化呈现。
- 所有文字必须使用简体中文，专有名词除外。
- 中文字体使用思源黑体或苹方，严禁草书、艺术字。
- 画面比例必须是 16:9 横版宽屏，prompt 中明确要求不要方图或竖图。
