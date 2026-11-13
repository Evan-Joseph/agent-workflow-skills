---
name: report-format-discovery
description: "用于发现某类报告、方案、综述、尽调、政策简报、行业研究、竞品分析或技术选型文档的结构规范、章节要素、证据要求和写作约束。Use before drafting or reviewing a report when the format is uncertain."
metadata:
  short-description: 报告结构规范发现
---

# Report Format Discovery

Use this skill when the user needs to decide what a specific report should look
like before drafting or reviewing it. This skill studies report structure, not
the factual conclusion itself.

## When To Use

- The user asks "这类报告应该怎么写", "给我报告结构", "行业报告框架", "竞品分析模板", "技术选型报告结构", "尽调报告怎么组织".
- A research, office, or design deliverable needs a defensible section outline before writing.
- Another skill is about to produce a long report and needs `report_shape`, required sections, tables, charts, and tone constraints.
- The user needs an industry map, investment memo, travel/cultural research brief, competition deliverable plan, or other domain-specific report structure before content generation.

## Source Strategy

Prefer current, authoritative sources:

- Official standards, regulator guidance, institutional templates, journal author guidelines, or professional organizations.
- High-quality real examples from credible publishers.
- For academic and medical reviews, prefer methodology organizations and journal instructions.
- For industry, market, product, and policy reports, prefer official reports, recognized consultancies, standards bodies, or primary organizations.

Avoid generic SEO templates unless no better source exists.

## Output

Return a compact format specification:

```markdown
# Report Format: <type>

## Use Case
<audience, decision context, region if relevant>

## Recommended Structure
1. <section>: <purpose and expected evidence>
2. ...

## Required Elements
- <tables, charts, appendices, citations, methods, assumptions>

## Style Constraints
- <tone, density, citation style, claims discipline>

## Anti-Patterns
- <what to avoid>

## Source Basis
- <source name + URL + why it matters>
```

## Rules

- Extract structure and constraints only; do not fill in factual conclusions unless the user asks.
- If a standard source and real examples conflict, state the difference.
- If evidence is thin, say which parts are inferred.

## Domain Patterns

Use these as structure probes, not as mandatory templates:

- **Industry map**: value chain, bottleneck, value-capture point, base-rate metrics, unresolved strategic questions, source basis.
- **Investment memo**: project identity, market reframing, flywheel or order-creation mechanism, evidence, risks, valuation or terms if provided, decision and next diligence.
- **Travel/cultural research**: historical layers, museums and artifacts, architecture or sites, archaeological context, reading/viewing list, route constraints, source confidence.
- **Design or competition entry**: official brief snapshot, category branch, deliverables, constraints, concept, asset plan, review gates, submission checklist.
- **Research brief**: question, search method, source register, evidence map, uncertainty, recommended next checks.

When a pattern overlaps a specialist Skill, use this Skill only to define the report shape, then hand execution to the specialist.
