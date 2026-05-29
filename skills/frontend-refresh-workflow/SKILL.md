---
name: frontend-refresh-workflow
description: "Refresh an existing frontend with a new prototype while preserving real product behavior. Use when auditing an old UI, writing a prototype brief, integrating a provided frontend build, replacing mock interactions with backend calls, and delivering a runnable project structure."
metadata:
  short-description: "Refresh existing frontends without fake UI"
  category: "frontend-workflow"
  version: "1.0.0"
---

# Frontend Refresh Workflow

Use this skill when an existing project needs a frontend refresh, not just a CSS tweak.

The goal is to move from old UI to a new, working frontend without leaving fake buttons, mock data, dead routes, or a confusing project layout.

## When to use

Use it when the user needs one or more of these:

- audit the current frontend before redesign
- write a prototype brief for another designer, tool, or agent
- integrate a supplied frontend prototype or ZIP
- connect a new UI to real backend behavior
- remove mock data and placeholder interactions
- reorganize the project for handoff

Do not use it for a single small style change or a purely backend task.

## Principles

- Inspect the current project before changing it.
- Run the project before judging the UI.
- Read code and use the actual interface; do not rely on code reading alone.
- Treat every visible control as either real or removable.
- Keep the new prototype's visual direction unless it blocks real behavior.
- Record the commands that actually worked.
- Avoid broad rewrites unless the project structure is already blocking delivery.

## Workflow

### A. Take over the old project

1. Check Git status and note unrelated changes.
2. Identify frontend, backend, docs, environment files, and build tools.
3. Find run commands and required environment variables.
4. Check port usage and choose free local ports if needed.
5. Start the project and open the real entry page.

Write down the exact commands that worked. They will go into the final handoff.

### B. Map the current frontend

Read code and browse the UI. Produce a page map that covers:

- route or entry point
- page purpose
- visible content blocks
- buttons, forms, filters, pagination, dialogs, drawers, uploads, maps, media players, and navigation
- data source and API calls
- auth requirements
- loading, empty, error, disabled, selected, expanded, and unauthenticated states
- which parts are real and which are local storage, mock data, or placeholders

Use `templates/page-map.md` if a written audit is needed.

### C. Write a prototype brief

When another person, tool, or agent will build the new prototype, write a tool-neutral brief. It should describe product goals, pages, states, interactions, and visual constraints.

Do not bundle tool-specific output instructions unless the user asks for them. A useful brief should work for a designer, an AI frontend tool, or another engineer.

Use `templates/prototype-brief.md` when needed.

### D. Integrate the new prototype

When a prototype or ZIP arrives:

1. Store the original archive or source in a clear location.
2. Identify framework, routes, package manager, build command, and environment variables.
3. Map prototype views to existing backend capabilities.
4. Decide which old frontend code is still needed.
5. Move the new frontend into the project without scattering files across the root.

If the old frontend is retained for reference, put it in a clearly named legacy location.

### E. Replace fake behavior

For every kept control:

- connect it to real data or real navigation
- implement form validation and error feedback
- replace mock data with API calls or documented fixtures
- remove controls that no longer have a purpose
- test success, loading, empty, and error paths

Do not accept a UI where buttons look clickable but do nothing useful.

### F. Verify and hand off

Run the project from a clean terminal. Check:

- main pages load
- important routes work
- forms submit or fail correctly
- lists, filters, and pagination use real data
- browser console has no critical errors
- README commands work
- environment example files match actual usage

Use `references/checklist.md` before final delivery.

