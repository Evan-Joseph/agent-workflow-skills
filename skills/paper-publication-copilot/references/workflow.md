# Paper Publication Workflow

## Stage Map

| Stage | Goal | Primary artifacts | Specialist skills |
|---|---|---|---|
| Intake | Understand current paper state and workspace boundaries | `status.md` | `paper-publication-copilot` |
| Evidence | Align claims, citations, figures, and experiments | `claim_evidence_matrix.md`, `literature_provenance.md`, `experiment_audit_matrix.md`, `figure_asset_register.md` | `academic-literature-search`, `data-analysis`, `academic-figure-ai` |
| Review | Identify reviewer-visible risks | `review_risk_register.md` | `academic-paper-review` |
| Revision | Convert risks into scoped actions and preserve academic semantics | `revision_queue.md`, updated claim/terminology checks | `document-crafting`, `shuorenhua` academic mode, specialist skills |
| Verification | Check revised claims and formatting | updated audit artifacts, rendered PDF | `academic-paper-review`, `pdf`, `latex:latex-compile` |
| Submission | Confirm venue and human-only fields | `submission_checklist.md` | browser/venue tools only after explicit instruction |

## Eight Artifacts

### `status.md`

Record venue, track, deadline, timezone, anonymity, page limits, current manuscript path, current PDF path, compile command, submission state, paper ID, author metadata state, AI disclosure state, and one-paper-at-a-time constraints.

For dynamic facts, use official current sources. Mark stale local notes as stale instead of merging them silently.

### `claim_evidence_matrix.md`

Map each high-impact claim to manuscript location, evidence source, exact locator, support status, and action. Include abstract, introduction, contribution bullets, method claims, result interpretations, limitations, and conclusion claims.

### `literature_provenance.md`

Record search dates, sources, queries, inclusion/exclusion logic, core papers, unread but relevant papers, and citation graph relationships. Separate `cites`, `extends`, `criticizes`, and `same-problem`.

### `experiment_audit_matrix.md`

Record run IDs, code paths, configs, seeds, commands, logs, metric files, generated table/figure paths, statistical status, failure notes, and claims supported by each run.

### `figure_asset_register.md`

Record each figure's source asset, editable source, data source, venue usage, AI-generated or AI-edited status, reuse risk, disclosure need, and fidelity status.

### `review_risk_register.md`

Merge real reviews, external AI reviews, local mock reviews, and user concerns. Every row should include source, reviewer perspective, issue, manuscript location, severity, evidence, action, and status.

### `revision_queue.md`

Sort tasks into:

- `must_fix`
- `high_value`
- `low_cost`
- `defer`
- `cannot_fix_now_but_soften_claim`
- `do_not_do`

Keep actions tied to reviewer acceptance risk, evidence quality, or submission hygiene. Remove tasks that only create busywork.

### `submission_checklist.md`

Check official template, page count, references, anonymity, author metadata, conflicts, AI disclosure, figure reuse, copyright, supplementary materials, source package, and upload permissions.

## Review-Informed Revision Loop

1. Convert every review comment into a risk row before drafting a response.
2. Decide whether the response is `fix`, `clarify`, `soften`, `defer`, or `push back`.
3. Change manuscript text only after the action is clear.
4. Re-review the changed manuscript against the original issue.
5. Keep rebuttal tone out of the paper body. The paper should read as a mature manuscript, not as a defense memo.
6. After prose naturalization, verify claim/evidence alignment, terminology identity, modality, causal strength, baselines, and scope before closing the revision item.

## Experiment Loop

1. Define the claim being tested.
2. Define minimal viable evidence and failure criteria.
3. Record exact run configuration before interpreting results.
4. Add negative results and failed runs when they affect scope.
5. Update claims after analysis; do not stretch interpretation to fit desired results.

## Figure Loop

1. Identify the reviewer takeaway for the figure.
2. Identify whether the figure is data-backed, source-image-backed, schematic, or mixed.
3. Register source and cross-venue usage.
4. Rebuild factual elements deterministically.
5. Render and check final size, legibility, caption alignment, and disclosure status.

## Stop Conditions

Pause and ask for user judgment when:

- Two plausible venues imply different claims or experiment priorities.
- A required experiment is expensive or may change the paper's central claim.
- External upload is needed.
- Author metadata, conflicts, or disclosure cannot be inferred from local files.
- The revision queue is growing without reducing core reviewer risk.
