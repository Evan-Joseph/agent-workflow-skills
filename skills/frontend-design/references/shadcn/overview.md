# shadcn/ui 架构与工程规范

> 官方源：[ui.shadcn.com](https://ui.shadcn.com) | CLI 规范：`npx shadcn@latest` | 理念：Open Code · Composition · Accessible Defaults

---

## 一、 核心设计哲学

1. **源码级所有权 (Open Code)**：
   - 不是打包发布的 npm 依赖黑盒，而是通过 CLI 直接将组件源码（TypeScript + Tailwind CSS + Radix/Base UI）植入工程目录（通常为 `@/components/ui/`）。
   - 开发者对组件的代码结构、变体定义、样式具有 100% 的修改与定制权。
2. **基于 Primitive 的无障碍组合 (Composition)**：
   - 底层深度集成 Radix UI 或 Base UI 原语，默认保障 WAI-ARIA 规范、键盘焦点陷阱（Focus Trap）、屏幕阅读器支持。
   - 依赖 `Slot` / `asChild` 模式进行结构组合，杜绝嵌套无意义的 `div` 包装器。
3. **语义化设计系统与 Tokens (Theming)**：
   - 统一采用现代 CSS 变量或 OKLCH 色彩空间，支持亮色与暗色模式无缝切换。
   - 严禁在业务代码中硬编码原始色值（如 `bg-blue-500`、`text-gray-400`），必须使用语义化 Token（`bg-primary`、`text-muted-foreground`、`border-border`）。

---

## 二、 CLI 与工程配置基线

### 1. 包管理器自适应运行
执行所有 shadcn 命令时，根据项目现有的 `packageManager`（检查 `package.json` 中的 `packageManager` 或锁文件）：
- **npm**: `npx shadcn@latest <command>`
- **pnpm**: `pnpm dlx shadcn@latest <command>`
- **bun**: `bunx --bun shadcn@latest <command>`

### 2. 常用操作指令
```bash
# 初始化工程配置（生成 components.json 与全局样式变量）
npx shadcn@latest init

# 搜索官方与社区 Registry
npx shadcn@latest search <query>

# 安装基础组件（支持多选批量安装）
npx shadcn@latest add button card dialog dropdown-menu form input table tabs

# 查看组件官方文档与示例地址
npx shadcn@latest docs <component>

# 输出当前工程配置与已安装组件清单（用于 Agent 上下文环境自检）
npx shadcn@latest info --json
```

### 3. `components.json` 关键配置项
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

---

## 三、 主题 Token 规范 (Semantic Design Tokens)

项目全局 CSS 必须映射基础设计令牌：
- **容器与背景**：`--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`
- **品牌交互与状态**：`--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`
- **中性与辅助**：`--muted`, `--muted-foreground`, `--border`, `--input`, `--ring`
- **图表与度量**：`--chart-1` 至 `--chart-5`
