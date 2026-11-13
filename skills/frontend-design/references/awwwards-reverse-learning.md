# Awwwards (SOTM / SOTY) 标杆站点只读逆向拆解与双轨协同规范

> **定位**：与 `Mobbin`（商业产品真实交互流与信息架构对标）构成正交双轨——`Mobbin` 锁定功能可用性与流程严密性下限，`Awwwards SOTM/SOTY` 拔高品牌叙事、流体排版张力、微交互缓动阻尼与 WebGL/View-Transitions 审美上限。

---

## 1. 「Mobbin × Awwwards」正交双轨与防错配红线

| 维度 | 轨道 A：`Mobbin`（商业产品流对标） | 轨道 B：`Awwwards SOTM / SOTY`（叙事与动效上限逆向） |
| :--- | :--- | :--- |
| **主导场景** | SaaS 控制台、工作台、Onboarding、Paywall、Settings、移动端多步任务流 | 旗舰产品官网（Landing Page）、个人学术/工程作品集（如 `portfolio.example.com`）、发布会专题页、高记忆点交互原型 |
| **核心提取物** | 信息架构（IA）、空/错/载状态完整性、表单密度、导航层级、转化漏斗 | 流体视口排版比例（Fluid Scale）、高对比表面色板、非对称阻尼缓动曲线、`Lenis + ScrollTrigger` 视差节奏、`View-Transitions` 无缝转场、局部 WebGL 焦点 |
| **融合范式** | 构建 Linear / Raycast / Vercel 级旗舰产品页时：**骨架与转化流先查 `Mobbin` 保可用性（Usability），首屏视觉锚点、排版比例与动效阻尼用 `:9223` 探针拆解 2–3 个同调性 `Awwwards SOTM/SOTY` 获奖站** |

### 五条反模式防火墙（严禁盲目搬运）
1. **禁搬强制 Preloader**：工具型界面与常规文档页严禁加入阻塞首屏交互的 2–5 秒百分比加载遮罩；
2. **禁劫持滚轮阻尼影响高频操作**：后台表格、长表单与在线测评页保持原生滚动，禁止强套重阻尼平滑滚动；
3. **禁全局接管系统光标（Custom Cursor）**：禁止隐藏系统指针或覆盖输入框/按钮原生 `cursor: pointer | text` 反馈；
4. **单页重型画布克制**：同一视口最多保留 1 个受控 DPR（`Math.min(devicePixelRatio, 2)`）且离屏自动暂停 `requestAnimationFrame` 的 WebGL/Shader 画布；
5. **强制无障碍降级**：所有提取复用的曲线与视差动画必须配齐 `@media (prefers-reduced-motion: reduce)` 瞬时或纯透明度回退。

---

## 2. 零浏览器开销选片协议（SSR 直取榜单、外链与评分）

`awwwards.com` 采用 Symfony + Stimulus 服务端渲染（SSR），经本地代理直请求返回 `HTTP 200`（无 Cloudflare Turnstile 拦截），**单次 HTTP GET 即可拿全整页 31 个获奖站点的真实上线外链与技术栈标签**：

- **核心榜单与分类直筛路由**：
  - 月度最佳（SOTM）：`https://www.awwwards.com/websites/sites_of_the_month/`
  - 年度最佳（SOTY）：`https://www.awwwards.com/websites/sites_of_the_year/`
  - 按技术/风格直筛：`/websites/gsap-animation/`、`/websites/three-js/`、`/websites/webgl/`、`/websites/typography/`、`/websites/transitions/`、`/websites/minimal/`
- **列表页卡片（`li.js-collectable`）提取规则**：
  - **内嵌模型 JSON**：读取属性 `data-collectable-model-value`（反转义 HTML 实体后 `JSON.parse`，过滤 `type === "submission"`），直取 `title`、`slug`（详情页 `/sites/${slug}`）、`tags` 数组与 `images.thumbnail`（高清图：`https://assets.awwwards.com/awards/${images.thumbnail}`）；
  - **真实上线外链（Live Site URL）**：卡片内 `a.figure-rollover__bt[data-controller="visit-count"][href^="http"]` 的 `href`；
  - **奖项期次与工作室**：`.card-site__awards .tooltip__content`（如 `Site Of The Month — Oct, 2026`）与 `.card-site__info .avatar-name__title`。
- **详情页（`/sites/<slug>`）四维评审分与六维工程分精准分离**：
  - **综合总分**：对 `.c-heading-score__note` 文本执行 `match(/[\d]+(?:\.\d+)?/)[0]`（勿用字符替换，防把上标 `<sup>/ 10</sup>` 拼入小数末尾）；
  - **双评分容器拆分**：`document.querySelectorAll('.layout-overall[data-controller="chartbar"]')` 中，`[0]` 为评审团四维分（`Design 40%` / `Usability 30%` / `Creativity 20%` / `Content 10%`），`[1]`（获 Developer Award 时存在）为工程六维分（可直接筛选 `Animations / Transitions >= 8.5` 的动效标杆）；
  - **官方色板与分模块微交互实录（Elements `.mp4`）**：正则提取 `<strong>HEX</strong>\s*#([0-9A-Fa-f]{6})` 与 `https://assets.awwwards.com/awards/element/\d{4}/\d{2}/[a-z0-9]+\.mp4`（单点菜单开合、滚轴转场高清录屏）。

---

## 3. `:9223` 标杆站点排版与动效 DNA 静默提取工作流

遵守 `browser-routing` 零焦点抢占契约，统一在后台受管分组 `task: "probe-awwwards"` 中执行，收尾强制销毁并回读核验：

```bash
# 1. 后台静默打开目标获奖上线站点（自动开启焦点仿真与折叠标签组）
curl -s -X POST ${CDP_RELAY_URL}/new -d '{"url":"https://landonorris.com/","task":"probe-awwwards","reuse":true}'

# 2. （可选）分段预滚动触发懒加载与 ScrollTrigger 注册后回到顶部
curl -s -X POST ${CDP_RELAY_URL}/eval -d '{"task":"probe-awwwards","expression":"(async()=>{for(let r of [0.35,0.7,1,0]){scrollTo(0,document.body.scrollHeight*r);await new Promise(ok=>setTimeout(ok,350));}return true;})()"}'

# 3. 执行下方「排版令牌 + CSS 变量 + 缓动曲线 + 滚动引擎」一键只读探针
# 4. 提取完毕立即一键清理并回读确认 probe-awwwards 归零
curl -s -X POST ${CDP_RELAY_URL}/cleanup -d '{"task":"probe-awwwards"}'
curl -s ${CDP_RELAY_URL}/tabs
```

### 一键只读提取 JS 探针（兼容 `:9223 /eval` 与 Playwright `page.evaluate`）
```javascript
(() => {
  const g = globalThis;
  const roles = { h1: 'h1, [class*="hero" i] h1', h2: 'h2', body: 'p, main li', interactive: 'button, nav a', mono: 'code, pre' };
  const roleTokens = {};
  for (const [role, sel] of Object.entries(roles)) {
    const el = [...document.querySelectorAll(sel)].find(n => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    if (!el) continue;
    const cs = getComputedStyle(el);
    roleTokens[role] = { fontFamily: cs.fontFamily, fontSize: cs.fontSize, fontWeight: cs.fontWeight, lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing };
  }
  const rootCS = getComputedStyle(document.documentElement);
  const customProps = { colors: {}, typography: {}, motion: {}, layout: {} };
  const easings = new Set(), fluidClamps = new Set();
  let hasViewTransition = false;
  const walk = (rules) => {
    for (const rule of rules) {
      try {
        if (rule.cssText && /@view-transition|::view-transition/.test(rule.cssText)) hasViewTransition = true;
        if (rule.cssRules) walk(rule.cssRules);
        const st = rule.style; if (!st) continue;
        const sel = rule.selectorText || '';
        const isRoot = sel === ':root' || sel === 'html' || sel.includes(':root');
        for (let i = 0; i < st.length; i++) {
          const p = st[i], v = st.getPropertyValue(p).trim();
          if (isRoot && p.startsWith('--')) {
            const rv = (rootCS.getPropertyValue(p) || v).trim();
            if (/color|bg|surface|accent|ink/i.test(p) && Object.keys(customProps.colors).length < 20) customProps.colors[p] = rv;
            else if (/font|text|leading|tracking/i.test(p) && Object.keys(customProps.typography).length < 15) customProps.typography[p] = rv;
            else if (/ease|cubic|bezier|duration|transition/i.test(p) && Object.keys(customProps.motion).length < 15) customProps.motion[p] = rv;
            else if (/space|gap|pad|radius|fluid|container/i.test(p) && Object.keys(customProps.layout).length < 15) customProps.layout[p] = rv;
          }
          (v.match(/cubic-bezier\([^)]+\)|linear\([^)]+\)/g) || []).forEach(c => easings.add(c));
          if ((p === 'font-size' || p === 'padding' || p === 'gap') && v.includes('clamp(') && fluidClamps.size < 12) fluidClamps.add(`${sel} { ${p}: ${v} }`);
          if (p === 'view-transition-name' && v !== 'none') hasViewTransition = true;
        }
      } catch {}
    }
  };
  for (const s of [...document.styleSheets]) { try { if (s.cssRules) walk(s.cssRules); } catch {} }
  const stPlugin = g.ScrollTrigger || g.gsap?.plugins?.ScrollTrigger;
  const stAll = stPlugin?.getAll?.() || [];
  const lenis = g.lenis || g.__lenis;
  return {
    url: location.href,
    fonts: [...document.fonts].filter(f => f.status === 'loaded').slice(0, 10).map(f => `${f.family} (${f.weight})`),
    roleTokens,
    customProps,
    fluidClamps: [...fluidClamps],
    easings: [...easings].slice(0, 20),
    gsap: g.gsap ? { version: g.gsap.version, tweens: (g.gsap.globalTimeline?.getChildren?.(true, true, true) || []).length } : null,
    scrollTrigger: stAll.length ? { total: stAll.length, scrubCount: stAll.filter(t => Boolean(t?.vars?.scrub)).length, pinCount: stAll.filter(t => Boolean(t?.vars?.pin)).length } : null,
    smoothScroll: (lenis || document.documentElement.classList.contains('lenis')) ? { engine: 'lenis', lerp: lenis?.options?.lerp ?? null } : 'native',
    viewTransitions: hasViewTransition || Boolean(document.querySelector('meta[name="view-transition"]')),
    webglCanvases: document.querySelectorAll('canvas').length
  };
})()
```

---

## 4. 获奖站点高频工程令牌转译速查

1. **无级流体视口缩放（Fluid Root Scaling，源自 SOTY `landonorris.com` 实测）**：
   - 根字号绑定设计基准宽度（如 `1728px`）：`html { font-size: calc(clamp(992px, 100vw, 1920px) / 1728 * 16); }`（移动端回退 `16px`），大标题与间距统一用 `rem` 表达，消除断点阶梯跳变。
2. **四条经典非对称阻尼缓动曲线（替代平庸默认 `ease`）**：
   - **Expo Out 丝滑落位（标题揭幕 / 抽屉弹出，`450–700ms`）**：`cubic-bezier(0.19, 1, 0.22, 1)` 或 `cubic-bezier(0.16, 1, 0.3, 1)`
   - **Quart Out 轻快微交互（卡片悬停 / 按钮态切换，`200–400ms`）**：`cubic-bezier(0.25, 1, 0.5, 1)`
   - **Sleek InOut 叙事转场（整屏遮罩 / 布局共享变形，`700–800ms`）**：`cubic-bezier(0.65, 0.05, 0, 1)` 或 `cubic-bezier(0.76, 0, 0.24, 1)`
3. **平滑滚动与时间轴耦合**：
   - 展示型长叙事页如需平滑滚轮，优先采用保留原生滚动条与 `sticky` 语义的 **Lenis（`lerp: 0.09–0.10`）+ GSAP `ScrollTrigger`**，或零 JS 依赖的现代原生 CSS `animation-timeline: view()`。
