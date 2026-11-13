# Citation Integrity Mode

Use this reference to verify whether references exist and whether cited sources support the claims attached to them.

## Two Different Questions

1. `Reference existence`: Does the source exist, and is the metadata correct?
2. `Claim support`: Does that source actually support the sentence or paragraph citing it?

Do not collapse these checks. A real paper can still be used to support a claim it never made.

## Workflow

1. Parse the citation.
   - In-text citation or footnote.
   - Reference-list entry.
   - DOI, arXiv ID, PubMed ID, Semantic Scholar ID, URL, title, authors, year.

2. Verify existence.
   - Prefer DOI resolver, publisher page, arXiv, PubMed/PMC, Crossref, OpenAlex, Semantic Scholar, or official repository.
   - Record metadata mismatches: title, author, year, venue, DOI, version.

3. Locate cited context.
   - Exact claim sentence.
   - Surrounding paragraph.
   - Locator: page, section, table, figure, quote, theorem, or appendix.
   - Whether the citation is used as background, method evidence, empirical result, or direct support.

4. Retrieve source text.
   - Full text or PDF is strongest.
   - Abstract-only is limited.
   - Metadata-only cannot establish claim support.
   - Paywalled or unavailable sources remain `unverified`, not `supported`.

5. Judge support.

Use these verdicts:

- `SUPPORTED`: source directly supports the cited claim.
- `PARTIAL`: source supports part of a compound claim but not all of it.
- `AMBIGUOUS`: source is related, but support is unclear.
- `UNSUPPORTED`: source does not support the claim.
- `CONTRADICTED`: source says the opposite or materially weakens the claim.
- `METADATA_ONLY`: reference exists, but claim support was not checked against source text.
- `RETRIEVAL_FAILED`: source text could not be obtained.

## Deterministic Helper

Use `scripts/citation_integrity_audit.py` for a first pass when you have a DOI, title, raw reference entry, claim, or extracted source text.

Examples:

```bash
python3 $HOME/.agents/skills/academic-literature-search/scripts/citation_integrity_audit.py --doi "10.1038/nature14236" --format markdown
python3 $HOME/.agents/skills/academic-literature-search/scripts/citation_integrity_audit.py --reference "raw reference entry" --claim "exact cited claim" --source-text source.txt --format json
```

What it can do:

- Verify DOI metadata through Crossref and doi.org.
- Search Crossref candidates from a title or raw reference.
- Search Semantic Scholar candidates when `--semantic-scholar` is explicitly set.
- Flag obvious title metadata mismatch.
- Rank source-text passages by lexical overlap with the cited claim.

What it cannot do:

- Prove claim support from metadata alone.
- Replace reading the relevant source passage.
- Decide final `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, or `CONTRADICTED` labels automatically.

When the script emits `CLAIM_REVIEW_NEEDED`, inspect the candidate passages yourself and then assign one of the citation-integrity verdicts above.

## Output Shape

```markdown
# Citation Integrity Audit

## Scope
Audited citations: <n>
Full-text checked: <n>
Metadata-only: <n>
Retrieval failed: <n>

## Findings
| Citation | Claim | Source checked | Verdict | Evidence | Fix |
|---|---|---|---|---|---|

## Unverifiable Items
| Citation | Reason | Next step |
|---|---|---|
```

## Red Flags

- Citation exists, but year/title/authors do not match the reference list.
- Review paper cited for a specific experimental result that appears only in a primary paper.
- Source supports a narrower condition than the manuscript claims.
- Citation cluster hides which source supports which clause.
- Negative or null results are cited as positive support.
- Author response says a citation was added, but no manuscript location is provided.

## Guardrails

- Quote only short source fragments when needed; otherwise paraphrase.
- Mark source access level: full text, abstract, metadata, inaccessible.
- For current guidelines, clinical claims, laws, or venue policies, verify live primary sources.
- Do not invent replacement citations. Suggest search queries or criteria when replacements are needed.
