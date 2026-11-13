# gpt-image2-ppt（`awesome-ppt` 内置生图与模板克隆后端组件）

本组件作为 [`awesome-ppt`](../../../SKILL.md) 的内置渲染与模板克隆后端维护，统一固定使用 `python3` 运行时：

- **十套内置风格**：`gradient-glass`、`clean-tech-blue`、`vector-illustration`、`editorial-mono`、`dark-aurora`、`risograph`、`japanese-wabi`、`swiss-grid`、`hand-sketch`、`y2k-chrome`（详见 [`references/styles.md`](./references/styles.md)）。
- **模板克隆模式**：渲染 `.pptx` 模板并通过本地唯一模型网关 MagPie `${OPENAI_COMPAT_BASE_URL}`（`group/carbon`）抽取视觉风格与逐页 JSON Schema（详见 [`references/template-clone.md`](./references/template-clone.md)）。
- **统一生图底座**：`scripts/image_generator.py` 直接委托复用 `$HOME/.agents/skills/image-generation/scripts/grsai_generate.py` 的 Grsai `/v1/api/generate` 核心逻辑与 `~/.config/grsai/grsai.env` 凭据配置，不重复维护独立客户端或外部安装脚本。
- **完整调用规范**：见 [`guide.md`](./guide.md)、[`references/workflow.md`](./references/workflow.md) 与 [`references/backends-and-env.md`](./references/backends-and-env.md)。

## 致谢与许可

- 风格与查看器参考：[op7418/NanoBanana-PPT-Skills](https://github.com/op7418/NanoBanana-PPT-Skills)、[lewislulu/html-ppt-skill](https://github.com/lewislulu/html-ppt-skill)
- 上游来源：[JuneYaooo/gpt-image2-ppt-skills](https://github.com/JuneYaooo/gpt-image2-ppt-skills)（Apache License 2.0，详见 [LICENSE](./LICENSE)）
