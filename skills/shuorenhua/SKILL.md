---
name: shuorenhua
description: "检查和清理中英文文本里的 AI 套路，并覆盖高情商沟通与关系敏感消息起草。适用于已有文本或学术稿件的“去 AI 味”“说人话”“自然一点”“先标问题”改写与审稿，以及论文、摘要、基金、cover letter 和 reviewer response 的保真改写、全稿术语一致性与全文模式审计；同时支持邮件、私信、求助、感谢、拒绝、跟进、导师/合作方沟通与冲突降温的起草和审阅。"
metadata:
  short-description: 中英文去AI味、学术保真改写、高情商沟通起草与术语一致性审计
---

# 说人话 (Shuorenhua)

把文本从“模型表演写作”拉回“具体人在当前语境下说话”：清掉套话、虚假主语、二元对立骨架和表演性技术腔，同时 100% 守住事实、术语、量化关系与责任主体。

## 运行时契约 (Runtime Contract)

- 学术风格与术语审计脚本（`scripts/academic_style_audit.py`、`scripts/academic_terminology_audit.py`）固定使用 `python3`（`homebrew-stdlib`），严禁自建 `venv` 或执行 `pip install`。

## 触发边界

- **启用**：去 AI 味 / 说人话 / 自然化改写；`README / release-note / forum-post / issue-reply / api-reference / faq` 文案打磨；学术稿件（论文、摘要、基金、cover letter、reviewer response）保真自然化与术语一致性审计；导师/合作方/人际沟通消息起草（结合 [`references/humane-communication/guide.md`](./references/humane-communication/guide.md)）。
- **跳过**：逐字翻译、指定仿官方模板、纯代码/配置/命令/日志文本、纯事实校对。

## 核心禁改门禁

1. **锁死专业锚点**：保留技术术语、系统行为主语、公式、单位、引用原文、命令、参数名、配置项与报错（边界见 [`references/protected-spans.md`](./references/protected-spans.md) 与 [`references/scene-guardrails.md`](./references/scene-guardrails.md)）。
2. **零事实漂移**：不增删核心事实，不篡改责任主体与因果方向；数字、分母、比较基线或期限有歧义时保留原文并标待确认；不用近义词表机械轮换。
3. **平实降调边界**：仅当用户明确要求“别吹 / 写平实点 / 去营销味”时降调纯程度夸饰并删空泛口号；可核查承诺（如“零停机”）、实验幅度与论证结论照常保留。
4. **个人履历真源与元话语清零**：涉及个人主页、简历、申报书时先读 [`user-facts-and-portfolio.md`](file://$HOME/.agents/skills/local-machine-profile/references/user-facts-and-portfolio.md) 核验事实；对外成稿强制剥离“严禁 Markdown 残留”“零孤字”等内部 Prompt 约束词。

## 固定执行流与分档矩阵

先按结构模式清理，再按词条兜底（细则见 [`references/audit-patterns-and-examples.md`](./references/audit-patterns-and-examples.md)）：

1. **定场景与禁改账本**：确定主语域（命中技术文档子场景自动叠加 [`references/scene-packs.md`](./references/scene-packs.md)），划定 `protected spans`。
2. **分级清理 (`Tier 1 -> Tier 3`)**：
   - `Tier 1`（直删直改）：开场/收尾套话（`值得注意的是`、`综上所述`、`Great question!`）、二元对比（`不是 X，而是 Y` 直接说 `Y`）、商业黑话与表演腔（`赋能/抓手/闭环/锚定/兜住/leverage`）、过度共情与身份吹捧；
   - `Tier 2`（同段聚集时改）：连接词、程度副词与姿态词重复；
   - `Tier 3`（全文过密时改）：`重要/关键/核心/significant`，删冗余或换具体动作事实。
3. **匹配 `Level × Scope`**：

| 主场景 | 默认 `Level` | 默认 `Scope` | 删改边界 |
| :--- | :--- | :--- | :--- |
| `chat`（即时沟通/评论） | `minimal` | `structural` | 去谄媚与空总结，保自然口语 |
| `status`（进度/复盘） | `minimal` / `standard` | `structural` | 聚焦时间线、动作、结果、风险；无源引用走 `audit-only` |
| `docs`（技术文档/API/FAQ） | `minimal`（禁 `aggressive`） | `bounded` / `structural` | 保可检索、可复现与术语稳定；无源引用走 `audit-only` |
| `public-writing`（`<1000` / `>=1000` 字） | `standard` | `structural` / `bounded` | 长文整句纯空话不直删，列文末「建议删除（待确认）」 |
| `academic`（论文/基金/审稿回复） | `minimal` / `standard` | `bounded` | 证据、逻辑、模态与全稿术语优先于自然化幅度 |
| 用户要求“一句别删/保句数” | 按需 | `in-place` | 禁删并整句；纯空句标 `[空句，建议人工确认是否删除]` |

4. **两遍回读与输出合同**：
   - **Pass 1 保真回读（必做）**：核验 `protected spans`、数字分母基线、主体谓词关系与语域一致性；**Pass 2（按需轻量）**：微调句首旁白与过匀句长。
   - **默认输出单一可直接发送的成稿**，不附审稿过程或多版比稿；
   - 用户明确要求“逐条列改动/批注修订版”时读取并启用 [`references/revision.md`](./references/revision.md)；明确要求“先标问题/先别改”时仅输出 `1–5` 条结构化诊断，不附重写稿。

## 学术模式专有合同 (`Academic Mode`)

论文、摘要、学位论文、基金、cover letter 与 reviewer response 依次叠加：
1. 按 [`references/academic-operating-contract.md`](./references/academic-operating-contract.md)（`C0–C7`）与 [`references/academic-semantic-contract.md`](./references/academic-semantic-contract.md) 锁定数字、引用、公式、模态与因果强度；
2. 多段或全稿建立 [`references/academic-terminology-contract.md`](./references/academic-terminology-contract.md) 术语账本，结合 [`references/academic-whitelist.md`](./references/academic-whitelist.md) 与 [`references/academic-contrast-logic.md`](./references/academic-contrast-logic.md) 保护功能性被动、hedging 与实验对比；
3. 按主语言读取 [`references/academic-rules-zh.md`](./references/academic-rules-zh.md) 或 [`references/academic-rules-en.md`](./references/academic-rules-en.md)，长稿读取 [`references/academic-global-pattern-contract.md`](./references/academic-global-pattern-contract.md)；
4. 需要可复现扫描时读取 [`references/academic-metrics-spec.md`](./references/academic-metrics-spec.md) 并运行 `academic_style_audit.py` / `academic_terminology_audit.py`（只报候选，不给 AI 概率分；引用真实性交 `academic-literature-search`）。

## 参考导航

- **通用与词表**：[`operation-manual.md`](./references/operation-manual.md) · [`positive-style.md`](./references/positive-style.md) · [`editing-guide.md`](./references/editing-guide.md) · [`phrases-zh.md`](./references/phrases-zh.md) · [`phrases-en.md`](./references/phrases-en.md) · [`structures.md`](./references/structures.md) · [`severity.md`](./references/severity.md) · [`boundary-cases.md`](./references/boundary-cases.md) · [`examples.md`](./references/examples.md) · [`academic-examples.md`](./references/academic-examples.md)
- **关系敏感沟通**：[`guide.md`](./references/humane-communication/guide.md) · [`communication-framework.md`](./references/humane-communication/communication-framework.md) · [`scene-playbooks.md`](./references/humane-communication/scene-playbooks.md) · [`anti-patterns.md`](./references/humane-communication/anti-patterns.md)
