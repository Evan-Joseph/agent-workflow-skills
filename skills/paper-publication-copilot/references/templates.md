# Artifact Templates

Use these as compact schemas. Adapt filenames to the workspace convention.

## `claim_evidence_matrix.md`

| claim_id | manuscript_location | claim_text | claim_strength | evidence_type | evidence_path_or_source | exact_locator | support_status | risk | action |
|---|---|---|---|---|---|---|---|---|---|
| C01 | Abstract sentence 2 |  | strong / moderate / scoped | experiment / figure / table / citation / limitation |  | page, section, row, log line, DOI, arXiv, URL | SUPPORTED / PARTIALLY_SUPPORTED / OVERSTATED / NOT_SUPPORTED / UNVERIFIED |  |  |

## `literature_provenance.md`

```markdown
# Literature Provenance

## Search Log
| date | source | query | filters | count | notes |
|---|---|---|---|---|---|

## Core Papers
| key | title | source | read_status | role | evidence_locator | notes |
|---|---|---|---|---|---|---|

## Lineage
| from | relation | to | confidence | basis |
|---|---|---|---|---|

## Gaps
- Unread but relevant:
- Search limits:
- Citation risks:
```

## `experiment_audit_matrix.md`

| run_id | claim_id | dataset | config | seed | command | code_commit_or_hash | log_path | metric_file | table_or_figure | statistical_status | rubric_id | risk | next_action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Recommended `statistical_status` values:

- `single_run`
- `multi_seed_mean_std`
- `bootstrap_ci`
- `paired_test`
- `descriptive_only`
- `not_applicable`
- `missing`

## `figure_asset_register.md`

| figure_id | manuscript_location | venue_usage | source_asset | editable_source | data_source | ai_generated_or_edited | reuse_risk | disclosure_needed | caption_claim | fidelity_status | action |
|---|---|---|---|---|---|---|---|---|---|---|---|

Recommended `fidelity_status` values:

- `DATA_BACKED`
- `SCHEMATIC_ONLY`
- `PARTIALLY_SUPPORTED`
- `TEXT_NEEDS_SOFTENING`
- `SOURCE_MISSING`
- `REBUILD_REQUIRED`

## `review_risk_register.md`

| risk_id | source | reviewer_perspective | risk | evidence | manuscript_location | severity | action | status |
|---|---|---|---|---|---|---|---|---|

Severity:

- `blocking`
- `major`
- `moderate`
- `minor`
- `watch`

Status:

- `open`
- `in_progress`
- `addressed`
- `verified`
- `deferred`
- `rejected_with_reason`

## `revision_queue.md`

```markdown
# Revision Queue

## must_fix
- [ ] RISK-ID: action, target file/section, validation

## high_value
- [ ] 

## low_cost
- [ ] 

## cannot_fix_now_but_soften_claim
- [ ] 

## defer
- [ ] 

## do_not_do
- [ ] action rejected and reason
```

## `submission_checklist.md`

```markdown
# Submission Checklist

## Official Rules
- [ ] Venue page checked:
- [ ] Deadline and timezone:
- [ ] Page limit:
- [ ] Anonymity:
- [ ] AI disclosure:
- [ ] Figure/image policy:

## Build
- [ ] Compile command:
- [ ] Current PDF:
- [ ] Page count:
- [ ] Undefined references/citations:
- [ ] Overfull/critical warnings:

## Content
- [ ] Claim-evidence matrix reviewed:
- [ ] Experiment audit reviewed:
- [ ] Figure register reviewed:
- [ ] Review risks addressed or deferred:

## Human Fields
- [ ] Authors:
- [ ] Affiliations:
- [ ] Corresponding author:
- [ ] Conflicts:
- [ ] Funding:
- [ ] Data availability:
- [ ] CRediT:
- [ ] Acknowledgements:

## Submission Package
- [ ] Main PDF:
- [ ] Supplement:
- [ ] Source package:
- [ ] Code/data statement:
- [ ] Upload permission confirmed by user:
```
