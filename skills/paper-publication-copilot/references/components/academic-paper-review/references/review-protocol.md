# Academic Paper Review Protocol

Use this reference for full review, quick review, desk-reject risk, and editorial decision letters.

## Intake

Record these fields before judging:

- Manuscript type: empirical, theoretical, literature review, meta-analysis, case study, policy analysis, thesis chapter, or proposal.
- Target venue or audience, if provided.
- Field and method family.
- Available material: full text, abstract only, figures/tables, supplementary files, code/data, prior reviews.
- Review mode and output depth.

If the target venue or article type materially changes the standard and the user did not provide it, ask one concise question or proceed with a general journal-style review and label the assumption.

## Reviewer Perspectives

Use separate perspectives before synthesis:

- `editor`: fit, contribution, novelty, reader value, desk-reject risk.
- `methodology`: design, validity, statistics, data, reproducibility.
- `domain`: literature coverage, theory, missing baselines, citation positioning.
- `impact`: implications, transferability, ethics, policy or practice relevance.
- `devil`: strongest counterargument, overclaim, alternative explanation, hidden assumption.

The same Codex instance can write all perspectives, but it must keep the findings separate before producing the final decision.

## Review Dimensions

Score only when useful. Use 0-100 as an ordinal signal:

- Originality: new question, theory, evidence, method, or useful combination.
- Methodological rigor: design matches the research question; threats to validity are handled.
- Evidence sufficiency: claims are supported by data, citations, and analysis.
- Argument coherence: problem, gap, method, finding, and implication connect.
- Writing quality: academic prose, terminology, structure, table/figure readability.
- Literature integration: current, relevant, critically synthesized sources.
- Significance: why the result matters for theory, method, practice, or policy.

Treat scores as rough review instruments. Do not present them as venue acceptance probabilities.

## Decision Mapping

- `Accept`: rare. No material validity issue; only minor polishing remains.
- `Minor Revision`: contribution and methods are sound; fixes are localized.
- `Major Revision`: plausible contribution, but required evidence, method, framing, or structure changes remain.
- `Reject`: core claim, method, evidence, or novelty is insufficient for the claimed venue.
- `Desk Reject Risk`: scope, fit, novelty, ethics, formatting, or basic completeness would likely fail before full review.

Any fatal method flaw, fabricated or unverifiable core evidence, or contradiction between data and conclusion should block `Accept`.

## Findings Format

Each material finding should include:

- `Severity`: Critical / Major / Minor / Editorial.
- `Location`: section, page, paragraph, line, figure, table, or quote.
- `Issue`: one direct sentence.
- `Why it matters`: effect on validity, contribution, readability, or venue fit.
- `Required action`: what must change or what evidence is needed.
- `Confidence`: high / medium / low, especially when only partial text is available.

## Output Shape

```markdown
# Academic Review

## Editorial Decision
<decision and one-paragraph rationale>

## Main Findings
1. [Major] ...

## Reviewer Reports
### Editor
...
### Methodology
...
### Domain and Literature
...
### Impact and Ethics
...
### Devil's Advocate
...

## Revision Roadmap
| Priority | Required action | Evidence needed | Location |
|---|---|---|---|

## Residual Risk
<unchecked sources, missing appendices, unavailable data, uncertain venue assumptions>
```

## Attribution

This local protocol selectively adapts review-workflow ideas from Imbad0202 Academic Research Skills, without vendoring its full Claude/Codex runtime.
