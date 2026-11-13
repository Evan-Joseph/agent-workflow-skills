# Figure Reuse And Disclosure

Use this reference when a paper figure may be reused across venues, generated or edited by AI, rebuilt from data, or used to support a claim.

## Figure Register Fields

| figure_id | manuscript_location | venue_usage | source_asset | editable_source | data_source | ai_generated_or_edited | reuse_risk | disclosure_needed | caption_claim | fidelity_status | action |
|---|---|---|---|---|---|---|---|---|---|---|---|

## Figure Classes

- `data_chart`: bars, lines, scatter, heatmap, metrics, confidence intervals. Must be rebuilt from data.
- `schematic`: pipeline, architecture, conceptual overview. Must match method text and avoid invented modules.
- `sample_grid`: dataset images, screenshots, qualitative outputs. Must preserve source identity and aspect ratio.
- `diagnostic_mixed`: combines charts, examples, annotations, and method objects. Split factual and illustrative parts.
- `ai_layout_draft`: image-model output used only for composition. Final facts, labels, and numbers must be rebuilt.

## Reuse Risk Levels

- `none`: new figure, no prior venue exposure.
- `low`: same underlying data but materially new design, caption, and claim.
- `medium`: recognizable reuse of layout, panels, or source images across related submissions.
- `high`: same or near-identical figure PDF/PNG/PPT used in another active or submitted venue.
- `blocked`: reuse likely violates venue, anonymity, copyright, or simultaneous-submission constraints.

## Fidelity Status

- `DATA_BACKED`: all values and labels trace to data or source files.
- `SCHEMATIC_ONLY`: explanatory schematic, no numeric factual claim.
- `PARTIALLY_SUPPORTED`: some panels or caption claims lack source support.
- `TEXT_NEEDS_SOFTENING`: figure supports a narrower takeaway than the caption or body claims.
- `SOURCE_MISSING`: source image/data/editable file missing.
- `REBUILD_REQUIRED`: final figure cannot be trusted as-is.

## Checks

1. Does the figure's reviewer takeaway match the paragraph that introduces it?
2. Are all numeric values, axis labels, legends, and categories deterministic and source-backed?
3. Are source images unstretched, unmerged, and correctly attributed?
4. Does the figure contain old venue names, old paper IDs, hidden watermarks, or old task labels?
5. Has this figure or its source asset appeared in another active submission?
6. Does AI generation or AI editing require disclosure under the target venue or publisher policy?
7. Can the figure be edited if a reviewer or editor requests changes?

## Disclosure Handling

Do not write final disclosure from memory. First check current venue or publisher policy. Record whether AI was used for:

- layout ideation,
- raster generation,
- image editing,
- text rewriting in captions,
- chart generation code,
- final visual content.

If AI output contributed to final factual content, require stronger manual verification.
