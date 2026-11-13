---
name: engineering-quality
description: "工程质量守护、全栈架构实现、逆向实证与方案澄清中枢（已融合原 fullstack-dev）。包含精简版必要澄清（吸收 grill-me，一次一问附推荐）、轻量设计规格（SDD）、全栈 API/鉴权/数据库/实时通信实现契约、逆向解包先行、非交互子进程与超时模板、Git 提交前隐私扫描与复杂度裁剪。在需求含未知重要分歧、关键方案选型、全栈应用构建、大功能重构或复杂排障时使用。"
metadata:
  short-description: 工程质量控制、必要澄清(Grill-me)、全栈架构与反过度工程
---

# Engineering Quality, Full-Stack Architecture & Grilling

本技能是工程严谨度、全栈系统实现与开发效率的平衡守门员，旨在以最小的开销确保代码健壮，同时坚决防止“为了证明谨慎而反复造轮子、过度探索或无限拷问”。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：本技能内部脚本（`scripts/pre_push_privacy_audit.py`、`references/components/complexity-pruning/scripts/scan_debt.py` 等）固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `homebrew-stdlib` 运行时，标准库实现）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/engineering-quality/scripts/pre_push_privacy_audit.py . --json
  python3 $HOME/.agents/skills/engineering-quality/references/components/complexity-pruning/scripts/scan_debt.py .
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。

## 一、 精简版“只在必要时澄清”（吸收 Matt Pocock `grill-me`，禁止无休止追问）

限定在**长期任务起点**或**关键架构分水岭**，且经自查后需求仍含**“未知且影响重大（Unknown & High-Impact）”**的分歧时触发：

1. **四条执行准则**：
   - **能自查的先自查**：凡可通过读源码、查 `local-machine-profile` SSOT、看历史卷宗或联网查证确认的事实，一律由 Agent 自行查清，严禁把事实查证推给用户。
   - **一次一问，附推荐答案**：调用 `ask_question` 工具每次只问 **1 个**最关键的决策问题，将推荐方案放在第一项（标注 `(Recommended)` 并说明简短依据），同时允许用户补充自定义说明。
   - **绿/黄层直接做，不请示**：具备特权通道或明确最佳实践时直接做到底，不写半自动教程、不反问细节；仅在图形人机验证码、最终支付、红层操作或真正影响架构方向的分歧时找用户。
   - **禁止连环审讯**：对齐核心分歧后立即进入实施，严禁多轮盘问。

2. **“该问（Should Ask）”与“不该问（Should Not Ask）”正反例**：
   - **该问（未知且高影响的用户主观取舍）**：
     1. *红层资产去留决策*：“检测到两个同名历史会话分别包含不同阶段记录，推荐保留完整主会话并归档早期中断副本，是否确认归档？”
     2. *核心产品形态分水岭*：“新建卡片应用的数据同步边界：`(Recommended) 纯本地 IndexedDB + 静态 Pages 零成本托管` vs `Cloudflare D1 跨端云同步（消耗每日写入配额）`？”
     3. *外部真实资金采购*：“订阅续期存在官方兑换码年卡与单席位拼车两条路径，涉及真实付款，请确认采用哪一方案？”
   - **不该问（Agent 应自行查清或按基线直接执行）**：
     1. *SSOT 已有个人事实*：“请问你的毕业院校、四六级分数是多少？”（应直接读 `local-machine-profile/references/user-facts-and-portfolio.md`）。
     2. *本机网关与代理端口*：“请问本地模型网关和代理端口是多少？”（应直接读 `local-machine-profile/references/environment-facts.md`：MagPie `${OPENAI_COMPAT_HOST}`、Clash `${PROXY_HOST}`、CDP `${CDP_RELAY_HOST}`）。
     3. *常规技术实现细节*：“我接下来要用 `pytest` 跑一下单元测试并修复类型报错，可以吗？”（绿/黄层常规工程动作，应直接执行并汇报结果）。

## 二、 规格驱动与全栈最小实现门禁 (SDD & Full-Stack Minimal Gate)

- **核心原则**：在改动多个文件、构建全栈特性或复杂业务逻辑前，先写出最小可验收契约（输入、输出、边界条件、明确排除项）。
- **全栈默认克制与重构模式双轨裁决（Surgical Patch vs. True Overhaul Gate）**：
  - **常规迭代（Surgical Patch）**：优先复用当前仓库既有框架、ORM、鉴权中间件与校验模式，严禁引入平行架构或堆砌 `*_v2.py` / `*_fixed.py`；除非需求明确要求，否则单次实现不捆绑引入 RBAC 权限矩阵、Docker/CI 流水线、Redis/消息队列或重型状态库。
  - **架构焕新与巨石拆解（True Overhaul）**：当用户明确要求“重构 / 架构迁移 / UI 彻底焕新”或现有组件已腐化为高耦合巨石文件（单组件 `>400` 行、状态与视图混写、存在废弃死代码）时，执行模块化拆分（抽离领域状态机/Hooks + 原子视图组件 + 清理死代码），不用零星微调充当重构。
  - **代码真相优于历史宣称（Code Truth Over Stale Claims）**：当历史摘要、Commit 说明或注释与当前真实源码或实测表现不符时，一律以当前源码与实测结果为准，并显式指出冲突点。
  - **严禁静默算法降级与偷工减料（No Silent Algorithm Fallback Gate）**：当全局求解器（如 CP-SAT）、启发式搜索或深度学习推理管线耗时较长或遇到环境报错时，严禁静默替换为退化贪心算法、Mock 假数据或静态贴图；确需降级或调整参数时必须显式汇报用户并获批。
  - **真实线上探测优于本地配置盲信（Live Endpoint Truth Gate）**：网络、代理、网关与服务排障时，严禁仅凭本地配置文件或 `fake-ip` 解析成功就断言服务恢复，必须执行真实业务载荷探测验证全链路连通。
  - **逆向实证先行，严禁盲猜菜单或质疑用户截图（Reverse-Engineering First Gate）**：当本地存在小程序包（`wxapkg`）、APK、Mach-O 二进制、前端 Bundle、VDF 或 SQLite 时，第一时间解包/反编译/查表定位真实 API 端点与参数逻辑，严禁凭空盲猜菜单路径或质疑用户真实截图；查探 Steam 游戏库或社交数据时 100% 走离线文件（`appinfo.vdf` / `localconfig.vdf` / 离线 SQLite），严禁调用 `SteamAPI_Init()` 或注入 IM 客户端。
  - **大模型原生语义与多模态优先于脆弱正则（LLM-Native Over Brittle Regex Gate）**：处理非结构化文本清洗、语义匹配、备注标准化、图片水印/二维码筛查时，**严禁编写脆弱正则表达式或长串 `if-else` 关键词硬编码**；直接调用当前 Agent 或本机唯一网关 **MagPie（`${OPENAI_COMPAT_BASE_URL}`）**，绑定项目专属 `magpie-<slug>` Key 并显式指定纯模型确定性组（`group/{carbon,opus,sonnet,sol,astra,flash,deepseek}`，向量与重排调 `/v1/{embeddings,rerank}` `moark/Qwen3-*`）；音视频去重采用 `ffmpeg` 音频波形互相关 + 多模态核验。
  - **站在巨人肩膀上（GitHub `>1,000` Stars 或垂直 Top 3 成熟基座优先）**：构建管理后台、远控面板或系统工具前，先通过 `developer-resource-search` / `gh` / `linuxdo` 检索头部活跃开源项目直接复用成熟工程基座，不拉取弃坑半成品或从零造轮子。
  - **前后端契约对齐**：每个接口同步落地输入 Schema 校验、鉴权边界、统一错误码返回及对应前端 loading/empty/error 状态。
- **多模型并行比稿与择优合并（Multi-Worktree Arena Workflow）**：
  - 当在多 Worktree 并行运行异构主力模型（如 `GPT-6.1 Sol xhigh`、`Claude Opus 5.5`、`Gemini 4 Carbon`）对比同一任务时，提示词采用**自包含契约**（明确技术栈、视觉方向、交互边界、验证命令与禁区）；
  - 评标合并采用 **Base + Cherry-pick Merge**：选定架构最稳的一方作为 Base 主干，拆解移植其余模型在微交互、边界异常处理或无障碍上的亮点，合并后统一跑通构建与浏览器实测。

## 三、 测试驱动、复杂度裁剪与发布前隐私扫描 (TDD, Anti-Over-Engineering & Pre-Push Gate)

- **红绿重构**：核心逻辑变更优先构造定点失败用例，通过后即止，不写镜像实现的冗余测试。
- **反防御性膨胀**：禁止在单次任务中无端引入通用抽象、多层包装或全局错误埋点。
- **技术债与复杂度静态扫描**：
  ```bash
  python3 $HOME/.agents/skills/engineering-quality/references/components/complexity-pruning/scripts/scan_debt.py .
  ```
- **Git 提交与公开仓库推送前安全扫描及远端同步门禁（Pre-Push Privacy & Remote Sync Gate）**：
  - 在向 GitHub 公开仓库执行 `git commit` / `git push` 前，必须运行确定性门禁脚本同时扫描工作区与 Git 历史（`git log -p`），确认零符号链接、零 API Key/Token、零个人/导师邮箱与手机号、零设备序列号、零内网/回环端口、零委托项目（`[CLIENT_RESTRICTED]`）标记（同时输出 `>400` 行巨石文件预警）；发现历史污染时先用 `git filter-repo` 或孤儿分支清洗：
    ```bash
    python3 $HOME/.agents/skills/engineering-quality/scripts/pre_push_privacy_audit.py . --json
    ```
  - 凡绑定远端仓库的项目，声明完成或跨会话移交前核验 `git status -sb` 为 `ahead == 0` 且线上生产端点返回 `HTTP 200`。
- **非交互 CLI、子进程 `Wait()` 回收与超时规范**：
  - 后台守护异步拉起子进程 100% 配套 `Wait()` / `proc.wait()` 回收；CLI 调用默认注入 `CI=1`、`GIT_TERMINAL_PROMPT=0` 并设 `stdin=DEVNULL` 与显式 `timeout`（单步前台 `<= 10` 分钟，完整模板见 `$HOME/.agents/skills/harness-governance/references/daemon-and-runtime-guards.md`）。

## 四、 深度专题参考路由 (Progressive Disclosure)

| 场景需求 | 参考指南 |
| :--- | :--- |
| 轻量规格驱动开发 (SDD) | [`references/components/spec-driven-development/guide.md`](./references/components/spec-driven-development/guide.md) |
| 测试驱动开发 (TDD) | [`references/components/test-driven-development/guide.md`](./references/components/test-driven-development/guide.md) |
| 系统性排障与错误恢复 | [`references/components/debugging-and-error-recovery/guide.md`](./references/components/debugging-and-error-recovery/guide.md) |
| 代码审查与合并前检查 | [`references/components/code-review-and-quality/guide.md`](./references/components/code-review-and-quality/guide.md) |
| 复杂度裁剪与反过度设计 | [`references/components/complexity-pruning/guide.md`](./references/components/complexity-pruning/guide.md) |
| 全栈工程总览与技术选型 | [`references/fullstack/guide.md`](./references/fullstack/guide.md)、[`references/fullstack/technology-selection.md`](./references/fullstack/technology-selection.md) |
| API 契约、鉴权流与数据库 Schema | [`references/fullstack/api-design.md`](./references/fullstack/api-design.md)、[`references/fullstack/auth-flow.md`](./references/fullstack/auth-flow.md)、[`references/fullstack/db-schema.md`](./references/fullstack/db-schema.md) |
| 全栈实现模式、安全与上线检查单 | [`references/fullstack/implementation-patterns.md`](./references/fullstack/implementation-patterns.md)、[`references/fullstack/security-best-practices.md`](./references/fullstack/security-best-practices.md)、[`references/fullstack/release-checklist.md`](./references/fullstack/release-checklist.md) |
