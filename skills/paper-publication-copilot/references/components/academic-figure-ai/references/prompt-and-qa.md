# Prompt And QA Reference

## Prompt Skeleton

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
signature_motif:
reference_images:
  - path:
    role: layout | style | content | numeric_anchor
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
  gutters:
  margins:
  legend:
  caption_policy:
style:
  background:
  palette:
  fonts:
  line_weight:
  chart_style:
negative_constraints:
rebuild_plan:
fact_check:
reject_if:
```

## Prompt Writing Rules

- Use a structured prompt, not a prose request.
- State the intended use: "publication-quality two-column academic figure for a CS/AI conference paper".
- State the visual direction before the layout: editorial-schematic, diagnostic dashboard, split-panel training analysis, or dataset-example strip.
- State the reviewer takeaway in one sentence. Every visual choice should serve that sentence.
- State exact panel count and panel order.
- State the reading path and focal element. Avoid all boxes having equal salience.
- State which text is allowed inside the image.
- State which text must not appear inside the image.
- State source image aspect-ratio preservation.
- State whether Image2 should draw actual charts or only make layout drafts.
- For charts, include exact values only as anchors, then say values will be rebuilt from CSV/PPT.
- For field names, code snippets, and data schema, keep strings short and require native-text rebuild.
- Use a small number of well-assigned references. For each reference, say "transfer layout rhythm only", "transfer chart grammar only", or "transfer source content only".
- Add `reject_if` criteria so bad drafts are discarded early instead of patched by hand.

## Good Defaults For CS/AI Papers

- Wide two-column figure unless the paper explicitly needs single-column.
- White background.
- Light grey rounded panel containers only when they serve grouping; do not make every figure a row of generic cards.
- Low-saturation palette.
- Times New Roman for prose labels.
- Consolas or monospace for code-like strings.
- Panel labels `(a)`, `(b)`, `(c)` when there are true subpanels.
- Captions own figure titles.
- Under-figure or in-panel takeaway limited to one short sentence when needed.
- One restrained signature motif per figure, such as a highlighted target document, a 5k checkpoint rule, or a diagnostic spine.

## Top-Tier Visual Direction Patterns

### Editorial-Schematic Pipeline

Use for method/data-construction figures.

- Make the contribution object visually dominant.
- Use a non-uniform flow: source evidence cards feed into a larger target artifact.
- Prefer one highlighted target card over four equal workflow boxes.
- Use real data thumbnails as evidence, but keep them secondary.
- Keep literal target text short and plan native-text rebuild.

### Compact Diagnostic Dashboard

Use for error analysis and robustness figures.

- Treat charts as evidence panels, not decorative screenshots.
- Keep a shared legend, consistent ordering, and one restrained annotation layer.
- If one category dominates, use an explicit broken-axis or inset plan; do not let the model invent scaling.
- Put the analytical contrast near the data, not as a big title.

### Split-Panel Training Analysis

Use for checkpoint and learning-curve figures.

- Build a paired reading: left panel answers "which checkpoint", right panel answers "what trade-off".
- Use one shared checkpoint marker across panels.
- Use line style and marker shape as semantic encodings.
- Avoid extra annotations that compete with the curves.

## Negative Prompt Defaults

```text
people, human, hands, face, avatar, mascot, cartoon, anime, comic, speech bubble,
unnecessary robot, robotic arm, logo, watermark, venue banner, old submission name,
3D chart, isometric chart, drop shadow, gradient mesh, glow, neon, lens flare,
fabricated number, invented category, invented architecture block,
large in-image figure title, Figure N headline, flattened contact sheet,
stretched source image, square aspect ratio when wide is requested
```

Add domain-specific negatives:

- For data-construction pipelines: ban policy/planner boxes, model-forward paths, closed-loop arrows, execution loops, JSON action objects if the training target is natural language.
- For diagnostic charts: ban extra categories, autoscaled axes that hide the intended comparison, 3D bars, decorative legends.
- For training dynamics: ban extrapolated curves, invented checkpoints, invented dimensions.

## QA Rubric

### Factuality

- Every number traces to CSV/log/table.
- Every source image traces to dataset or confirmed asset.
- Every schema/code string matches the paper.
- No invented method module or task stage appears.

### Paper Fit

- The figure supports the exact local paragraph.
- The figure does not over-explain content already in caption.
- The figure avoids old venue names, internal prompt artifacts, and tool names.
- The style matches the rest of the paper.

### Readability

- Text remains readable at final displayed width.
- Legend and labels do not crowd plot area.
- Grayscale printing still distinguishes groups.
- Axis labels, units, and tick marks are complete for quantitative charts.

### Editability

- Source photos are separate picture objects.
- Text labels are native text where possible.
- Arrows and connectors are separate shapes.
- Chart values can be regenerated or edited without repainting the whole figure.

### Handoff

- Include final prompt.
- Include reference image list with roles.
- Include data source list.
- Include rebuild object list.
- Include known manual-proofing items.
