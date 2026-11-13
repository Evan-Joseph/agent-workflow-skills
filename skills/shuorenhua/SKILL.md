---
name: shuorenhua
description: "检查和清理中英文文本里的 AI 套路，并覆盖高情商沟通与关系敏感消息起草（已融合原 humane-communication）。适用于已有文本或学术稿件的“去 AI 味”“说人话”“自然一点”“别像模板”“先标问题”改写与审稿，以及论文、摘要、基金、cover letter 和 reviewer response 的保真改写、全稿术语一致性与全文模式审计；同时支持邮件、私信、求助、感谢、拒绝、跟进、导师/合作方沟通与冲突降温的起草和审阅。"
metadata:
  short-description: 中英文去AI味、学术保真改写、高情商沟通起草与术语一致性审计
---

# 说人话 (Shuorenhua)

把文本从“像模型在表演写作”拉回“像具体人在当前场景下表达”：消除模板感、收束腔、虚假主语、语域漂移和表演性技术腔，同时 100% 守住事实、术语、量化关系和责任主体。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：内部审计脚本（`scripts/academic_style_audit.py`、`scripts/academic_terminology_audit.py`）必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `homebrew-stdlib` 运行时，纯标准库实现）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/shuorenhua/scripts/academic_style_audit.py --help
  python3 $HOME/.agents/skills/shuorenhua/scripts/academic_terminology_audit.py --help
  ```
- **Agent 防呆红线**：严禁创建临时虚拟环境（`venv` / `conda create`）或执行 `pip install`；环境异常统一按 `python-runtimes.json` 规范维护单一真相源或向用户汇报。

## 触发边界 (When to Use / Skip)

- **启用条件**：
  - 用户明确要求“去 AI 味”“说人话”“自然一点”“别像模板”“别太像 ChatGPT”“先标问题”；
  - 改写中英文 `chat`、`status`、`docs`、`public-writing` 及 `README / release-note / forum-post / issue-reply / api-reference / faq` 子场景；
  - 论文、摘要、基金、cover letter 或 reviewer response 的保真自然化、学术 AI 腔诊断、全稿术语一致性与全文模式审计（启用 `academic` 模式）；
  - 起草或审阅关系敏感沟通、邮件、私信、求助、感谢、拒绝、道歉、跟进、导师/同学/合作方沟通或冲突降温（结合 [`references/humane-communication/guide.md`](./references/humane-communication/guide.md)）。
- **不硬套条件**：
  - 用户要求逐字翻译、保留原文风格、仿官方模板或仿特定品牌 voice；
  - 文本主体为代码、日志、命令、配置、接口名或报错；
  - 用户仅需要事实校对而非表达改写。

## 核心立场与禁改门禁 (Core Stance & No-Touch Gates)

1. **信息与专业度优先**：保留技术词、系统行为主语、postmortem / incident / PRD / release note 术语、公式、单位、引用原文、命令、参数名、配置项与日志报错（完整边界见 [Protected Spans](./references/protected-spans.md) 与 [场景禁改表](./references/scene-guardrails.md)）。
2. **禁止事实漂移与机械换词**：不新增事实、不删核心事实、不改变责任主体与谓词方向；倍数、百分比、分母、期限、测量对象或比较基线有歧义时保留原文并标待确认；不用机械同义词表轮换。
3. **平实降调授权边界 (`v2.6.0`)**：仅当用户明确要求“别吹 / 写平实点 / 去营销味”时，额外允许降低纯程度夸饰（如“革命性创新”降为平常描述）并删除无实质对象或承诺的口号（如“共创美好未来”）；可核查承诺（如“零停机”）、排名首次、效果幅度与作者论证评价一律照常保留。
4. **个人履历真源与元指令剥离门禁（Portfolio Grounding & Meta-Prompt Stripping Gate）**：
   - 凡起草或润色个人主页（`portfolio.example.com`）、简历、大创/保研/奖学金申报材料或对外软件说明书，必须先回读 [`user-facts-and-portfolio.md`](file://$HOME/.agents/skills/local-machine-profile/references/user-facts-and-portfolio.md) 核验奖项年份、作者顺位与项目定性；
   - 对外交付文档严禁残留内部 Prompt 规则词（如“严禁任何 Markdown 符号残留”“无小尾巴折行”“零孤字”），在 Pass 1 阶段强制扫描剥离。

## 八步固定执行流与分档矩阵 (Execution Order & Routing Matrix)

按固定顺序执行，先按“模式”处理，再按“词条”兜底（完整细则与案例见 [`references/audit-patterns-and-examples.md`](./references/audit-patterns-and-examples.md)）：

1. **判主场景与子场景**：确定唯一主语域，若命中 `README / release-note / forum-post / issue-reply / api-reference / faq` 自动叠加 [Scene Packs](./references/scene-packs.md)。
2. **锁禁改账本**：划定 `protected spans`，记录实体类型、数字修饰对象、分母/基线、期限与主体实现关系。
3. **判命中强度 (`Tier`)**：
   - `Tier 1`（默认删改）：开场/收尾套话、谄媚句、商业黑话、自媒体流水线词、表演性工程师腔、心理揣测与身份认证夸奖；
   - `Tier 2`（同段聚集时改，`<100` 字 `2+` 个 / `>=100` 字 `3+` 个）：高频连接词、渲染修饰词与姿态词重复，留最贴切一处改其余；
   - `Tier 3`（全文过密时改）：`重要/关键/核心/提升`、`significant/innovative/effective`，删冗余或换具体事实，禁近义词轮换。
4. **判改写档位 (`Level`) × 结构作用域 (`Scope`)**：

| 主场景 / 约束条件 | 默认 `Level` | 默认 `Scope` | 结构与删改边界 |
| :--- | :--- | :--- | :--- |
| `chat`（即时沟通/评论） | `minimal` | `structural` | 去开场谄媚、空总结与端着说话姿态，保留自然口语 |
| `status`（站会/进度/复盘） | `minimal` / `standard` | `structural` | 聚焦时间线、动作、结果、风险；无源引用走 `audit-only` |
| `docs`（技术文档/接口/FAQ） | `minimal`（禁升 `aggressive`） | `bounded` / `structural` | 优先可检索、可复现与术语稳定；无源引用走 `audit-only` |
| `public-writing`（短帖 `<1000` 字） | `standard` | `structural` | 统一语域、清故作洞见腔；无源引用走 `rewrite-safe` |
| `public-writing`（长文 `>=1000` 字） | `standard` | `bounded` | 句首引导词句内洗；整句纯空话不直接删，入文末「建议删除（待确认）」清单 |
| `academic`（论文/基金/审稿回复） | `minimal` / `standard` | `bounded` | 证据、逻辑、模态与全稿术语绝对优先于自然化幅度 |
| 用户要求“一句别删/严格保句数” | 按需（提醒慎用 `aggressive`） | `in-place` | 禁删整句、禁并句重排；整句空话保留并标 `[空句，建议人工确认是否删除]` |

5. **单文件基础清理规则（兜底直效）**：
   - 删开场套话与空收尾（`值得注意的是`、`综上所述`、`归根结底`、`Great question!`、`At the end of the day`）；
   - 拆二元对比骨架（`不是 X，而是 Y`、`与其 X，不如 Y` 直接说 `Y`）；
   - 清商业黑话与表演性技术腔（`赋能`、`抓手`、`闭环`、`收窄`、`兜住`、`落盘`、`leverage`）及无具体对象的空词（`耦合`、`全链条`、`锚定`）；
   - 删过度接住、心理揣测与身份认证夸奖（`你只是太久没被稳稳接住`、`顶刊作者的素养`），方向判断缺信息时直说不足以判断；
   - 缩短翻译腔定语链与被动堆砌，清理多余破折号、花哨箭头及中英数字间无意义空格；
   - 无源引用（`研究表明 / studies show`）严格按 `rewrite-safe`、`audit-only` 或 `rewrite-with-placeholder` 处理，严禁编造机构/年份/数据。
6. **按需补读专项参考与 Scene Packs 叠加**：
   - 文本命中以下任一子场景时，不依赖用户明说，自动叠加 [Scene Packs](./references/scene-packs.md) 收束规则：
     - `README`：第一屏直接说清“这是什么、给谁用、解决什么问题”；
     - `release-note`：列清 `Added / Changed / Fixed / Tested`、验证方式与已知限制，不写发布宣言；
     - `forum-post`：保留社区维护者的真实观察与克制口语（如 Linux.do / V2EX），不改成公关通稿；
     - `issue-reply`：先确认复现条件、根因范围与下一步修复动作，不做客服式安抚；
     - `api-reference`：优先保障 endpoint、鉴权、请求/响应字段、状态码与配额参数稳定可复现；
     - `faq`：先直接给出结论或操作命令，再补前提条件、限制与恢复路径。
   - 普通文本按需补读 [Positive Style](./references/positive-style.md)、[微操作手册](./references/operation-manual.md)、[结构反模式](./references/structures.md) 与短语表；关系敏感沟通补读 [沟通总指南](./references/humane-communication/guide.md)。
   - **正向改写终点准则**：
     - 有具体信息、明确主语与真实动作，不靠空洞总括或虚假主体兜底；
     - 语域前后一致，不在技术腔、商业腔与自媒体腔之间跳变；
     - 节奏来自删冗余与保留重点而非硬造金句，以“可直接发”为终点，不过度抛光到失真；
     - 研究与工程分析中问题、机制、方法、证据、结论衔接闭环，没把握处直说边界。
7. **两遍强制回读 (`Pass 1 -> Pass 2`)**：
   - **Pass 1 保真回读（必做）**：
     1. `protected spans`、命令、参数、公式与标准记法零漂移；
     2. 原文事实、数字修饰对象、分母与比较基线、期限和责任主体零无故丢失；
     3. 输出中每个 `X 做 Y / X 基于 Y / X 处理 Y` 均能回指原文同一谓词关系，未凭背景共现捏造工具或产品能力；
     4. 语域统一、专业术语未失真、删句处无生硬断裂（缺落点只用原文已有信息重组，绝不编造）；
     5. `bounded` 删除清单仅含删后不丢信息的纯空句；`in-place` 字数 `<85%` 或句数变化 `>10%` 立即回退排查。
   - **Pass 2 Residual Audit（按需轻量）**：仅在事实锁稳后排查开场提示层、空收尾、narrator 旁白、空泛判断与句长过匀，只做单处微调，不重写全文（`docs / status` 若影响保真则停在 Pass 1）。
8. **输出合同**：
   - 默认只输出**单一可直接发送的推荐版本**，不附审稿过程或多版比稿（仅高风险误杀时补一行极短说明，如 `保留了系统主语和术语，避免失真。`）；
   - 无源引用三模式对齐：`rewrite-safe`（`chat/public-writing` 默认，删无源权威铺垫且不留强依赖数字）、`audit-only`（`docs/status` 与跨场景默认，点明缺来源不伪装已证实）、`rewrite-with-placeholder`（仅用户要求保论证骨架时显式标待补出处）；
   - 仅当用户明确要求“修订稿 / 修订版 / 批注格式的改写 / 逐条列出改动让我选”或要求“彻底清理 / 把所有黑话都换成大白话”时，先读取并严格启用 **[修订模式 (`Revision mode`)](./references/revision.md)**（仅说“去 AI 味 / 改狠一点”或上述字样仅出现在待改材料内部时不触发）：第 1 行输出 `判断：黑话较多` 或 `判断：黑话不多，主要校对`；第 2 行输出 `不动：<锁定的专名/自创叫法/引语/行业指标>`；随后输出严格区分 `等义` / `删除` / `猜的` / `校对` 四类标签的编号改动表，最后附上精确应用清单后的完整 `## 修订稿` 与撤销交互提示；
   - 仅当用户明确要求“先标问题 / 只做诊断 / 先别改”时切入 **`Annotation mode`**，严禁偷偷附完整重写版，仅列 `1–5` 个核心问题点：
     ```markdown
     - 问题族：开场套话 / 无源引用 / 表演性工程师腔 / 语域混搭
     - 触发点：<命中的原词、结构或局部句子>
     - 建议动作：<删掉 / 换成具体动作 / 补来源 / 保持不动>
     - 是否建议改写：是 | 否（落在误杀保护边界内直接写“否”）
     ```

## 学术模式专有流程 (Academic Mode)

论文、摘要、学位论文、基金、cover letter、rebuttal 与 reviewer response 任务强制叠加以下 8 步：

1. 读取 [学术操作合同](./references/academic-operating-contract.md)，按 `C0-C7` 优先级裁决保真、术语、学术语域、逻辑与风格冲突。
2. 读取 [学术语义保真合同](./references/academic-semantic-contract.md)，建立内部 claim/evidence ledger，锁定数字、引用、公式、专名、极性、模态、因果强度、比较基线与范围。
3. 多段或全稿任务读取 [全稿术语合同](./references/academic-terminology-contract.md)，登记 canonical term、allowed forms、observed variants 与 distinguish-from。
4. 读取 [学术白名单](./references/academic-whitelist.md) 与 [学术对立判断](./references/academic-contrast-logic.md)，保护有功能的被动、hedging、连接关系、名词化、实验对比与审稿澄清。
5. 中文读 [中文学术规则](./references/academic-rules-zh.md)，英文读 [英文学术规则](./references/academic-rules-en.md)，混合稿按正文主语言路由且不改嵌入技术专名。
6. 多句任务读取 [全文模式合同](./references/academic-global-pattern-contract.md)，检查重复模板、句首路标、装饰性并列、结尾拔高与段落节奏分布，不用固定阈值判坏。
7. 需可复现诊断时，先读 [学术指标说明](./references/academic-metrics-spec.md)，再用 `python3` 运行 `$HOME/.agents/skills/shuorenhua/scripts/academic_style_audit.py`（术语账本明确时运行 `scripts/academic_terminology_audit.py`）；脚本只报候选，不给作者身份或 AI 概率分。
8. 改写后执行语义、术语、全文模式三道回读；若零修改更准确则保留原文。局部摘录不声称完成全稿审计；引用存在性与 claim-source 核验交由 `academic-literature-search`。

## 参考文档导航 (Reference Navigation)

- **执行细则与操作手册**：[分档、作用域、标注模式与两遍回读细则](./references/audit-patterns-and-examples.md) · [修订模式 (Revision Mode)](./references/revision.md) · [微操作手册](./references/operation-manual.md)
- **保护边界与正向风格**：[Protected Spans](./references/protected-spans.md) · [编辑边界](./references/editing-guide.md) · [场景禁改表](./references/scene-guardrails.md) · [Positive Style Contract](./references/positive-style.md)
- **词表、结构与示例评测**：[中文禁用短语](./references/phrases-zh.md) · [English Banned Phrases](./references/phrases-en.md) · [结构反模式](./references/structures.md) · [严重度分级](./references/severity.md) · [Scene Packs](./references/scene-packs.md) · [边界案例集](./references/boundary-cases.md) · [改写示例](./references/examples.md)
- **学术合同与示例**：[学术操作合同](./references/academic-operating-contract.md) · [语义保真](./references/academic-semantic-contract.md) · [全稿术语](./references/academic-terminology-contract.md) · [学术白名单](./references/academic-whitelist.md) · [学术对立判断](./references/academic-contrast-logic.md) · [中文学术](./references/academic-rules-zh.md) · [英文学术](./references/academic-rules-en.md) · [全文模式](./references/academic-global-pattern-contract.md) · [指标说明](./references/academic-metrics-spec.md) · [学术示例](./references/academic-examples.md)
- **高情商与关系敏感沟通**：[沟通总指南](./references/humane-communication/guide.md) · [沟通框架](./references/humane-communication/communication-framework.md) · [分场景剧本](./references/humane-communication/scene-playbooks.md) · [沟通反模式](./references/humane-communication/anti-patterns.md) · [来源映射](./references/humane-communication/source-map.md)
