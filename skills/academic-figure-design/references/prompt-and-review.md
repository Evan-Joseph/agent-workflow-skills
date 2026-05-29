# Prompt and Review Reference

## Good defaults

- Wide two-column canvas unless the paper needs a single-column figure.
- White or very light background.
- Low-saturation palette.
- Sparse labels.
- Clear reading path.
- One focal region for the paper's contribution.
- Captions own full figure titles.
- Use panel labels only when the figure has real subpanels.

Avoid generic rows of equal boxes. A strong paper figure usually has hierarchy: one main claim, supporting evidence, and a controlled amount of context.

## Visual directions

### Editorial schematic

Use for method or data-construction figures.

- Make the contribution object visually dominant.
- Let source evidence feed into a larger target artifact.
- Keep literal text short.
- Rebuild all labels later.

### Diagnostic dashboard

Use for error analysis, robustness, or ablation figures.

- Treat charts as evidence, not decoration.
- Use shared legends and consistent ordering.
- Place analytical contrast near the data.
- Rebuild all chart geometry from source data.

### Split-panel training analysis

Use for learning curves and checkpoint comparisons.

- Pair the panels around one question.
- Use a shared checkpoint marker when relevant.
- Use line style and markers for grayscale readability.

## Negative constraints

Start with these and add task-specific ones:

```text
people, faces, hands, mascot, cartoon, anime, speech bubble, unnecessary robot,
logo, watermark, venue banner, old submission name, 3D chart, isometric chart,
drop shadow, glow, neon, lens flare, fabricated number, invented category,
invented architecture block, large in-image title, flattened contact sheet,
stretched source image, garbled text
```

## Review checklist

### Factuality

- Every number traces to a CSV, log, table, or manuscript source.
- Every source image has a known origin.
- Every schema, field, and code-like string matches the paper.
- No invented method module appears.

### Paper fit

- The figure answers the paragraph that calls it.
- The figure does not over-explain content that belongs in the caption.
- The style fits the rest of the manuscript.

### Readability

- Text remains readable at final displayed width.
- Labels and legends do not crowd data.
- Important groups remain distinguishable in grayscale.
- Axes, units, legends, and captions are complete.

### Editability

- Source photos are separate objects.
- Text labels are editable where possible.
- Arrows and connectors are separate shapes.
- Charts can be regenerated without repainting the entire figure.

### Handoff

Include:

- final prompt
- reference image list with roles
- data source list
- rebuild object list
- known manual-proofing items

