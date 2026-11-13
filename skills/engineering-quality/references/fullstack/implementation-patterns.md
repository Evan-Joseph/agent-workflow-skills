# Full-Stack Implementation Patterns

## 1. Project Structure & Layering (CRITICAL)

### Feature-First Organization

```
✅ Feature-first                    ❌ Layer-first
src/                                src/
  orders/                             controllers/
    order.controller.ts                 order.controller.ts
    order.service.ts                    user.controller.ts
    order.repository.ts               services/
    order.dto.ts                        order.service.ts
    order.test.ts                       user.service.ts
  users/                              repositories/
    user.controller.ts                  ...
    user.service.ts
  shared/
    database/
    middleware/
```

### Three-Layer Architecture

```
Controller (HTTP) → Service (Business Logic) → Repository (Data Access)
```

| Layer | Responsibility | ❌ Never |
|-------|---------------|---------|
| Controller | Parse request, validate, call service, format response | Business logic, DB queries |
| Service | Business rules, orchestration, transaction mgmt | HTTP types (req/res), direct DB |
| Repository | Database queries, external API calls | Business logic, HTTP types |

### Dependency Injection (All Languages)

**TypeScript:**
```typescript
class OrderService {
  constructor(
    private readonly orderRepo: OrderRepository,    // ✅ injected interface
    private readonly emailService: EmailService,
  ) {}
}
```

**Python:**
```python
class OrderService:
    def __init__(self, order_repo: OrderRepository, email_service: EmailService):
        self.order_repo = order_repo                 # ✅ injected
        self.email_service = email_service
```

**Go:**
```go
type OrderService struct {
    orderRepo    OrderRepository                      // ✅ interface
    emailService EmailService
}

func NewOrderService(repo OrderRepository, email EmailService) *OrderService {
    return &OrderService{orderRepo: repo, emailService: email}
}
```

---

## 2. Configuration & Environment (CRITICAL)

### Centralized, Typed, Fail-Fast

**TypeScript:**
```typescript
const config = {
  port: parseInt(process.env.PORT || '3000', 10),
  database: { url: requiredEnv('DATABASE_URL'), poolSize: intEnv('DB_POOL_SIZE', 10) },
  auth: { jwtSecret: requiredEnv('JWT_SECRET'), expiresIn: process.env.JWT_EXPIRES_IN || '1h' },
} as const;

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var: ${name}`);  // fail fast
  return value;
}
```

**Python:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str                        # required — app won't start without it
    jwt_secret: str                          # required
    port: int = 3000                         # optional with default
    db_pool_size: int = 10
    class Config:
        env_file = ".env"

settings = Settings()                        # fails fast if DATABASE_URL missing
```

### Rules

```
✅ All config via environment variables (Twelve-Factor)
✅ Validate required vars at startup — fail fast
✅ Type-cast at config layer, not at usage sites
✅ Commit .env.example with dummy values

❌ Never hardcode secrets, URLs, or credentials
❌ Never commit .env files
❌ Never scatter process.env / os.environ throughout code
```

---

## 3. Error Handling & Resilience (HIGH)

### Typed Error Hierarchy

```typescript
// Base (TypeScript)
class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number,
    public readonly isOperational: boolean = true,
  ) { super(message); }
}
class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(`${resource} not found: ${id}`, 'NOT_FOUND', 404);
  }
}
class ValidationError extends AppError {
  constructor(public readonly errors: FieldError[]) {
    super('Validation failed', 'VALIDATION_ERROR', 422);
  }
}
```

```python
# Base (Python)
class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int):
        self.message, self.code, self.status_code = message, code, status_code

class NotFoundError(AppError):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} not found: {id}", "NOT_FOUND", 404)
```

### Global Error Handler

```typescript
// TypeScript (Express)
app.use((err, req, res, next) => {
  if (err instanceof AppError && err.isOperational) {
    return res.status(err.statusCode).json({
      title: err.code, status: err.statusCode,
      detail: err.message, request_id: req.id,
    });
  }
  logger.error('Unexpected error', { error: err.message, stack: err.stack, request_id: req.id });
  res.status(500).json({ title: 'Internal Error', status: 500, request_id: req.id });
});
```

### Rules

```
✅ Typed, domain-specific error classes
✅ Global error handler catches everything
✅ Operational errors → structured response
✅ Programming errors → log + generic 500
✅ Retry transient failures with exponential backoff

❌ Never catch and ignore errors silently
❌ Never return stack traces to client
❌ Never throw generic Error('something')
```

---

## 4. Database Access Patterns (HIGH)

### Migrations Always

```bash
# TypeScript (Prisma)           # Python (Alembic)              # Go (golang-migrate)
npx prisma migrate dev          alembic revision --autogenerate  migrate -source file://migrations
npx prisma migrate deploy       alembic upgrade head             migrate -database $DB up
```

```
✅ Schema changes via migrations, never manual SQL
✅ Migrations must be reversible
✅ Review migration SQL before production
❌ Never modify production schema manually
```

### N+1 Prevention

```typescript
// ❌ N+1: 1 query + N queries
const orders = await db.order.findMany();
for (const o of orders) { o.items = await db.item.findMany({ where: { orderId: o.id } }); }

// ✅ Single JOIN query
const orders = await db.order.findMany({ include: { items: true } });
```

### Transactions for Multi-Step Writes

```typescript
await db.$transaction(async (tx) => {
  const order = await tx.order.create({ data: orderData });
  await tx.inventory.decrement({ productId, quantity });
  await tx.payment.create({ orderId: order.id, amount });
});
```

### Connection Pooling

Pool size = `(CPU cores × 2) + spindle_count` (start with 10-20). Always set connection timeout. Use PgBouncer for serverless.

---

## 5. API Client Patterns (MEDIUM)

The "glue layer" between frontend and backend. Choose the approach that fits your team and stack.

### Option A: Typed Fetch Wrapper (Simple, No Dependencies)

```typescript
// lib/api-client.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://<LOCAL_HOST>:3001';

class ApiError extends Error {
  constructor(public status: number, public body: any) {
    super(body?.detail || body?.message || `API error ${status}`);
  }
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();  // from cookie / memory / context

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  get: <T>(path: string) => api<T>(path),
  post: <T>(path: string, data: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(data) }),
  put: <T>(path: string, data: unknown) => api<T>(path, { method: 'PUT', body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: <T>(path: string) => api<T>(path, { method: 'DELETE' }),
};
```

### Option B: React Query + Typed Client (Recommended for React)

```typescript
// hooks/use-orders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

interface Order { id: string; total: number; status: string; }
interface CreateOrderInput { items: { productId: string; quantity: number }[] }

export function useOrders() {
  return useQuery({
    queryKey: ['orders'],
    queryFn: () => apiClient.get<{ data: Order[] }>('/api/orders'),
    staleTime: 1000 * 60,  // 1 min
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateOrderInput) =>
      apiClient.post<{ data: Order }>('/api/orders', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}

// Usage in component:
function OrdersPage() {
  const { data, isLoading, error } = useOrders();
  const createOrder = useCreateOrder();
  if (isLoading) return <Skeleton />;
  if (error) return <ErrorBanner error={error} />;
  // ...
}
```

### Option C: tRPC (Same Team Owns Both Sides)

```typescript
// server: trpc/router.ts
export const appRouter = router({
  orders: router({
    list: publicProcedure.query(async () => {
      return db.order.findMany({ include: { items: true } });
    }),
    create: protectedProcedure
      .input(z.object({ items: z.array(orderItemSchema) }))
      .mutation(async ({ input, ctx }) => {
        return orderService.create(ctx.user.id, input);
      }),
  }),
});
export type AppRouter = typeof appRouter;

// client: automatic type safety, no code generation
const { data } = trpc.orders.list.useQuery();
const createOrder = trpc.orders.create.useMutation();
```

### Option D: OpenAPI Generated Client (Public / Multi-Consumer APIs)

```bash
npx openapi-typescript-codegen \
  --input http://<LOCAL_HOST>:3001/api/openapi.json \
  --output src/generated/api \
  --client axios
```

### Decision: Which API Client?

| Approach | When | Type Safety | Effort |
|----------|------|-------------|--------|
| Typed fetch wrapper | Simple apps, small teams | Manual types | Low |
| React Query + fetch | React apps, server state | Manual types | Medium |
| tRPC | Same team, TypeScript both sides | Automatic | Low |
| OpenAPI generated | Public API, multi-consumer | Automatic | Medium |
| GraphQL codegen | GraphQL APIs | Automatic | Medium |

---

## 6. Authentication & Middleware (HIGH)

> **Full reference:** [auth-flow.md](auth-flow.md) — JWT bearer flow, automatic token refresh, Next.js server-side auth, RBAC pattern, backend middleware order.

### Standard Middleware Order

```
Request → 1.RequestID → 2.Logging → 3.CORS → 4.RateLimit → 5.BodyParse
       → 6.Auth → 7.Authz → 8.Validation → 9.Handler → 10.ErrorHandler → Response
```

### JWT Rules

```
✅ Short expiry access token (15min) + refresh token (server-stored)
✅ Minimal claims: userId, roles (not entire user object)
✅ Rotate signing keys periodically

❌ Never store tokens in localStorage (XSS risk)
❌ Never pass tokens in URL query params
```

### RBAC Pattern

```typescript
function authorize(...roles: Role[]) {
  return (req, res, next) => {
    if (!req.user) throw new UnauthorizedError();
    if (!roles.some(r => req.user.roles.includes(r))) throw new ForbiddenError();
    next();
  };
}
router.delete('/users/:id', authenticate, authorize('admin'), deleteUser);
```

### Auth Token Automatic Refresh

```typescript
// lib/api-client.ts — transparent refresh on 401
async function apiWithRefresh<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    return await api<T>(path, options);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      const refreshed = await api<{ accessToken: string }>('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',  // send httpOnly cookie
      });
      setAuthToken(refreshed.accessToken);
      return api<T>(path, options);  // retry
    }
    throw err;
  }
}
```

---

## 7. Logging & Observability (MEDIUM-HIGH)

### Structured JSON Logging

```typescript
// ✅ Structured — parseable, filterable, alertable
logger.info('Order created', {
  orderId: order.id, userId: user.id, total: order.total,
  items: order.items.length, duration_ms: Date.now() - startTime,
});
// Output: {"level":"info","msg":"Order created","orderId":"ord_123",...}

// ❌ Unstructured — useless at scale
console.log(`Order created for user ${user.id} with total ${order.total}`);
```

### Log Levels

| Level | When | Production? |
|-------|------|------------|
| error | Requires immediate attention | ✅ Always |
| warn | Unexpected but handled | ✅ Always |
| info | Normal operations, audit trail | ✅ Always |
| debug | Dev troubleshooting | ❌ Dev only |

### Rules

```
✅ Request ID in every log entry (propagated via middleware)
✅ Log at layer boundaries (request in, response out, external call)
❌ Never log passwords, tokens, PII, or secrets
❌ Never use console.log in production code
```

---

## 8. Background Jobs & Async (MEDIUM)

### Rules

```
✅ All jobs must be IDEMPOTENT (same job running twice = same result)
✅ Failed jobs → retry (max 3) → dead letter queue → alert
✅ Workers run as SEPARATE processes (not threads in API server)

❌ Never put long-running tasks in request handlers
❌ Never assume job runs exactly once
```

### Idempotent Job Pattern

```typescript
async function processPayment(data: { orderId: string }) {
  const order = await orderRepo.findById(data.orderId);
  if (order.paymentStatus === 'completed') return;  // already processed
  await paymentGateway.charge(order);
  await orderRepo.updatePaymentStatus(order.id, 'completed');
}
```

---

## 9. Caching Patterns (MEDIUM)

### Cache-Aside (Lazy Loading)

```typescript
async function getUser(id: string): Promise<User> {
  const cached = await redis.get(`user:${id}`);
  if (cached) return JSON.parse(cached);

  const user = await userRepo.findById(id);
  if (!user) throw new NotFoundError('User', id);

  await redis.set(`user:${id}`, JSON.stringify(user), 'EX', 900);  // 15min TTL
  return user;
}
```

### Rules

```
✅ ALWAYS set TTL — never cache without expiry
✅ Invalidate on write (delete cache key after update)
✅ Use cache for reads, never for authoritative state

❌ Never cache without TTL (stale data is worse than slow data)
```

| Data Type | Suggested TTL |
|-----------|---------------|
| User profile | 5-15 min |
| Product catalog | 1-5 min |
| Config / feature flags | 30-60 sec |
| Session | Match session duration |

---

## 10. File Upload Patterns (MEDIUM)

### Option A: Presigned URL (Recommended for Large Files)

```
Client → GET /api/uploads/presign?filename=photo.jpg&type=image/jpeg
Server → { uploadUrl: "https://s3.../presigned", fileKey: "uploads/abc123.jpg" }
Client → PUT uploadUrl (direct to S3, bypasses your server)
Client → POST /api/photos { fileKey: "uploads/abc123.jpg" }  (save reference)
```

**Backend:**
```typescript
app.get('/api/uploads/presign', authenticate, async (req, res) => {
  const { filename, type } = req.query;
  const key = `uploads/${crypto.randomUUID()}-${filename}`;
  const url = await s3.getSignedUrl('putObject', {
    Bucket: process.env.S3_BUCKET, Key: key,
    ContentType: type, Expires: 300,  // 5 min
  });
  res.json({ uploadUrl: url, fileKey: key });
});
```

**Frontend:**
```typescript
async function uploadFile(file: File) {
  const { uploadUrl, fileKey } = await apiClient.get<PresignResponse>(
    `/api/uploads/presign?filename=${file.name}&type=${file.type}`
  );
  await fetch(uploadUrl, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } });
  return apiClient.post('/api/photos', { fileKey });
}
```

### Option B: Multipart (Small Files < 10MB)

```typescript
// Frontend
const formData = new FormData();
formData.append('file', file);
formData.append('description', 'Profile photo');
const res = await fetch('/api/upload', { method: 'POST', body: formData });
// Note: do NOT set Content-Type header — browser sets boundary automatically
```

### Decision

| Method | File Size | Server Load | Complexity |
|--------|-----------|-------------|------------|
| Presigned URL | Any (recommended > 5MB) | None (direct to storage) | Medium |
| Multipart | < 10MB | High (streams through server) | Low |
| Chunked / Resumable | > 100MB | Medium | High |

---

## 11. Real-Time Patterns (MEDIUM)

### Option A: Server-Sent Events (SSE) — One-Way Server → Client

Best for: notifications, live feeds, streaming AI responses.

**Backend (Express):**
```typescript
app.get('/api/events', authenticate, (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });
  const send = (event: string, data: unknown) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };
  const unsubscribe = eventBus.subscribe(req.user.id, (event) => {
    send(event.type, event.payload);
  });
  req.on('close', () => unsubscribe());
});
```

**Frontend:**
```typescript
function useServerEvents(userId: string) {
  useEffect(() => {
    const source = new EventSource(`/api/events?userId=${userId}`);
    source.addEventListener('notification', (e) => {
      showToast(JSON.parse(e.data).message);
    });
    source.onerror = () => { source.close(); setTimeout(() => /* reconnect */, 3000); };
    return () => source.close();
  }, [userId]);
}
```

### Option B: WebSocket — Bidirectional

Best for: chat, collaborative editing, gaming.

**Backend (ws library):**
```typescript
import { WebSocketServer } from 'ws';
const wss = new WebSocketServer({ server: httpServer, path: '/ws' });
wss.on('connection', (ws, req) => {
  const userId = authenticateWs(req);
  if (!userId) { ws.close(4001, 'Unauthorized'); return; }
  ws.on('message', (raw) => handleMessage(userId, JSON.parse(raw.toString())));
  ws.on('close', () => cleanupUser(userId));
  const interval = setInterval(() => ws.ping(), 30000);
  ws.on('pong', () => { /* alive */ });
  ws.on('close', () => clearInterval(interval));
});
```

**Frontend:**
```typescript
function useWebSocket(url: string) {
  const [ws, setWs] = useState<WebSocket | null>(null);
  useEffect(() => {
    const socket = new WebSocket(url);
    socket.onopen = () => setWs(socket);
    socket.onclose = () => setTimeout(() => /* reconnect */, 3000);
    return () => socket.close();
  }, [url]);
  const send = useCallback((data: unknown) => ws?.send(JSON.stringify(data)), [ws]);
  return { ws, send };
}
```

### Option C: Polling (Simplest, No Infrastructure)

```typescript
function useOrderStatus(orderId: string) {
  return useQuery({
    queryKey: ['order-status', orderId],
    queryFn: () => apiClient.get<Order>(`/api/orders/${orderId}`),
    refetchInterval: (query) => {
      if (query.state.data?.status === 'completed') return false;
      return 5000;
    },
  });
}
```

### Decision

| Method | Direction | Complexity | When |
|--------|-----------|------------|------|
| Polling | Client → Server | Low | Simple status checks, < 10 clients |
| SSE | Server → Client | Medium | Notifications, feeds, AI streaming |
| WebSocket | Bidirectional | High | Chat, collaboration, gaming |

---

## 12. Cross-Boundary Error Handling (MEDIUM)

### API Error → User-Facing Message

```typescript
// lib/error-handler.ts
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401: return 'Please log in to continue.';
      case 403: return 'You don\'t have permission to do this.';
      case 404: return 'The item you\'re looking for doesn\'t exist.';
      case 409: return 'This conflicts with an existing item.';
      case 422:
        const fields = error.body?.errors;
        if (fields?.length) return fields.map((f: any) => f.message).join('. ');
        return 'Please check your input.';
      case 429: return 'Too many requests. Please wait a moment.';
      default: return 'Something went wrong. Please try again.';
    }
  }
  if (error instanceof TypeError && error.message === 'Failed to fetch') {
    return 'Cannot connect to server. Check your internet connection.';
  }
  return 'An unexpected error occurred.';
}
```

### React Query Global Error Handler

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    mutations: { onError: (error) => toast.error(getErrorMessage(error)) },
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status < 500) return false;
        return failureCount < 3;
      },
    },
  },
});
```

### Rules

```
✅ Map every API error code to a human-readable message
✅ Show field-level validation errors next to form inputs
✅ Auto-retry on 5xx (max 3, with backoff), never on 4xx
✅ Redirect to login on 401 (after refresh attempt fails)
✅ Show "offline" banner when fetch fails with TypeError

❌ Never show raw API error messages to users ("NullPointerException")
❌ Never silently swallow errors (show toast or log)
❌ Never retry 4xx errors (client is wrong, retrying won't help)
```

### Integration Decision Tree

```
Same team owns frontend + backend?
│
├─ YES, both TypeScript
│   └─ tRPC (end-to-end type safety, zero codegen)
│
├─ YES, different languages
│   └─ OpenAPI spec → generated client (type safety via codegen)
│
├─ NO, public API
│   └─ REST + OpenAPI → generated SDKs for consumers
│
└─ Complex data needs, multiple frontends
    └─ GraphQL + codegen (flexible queries per client)

Real-time needed?
│
├─ Server → Client only (notifications, feeds, AI streaming)
│   └─ SSE (simplest, auto-reconnect, works through proxies)
│
├─ Bidirectional (chat, collaboration)
│   └─ WebSocket (need heartbeat + reconnection logic)
│
└─ Simple status polling (< 10 clients)
    └─ React Query refetchInterval (no infrastructure needed)
```

---

## 13. Production Hardening (MEDIUM)

### Health Checks

```typescript
app.get('/health', (req, res) => res.json({ status: 'ok' }));           // liveness
app.get('/ready', async (req, res) => {                                   // readiness
  const checks = {
    database: await checkDb(), redis: await checkRedis(), 
  };
  const ok = Object.values(checks).every(c => c.status === 'ok');
  res.status(ok ? 200 : 503).json({ status: ok ? 'ok' : 'degraded', checks });
});
```

### Graceful Shutdown

```typescript
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received');
  server.close();              // stop new connections
  await drainConnections();    // finish in-flight
  await closeDatabase();
  process.exit(0);
});
```

### Security Checklist

```
✅ CORS: explicit origins (never '*' in production)
✅ Security headers (helmet / equivalent)
✅ Rate limiting on public endpoints
✅ Input validation on ALL endpoints (trust nothing)
✅ HTTPS enforced
❌ Never expose internal errors to clients
```

---

## Anti-Patterns

| # | ❌ Don't | ✅ Do Instead |
|---|---------|--------------|
| 1 | Business logic in routes/controllers | Move to service layer |
| 2 | `process.env` scattered everywhere | Centralized typed config |
| 3 | `console.log` for logging | Structured JSON logger |
| 4 | Generic `Error('oops')` | Typed error hierarchy |
| 5 | Direct DB calls in controllers | Repository pattern |
| 6 | No input validation | Validate at boundary (Zod/Pydantic) |
| 7 | Catching errors silently | Log + rethrow or return error |
| 8 | No health check endpoints | `/health` + `/ready` |
| 9 | Hardcoded config/secrets | Environment variables |
| 10 | No graceful shutdown | Handle SIGTERM properly |
| 11 | Hardcode API URL in frontend | Environment variable (`NEXT_PUBLIC_API_URL`) |
| 12 | Store JWT in localStorage | Memory + httpOnly refresh cookie |
| 13 | Show raw API errors to users | Map to human-readable messages |
| 14 | Retry 4xx errors | Only retry 5xx (server failures) |
| 15 | Skip loading states | Skeleton/spinner while fetching |
| 16 | Upload large files through API server | Presigned URL → direct to S3 |
| 17 | Poll for real-time data | SSE or WebSocket |
| 18 | Duplicate types frontend + backend | Shared types, tRPC, or OpenAPI codegen |

---

## Common Issues

### Issue 1: "Where does this business rule go?"

**Rule:** If it involves HTTP (request parsing, status codes, headers) → controller. If it involves business decisions (pricing, permissions, rules) → service. If it touches the database → repository.

### Issue 2: "Service is getting too big"

**Symptom:** One service file > 500 lines with 20+ methods.

**Fix:** Split by sub-domain. `OrderService` → `OrderCreationService` + `OrderFulfillmentService` + `OrderQueryService`. Each focused on one workflow.

### Issue 3: "Tests are slow because they hit the database"

**Fix:** Unit tests mock the repository layer (fast). Integration tests use test containers or transaction rollback (real DB, still fast). Never mock the service layer in integration tests.

---
