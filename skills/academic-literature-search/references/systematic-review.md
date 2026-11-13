# Systematic Review Mode

Use this reference for systematic reviews, PRISMA-style evidence synthesis, meta-analysis preparation, and reproducible literature review protocols.

## Boundary

Only call a deliverable a `systematic review` when the search, screening, inclusion/exclusion criteria, and exclusion reasons are documented. If time, database coverage, or screening is incomplete, call it `rapid review`, `scoping review`, or `literature scan`.

## Workflow

1. Define the review question.
   - Use PICOS for intervention/effect questions.
   - Use SPIDER or equivalent for qualitative questions.
   - State scope boundaries: population, geography, time range, language, publication type, and study design.

2. Write the protocol before searching.
   - Review question.
   - Eligibility criteria.
   - Databases and search strings.
   - Screening process.
   - Data extraction fields.
   - Risk-of-bias approach.
   - Synthesis plan.

3. Search and log every source.
   - Use at least two appropriate databases for systematic coverage.
   - Record exact search string, date, database, filters, and hit count.
   - Keep a separate list for backward/forward citation chasing.

4. Screen in two passes.
   - Title/abstract screening.
   - Full-text screening.
   - Record exclusion reasons at full-text stage.

5. Extract structured data.
   - Bibliographic metadata.
   - Study design, population, sample size, context.
   - Intervention/exposure/comparator/outcome or qualitative equivalent.
   - Key findings and limitations.
   - Risk-of-bias notes.

6. Synthesize.
   - Pool quantitatively only when measures, populations, and designs are compatible.
   - If not pooling, use structured narrative synthesis.
   - Separate effect direction, effect size, evidence certainty, and bias risk.

## Minimum Evidence Log

```markdown
## Search Log
| Date | Database | Query | Filters | Hits | Notes |
|---|---|---|---|---|---|

## Screening Log
| Stage | Included | Excluded | Exclusion reasons |
|---|---:|---:|---|

## Included Studies
| ID | Citation | Design | Population | Outcome | Key result | Bias risk |
|---|---|---|---|---|---|---|
```

## PRISMA Counts

Track:

- Records identified.
- Duplicates removed.
- Records screened.
- Records excluded.
- Reports sought.
- Reports not retrieved.
- Full texts assessed.
- Full texts excluded with reasons.
- Studies included in review.
- Studies included in quantitative synthesis, if any.

## Risk-of-Bias Selection

- RCTs: use RoB 2 concepts.
- Non-randomized intervention studies: use ROBINS-I concepts.
- Diagnostic studies: use QUADAS-2 concepts.
- Qualitative studies: use field-appropriate credibility, transferability, dependability, confirmability checks.
- Mixed corpora: do not force one bias tool across all study designs.

## Output Shape

```markdown
# Systematic Review Protocol or Report

## Review Question
...

## Eligibility Criteria
...

## Search Strategy
...

## Screening Flow
...

## Included Study Matrix
...

## Synthesis
...

## Bias and Certainty
...

## Limits of This Review
...
```

## Attribution

This local reference selectively adapts public systematic-review workflow ideas from Imbad0202 Academic Research Skills and keeps them as a lightweight Codex skill reference.
