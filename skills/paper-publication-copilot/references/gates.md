# Publication Gates

## Mature CS/AI Paper Gates

1. **Reader Contract**: Abstract and introduction promise only what the paper actually proves or argues.
2. **Contribution Spine**: The paper has one dominant technical story. Secondary claims support it.
3. **Claim-Evidence Match**: Every strong claim has an experiment, figure, table, citation, or explicit limitation.
4. **Baseline Comparability**: Baselines are comparable in data, budget, target format, decoding, and evaluation contract.
5. **Ablation Necessity**: Missing ablations are either added, replaced by relevant evidence, or handled by reducing claim strength.
6. **Statistical Honesty**: Single-run or low-sample evidence is labeled as such. Confidence intervals or bootstrap estimates are added when feasible.
7. **Mechanism Transparency**: Parser, schema, prompt, target format, or evaluation contract is explained enough to avoid suspicion of benchmark-specific tuning.
8. **Related Work Positioning**: Related work shows the paper's exact gap and baseline lineage, not only a citation list.
9. **Figure Argument**: Each figure has one clear takeaway and does not make the caption carry unsupported claims.
10. **Limitations Discipline**: Limitations are concrete and scoped. Avoid apology tone, hidden rebuttal, or broad self-undermining.
11. **Reproducibility Route**: Readers can identify data, code, settings, metrics, and expected outputs even when full release is deferred.
12. **Submission Hygiene**: Venue rules, anonymity, page count, references, AI disclosure, image policy, source package, and author metadata are checked against official sources.

## Academic Revision Gate

When manuscript prose is drafted or naturalized with `shuorenhua` academic mode:

1. Preserve every material claim and evidence-bearing relation in both directions: source to output and output to source.
2. Preserve numbers, units, polarity, modality, causal strength, comparison direction, baseline, attribution, limitations, and scope.
3. Keep quotations, formulas, code, citation markers, reference entries, proper nouns, model/dataset names, and user-locked text unchanged.
4. Normalize only confirmed same-concept terminology drift. Keep declared abbreviations and genuinely distinct concepts separate.
5. Treat repeated discourse markers, contrasts, passives, lists, and sentence patterns as candidates whose function must be checked, not automatic defects.
6. Re-run claim-evidence and terminology checks after editing. A more natural sentence that strengthens or weakens the scientific claim fails this gate.

## Reviewer Perspectives

Use these perspectives in `review_risk_register.md`:

- `editor`: fit, contribution strength, desk-reject risk, venue expectations.
- `historian`: field lineage, whether the claimed gap is real, recent adjacent work.
- `baseline_scout`: missing baselines, unfair comparison, outdated benchmark, data leakage risk.
- `methodology_skeptic`: causal claims, statistics, confounds, external validity.
- `reproducibility_checker`: data, code, settings, seeds, logs, hardware, package route.
- `figure_critic`: figure readability, factual support, caption alignment, reuse risk.
- `style_guard`: AI flavor, rebuttal tone, over-concession, overclaim, promotional language.

## Common CS/AI Submission Failure Patterns

- A strong abstract claim is supported only by a narrow diagnostic.
- Related work cites the right papers but does not show why the paper's gap remains open.
- Baseline comparison changes more than one variable at a time.
- The method's strongest mechanism is not isolated in ablations.
- A data figure is visually polished but not reproducible from stored data.
- A schematic repeats an old venue figure with small caption changes.
- The limitations section reads like a response to known reviewers.
- The rebuttal promises changes that the revised manuscript does not actually contain.
- AI-generated diagrams contain invented labels, fabricated numbers, or old task names.

## External Review Gate

Treat external AI reviews as candidate risks. Before acting on a finding:

1. Locate the exact manuscript section.
2. Decide whether the criticism is valid, partially valid, unclear, or false.
3. Map valid criticism to evidence, manuscript edit, experiment, figure change, or claim softening.
4. Keep false or low-value criticism in the risk register with a reason for not acting.

## Bibliographic & Temporal Integrity Gate

Before locking related work, introduction claims, or bibliography entries, enforce this 3-layer integrity check:

1. **Retraction & Hijack Check**: Verify via OpenAlex (`is_retracted`), Crossref (`update-to` retraction notices), and `citation_integrity_audit.py` that no cited work has been retracted or hijacked by predatory `posted-content` DOIs (such as `10.65215/*`).
2. **Temporal Causality & Unanchored "Recently" Check**: Audit temporal markers (`recently`, `in recent years`, `state-of-the-art`, `emerging`, `new`) against actual publication years. Flag unanchored `recently` claims citing papers older than 3–5 years without historical framing, and verify chronological causality across citation chains (a paper must never be framed as extending, critiquing, or benchmarking against a work published after it).
3. **Uncited Empirical Assertion Check**: Scan prose for quantitative, comparative, or empirical assertions (`studies show`, `prior work demonstrates`, `widely adopted`, `achieves superior accuracy`, or specific benchmark deltas) that lack an immediate citation, internal experiment table/figure pointer, or explicit scope qualifier.

## Final Submission & Visual Layout Gate (`latex_pdf_qa.py`)

Do not mark a paper submission-ready until:

- Current venue rules were checked from official sources.
- PDF compiles cleanly from current source and passes `python3 $HOME/.agents/skills/paper-publication-copilot/scripts/latex_pdf_qa.py <Main.pdf> --log <Main.log>`:
  - Zero `Undefined citations` or `Undefined references`;
  - Zero `Overfull \hbox` or horizontal figure/table margin overflows;
  - Paragraph last-line fill ratios audited (`小尾巴` check): eliminate `<35%` orphan tails and tighten/expand multi-line paragraphs toward `80%–100%` last-line width fill (using concise phrasing or `\looseness=-1`);
  - When visual page inspection is needed, use `--render-dir` at `110 DPI` (`<100KB/page`) rather than high-DPI PNGs to avoid bloating conversation state.
- Reference closure, undefined references, and the Bibliographic & Temporal Integrity Gate (retraction, temporal causality, uncited empirical assertions) were checked.
- Figure files render and match captions.
- AI disclosure and image policy are explicitly decided.
- All author, conflict, funding, data availability, and acknowledgement fields have human confirmation or clear placeholders.
