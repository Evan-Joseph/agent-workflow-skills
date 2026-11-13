---
name: document-parsing
description: "用于从 PDF、扫描件、图片、表格和 Office/HTML 文档中提取结构化内容、OCR、表格、公式、页码来源和 Markdown 素材。印刷体主力路由至 MinerU 高精度解析与 OCR；手写数学/408 答卷严禁调 paddleocr/tesseract，统一经 crop_exam_sheet.py 做 300 DPI 单题裁剪后多模态盲转写；版式重排、表单填写和最终 PDF 渲染路由至 document-crafting。"
metadata:
  short-description: 文档解析、MinerU高精度OCR与手写答卷300DPI单题裁剪
---

# Document Parsing

Choose one extraction path and keep the source file, output directory, and
page/region provenance explicit. Do not upload private material unless the user
has explicitly approved that service and the workspace policy allows it.

## 运行时契约与环境约束 (Runtime Contract)

- **解释器绑定（按职责对齐 `python-runtimes.json`）**：
  - **印刷体 / 扫描件解析（`mineru_parse.py`）**：固定使用 `python3`（`homebrew-stdlib` 运行时，纯标准库实现）。
  - **手写答卷 `300 DPI` `<150KB` 单题裁剪（`scripts/crop_exam_sheet.py`）与私密文档零联网提取（`scripts/office_to_md.py`）**：固定使用 `python3`（`miniconda-agent-general` 运行时，基于 `fitz` PyMuPDF + `PIL` Pillow + `python-docx` + `openpyxl`）。
- **执行命令范例**：
  ```bash
  # 0. 上传前本地预检（检查文件非空、体积 <= 200MB 及 PDF 页数 <= 200 页，超出则使用 --page-ranges 分段）
  python3 -c '
  import pathlib, re
  p = pathlib.Path("input.pdf")
  mb = p.stat().st_size / (1024 * 1024)
  pages = len(re.findall(rb"/Type\s*/Page\b", p.read_bytes())) if p.suffix.lower() == ".pdf" else None
  print(f"file={p.name} size={mb:.2f}MB approx_pages={pages}")
  assert 0 < mb <= 200, f"File size {mb:.2f}MB out of MinerU precision limit (0..200MB)"
  '
  # 1. 印刷体主力：检查 MinerU 凭据并解析本地 PDF / 扫描件 / 图片
  python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py config
  python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py file input.pdf --is-ocr --output-dir ./mineru_output

  # 2. 手写数学 / 408 答卷单题裁剪（支持 --bbox、--grid 或 --auto-bands 水平空白投影无损切题，输出严格 <145KB Baseline JPEG \xff\xd8\xff）
  python3 $HOME/.agents/skills/document-parsing/scripts/crop_exam_sheet.py --self-test
  python3 $HOME/.agents/skills/document-parsing/scripts/crop_exam_sheet.py answer_sheet.pdf --dpi 300 --page 1 --auto-bands --out-dir ./exam_crops
  python3 $HOME/.agents/skills/document-parsing/scripts/crop_exam_sheet.py answer_sheet.pdf --dpi 300 --page 1 --bbox 0.04,0.10,0.96,0.52 --out ./exam_crops/q17.jpg
  python3 $HOME/.agents/skills/document-parsing/scripts/crop_exam_sheet.py answer_sheet.pdf --dpi 300 --page 2 --grid 3,1 --out-dir ./exam_crops

  # 3. 禁上传云端的私密本地文档（.docx / .xlsx / .pdf）100% 离线结构化 Markdown + 表格提取
  python3 $HOME/.agents/skills/document-parsing/scripts/office_to_md.py private_contract.docx -o ./parsed/contract.md
  python3 $HOME/.agents/skills/document-parsing/scripts/office_to_md.py financial_ledger.xlsx -o ./parsed/ledger.md
  python3 $HOME/.agents/skills/document-parsing/scripts/office_to_md.py private_transcript.pdf --pages 1-5 -o ./parsed/transcript.md
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - **手写批阅红线**：考研数学 / 408 手写答卷与草稿严禁调用 `paddleocr` 或 `tesseract`（本机亦不维护本地 `paddleocr` 环境），强制执行「`300 DPI` 单题裁剪 -> `read_file` 多模态原样盲转写 -> 对照标准答案批阅」三步链路；
  - 遇到依赖或环境异常，统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **凭据路径**：MinerU 凭据自动读取 `~/.config/mineru/mineru.env` 中的 `MINERU_API_TOKEN`（统一纳管登记于 `~/.config/ai-relays/credentials.json` 的 `tool_apis.mineru` 指针台账，严禁在代码或文档中打印明文 Token）。

## Route

| Input or need | Read / Run next |
|---|---|
| Printed digital or scanned PDF, Office, image OCR, HTML, tables, formulas, batch parsing, Markdown/assets (Default Primary) | [`references/components/mineru-document-parse/guide.md`](./references/components/mineru-document-parse/guide.md) |
| Handwritten math / 408 exam answers & scratch work (`手写答卷批阅`) | **Strictly ban `paddleocr` / `tesseract`**; run [`scripts/crop_exam_sheet.py`](./scripts/crop_exam_sheet.py) (`--dpi 300 --page N --auto-bands`, `--bbox ...`, or `--grid ...`) to emit `<145KB` Baseline JPEG slices, transcribe verbatim via `read_file` multimodal vision, then compare against the answer key |
| Offline-only private `.docx` / `.xlsx` / `.pdf` extraction (when network upload is prohibited) | Run [`scripts/office_to_md.py`](./scripts/office_to_md.py) (`python-docx` / `openpyxl` / PyMuPDF `find_tables()` + `blocks`) for 100% local structured Markdown & table extraction, or slice raster pages via [`scripts/crop_exam_sheet.py`](./scripts/crop_exam_sheet.py) and inspect via `read_file` |
| PDF layout editing, form filling, reflow, rendering or visual signoff | `document-crafting` |

## Shared Contract

1. Inspect the input before choosing a parser; distinguish embedded text from
   raster pages, and distinguish printed documents (MinerU) from handwritten exam sheets (`crop_exam_sheet.py` + multimodal blind transcription).
2. Preserve page numbers, bounding boxes or timestamps when the downstream
   task needs provenance; when extracting personal resumes/rosters from multi-column PDFs or school-wide spreadsheets, isolate by PyMuPDF `get_text("blocks")` bounding boxes or exact (`Name + StudentID`) keys so adjacent entries never pollute the target profile.
3. Keep raw input and final parsed Markdown/JSON in a named workspace subdirectory, and **always clean up temporary page-split / `./exam_crops` / `./mineru_output` intermediate caches before finishing the turn** (aligning with `AGENTS.md` Rule II.2).
4. Check tables, formulas, OCR confidence and reading order on representative
   pages. A successful parser exit code is not content validation.
5. Never invent missing pages, ISBNs, labels or source locations.
