---
name: debugging-and-error-recovery
description: 用于测试失败、构建失败、运行异常、日志报错、同一问题反复修复失败、怀疑 fallback/adapter/重复 owner 掩盖根因时做系统排障。先保留证据、复现、定位 canonical owner，再最小修改并验证。
metadata:
  short-description: 系统排障与恢复
  sources:
    - "Adapted from addyosmani/agent-skills v0.6.0"
    - "Selective debugging discipline adapted from GanyuanRan/Aegis v2.3.0 (MIT)"
---

# Debugging and Error Recovery

## Use When

- 测试、构建、启动、部署或运行时失败。
- 浏览器控制台、服务日志、CLI输出或用户反馈显示异常。
- 同一类问题连续尝试两次仍未解决。
- 需要从混乱状态恢复到可解释、可验证的状态。

## Do Not Use When

- 只是正常功能开发，没有异常现象。
- 用户明确要求先做探索性原型，不要求排障。

## Workflow

1. 保留证据：记录精确命令、错误文本、环境、最近改动和复现条件。
2. 最小复现：缩小到一个测试、一个请求、一个页面、一个文件或一个输入。
3. 定位边界：区分配置、依赖、权限、数据、代码逻辑、外部服务、平台约束和规格缺口。
4. 找 canonical owner：沿数据流向上追，不在调用方、展示层或消费端给生产者问题打补丁。
5. 修复前做 patch-shape triage；如果候选方案会新增 guard、fallback、adapter、重复解析、兼容分支或新 owner，先证明它是正确 owner，否则继续追根因。
6. 做最小修复：只改和根因相关的文件，避免顺手重构。
7. 验证恢复：重跑失败命令和必要的相邻回归。

## Diagnostic Layers

排障不要停在第一个症状。按需向上追：

1. 症状：什么失败，如何复现。
2. 逻辑：哪个分支、状态或不变量错了。
3. 系统：哪个组件边界或依赖交互错了。
4. 架构：是否有重复 owner、fallback 链或错误职责划分。
5. 跨系统契约：API、时序、SLA、数据格式或权限契约是否未对齐。
6. 平台约束：运行时、OS、框架、浏览器或供应商限制。
7. 规格缺口：需求本身是否没有定义正确行为。

当修复位置有争议时，先输出当前停止层、已排除层和能推翻判断的证据，再改代码。

## Patch-Shape Triage

以下形态是风险信号，不能直接当成“最小修复”：

- 关键词、正则、样例文本例外。
- 额外条件、early return、try/catch、局部 guard。
- fallback、adapter、兼容分支或 legacy path 扩张。
- 调用方、展示层、readiness 层补丁。
- 下游重新解析原始文本，而已有 typed intent、规范化状态或 source-of-truth。
- artifact、download、export、cache 的消费端补丁，没有先找生产者。
- 重复解析、重复 owner 或“先两个都留着”。

触发这些信号时，先写清：

```text
PatchShape:
CanonicalOwner:
Why local patch is insufficient or sufficient:
Decision: fix owner | continue investigation | mitigation-with-retirement | needs-clarification
```

非平凡源码改动前补一行 `Change Necessity`：用户可见需求、非代码选项为何不足、最小变更边界和 `Decision`。

## Stop Rule

同一问题连续两次修复失败后，停止继续硬改，输出：

- 现象
- 已尝试动作
- 每次失败原因
- 当前最可能根因
- 需要用户确认或需要更多证据的点

## Verification

- 最终结论能解释为什么失败、为什么这个修复有效。
- 失败命令已恢复，或明确说明仍受哪个外部条件阻断。
- 没有为了掩盖错误而删除测试、吞异常或降低校验强度。
- 如果修复退役旧路径，要验证新 owner 承接主链路、旧路径不再被引用，且必要的负向检查通过。
