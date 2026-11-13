---
name: paper-publication-copilot
description: "CS/AI科研论文投稿总控 Skill。用于论文工作区治理、AI辅助论文写作、实验推进、实验审计、claim-evidence 对齐、引用核验、图表复用登记、自我审稿、外部审稿结果合并、返修迭代、rebuttal/response 检查和投稿前门禁。适用于会议论文、期刊论文、Neurocomputing/KBS/Elsevier EM/PRICAI/PRCV/ACL/NeurIPS/ICML/ICLR等投稿与返修流程；不用于自动投稿、自动上传未发表论文或替代作者最终判断。"
metadata:
  short-description: CS/AI科研论文写作、实验审计与投稿总控
---

# Paper Publication Copilot

Use this skill as the coordinator for auditable CS/AI paper workflows. It owns
the paper lifecycle and routes only the blocking specialist mode or retained
cross-domain Skill needed for the current phase.

## Core Boundary

- Keep the paper workspace as the source of truth. Read existing `状态.md`, manuscript folders, review folders, notes, figures, code, logs, and submission materials before proposing work.
- Do not auto-submit, email, publish, or upload unpublished manuscripts, reviews, code, data, or supplements to external services.
- Do not treat AI reviews as acceptance predictions or final truth. Convert them into risk records.
- Do not rewrite the whole manuscript when a local patch, audit table, or checklist addresses the task.
- Verify current venue rules from official sources before making hard claims about deadlines, anonymity, AI disclosure, page limits, copyright, or submission systems.

## Specialist Routing

Use the smallest relevant set:

| Need | Route |
|---|---|
| Literature discovery, citation existence, citation support, lineage, PRISMA-like provenance | `academic-literature-search` |
| Manuscript review, methodology critique, desk-reject risk, re-review, rebuttal audit | `references/components/academic-paper-review/guide.md` |
| Elsevier Editorial Manager / *Neurocomputing*-class journal submission & revision gates (`Highlights <=85 chars`, `CRediT`, flat LaTeX source, `Response to Reviewers`, local `:3425` `group/sol` + `group/opus` simulated review) | [`references/elsevier-em-revision-gate.md`](./references/elsevier-em-revision-gate.md) |
| Paper figures, figure prompts, figure QA, chart fidelity, cross-venue reuse | `references/components/academic-figure-ai/guide.md` |
| Experiment logs, CSV/Excel metrics, statistics, plots, run provenance | `scripts/latex_pdf_qa.py` & `miniconda-agent-general` (`python3`) |
| Rendered PDF, LaTeX `.log` / BibTeX `.blg` & bbox layout QA (Type 3 bitmap fonts, `Label(s) may have changed`, BibTeX empty `journal/booktitle/year`, `Overfull \hbox`, orphan tail `小尾巴` fill ratio, margin overflow) | `scripts/latex_pdf_qa.py` (`miniconda-agent-general`) and `document-crafting` |
| Long-form writing coordination after risks are clear | `document-crafting` |
| Fact-preserving academic drafting, de-AI revision, terminology consistency, and whole-manuscript style audit | `shuorenhua` academic mode |
| GitHub, Hugging Face, benchmark code, tooling and implementation resources | `developer-resource-search` |

## Workflow Selection

- **New paper or new venue branch**: read [workflow.md](references/workflow.md), then create or update the eight audit artifacts.
- **Existing manuscript pre-submission**: read [gates.md](references/gates.md), then build `review_risk_register.md`, `claim_evidence_matrix.md`, and `submission_checklist.md`.
- **Received reviews, journal R1/R2 revision, or local simulated review**: read [workflow.md](references/workflow.md) and (for Elsevier / *Neurocomputing*-class journals) [elsevier-em-revision-gate.md](references/elsevier-em-revision-gate.md), then update `review_risk_register.md` and `revision_queue.md`; read `references/components/academic-paper-review/guide.md` for re-review or rebuttal audit, and use local MagPie `${OPENAI_COMPAT_BASE_URL}` (`group/sol` + `group/opus`) for offline simulated peer review. **Hard Redline**: Never enter advisor (`<ADVISOR_EMAIL>`) or collaborator emails into third-party AI review websites (such as `paperreview.ai`); always use the user's own authorized email or token.
- **Experiment-backed revision**: read [templates.md](references/templates.md), then analyze logs and metrics using `python3` (`pandas`/`matplotlib`/`scipy`).
- **Figure redraw or multi-venue reuse risk**: read [gates.md](references/gates.md), then route to `references/components/academic-figure-ai/guide.md`. For multi-frame video sequence figures, compute SHA-256 / pHash across all sub-frames and inspect via `read_file` (`<150KB` JPEG) to prevent duplicate first-frame bugs and label overflow.
- **Idea origin & author list verification**: Before drafting or revising paper history, author lists, or core problem formulations, cross-check WeChat history (`chat-history-export`), meeting notes, and Git commit logs rather than guessing.
- **Zero meta-language & quote hygiene**: Never leave internal prompt notes (e.g., `内部审稿后添加`, `从OpenReview获取`, `严格控制在XX页`) in manuscript text; use `\enquote{}` (`csquotes`) or proper TeX quotes (` ``...'' `) instead of raw straight quotes.
- **Academic prose revision or terminology cleanup**: establish the intended claims and evidence first, then route to `shuorenhua` academic mode; re-run claim/evidence and terminology gates after editing.
- **External service or cross-model review**: read [privacy-and-submission-boundaries.md](references/privacy-and-submission-boundaries.md) before any upload.

## Required Audit Artifacts

For each active venue branch, maintain these artifacts when relevant:

1. `status.md`
2. `claim_evidence_matrix.md`
3. `literature_provenance.md`
4. `experiment_audit_matrix.md`
5. `figure_asset_register.md`
6. `review_risk_register.md`
7. `revision_queue.md`
8. `submission_checklist.md`

Use existing workspace naming conventions. If the repo already uses Chinese natural names, keep that style for notes; keep LaTeX, BibTeX, scripts, and submission package names compatible with tooling.

## Default Operating Loop

1. Locate the current paper branch and read `状态.md` first.
2. Identify the current stage: scoping, writing, experiment, review, revision, final checks, or submission packaging.
3. Build or refresh the relevant audit artifacts before editing the manuscript.
4. Route specialist tasks to the existing skills listed above.
5. Apply changes only when the evidence and scope are clear.
6. For academic prose edits, preserve numbers, citations, polarity, modality, causal strength, baselines, scope, and canonical terminology; do not use detector scores as an editing target.
7. When writing or reconstructing a long `.tex` manuscript (`>350` lines), never emit the entire file in a single `write_file` tool call (avoids output token truncation `EOF while parsing a string`). Write in `250–350` line chunks with `write_file(..., Append=True)` or split into `\input{sections/...}`.
8. Compile and run `python3 $HOME/.agents/skills/paper-publication-copilot/scripts/latex_pdf_qa.py <Main.pdf> --log <Main.log> --blg <Main.blg>` whenever layout, prose, figures, or references change. Eliminate all Type 3 bitmap fonts (`matplotlib.rcParams['pdf.fonttype'] = 42`), `Label(s) may have changed` rerun warnings, BibTeX empty `journal/booktitle/year` warnings, `Overfull \hbox`, figure/table margin overflows, and short paragraph last-line orphan tails (`小尾巴`, target `80%–100%` last-line width fill via concise phrasing or `\looseness=-1`); run `academic-literature-search/scripts/citation_integrity_audit.py --bib-file <refs.bib>` before submission.
9. Finish with remaining risks, validation commands, and required human confirmations.

## Human Confirmation Points

Always leave these to the user or explicit human approval:

- Research direction and target venue choice.
- Whether to run large experiments or change the main claim.
- Author list, affiliations, CRediT, conflicts, funding, acknowledgements, data availability, and AI disclosure.
- External upload of unpublished manuscripts, review comments, code, or data.
- Formal submission, camera-ready upload, public release, email sending, or response submission.

## External Source Policy

External skill repositories can inform workflow design, but do not copy non-permissive or unclear-license content into this skill. Re-express any borrowed workflow idea in local terms and keep source notes in project reports, not in runtime instructions.
