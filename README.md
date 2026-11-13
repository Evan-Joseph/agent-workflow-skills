# Agent Workflow Skills (`v2.0`)

<p align="center">
  <img src="https://img.shields.io/badge/Skills-20%20Production%20Packs-1f6feb?style=flat-square" alt="20 Skills" />
  <img src="https://img.shields.io/badge/Python%20Tooling-87%20Executable%20Scripts-2ea043?style=flat-square&logo=python&logoColor=white" alt="Python Scripts" />
  <img src="https://img.shields.io/badge/Harnesses-Claude%20Code%20%7C%20Codex%20%7C%20Antigravity%20%7C%20Oh--My--Pi-8957e5?style=flat-square" alt="Cross-Harness" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-d29922?style=flat-square" alt="Apache-2.0" /></a>
</p>

> **20 production-tested, cross-harness AI Agent skill packs** — combining structured `SKILL.md` contracts, **87 executable Python verification/automation scripts**, progressive-disclosure `references/` trees, and deterministic pre-delivery quality gates across **Claude Code**, **OpenAI Codex**, **Google Antigravity**, **Oh-My-Pi (`omp` / `PI-Desktop`)**, and compatible `SKILL.md` harnesses.
>
> **20 个经实战验证的跨平台 AI Agent 标准化技能包**：涵盖科研文献审计与投稿门禁、全栈工程质量与前端视觉系统、高保真长文档/PPT/视频工程、跨平台社区检索与移动端 ADB 治理，内置 **87 个可执行 Python 工具脚本**与确定性交付自审门禁。

---

## 1. Quick Installation / 一键安装

### Option A — Skills CLI (`npx skills`)
```bash
# Install all 20 skills
npx skills add Evan-Joseph/agent-workflow-skills

# Or install a single targeted skill (e.g., paper-publication-copilot or frontend-design)
npx skills add Evan-Joseph/agent-workflow-skills --skill paper-publication-copilot
```

### Option B — Claude Code Marketplace (`.claude-plugin/marketplace.json`)
```bash
/plugin marketplace add Evan-Joseph/agent-workflow-skills
/plugin install agent-workflow-skills@agent-workflow-skills
```

### Option C — Direct Clone to `~/.agents/skills` (Codex / Antigravity / Universal)
```bash
git clone https://github.com/Evan-Joseph/agent-workflow-skills.git /tmp/agent-workflow-skills
mkdir -p "$HOME/.agents/skills"
cp -R /tmp/agent-workflow-skills/skills/* "$HOME/.agents/skills/"
```

---

## 2. Complete Catalog of 20 Flagship Skills / 20 项核心技能全景矩阵

### A. Academic Research, Literature Audit & Publication Gates（学术检索、文献核验与顶会/SCI 投稿门禁）
| Skill | Core Capabilities & Bundled Scripts |
| :--- | :--- |
| **[`academic-literature-search`](./skills/academic-literature-search)** | Unified search & metadata verification across **OpenAlex, DBLP, ArXiv, Semantic Scholar, PubMed/PMC, and Wikipedia** (`openalex_search.py`, `dblp_search.py`, `citation_integrity_audit.py`, `rerank_abstracts.py`), featuring predatory-DOI hijack filtering and claim-source provenance auditing. |
| **[`paper-publication-copilot`](./skills/paper-publication-copilot)** | End-to-end CS/AI conference & journal submission governance (AAAI / ICML / NeurIPS / ACL / Elsevier EM) with geometric PDF layout & `Overfull \hbox` inspection (`latex_pdf_qa.py`), claim-evidence alignment, figure reuse tracking, and rebuttal verification. |
| **[`shuorenhua`](./skills/shuorenhua)** | Bilingual AI-slop detector & high-fidelity academic prose humanizer (`academic_style_audit.py`, `academic_terminology_audit.py`), pairing zero-distortion scholarly rewriting with context-aware interpersonal communication playbooks. |
| **[`ip-materials`](./skills/ip-materials)** | Automated 60-page source-code extraction, 84-column wrapping, user manual drafting, and CNIPA patent disclosure / Paper-to-Patent generation (`extract_code_material.py`, `build_docx_from_md.py`). |

### B. Software Engineering, Frontend UI/UX, Browser & Edge Cloud（全栈架构、前端设计、浏览器中继与云原生）
| Skill | Core Capabilities & Bundled Scripts |
| :--- | :--- |
| **[`engineering-quality`](./skills/engineering-quality)** | Full-stack architecture & engineering quality hub: Spec-Driven Development (SDD), minimal-diff discipline, reverse-first empirical debugging, non-interactive subprocess timeouts, and pre-push privacy/secret/monolith scanning (`pre_push_privacy_audit.py`, `scan_debt.py`). |
| **[`frontend-design`](./skills/frontend-design)** | Production Web & mobile UI/UX system integrating **shadcn/ui, transitions.dev, beautiful-ui, beUI, Rare UI, 192 industry design-system rules (`search.py`), and Impeccable visual audits**, enforcing concentric radii, anti-widow typography, and `<150 KB` multi-viewport visual self-review. |
| **[`browser-routing`](./skills/browser-routing)** | Zero-focus-stealing browser automation router across headless Playwright sandboxes, persistent CDP tab-group relays (`$CDP_RELAY_URL`), Camoufox (`camoufox_profile.py`), and non-intrusive macOS CAPTCHA human-handoff banners (`notify_human_handoff.py`). |
| **[`cloudflare`](./skills/cloudflare)** | Comprehensive Cloudflare engineering reference covering **Workers, Pages, D1, KV, R2, Durable Objects (WebSocket Hibernation quota gates), Hyperdrive, Workflows, Containers, Sandbox SDK, and Wrangler** across 64 product modules. |

### C. High-Fidelity Documents, Slides, Visuals & Video Engineering（长文档排版、渲染式 PPT、图像与音视频工程）
| Skill | Core Capabilities & Bundled Scripts |
| :--- | :--- |
| **[`document-crafting`](./skills/document-crafting)** | Zero-corruption `.docx` XML template engine (`docx_template_tool.py`, `fill_inspect.py`, `fill_write.py`, `docx_qa_gate.py`), offline HTML report rendering (`render_report.py`), and structured PRD/RFC co-authoring. |
| **[`document-parsing`](./skills/document-parsing)** | High-precision PDF/scan formula & table extraction routed via MinerU (`mineru_parse.py`) plus 300-DPI single-question sheet cropping (`crop_exam_sheet.py`) for multimodal transcription. |
| **[`awesome-ppt`](./skills/awesome-ppt)** | Image-rendered & editable slide deck pipeline: template visual schema cloning (`template_analyzer.py`), multimodal slide generation, HTML-to-PPTX conversion (`html_slides_to_pptx.py`), and 16:9 PPTX packaging (`images_to_pptx.py`). |
| **[`image-generation`](./skills/image-generation)** | Cross-harness image generation, editing, contact-sheet composition, and ImageMagick downsampling (`generate.py`, `grsai_generate.py`). |
| **[`video-use`](./skills/video-use)** | Deterministic FFmpeg transcoding (`yuv420p` + `+faststart`), word-level transcription (`transcribe.py`), EDL cutting, color grading (`grade.py`), contact timelines (`timeline_view.py`), and programmatic audio-reactive MV workflows. |

### D. Multi-Platform Intelligence, Developer Search & Device Ops（全网研学检索、社区情报与多端运维）
| Skill | Core Capabilities & Bundled Scripts |
| :--- | :--- |
| **[`developer-resource-search`](./skills/developer-resource-search)** | Parallel search across **GitHub repositories/issues/code, Stack Overflow, Hacker News, and HuggingFace Hub** (`github_search.py`, `stackoverflow_search.py`, `hackernews_search.py`, `huggingface_search.py`). |
| **[`agent-reach`](./skills/agent-reach)** | Multi-platform public content & community research hub (`reach_hub.py`, `xhs_research.py`, `doctor.py`) spanning WeChat articles, Xiaohongshu, Bilibili subtitles/comments, Zhihu, Douyin, X/Twitter, Reddit, V2EX, and Jina Reader. |
| **[`anysearch`](./skills/anysearch)** | Structured real-time cross-domain web & vertical search CLI (`anysearch_cli.py`, `provider_routing.py`) with automatic provider failover. |
| **[`linuxdo`](./skills/linuxdo)** | Read-only search, topic pagination, category browsing, and hot-topic tracking for the LinuxDO technical community (`linuxdo_cli.py`). |
| **[`quarkpan-resource-access`](./skills/quarkpan-resource-access)** | Quark Cloud Drive share-link metadata inspection, directory-size preflight, and resumable `Range` chunk downloading via `quarkpan-qr`. |
| **[`chat-history-export`](./skills/chat-history-export)** | Millisecond offline full-text search & contact governance audits over pre-exported WeChat JSON/SQLite archives (`chat_search.py`, `vault_cli.py`) and OneBot/QCE endpoints (`napcat_api.py`), paired with strict anti-ban redlines. |
| **[`mobile-device-ops`](./skills/mobile-device-ops)** | Multi-device Android ADB inspection, `<120 KB` downsampled screenshot capture, UI XML hierarchy dumping (`adb_ops.py`), safe system-package debloat rules, and Flutter/RN/JNI reverse-engineering triage. |

---

## 3. Migration Map from `v1.0` (Legacy 6 Docs -> `v2.0` Executable Suite)

All 6 documentation-only workflow templates from `v1.0` (`2026-05`) have been upgraded and consolidated into full script-backed `v2.0` skills:

| Legacy `v1.0` Skill | Upgraded `v2.0` Target Skill | Key Upgrade in `v2.0` |
| :--- | :--- | :--- |
| `academic-figure-design` | **[`paper-publication-copilot`](./skills/paper-publication-copilot)** (`references/components/academic-figure-ai/`) | Merged with `latex_pdf_qa.py` geometric PDF auditing, claim-evidence matrices, and journal revision gates |
| `frontend-refresh-workflow` | **[`frontend-design`](./skills/frontend-design)** (`references/components/project-frontend-refresh/`) | Expanded with 192 industry design rules (`search.py`), 5-pillar modern UI catalogs, and `<150 KB` visual QA gates |
| `rednote-research-workflow` | **[`agent-reach`](./skills/agent-reach)** (`scripts/xhs_research.py` & `reach_hub.py`) | Upgraded from prompt notes to executable multi-platform extraction & cross-source verification |
| `design-competition-entry` | **[`document-crafting`](./skills/document-crafting)** & **[`awesome-ppt`](./skills/awesome-ppt)** | Upgraded into deterministic `.docx` XML engines, offline HTML/PDF builders, and PPTX synthesis pipelines |
| `multi-model-consultation` | **[`engineering-quality`](./skills/engineering-quality)** | Integrated into Spec-Driven Development (SDD), empirical verification, and minimal-diff review contracts |
| `security-asset-search-workflow` | **[`developer-resource-search`](./skills/developer-resource-search)** & **[`anysearch`](./skills/anysearch)** | Replaced by structured multi-provider CLI search with clean public compliance boundaries |

---

## 4. Clean-Room Build & Zero-Leak Verification (`scripts/`)

This repository is maintained via a deterministic one-way clean-room compiler and a 5-stage CI blocker:

```bash
# 1. Re-compile and sanitize the 20 public skills + plugin manifests
python3 scripts/export_public_skills.py

# 2. Run the 5-stage zero-leak verification gate (symlinks, forbidden paths, PII, LAN/UUIDs, YAML + Python AST)
bash scripts/check.sh
```

Every commit must pass `bash scripts/check.sh` with `exit 0` (zero symlinks, zero personal paths/emails/domains/serials/hardcoded loopback ports, valid `SKILL.md` YAML frontmatter, and `ast.parse()` verification across all 87 Python scripts).

---

## License

Released under the [Apache License 2.0](./LICENSE). Third-party upstream attributions and embedded component licenses are documented in [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md) and individual skill directories.
