---
name: fullstack-dev
description: 用于构建或改造全栈应用、后端服务和前后端集成，覆盖接口设计、鉴权、文件上传、实时能力、错误处理和生产化约束。需求明确时直接推进；只有架构、技术栈或数据边界会影响实现时才先澄清。
license: MIT
metadata:
  short-description: 全栈架构与前后端集成
  category: full-stack
  version: "1.0.0"
  sources:
    - The Twelve-Factor App (12factor.net)
    - Clean Architecture (Robert C. Martin)
    - Domain-Driven Design (Eric Evans)
    - Patterns of Enterprise Application Architecture (Martin Fowler)
    - Martin Fowler (Testing Pyramid, Contract Tests)
    - Google SRE Handbook (Release Engineering)
    - ThoughtWorks Technology Radar
    - "DietrichGebert/ponytail (MIT), minimal implementation ladder"
---

# Full-Stack Development Practices

## Pragmatic Workflow

Use the workflow depth that matches the task. Do not turn small, clear changes into a full architecture exercise.

- For a clear bug fix or feature slice, inspect the existing code and implement directly.
- For a new service, auth/data boundary, public API, or production deployment path, make the architecture decisions explicit before coding.
- If key requirements are missing and would change the implementation direction, ask one concise clarification round. If the missing details are minor, state assumptions and continue.

### Minimal Implementation Gate

Before adding a new layer, dependency, service, abstraction, or config surface, run this gate:

1. Does the requirement exist now, or is it speculative?
2. Does this codebase already have a helper, component, middleware, DTO, script, service, or pattern to reuse?
3. Does the language standard library solve it?
4. Does the platform solve it natively, such as HTML controls, CSS, browser APIs, database constraints, shell tools, or framework conventions?
5. Does an already-installed dependency solve it?
6. Can a small function or one-line call solve it without hiding edge cases?

Only scaffold the larger pattern when the current requirement needs it. Do not add an interface with one implementation, a factory for one product, a config option nobody sets, a wrapper that only delegates, or a package for behavior already covered by the stack. Never simplify away trust-boundary validation, auth, data-loss protection, accessibility basics, migrations, observability needed for production, or behavior the user explicitly requested.

### Step 0: Gather Requirements

Before scaffolding a new app or service, clarify or infer from context:

1. **Stack**: Language/framework for backend and frontend (e.g., Express + React, Django + Vue, Go + HTMX)
2. **Service type**: API-only, full-stack monolith, or microservice?
3. **Database**: SQL (PostgreSQL, SQLite, MySQL) or NoSQL (MongoDB, Redis)?
4. **Integration**: REST, GraphQL, tRPC, or gRPC?
5. **Real-time**: Needed? If yes — SSE, WebSocket, or polling?
6. **Auth**: Needed? If yes — JWT, session, OAuth, or third-party (Clerk, Auth.js)?

If the user has already specified these in their request or the existing project makes them obvious, skip asking and proceed.

### Step 1: Architectural Decisions

Based on requirements, make and state these decisions before coding:

| Decision | Options | Reference |
|----------|---------|-----------|
| Project structure | Feature-first (recommended) vs layer-first | [Section 1](#1-project-structure--layering-critical) |
| API client approach | Typed fetch / React Query / tRPC / OpenAPI codegen | [Section 5](#5-api-client-patterns-medium) |
| Auth strategy | JWT + refresh / session / third-party | [Section 6](#6-authentication--middleware-high) |
| Real-time method | Polling / SSE / WebSocket | [Section 11](#11-real-time-patterns-medium) |
| Error handling | Typed error hierarchy + global handler | [Section 3](#3-error-handling--resilience-high) |

Briefly explain each choice (1 sentence per decision).

### Step 2: Scaffold with Checklist

Use the appropriate checklist below as a reference. Implement only the items relevant to the requested scope.

### Step 3: Implement Following Patterns

Write code following the patterns in this document. Reference specific sections as you implement each part.

### Step 4: Test & Verify

After implementation, run these checks before claiming completion:

1. **Build check**: Ensure both backend and frontend compile without errors
   ```bash
   # Backend
   cd server && npm run build
   # Frontend
   cd client && npm run build
   ```
2. **Start & smoke test**: Start the server, verify key endpoints return expected responses
   ```bash
   # Start server, then test
   curl http://<LOCAL_HOST>:3000/health
   curl http://<LOCAL_HOST>:3000/api/<resource>
   ```
3. **Integration check**: Verify frontend can connect to backend (CORS, API base URL, auth flow)
4. **Visible frontend check** (if applicable): when the task creates or changes user-facing UI, use `frontend-design` (which unifies `ui.shadcn.com`, `transitions.dev`, `beautifului.dev`, `beui.dev`, and `rareui.com`); for rough, "feels off", micro-interaction, hover/press, dynamic number, or responsive polish work, reference `frontend-design/references/transitions/` and `frontend-design/references/components/ui-ux-design/references/ui-polish-microdetails.md`. Verify rendered UI via `browser-routing` (`${CDP_RELAY_HOST}` persistent relay or headless Playwright with background tabs and focus emulation; never connect directly to `9222` or steal foreground window focus).
5. **Real-time check** (if applicable): Using two headless or background browser tabs via `browser-routing` (`${CDP_RELAY_HOST}` relay), verify changes sync without stealing foreground focus.

If any check fails, fix the issue before proceeding.

### Step 5: Handoff Summary

Provide a brief summary to the user:

- **What was built**: List of implemented features and endpoints
- **How to run**: Exact commands to start backend and frontend
- **What's missing / next steps**: Any deferred items, known limitations, or recommended improvements
- **Key files**: List the most important files the user should know about

---

## Scope

**USE this skill when:**
- Building a full-stack application (backend + frontend)
- Scaffolding a new backend service or API
- Designing service layers and module boundaries
- Implementing database access, caching, or background jobs
- Writing error handling, logging, or configuration management
- Reviewing backend code for architectural issues
- Hardening for production
- Setting up API clients, auth flows, file uploads, or real-time features

**NOT for:**
- Pure frontend/UI concerns (use your frontend framework's docs)
- Pure database schema design without backend context

---

## Quick Start — New Backend Service Checklist

- [ ] Project scaffolded with **feature-first** structure
- [ ] Configuration **centralized**, env vars **validated at startup** (fail fast)
- [ ] **Typed error hierarchy** defined (not generic `Error`)
- [ ] **Global error handler** middleware
- [ ] **Structured JSON logging** with request ID propagation
- [ ] Database: **migrations** set up, **connection pooling** configured
- [ ] **Input validation** on all endpoints (Zod / Pydantic / Go validator)
- [ ] **Authentication middleware** in place
- [ ] **Health check** endpoints (`/health`, `/ready`)
- [ ] **Graceful shutdown** handling (SIGTERM)
- [ ] **CORS** configured (explicit origins, not `*`)
- [ ] **Security headers** (helmet or equivalent)
- [ ] `.env.example` committed (no real secrets)

## Quick Start — Frontend-Backend Integration Checklist

- [ ] **API client** configured (typed fetch wrapper, React Query, tRPC, or OpenAPI generated)
- [ ] **Base URL** from environment variable (not hardcoded)
- [ ] **Auth token** attached to requests automatically (interceptor / middleware)
- [ ] **Error handling** — API errors mapped to user-facing messages
- [ ] **Loading states** handled (skeleton/spinner, not blank screen)
- [ ] **Type safety** across the boundary (shared types, OpenAPI, or tRPC)
- [ ] **CORS** configured with explicit origins (not `*` in production)
- [ ] **Refresh token** flow implemented (httpOnly cookie + transparent retry on 401)

---

## Quick Navigation

| Need to… | Jump to |
|----------|---------|
| Organize project folders | [1. Project Structure](#1-project-structure--layering-critical) |
| Manage config + secrets | [2. Configuration](#2-configuration--environment-critical) |
| Handle errors properly | [3. Error Handling](#3-error-handling--resilience-high) |
| Write database code | [4. Database Access Patterns](#4-database-access-patterns-high) |
| Set up API client from frontend | [5. API Client Patterns](#5-api-client-patterns-medium) |
| Add auth middleware | [6. Auth & Middleware](#6-authentication--middleware-high) |
| Set up logging | [7. Logging & Observability](#7-logging--observability-medium-high) |
| Add background jobs | [8. Background Jobs](#8-background-jobs--async-medium) |
| Implement caching | [9. Caching](#9-caching-patterns-medium) |
| Upload files (presigned URL, multipart) | [10. File Upload Patterns](#10-file-upload-patterns-medium) |
| Add real-time features (SSE, WebSocket) | [11. Real-Time Patterns](#11-real-time-patterns-medium) |
| Handle API errors in frontend UI | [12. Cross-Boundary Error Handling](#12-cross-boundary-error-handling-medium) |
| Harden for production | [13. Production Hardening](#13-production-hardening-medium) |
| Design API endpoints | [API Design](./api-design.md) |
| Design database schema | [Database Schema](./db-schema.md) |
| Auth flow (JWT, refresh, Next.js SSR, RBAC) | [auth-flow.md](./auth-flow.md) |
| CORS, env vars, environment management | [environment-management.md](./environment-management.md) |

---

## Core Principles (7 Iron Rules)

```
1. ✅ Organize by FEATURE, not by technical layer
2. ✅ Controllers never contain business logic
3. ✅ Services never import HTTP request/response types
4. ✅ All config from env vars, validated at startup, fail fast
5. ✅ Every error is typed, logged, and returns consistent format
6. ✅ All input validated at the boundary — trust nothing from client
7. ✅ Structured JSON logging with request ID — not console.log
```

---

## Implementation Patterns

Detailed implementation guidance lives in [implementation-patterns.md](./implementation-patterns.md). Load it only when the task needs concrete backend/frontend code patterns beyond the quick workflow above.

It covers:

- Project structure, layering, and dependency injection
- Configuration, typed errors, global error handling, and resilience
- Database access, transactions, pooling, and N+1 prevention
- API clients, authentication, middleware, logging, background jobs, caching, file uploads, real-time patterns, and production hardening
- Anti-patterns and common placement/testing questions

## Reference Documents

This skill includes deep-dive references for specialized topics. Read the relevant reference when you need detailed guidance.

| Need to… | Reference |
|----------|-----------|
| Write backend tests (unit, integration, e2e, contract, performance) | [testing-strategy.md](./testing-strategy.md) |
| Validate a release before deployment (6-gate checklist) | [release-checklist.md](./release-checklist.md) |
| Choose a tech stack (language, framework, database, infra) | [technology-selection.md](./technology-selection.md) |
| Build with Django / DRF (models, views, serializers, admin) | [django-best-practices.md](./django-best-practices.md) |
| Design REST/GraphQL/gRPC endpoints (URLs, status codes, pagination) | [api-design.md](./api-design.md) |
| Design database schema, indexes, migrations, multi-tenancy | [db-schema.md](./db-schema.md) |
| Auth flow (JWT bearer, token refresh, Next.js SSR, RBAC, middleware order) | [auth-flow.md](./auth-flow.md) |
| CORS config, env vars per environment, common CORS issues | [environment-management.md](./environment-management.md) |
