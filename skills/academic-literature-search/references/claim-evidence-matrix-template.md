# Claim Evidence Matrix

Use this template when a paper, report, rebuttal, related-work section, or submission checklist needs claim-source alignment.

## Table

| claim_id | manuscript_location | claim_text | cited_source | source_type | exact_locator | source_read_status | support_status | citation_risk | required_action |
|---|---|---|---|---|---|---|---|---|---|

## Field Guide

- `claim_id`: stable identifier such as `C01`.
- `manuscript_location`: section, paragraph, line, page, figure, table, or caption.
- `claim_text`: exact claim sentence or concise paraphrase.
- `cited_source`: BibTeX key, DOI, arXiv ID, URL, or local file.
- `source_type`: peer-reviewed, preprint, official docs, benchmark page, code repo, dataset card, blog, metadata only.
- `exact_locator`: page, section, theorem, table, figure, paragraph, quote locator, or API field.
- `source_read_status`: `full_text_read`, `abstract_only`, `metadata_only`, `unavailable`, `not_checked`.
- `support_status`: see below.
- `citation_risk`: hallucinated reference, wrong venue/year, no locator, source mismatch, overclaim, outdated, weak source, paywalled.
- `required_action`: verify, replace citation, soften claim, add locator, add source, remove claim, move to limitation.

## Support Status

- `SUPPORTED`: the cited source directly supports the claim at the stated locator.
- `PARTIALLY_SUPPORTED`: the source supports part of the claim or a narrower version.
- `OVERSTATED`: the source is relevant but the manuscript claim is stronger than the evidence.
- `CONTRADICTED`: the source conflicts with the claim.
- `NOT_ADDRESSED`: the source does not address the claim.
- `UNVERIFIED`: source text or reliable metadata was not checked.

## Rules

- Reference existence is not claim support.
- Metadata-level checks can verify existence, title, authors, year, DOI, or venue; they cannot verify nuanced claim support.
- Prefer primary paper text, official dataset or benchmark documentation, and publisher/arXiv pages over secondary summaries.
- When source access is limited, mark the limit explicitly instead of inferring support.
- For broad claims, require either multiple sources or a narrower claim.
