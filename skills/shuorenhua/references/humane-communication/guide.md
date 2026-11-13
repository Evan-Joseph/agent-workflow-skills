---
name: humane-communication
description: "用于沟通策略、消息、邮件、书信、私信、回复、跟进、感谢、拒绝、道歉、求助、谈判和冲突降温的起草与审阅；适用于用户要求高情商、会说好话、礼貌但不低姿态、非暴力沟通、话术、帮我写给老师/同学/合作方/客户/维护者的场景。已有文本去 AI 味或自然化改写优先配合 shuorenhua。"
metadata:
  short-description: 高情商沟通、邮件消息起草与冲突降温
---

# Humane Communication

This skill helps draft communication that is clear, kind, specific, and useful. The goal is not to sound polished; the goal is to protect the relationship while making the request easy to understand and easy to answer.

## Boundary

Use this for communication tasks where the wording changes the relationship or outcome:

- first contact, help requests, mentoring/advisor emails, collaborator messages
- follow-up after no reply, thanks, apology, refusal, bad news, correction
- negotiation, conflict de-escalation, maintainer/customer/community replies
- reviewing whether a message is too defensive, too low-posture, too vague, or too pushy

Do not use it as a general long-document writer. Use `document-crafting` for substantial documents and `shuorenhua` for polishing an existing text after the communication strategy is already clear.

Do not send messages, email, post, comment, or submit forms unless the user explicitly asks for external action and the current tool/workflow permits it. Default to local draft only.

## Core Workflow

Before drafting, do a short private communication brief:

1. Receiver: who they are, what role/power/time pressure they have, what they probably care about.
2. Relationship goal: first impression, maintain trust, ask for help, repair, decline, escalate, or close the loop.
3. Facts: what is confirmed, what must not be exaggerated, what evidence or prior work can be named.
4. Request: one concrete action the receiver can take now; if useful, offer two acceptable options.
5. Risk: low posture, emotional pressure, fake praise, defensive disclaimers, unclear ask, too many questions, or overlong background.

Then draft in this order:

1. Context: identify the sender and situation quickly.
2. Specific bridge: mention a concrete fact, prior work, shared context, or receiver-side reason.
3. Main point: state the need or question directly.
4. Respectful choice: make the requested action easy to accept, decline, defer, or answer briefly.
5. Close: thank for the specific help or attention; avoid extra apology loops.

## Tone Rules

- Be polite without shrinking the sender. One concise respect marker is enough.
- Praise specific behavior, work, advice, or time spent; avoid generic flattery.
- Ask clearly. A good request has an object, a reason, and a next action.
- Give the other side agency. Prefer “如果方便，能否…” plus a fallback over pressure.
- For conflict, separate facts, impact, need, and request. Avoid labels, motives, and moral verdicts.
- For negotiation, be firm on the substance and soft on the person. Name interests, options, and fair criteria.
- For help requests, show prior work and narrow the question. Do not make the receiver reconstruct the whole problem.
- For public or professional replies, acknowledge the issue, state verified facts, and give the next step. Do not overpromise.

## Output Contract

Default output is one best draft, ready to copy. If the situation is high-stakes or underspecified, output:

```markdown
沟通判断：<one paragraph>

可直接发送版本：
<draft>

发送前检查：
- <1-5 concrete checks>
```

If the user asks to review an existing draft, lead with the main risk, then provide a revised version. Do not produce many alternatives unless the user explicitly asks for options.

## Reference Navigation

- Use [communication-framework.md](./communication-framework.md) for NVC, smart questioning, principled negotiation, influence boundaries, and story framing.
- Use [scene-playbooks.md](./scene-playbooks.md) for first contact, help requests, follow-ups, thanks, refusal, apology, conflict, and maintainer/customer replies.
- Use [anti-patterns.md](./anti-patterns.md) when a draft feels low-posture, manipulative, defensive, vague, or overly polished.
- Use [source-map.md](./source-map.md) for local material provenance and risk boundaries.

Read only the reference file needed for the task. Keep final wording adapted to the user’s actual facts and channel.
