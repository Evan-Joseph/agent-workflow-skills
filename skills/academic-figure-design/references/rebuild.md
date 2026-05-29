# Rebuild Rules

Use generated images as layout drafts. Rebuild anything that needs precision.

## Editable object list

Final editable packs should keep each semantic object separate:

- source image
- panel background
- panel title
- panel label
- arrow
- text card
- legend swatch
- legend label
- chart panel
- annotation
- callout line

Avoid flattening several dataset images or labels into one bitmap unless the final figure is intentionally a contact sheet.

## Source images

- Preserve native aspect ratio.
- Do not stretch.
- Crop only when the figure brief says so.
- Keep each source image as a separate object.
- Keep a material page when useful: raw candidate images, captions, and notes as separate objects.

## Numerical charts

Prefer this order:

1. Generate the exact chart from CSV/log/table data using a deterministic plotting tool.
2. Import the chart as vector when the workflow supports it.
3. Add labels, annotations, and highlight markers as editable objects.
4. Use the generated draft only for layout, palette, and density.

Never use model-rendered bars, lines, ticks, or numeric labels as final values.

## Text

- Put long labels in native text boxes or LaTeX.
- Keep in-image generated text short.
- Let the caption carry the full figure title and explanatory prose.
- Use monospace only for code-like fields.

## Figure-specific notes

### Pipeline figure

- Keep data construction, model architecture, and inference visually distinct.
- Use real examples only when verified.
- Do not invent modules or stages.

### Dataset or sample figure

- Use real source images.
- Keep each image separate.
- Add labels and task captions as native text.

### Error or robustness figure

- Keep category labels exactly as in the paper.
- Keep model and method ordering consistent with tables.
- Use redundant encodings such as color plus marker or line style.

### Training dynamics figure

- Rebuild every line from data.
- Do not extrapolate missing checkpoints.
- Mark matched checkpoints explicitly if the paper relies on them.

## Final export

- Prefer vector PDF/SVG for plots and diagrams.
- Export PNG previews only for review or sharing.
- After replacing the figure in a manuscript, check captions, references, page budget, overfull boxes, and final text size.

