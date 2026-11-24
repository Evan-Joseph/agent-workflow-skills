---
name: cloudflare
description: "用于 Cloudflare 平台开发、排障和方案审查，包括 Workers、Pages、KV、D1、R2、Durable Objects、Workers AI、Vectorize、Agents SDK、网络、安全和 IaC。"
license: Complete terms in LICENSE.txt
metadata:
  short-description: Cloudflare平台开发、生产资产门禁与DO休眠配额治理
---

# Cloudflare Platform & Production Asset Governance

统一收口 Cloudflare 边缘研发、线上生产资产防误删门禁与免费配额精算。API 限额与配置字段优先用一手文档校验，不盲信预训练旧记忆。

## 一、 生产变更安全门禁与 DO 休眠配额治理

1. **破坏性操作显式确认门禁**：执行 `wrangler delete`、`wrangler pages project delete`、`wrangler d1/kv/r2 delete`、`cloudflared tunnel delete` 或 REST `DELETE` 前，列出「精确资产名、资源类型、绑定自定义域名、最后部署时间、拟执行动作」完整影响表，获用户本回合确认后方可执行；
2. **禁止重部署已归档项目**：历史归档展示项目保持冻结，未经明确指示不运行 `wrangler deploy` 或修改 `wrangler.toml`；
3. **Durable Objects 强制休眠零计费（`28.21 DO-小时/天` 免费红线）**：免费版每日 DO 活跃时长限额 `101,562.5s`（`~28.21 DO-h/day`）。长连接 WebSocket 协调器统一采用 Hibernation API（`this.ctx.acceptWebSocket(ws, tags)`、`this.ctx.getWebSockets(tag)` 与 `this.ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair("PING", "PONG"))`），客户端文本 `"PING"` 间隔 `>= 45s`，确保空闲连接零活跃时长计费；
4. **严格区分 `wrangler pages deploy` 与 `wrangler deploy`**：部署前核对项目目录结构（Pages 静态产物/`_worker.js` vs 独立 Worker `main` 入口），防止混调；
5. **部署后 `HTTP 200` 实测门禁**：部署或迁移域名后执行 `curl -ILs` 确认生产端点返回 `HTTP 200`（防止 `HTTP 522` 或 `HTTP 403 Error 1014` 悬空 CNAME），并按需更新 Service Worker 缓存版本。

### 一键只读健康度与 24h 配额巡检（`homebrew-stdlib`）
```bash
python3 $HOME/.agents/skills/cloudflare/scripts/cf_health_and_quota.py
python3 $HOME/.agents/skills/cloudflare/scripts/cf_health_and_quota.py --endpoints-only --json
```

## 二、 一手文档检索与核心组件按需加载

1. **最新规范查证优先级**：`context7` MCP / `developers.cloudflare.com` 官方文档 > 本地 `node_modules/wrangler/config-schema.json` & `@cloudflare/workers-types` > 静态参考文件。
2. **高频专项指南（按需只读命中的一项）**：
   - Workers 架构、流式响应、绑定与可观测性：[`references/components/workers-best-practices/guide.md`](./references/components/workers-best-practices/guide.md)
   - `wrangler` 命令、`wrangler.jsonc`、本地调试与发布：[`references/components/wrangler/guide.md`](./references/components/wrangler/guide.md)
   - Durable Objects、SQLite 存储、Alarms 与休眠 WebSocket：[`references/components/durable-objects/guide.md`](./references/components/durable-objects/guide.md)
   - Sandbox SDK 容器代码执行：[`references/components/sandbox-sdk/guide.md`](./references/components/sandbox-sdk/guide.md)
   - 全产品（KV / D1 / R2 / Queues / Vectorize / Tunnel / WAF / Turnstile / IaC 等 50+ 服务）选型树与参考路径索引：[`references/product-catalog-and-trees.md`](./references/product-catalog-and-trees.md)
