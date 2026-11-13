---
name: spec-driven-development
description: 用于新项目、大功能、需求模糊、长期任务、跨会话任务或架构决策前编写轻量规格说明，明确目标、成功证据、停止条件、边界、验收方式和实施约束。小修小改、用户需求已经明确且可以直接执行时不要触发。
metadata:
  short-description: 轻量规格先行
  sources:
    - "Adapted from addyosmani/agent-skills v0.6.0"
    - "Selective goal-framing and continuation patterns adapted from GanyuanRan/Aegis v2.3.0 (MIT)"
---

# Spec-Driven Development

## Use When

- 新项目、新功能、跨模块改动或架构选择开始前，需求还没有稳定规格。
- 用户要求写PRD、技术规格、设计方案、实现计划或验收标准。
- 任务范围可能超过一次小改，继续直接写代码会导致返工。
- 需要给人类、外部模型或后续会话留下单一事实源。

## Do Not Use When

- 用户需求明确，且改动很小，可以直接完成。
- 只是修拼写、改文案、调配置、补一两个简单测试。
- 用户明确要求先不要写文档或先快速验证。

## Workflow

1. 先查当前工作区已有README、docs、AGENTS.md、issue、配置和代码结构，沿用现有命名和存放规范。
2. 建立轻量 goal frame：目标、成功证据、停止条件、非目标、范围和风险提示。
3. 如果信息缺口会改变实现方向，只问一轮关键问题；能合理推断的小缺口直接写明假设。
4. 建立 baseline read-set：列出已读的 README、ADR、docs、配置、入口代码、测试或用户材料；缺失但会影响方向的基线要标明。
5. 规格要落到可验证项，不写空泛愿景。
6. 若需要落盘，优先使用项目已有文档位置；新建文件前先确认工作区规范。不要为了流程感强行创建 `docs/aegis` 或新文档树。

## Goal Frame

大任务、跨模块任务或长期任务先给最小可用框定：

```text
Requested outcome:
Goal:
Success evidence:
Stop condition: done | blocked | needs-verification | scope-exceeded
Non-goals:
Constraints:
Scope:
Risk hints:
Next:
```

用户要求继续实现时，写完 frame 后继续进入计划或实施；只有用户明确要求“先只定目标/等确认”时才停下。

## Long-Task Continuation

任务可能跨会话、压缩上下文、多人/多 agent 协作或多阶段交付时，维护一个轻量 checkpoint。优先更新项目已有计划、交接、TODO 或工作记录；没有规范时在最终回复中给可复制的继续执行卡片，不默认落盘。

```text
Slice Card:
- Goal:
- Parent plan/spec:
- Files:
- Boundary:
- Verification:
- Stop:
```

每个阶段结束前检查：是否仍服务原目标，是否越过非目标，是否新增 owner/fallback/adapter，证据是否足够支撑下一步声明。

## Output Shape

默认输出轻量规格，包含：

- 目标
- 成功证据和停止条件
- 非目标
- 当前证据
- baseline read-set
- 设计约束
- 实施边界
- 验收标准
- 待确认问题

如果用户要继续实现，规格写完后直接进入实施，不把流程拖成长文档。

## Verification

- 规格能回答“做什么、不做什么、怎么验收”。
- 每个关键判断都来自用户要求、本地文件、官方文档或明确假设。
- 没有把小任务强行升级成PRD。
