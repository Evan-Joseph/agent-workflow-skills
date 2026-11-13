# Stitch Loop Workflow Reference

本文件在需要查看 baton 示例、文件结构、Stitch metadata schema、编排选项或排障表时读取。

## Baton Example

`.stitch/next-prompt.md`：

```markdown
---
page: about
---
A page describing how jules.top tracking works.

**DESIGN SYSTEM (REQUIRED):**
[Copy from .stitch/DESIGN.md Section 6]

**Page Structure:**
1. Header with navigation
2. Explanation of tracking methodology
3. Footer with links
```

关键规则：

- `page` 字段决定输出文件名。
- prompt 必须包含 `.stitch/DESIGN.md` 的设计系统块。
- 每次完成前都要更新 `.stitch/next-prompt.md`。

## File Structure

```text
project/
├── .stitch/
│   ├── metadata.json
│   ├── DESIGN.md
│   ├── SITE.md
│   ├── next-prompt.md
│   └── designs/
│       ├── {page}.html
│       └── {page}.png
└── site/public/
    ├── index.html
    └── {page}.html
```

## Metadata Schema

`.stitch/metadata.json` 持久化 Stitch project 和 screen 标识。创建项目或生成 screen 后，调用 Stitch 的 `get_project` 并更新该文件。

```json
{
  "name": "projects/6139132077804554844",
  "projectId": "6139132077804554844",
  "title": "My App",
  "visibility": "PRIVATE",
  "createTime": "2026-03-04T23:11:25.514932Z",
  "updateTime": "2026-03-04T23:34:40.400007Z",
  "projectType": "PROJECT_DESIGN",
  "origin": "STITCH",
  "deviceType": "MOBILE",
  "designTheme": {
    "colorMode": "DARK",
    "font": "INTER",
    "roundness": "ROUND_EIGHT",
    "customColor": "#40baf7",
    "saturation": 3
  },
  "screens": {
    "index": {
      "id": "d7237c7d78f44befa4f60afb17c818c1",
      "sourceScreen": "projects/6139132077804554844/screens/d7237c7d78f44befa4f60afb17c818c1",
      "x": 0,
      "y": 0,
      "width": 390,
      "height": 1249
    }
  },
  "metadata": {
    "userRole": "OWNER"
  }
}
```

字段说明：

- `name`：完整资源名。
- `projectId`：Stitch project ID。
- `title`：项目标题。
- `designTheme`：颜色模式、字体、圆角、自定义色、饱和度等设计 token。
- `deviceType`：`MOBILE`、`DESKTOP` 或 `TABLET`。
- `screens`：页面名到 screen metadata 的映射，包含 `id`、`sourceScreen`、画布位置和尺寸。
- `metadata.userRole`：用户在项目中的角色。

## Orchestration Options

| Method | How it works |
|--------|--------------|
| CI/CD | GitHub Actions triggers on `.stitch/next-prompt.md` changes |
| Human-in-loop | Developer reviews each iteration before continuing |
| Agent chains | One agent dispatches to another |
| Manual | Developer reruns the agent with the same repo |

本 Skill 只约束 loop pattern，不绑定具体触发器。

## Design System Integration

与 `design-md` 配合时：

1. 首次设置：用 `design-md` 从现有 Stitch screen 生成 `.stitch/DESIGN.md`。
2. 每次迭代：把 Section 6 `Design System Notes for Stitch Generation` 复制进 baton prompt。
3. 一致性：所有生成页面共享同一视觉语言。

## Common Pitfalls

- 忘记更新 `.stitch/next-prompt.md`，导致 loop 断掉。
- 重建 sitemap 中已经存在的页面。
- prompt 没带 `.stitch/DESIGN.md` 的设计系统块。
- 导航仍然保留 `href="#"`。
- 创建新项目或 screen 后没有更新 `.stitch/metadata.json`。

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Stitch generation fails | Check that the prompt includes the design system block |
| Inconsistent styles | Ensure `.stitch/DESIGN.md` is current and copied into the baton |
| Loop stalls | Verify `.stitch/next-prompt.md` has valid frontmatter |
| Navigation broken | Check all internal links use correct relative paths |
| Assets look low-resolution | Append `=w{width}` to screenshot download URL before saving |
