---
name: stitch-workflow
description: "用于统筹 Stitch 原型生成、AI Studio 中转、代码导出、本地复现、UI polish 检查和交付记录。Use when coordinating a multi-step Stitch prototype workflow."
metadata:
  short-description: Stitch原型编排
---

# stitch-workflow

## When to use
- 需要把 `Stitch` 原型流程接入本机 Agent/Skills 体系，并与现有 `~/.agents/skills` 单一真源及跨端暴露治理（`magpie library sync`）保持一致。
- 需要基于已有视觉图（如 image2 输出）批量生成多版本网页原型，并导出代码到本地复现。
- 需要在 `Stitch` 与 `AI Studio (Gemini 4 Carbon)` 之间中转生成结果，再导出代码包。

## Inputs expected
- 版本列表（例如：保守版、激进版、中和版）。
- 每个版本对应的视觉输入图与文案指令。
- 导出目标（直接代码 zip，或先到 AI Studio 再导出 zip）。

## Standard workflow
1. 预检查
   - 确认输入图存在并命名一致。
   - 确认文案事实边界，避免夸大表述。
2. Stitch 生成
   - 每个版本独立项目。
   - 优先使用 `Web` 模式 + `Gemini 4 Carbon`。
   - 生成或改稿前，把 `$HOME/.agents/skills/frontend-design/references/components/ui-ux-design/references/ui-polish-microdetails.md` 中与页面相关的规则转成 prompt 约束，覆盖文字换行、圆角层级、光学对齐、边缘处理、状态覆盖、命中区域、动态数字和动效边界。
3. 导出路径
   - 优先直接导出代码 zip。
   - 若直接导出受限，走 AI Studio 中转（每版一个项目），附对应输入图再导出 zip。
4. 本地复现
   - 每个 zip 独立解压到单独目录。
   - 安装依赖并启动本地服务，记录端口和运行结果。
   - 本地打开后做一次UI polish检查；发现粗糙细节时记录到交付清单，必要时回到 Stitch/AI Studio 改 prompt。
5. 交付清单
   - 三个项目链接（Stitch/AI Studio）。
   - 三个 zip 本地路径。
   - 三个本地访问地址与复现状态。

## Output format
- 按版本输出：`项目链接 -> 代码包路径 -> 启动命令 -> 访问地址 -> 复现结论`。
- 明确失败项和阻塞点，不省略。
