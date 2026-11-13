# Elsevier Editorial Manager & Journal Revision Gate (`elsarticle` / *Neurocomputing*-Class)

Use this gate whenever preparing an initial submission, Major/Minor Revision package, or camera-ready source upload for Elsevier journals hosted on **Editorial Manager (EM)** (such as *Neurocomputing*, *Knowledge-Based Systems*, *Pattern Recognition*, *Information Fusion*, or *Expert Systems with Applications*). Keep all checks generic and tied to the active paper workspace's `status.md`, `revision_queue.md`, and `submission_checklist.md`.

---

## 1. Highlights Hard Character Gate (`<= 85` Characters Including Spaces)

Elsevier EM enforces a strict automated gate on the standalone `Highlights` file (`highlights.tex` / `Highlights.docx`):

1. **Bullet Count**: Exactly **`3` to `5` bullet points** summarizing core novel findings or methodological contributions (no generic background sentences, no citations, no undefined acronyms, no math macros that fail in plain-text metadata extraction).
2. **Strict Length Cap**: Every single bullet MUST be **`<= 85` characters INCLUDING spaces** (excluding the leading bullet marker `- ` or `\item `).
3. **Deterministic Pre-Flight Check**: Run a character-count assertion before packaging; never eyeball character length:
   ```bash
   python3 -c '
   bullets = [
       # Paste exact highlight strings here
   ]
   assert 3 <= len(bullets) <= 5 or not bullets, f"Expected 3..5 bullets, got {len(bullets)}"
   for i, b in enumerate(bullets, 1):
       assert len(b) <= 85, f"Highlight #{i} is {len(b)} chars (>85): {b!r}"
       print(f"[OK] H{i} ({len(b)}/85 chars): {b}")
   '
   ```

---

## 2. Mandatory Metadata, `CRediT` & Disclosure Statements

Verify human signoff and exact consistency across the title page, manuscript end-matter, and Editorial Manager web fields:

- **`CRediT authorship contribution statement`**: Use official 14-role CRediT taxonomy (`Conceptualization`, `Methodology`, `Software`, `Validation`, `Formal analysis`, `Investigation`, `Data curation`, `Writing – original draft`, `Writing – review & editing`, `Visualization`, `Supervision`, `Project administration`, `Funding acquisition`). Every listed author must map to accurate roles confirmed by the user.
- **`Declaration of competing interest`**: Explicit conflict/non-conflict statement matching EM submission answers.
- **`Data availability`**: Concrete repository URL, benchmark availability statement, or "Data will be made available on request" per author approval.
- **`Funding` & `Acknowledgements`**: Exact grant numbers or explicit non-funded wording (`This research did not receive any specific grant...`); never guess grant IDs.
- **Declaration of Generative AI in Scientific Writing**: Align with current Elsevier policy—AI tools must never be listed as authors; if language-polishing assistance requires disclosure, place the standard `Declaration of generative AI and AI-assisted technologies in the writing process` section immediately before References only after explicit author confirmation.

---

## 3. Flat LaTeX Source Package & Dual-Track Diff Gate

Editorial Manager's server-side TeX Live builder flattens uploaded `.zip` archives or rejects nested subdirectory paths (`sections/`, `figures/`):

1. **Zero-Subdirectory Flat Staging**:
   - Build a clean release staging folder containing **zero subdirectories**: `manuscript.tex`, `.bib` (and pre-built `.bbl`), `elsarticle.cls` / `.bst` if non-standard, and all figure files (`.pdf`, `.eps`, `.png`, `.jpg`) placed at the **same root level**.
   - Rewrite all `\input{sections/...}` inline (or to root-level filenames) and rewrite `\includegraphics[...]{figs/foo.pdf}` to `\includegraphics[...]{foo.pdf}`; strip commented-out draft blocks (`% TODO`, internal review notes, unused figure files) so unpublished internal comments never leak into uploaded `.tex` sources.
2. **Clean + Marked-Up Dual PDF Pair**:
   - Compile **`manuscript_clean.pdf`** from scratch in an isolated `/tmp` directory containing only the flat staging files (`pdflatex -> bibtex -> pdflatex -> pdflatex`) and run `python3 $HOME/.agents/skills/paper-publication-copilot/scripts/latex_pdf_qa.py manuscript_clean.pdf --log manuscript_clean.log` (`0` undefined citations/references, `0` `Overfull \hbox`, `0` orphan short tails `<35%`).
   - For revisions, generate **`manuscript_marked.pdf`** (via `latexdiff` against the prior submitted `.tex` baseline or explicit color-marked environments) and run `latex_pdf_qa.py` on the marked PDF as well to ensure change markup does not blow up table widths or page margins.

---

## 4. `Response to Reviewers` Point-by-Point Alignment Gate

Every revision package must include a standalone `Response to Reviewers` (`response_letter.tex` / `.pdf` / `.docx`) audited against the actual revised manuscript:

1. **100% Comment Enumeration**: Index every comment from the Associate Editor and all Reviewers (`AE-1`, `R1-C1`, `R1-C2`, ..., `Rn-Ck`). Never merge two distinct technical questions into one vague paragraph to dodge a sub-question.
2. **Three-Part Verifiable Tuple per Comment**:
   - **Verbatim Reviewer Comment**: Quoted accurately without truncation of critical qualifiers;
   - **Direct Response & Evidence**: Clear answer (`We agree...` / respectful evidence-backed clarification), new experiment/ablation numbers, and statistical context;
   - **Exact Manuscript Diff Pointer**: Section number, page/paragraph locator in `manuscript_clean.pdf`, and the exact revised excerpt or table/figure ID.
3. **Zero Phantom Edits & Tone Audit**:
   - Every change promised in `Response to Reviewers` must physically exist in `manuscript_clean.tex` and `manuscript_marked.pdf`;
   - Run `shuorenhua` academic mode (`bounded` scope) over both the revised prose and the response letter to strip sycophantic AI openers (`Thank you for this insightful and profound comment!`) while keeping a calm, collegial, respectful scholarly register.

---

## 5. Local Offline Simulated Double-Blind Peer Review (`:3425` MagPie)

Before locking an initial submission or revision package:

- **Privacy & Email Redline**: Never upload unpublished manuscripts, review letters, or rebuttal drafts to third-party web review sites, and **never enter advisor (`<ADVISOR_EMAIL>`) or collaborator emails** into external forms.
- **Local Deterministic Dual-Reviewer Protocol**: Run offline simulated review exclusively through local MagPie (`${OPENAI_COMPAT_BASE_URL}`, project-bound `Bearer magpie-<slug>` key + `X-Magpie-Session`, bypassing proxy on `127.0.0.1`):
  - **`group/sol` (Methodology, Math & Baseline Skeptic)**: Audits formal definitions, equation indices/dimensions, ablation isolation, baseline fairness, statistical significance, and claim-evidence overreach;
  - **`group/opus` (AE / Narrative & Rebuttal Critique)**: Audits contribution clarity, related-work positioning, *Neurocomputing* / Elsevier scope fit, figure-caption self-containment, and whether `Response to Reviewers` persuasively resolves every reviewer concern without over-conceding.
- Log all valid findings into `review_risk_register.md` and resolve blocking items before human final signoff.
