# Privacy And Submission Boundaries

## Default Rule

Keep unpublished manuscripts, reviewer comments, draft rebuttals, experiment logs, datasets, and author metadata local unless the user explicitly authorizes a specific external upload.

## Before External Upload

Record:

- Service name and URL.
- Content class being uploaded.
- Whether the content contains unpublished manuscript text, reviews, author metadata, code, data, or secrets.
- Upload purpose.
- Expected output.
- Token, result URL, or retrieval handle when applicable.
- User confirmation.

Prefer uploading the minimum necessary content. When a task can be done with metadata, excerpts, or anonymized snippets, avoid full-text upload.

## AI Disclosure

Track AI-assisted work in the project notes. Do not decide final disclosure text without checking the venue or publisher's current official policy.

Common disclosure-sensitive actions:

- Drafting or rewriting manuscript prose.
- Generating or editing figures.
- Generating code used for experiments or analysis.
- Translating or copy-editing.
- External AI review of the manuscript.

## Human-Only Actions

Do not perform these without explicit instruction at the moment of action:

- Submit or resubmit a manuscript.
- Upload camera-ready files.
- Submit rebuttal or response-to-reviewers.
- Email editors, chairs, reviewers, or coauthors.
- Publicly release code, data, figures, preprints, or project pages.
- Change author list, author order, conflicts, funding, data availability, or CRediT statements as final facts.

## Local Records

When using any external review or AI service, save the raw response and a readable summary under the venue branch's `外部评审/` or equivalent directory. The token or URL is the retrieval handle; do not rely on email arrival alone.
