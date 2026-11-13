# Design Mappings & Descriptors

Use these mappings to transform vague user requests into precise, high-fidelity design instructions.

## UI/UX Keyword Refinement

| Vague Term | Enhanced Professional Terminology |
|:---|:---|
| "menu at the top" | "sticky navigation bar with logo and list items" |
| "big photo" | "high-impact hero section with full-width imagery" |
| "list of things" | "responsive card grid with hover states and subtle elevations" |
| "button" | "primary call-to-action button with micro-interactions" |
| "form" | "clean form with labeled input fields, validation states, and submit button" |
| "picture area" | "hero section with focal-point image or video background" |
| "sidebar" | "collapsible side navigation with icon-label pairings" |
| "popup" | "modal dialog with overlay and smooth entry animation" |
| "looks rough / feels off" | "polish pass covering balanced text wrapping, concentric corner relationships, optical icon alignment, clean image outlines, adequate hit targets, and complete hover/press/focus states" |
| "make it feel better" | "targeted interface refinement: stable dynamic numbers, restrained interruptible motion, subtle enter/exit transitions, and surface depth that uses shadows/rings instead of hard borders where appropriate" |

## Atmosphere & "Vibe" Descriptors

Add these adjectives to set the mood and aesthetic philosophy:

| Basic Vibe | Enhanced Design Description |
|:---|:---|
| "Modern" | "Clean, minimal, with generous whitespace and high-contrast typography." |
| "Professional" | "Sophisticated, trustworthy, utilizing subtle shadows and a restricted, premium palette." |
| "Fun / Playful" | "Vibrant, organic, with rounded corners, bold accent colors, and bouncy micro-animations." |
| "Dark Mode" | "Electric, high-contrast accents on deep slate or near-black backgrounds." |
| "Luxury" | "Elegant, spacious, with fine lines, serif headers, and a focus on high-fidelity photography." |
| "Tech / Cyber" | "Futuristic, neon accents, glassmorphism effects, and technological monospaced typography." |

## Geometry & Shape Translation

Convert technical values into physical descriptions for Stitch:

- **Pill-shaped**: Used for `rounded-full` elements (buttons, tags).
- **Softly rounded**: Used for `rounded-xl` (12px) or `rounded-2xl` (16px) containers.
- **Sharp/Precise**: Used for `rounded-none` or `rounded-sm` elements.
- **Glassmorphism**: Semi-transparent surfaces with background blur and thin borders.

## Depth & Elevation

- **Flat**: No shadows, focus on color blocking and borders.
- **Whisper-soft**: Diffused, light shadows for subtle lift.
- **Floating**: High-offset, soft shadows for elements that appear high above the surface.
- **Inset**: Inner shadows for pressable or nested elements.

## Polish Microdetails

- **Balanced text wrapping**: Headings and compact titles should avoid awkward orphan words.
- **Concentric corner relationships**: Tight nested surfaces should have outer corners that visually account for inner radius plus padding.
- **Optical icon alignment**: Asymmetric icons such as arrows or play triangles may need visual nudging.
- **Clean image edge**: Screenshots and rectangular media need subtle neutral outlines or inset rings in both light and dark modes.
- **Stable numeric layout**: Updating counters, prices, scores, and dashboard metrics should keep digit widths stable.
- **Interruptible state motion**: Hover, press, toggle, drawer, and tab changes should respond smoothly when the user reverses intent.
