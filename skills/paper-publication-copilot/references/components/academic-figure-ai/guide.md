---
name: academic-figure-ai
description: "用于 CS/AI 论文图表生成、重绘和审查。Use when designing academic figure prompts, choosing reference images, rebuilding paper figures, or checking generated figures for layout, factual accuracy, and publication readiness."
metadata:
  short-description: 学术论文插图生成与审核
---

# Academic Figure AI

Use this skill to turn a paper's figure intent, data, reference images, and venue constraints into an AI-image prompt plus a reconstruction plan. Treat image models as composition engines, not truth sources. For "top-tier conference style", do not start from generic rounded boxes; first retrieve or inspect strong academic references, plan the visual claim, then write the prompt.

## Core Rule

For publication figures, separate three roles:

1. **Image2/Grsai**: composition, visual rhythm, rough panel layout, overall design quality.
2. **Ground-truth assets**: CSVs, logs, source images, existing figures, captions, and paper text decide facts.
3. **PPT/matplotlib/vector rebuild**: final numbers, labels, axes, legends, image crops, arrows, and editable objects.

Do not trust generated text, generated chart values, generated axis geometry, generated labels, or generated schema/code snippets as final content.

## Workflow

### 1. Inspect local context first

- Locate the paper draft, figure list, captions, existing images, CSVs, logs, source photos, and prior prompts.
- Respect the existing directory structure and naming scheme.
- Do not rename, delete, overwrite, or reorganize figure assets unless the user explicitly asks.
- Identify venue constraints: single-column vs two-column, max height, final format, font size, and whether title belongs in caption only.
- Read the exact paragraph that introduces or cites the figure. Record the one-sentence reviewer takeaway the visual must create.

### 1.5. Retrieve and grade references

Before writing Image2 prompts for a serious paper figure:

- Search local reference folders first; if weak, search the web or relevant communities for CS/AI methodology figures, PaperBanana-style examples, and venue-adjacent papers.
- Classify each reference by role: layout, style, content, chart grammar, or anti-example.
- Keep only 2--5 references per figure. Too many references dilute style control.
- Prefer references with strong hierarchy, asymmetric but disciplined layout, compact labels, visible reading path, and one highlighted contribution.
- Reject references that are merely clean but visually ordinary, have decorative 3D/chartjunk, rely on tiny text, or conflict with the paper's scientific claim.
- State what to transfer and what not to transfer from every reference.

### 2. Classify the figure

- **Concept/pipeline figure**: Image2 can generate the visual draft, but facts and text cards must be rebuilt.
- **Dataset/sample figure**: Image2 may help with layout; original dataset images must stay as independent objects and keep aspect ratio.
- **Numerical chart**: Image2 is layout-only. Rebuild chart geometry from CSV/matplotlib/PPT shapes.
- **Mixed diagnostic figure**: Split into panels. For chart panels, rebuild values; for visual panels, preserve source images.
- **Dense text/table figure**: Avoid direct image-model text. Use native PPT/LaTeX text.

### 3. Build a prompt package, not prose

Use short labeled sections or YAML. Include:

- `figure_id`
- `target_size` or intended aspect ratio
- `figure_type`
- `paper_claim`
- `reviewer_takeaway`
- `layout`
- `reference_images`
- `content_anchors`
- `exact_text_strings`
- `data_sources`
- `style`
- `negative_constraints`
- `rebuild_plan`
- `fact_check`

For top-tier CS/AI figure drafts, also include:

- `visual_direction`: e.g. editorial-schematic, compact diagnostic dashboard, split-panel training analysis.
- `reading_path`: the exact order a reviewer should scan.
- `hierarchy`: primary object, secondary evidence, tertiary labels.
- `signature_motif`: one restrained visual device that makes the figure memorable, such as a target-document focal card, a thin amber checkpoint rule, or a diagnostic matrix spine. Use at most one motif per figure.
- `reject_if`: concrete failures that make a generated draft unusable.

For image inputs, number each reference explicitly: `Image 1: layout reference`, `Image 2: style reference`, `Image 3: source photo`, etc. State exactly how each reference may be used.

### 4. Use references correctly

- Layout references may transfer panel rhythm, spacing, density, hierarchy, and palette mood.
- Style references may transfer line weight, rounded containers, white-space management, and overall scientific polish.
- Content references supply source photos, screenshots, or existing chart geometry.
- Never allow style references to transfer unrelated subject matter, icons, logos, people, colors, or text.
- For dataset images, require independent image cards or PPT picture objects. Never flatten several source photos into one contact sheet unless the final figure truly needs a contact sheet.

### 5. Control text and typography

- Put literal in-image text in quotes.
- Keep text sparse. Prefer panel labels, short titles, axis labels, legend labels, and compact annotations.
- Do not put full figure titles inside the image when the paper caption owns the title.
- Use standard publication fonts. Default to Times New Roman for prose labels and Consolas/monospace for code-like strings when the project has no other convention.
- For unusual field names or acronyms, spell them exactly and include a rebuild note because image models still misspell.
- For small text or dense infographics, use higher quality if generating through OpenAI; still plan to relabel manually.

### 6. Specify layout like a designer

State aspect ratio, orientation, panel count, panel order, gutters, margins, background, border style, line weight, gridline style, and legend location. Prefer wide two-column layouts for CS conference overview figures unless the draft requires single-column.

Default CS/AI paper style:

- white or very light background
- low-saturation palette
- strong hierarchy
- minimal decoration
- no 3D chart effects
- no drop shadows unless the existing design system requires them
- black-and-white readable through line style, marker shape, direct labels, and ordering

Top-tier style cues for CS/AI methodology and diagnostic figures:

- Use a clear visual thesis, not a uniform chain of equally weighted boxes.
- Create depth through hierarchy, scale, grouping, whitespace, and line weight, not shadows or 3D decoration.
- Use one focal region where the paper's contribution lives; other elements support it.
- Prefer restrained asymmetry: one large anchor panel plus smaller evidence cards often reads stronger than four identical columns.
- Put dense facts into rebuilt PPT/LaTeX text or deterministic charts; let Image2 establish rhythm, spacing, and motif.
- Avoid "enterprise slide template" aesthetics: oversized cards, generic icons, and decorative callout strips make paper figures look average.

### 7. Make negative constraints explicit

Always ban:

- figure-title text inside the image when captions own titles
- watermarks, logos, venue names, old submission names
- people, mascots, cartoons, avatars, unnecessary robots
- decorative chartjunk, 3D bars, gradients, glow, lens flare
- fabricated numbers, invented categories, invented architecture blocks
- flattened multi-element objects when PPT editing is required

Add project-specific bans from the paper. For example, if a pipeline is about target construction, ban model-forward arrows, closed-loop execution arrows, policy/planner boxes, and JSON action schemas unless those are actually in the method.

### 8. Produce a reconstruction plan

For every figure, list:

- which elements are source images
- which elements are native text boxes
- which elements are shapes/arrows
- which panels are generated raster drafts
- which charts are rebuilt from CSV/matplotlib
- which numbers or strings require manual proofing
- final expected export format

For PPT/PPTX packs, each semantically distinct image, label, arrow, bar, line, legend swatch, and annotation should be independently editable unless the user asks for flattened art.

### 9. Run figure QA

Before handing off:

- Check that generated drafts match figure intent and paper claims.
- Check exact data sources for all values.
- Check no old venue/task/prompt pollution appears.
- Check source images are not stretched or merged.
- Check all panels are readable at final paper size.
- Check captions and in-figure text do not duplicate each other.
- Check LaTeX figure placement and page budget if the user asks for integration.

## Reference Files

- For detailed prompt templates and QA rubrics, read `references/prompt-and-qa.md`.
- For PPT/matplotlib rebuild rules, read `references/rebuild.md`.
- For cross-venue figure reuse, AI-generation disclosure, source traceability, and figure fidelity checks, read `references/figure-reuse-and-disclosure.md`.
- For source-backed best practices used to create this skill, read `references/sources.md` only when citations or rationale are needed.
