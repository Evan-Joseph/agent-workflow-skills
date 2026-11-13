# PPT And Chart Rebuild Rules

## General

Use AI-generated images as layout drafts. Rebuild anything requiring precision.

Final editable packs should make each semantically distinct element independently selectable:

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

Avoid flattening several dataset images or labels into one bitmap. A single PPT slide may contain many objects.

## Source Images

- Preserve native aspect ratio.
- Do not stretch.
- Crop only if the paper's figure brief says so.
- Keep each source image as a separate PPT picture object.
- Keep a source-material page when useful: place raw candidate images and captions as independent objects for manual reuse.

## Numerical Charts

For charts, prefer this hierarchy:

1. Generate exact chart from CSV using matplotlib or another deterministic plotting tool.
2. Import PDF/SVG/EMF as vector if the local workflow supports it.
3. Add labels, annotations, and highlight markers as PPT native objects.
4. Use Image2 draft only to guide layout, palette, and visual density.

Never use image-model-rendered bars, lines, ticks, or numeric labels as final values.

## Text

- Put long text in native PPT text boxes or LaTeX, not in generated raster art.
- Keep in-image text short.
- Use caption for full figure title and explanatory prose.
- Keep code-like fields in monospace if project style allows.

## Figure-Type Specific Rules

### Pipeline Figure

- Keep stages left-to-right unless the target venue or paper style suggests another layout.
- Use real data examples only when verified.
- Do not invent model modules.
- Distinguish data construction from model architecture and inference.

### Dataset/Sample Figure

- Use real source images.
- Keep each image separate.
- Place image labels and task captions as native text.
- Include a material page if the user needs to manually copy objects.

### Error/Robustness Figure

- Keep categorical labels exactly as in the paper.
- Group bars consistently.
- Use the same model ordering as tables.
- Rebuild from CSV.
- Do not add categories with no analytical role.

### Training Dynamics Figure

- Rebuild all lines from CSV.
- Do not extrapolate missing checkpoints.
- Mark matched checkpoints explicitly if the paper relies on them.
- Use line style and marker shape to support grayscale reading.

## Final Export

- For LaTeX submission, prefer vector PDF when available.
- For preview or external review, export PNG at sufficient resolution.
- After replacing figures in LaTeX, compile and check page budget, references, overfull boxes, and caption consistency.
