# Paper Lineage Mode

Use this reference to trace how a research problem evolved around a target paper.

## Goal

Build a source-backed problem lineage:

```text
earlier problem framing -> baseline method -> target shift -> later response
```

The unit is the problem and method shift, not a raw citation list.

## Procedure

1. Resolve the target paper.
   - Use arXiv ID, DOI, title, PDF metadata, or Semantic Scholar search.
   - Record title, authors, year, venue, URL, and paper id.

2. Read the primary surface.
   - Abstract: central claim and result.
   - Introduction: problem pressure and claimed gap.
   - Related work: named predecessors and baselines.
   - Limitations or discussion: boundary of the claim.

3. Collect candidates.
   - Backward: `semantic_scholar_refs.py <paper_id> --direction backward --limit 30`
   - Forward: `semantic_scholar_refs.py <paper_id> --direction forward --limit 30`
   - Add arXiv or publisher pages when metadata is thin.

4. Classify each relationship.
   - `baseline`: the target directly compares against it.
   - `criticized`: the target names a limitation or failure.
   - `extended`: the target builds a mechanism on top of it.
   - `same-problem`: related but no direct dependency is proven.
   - `follow-up`: later work cites and modifies the target.

5. Choose a focused chain.
   - Prefer 3-7 nodes.
   - Keep only papers that move the problem framing or method.
   - Do not chase broad survey branches unless the user asks for a map.

6. Write the evolution.
   - For each paper: problem seen, method tried, limitation exposed, next pressure created.
   - Explain why the next paper had to exist.
   - Put evidence source after each key relationship.

## Output Shape

```markdown
# Paper Lineage: <target>

## Target
- <title>, <authors>, <year>, <venue/source>
- Core claim: ...

## Lineage Map
<ASCII or bullet chain with relationship labels>

## Problem Evolution
1. <paper>: saw ...
2. <paper>: changed ...

## Forward Edge
<later papers and how they respond>

## Uncertain Links
- <paper>: relationship is inferred because ...

## Sources Checked
- <paper/url/metadata source>
```

## Guardrails

- Citation means "referenced", not "caused". State the stronger relationship only when the paper text supports it.
- If only metadata is available, say `metadata-only`.
- If a paper is famous but not in the relevant chain, leave it out or put it under context.
- Prefer exact dates and venues when evaluating "latest" or "follow-up" claims.
