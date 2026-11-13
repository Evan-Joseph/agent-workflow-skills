# Source-Backed Best Practices

Use these references when the user asks for rationale, citations, or current best-practice justification. For dynamic API/model details, re-check official docs before making hard claims.

## OpenAI Image Generation Prompting

- GPT image prompting guide: https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
- Image generation API guide: https://developers.openai.com/api/docs/guides/image-generation
- Images and vision guide: https://developers.openai.com/api/docs/guides/images-vision

Key operational takeaways:

- Use structured prompts with explicit goal, subject, details, and constraints.
- Use short labeled segments for complex requests.
- State layout and placement when layout matters.
- Put literal text in quotes and specify typography/placement.
- Reference each input image by index and role.
- Separate what changes from what must remain invariant.
- Iterate with small changes instead of overloaded prompts.
- Use higher quality for dense text, detailed infographics, and high-resolution outputs.
- For generated paper figures, treat text, numbers, axes, legends, and schema-like strings as proofing targets even when the model renders them well.

## AI Academic Diagram Systems And Community Practice

- PaperBanana HN launch discussion: https://news.ycombinator.com/item?id=47132143

Key operational takeaways:

- Strong AI paper diagrams benefit from retrieval before generation: find structurally similar academic diagrams, then plan layout, components, connections, and groupings before style polishing.
- A useful pipeline has separate planning, styling, visualization, and critique stages; a single direct "make it beautiful" prompt tends to produce generic diagrams.
- CS/AI methodology diagrams follow recognizable visual conventions, but generated text can still be garbled, so labels should remain sparse and be rebuilt in editable form.
- Community/social sources, including 小红书 or forum examples, are useful for style leads and prompting language only; verify scientific claims and final figure constraints against primary sources and the paper itself.

## Scientific Figure Design

- Nature figure preparation guide: https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/
- PLOS Computational Biology "Ten Simple Rules for Better Figures": https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833
- ACM figure description/accessibility guidance: https://authors.acm.org/proceedings/production-information/describing-figures

Key operational takeaways:

- Figures should communicate one clear message.
- Avoid default chart styling when it hurts interpretation.
- Avoid rainbow/jet palettes, 3D chart effects, shadows, and decoration.
- Include readable labels, complete axes, units, legends, and meaningful captions.
- Use accessible color and redundant encodings such as shape, line style, marker, and order.
- Separate caption/explanatory text from the visual when that improves readability.

## CS/AI Conference Constraints

- Use official venue templates and author kits for final page/figure constraints.
- Prefer vector PDF for plots and diagrams.
- Check final displayed size, not only the source canvas.
- Ensure embedded fonts and readable text in the compiled PDF.

## Fast Search Queries

Use these when local references are weak:

- `PaperBanana publication-ready diagrams academic diagrams methodology text`
- `AI generated academic paper figures best practices prompt engineering diagrams`
- `site:github.com scientific diagram generation from paper text`
- `site:xiaohongshu.com 科研绘图 AI 论文插图 提示词`
- `site:linux.do AI 科研 绘图 论文 插图 提示词`
