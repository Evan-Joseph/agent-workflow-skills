# MinerU Output Layout

Official output docs: https://opendatalab.github.io/MinerU/reference/output_files/

## Files in MinerU Results

The exact zip contents vary by backend and source type. Preserve `raw/extracted/` because downstream details can change between MinerU versions.

Common files:

- `full.md`: primary Markdown result.
- `main.html`: HTML source extraction result, when parsing HTML.
- `{original_filename}_layout.pdf`: visual layout analysis with reading-order boxes.
- `{original_filename}_span.pdf`: pipeline backend text span debug view.
- `{original_filename}_model.json`: model inference result.
- `{original_filename}_middle.json`: intermediate processing result.
- `{original_filename}_content_list.json`: flat readable content blocks in reading order.
- `{original_filename}_content_list_v2.json`: newer page-grouped structured output, added in MinerU 3.0 and subject to change.
- `images/...`: extracted images, tables, charts, formulas, or screenshots referenced by Markdown and JSON.
- Optional exports requested through `extra_formats`: `.docx`, `.html`, `.latex` or `.tex`.

The MinerU API docs describe `layout.json` as corresponding to the intermediate result `middle.json`; `*_model.json` maps to model inference output; `*_content_list.json` maps to content list output.

## Local Normalized Layout

The bundled script normalizes a downloaded result to:

```text
<output-dir>/<safe-source-stem>__<task-or-batch-id>/
  raw/result.zip
  raw/extracted/
  markdown/full.md
  markdown/images/
  json/
  ./assets/images/
  html/
  exports/
  debug/
  manifest.json
```

Rules:

- Keep the original zip at `raw/result.zip`.
- Extract the zip safely into `raw/extracted/`.
- Copy all Markdown files into `markdown/`; if `full.md` exists, also keep it as `markdown/full.md`.
- Copy `images/` into both the run's `./assets/images/` and `markdown/images/` so original Markdown image links still render locally.
- Copy `*_content_list*.json`, `*_middle.json`, `*_model.json`, `layout.json`, and other JSON files into `json/`.
- Copy `*_layout.pdf`, `*_span.pdf`, and debug PDFs into `debug/`.
- Copy `main.html` into `html/`.
- Copy optional `.docx`, `.html`, `.tex`, `.latex`, and other export files into `exports/` by type, unless the file is `main.html`.
- Write `manifest.json` with source, API mode, parameters, task or batch data, downloaded URLs, file inventory, and SHA256 hashes.

## Content List Notes

`content_list.json` is a flat structure. Common `type` values:

- `text`: text/title. `text_level` may identify heading level.
- `image`: visual image. Usually includes `img_path`, captions, footnotes, `bbox`, and `page_idx`.
- `table`: table, often with `table_body` as HTML.
- `equation`: display formula, often with LaTeX text and optional image path.
- `chart`: chart image and optional structured content.
- VLM extensions: `code`, `list`, `header`, `footer`, `page_number`, `aside_text`, `page_footnote`.

`content_list_v2.json` is page-grouped. Items use a unified `type + content` payload and may contain rich span lists, anchors, hyperlinks, and visual block metadata.

Coordinate conventions differ:

- `content_list.json` bounding boxes are normalized into a 0-1000 range.
- VLM raw `model.json` uses normalized page percentages in `[0, 1]`.
- Pipeline intermediate data may use page-space coordinates.

## Practical Quality Checks

For serious document ingestion:

1. Read `markdown/full.md` for end-user text quality.
2. Check `json/content_list.json` for block ordering and table/formula extraction.
3. Open `debug/*_layout.pdf` when sections, columns, captions, or reading order look wrong.
4. Open `debug/*_span.pdf` for pipeline text loss or formula segmentation issues.
5. Compare image paths in Markdown against `markdown/images/` before moving outputs.
6. For HTML sources, inspect both `markdown/full.md` and `html/main.html`.
