#!/usr/bin/env python3
"""Render a Markdown research report as a comfortable standalone HTML file."""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:  # pragma: no cover - environment guidance
    print("Missing dependency: python package 'markdown'. Install it and rerun.", file=sys.stderr)
    raise


MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TOC_HEADING_RE = re.compile(r"^\s{0,3}#{2,6}\s+(?:目录|目錄|contents?|table of contents)\s*$", re.IGNORECASE)
TOC_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[^\]]+\]\(#[^)]+\)\s*$")
HR_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
MERMAID_BLOCK_RE = re.compile(
    r'<pre><code class="(?:[^"]*\s)?language-mermaid(?:\s[^"]*)?">(.*?)</code></pre>',
    re.S,
)
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"


REPORT_CSS = """/* Hallmark · checked: 2026-11-26 · shape: app screen · genre: modern-minimal · built: the project · redesign: polish · v2.0.0 */

/* ---------- Tokens · light paper ---------- */
:root {
  color-scheme: light;

  --bg: #f6f6f3;
  --paper: #fcfcfa;
  --surface: #f9f9f6;
  --surface-muted: #f0f0ec;
  --surface-hover: #e9e9e3;

  --ink: #181a1f;
  --ink-soft: #3a3d45;
  --muted: #646872;

  --line: #e3e3dd;
  --line-strong: #cdcdc5;

  --accent: #0f766e;
  --accent-hover: #0b5d56;
  --accent-ink: #fcfcfa;
  --accent-wash: #e4f1ef;
  --accent-line: #9cc9c4;
  --selection: #cfe8e4;

  --code-surface: #f2f2ee;
  --code-ink: #24272e;
  --inline-code-surface: #ecece7;

  --disabled-surface: #ecece8;
  --disabled-ink: #5d616b;

  --focus: #0f766e;

  --font-sans: "Inter", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-serif: "Source Serif 4", "Noto Serif SC", "Songti SC", "STSong", Georgia, serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;

  --radius-sm: 6px;
  --radius: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  --measure: 760px;
  --toc-width: 248px;

  --ease: cubic-bezier(0.2, 0, 0, 1);
  --dur: 160ms;

  accent-color: var(--accent);
}

/* ---------- Tokens · deep slate ---------- */
:root[data-theme="dark"] {
  color-scheme: dark;

  --bg: #0d1014;
  --paper: #14181f;
  --surface: #11151b;
  --surface-muted: #1a1f27;
  --surface-hover: #222833;

  --ink: #eef0f4;
  --ink-soft: #c9cdd5;
  --muted: #8d939e;

  --line: #262c36;
  --line-strong: #363d4a;

  --accent: #2dd4bf;
  --accent-hover: #5eead4;
  --accent-ink: #0d1014;
  --accent-wash: #112e2b;
  --accent-line: #1f6f66;
  --selection: #154a44;

  --code-surface: #0f1318;
  --code-ink: #dfe3ea;
  --inline-code-surface: #1d232c;

  --disabled-surface: #1a1f27;
  --disabled-ink: #9299a6;

  --focus: #2dd4bf;
}

/* ---------- Base ---------- */
*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
  scroll-padding-top: 24px;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}

html,
body {
  overflow-x: clip;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.75;
  font-feature-settings: "kern", "liga";
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

::selection {
  background: var(--selection);
  color: var(--ink);
}

/* ---------- Reading progress ---------- */
.progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  height: 2px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: 0 50%;
  transition: transform 80ms linear;
  pointer-events: none;
  will-change: transform;
}

/* ---------- Layout ---------- */
.layout {
  display: grid;
  grid-template-columns: var(--toc-width) minmax(0, 1fr);
  gap: 48px;
  align-items: start;
  max-width: 1240px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

main {
  min-width: 0;
  padding: 48px 64px 64px;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
}

article {
  max-width: var(--measure);
  margin: 0 auto;
  overflow-wrap: break-word;
}

/* ---------- Table of contents ---------- */
.toc-panel {
  position: sticky;
  top: 32px;
  max-height: calc(100vh - 64px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 16px 12px;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  scrollbar-width: thin;
  scrollbar-color: var(--line-strong) var(--surface);
}

.toc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0 0 8px;
  padding: 0 8px 12px;
  border-bottom: 1px solid var(--line);
}

.toc-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  text-transform: none;
  letter-spacing: 0;
  color: var(--ink);
}

.toc-panel ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.toc-panel li {
  margin: 0;
  padding: 0;
}

.toc-panel li ul {
  margin: 2px 0 4px;
  padding-left: 12px;
}

.toc-panel a {
  display: block;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
  text-decoration: none;
  transition: background-color var(--dur) var(--ease), color var(--dur) var(--ease);
}

.toc-panel li ul a {
  font-size: 12.5px;
}

.toc-panel a:hover {
  background: var(--surface-muted);
  color: var(--ink);
}

.toc-panel a:active {
  background: var(--surface-hover);
  color: var(--ink);
}

.toc-panel a.active,
.toc-panel a[aria-current="true"],
.toc-panel a[aria-current="location"] {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}

/* ---------- Theme toggle ---------- */
.theme-toggle {
  flex: none;
  margin: 0;
  padding: 4px 12px;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  background: var(--paper);
  color: var(--ink-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background-color var(--dur) var(--ease), border-color var(--dur) var(--ease), color var(--dur) var(--ease);
}

.theme-toggle:hover {
  background: var(--surface-muted);
  border-color: var(--line-strong);
  color: var(--ink);
}

.theme-toggle:active {
  background: var(--surface-hover);
  color: var(--ink);
}

.theme-toggle:disabled {
  background: var(--disabled-surface);
  color: var(--disabled-ink);
  border-color: var(--line);
  cursor: not-allowed;
}

/* ---------- Headings ---------- */
article h1,
article h2,
article h3,
article h4 {
  color: var(--ink);
  font-weight: 650;
  text-wrap: balance;
  scroll-margin-top: 24px;
}

article h1 {
  margin: 0 0 32px;
  padding: 0 0 20px;
  font-family: var(--font-serif);
  font-size: clamp(30px, 3.6vw, 40px);
  font-weight: 700;
  line-height: 1.22;
  letter-spacing: -0.01em;
  border-bottom: 1px solid var(--line);
}

article h2 {
  margin: 48px 0 16px;
  font-size: 24px;
  line-height: 1.35;
  letter-spacing: -0.005em;
}

article h3 {
  margin: 32px 0 12px;
  font-size: 19px;
  line-height: 1.45;
}

article h4 {
  margin: 24px 0 8px;
  font-size: 16px;
  line-height: 1.5;
  color: var(--ink-soft);
}

article h1 + h2,
article h2 + h3,
article h3 + h4 {
  margin-top: 24px;
}

/* ---------- Text ---------- */
article p {
  margin: 0 0 16px;
  color: var(--ink);
  text-wrap: pretty;
}

article strong,
article b {
  font-weight: 650;
  color: var(--ink);
}

article a {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-decoration-color: var(--accent-line);
  text-underline-offset: 4px;
  transition: color var(--dur) var(--ease), text-decoration-color var(--dur) var(--ease);
}

article a:hover {
  color: var(--accent-hover);
  text-decoration-color: var(--accent-hover);
}

article a:active {
  color: var(--accent-hover);
  text-decoration-color: var(--accent);
}

article hr {
  height: 0;
  margin: 40px 0;
  border: 0;
  border-top: 1px solid var(--line);
}

/* ---------- Lists ---------- */
article ul,
article ol {
  margin: 0 0 16px;
  padding-left: 24px;
}

article li {
  margin: 0;
  padding-left: 4px;
}

article li + li {
  margin-top: 4px;
}

article li > ul,
article li > ol {
  margin: 4px 0 0;
}

article li::marker {
  color: var(--muted);
}

/* ---------- Blockquote ---------- */
article blockquote {
  margin: 24px 0;
  padding: 16px 20px;
  background: var(--surface-muted);
  color: var(--ink-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

article blockquote p {
  color: var(--ink-soft);
}

article blockquote > :last-child {
  margin-bottom: 0;
}

/* ---------- Tables ---------- */
.table-scroll {
  margin: 24px 0;
  overflow-x: auto;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--line-strong) var(--paper);
}

.table-scroll table {
  width: 100%;
  min-width: 480px;
  margin: 0;
  border-collapse: collapse;
  font-size: 14px;
  line-height: 1.55;
  font-variant-numeric: tabular-nums;
}

.table-scroll th,
.table-scroll td {
  padding: 8px 16px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--line);
}

.table-scroll th {
  background: var(--surface-muted);
  color: var(--ink);
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}

.table-scroll td:first-child {
  white-space: nowrap;
}

.table-scroll td {
  background: var(--paper);
  color: var(--ink-soft);
}

.table-scroll tbody tr:nth-child(even) td {
  background: var(--surface);
  color: var(--ink-soft);
}

.table-scroll tbody tr:last-child td {
  border-bottom: 0;
}

.table-scroll tbody tr:hover td {
  background: var(--surface-muted);
  color: var(--ink);
}

/* ---------- Code ---------- */
article code {
  font-family: var(--font-mono);
  font-size: 0.9em;
  font-variant-ligatures: none;
}

article :not(pre) > code {
  padding: 2px 4px;
  background: var(--inline-code-surface);
  color: var(--code-ink);
  border-radius: 4px;
}

article pre {
  margin: 24px 0;
  padding: 16px 20px;
  overflow-x: auto;
  background: var(--code-surface);
  color: var(--code-ink);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: 13.5px;
  line-height: 1.65;
  tab-size: 2;
  scrollbar-width: thin;
  scrollbar-color: var(--line-strong) var(--code-surface);
}

article pre code {
  padding: 0;
  background: none;
  color: var(--code-ink);
  font-size: inherit;
  border-radius: 0;
}

/* ---------- Diagrams & media ---------- */
article .mermaid {
  margin: 24px 0;
  padding: 24px;
  overflow-x: auto;
  text-align: center;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

article .mermaid svg {
  max-width: 100%;
  height: auto;
}

article img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 24px auto;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

/* ---------- Back to top ---------- */
.back-top {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 40;
  margin: 0;
  padding: 8px 16px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  text-wrap-mode: nowrap;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: opacity var(--dur) var(--ease), transform var(--dur) var(--ease), visibility var(--dur) var(--ease), background-color var(--dur) var(--ease);
}

.js .back-top {
  opacity: 0;
  visibility: hidden;
  transform: translateY(8px);
}

.js .back-top.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.back-top:hover {
  background: var(--surface-muted);
  color: var(--ink);
}

.back-top:active {
  background: var(--surface-hover);
  color: var(--ink);
}

.back-top.show:active {
  transform: translateY(2px);
}

.back-top:disabled {
  background: var(--disabled-surface);
  color: var(--disabled-ink);
  border-color: var(--line);
  cursor: not-allowed;
}

/* ---------- Focus ---------- */
:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}

a:focus-visible,
button:focus-visible,
.toc-panel a:focus-visible,
.theme-toggle:focus-visible,
.back-top:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}

.table-scroll:focus-visible,
article pre:focus-visible,
.toc-panel:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}

:focus:not(:focus-visible) {
  outline: none;
}

/* ---------- Reduced motion ---------- */
@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  .progress,
  .back-top,
  .theme-toggle,
  .toc-panel a,
  article a {
    transition: none;
  }

  .back-top,
  .back-top.show,
  .back-top.show:active {
    transform: none;
  }
}

/* ---------- Narrow screens ---------- */
@media (max-width: 1020px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
    padding: 16px 16px 48px;
  }

  .toc-panel {
    position: static;
    max-height: 320px;
  }

  main {
    padding: 32px 24px 48px;
  }

  article h1 {
    margin-bottom: 24px;
    padding-bottom: 16px;
    font-size: clamp(26px, 6vw, 32px);
  }

  article h2 {
    margin-top: 40px;
    font-size: 21px;
  }

  article h3 {
    font-size: 18px;
  }

  .back-top {
    right: 16px;
    bottom: 16px;
  }
}

@media (max-width: 560px) {
  main {
    padding: 24px 16px 40px;
    border-radius: var(--radius);
  }

  article pre,
  article .mermaid {
    padding: 12px 16px;
  }
}

/* ---------- Print ---------- */
@media print {
  html {
    scroll-behavior: auto;
  }

  body {
    background: var(--paper);
    color: var(--ink);
    font-size: 11pt;
    line-height: 1.6;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .progress,
  .toc-panel,
  .back-top,
  .theme-toggle {
    display: none;
  }

  .layout {
    display: block;
    max-width: none;
    margin: 0;
    padding: 0;
  }

  main {
    padding: 0;
    background: var(--paper);
    color: var(--ink);
    border: 0;
    border-radius: 0;
  }

  article {
    max-width: none;
  }

  article h1,
  article h2,
  article h3,
  article h4 {
    break-after: avoid;
  }

  article p,
  article li {
    orphans: 3;
    widows: 3;
  }

  article pre {
    overflow: visible;
    text-wrap-mode: wrap;
  }

  .table-scroll {
    overflow: visible;
  }

  .table-scroll table {
    min-width: 0;
  }

  article pre,
  article blockquote,
  article img,
  article .mermaid,
  .table-scroll tr {
    break-inside: avoid;
  }

  article a[href^="http"]::after {
    content: " (" attr(href) ")";
    font-size: 0.85em;
    color: var(--muted);
    overflow-wrap: anywhere;
  }
}"""


def is_external(src: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src)) or src.startswith("//")


def embed_images(text: str, base_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        alt, src = match.groups()
        if is_external(src):
            return match.group(0)

        image_path = (base_dir / src).resolve()
        if not image_path.exists():
            return match.group(0)

        mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"![{alt}](data:{mime};base64,{encoded})"

    return MD_IMAGE_RE.sub(replace, text)


def normalize_markdown(text: str) -> str:
    """Make common report Markdown patterns parse consistently."""
    text = text.replace("｜", "|")
    lines = text.splitlines()
    normalized: list[str] = []
    in_fence = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence

        if (
            not in_fence
            and LIST_ITEM_RE.match(line)
            and normalized
            and normalized[-1].strip()
            and not LIST_ITEM_RE.match(normalized[-1])
        ):
            normalized.append("")

        normalized.append(line)

        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if (
            not in_fence
            and LIST_ITEM_RE.match(line)
            and next_line.strip()
            and not LIST_ITEM_RE.match(next_line)
            and not next_line.startswith((" ", "\t"))
        ):
            normalized.append("")

    return "\n".join(normalized) + ("\n" if text.endswith("\n") else "")


def strip_inline_toc(text: str) -> str:
    """Remove a generated Markdown TOC when a side TOC will be rendered."""
    lines = text.splitlines()
    stripped: list[str] = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]
        marker = line.strip()
        if marker.startswith("```") or marker.startswith("~~~"):
            in_fence = not in_fence
            stripped.append(line)
            i += 1
            continue

        if not in_fence and TOC_HEADING_RE.match(line):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            item_count = 0
            while j < len(lines) and TOC_ITEM_RE.match(lines[j]):
                item_count += 1
                j += 1

            if item_count >= 2:
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and HR_RE.match(lines[j]):
                    j += 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                i = j
                continue

        stripped.append(line)
        i += 1

    return "\n".join(stripped) + ("\n" if text.endswith("\n") else "")


def title_from_body(body: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    if not match:
        return "Markdown Report"
    return re.sub(r"<.*?>", "", match.group(1)).strip() or "Markdown Report"


def description_from_body(body: str, fallback: str) -> str:
    match = re.search(r"<p[^>]*>(.*?)</p>", body, re.S)
    if match:
        plain = re.sub(r"<.*?>", "", match.group(1)).strip()
        plain = re.sub(r"\s+", " ", plain).replace("—", "，").replace("–", "至")
        if plain:
            return plain[:140]
    return f"{fallback} 独立离线排版报告。"


def render_mermaid_blocks(body: str) -> tuple[str, int]:
    """Convert fenced mermaid code blocks into Mermaid render targets."""

    def replace(match: re.Match[str]) -> str:
        diagram = html.unescape(match.group(1)).strip()
        return f'<div class="mermaid">{html.escape(diagram)}</div>'

    return MERMAID_BLOCK_RE.subn(replace, body)


def build_mermaid_js(source: str) -> str:
    if source == "none":
        return ""

    if source == "local":
        loader = '<script src="mermaid.min.js"></script>'
    else:
        loader = f'<script src="{MERMAID_CDN}"></script>'

    return f"""
  {loader}
  <script>
    (() => {{
      if (!window.mermaid) return;
      const cs = getComputedStyle(document.documentElement);
      const token = (k, fb) => (cs.getPropertyValue(k) || '').trim() || fb;
      window.mermaid.initialize({{
        startOnLoad: true,
        securityLevel: 'loose',
        theme: 'base',
        themeVariables: {{
          primaryColor: token('--accent-wash', '#e4f1ef'),
          primaryTextColor: token('--ink', '#181a1f'),
          primaryBorderColor: token('--accent', '#0f766e'),
          lineColor: token('--muted', '#646872'),
          secondaryColor: token('--surface-muted', '#f0f0ec'),
          tertiaryColor: token('--paper', '#fcfcfa'),
          mainBkg: token('--paper', '#fcfcfa'),
          clusterBkg: token('--surface', '#f9f9f6'),
          clusterBorder: token('--line', '#e3e3dd'),
          edgeLabelBackground: token('--paper', '#fcfcfa'),
          textColor: token('--ink', '#181a1f'),
          titleColor: token('--ink', '#181a1f'),
          nodeTextColor: token('--ink', '#181a1f'),
          fontFamily: token('--font-sans', 'sans-serif')
        }}
      }});
    }})();
  </script>
"""


def build_js(with_js: bool) -> str:
    scroll_logic = """
      const progress = document.querySelector('.progress');
      const topBtn = document.querySelector('.back-top');
      const links = [...document.querySelectorAll('.toc-panel a[href^="#"]')];
      const headings = links
        .map(a => document.getElementById(decodeURIComponent(a.hash.slice(1))))
        .filter(Boolean);

      function onScroll() {
        const max = document.documentElement.scrollHeight - innerHeight;
        const ratio = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 0;
        if (progress) progress.style.transform = `scaleX(${ratio})`;
        if (topBtn) topBtn.classList.toggle('show', scrollY > innerHeight * 0.6);

        let current = headings[0];
        for (const h of headings) {
          if (h.getBoundingClientRect().top <= 120) current = h;
        }
        links.forEach(a => a.classList.toggle('active', Boolean(current && a.hash === `#${current.id}`)));
      }

      addEventListener('scroll', onScroll, { passive: true });
      topBtn?.addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
      onScroll();
""" if with_js else ""

    return f"""
  <script>
    (() => {{
      const root = document.documentElement;
      root.classList.add('js');
      const toggleBtn = document.querySelector('.theme-toggle');
      const applyTheme = (mode) => {{
        root.dataset.theme = mode;
        if (toggleBtn) toggleBtn.textContent = mode === 'dark' ? '浅色' : '深色';
      }};
      const saved = (() => {{
        try {{ return localStorage.getItem('report.theme'); }} catch (_e) {{ return null; }}
      }})();
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      applyTheme(saved === 'dark' || (!saved && prefersDark) ? 'dark' : 'light');
      toggleBtn?.addEventListener('click', () => {{
        const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        try {{ localStorage.setItem('report.theme', next); }} catch (_e) {{}}
      }});
{scroll_logic}    }})();
  </script>
"""


def build_html(title: str, toc: str, body: str, with_js: bool, mermaid_source: str = "none") -> str:
    safe_title = html.escape(title.replace("—", "：").replace("–", "至"))
    desc = html.escape(description_from_body(body, title))
    progress = '<div class="progress"></div>' if with_js else ""
    back_top = '<button class="back-top" type="button" aria-label="返回顶部">顶部</button>' if with_js else ""
    js = build_js(with_js)
    mermaid_js = build_mermaid_js(mermaid_source)

    return f"""<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="{desc}">
  <title>{safe_title}</title>
  <style>
{REPORT_CSS}
  </style>
</head>
<body>
  {progress}
  <div class="layout">
    <aside class="toc-panel" aria-label="目录">
      <div class="toc-head">
        <p class="toc-title">目录</p>
        <button class="theme-toggle" type="button" aria-label="切换明暗主题">深色</button>
      </div>
      {toc}
    </aside>
    <main>
      <article>
        {body}
      </article>
    </main>
  </div>
  {back_top}
  {mermaid_js}
  {js}
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input Markdown file")
    parser.add_argument("output", nargs="?", help="Output HTML file")
    parser.add_argument("--embed-images", dest="embed_images", action="store_true", default=True)
    parser.add_argument("--no-embed-images", dest="embed_images", action="store_false")
    parser.add_argument("--with-js", action="store_true", help="Add progress, active TOC, and back-to-top interactions")
    parser.add_argument("--keep-inline-toc", action="store_true", help="Keep an existing Markdown TOC in the article body")
    parser.add_argument(
        "--mermaid-source",
        choices=["auto", "cdn", "local", "none"],
        default="auto",
        help="Render mermaid fences with CDN JS, local mermaid.min.js, or disable rendering",
    )
    parser.add_argument("--title-style", choices=["comfortable"], default="comfortable")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        print(f"Input file not found: {source}", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser().resolve() if args.output else source.with_suffix(".html")

    text = normalize_markdown(source.read_text(encoding="utf-8"))
    if not args.keep_inline_toc:
        text = strip_inline_toc(text)
    if args.embed_images:
        text = embed_images(text, source.parent)

    md = markdown.Markdown(
        extensions=["extra", "toc", "sane_lists"],
        extension_configs={"toc": {"permalink": False, "separator": "-"}},
    )
    body = md.convert(text)
    body = re.sub(r"(<table>.*?</table>)", r'<div class="table-scroll">\1</div>', body, flags=re.S)
    body, mermaid_count = render_mermaid_blocks(body)
    mermaid_source = "none"
    if mermaid_count and args.mermaid_source != "none":
        mermaid_source = "cdn" if args.mermaid_source == "auto" else args.mermaid_source
    html_out = build_html(title_from_body(body), md.toc, body, args.with_js, mermaid_source)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_out, encoding="utf-8")
    print(output)
    print(f"tables={html_out.count('<table')}")
    print(f"images={html_out.count('<img')}")
    print(f"embedded_images={html_out.count('data:image/')}")
    print(f"mermaid={mermaid_count}")
    if mermaid_source == "cdn":
        print("mermaid_source=cdn")
    elif mermaid_source == "local":
        print("mermaid_source=local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
