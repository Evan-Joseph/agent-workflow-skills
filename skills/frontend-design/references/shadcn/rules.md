# shadcn/ui 强制编码规则与反模式防御

本规范基于 shadcn/ui 官方 Agent 规则提炼，在编写和改造基于 shadcn 的前端组件时强制执行。

---

## 一、 样式与 Tailwind 规范 (Styling)

1. **`className` 仅用于布局与间距，禁止覆盖组件语义色**：
   - **错误**：`<Button className="bg-blue-600 hover:bg-blue-700 text-white">保存</Button>`
   - **正确**：`<Button variant="default">保存</Button>`（或在需要微调外边距时只加 `className="mt-4 w-full"`）
2. **禁止使用 `space-x-*` 与 `space-y-*`**：
   - Tailwind 的 `space-*` 在子元素被条件渲染隐藏或插槽改变时会引入伪类边距错位。
   - **一律使用** Flexbox 或 Grid 配合 `gap-*`：`flex flex-col gap-4` 或 `flex items-center gap-2`。
3. **尺寸等宽等高采用 `size-*` 简写**：
   - 避免 `w-8 h-8`、`w-4 h-4`，一律简写为 `size-8`、`size-4`。
4. **单行省略统一采用 `truncate`**：
   - 避免冗长拼写 `overflow-hidden text-ellipsis whitespace-nowrap`，直接使用 `truncate`。
5. **严禁手动硬编码 `dark:` 颜色分支**：
   - 依赖语义色彩变量实现自动适配：使用 `text-muted-foreground` 而非 `text-gray-500 dark:text-gray-400`。
6. **条件类名合并必须通过 `cn()`**：
   - 使用 `@/lib/utils` 中的 `cn(...)`（内部包裹 `clsx` + `tailwind-merge`），避免模板字符串手动拼接三元表达式产生类名冲突。
7. **禁止在浮层组件上硬编码 `z-index`**：
   - `Dialog`, `Sheet`, `Popover`, `DropdownMenu` 自带符合层叠上下文的预设 z-index，手动加 `z-[9999]` 会破坏多层嵌套堆叠顺序。

---

## 二、 表单与输入规范 (Forms & Inputs)

1. **表单结构采用 `FieldGroup` + `Field`**：
   - 替代散落的 `div.space-y-2`，确保表单 Label、Input 与 Error 消息绑定正确的 `aria-describedby`。
2. **输入框内嵌按钮采用 `InputGroup` + `InputGroupAddon`**：
   - 搜索框内嵌清除按钮或复制按钮时，使用标准的 `InputGroup` 原语，避免手写绝对定位 `absolute right-2`。
3. **少量选项（2–7 项）优先采用 `ToggleGroup`**：
   - 视图切换、单选过滤等不要手写一组 `Button` 遍历与 active 状态管理，使用 `<ToggleGroup type="single">`。
4. **校验状态与无障碍标记联动**：
   - 校验失败时，在 Field 容器标记 `data-invalid`，在 Input 控件上声明 `aria-invalid="true"`。

---

## 三、 组件组合架构 (Composition)

1. **列表项必须嵌套在专用分组容器内**：
   - `SelectItem` 必须在 `SelectGroup` 内。
   - `DropdownMenuItem` 必须在 `DropdownMenuGroup` 内。
   - `CommandItem` 必须在 `CommandGroup` 内。
2. **自定义触发器必须使用 `asChild` (Radix) 或 `render` (Base UI)**：
   - **错误**：`<DialogTrigger><Button>打开</Button></DialogTrigger>`（会产生无意义的 button 嵌套 button 语法报错）。
   - **正确**：`<DialogTrigger asChild><Button>打开</Button></DialogTrigger>`。
3. **弹窗类组件必须包含 Accessible Title**：
   - `Dialog` 必须包含 `DialogTitle`；`Sheet` 必须包含 `SheetTitle`；`Drawer` 必须包含 `DrawerTitle`。
   - 若设计视觉上不需要标题文字，必须使用 `<DialogTitle className="sr-only">标题</DialogTitle>` 保持屏幕阅读器可达。
4. **Card 组件完整结构组合**：
   - 遵循 `CardHeader` -> `CardTitle` / `CardDescription` -> `CardContent` -> `CardFooter` 分层，禁止将所有内容直接塞进 `Card` 根节点。
5. **Button 加载态组合规范**：
   - shadcn Button 默认没有 `isLoading` 属性。
   - 正确写法：`<Button disabled={isLoading}>{isLoading && <Spinner data-icon="inline-start" />}提交</Button>`。
6. **Avatar 必须声明 `AvatarFallback`**：
   - 必须提供在头像加载失败或跨域被拦截时的文字/图标兜底。

---

## 四、 拒绝手工造轮子 (Component Substitution)

在构建界面时，严禁使用原生基础标签拼凑已存在官方原语的场景：
- **警告提示框**：使用 `<Alert>` / `<AlertDescription>`，禁止自建 `bg-yellow-50 border-yellow-200` 容器。
- **空状态**：使用 `<Empty>` 原语，禁止手写占位容器。
- **通知系统**：Radix 项目一律统一使用 `sonner` (`toast.success()`, `toast.error()`)，并在根布局放置 `<Toaster />`。
- **分割线**：使用 `<Separator />`，禁止使用 `<hr />` 或 `<div className="border-t" />`。
- **骨架屏**：使用 `<Skeleton className="..." />`，禁止手写 `animate-pulse bg-gray-200`。
- **徽标标签**：使用 `<Badge variant="...">`，禁止手写带有内边距和圆角的小 span。
