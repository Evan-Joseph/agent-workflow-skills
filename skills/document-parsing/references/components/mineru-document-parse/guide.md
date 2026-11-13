---
name: mineru-document-parse
description: "用于 MinerU API 文档解析和多格式转 Markdown。Use when parsing PDF, Office, image, or HTML files; extracting OCR/tables/formulas; handling MinerU zip results; batch parsing; or organizing Markdown, JSON, assets, and exports."
---

# MinerU Document Parse

## Overview

Use MinerU for document-to-Markdown work when layout, OCR, tables, formulas, Office conversion, images, or structured JSON outputs matter. Prefer the bundled CLI so task submission, polling, download, zip extraction, naming, and output organization stay consistent.

Never write API keys, tokens, cookies, or signed upload URLs into Skill files, project files, shell profiles, examples, or logs. Use `MINERU_API_TOKEN` for the precision API.

## Credentials

The CLI reads credentials in this order:

1. `MINERU_API_TOKEN` / `MINERU_API_BASE` from the current process environment.
2. `~/.config/mineru/mineru.env`, a private user-level env file with mode `600`.

Check status without printing secrets:

```bash
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py config
```

Save or rotate the token:

```bash
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py save-token
```

## Route

Use `scripts/mineru_parse.py`:

- Precision API: use for normal work. Requires `MINERU_API_TOKEN`, supports up to 200 MB / 200 pages, batch tasks, Markdown + JSON zip, and optional `docx/html/latex` exports.
- Agent lightweight API: use only for quick small files when no token should be used. It is IP-limited, single-file, up to 10 MB / 20 pages, and returns Markdown only.

## Quick Commands

Precision URL parsing:

```bash
export MINERU_API_TOKEN='<token>'
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py \
  url 'https://example.com/paper.pdf' \
  --model-version vlm \
  --extra-format docx \
  --output-dir ./mineru-output
```

Precision local files:

```bash
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py \
  file ./paper.pdf ./slides.pptx \
  --language ch \
  --output-dir ./mineru-output
```

Agent lightweight parsing:

```bash
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py \
  agent-file ./small.pdf \
  --output-dir ./mineru-output
```

Organize an existing MinerU zip:

```bash
python3 $HOME/.agents/skills/document-parsing/references/components/mineru-document-parse/scripts/mineru_parse.py \
  organize ./result.zip \
  --source-name paper.pdf \
  --output-dir ./mineru-output
```

## Workflow

1. Check source type and size. Use precision API for serious work, batch work, HTML, optional exports, or files near the lightweight limits.
2. Use `--model-version vlm` for most PDF/image/Office documents. Use `--model-version MinerU-HTML` for HTML sources. `auto` chooses this from extensions and rejects mixed HTML/non-HTML batches.
3. Set `--is-ocr` for scanned PDFs or image-heavy documents. Keep table and formula recognition enabled unless speed matters more than structure.
4. Use `--page-ranges` for precision API and `--page-range` for Agent API; the lightweight API only supports a simple single page or `from-to` range.
5. Let the CLI poll, download, and organize outputs. If polling times out, keep the returned `task_id` or `batch_id` and use `status` or `batch-status` later.
6. Inspect `manifest.json`, `markdown/full.md`, `json/content_list.json`, and `debug/*_layout.pdf` / `debug/*_span.pdf` when quality matters.

## Output Convention

Each run is placed under:

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

`raw/extracted/` always preserves MinerU's original zip layout. The other folders are normalized copies for daily use.

## References

- Read `references/mineru-api.md` when choosing endpoint, parameters, limits, states, or error handling.
- Read `references/output-layout.md` when inspecting MinerU zip contents or building downstream processors from `content_list.json`, `middle.json`, or `model.json`.

## Common Mistakes

- Do not use the Agent lightweight API for important Office/PDF conversion unless the user explicitly wants a no-token quick pass.
- Do not submit local files to `/api/v4/extract/task`; v4 local upload uses `/api/v4/file-urls/batch`, then PUT upload, then batch polling.
- Do not assume `content_list.json` and `content_list_v2.json` have the same shape. V2 is page-grouped and newer.
- Do not promise legal, privacy, or copyright clearance for submitted documents. Confirm with the user before uploading sensitive or unpublished material.
- Do not log or persist `MINERU_API_TOKEN`. If the token is missing, ask the user to export it or provide a one-time environment variable for the command.
