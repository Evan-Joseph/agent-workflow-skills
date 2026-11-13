# MinerU API Reference

Sources checked on 2026-07-02:

- MinerU API docs: https://mineru.net/apiManage/docs
- MinerU output file docs: https://opendatalab.github.io/MinerU/reference/output_files/

## API Modes

Precision API is the default route for reliable document-to-Markdown work.

| Mode | Auth | Endpoints | Limits | Output |
|---|---|---|---|---|
| Precision API | `Authorization: Bearer <token>` | `/api/v4/extract/task`, `/api/v4/file-urls/batch`, `/api/v4/extract/task/batch`, `/api/v4/extract-results/batch/{batch_id}` | 200 MB, 200 pages, batch up to 200; signed local upload request up to 50 file URLs per call | Zip with Markdown and JSON by default; optional `docx`, `html`, `latex` |
| Agent lightweight API | No token; IP-limited | `/api/v1/agent/parse/url`, `/api/v1/agent/parse/file`, `/api/v1/agent/parse/{task_id}` | 10 MB, 20 pages, single file | Markdown URL only |

Base URL defaults to `https://mineru.net`. The bundled script also accepts `MINERU_API_BASE`, first from the process environment and then from `~/.config/mineru/mineru.env`.

## Precision API

### Single URL Task

`POST /api/v4/extract/task`

Required header:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Request fields:

- `url` required.
- `model_version`: `pipeline`, `vlm`, or `MinerU-HTML`. Use `vlm` for most non-HTML work; use `MinerU-HTML` for HTML sources.
- `is_ocr`: boolean, default `false`, pipeline/vlm only.
- `enable_formula`: boolean, default `true`, pipeline/vlm only.
- `enable_table`: boolean, default `true`, pipeline/vlm only.
- `language`: default `ch`, pipeline/vlm only.
- `data_id`: optional, `[A-Za-z0-9_.-]`, max 128 chars.
- `callback`: optional callback URL. If set, `seed` is required.
- `seed`: optional callback signing seed, `[A-Za-z0-9_]`, max 64 chars.
- `extra_formats`: optional array drawn from `docx`, `html`, `latex`. Ignored for HTML sources.
- `page_ranges`: examples: `2,4-6`, `2--2`.
- `no_cache`: boolean, default `false`.
- `cache_tolerance`: seconds, default `900`, effective when `no_cache=false`.

Success response contains `data.task_id`.

Poll with `GET /api/v4/extract/task/{task_id}`. States include `pending`, `running`, `converting`, `done`, and `failed`. Running responses may include `extract_progress.extracted_pages`, `total_pages`, and `start_time`. Done responses include `full_zip_url`.

### Local File Batch Upload

`POST /api/v4/file-urls/batch`

Use this for local files, including a single local file. Do not call `/api/v4/extract/task` with local file bytes.

Request fields:

- Global fields: `enable_formula`, `enable_table`, `language`, `callback`, `seed`, `extra_formats`, `model_version`.
- `files`: array of file descriptors:
  - `name` required; include the correct extension.
  - `data_id` optional.
  - `is_ocr` optional.
  - `page_ranges` optional.

Success response contains `data.batch_id` and `data.file_urls`. Upload each local file to the matching URL with HTTP `PUT`. The docs state no `Content-Type` header is needed. Upload links are valid for 24 hours. After upload, MinerU automatically submits parsing tasks.

Poll with `GET /api/v4/extract-results/batch/{batch_id}`.

### Batch URL Task

`POST /api/v4/extract/task/batch`

Request fields are similar to local batch upload, but each file object uses `url` instead of `name`. Success response contains `data.batch_id`.

Poll with `GET /api/v4/extract-results/batch/{batch_id}`. Each item in `data.extract_result` has:

- `file_name`
- `state`: `waiting-file`, `pending`, `running`, `converting`, `done`, or `failed`
- `full_zip_url` when done
- `err_msg` when failed
- `data_id` if provided
- optional `extract_progress`

## Agent Lightweight API

This route is for quick no-token parsing only.

### URL

`POST /api/v1/agent/parse/url`

Request fields:

- `url` required.
- `file_name` optional.
- `language`, `enable_table`, `is_ocr`, `enable_formula`, `page_range` are primarily PDF options.
- `page_range` supports a single page or `from-to`, not complex comma ranges.

Success response contains `data.task_id`.

### Local File

`POST /api/v1/agent/parse/file`

Request fields mirror URL mode, with `file_name` required. Response contains `data.task_id` and signed `data.file_url`. Upload with PUT, then poll.

### Poll

`GET /api/v1/agent/parse/{task_id}`

States include `waiting-file`, `uploading`, `pending`, `running`, `done`, and `failed`. Done responses include `data.markdown_url`.

Agent errors:

| Code | Meaning |
|---|---|
| `-30001` | File size exceeds 10 MB lightweight limit |
| `-30002` | Unsupported lightweight file type |
| `-30003` | Page count exceeds lightweight limit |
| `-30004` | Request parameter error |

## Languages

Common values:

- `ch`: Chinese, English, Traditional Chinese; default.
- `ch_server`: Chinese, English, Traditional Chinese, Japanese; useful for handwritten/traditional-heavy content.
- `en`: English.
- `japan`, `korean`, `chinese_cht`, `ta`, `te`, `ka`, `el`, `th`.
- Family packs: `latin`, `arabic`, `cyrillic`, `east_slavic`, `devanagari`.

## Precision Error Codes

Common API-level errors:

| Code | Meaning |
|---|---|
| `A0202` | Token error |
| `A0211` | Token expired |
| `-500` | Parameter error |
| `-10001` | Service exception |
| `-10002` | Request parameter error |
| `-60001` | Failed to generate upload URL |
| `-60002` | Could not match file format |
| `-60003` | File read failed |
| `-60004` | Empty file |
| `-60005` | File size exceeds 200 MB |
| `-60006` | Page count exceeds 200 pages |
| `-60007` | Model service temporarily unavailable |
| `-60008` | File read timeout |
| `-60009` | Submission queue full |
| `-60010` | Parsing failed |
| `-60011` | Could not obtain valid file |
| `-60012` | Task not found |
| `-60013` | No permission for task |
| `-60015` / `-60016` | File conversion failed |
| `-60018` | Daily parsing task limit reached |
| `-60019` | HTML parsing quota exhausted |
| `-60022` | Web page read failed |

Always surface the raw `trace_id`, `code`, and `msg` in failure reports. Do not retry blindly after quota, token, unsupported file, or page/size-limit errors.
