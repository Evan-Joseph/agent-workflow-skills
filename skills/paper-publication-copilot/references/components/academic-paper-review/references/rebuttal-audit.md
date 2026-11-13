# Rebuttal Audit

Use this reference when the user has an existing rebuttal draft, response-to-reviewers letter, or author response and wants it checked against reviewer comments.

## Boundary

This mode audits the response letter. It does not certify that the revised manuscript passed final integrity checks. If manuscript verification is needed, switch to `re-review`.

## Required Inputs

- Original reviewer comments.
- Existing rebuttal or response draft.
- Revised manuscript or change log, optional but useful.

If there is no response draft, produce a revision roadmap instead of claiming to audit a rebuttal.

## Audit Questions

For each reviewer comment:

1. Is there a direct response?
2. Does the response address the core concern or deflect to a nearby issue?
3. Does it state a concrete manuscript change, location, or rationale?
4. If disagreeing, does it provide evidence rather than tone?
5. Does it overpromise experiments, analyses, or citations that are not shown elsewhere?
6. Is the tone professional, concise, and non-defensive?
7. Are all cross-references, page numbers, figure/table labels, and section names plausible and consistent?

## Response Status

- `covered`: directly answers the comment.
- `partially-covered`: responds to part of the comment.
- `missing`: no response found.
- `deflecting`: answers a different issue.
- `unsupported`: makes a claim without evidence or location.
- `overpromised`: claims a change or experiment that is not documented.
- `tone-risk`: wording is defensive, dismissive, vague, or excessive.

## Output Shape

```markdown
# Rebuttal Audit

## Summary
<direct conclusion: ready / needs targeted repair / structurally incomplete>

## Coverage Matrix
| Comment ID | Reviewer concern | Response status | Evidence/location | Risk | Required fix |
|---|---|---|---|---|---|

## High-Risk Passages
> <short excerpt>

Issue: ...
Revision direction: ...

## Missing or Weak Commitments
<list concrete promises that need manuscript evidence, rationale, or removal>
```

## Rules

- Preserve the author's position; do not force agreement with every reviewer.
- A valid disagreement needs a clear reason and evidence.
- Avoid generating a new full response unless the user explicitly asks after the audit.
- Keep audit findings separate from manuscript edit suggestions.
