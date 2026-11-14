# Cloudflare 全产品选型决策树与参考目录索引 (`product-catalog-and-trees.md`)

> 所有具体目录均位于 `$HOME/.agents/skills/cloudflare/references/` 下，按需渐进加载。

## 1. 场景快速选型树

- **运行代码 (Compute)**：
  - 边缘无状态函数 / API -> `references/workers/` + `references/components/workers-best-practices/guide.md`
  - 静态前端 / 全栈 Pages 部署 -> `references/pages/` + `references/pages-functions/`
  - 强一致单实体状态与长连接协同 -> `references/components/durable-objects/guide.md`
  - 多步长周期编排 -> `references/workflows/`
  - 容器 / 沙盒代码执行 -> `references/containers/` + `references/components/sandbox-sdk/guide.md`
  - 定时任务 -> `references/cron-triggers/`
- **数据存储 (Storage)**：
  - 键值配置/缓存 -> `references/kv/`
  - 关系型 SQLite -> `references/d1/`（外部 Postgres/MySQL 加速 -> `references/hyperdrive/`）
  - S3 兼容对象存储 -> `references/r2/`（目录/SQL -> `references/r2-data-catalog/`、`references/r2-sql/`）
  - 异步消息队列 -> `references/queues/`；流式入湖 -> `references/pipelines/`
  - 向量检索 -> `references/vectorize/`；机密管理 -> `references/secrets-store/`
- **AI 与智能体 (AI / Agents)**：
  - 边缘推理 -> `references/workers-ai/`；有状态 Agent -> `references/agents-sdk/`；多源 AI 网关 -> `references/ai-gateway/`；站点 AI 搜索 -> `references/ai-search/`
- **网络、安全与媒体 (Network / Security / Media)**：
  - 内网穿透 -> `references/tunnel/`；TCP/UDP -> `references/spectrum/`；WebRTC -> `references/turn/` / `references/realtimekit/` / `references/realtime-sfu/`
  - 防护与验证 -> `references/waf/`、`references/ddos/`、`references/bot-management/`、`references/api-shield/`、`references/turnstile/`
  - 媒体与渲染 -> `references/images/`、`references/stream/`、`references/browser-rendering/`
- **工具、遥测与 IaC (Tooling & IaC)**：
  - CLI 与配置 -> `references/components/wrangler/guide.md`、`references/miniflare/`、`references/workerd/`、`references/bindings/`、`references/static-assets/`
  - 日志与统计 -> `references/observability/`、`references/graphql-api/`、`references/analytics-engine/`、`references/web-analytics/`、`references/tail-workers/`
  - 特性开关与邮件 -> `references/flagship/`、`references/email-routing/`、`references/email-workers/`
  - IaC 与 REST -> `references/pulumi/`、`references/terraform/`、`references/api/`
