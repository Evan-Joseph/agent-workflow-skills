# Paper Story Mode

Use this reference to explain a paper as a coherent proposition rather than a section-by-section summary.

## Goal

Make the paper legible to a technically capable reader:

```text
problem pressure -> old route -> turning point -> method mechanism -> evidence -> portable takeaway
```

This is not peer review. It can feed review, writing, or teaching, but it should not invent acceptance judgments.

## Seven Beats

1. **Actor**: who or what is under pressure: a model, system, user, dataset, evaluator, or research community.
2. **Bind**: the concrete difficulty or trade-off that makes the problem matter.
3. **Old route**: what prior work or common practice tried, and why it was insufficient.
4. **Proposition**: the paper's bold claim or bet in one sentence.
5. **Mechanism**: how the method makes the proposition plausible.
6. **Evidence**: the smallest set of results that actually supports the proposition.
7. **Takeaway**: the new way of seeing that survives outside this one paper.

## Procedure

1. Resolve metadata: title, authors, year, venue/source, URL, DOI/arXiv ID.
2. Read primary text:
   - abstract for claim and result;
   - introduction for pressure and old route;
   - method for mechanism;
   - experiments for evidence and base rate;
   - limitations/discussion for boundary.
3. Extract a base-rate ruler where possible:
   - previous baseline level;
   - typical improvement scale;
   - dataset/task scope;
   - cost, data, or evaluation constraints.
4. Write the proposition as a falsifiable sentence, not a topic label.
5. Choose only 2-4 evidence points. More points usually blur the story.
6. State boundary conditions and what evidence would weaken the proposition.

## Output Shape

```markdown
# Paper Story: <title>

## Speed Card
- One sentence:
- Big idea:
- Remember these three:

## Story
1. Actor:
2. Bind:
3. Old route:
4. Proposition:
5. Mechanism:
6. Evidence:
7. Takeaway:

## Evidence And Boundaries
| point | source locator | supports | boundary |
|---|---|---|---|

## What To Check Next
- citation or lineage:
- experiment or reproduction:
- claim to soften:
```

## Guardrails

- Do not replace paper reading with a metaphor.
- Do not hide weak evidence behind narrative flow.
- Do not overstate novelty; if lineage is unclear, route to Paper Lineage Mode.
- Keep exact numbers, datasets, baselines, and limitations attached to source locators.
