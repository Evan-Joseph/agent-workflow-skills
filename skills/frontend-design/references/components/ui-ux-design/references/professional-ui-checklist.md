# Professional UI Checklist

本文件在实现、审查或交付 UI 代码前读取，用于避免常见的低质感界面问题。

## Icons And Visual Elements

| Rule | Do | Don't |
|------|----|----- |
| No emoji icons | Use SVG icons such as Heroicons, Lucide, Simple Icons | Use emojis as UI icons |
| Stable hover states | Use color, opacity, border or shadow transitions | Use scale transforms that shift layout |
| Correct brand logos | Research official SVG from Simple Icons | Guess logo paths or redraw brand marks |
| Consistent icon sizing | Use fixed viewBox and consistent width/height | Mix arbitrary icon sizes |

## Interaction And Cursor

| Rule | Do | Don't |
|------|----|----- |
| Cursor pointer | Add `cursor-pointer` to clickable or hoverable cards | Leave default cursor on interactive elements |
| Hover feedback | Provide visible feedback | No indication element is interactive |
| Smooth transitions | Use 150-300ms transitions | Instant changes or slow transitions over 500ms |
| Specific transitions | Transition only changed properties | Use `transition: all` or broad Tailwind `transition` blindly |
| Press feedback | Use restrained press scale such as `0.96` when appropriate | Use exaggerated press scale below `0.95` |
| Interruptible states | Use transitions for hover, toggle, open and close states | Use fixed keyframes for user-interruptible state changes |

## UI Polish Microdetails

Full rules live in [ui-polish-microdetails.md](ui-polish-microdetails.md). Use this quick gate before delivery:

| Rule | Do | Don't |
|------|----|----- |
| Text wrapping | Use `text-wrap: balance` for headings and `pretty` for short body text | Leave obvious orphan words in hero, cards or labels |
| Tabular numbers | Use `tabular-nums` for dynamic counters, prices, timers and dashboards | Let changing digits shift layout |
| Concentric radius | Make outer radius account for inner radius plus padding | Use identical radii on tight nested surfaces |
| Optical alignment | Adjust icon/text and asymmetric icons by visual weight | Trust geometric centering when it visibly looks off |
| Depth edges | Use subtle shadow/ring for cards, buttons and images | Add hard borders everywhere for depth |
| Image outline | Use black/10 in light mode and white/10 in dark mode | Use tinted neutral outlines that make image edges look dirty |
| Hit area | Keep interactive targets near 40-44px and avoid overlap | Leave tiny icon controls hard to click |

## Light/Dark Mode Contrast

| Rule | Do | Don't |
|------|----|----- |
| Glass card light mode | Use `bg-white/80` or higher opacity | Use `bg-white/10` in light mode |
| Text contrast light | Use `#0F172A` or similarly dark text | Use `#94A3B8` for body text |
| Muted text light | Use `#475569` minimum | Use gray-400 or lighter |
| Border visibility | Use visible light-mode borders | Use `border-white/10` in light mode |

## Layout And Spacing

| Rule | Do | Don't |
|------|----|----- |
| Floating navbar | Add edge spacing such as `top-4 left-4 right-4` | Stick floating nav to `top-0 left-0 right-0` |
| Content padding | Account for fixed navbar height | Let content hide behind fixed elements |
| Consistent max-width | Use a stable container width system | Mix unrelated max widths |

## Pre-Delivery Checklist

Visual quality:

- No emojis used as icons.
- All icons from a consistent icon set.
- Brand logos are correct.
- Hover states do not cause layout shift.
- Theme colors are used directly, not wrapped unnecessarily.

Interaction:

- Clickable elements have `cursor-pointer`.
- Hover states provide clear visual feedback.
- Transitions are smooth.
- Focus states are visible for keyboard navigation.
- User-interruptible animations use transitions, not one-shot keyframes.
- Dynamic numbers use tabular numerals where layout stability matters.
- No `transition: all` or `will-change: all`.
- Small controls have adequate hit areas.

Light/dark mode:

- Light mode text has sufficient contrast.
- Glass and transparent elements remain visible in light mode.
- Borders are visible in both modes.
- Both modes have been checked before delivery.

Layout:

- Floating elements have proper spacing from edges.
- Content is not hidden behind fixed navbars.
- Responsive layout works at 375px, 768px, 1024px and 1440px.
- No horizontal scroll on mobile.

Accessibility:

- Images have alt text.
- Form inputs have labels.
- Color is not the only indicator.
- `prefers-reduced-motion` is respected.
