# Security Finding Four-Element Verification Gate (漏洞发现四要素实证门禁)

所有从 ARTEX (`artex_cli.py findings`) 提取或白盒源码审计产出的候选安全发现，在标记为有效漏洞（`confirmed`）或进入人工报送材料前，**必须逐条通过以下四要素闭环核验**。缺失任一要素的猜测性报告一律降级为 `unverified_lead` 或直接淘汰，杜绝 LLM 幻觉误报。

---

## 一、 四要素硬性门槛 (`Trust Boundary -> Affected Principal -> Concrete Reproduction -> Minimal Fix`)

### 1. Trust Boundary（信任边界跨越）
- **核心问题**：输入源位于哪一信任域，越过了哪一道服务端强制校验边界？
- **必须指明**：
  - 入口点精确位置（HTTP 路由 `METHOD /path`、RPC 方法名或源码 `file:line`）；
  - 不可信控制面（未认证匿名调用方、低权限普通租户 `User A`、受控 Webhook 回调或跨源页面）；
  - 失效的守卫机制（如中间件漏挂载鉴权、SQL 拼接未参数化、反序列化未限制类型、路径拼接未在 `filepath.Clean` 后校验根目录前缀）。
- **直接淘汰情形**：要求攻击者本身已具备管理员口令、宿主机本地 Shell、环境变量写权限或数据库直连权限才能触发的“自攻击”链路。

### 2. Affected Principal（受损主体与真实安全影响）
- **核心问题**：攻击成功后，哪类真实主体（Principal）的机密性、完整性或可用性受损？
- **必须指明**：
  - 受损对象（其他租户私密数据、平台服务端凭据、任意用户会话接管、内网管理平面）；
  - 可量化的实际危害（而非泛泛套话“可能导致信息泄露或安全风险”）。
- **直接淘汰情形**：
  - 公开设计即对外暴露的版本号、静态前端路由表、公开 API Schema、无敏感字段的健康检查 `/health`；
  - 缺少 CSRF Token 但接口本身强制校验自定义 Header + `Authorization: Bearer`（无 Cookie 自动携带条件）；
  - 纯客户端 Self-XSS（无法跨会话投递给其他用户）。

### 3. Concrete Reproduction（确定性最小复现证据）
- **核心问题**：能否在不做破坏性操作的前提下，给出 100% 可复现的请求/响应或本地 Fixture 证据？
- **必须具备**：
  - 精确的原始 HTTP 请求报文 / CLI 复现步骤（脱敏处理真实生产 Token）及对应的服务端响应状态码与关键字段；
  - 关联的 ARTEX 流量记录引用（`traffic_refs`）或源码调用链追踪（`Entry -> Sink` 完整路径，确认中间无隐藏全局 Filter 拦截）；
  - **合规边界**：复现探针严格遵循无害只读验证（如越权仅对比自己测试双账号 `Account A` vs `Account B`，命令/SQL 边界仅用布尔/时间或本地容器 Fixture 验证，严禁拉取真实第三方生产用户隐私数据或执行破坏性写入）。

### 4. Minimal Fix（最小侵入修复建议）
- **核心问题**：如何在不推翻业务架构的前提下，于信任边界处用最小增量消除根因？
- **必须给出**：
  - 定位到具体函数/中间件层级的确定性修复方案（例如：在查询条件强制绑定会话态 `WHERE org_id = ctx.OrgID`、改用参数化预编译语句、限制 `net.DialContext` 阻断 `127.0.0.0/8`、`198.51.100.0/8`、`169.254.169.254` 等内网段）。

---

## 二、 高频误报一票否决清单（Auto-Reject Checklist）

遇到以下典型扫描器/大模型幻觉噪声时，无需进入报送流程，直接标记淘汰：

1. **纯响应头提示类噪声**：单独缺失 `X-Frame-Options`、`Content-Security-Policy`、`Strict-Transport-Security` 或 `Server` Banner 版本回显，且无实际可串联利用链；
2. **预期公开特性误判**：注册/登录接口存在合理限流下的状态提示、公开文档中心、OAuth `.well-known/openid-configuration` 元数据；
3. **死代码与测试桩**：仅存在于 `*_test.go`、`examples/`、未挂载路由或编译期未启用的构建标签分支；
4. **前端校验缺失但后端已拦截**：仅凭前端 Bundle 未做权限隐藏就断言越权，实测后端接口返回 `401/403` 的情形。
