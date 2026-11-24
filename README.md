# Agent Workflow Skills

[![Agent Skills](https://img.shields.io/badge/format-SKILL.md-1f6feb?style=flat-square)](https://agentskills.io)
[![Skills](https://img.shields.io/badge/skills-22-2ea043?style=flat-square)](#available-skills)
[![Python Scripts](https://img.shields.io/badge/python_scripts-94-3776ab?style=flat-square&logo=python&logoColor=white)](#repository-structure)
[![License](https://img.shields.io/badge/license-Apache--2.0-d29922?style=flat-square)](./LICENSE)

A collection of 22 portable skills for AI coding agents, following the [Agent Skills (`SKILL.md`)](https://agentskills.io) format. Each skill folder packages concise instructions (`< 12 KB`), on-demand `references/` guides, and executable Python utilities (`94` scripts total) compatible with **Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Gemini CLI**, and other `SKILL.md`-enabled agents.

面向 AI 编程智能体的 22 个便携式标准技能包（遵循 `SKILL.md` 规范），覆盖学术文献检索与投稿检查、全栈工程与前端界面设计、长文档/演示文稿/音视频处理、浏览器自动化与多端开发配置管理，附带 94 个可执行 Python 工具脚本。

## Installation

### Skills CLI (`npx skills`)

```bash
# Install all 22 skills
npx skills add Evan-Joseph/agent-workflow-skills

# Install a single skill
npx skills add Evan-Joseph/agent-workflow-skills --skill academic-literature-search
```

### Claude Code Plugin Marketplace

```text
/plugin marketplace add Evan-Joseph/agent-workflow-skills
/plugin install agent-workflow-skills@agent-workflow-skills
```

### Manual Copy (`~/.agents/skills`)

```bash
git clone https://github.com/Evan-Joseph/agent-workflow-skills.git /tmp/agent-workflow-skills
mkdir -p "$HOME/.agents/skills"
cp -R /tmp/agent-workflow-skills/skills/* "$HOME/.agents/skills/"
```

## Available Skills

### Academic Research & Technical Writing

| Skill | Description & Bundled Tools |
| :--- | :--- |
| [`academic-literature-search`](./skills/academic-literature-search) | Literature search, citation verification, and abstract reranking across OpenAlex, DBLP, arXiv, Semantic Scholar, PubMed/PMC, and Wikipedia (`openalex_search.py`, `dblp_search.py`, `citation_integrity_audit.py`, `rerank_abstracts.py`). |
| [`paper-publication-copilot`](./skills/paper-publication-copilot) | Conference and journal submission workflow with LaTeX PDF layout inspection (`latex_pdf_qa.py`), claim-evidence alignment matrices, figure reuse tracking, and rebuttal checklists. |
| [`shuorenhua`](./skills/shuorenhua) | Bilingual AI-cliche detector, terminology consistency checker, and natural prose revision guide for technical docs, papers, and interpersonal messages (`academic_style_audit.py`, `academic_terminology_audit.py`). |
| [`ip-materials`](./skills/ip-materials) | Software copyright source-code formatting, user manual drafting, and patent technical disclosure templates (`extract_code_material.py`, `build_docx_from_md.py`). |

### Software Engineering, Web UI, Cloud & Security

| Skill | Description & Bundled Tools |
| :--- | :--- |
| [`engineering-quality`](./skills/engineering-quality) | Lightweight spec-driven development (SDD), minimal-diff editing discipline, non-interactive subprocess timeouts, and pre-push secret/PII scanning (`pre_push_privacy_audit.py`, `scan_debt.py`). |
| [`frontend-design`](./skills/frontend-design) | Web and mobile UI implementation workflow integrating `shadcn/ui`, component catalogs, searchable design rules (`search.py`), and multi-viewport visual inspection checklists. |
| [`browser-routing`](./skills/browser-routing) | Browser automation conventions across headless Playwright, persistent Chrome CDP tab-group relays (`cdp_ctl.py`), Camoufox (`camoufox_profile.py`), and non-intrusive CAPTCHA human-handoff alerts (`notify_human_handoff.py`). |
| [`cloudflare`](./skills/cloudflare) | Reference guides and quota checks for Cloudflare Workers, Pages, D1, KV, R2, Durable Objects (WebSocket Hibernation), Workflows, and Wrangler (`cf_health_and_quota.py`). |
| [`artex-client`](./skills/artex-client) | Zero-dependency REST CLI (`artex_cli.py`) with `0600` local JWT caching and a four-element finding verification gate (`Trust Boundary -> Affected Principal -> Concrete Reproduction -> Minimal Fix`) for authorized security evaluations. |
| [`local-machine-profile`](./skills/local-machine-profile) | Three-tier workstation SSOT pattern separating static verified baselines, live read-only environment probes (`collect_env_baseline.py`), and project ledger pointers without storing plaintext credentials. |

### Documents, Slides, Images & Video

| Skill | Description & Bundled Tools |
| :--- | :--- |
| [`document-crafting`](./skills/document-crafting) | Structured `.docx` XML template inspection and filling (`docx_template_tool.py`, `fill_inspect.py`, `fill_write.py`, `docx_qa_gate.py`), offline HTML report rendering (`render_report.py`), and RFC/PRD authoring guides. |
| [`document-parsing`](./skills/document-parsing) | PDF, scan, table, and formula extraction via MinerU (`mineru_parse.py`) alongside 300-DPI single-question image cropping (`crop_exam_sheet.py`) for multimodal transcription. |
| [`awesome-ppt`](./skills/awesome-ppt) | Slide deck generation and editable PPTX assembly pipeline (`template_analyzer.py`, `html_slides_to_pptx.py`, `images_to_pptx.py`, `build_deck.py`). |
| [`image-generation`](./skills/image-generation) | Image generation, editing, contact-sheet composition, and ImageMagick format/size conversion helpers (`generate.py`, `grsai_generate.py`). |
| [`video-use`](./skills/video-use) | FFmpeg transcoding, parallel hardware HTML/WebGL-to-MP4 rendering (`web_to_mp4.py`), transcription (`transcribe.py`), EDL cutting, color grading (`grade.py`), and timeline contact sheets (`timeline_view.py`). |

### Search, Community Research & Device Operations

| Skill | Description & Bundled Tools |
| :--- | :--- |
| [`developer-resource-search`](./skills/developer-resource-search) | CLI search across GitHub repositories/issues/code, Stack Overflow, Hacker News, and Hugging Face Hub (`github_search.py`, `stackoverflow_search.py`, `hackernews_search.py`, `huggingface_search.py`). |
| [`agent-reach`](./skills/agent-reach) | Public article, subtitle, and discussion retrieval across technical blogs, video platforms, and social forums (`reach_hub.py`, `xhs_research.py`, `doctor.py`). |
| [`anysearch`](./skills/anysearch) | Multi-provider web and vertical search CLI with automatic fallback (`anysearch_cli.py`, `provider_routing.py`). |
| [`linuxdo`](./skills/linuxdo) | Read-only search, topic pagination, and category browsing CLI for the LinuxDO forum (`linuxdo_cli.py`). |
| [`quarkpan-resource-access`](./skills/quarkpan-resource-access) | Quark Cloud Drive share metadata inspection and resumable `Range` downloading wrapper. |
| [`chat-history-export`](./skills/chat-history-export) | Offline read-only search across exported IM JSON/SQLite archives (`chat_search.py`, `vault_cli.py`, `napcat_api.py`) with strict anti-automation safety rules for desktop IM clients. |
| [`mobile-device-ops`](./skills/mobile-device-ops) | Android ADB device inspection, downsampled screenshot capture, UI hierarchy XML dumping (`adb_ops.py`), and mobile reverse-engineering static triage guides. |

## Repository Structure

```text
agent-workflow-skills/
├── .claude-plugin/marketplace.json   # Claude Code plugin marketplace manifest
├── .codex-plugin/plugin.json         # OpenAI Codex plugin manifest
├── skills/                           # 22 self-contained SKILL.md directories
├── scripts/
│   ├── export_public_skills.py       # Sanitization & manifest sync script
│   └── check.sh                      # Validation gate (YAML, Python AST, links & privacy)
├── THIRD_PARTY_NOTICES.md            # Upstream attributions and component licenses
└── LICENSE                           # Apache License 2.0
```

## Validation

Run the repository check suite locally to verify zero symlinks, valid `SKILL.md` YAML frontmatter, `ast.parse()` syntax validity across all Python scripts, and zero broken relative Markdown links:

```bash
bash scripts/check.sh
```

## License

Licensed under the [Apache License 2.0](./LICENSE). Upstream attributions and bundled component licenses are listed in [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md).
