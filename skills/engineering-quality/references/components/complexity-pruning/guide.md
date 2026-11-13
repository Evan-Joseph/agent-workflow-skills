---
name: complexity-pruning
description: 用于用户要求最小实现、反过度工程、删代码、减少依赖、检查是否重复造轮子、评估 AI 生成代码是否太复杂时；也用于清理重复 owner、历史 fallback、兼容分支、无效抽象、样板层、手写标准库、平台原生替代项，或扫描 complexity-pruning 债务标记。
license: MIT
metadata:
  short-description: 反过度工程与复杂度修剪
  sources:
    - "Adapted from DietrichGebert/ponytail (MIT), localized for this local Skills system"
    - "Selective governance patterns adapted from GanyuanRan/Aegis v2.3.0 (MIT)"
---

# Complexity Pruning

把 AI 代码产物拉回“足够完成需求的最小实现”。目标是少写、少引依赖、少造层，同时不牺牲正确性、安全、数据保护、可访问性和必要验证。

## Use When

- Use when the user wants a repo-wide over-engineering audit, a ponytail-style one-shot simplification review, or a ranked list of code that can be deleted, shrunk, or replaced with stdlib/native equivalents.
- 用户说“最小实现”“别过度工程”“能不能删”“减少依赖”“YAGNI”“先做简单版”。
- 审查外部模型、Agent 或人写的代码，怀疑有过多包装层、抽象、配置或未来预留。
- 功能很小，但实现开始引入新框架、新依赖、新目录层级或大型模板。
- 清理旧逻辑、重复 owner、历史 fallback、兼容分支或无人维护的配置面。
- 需要给现有代码库做只读复杂度审计。
- 需要扫描 `complexity-pruning:` 注释，整理此前有意留下的简化上限和回访条件。

## Do Not Use When

- 用户明确要完整架构、平台化能力、长期扩展方案或正式设计文档。
- 风险来自正确性、安全、权限、并发、数据一致性或性能瓶颈；这些优先走常规代码审查。
- 简化会删除输入校验、错误处理、审计日志、权限控制、数据迁移保护、无障碍基础或用户明确要求的行为。

## Minimal Implementation Ladder

写代码前先理解真实调用链和现有约定，再按顺序停在第一个可用层级：

1. 需求是否真实存在；推测性需求先跳过，并说明触发条件。
2. 项目里是否已有 helper、组件、类型、服务、脚本或模式可复用。
3. 语言标准库是否已经提供。
4. 平台原生能力是否覆盖，例如 HTML 控件、CSS、数据库约束、浏览器 API、系统命令。
5. 已安装依赖是否已经解决，不为几行代码新增依赖。
6. 一行或一个小函数能否完成。
7. 以上都不够时，写最小可工作的自定义实现。

修 bug 时，最小改动要落在根因位置。先查调用方和共享路径；一个共享函数里的 guard 往往比多个入口各补一次更小、更稳。

## Anti-Entropy Governance

当任务涉及删除、合并重复 owner、退役 fallback 或清理兼容路径时，先分类再动手：

- `code-retirement`: 内部源码、旧触发、重复 owner、死 fallback。默认 `delete-first`，但要验证新 owner 承接了行为。
- `contract-carrying code`: schema、migration、公共 API、持久化读写、宿主安装/发现契约。允许删除或改造，但必须扩大验证面。
- `derived-state`: 可重建缓存、生成索引、临时导出。先证明可重建，再处理。
- `persistent-state`: 真实数据库行列、用户文件、权限、身份、审计、账单、不可重放队列。必须先停下，列出目标、不可逆性、备份/回滚和只读下一步，等用户明确范围确认。

内部复杂度默认不要“先留着兼容”。只有有活跃外部依赖证据时，才保留兼容例外，并写清保留原因和退役触发条件。未知依赖不等于活跃依赖。

## Change Necessity

新增源码路径、fallback、adapter、抽象层或依赖前，先做一行判断：

```text
Change Necessity: 用户可见需求是什么；现有 owner / 非代码路径为什么不足；最小变更边界在哪里；Decision: no-change | docs/config-only | code-change | needs-clarification
```

如果是 `no-change` 或 `docs/config-only`，不要把它升级成源码改动。若候选方案只是“再加一个 guard / fallback”，先找正确 owner 和可删除的旧路径。

## Review Tags

专项审查时只报告复杂度问题，用这些标签：

- `delete`: 死代码、推测功能、无人使用的配置或开关。
- `stdlib`: 手写了标准库已有能力。
- `native`: 依赖或自定义代码替代了平台原生能力。
- `yagni`: 单实现接口、单产品工厂、单调用方分层、没人设置的配置。
- `shrink`: 同样行为可以用更少代码表达。
- `reuse`: 项目已有实现被重新写了一遍。

每条 finding 指向具体文件、行或符号，写清“删什么、用什么替代、什么时候再加回来”。只读审计不直接改代码，除非用户明确要求继续实施。

## Debt Comments

刻意简化但有已知上限时，允许留下短注释：

```text
// complexity-pruning: global lock; switch to per-account locks if write contention appears
```

注释必须包含上限和重新设计的触发条件。不要用它为偷懒、遗漏验证或绕过安全兜底。

扫描现有债务标记：

```bash
python3 $HOME/.agents/skills/engineering-quality/references/components/complexity-pruning/scripts/scan_debt.py <repo>
```

输出按文件分组，列出每个标记的行号、简化内容和是否缺少触发条件。没有命中时报告 `No complexity-pruning debt markers.`。

## Ponytail-style audits

For a ranked one-shot over-engineering audit, keep the review tight:

- look for dead code, unused flexibility, single-implementation abstractions, and hand-rolled standard/library equivalents
- keep correctness/security/performance out of scope unless the user asks for them
- end with `net: -<N> lines possible` or `Lean already. Ship.`

## Output

- 实施任务：代码或变更说明优先，然后用最多三行说明跳过了什么、何时再补。
- 审查任务：按严重程度列 finding；只查复杂度时最后给 `net: -N lines, -M deps possible` 的估计。
- 债务扫描：列出 `complexity-pruning:` 标记；指出缺触发条件的条目，不自动修改代码。
- 退役任务：说明旧路径、新 owner、保留行为、退役行为、是否触及外部边界和是否需要用户确认。
- 没有可删项时直接说 `已经够精简，可以保留。`

## Boundaries

这不是代码高尔夫。非平凡逻辑至少要有一个最小可运行验证：现有测试、局部测试、断言脚本、构建、lint、类型检查或可重复手工步骤。不要为了少代码删除能防止数据丢失、越权、注入、误提交或不可恢复操作的保护。

删除验证不能只看测试变绿，还要检查：

- main path 仍由新 canonical owner 承接。
- 旧路径不再被主链路引用。
- 被退役的触发、fallback 或兼容入口确实失效。
- schema、API、宿主发现、持久化或外部兼容边界没有被误伤。
