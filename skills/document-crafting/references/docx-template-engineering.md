# Word / Docx 模板零破坏工程规范 (Template-First OOXML Engineering)

本规范综合 `anthropics/skills/skills/docx`、`Rayminliu/texere`、`goingogle/wps-docx-layout-engineering`、`Abird64/word-skill` 与本机 `docx-toolkit` 最佳实践，针对 Agent 编辑 `.docx` 模板时的**排版异常、字体退化、模板理解缺失、填表破坏合并格与下划线**五大顽疾，确立底层 OOXML 级零破坏工作流。

---

## 一、 破坏 `.docx` 模板的五大底层根因与禁令

1. **严禁直接赋值 `paragraph.text = ...` 或 `cell.text = ...`**：
   - `python-docx` 对 `.text` 赋值会调用 `.clear()`，直接销毁段落内所有 `<w:r>` 节点及其 `<w:rPr>` 属性（字号、粗体、颜色、下划线、行内图片与域代码），随后插入一个无任何 `<w:rPr>` 的裸 `<w:r>`，导致文本回退到 `Normal` 默认样式。
2. **空白单元格与空段落的预设字体存储在 `<w:pPr><w:rPr>`（段落标记属性）**：
   - 中文申报书、行政公文、高校表格的空白待填格内**没有 `<w:r>` 节点**，模板设计者预设的“宋体 / 仿宋_GB2312 / 五号”存储在 `<w:p><w:pPr><w:rPr>` 中。
   - 若直接 `p.add_run(text)` 而不从 `<w:pPr><w:rPr>`（或上方数据格、左侧标签格）克隆 `<w:rPr>`，写入的文字会退化为 `Calibri` 或 `等线`。
3. **中英双字体槽位（`w:eastAsia` vs `w:ascii`）严禁混写**：
   - OOXML 将西文字体存于 `w:rFonts/@w:ascii` 与 `@w:hAnsi`（常为 `Times New Roman`），将中文字体存于 `w:rFonts/@w:eastAsia`（常为 `仿宋_GB2312`、`宋体`、`黑体`）。
   - `python-docx` 的 `run.font.name` **仅读写 `w:ascii`**。严禁将 `run.font.name` 读取到的值写回 `w:eastAsia`，否则会把中文字体槽位污染为 `Times New Roman`，触发中文字体异常回退。
4. **合并单元格 `_tc` 别名碰撞与多行 `\n` 缩进失效**：
   - 在 `python-docx` 中，水平合并（`w:gridSpan`）或垂直合并（`w:vMerge`）的单元格在 `row.cells` 中共享同一个底层 `CT_Tc`（`cell._tc`）节点。若未先解析合并拓扑而向延续格写入，会直接覆盖左侧标签格文字。
   - 单元格或正文多段文本若直接将 `\n` 塞入单个 `<w:t>`，Word 会将其视为软回车，导致第 2 段起丢失 `<w:pPr>` 的 `firstLineChars="200"`（首行缩进 2 字符）与段间距。必须按 `\n` 拆分为多个 `<w:p>` 并深度克隆 `<w:pPr>` 与 `<w:rPr>`。
5. **碎片化 `<w:r>`（Run Splitting）与中文编号标题（`Normal` 样式）盲区**：
   - Word 拼写检查（`w:proofErr`）与修订号（`w:rsid*`）常将 `{{PROJECT_NAME}}` 拆成 3～5 个相邻 `<w:r>`，逐个遍历 `para.runs` 无法匹配完整占位符。必须先执行同样式相邻 Run 合并（`merge-runs`）与跨 Run 区间替换。
   - 90% 的中文模板章节标题（`一、立项依据`、`（一）研究内容`）使用 `Normal` 样式加直接格式（黑体/加粗），而非内置 `Heading 1`。按章节替换时必须同时识别内置 Heading 与中文序号层级，严禁因只查 `Heading` 而误删后续全文。

---

## 二、 标准五步工作流（Inspect → Plan → Surgical Fill → Audit → Visual Check）

所有 `.docx` 模板填写、改稿与从零建档任务统一使用 `docx-tool`（即 `$HOME/.agents/skills/document-crafting/scripts/docx_template_tool.py`）。

### Step 1：先探查模板蓝图（Inspect Blueprint）

**严禁在不了解段落索引、表格坐标与合并关系的情况下盲写。**

- **CLI 命令**：
  ```bash
  docx-tool inspect template.docx
  ```

探查报告会完整输出：
- 页面尺寸、页边距、页眉页脚文本；
- 全文显式占位符（`{{...}}`、`【...】`）所在坐标；
- 每个正文段落的 `[index]`、样式名、有效字体签名（`eastAsia/size_pt/B/U`）、首行缩进，以及是否属于 **`[下划线填空: 前缀='...']`**；
- 每个表格的 `(row, col)` 矩阵、有效字体签名、`<空>` 待填格位置，以及 **`↳合并至(r,c)`** 拓扑关系；
- `<w:sdt>` 结构化内容控件列表。

### Step 2：规划填充映射（Plan `fill.json`）

根据 Step 1 输出的坐标蓝图，编写声明式 JSON 规格（支持字典或列表格式）：

```json
{
  "merge_runs": true,
  "replacements": {
    "{{PROJECT_ID}}": "2026-YFA-001",
    "【申报日期】": "2026年10月23日"
  },
  "paragraphs": [
    {"index": 0, "text": "多智能体文档排版零破坏治理研究", "preserve_label_blank": true},
    {"index": 3, "text": "第一段正文：自动继承首行缩进与仿宋字体。\n第二段正文：自动克隆 <w:pPr> 与 <w:rPr>。"}
  ],
  "cells": [
    {"table": 0, "row": 0, "col": 2, "text": "深度智能体实验室"},
    {"table": 0, "row": 1, "col": 1, "text": "摘要第一段。\n摘要第二段。"}
  ],
  "append_rows": [
    {
      "table": 1,
      "template_row": -1,
      "rows": [
        ["2", "李四", "核心算法研发"],
        ["3", "王五", "系统工程验证"]
      ]
    }
  ]
}
```

### Step 3：执行保格式外科手术写入（Surgical Fill）

- **批量回填（推荐，自动执行合并 Run + 逆序段落写入 + 模板对比审计）**：
  ```bash
  python3 $HOME/.agents/skills/document-crafting/scripts/docx_template_tool.py fill template.docx --spec fill.json -o output.docx
  ```
- **单项精细操作 CLI**：
  ```bash
  # 跨 Run 保格式文本替换
  python3 $HOME/.agents/skills/document-crafting/scripts/docx_template_tool.py replace input.docx --old "{{NAME}}" --new "张三" --in-place

  # 按索引修改段落（自动识别 Label：______ 下划线填空并支持 \n 多段克隆）
  python3 $HOME/.agents/skills/document-crafting/scripts/docx_template_tool.py set-para input.docx --index 0 --text "新标题" --in-place

  # 按坐标修改表格单元格（含空白格 <w:pPr><w:rPr> 字体继承与合并格防误写保护）
  docx-tool set-cell input.docx --table 0 --row 0 --col 2 --text "填写内容" --in-place
  ```
- **从零新建规范文档（`build` 子命令）**：
  无现成模板时，通过 `docx-tool build --spec spec.json -o output.docx` 一次性按声明式 JSON 创建页边距、标题层级、正文缩进、三线表/全框表与分页符，自动保证 `w:eastAsia` 与 `w:ascii` 双槽位字体分离。

### Step 4：与原模板进行结构与字体回归审计（Audit）

```bash
python3 $HOME/.agents/skills/document-crafting/scripts/docx_template_tool.py audit --template template.docx --output output.docx
```

审计器会自动核验：
1. 节数（Sections）、纸张尺寸、页边距是否与原模板完全一致；
2. 表格总数与列数是否被意外改变；
3. 是否存在西文字体（`Times New Roman`、`Calibri`、`Arial`）污染 `w:eastAsia` 中文槽位；
4. 是否存在未替换完的残留占位符（`{{...}}`、`【...】`）。

### Step 5：Microsoft Word 官方引擎导出 PDF 视觉终检

对于重要交付件，使用本机 `docx2pdf`（调用 Microsoft Word 官方排版引擎）生成 PDF 进行版面抽检，确认无跨页断行、孤行、表格撑破或下划线跑偏：

```bash
docx2pdf output.docx output.pdf
```

---

## 三、 复杂场景升级路由（何时使用 `.NET` `docx-toolkit`）

当任务超出模板回填范畴，涉及以下重度 OOXML 构造时，升级调用 `$HOME/.agents/skills/ip-materials/vendor/docx-toolkit/`（基于 `.NET 8` OpenXML SDK 3.1.1）：
1. **带批注与修订留痕（Track Changes `<w:ins>` / `<w:del>` / `<w:comment>`）的合同或论文审阅稿**：参阅 `vendor/docx-toolkit/commands/scenario_b_edit_content.md`。
2. **从零构建含复杂页眉横线、奇偶页不同页眉、三线表与国标公文版记的全新 `.docx`**：参阅 `vendor/docx-toolkit/commands/scenario_a_create_from_scratch.md` 与 `cjk_typography.md`。
