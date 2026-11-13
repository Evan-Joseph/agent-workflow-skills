# Provenance-Lite Record

Use this lightweight record for long research tasks, literature reviews, citation audits, and handoffs to writing. It is inspired by the ARS Material Passport pattern, but deliberately smaller.

## Purpose

Keep enough provenance to answer:

- What question was investigated?
- Which sources were searched?
- Which source text was actually read?
- Which claims are verified, partial, or still unchecked?
- Which assumptions remain?

## Record Shape

```markdown
# Research Provenance

## Task
- User goal:
- Working question:
- Date:
- Scope:

## Search Log
| Source | Query | Date | Filters | Hits | Notes |
|---|---|---|---|---:|---|

## Source Register
| ID | Citation / URL | Type | Access level | Status | Notes |
|---|---|---|---|---|---|

## Evidence Map
| Claim / question | Source ID | Passage / locator | Support status | Notes |
|---|---|---|---|---|

## Unresolved Items
| Item | Why unresolved | Next check |
|---|---|---|
```

## Access Levels

- `full-text`: PDF, HTML full text, PMC, arXiv, or official full text read.
- `abstract`: abstract only.
- `metadata`: title/authors/year/venue/DOI only.
- `secondary`: citation or summary from another source.
- `unavailable`: not retrieved.

## Support Status

- `verified`: checked against source text.
- `partial`: source supports only part of the claim.
- `inferred`: plausible relation, but not directly stated.
- `metadata-only`: source exists; claim support not checked.
- `unchecked`: not yet verified.
- `conflicting`: sources disagree.

## Rules

- Prefer stable identifiers: DOI, arXiv ID, PMID, PMCID, Semantic Scholar ID.
- Keep exact search dates for dynamic databases.
- Separate evidence from interpretation.
- Record failed retrievals; they matter for future audit.
- Do not use this record as proof of correctness. It documents what was checked.
