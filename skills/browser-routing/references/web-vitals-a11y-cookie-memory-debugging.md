# Web Vitals (LCP)、无障碍 (A11y)、Cookie 鉴权与内存泄漏诊断手册（基于 9223 中继与 Playwright）

> 本手册收拢自 Chrome DevTools 诊断规范，并适配本机 `${CDP_RELAY_HOST}` 持久 CDP 守护中继与无头 Playwright 沙盒（严禁直连 `9222` 端口或启动独立 `chrome-devtools-mcp`）。

---

## 一、 Largest Contentful Paint (LCP) 四阶段拆解与优化

LCP 衡量首屏最大图像或文本块的渲染耗时（`<= 2.5s` 优秀，`2.5–4.0s` 待改进，`> 4.0s` 差）。任何页面的 LCP 均严格拆解为四个不重叠的连续子阶段：

| 子阶段 | 理想占比 | 物理含义 | 核心优化策略 |
| :--- | :--- | :--- | :--- |
| **1. TTFB (Time to First Byte)** | `~40%` | 导航开始 → 收到首字节 HTML | 减少重定向、优化服务端响应、开启 CDN 边缘缓存与 `bfcache` |
| **2. Resource Load Delay** | `<10%` | TTFB → 浏览器开始下载 LCP 资源 | **严禁对首屏 LCP 图片加 `loading="lazy"`**；避免用 JS/CSS 延迟加载首屏图；添加 `<link rel="preload" fetchpriority="high">` 与 `<img fetchpriority="high">` |
| **3. Resource Load Duration** | `~40%` | LCP 资源下载耗时 | 采用 WebP/AVIF 与响应式 `srcset`、CDN 分发、字体使用 `font-display: swap` |
| **4. Element Render Delay** | `<10%` | LCP 资源下载完成 → 实际渲染上屏 | 内联首屏关键 CSS、推迟非关键同步 `<script>`、拆分阻塞主线程的长任务、采用 SSR |

### 9223 / Playwright 采集 LCP 元素与阶段耗时代码片段
通过 `POST ${CDP_RELAY_URL}/eval` 或 Playwright `page.evaluate()` 执行：
```javascript
() => new Promise((resolve) => {
  const nav = performance.getEntriesByType('navigation')[0];
  const ttfb = nav ? nav.responseStart : 0;
  new PerformanceObserver((list) => {
    const entries = list.getEntries();
    const last = entries[entries.length - 1];
    if (!last) return resolve({ error: 'No LCP entry' });
    const res = last.url ? performance.getEntriesByName(last.url)[0] : null;
    const loadDelay = res ? Math.max(0, res.requestStart - ttfb) : 0;
    const loadDuration = res ? Math.max(0, res.responseEnd - res.requestStart) : 0;
    const renderDelay = Math.max(0, last.startTime - (res ? res.responseEnd : ttfb));
    resolve({
      lcpMs: Math.round(last.startTime),
      tag: last.element ? last.element.tagName : null,
      url: last.url || '(text element)',
      subpartsMs: {
        ttfb: Math.round(ttfb),
        resourceLoadDelay: Math.round(loadDelay),
        resourceLoadDuration: Math.round(loadDuration),
        elementRenderDelay: Math.round(renderDelay),
      },
    });
  }).observe({ type: 'largest-contentful-paint', buffered: true });
})
```

---

## 二、 无障碍 (A11y) 语义树、焦点与点击热区审计

1. **语义树优先于 DOM 视觉隐藏**：`opacity: 0` 与 `display: none` / `aria-hidden="true"` 在屏幕阅读器中的暴露行为完全不同。使用 `agent-browser snapshot -i` 或 Playwright `page.locator('body').ariaSnapshot()` 检查真实无障碍树。
2. **孤儿表单控件与点击热区（Tap Targets）一键排查脚本**：
   ```javascript
   () => {
     const orphanedInputs = [...document.querySelectorAll('input:not([type="hidden"]), select, textarea')]
       .filter(el => !el.labels?.length && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
       .map(el => ({ tag: el.tagName, name: el.name || el.id || el.placeholder }));
     const smallTargets = [...document.querySelectorAll('button, a, [role="button"], input[type="checkbox"], input[type="radio"]')]
       .map(el => ({ text: (el.innerText || el.getAttribute('aria-label') || '').slice(0, 30), rect: el.getBoundingClientRect() }))
       .filter(x => x.rect.width > 0 && x.rect.height > 0 && (x.rect.width < 44 || x.rect.height < 44));
     return { orphanedInputs, smallTargetsCount: smallTargets.length, smallTargets: smallTargets.slice(0, 15) };
   }
   ```
3. **键盘焦点流与模态框焦点捕获（Focus Trap）**：使用 `Page.dispatchKeyEvent` 或 Playwright `page.keyboard.press('Tab')` 验证焦点是否移入弹窗且不会逃逸至背景层。

---

## 三、 Cookie、Session 状态与 401/403 鉴权诊断

1. **`HttpOnly` 与客户端 `cookieStore` 边界**：
   - 标记为 `HttpOnly` 的 Cookie **无法**通过 `document.cookie` 或 `await cookieStore.getAll()` 读取或删除（JS 删除会静默失败）。
   - 检查或导出包含 `HttpOnly` 的完整 Cookie 必须通过 `${CDP_RELAY_HOST}/cdp` 调用原生 CDP：
     ```bash
     curl -s -X POST ${CDP_RELAY_URL}/cdp -d '{"method":"Network.getCookies","params":{"urls":["https://target.com"]}}'
     ```
2. **401 / 403 / 302 鉴权丢失五大根因排查表**：
   - **Path 不匹配**：`Set-Cookie` 指定了 `Path=/api`，而前端请求发往 `/v1/user`；
   - **Domain 跨子域隔离**：`Domain=auth.example.com` 导致 `app.example.com` 无法携带；
   - **Secure 标志在 HTTP 下被拒**：本地 `http://` 调试时后端下发了 `Secure` 属性（`localhost` 例外，但自定义局域网 IP 会被浏览器丢弃）；
   - **SameSite 拦截**：跨站跳转下 `SameSite=Strict` 不发送；`SameSite=None` 未同时携带 `Secure` 被现代浏览器直接拒绝；
   - **过期时间 (`Expires` / `Max-Age`)**：服务端时钟偏移导致落盘即过期。

---

## 四、 前端与 Node.js 内存泄漏 (Memory Leak) 诊断流程

1. **三态快照对比法（Baseline → Action ×10 → Reverted Target）**：
   - 先在初始状态采集 Heap Snapshot 1（Baseline）；
   - 重复执行疑似泄漏的交互（如打开/关闭弹窗、切换路由）10 次并回到初始视图，触发 GC（CDP `HeapProfiler.collectGarbage`）后采集 Snapshot 2；
   - 对比两份快照的 Delta，重点排查：
     - `Detached HTMLDivElement / Detached DOM tree`（DOM 节点已从文档树移除，但被全局数组、未清理的 `ResizeObserver`/`IntersectionObserver` 或闭包引用保留）；
     - 未解绑的 Event Listeners（`window.addEventListener` 在组件卸载时未 `removeEventListener`）；
     - 无限增长的全局 `Map` / `Set` 缓存。
2. **禁止直接用 LLM 读取原始 `.heapsnapshot` 大文件**：`.heapsnapshot` 动辄数十 MB，必须用 Python/Node 脚本解析 JSON 的 `nodes`/`edges`/`strings` 数组提取增长 Top 10 构造函数及 Retaining Paths。
