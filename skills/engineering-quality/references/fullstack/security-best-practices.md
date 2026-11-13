---
name: "security-best-practices"
description: "用于Python、JavaScript/TypeScript或Go项目的安全最佳实践审查与改进建议，仅在用户明确要求安全审查或安全加固时触发。"
metadata:
  short-description: 安全最佳实践审查与修复
---

# Security Best Practices

只在明确的安全最佳实践任务中使用这个skill。目标是找准技术栈，读取对应参考资料，把结论落到具体代码、配置和调用路径上。

## When to use

- 用户明确要求安全最佳实践建议、安全评审、安全报告，或secure-by-default实现。
- 任务语言属于`python`、`javascript/typescript`或`go`。
- 不用于一般代码审查、普通调试，或用户没有提出安全目标的场景。

## Workflow

1. 识别当前任务涉及的语言和主框架。前后端都在范围内时，两边都要覆盖。
2. 到`references/`里读取匹配文件。命名规则通常是`<language>-<framework>-<stack>-security.md`；同时检查对应的`<language>-general-<stack>-security.md`。
3. 如果是Web项目且前端框架未定，也要补看`javascript-general-web-frontend-security.md`这类通用前端规则。
4. 如果`references/`没有覆盖到当前栈，先明确告诉用户覆盖缺口，再只使用你能确认的通用安全规则；需要补资料时，优先查官方文档。
5. 根据用户目标选择模式：
   - 新代码或新项目：按安全默认值直接实现。
   - 日常协作：被动发现高影响问题并及时指出。
   - 明确的安全评审或报告：给出分级、定位和修复建议。
6. 所有结论都要落到具体文件、配置项、接口或调用路径，避免空泛建议。

## Workflow Decision Tree

- If the language/framework is unclear, inspect the repo to determine it and list your evidence.
- If matching guidance exists in `references/`, load only the relevant files and follow their instructions.
- If no matching guidance exists, say that the coverage is incomplete. You can still point out critical issues you can verify, but do not pretend the reference set is complete.

## Overrides

项目里的既有约束可能要求偏离通用最佳实践。遇到这种情况，先确认这是项目明确要求还是历史遗留，再把风险和原因说清楚。可以建议把例外写进项目文档，但不要和用户来回拉扯。

## Report handling

写报告时，先给一个简短摘要，再按严重度分组列出问题。每条问题都要有：

- 编号
- 影响说明
- 证据位置，包含文件和行号
- 建议修复方向

只在用户明确要求文件输出，或明确给了保存路径时，再把报告写成Markdown文件。即使写了文件，也要在对话里先汇总主要问题。

## Fix workflow

- 用户要求修复时，一次先处理一个问题，避免把不相关的安全改动揉进同一个提交。
- 修复前先评估功能影响和回归风险，别用“安全”做理由硬改一大片。
- 代码注释只写必要信息，说明这段改动对应的安全约束即可。
- 继续沿用项目原有的测试和提交流程。

## General Security Advice

Below is a few bits of secure coding advice that applies to almost any language or framework.

### Avoid Using Incrementing IDs for Public IDs of Resources

When assigning an ID for some resource, which will then be used by exposed to the internet, avoid using small auto-incrementing IDs. Use longer, random UUID4 or random hex string instead. This will prevent users from learning the quantity of a resource and being able to guess resource IDs.

### A note on TLS

While TLS is important for production deployments, most development work will be with TLS disabled or provided by some out-of-scope TLS proxy. Due to this, be very careful about not reporting lack of TLS as a security issue. Also be very careful around use of "secure" cookies. They should only be set if the application will actually be over TLS. If they are set on non-TLS applications (such as when deployed for local dev or testing), it will break the application. You can provide a env or other flag to override setting secure as a way to keep it off until on a TLS production deployment. Additionally avoid recommending HSTS. It is dangerous to use without full understanding of the lasting impacts (can cause major outages and user lockout) and it is not generally recommended for the scope of projects being reviewed by codex.
