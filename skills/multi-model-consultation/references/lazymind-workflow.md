# LazyMind Workflow Mapping

Use this optional mapping when a consultation must survive more than one agent
session or when a human needs to approve data exposure, retries, and the final
recommendation separately. Keep the native Skill path for a small, low-risk
panel that can be run and reviewed in one session.

This is a candidate mapping to a [LazyMind](https://github.com/LazyAGI/LazyMind)
Workflow. The source contract and this document can be checked locally, but this
exact conversion has not been run end to end.

## Pinned source and native path

- Repository: [`Evan-Joseph/agent-workflow-skills`](https://github.com/Evan-Joseph/agent-workflow-skills)
- Commit: [`830b9e85ebb82b45847d345bcb57a6dc7a3e1919`](https://github.com/Evan-Joseph/agent-workflow-skills/commit/830b9e85ebb82b45847d345bcb57a6dc7a3e1919)
- Skill: [`skills/multi-model-consultation/SKILL.md`](https://github.com/Evan-Joseph/agent-workflow-skills/blob/830b9e85ebb82b45847d345bcb57a6dc7a3e1919/skills/multi-model-consultation/SKILL.md), Git blob `ffd28a8310cd019761e78265e36f37d0f3801bde`
- License: Apache-2.0

The native path builds one provider-neutral prompt packet, chooses the smallest
useful panel, runs the available local panel tool, compares raw answers, and
makes one final recommendation. Inputs are the goal, confirmed facts,
constraints, questions, output contract, panel shape, and any approved image.
Outputs are the raw model responses, comparison, recommendation, and next
action.

## Start the Workflow path

1. Install LazyMind using its [Quick Start](https://github.com/LazyAGI/LazyMind#quick-start).
2. Add the pinned Skill source above and choose **Skill -> Workflow**.
3. Compare the generated inputs, outputs, steps, tools, and failure paths with
   the pinned Skill before publishing the Workflow.
4. Keep provider calls disabled until a human has reviewed the exact prompt,
   attachments, model roster, expected cost, and allowed data exposure.

Conversion does not provide model credentials, grant permission to disclose
private material, or prove that a larger panel improves the decision.

## Workflow contract

Preserve these stages and handoffs:

1. **Scope** - record the goal, confirmed facts, constraints, questions, output
   contract, panel shape, and reason a direct source check is insufficient.
2. **Prompt review** - save the prompt packet as an artifact. A human confirms
   that it excludes secrets, credentials, unapproved proprietary material, and
   irrelevant persuasive framing.
3. **Panel plan** - record the selected model group, provider tool, attachment
   list, expected cost boundary, and output location. Missing tools or approval
   block dispatch.
4. **Dispatch** - run the smallest approved panel. Save each raw response,
   model identifier, invocation status, and error separately rather than
   overwriting earlier attempts.
5. **Completeness check** - verify that every approved panel slot has either a
   response or an explicit failure. A retry requires a human decision and keeps
   the failed attempt as an artifact.
6. **Compare** - produce a comparison artifact covering consensus, meaningful
   disagreement, unsupported confidence, missing constraints, and evidence that
   still needs a primary-source check.
7. **Recommendation review** - present the comparison and proposed final call.
   Keep the Workflow pending until a human accepts, revises, or rejects it.
8. **Hand off** - save the accepted recommendation, unresolved uncertainty, and
   next action without deleting the raw panel evidence.

The reviewed prompt hands off to the panel plan. Raw responses and explicit
failures hand off to completeness checking. Only a complete or human-approved
partial panel can hand off to comparison; panel majority never bypasses the
recommendation review.

## Restricted trial

Start without provider credentials. Use two short fixture responses stored in a
temporary test directory: one that supports an option and one that names a
missing constraint. Do not include proprietary text or call a paid model.

Check that the Workflow:

- remains pending until prompt exposure is approved;
- stores the two raw responses as separate artifacts;
- blocks comparison when one expected response is absent;
- preserves a failed attempt before exposing an explicit retry decision;
- records disagreement and the missing constraint instead of averaging them;
- keeps the proposed recommendation pending for human review; and
- hands off the accepted recommendation with unresolved uncertainty attached.

If the conversion, artifact, approval, or retry tools are unavailable, stop at
that boundary and mark the affected stages unverified. Do not simulate a
successful panel run.

## Limits and disclosure

External model outputs remain untrusted advice. Direct source verification,
privacy review, and cost control still apply. This mapping does not claim better
accuracy, lower cost, faster execution, or compatibility with every provider.

The contributor also contributes to LazyMind. This mapping does not imply that
this repository endorses LazyMind.
