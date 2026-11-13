---
name: cloudflare
description: "用于 Cloudflare 平台开发、排障和方案审查，包括 Workers、Pages、KV、D1、R2、Workers AI、Vectorize、Agents SDK、网络、安全和 IaC。"
license: Complete terms in LICENSE.txt
metadata:
  short-description: Cloudflare 平台开发、变更安全门禁与 DO 休眠配额治理
  references:
  - workers
  - pages
  - d1
  - durable-objects
  - workers-ai
  sources:
  - OpenAI curated Cloudflare plugin 3fdeeb49
  - Cloudflare documentation
---
# Cloudflare Platform Skill

Consolidated parent entry for Cloudflare platform work. Use the decision trees below to find the right product, then load detailed references or specialized local Skills only when their narrower scope is needed.

Your knowledge of Cloudflare APIs, types, limits, and pricing may be outdated. **Prefer retrieval over pre-training** — the references in this skill are starting points, not source of truth.

## Production Safety & Quota Governance Gates

- **Five Mandatory Operational Gates**:
  1. **Explicit Confirmation Before Destructive Commands**: Before running `wrangler delete`, `wrangler pages project delete`, `wrangler d1/kv/r2 delete`, `cloudflared tunnel delete`, or `DELETE` REST calls, present a complete impact table (exact asset name, resource type, bound custom domains, last deployment timestamp, and proposed action) and obtain explicit user confirmation;
  2. **Do Not Redeploy Archived Projects**: Keep completed historical showcase projects frozen; never run `wrangler deploy` or mutate `wrangler.toml` inside archived directories without explicit instruction;
  3. **Post-Deploy HTTP 200 Verification Gate**: After deploying or migrating Pages / Workers, run `curl -ILs` against production endpoints to confirm `HTTP 200` (preventing `HTTP 522` or `HTTP 403 Error 1014` dangling CNAMEs) and bump Service Worker cache versions when applicable;
  4. **Free-Tier Quota & Durable Objects WebSocket Hibernation Gate**: Cloudflare's Free plan caps Durable Objects active duration at `101,562.5` seconds (`~28.21 DO-hours/day`). Any long-lived WebSocket coordinator **must** use the Hibernation API (`this.ctx.acceptWebSocket(ws, tags)`, `this.ctx.getWebSockets(tag)`, and `this.ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("PING", "PONG"))`) with client text `"PING"` intervals `>= 45s` so idle connections consume zero active duration;
  5. **Strict Separation of `wrangler pages deploy` vs. `wrangler deploy`**: Inspect project structure (`pages_dist/` / `_worker.js` vs. standalone Worker `main` entry) before deploying so Pages and Workers targets are never cross-deployed.

## Retrieval Sources

Fetch the **latest** information before citing specific numbers, API signatures, or configuration options. Do not rely on baked-in knowledge or these reference files alone.

| Source | How to retrieve | Use for |
|--------|----------------|---------|
| Cloudflare docs | `context7` MCP (`resolve-library-id` / `query-docs`) or `anysearch` / `agent-reach` against `https://developers.cloudflare.com/` | Limits, pricing, API reference, compatibility dates/flags |
| Workers types | `npm pack @cloudflare/workers-types` or check `node_modules` | Type signatures, binding shapes, handler types |
| Wrangler config schema | `node_modules/wrangler/config-schema.json` | Config fields, binding shapes, allowed values |
| Product changelogs | `https://developers.cloudflare.com/changelog/` | Recent changes to limits, features, deprecations |

When a reference file and the docs disagree, **trust the docs**. This is especially important for: numeric limits, pricing tiers, type signatures, and configuration options.

## Integrated Implementation Modes

This is the only canonical Cloudflare entry. Select one focused component after
identifying the product; do not load every component just because the task
mentions multiple Cloudflare terms.

| Need | Read only this component next |
|------|--------------------------------|
| Workers implementation, review, streaming, bindings, secrets, observability | `references/components/workers-best-practices/guide.md` |
| `wrangler` commands, `wrangler.jsonc`, local dev, deploy, previews, bindings | `references/components/wrangler/guide.md` |
| Durable Objects, SQLite storage, alarms, RPC, WebSocket coordination, migrations | `references/components/durable-objects/guide.md` |
| Cloudflare Sandbox SDK, code interpreter, untrusted-code execution, container lifecycle | `references/components/sandbox-sdk/guide.md` |
| Cloudflare Agents SDK on Workers | `agents-sdk` when that plugin is available; otherwise `references/agents-sdk/` |

Treat the listed component guides as progressive-disclosure material. They retain
their original detailed references and examples, while this entry remains the
owner of product selection, current-doc retrieval, deployment safety, and
cross-product tradeoffs.

## Quick Decision Trees

### "I need feature flags"

```
Need feature flags?
└─ Feature toggles, targeting rules, percentage rollouts → flagship/
   ├─ Evaluate in Workers → Flagship binding (env.FLAGS)
   ├─ Evaluate in Node.js / browser → OpenFeature SDK (@cloudflare/flagship)
   └─ Manage flags via API → Flagship REST API
```

### "I need to run code"

```
Need to run code?
├─ Serverless functions at the edge → workers/
├─ Full-stack web app with Git deploys → pages/
├─ Stateful coordination/real-time → durable-objects/
├─ Long-running multi-step jobs → workflows/
├─ Run containers → containers/
├─ Multi-tenant (customers deploy code) → workers-for-platforms/
├─ Scheduled tasks (cron) → cron-triggers/
├─ Lightweight edge logic (modify HTTP) → snippets/
├─ Process Worker execution events (logs/observability) → tail-workers/
└─ Optimize latency to backend infrastructure → smart-placement/
```

### "I need to store data"

```
Need storage?
├─ Key-value (config, sessions, cache) → kv/
├─ Relational SQL → d1/ (SQLite) or hyperdrive/ (existing Postgres/MySQL)
├─ Object/file storage (S3-compatible) → r2/
├─ Versioned file trees (repos, build outputs, checkpoints) → artifacts/
├─ Message queue (async processing) → queues/
├─ Vector embeddings (AI/semantic search) → vectorize/
├─ Strongly-consistent per-entity state → durable-objects/ (DO storage)
├─ Secrets management → secrets-store/
├─ Streaming ETL to R2 → pipelines/
└─ Persistent cache (long-term retention) → cache-reserve/
```

### "I need AI/ML"

```
Need AI?
├─ Run inference (LLMs, embeddings, images) → workers-ai/
├─ Vector database for RAG/search → vectorize/
├─ Build stateful AI agents → agents-sdk/
├─ Gateway for any AI provider (caching, routing) → ai-gateway/
└─ AI-powered search widget → ai-search/
```

### "I need networking/connectivity"

```
Need networking?
├─ Expose local service to internet → tunnel/
├─ TCP/UDP proxy (non-HTTP) → spectrum/
├─ WebRTC TURN server → turn/
├─ Private network connectivity → network-interconnect/
├─ Optimize routing → argo-smart-routing/
├─ Optimize latency to backend (not user) → smart-placement/
└─ Real-time video/audio → realtimekit/ or realtime-sfu/
```

### "I need security"

```
Need security?
├─ Web Application Firewall → waf/
├─ DDoS protection → ddos/
├─ Bot detection/management → bot-management/
├─ API protection → api-shield/
├─ CAPTCHA alternative → turnstile/
└─ Credential leak detection → waf/ (managed ruleset)
```

### "I need media/content"

```
Need media?
├─ Image optimization/transformation → images/
├─ Video streaming/encoding → stream/
├─ Browser automation/screenshots → browser-rendering/
└─ Third-party script management → zaraz/
```

### "I need analytics/metrics data"

```
Need analytics?
├─ Query across all Cloudflare products (HTTP, Workers, DNS, etc.) → graphql-api/
├─ Custom high-cardinality metrics from Workers → analytics-engine/
├─ Client-side (RUM) performance data → web-analytics/
├─ Workers Logs and real-time debugging → observability/
└─ Raw logs (Logpush to external tools) → Cloudflare docs
```

### "I need infrastructure-as-code"

```
Need IaC? → pulumi/ (Pulumi), terraform/ (Terraform), or api/ (REST API)
```

## Product Index

### Feature Flags
| Product | Reference |
|---------|-----------|
| Flagship | `references/flagship/` |

### Compute & Runtime
| Product | Reference |
|---------|-----------|
| Workers | `references/workers/` |
| Pages | `references/pages/` |
| Pages Functions | `references/pages-functions/` |
| Durable Objects | `references/components/durable-objects/guide.md` |
| Workflows | `references/workflows/` |
| Containers | `references/containers/` |
| Workers for Platforms | `references/workers-for-platforms/` |
| Cron Triggers | `references/cron-triggers/` |
| Tail Workers | `references/tail-workers/` |
| Snippets | `references/snippets/` |
| Smart Placement | `references/smart-placement/` |

### Storage & Data
| Product | Reference |
|---------|-----------|
| KV | `references/kv/` |
| D1 | `references/d1/` |
| R2 | `references/r2/` |
| Artifacts | `references/artifacts/` |
| Queues | `references/queues/` |
| Hyperdrive | `references/hyperdrive/` |
| DO Storage | `references/do-storage/` |
| Secrets Store | `references/secrets-store/` |
| Pipelines | `references/pipelines/` |
| R2 Data Catalog | `references/r2-data-catalog/` |
| R2 SQL | `references/r2-sql/` |

### AI & Machine Learning
| Product | Reference |
|---------|-----------|
| Workers AI | `references/workers-ai/` |
| Vectorize | `references/vectorize/` |
| Agents SDK | `references/agents-sdk/` |
| AI Gateway | `references/ai-gateway/` |
| AI Search | `references/ai-search/` |

### Networking & Connectivity
| Product | Reference |
|---------|-----------|
| Tunnel | `references/tunnel/` |
| Spectrum | `references/spectrum/` |
| TURN | `references/turn/` |
| Network Interconnect | `references/network-interconnect/` |
| Argo Smart Routing | `references/argo-smart-routing/` |
| Workers VPC | `references/workers-vpc/` |

### Security
| Product | Reference |
|---------|-----------|
| WAF | `references/waf/` |
| DDoS Protection | `references/ddos/` |
| Bot Management | `references/bot-management/` |
| API Shield | `references/api-shield/` |
| Turnstile | `references/turnstile/` |

### Media & Content
| Product | Reference |
|---------|-----------|
| Images | `references/images/` |
| Stream | `references/stream/` |
| Browser Rendering | `references/browser-rendering/` |
| Zaraz | `references/zaraz/` |

### Real-Time Communication
| Product | Reference |
|---------|-----------|
| RealtimeKit | `references/realtimekit/` |
| Realtime SFU | `references/realtime-sfu/` |

### Developer Tools
| Product | Reference |
|---------|-----------|
| Wrangler | `references/components/wrangler/guide.md` |
| Miniflare | `references/miniflare/` |
| C3 | `references/c3/` |
| Observability | `references/observability/` |
| GraphQL Analytics API | `references/graphql-api/` |
| Analytics Engine | `references/analytics-engine/` |
| Web Analytics | `references/web-analytics/` |
| Sandbox | `references/sandbox/` |
| Workerd | `references/workerd/` |
| Workers Playground | `references/workers-playground/` |

### Infrastructure as Code
| Product | Reference |
|---------|-----------|
| Pulumi | `references/pulumi/` |
| Terraform | `references/terraform/` |
| API | `references/api/` |

### Other Services
| Product | Reference |
|---------|-----------|
| Email Routing | `references/email-routing/` |
| Email Workers | `references/email-workers/` |
| Static Assets | `references/static-assets/` |
| Bindings | `references/bindings/` |
| Cache Reserve | `references/cache-reserve/` |
