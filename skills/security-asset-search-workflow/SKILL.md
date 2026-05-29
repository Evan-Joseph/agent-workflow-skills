---
name: security-asset-search-workflow
description: "Plan and document authorized internet-asset searches. Use when composing queries for public asset search engines, checking exposed services, inventorying owned infrastructure, triaging search results, or turning raw findings into a source-backed security note."
metadata:
  short-description: "Authorized asset search and evidence workflow"
  category: "security-workflow"
  version: "1.0.0"
---

# Security Asset Search Workflow

Use this skill for authorized asset discovery, exposure checks, and defensive research using public internet-asset search tools.

The goal is not to collect the biggest result set. The goal is to ask a scoped question, keep evidence, and produce findings that another person can verify.

## Scope first

Before writing queries, establish:

- target organization, domain, IP range, product, or technology
- authorization boundary
- time window
- allowed data sources
- what counts as a finding
- what should be excluded

If the scope is unclear, stop and ask for it. Do not expand from a single domain or product name into unrelated infrastructure without a reason.

## Good use cases

- inventorying exposed assets for a domain or known IP range
- checking whether a technology, banner, certificate, or title appears in owned infrastructure
- finding stale test environments or forgotten services
- comparing results from several asset search engines
- turning search results into a short defensive report
- adapting old query notes to a different provider's syntax

Do not use this skill as a substitute for direct validation against the owner's systems, logs, or configuration.

## Workflow

### 1. Write the search question

Use one sentence:

- "Find public web services under this owned domain that expose staging or admin-like titles."
- "Check whether this certificate name appears outside the approved IP ranges."
- "Inventory public assets that mention this product banner and belong to the approved organization."

### 2. Build query blocks

Break the search into small blocks:

- identity: domain, organization, certificate, ASN, IP range
- service: protocol, port, product, title, header, favicon, banner
- environment: staging, dev, test, admin, dashboard, debug
- exclusion: CDN, shared hosting, unrelated brands, known false positives
- time: first seen, last seen, recently updated if the provider supports it

Use provider-specific syntax only after the blocks are clear.

Read `references/query-design.md` when building or translating queries.

### 3. Run narrow first

Start with narrow queries and small result limits.

For each run, record:

- provider
- query string
- retrieval date
- result count if available
- fields requested
- pagination or cursor state if used
- known limitations

Avoid pulling large result sets unless the task needs it.

### 4. Normalize results

For each candidate asset, keep:

- host or URL
- IP
- port and protocol
- title or service name
- evidence field that matched
- source provider
- retrieval date
- confidence
- verification gap

Do not treat a search-engine row as final proof. Asset search indexes can be stale, merged, partial, or wrong.

### 5. Verify and classify

Classify candidates:

- in scope and confirmed
- likely in scope, needs owner-side verification
- false positive
- out of scope
- stale or inconclusive

Use direct owner-approved checks when needed. Do not interact with systems outside the authorized boundary.

Read `references/evidence-and-reporting.md` before writing a report.

## Output

Default report shape:

| Asset | Why it matched | Evidence | Scope status | Confidence | Next check |
|---|---|---|---|---|---|

Then add:

- query summary
- likely false positives
- unresolved verification gaps
- recommended next action

## Boundaries

- Keep authorization explicit.
- Do not include working credentials or private keys in queries, notes, or reports.
- Do not rely on a single search provider when the finding has operational impact.
- Do not use stale indexed data as proof of current exposure.
- Do not include exploitation steps unless the user explicitly asks for an authorized validation plan.

