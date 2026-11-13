# Premium Design Rules For Stitch

Use this only when the user asks for stronger taste, less generic UI, premium direction, UI polish, or "make it feel better" output. Do not apply every rule blindly; match the product type and audience.

## Design Direction

- Start from the product's real use: operational tools should be dense, quiet, scannable, and efficient; editorial, portfolio, brand, or game pages can be more expressive.
- Define atmosphere in concrete terms: density, visual variance, motion intensity, content hierarchy, and interaction rhythm.
- Avoid generic AI design tells: oversaturated purple-blue gradients, neon outer glows, huge gradient headlines, equal three-card feature rows, fake metrics, fake round numbers, stock placeholder names, scroll arrows, and "elevate / unleash / next-gen" copy.
- Use one coherent palette. Prefer neutral bases with one controlled accent. Avoid pure black; use charcoal, zinc, slate, or off-black when dark depth is needed.
- Use cards only where elevation communicates hierarchy. Dense tools often work better with dividers, tables, grouped rows, and stable controls.

## Typography

- Match type scale to container density. Do not use hero-sized text inside dashboards, sidebars, cards, forms, or tool panels.
- Keep headings balanced and avoid orphan words in compact headings.
- Use monospace for dense numbers, IDs, logs, metrics, code, timestamps, or tabular technical values.
- Do not force decorative fonts into work-focused software UI. Distinctive display fonts are acceptable for editorial or brand surfaces when they improve recognition.

## Layout

- Use CSS Grid or clear layout tracks for structured content. Avoid brittle percentage math.
- Constrain content with max-widths and stable responsive rules.
- Mobile layouts collapse predictably to one column; no horizontal overflow.
- Avoid overlapping text, images, controls, and decorative elements. Every element needs a clear spatial zone.
- Use stable dimensions for counters, boards, tile grids, toolbars, icon buttons, and fixed-format modules so hover states or dynamic labels do not shift layout.

## Components

- Buttons need clear hover, press, focus, disabled, loading, and active states. Press feedback should be restrained and interruptible.
- Inputs use labels, helper text, inline errors, focus rings, and predictable spacing.
- Loading states should match the real layout. Avoid generic spinners when skeletons or progress states are more informative.
- Empty and error states should explain the next action without marketing copy.
- Hit targets should be comfortable, typically around 40-44 px or larger for touch contexts.

## Motion

- Animate transform and opacity where possible.
- Avoid broad `transition: all` and unnecessary `will-change`.
- Entrances may be semantic and staggered; exits should be shorter and quieter.
- Infinite motion should communicate live status or activity, not decorate every component.
- Respect reduced-motion needs in implementation prompts when motion is significant.

## Prompt Pattern

When enhancing a Stitch prompt, produce:

```markdown
[One-line purpose and atmosphere]

**DESIGN SYSTEM (REQUIRED):**
- Platform:
- Product type:
- Density:
- Palette:
- Typography:
- Component rules:
- UI polish:
- Motion:
- Anti-patterns:

**PAGE STRUCTURE:**
1. ...
```

Keep this as design guidance, not a wall of bans. The best prompt makes the target interface more specific, not more ornate.
