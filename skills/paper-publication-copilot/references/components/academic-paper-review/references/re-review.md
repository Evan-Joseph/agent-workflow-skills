# Re-Review Verification

Use this reference when the user provides prior reviewer comments, a revised manuscript, and optionally a response-to-reviewers letter.

## Purpose

Verify whether revisions actually address prior comments. Do not reward persuasive response text unless the manuscript change exists and is adequate.

## Inputs

- Prior reviewer comments or a revision roadmap.
- Revised manuscript.
- Response-to-reviewers letter, if available.
- Change log, diff, tracked changes, or line/page references, if available.

If any of the first two inputs are missing, state the missing input and produce only a limited assessment.

## Verification Steps

1. Parse every prior comment into an item with reviewer id, priority, issue, requested change, and evidence needed.
2. Read the author's response claim for that item.
3. Navigate to the claimed manuscript location.
4. Independently verify whether the claimed change exists and addresses the issue.
5. Scan for new issues introduced by the revision, especially contradictions, unsupported new claims, broken citations, and inconsistent terminology.

## Status Labels

- `FULLY_ADDRESSED`: the required evidence is present and substantively resolves the issue.
- `PARTIALLY_ADDRESSED`: some evidence exists, but a meaningful gap remains.
- `NOT_ADDRESSED`: the issue remains or no relevant change is found.
- `MADE_WORSE`: the revision introduces a larger problem.
- `CANNOT_VERIFY`: location, evidence, or manuscript access is insufficient.
- `REASONABLY_DECLINED`: the author explicitly declines and gives a defensible rationale.

## Commitment Ledger

For compound comments, split promised actions into separate commitments:

- `commitment_text`: the promise or requested action.
- `commitment_type`: add_experiment / add_analysis / add_clarification / add_citation / restructure / other.
- `required_evidence_type`: new_section / new_figure / new_table / new_citation / methods_paragraph / discussion_paragraph / prose_edit / acknowledgment_only / other.
- `fulfillment_status`: fulfilled / partial / not-fulfilled / explicitly-rejected-with-rationale.
- `unfulfilled_rationale`: required for partial, not-fulfilled, or explicitly rejected commitments.

Keep lifecycle fields inside each commitment object. Do not use separate parallel lists that can drift out of alignment.

## Output Shape

```markdown
# Verification Review

## Decision
<Accept / Minor Revision / Major Revision / Reject / Cannot Verify>

## Revision Verification Matrix
| ID | Prior comment | Author claim | Manuscript location checked | Status | Evidence | Residual issue |
|---|---|---|---|---|---|---|

## New Issues
| ID | Location | Issue | Severity |
|---|---|---|---|

## Required Next Actions
<only unresolved material issues>
```

## Red Lines

- Do not mark a comment resolved from response-letter rhetoric alone.
- Do not assume tracked changes are complete; verify in the revised manuscript.
- Do not treat citation insertion as sufficient if the inserted source does not support the claim.
