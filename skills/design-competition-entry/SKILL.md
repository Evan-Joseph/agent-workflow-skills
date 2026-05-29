---
name: design-competition-entry
description: "Manage a design competition entry from brief verification to deliverable planning. Use when an agent must check official rules, choose the correct deliverable branch, define a concept, write image or layout prompts, review drafts, and prepare submission assets."
metadata:
  short-description: "Design competition entry workflow"
  category: "design-workflow"
  version: "1.0.0"
---

# Design Competition Entry

Use this skill for design competition work that has rules, categories, deliverables, prompts, drafts, and final submission files.

Do not start by making images. Start by verifying the brief and choosing the right deliverable branch.

## When to use

Use it when the task involves:

- reading or re-checking a competition brief
- choosing a category or deliverable type
- planning product, poster, script, spatial, or video materials
- writing prompts for image or layout generation
- reviewing drafts against rules and submission needs
- preparing final assets for a competition platform

Do not use it for a one-line copy edit or a single standalone image prompt.

## First pass

Always output these four blocks before creative work:

1. **Official rules snapshot**
   - competition name
   - verification date
   - official sources
   - confirmed requirements
   - open questions
2. **Branch decision**
   - selected branch
   - reason
   - branches not used
3. **Current deliverable**
   - what will be produced now
   - what it depends on
4. **Next step**
   - one concrete next action

If official rules are missing or incomplete, continue with clearly marked assumptions and open questions. Do not invent final requirements.

## Branches

Choose one branch:

- **Product or poster board**: visual identity, product set, application set, final board.
- **Script or digital media**: concept, story, scene structure, key visuals, final text or media package.
- **Environment or spatial design**: site assumption, movement path, zones, materials, views, explanation board.
- **Video or virtual production**: prompt, script, storyboard, shot plan, production workflow, technical note.

If the task does not fit these branches, say so and define a task-specific branch before continuing.

## Workflow

### 0. Verify rules

Check the latest official source. Record:

- exact competition or track name
- dates
- category definitions
- deliverables
- size, format, duration, resolution, and file limits
- logo or organizer requirements
- prohibited content or common disqualification risks

Use exact dates instead of "today", "this year", or "next week".

### 1. Set up a working structure

For new entries, create or ask for a simple structure:

```text
00-sources/
01-brief/
02-references/
03-prompts/
04-drafts/
05-submission/
```

Keep raw sources, references, prompts, drafts, and final assets separate.

### 2. Read the brief

Summarize:

- theme or problem
- target audience
- judging priorities
- required deliverables
- format constraints
- clear risks

### 3. Choose and narrow the concept

Pick one direction. A usable direction states:

- the source idea or cultural/technical basis
- the intended use or experience
- why it fits the track
- what has been ruled out

Do not keep five weak concepts alive just to look comprehensive.

### 4. Define deliverables before prompts

Before writing generation prompts, define the object or page:

- category
- structure
- number of components
- material or medium
- dimensions or aspect ratio
- required text
- forbidden text
- what the result must not turn into

Read `references/prompt-rules.md` before writing image or layout prompts.

### 5. Review drafts

Review against:

- official rules
- branch fit
- category recognizability
- practical use
- visual hierarchy
- text whitelist
- source/reference consistency
- final submission constraints

Use `references/review-checklist.md` before regenerating or submitting.

