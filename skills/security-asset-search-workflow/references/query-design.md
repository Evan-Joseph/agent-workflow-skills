# Query Design

Use this reference when turning a security question into asset-search queries.

## Build from blocks

Start with plain-language blocks before provider syntax.

### Identity

Examples:

- root domain
- subdomain pattern
- organization name
- ASN
- certificate subject or issuer
- approved IP range

### Service

Examples:

- protocol
- port
- product name
- page title
- HTTP header
- TLS certificate field
- favicon hash
- banner string

### Environment

Examples:

- admin
- dashboard
- staging
- test
- dev
- debug
- backup
- internal

### Exclusions

Examples:

- CDN ranges
- shared hosting
- unrelated brand collisions
- parked domains
- mirrors
- old acquisitions outside current scope

## Query progression

Use this order:

1. identity-only query
2. identity plus one service signal
3. identity plus environment signal
4. add exclusions
5. widen only if result count is too low

This makes false positives easier to explain.

## Provider translation

Each provider has different field names, syntax, result freshness, and pagination behavior.

When translating:

- keep the original search question
- write the provider-specific query next to it
- record unsupported fields
- avoid pretending two providers mean the same thing when they index different data

## Pagination

If a provider uses page numbers, record page and page size.

If it uses cursors, keep the original query and cursor together. A cursor without its query is often not reproducible.

## Field selection

Ask for only the fields needed to verify the question.

Useful defaults:

- host or URL
- IP
- port
- protocol
- title or product
- matched field
- timestamp if available

Large fields such as full banners, headers, certificates, or screenshots should be requested only when they help confirm the finding.

