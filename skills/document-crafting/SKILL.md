---
name: document-crafting
description: "高保真长文档协作起草、审阅、排版与多格式交付中枢（已融合原 doc-coauthoring 与 report-format-discovery）。覆盖方案/PRD/技术规格/RFC/决策文档协作撰写、报告结构规范发现、Word/Docx 格式规范与 docx-tool (docx_template_tool.py) 零破坏引擎、OnlyOffice 转换、Markdown 转离线排版 HTML 报告、以及基于 LaTeX/Docx 的高质量 PDF 交付。在需要起草或审阅长文档、生成正式公文报告、格式转换或检查排版质量时使用。"
metadata:
  short-description: 长文档协作起草审阅、Word/Docx排版与高质量PDF/HTML交付
---

# Document Crafting & High-Fidelity Publishing

统一长文档内容协作（结构发现、起草、审阅）与高品质多格式排版交付（Word/Docx、离线 HTML、矢量 PDF）标准。

## 零、 长文档协作起草、审阅与报告结构发现 (Doc Co-Authoring & Format Discovery)

当任务处于内容构建阶段（起草或审阅方案、PRD、技术规格、RFC、决策记录、项目申报书、尽调/行业报告）：
- **协作撰写与审阅规范**：参阅 [`references/coauthoring-workflow.md`](./references/coauthoring-workflow.md)（先对齐读者与事实口径、最小增量改稿、源稿同源维护与收尾四项读者复核）。
- **个人事实锚定与内部元话语清零铁律**：
  1. 起草简历、申报书、综测/奖学金材料或项目报告前，必须先读取 `$HOME/.agents/skills/local-machine-profile/references/user-facts-and-portfolio.md`，严格区分“本人主导项目”与“外部委托或协作项目”，严禁跨栏提取名册张冠李戴或虚标奖项级别；
  2. 正式交付正文与支撑材料中，**严禁残留任何内部 Prompt 约束话术或 AI 防御性免责声明**（如“本节明确测算逻辑，不预先虚构销售收入”、“参考来源：本地材料”、“内部审稿后添加”、“严格控制在40页以内”、“数据从OpenReview获取”或“XX公司专属定制版”）；中文标题严禁混搭中文顿号 `、` 与英文 `&`；统计图表涉及港澳台时必须表述为“中国台湾/中国香港（地区）”；
  3. Markdown Artifact 内嵌展示图片时，**必须先将图片拷贝至当前会话 `<appDataDir>/brain/<cid>/` 目录下**，严禁直接引用桌面工作区路径触发 Webview CSP 破图；严禁用 PyMuPDF `page.apply_redactions()` 在导出 PDF 上涂白掩盖源 `.docx` 排版问题。
- **报告结构规范发现**：若目标报告类型（如行业图谱、投资备忘录、尽调报告、竞赛交付物）的章节要素与证据标准未定，先参阅 [`references/components/report-format-discovery/guide.md`](./references/components/report-format-discovery/guide.md) 产出结构规范，再进入正文撰写与多格式排版。
- **相邻技能边界**：去 AI 味、自然化润色与人际/商务沟通起草统一用 `shuorenhua`；学术论文审稿、实验审计与 Rebuttal 用 `paper-publication-copilot`。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时，已预装 `python-docx`、`pypdf`、`markdown`、`reportlab` 等）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/document-crafting/scripts/render_report.py input.md output.html --with-js
  python3 $HOME/.agents/skills/document-crafting/scripts/check_image_refs.py output.html
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **外部编译器与套件**：LaTeX 学术排版使用 `/Library/TeX/texbin/pdflatex` 或 `/Library/TeX/texbin/xelatex`；公文与文档套件日常交互使用 ONLYOFFICE 或 Microsoft Word；Agent 结构化创建与模板保真编辑统一使用 `docx-tool`（即 `scripts/docx_template_tool.py`），无头转 PDF 使用 `docx2pdf`。

## 核心交付铁律（高质量 PDF 准则）

- **坚决禁止粗糙手绘 PDF**：严禁用 Python reportlab 拼凑位图、硬画坐标生成粗糙的劣质 PDF。
- **正规 PDF 生成路线**：
  1. **学术科研与精细出版**：必须通过标准 LaTeX 源码（`.tex`）经由 `latex-compile` 编译生成矢量 PDF。
  2. **办公公文、PRD 与分析报告**：先构建符合规范的 `.docx` 文件（带清晰的样式层、标题树、正规表格），再通过本机 `docx2pdf`（基于 Microsoft Word 官方引擎无头导出）转出 100% 还原中文字体与版式的高保真 PDF：
     ```bash
     docx2pdf target.docx target.pdf
     ```
     *注：彻底废弃中文字体映射易错位、行高分页截断的 LibreOffice (`soffice`) 路线。*
  3. **离线浏览与多端研读**：采用结构化 Markdown 经内置模板渲染为响应式、自带导航与代码高亮的离线 `.html` 报告。

## 一、 Word / Docx 模板零破坏协作与排版工程 (Template-First OOXML)

编辑既有 `.docx` 模板（申报书、行政表格、技术报告母版）时，必须严格遵守 [`references/docx-template-engineering.md`](./references/docx-template-engineering.md) 的五步法（**Inspect → Plan → Surgical Fill → Audit → Visual Check**）：

1. **五条硬红线**：
   - **严禁裸写 `paragraph.text = ...` 或 `cell.text = ...`**：会直接清空 `<w:rPr>` 与行内元素，导致字体退化为 `Normal`。
   - **严禁丢失空白格 `<w:pPr><w:rPr>` 预设字体**：空白表格格与空段落的预设字体（如 `宋体` / `仿宋_GB2312`）存于 `<w:p><w:pPr><w:rPr>` 或相邻单元格，必须通过 `docx-tool`（`docx_template_tool.py`）自动继承。
   - **严禁混写 `w:eastAsia` 与 `w:ascii`**：中文字体必须写入 `w:rFonts/@w:eastAsia`，西文字体写入 `w:ascii`/`w:hAnsi`；禁止用 `run.font.name` 覆盖 `w:eastAsia`。
   - **严禁盲写合并单元格或塞入软回车 `\n`**：先通过 `inspect` 识别 `↳合并至(r,c)` 拓扑；多段内容通过 `\n` 自动克隆带 `firstLineChars="200"` 的独立 `<w:p>`。
   - **严禁破坏 `Label：______` 下划线填空区**：对封面/表头的下划线填空段落，只替换带 `w:u` 的空白 Run，完整保留前缀标签与下划线宽度。
2. **标准执行通道（统一确定性 CLI `docx-tool`）**：
   - **第一步（既有模板必做）：探查模板蓝图**：
     ```bash
     docx-tool inspect template.docx
     ```
   - **第二步：从零声明式建档（`build`）或既有模板保格式回填（`fill` / `replace` / `set-para` / `set-cell`）**：
     ```bash
     # 从零按 JSON spec 新建规范双字体（中英分槽 + 三线表/网格表 + 页边距）文档
     docx-tool build --spec build_spec.json -o created.docx

     # 声明式 JSON 批量回填既有模板（自动合并碎片 Run、逆序写段落、克隆表格行并执行模板对比审计）
     docx-tool fill template.docx --spec fill.json -o output.docx

     # 单项跨 Run 替换 / 段落写入 / 单元格写入
     docx-tool replace input.docx --old "{{ID}}" --new "2026-01" --in-place
     docx-tool set-para input.docx --index 0 --text "新内容" --in-place
     docx-tool set-cell input.docx --table 0 --row 0 --col 2 --text "填写值" --in-place
     ```
   - **第三步（交付门禁必做）：模板、公式、封面字号与渲染分页闭环审计 (`docx_qa_gate.py`)**：
     ```bash
     # 执行结构/中文字体/封面字号防缩小/OMML 公式防裸露 LaTeX 审计，并通过 Word 沙盒静默导出 PDF + 110 DPI 分页溢出检查
     python3 $HOME/.agents/skills/document-crafting/scripts/docx_qa_gate.py output.docx --template template.docx --export-pdf --render-dir ./qa_pages
     # 若存在往年已通过的同类优秀范本（如往期结项报告/申请书），传入 --reference-docx 对齐封面与版式基准
     python3 $HOME/.agents/skills/document-crafting/scripts/docx_qa_gate.py output.docx --template template.docx --reference-docx past_approved.docx --export-pdf
     ```
     *门禁约束：严禁缩小封面标题字号；严禁封面内容溢出 1~2 行到第 2 页；Word 转 PDF 必须经由 `~/Library/Containers/com.microsoft.Word/Data/Documents/` 沙盒静默 `save as ... file format format PDF`（严禁调用 `print out` 触发打印弹窗）；视觉抽检必须读取 `110 DPI` 降采样预览图（单张 `<100KB`，严禁读取 300 DPI 大图污染会话 DB）。*
3. **重度 OOXML 与修订留痕升级路由**：需要生成 Word 批注/修订留痕（Track Changes `<w:ins>`/`<w:del>`）或从零构建复杂国标公文时，路由至共享工具链 `$HOME/.local/libexec/docx-toolkit/`（`.NET 8` OpenXML SDK，供 `document-crafting` 与 `ip-materials` 正向共享调用）。

## 二、 离线 HTML 排版报告 (Markdown to HTML)

当用户需要交付离线可读的技术调研报告、行业分析或交付总结时：
- 生成语义清晰、自适应排版、内置目录导航与 Mermaid 支持的独立 HTML 单文件，并校验本地图片引用：
  ```bash
  python3 $HOME/.agents/skills/document-crafting/scripts/render_report.py input.md output.html --with-js
  python3 $HOME/.agents/skills/document-crafting/scripts/check_image_refs.py output.html
  ```

## 三、 PDF 表单填充与高质量矢量交付审阅 (PDF Crafting & QA)

- **版式设计规范**：参阅 [`references/design.md`](./references/design.md)。
- **PDF 交互式表单探查与回填（AcroForm）**：使用 `scripts/fill_inspect.py --input form.pdf` 探查表单域结构，使用 `scripts/fill_write.py --input form.pdf --data values.json --out filled.pdf` 精确写入。
- **高保真矢量 PDF 生成（严禁 ReportLab 手绘）**：统一通过 LaTeX（`/Library/TeX/texbin/xelatex`）或 Word 模板零破坏引擎（`scripts/docx_template_tool.py` + `docx2pdf`）生成。
- **交付前受众自审门禁（Pre-Delivery Audience Self-Review Gate — P1-1，必做）**：
  - 任何 `.docx`、`.pdf` 或 `.html` 报告向用户交付前，必须执行受众视角自审闭环：① 完成真实渲染导出（Word 沙盒静默转 PDF 或浏览器加载离线 HTML）；② 将关键页面（封面、跨页表格、公式密集页、目录页）渲染为 `<150 KB` 真实 JPEG/PNG 预览图（或对 HTML 截取多视口 `<150 KB` 截图并检查控制台与计算样式）；③ **亲自调用 `read_file` 从读者视角逐页审阅**，确认封面未溢出到次页、字号未被压缩、无裸露 LaTeX/Markdown 源码、无内部 Prompt 话术残留且论述层次清晰。
