---
name: code-review-and-quality
description: 用于用户明确要求代码审查、合并前检查、较大改动收尾、完成证据核验或评估其他模型/代理生成代码时，按正确性、owner完整性、退役路径、可维护性、安全、性能和项目约定做质量审查。不是每个小改动的默认流程。
metadata:
  short-description: 代码质量审查
  sources:
    - "Adapted from addyosmani/agent-skills v0.6.0"
    - "DietrichGebert/ponytail (MIT), complexity pruning ideas"
    - "Selective review governance adapted from GanyuanRan/Aegis v2.3.0 (MIT)"
---

# Code Review and Quality

## Use When

- 用户明确说review、审查、检查、把关、合并前看一下。
- 一个功能或修复已经完成，需要收尾质量门禁。
- 需要评估人类、外部模型或其他代理写的代码。
- 改动涉及安全、数据、权限、并发、部署或公共接口。
- 用户特别担心代码过度工程、依赖太多、抽象太重、AI 写得太绕时，补做复杂度修剪。

## Do Not Use When

- 用户只要求直接实现一个小改动。
- 还没有可审查的diff、文件或代码片段。
- 任务是解释代码而不是判断代码是否可合入。

## Review Axes

按优先级检查：

1. 正确性：行为是否满足需求，边界条件是否漏掉。
2. 项目约定：目录、命名、依赖、错误处理是否符合现有风格。
3. 可维护性：复杂度、重复、抽象层级、注释是否合理。
4. 安全：输入、权限、凭据、外部服务、文件操作是否安全。
5. 性能：是否有明显低效、阻塞、泄漏或不必要的大开销。
6. 复杂度修剪：是否有推测性功能、单实现抽象、手写标准库、可用平台原生能力替代项或重复造轮子。
7. owner完整性：修复是否落在 canonical owner，是否新增重复 owner、fallback、adapter 或调用方补丁。
8. 收口证据：完成声明是否有新鲜验证，是否写清覆盖范围、未覆盖范围和剩余风险。
9. 依赖升级：核对 changelog 与迁移要求，隔离单个依赖变更，比较升级前后测试，并审查 lockfile 和传递依赖图；必须保留明确回滚路径。

如果用户明确要求“反过度工程”“能删什么”“最小实现”“YAGNI”“减少依赖”，或评审对象明显是 AI 生成的大而全代码，补看 [Complexity Pruning Pass](./references/complexity-pruning.md)。只做专项复杂度审查时，聚焦可删项，不把正确性、安全和性能问题混进同一 finding；这些问题另列常规 review。

## Governance Checks

对非平凡改动额外检查：

- `Change Necessity`: 是否真的需要源码改动；非代码、配置、文档或复用现有 owner 是否足够。
- `Patch Shape`: 是否用关键词、局部 guard、fallback、adapter、消费端补丁掩盖生产者或契约问题。
- `Repair Track`: 新 owner 或修复路径如何满足原需求。
- `Retirement Track`: 旧路径、旧 fallback、旧配置是否删除、保留兼容、还是需要后续退役触发条件。
- `Complexity Delta`: 改动是否让大文件、大函数、多职责模块、测试 harness 或计划文档继续膨胀。

这些检查不要求每次都输出完整卡片；只有发现风险或用户要求审计时展开。

## Output Rules

- 发现问题时先列finding，按严重程度排序。
- 每条finding指向具体文件、函数、命令或行为，不写泛泛建议。
- 没有实质问题时直接说未发现阻断问题，再给简短剩余风险。
- 不把个人偏好包装成必须修改。
- 复杂度修剪 finding 使用 `delete / stdlib / native / yagni / shrink / reuse` 标签，并说明删什么、替代方案和何时再补。
- 收尾审查要区分 `complete`、`needs-verification`、`blocked` 和 `scope-exceeded`；只有新鲜证据覆盖验收条件时才说完成。

## Verification

- 能说明审查依据来自diff、本地文件、测试结果或官方文档。
- 高风险问题有复现路径或明确推理链。
- 收尾给出已跑和未跑的验证命令。
- 明确 covered scope、uncovered scope、residual risk；不能用其他 agent 的“已完成”声明替代本地证据。
