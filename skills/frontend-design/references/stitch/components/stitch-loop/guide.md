---
name: stitch-loop
description: 用于通过 Stitch 迭代构建网站页面，并用 `.stitch/next-prompt.md` 接力文件管理连续生成、集成、UI polish验证和下一步任务。
metadata:
  short-description: Stitch迭代构建
allowed-tools:
  - "stitch*:*"
  - "chrome*:*"
  - "Read"
  - "Write"
  - "Bash"
---

# Stitch Build Loop

用 Stitch 生成页面、集成到本地站点、验证结果，并把下一轮任务写回 `.stitch/next-prompt.md`。这个 Skill 的核心是 baton 文件接力：每轮读当前任务，完成页面，再写下一轮任务。

## Prerequisites

Required:

- Stitch MCP Server 可用。
- 视觉验证前先加载 `browser-routing`。使用官方 Chrome 扩展时，先命名任务分组再创建标签页，验证中间页用完立即关闭，结束时只保留明确的 deliverable 或 handoff；使用 Chrome DevTools 时记录并关闭本轮创建的全部 page。
- 已有 Stitch project，或允许创建新 project。
- `.stitch/DESIGN.md` 存在；没有时先用 `design-md` 生成。
- `.stitch/SITE.md` 记录站点愿景、project ID、sitemap 和 roadmap。
- 若站点涉及UI polish、微交互、界面粗糙或"make it feel better"，`.stitch/DESIGN.md`和baton prompt必须吸收`$HOME/.agents/skills/frontend-design/references/components/ui-ux-design/references/ui-polish-microdetails.md`的相关规则。

Optional:

- Chrome DevTools MCP Server，用于视觉验证。

模板和 schema 见 `resources/baton-schema.md`、`resources/site-template.md`，完整文件结构和 metadata schema 见 [resources/workflow-reference.md](resources/workflow-reference.md)。

## Execution Protocol

### 1. Read The Baton

读取 `.stitch/next-prompt.md`：

- 从 YAML frontmatter 提取 `page`。
- 从 Markdown body 提取完整 Stitch prompt。

`page` 决定输出文件名，prompt 必须包含 `.stitch/DESIGN.md` 的设计系统块。
如果prompt没有说明文字换行、圆角层级、光学对齐、状态覆盖、命中区域、动态数字和动效边界，先补齐再生成。

### 2. Consult Context

生成前读取：

| File | Purpose |
|------|---------|
| `.stitch/SITE.md` | Site vision, Stitch Project ID, sitemap, roadmap |
| `.stitch/DESIGN.md` | Required visual style for Stitch prompts |

检查：

- `SITE.md` Section 4：不要重建已有页面。
- `SITE.md` Section 5：优先消费 roadmap。
- `SITE.md` Section 6：roadmap 为空时选 creative freedom 项。

### 3. Generate With Stitch

1. 发现 Stitch MCP namespace。
2. 获取或创建 project：
   - `.stitch/metadata.json` 存在时复用其中 `projectId`。
   - 不存在时调用 `create_project`，再调用 `get_project`，保存完整 metadata。
3. 调用 `generate_screen_from_text`：
   - `projectId`：Stitch project ID。
   - `prompt`：baton 中的完整 prompt，包括设计系统块。
   - `deviceType`：默认 `DESKTOP`，除非 baton 或项目明确指定。
4. 生成后调用 `get_project`，更新 `.stitch/metadata.json` 的 `screens` map。
5. 下载资产：
   - 如果 `.stitch/designs/{page}.html` 或 `.png` 已存在，先问用户是刷新还是复用。
   - 下载 HTML 到 `.stitch/designs/{page}.html`。
   - 下载 screenshot 时给 URL 追加 `=w{width}`，避免 Google CDN 返回低清缩略图。

### 4. Integrate Into Site

1. 将 `.stitch/designs/{page}.html` 集成到 `site/public/{page}.html`。
2. 修正资源路径，使其相对 `site/public/` 可用。
3. 更新导航，替换 `href="#"`，必要时加入全局导航。
4. 保持 header/footer 与现有页面一致。

### 5. Visual Verification

如果 Chrome DevTools MCP 可用：

1. 启动本地静态服务，例如 `npx serve site/public`。
2. 打开 `http://<LOCAL_HOST>:3000/{page}.html`。
3. 截图并与 `.stitch/designs/{page}.png` 比对。
4. 同时检查UI polish：没有难看的孤行/挤压、嵌套圆角协调、图标视觉重心正确、图片边缘干净、小控件好点、动态数字不抖动、动画不夸张。
5. 结束本地服务。

没有 Chrome DevTools MCP 时跳过这一步，但要说明未做视觉验证。

### 6. Update Site Documentation

更新 `.stitch/SITE.md`：

- 在 Section 4 sitemap 中标记新页面 `[x]`。
- 移除已经消费的 Section 6 idea。
- 更新 Section 5 roadmap。

### 7. Prepare Next Baton

完成前必须更新 `.stitch/next-prompt.md`：

1. 优先从 `.stitch/SITE.md` Section 5 选择下一项。
2. Roadmap 为空时，从 Section 6 选择或提出符合站点愿景的新页面。
3. 写入合法 YAML frontmatter 和完整 prompt，包含设计系统块。

## Critical Rules

- 不要重建 sitemap 中已经存在的页面。
- 不要省略 `.stitch/DESIGN.md` 的设计系统块。
- 不要省略UI polish约束；不能只写“高级、精致、现代”。
- 不要在完成前留下旧的 `.stitch/next-prompt.md`。
- 不要手工丢弃 `.stitch/metadata.json` 中的 project 和 screen IDs。
- 不要留下 `href="#"` 占位链接。

## References

- Baton schema：[resources/baton-schema.md](resources/baton-schema.md)
- Site/DESIGN 模板：[resources/site-template.md](resources/site-template.md)
- 文件结构、metadata schema、编排方式和排障：[resources/workflow-reference.md](resources/workflow-reference.md)
