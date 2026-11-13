# CS/AI Publication Review

Use this reference for CS/AI conference and journal manuscripts, especially when pre-submission review, desk-reject risk, reviewer-comment triage, or revision verification is needed.

## Reviewer Roles

Write role sections independently before synthesis:

- `editor`: venue fit, contribution strength, novelty framing, desk-reject risk.
- `historian`: whether the related-work gap is real and current.
- `baseline_scout`: missing baselines, unfair comparisons, outdated datasets, token-budget or supervision mismatch.
- `methodology_skeptic`: causal attribution, confounds, statistics, seed count, external validity.
- `reproducibility_checker`: code/data route, configs, metrics, logs, package and environment clarity.
- `figure_critic`: figure readability, data fidelity, caption alignment, cross-venue reuse risk.
- `style_guard`: overclaiming, promotional language, AI flavor, rebuttal tone, over-concession.

## Risk Output

For each serious issue, output:

| risk | evidence | manuscript location | reviewer perspective | severity | action | verification |
|---|---|---|---|---|---|

Severity:

- `blocking`: likely desk reject, ethical/compliance issue, or unsupported central claim.
- `major`: likely reviewer objection that changes acceptability.
- `moderate`: weakens persuasiveness but can be handled with scoped revision.
- `minor`: clarity, wording, or formatting issue.

## CS/AI Checks

- Does the main claim require a stronger baseline, ablation, or statistical report than the manuscript provides?
- Are baseline methods comparable in data, supervision, decoding, target format, budget, and evaluation contract?
- Does the paper isolate its claimed mechanism, or only show a favorable end-to-end result?
- Are single-seed or narrow-benchmark results written as broad conclusions?
- Does the related work explain the open gap, or only list adjacent papers?
- Does the method section expose enough details for a reviewer to reproduce the evaluation?
- Do figures support the exact claims made in captions and surrounding text?
- Do limitations scope the contribution without sounding like a defense against known reviews?

## Revision Review

When checking a revised manuscript:

1. Map each prior review issue to exact changed text, table, figure, experiment, or limitation.
2. Mark status as `addressed`, `partially_addressed`, `not_addressed`, `overclaimed`, or `new_risk`.
3. Check that the manuscript now reads naturally and not like a rebuttal pasted into the body.
4. Re-run claim-evidence checks for any new or stronger claim introduced during revision.

## Rebuttal And Response Audit

For response drafts, check:

- Does every reviewer comment receive a direct response?
- Does the response cite exact manuscript changes?
- Does it concede when evidence is insufficient?
- Does it push back only with evidence?
- Does it avoid promising experiments or releases that are not actually done?
- Does the revised manuscript support the response?
