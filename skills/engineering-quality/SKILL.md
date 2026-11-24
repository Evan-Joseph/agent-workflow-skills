---
name: engineering-quality
description: "工程质量守护、全栈架构实现、逆向实证与方案澄清中枢。包含精简版必要澄清（吸收 grill-me，一次一问附推荐）、轻量设计规格（SDD）、全栈最小实现契约、逆向解包先行、非交互子进程与超时规范、Git 提交前隐私扫描与复杂度裁剪。"
metadata:
  short-description: 工程质量控制、必要澄清(Grill-me)、全栈架构与反过度工程
---

# Engineering Quality, Full-Stack Architecture & Grilling

以最小心智负担保障代码健壮与架构干净，杜绝无休止反问、闭门硬猜与防御性过度设计。

## 运行时契约 (Runtime Contract)

- 内部脚本（`scripts/pre_push_privacy_audit.py`、`references/components/complexity-pruning/scripts/scan_debt.py`）固定使用 `python3`（`homebrew-stdlib`），严禁自建 `venv` 或执行 `pip install`。

## 一、 只在必要时澄清（吸收 `grill-me`）

仅在**长期任务起点**或**关键架构分水岭**、且自查后仍存在**未知但影响重大**的主观取舍时触发：
1. **能自查的绝不问用户**：个人履历、本机网关/代理端口、仓库结构与公开文档一律由 Agent 自行查清。
2. **一次一问，首项附 `(Recommended)`**：调用 `ask_question` 每次只问 1 个核心分歧（如红层资产去留、真实资金支出、核心存储/架构路线），给出推荐项与一句话依据，对齐后立即动手，禁止连环盘问。
3. **绿/黄层直接闭环**：单测、构建预览、本地修补直接执行到底并汇报验证结果，不请示常规工程动作。

## 二、 规格驱动、逆向先行与全栈克制

1. **最小增量、防“修 B 丢 AC”与模块化真重构**：
   - 日常修补复用既有框架与中间件，严禁堆砌 `*_v2.py` / `*_fixed.py` 或无故捆绑引入重型队列/权限库；
   - **防近因隧道视野（严禁“修 B 丢 AC”）**：因局部缺陷 `B` 修改提示词、规则、配置或长文档前，必须先通读盘点原产物的完整骨架 `A + B + C`，采用 `edit_file` 手术式最小修改并在收尾执行 `diff` 全结构核对，严禁让局部补丁把全局坍缩为 `B1B2B3` 而弄丢 `A` 与 `C`；
   - 当用户要求重构或单组件 `>400` 行高耦合腐化时，做正交模块化拆分（领域状态机 + 视图组件 + 死代码清理），不用贴补丁冒充重构。
2. **源码与逆向实证优先（`arXiv:2610.30571`）**：
   - 仓库文档与现存源码约定冲突时严格遵循现存源码与实测结果，并在收尾指出且同步修正文档偏差；网络与服务排障必须发真实业务载荷验证，不单信本地配置或 `fake-ip`。
   - 面对本地 `wxapkg`、APK、Mach-O、前端 Bundle、VDF 或 SQLite，第一时间解包/查表定位真实接口与字段，严禁盲猜菜单或质疑用户截图。
3. **语义理解交给大模型，确定性操作交给脚本**：
   - 非结构化清洗、备注归纳、语义匹配与图像筛查直接调用当前 Agent 或本地确定性模型组（向量与重排走 `moark/Qwen3-*`），严禁堆砌脆弱正则或死板打分枚举。
   - 构建后台、远控或工具前先通过 `developer-resource-search` / `gh` / `linuxdo` 检索 GitHub `>1,000` Stars 成熟开源基座，严禁静默将全局求解器（如 CP-SAT）降级为贪心算法。

## 三、 测试、子进程卫生与公开库隐私门禁

- **定点红绿测试与复杂度裁剪**：核心逻辑改动先写最小复现测试，通过即止；可用 `scan_debt.py .` 排查冗余抽象。
- **非交互子进程防僵尸规范**：守护进程拉起子进程 100% 配 `Wait()` / `proc.wait()`；CLI 默认注入 `CI=1 GIT_TERMINAL_PROMPT=0`、`stdin=DEVNULL` 与显式 `timeout`（单步前台 `<= 10` 分钟）；LaunchAgent 统一设 `ThrottleInterval >= 15` 与 `Soft=2048 / Hard=2500`。
- **公开仓库提交前隐私扫描（必做）**：向公开 GitHub 仓库提交或推送前必须运行：
  ```bash
  python3 $HOME/.agents/skills/engineering-quality/scripts/pre_push_privacy_audit.py . --json
  ```
  确认工作区（源码）、编译/渲染产物与 `git log -p` 三者同步干净（零符号链接、零密钥、零个人/导师邮箱与手机号、零设备序列号、零回环端口与内部委托标记）；交付远端仓库前确认 `ahead == 0` 且线上返回 `HTTP 200`。

## 四、 专题参考导航 (Progressive Disclosure)

- 研发方法论：[`spec-driven-development`](./references/components/spec-driven-development/guide.md) · [`test-driven-development`](./references/components/test-driven-development/guide.md) · [`debugging-and-error-recovery`](./references/components/debugging-and-error-recovery/guide.md) · [`code-review-and-quality`](./references/components/code-review-and-quality/guide.md) · [`complexity-pruning`](./references/components/complexity-pruning/guide.md)
- 全栈实现契约：[`fullstack/guide.md`](./references/fullstack/guide.md) · [`technology-selection.md`](./references/fullstack/technology-selection.md) · [`api-design.md`](./references/fullstack/api-design.md) · [`auth-flow.md`](./references/fullstack/auth-flow.md) · [`db-schema.md`](./references/fullstack/db-schema.md) · [`implementation-patterns.md`](./references/fullstack/implementation-patterns.md) · [`security-best-practices.md`](./references/fullstack/security-best-practices.md) · [`release-checklist.md`](./references/fullstack/release-checklist.md)
