---
name: academic-figure-design
description: "Plan AI-assisted academic figures for CS, AI, and data-driven papers. Use when turning a paper claim, caption, data source, or rough sketch into an image-generation prompt plus an editable rebuild plan for charts, labels, panels, and source images."
metadata:
  short-description: "Plan academic figures with editable rebuilds"
  category: "research-design"
  version: "1.0.0"
---

# Academic Figure Design

Use this skill when a paper figure needs both visual direction and factual control.

Image models are useful for composition, panel rhythm, and style exploration. They are not a source of truth for chart values, labels, axes, legends, dataset examples, architecture names, or paper claims.

## Core rule

Split every serious figure into three layers:

1. **Draft image**: composition, hierarchy, visual rhythm, and rough panel layout.
2. **Ground truth**: paper text, captions, CSVs, logs, source images, tables, and verified screenshots.
3. **Editable rebuild**: final labels, numeric plots, legends, arrows, crops, and export-ready vector or slide objects.

Do not ship a raster draft as the final figure when the figure contains important text, numbers, charts, or source images.

## Workflow

### 1. Read the figure context

- Find the paragraph that introduces the figure.
- Read the current caption or figure TODO.
- Identify the single reviewer takeaway.
- Check venue constraints: single-column or two-column width, final displayed size, file format, font size, and whether the caption carries the title.
- List the exact data sources, source images, or logs that must control the figure.

### 2. Classify the figure

- **Pipeline or method figure**: use image generation for the draft; rebuild labels and key objects.
- **Dataset or sample figure**: keep source images as independent objects with preserved aspect ratio.
- **Numerical chart**: generate the final chart from data; use image generation only for layout ideas.
- **Diagnostic or error figure**: split visual panels and chart panels; rebuild chart values deterministically.
- **Dense text or table figure**: use native text, LaTeX, or slide/table objects instead of generated text.

### 3. Gather references

Use 2 to 5 references. More usually weakens control.

For each reference, state one role:

- layout
- style
- content
- chart grammar
- anti-example

Also state what must not transfer. A style reference should not donate unrelated objects, colors, logos, people, or labels.

### 4. Write a prompt package

Use labeled sections or YAML:

```yaml
figure_id:
target_canvas:
aspect_ratio:
figure_type:
paper_claim:
reviewer_takeaway:
visual_direction:
reading_path:
hierarchy:
reference_images:
  - path:
    role:
    allowed_use:
    forbidden_use:
content_anchors:
  source_images:
  exact_strings:
  exact_numbers:
  data_sources:
layout:
  panel_count:
  panel_order:
  margins:
  gutters:
  legend:
style:
  background:
  palette:
  typography:
  line_weight:
negative_constraints:
rebuild_plan:
fact_check:
reject_if:
```

Keep literal in-image text short and quoted. If the model may misspell it, plan to rebuild it as native text.

### 5. Rebuild precisely

For final assets:

- Rebuild numeric charts from CSV, logs, or tables.
- Keep source images as separate picture objects.
- Keep text labels as native text when possible.
- Keep arrows, callouts, legends, and panel labels editable.
- Export vector PDF/SVG for LaTeX when the workflow supports it.
- Compile or render the target paper/page and check final displayed size.

Read `references/rebuild.md` when the task reaches slide, vector, or chart reconstruction.

### 6. Review before handoff

Check:

- Every number traces to a source.
- Every source image is verified and keeps its intended crop/aspect ratio.
- The figure supports the local paragraph, not a broader story the paper does not claim.
- Text remains readable at final displayed size.
- Grayscale printing still distinguishes important groups.
- The figure can be edited without repainting the whole bitmap.

Use `references/prompt-and-review.md` for prompt patterns and review checks.

