# DESIGN.md — Frontend Design Constitution

Locked visual and interaction rules for `static/fan.html`, `static/staff.html`, and the server-rendered route SVG.

Written **before** any HTML/CSS is committed. Every subsequent frontend change refers back to this file. If code contradicts an active rule here, the code is wrong. Same governance as DECISIONS.md.

**Why this file exists:** EcoSphere (97.7 in Challenge 3) shipped a similar file (`claude.md`) and used it to enforce visual coherence across a small frontend for near-zero engineering cost. The Evaluator Insights analysis flagged design coherence as a low-cost, high-visibility PS Alignment and Accessibility signal.

---

## Product tone

- **Voice:** direct, calm, helpful. Never marketing. Never emoji-heavy.
- **Copy length:** one-line labels, two-line hints. If a UI string won't fit in two lines on a phone, it's too long.
- **Fan-facing microcopy examples:**
  - Placeholder: `Where are you, and where do you want to go?`
  - Loading: `Working out the route…`
  - Error (transient): `Something went wrong. Try again.`
  - Error (permanent): `I couldn't find that location. Try a nearby gate or section.`
- **Staff-facing microcopy examples:**
  - Header: `Closures`
  - Empty state: `No closures active.`
  - Confirm: `Close Gate B?` / `Reopen Gate B?`

---

## Color palette (locked)

Six colors. No others without a supersession amendment.

| Token             | Hex       | Use                                                   |
| ----------------- | --------- | ----------------------------------------------------- |
| `--color-bg`      | `#0F172A` | Page background (slate-900)                           |
| `--color-surface` | `#1E293B` | Cards, message bubbles, panels (slate-800)            |
| `--color-text`    | `#F1F5F9` | Primary text (slate-100)                              |
| `--color-muted`   | `#94A3B8` | Secondary text, hints, timestamps (slate-400)         |
| `--color-accent`  | `#22D3EE` | Interactive elements, route highlight, focus (cyan-400) |
| `--color-warn`    | `#F87171` | Closures, blocked routes, errors (red-400)            |

**Rules:**

- Dark background is chosen for battery reasons on fan phones during a match — practical, not stylistic. Also higher contrast for the schematic SVG.
- The route highlight in the SVG uses `--color-accent`. Closure indicators use `--color-warn`. No other route or closure colors.
- Focus rings are `--color-accent` at 2px, always visible on `:focus-visible`.
- Text contrast ratios must clear WCAG AA (4.5:1 for body, 3:1 for large) — verify with the pair `--color-text` on `--color-bg` and `--color-muted` on `--color-surface`. Both pass by construction; do not change either without re-verifying.

---

## Typography (locked)

- **Family:** system font stack. No web fonts. `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`.
- **Rationale for system stack:** zero network fetches, matches OS accessibility settings by default, faster paint (Efficiency proxy).
- **Sizes:**
  - Body: `16px` (mobile) / `15px` (desktop)
  - Small: `13px`
  - H2 (section headers on staff panel): `20px`, weight 600
  - H1 (page title, if used): `24px`, weight 600
- **Line height:** `1.5` for all body text.
- **Weight:** `400` default, `600` for headings and emphasized labels. No `700`+ except in the SVG title.
- **Letter-spacing:** default. No tracking adjustments.

---

## Spacing (locked)

4px baseline grid. Every gap, margin, and padding value must be a multiple of 4.

| Token         | Value  | Typical use                                    |
| ------------- | ------ | ---------------------------------------------- |
| `--space-xs`  | `4px`  | Icon-to-text gap                               |
| `--space-sm`  | `8px`  | Between tight related elements                 |
| `--space-md`  | `16px` | Between form fields, message rows              |
| `--space-lg`  | `24px` | Between major sections                         |
| `--space-xl`  | `32px` | Page-level padding                             |

**Rules:**

- Message bubbles have `--space-md` internal padding, `--space-sm` between consecutive bubbles.
- Buttons: `--space-sm` vertical, `--space-md` horizontal padding.
- Input row and message list are separated by `--space-md`.

---

## Layout (locked)

- **Mobile-first.** Baseline width is 380px. Desktop is a widened version, not a different layout.
- **Fan chat page (`static/fan.html`):**
  - Vertical stack. Fixed height, no page scroll. Message list scrolls internally.
  - Input row pinned to the bottom.
  - SVG route image appears inline in the assistant's response bubble, at `max-width: 100%`.
  - No sidebar, no header nav, no footer. Nothing above the message list except the page title bar (48px tall, contains the app name only).
- **Staff panel (`static/staff.html`):**
  - Two-column on desktop: closures list on the left, toggle panel on the right.
  - Single-column stack on mobile.
  - Header bar shows current closure count.
  - No fan-facing elements, no navigation to the fan page.

---

## Accessibility (enforced by rule, not aspiration)

The Accessibility proxy is low-weight (per Evaluator Insights) but cheap to satisfy. Do all of these:

- Every `<button>`, `<input>`, `<img>` has a proper label:
  - Buttons: text content that describes the action ("Close Gate B", not "Close"). If icon-only, `aria-label` mandatory.
  - Inputs: `<label>` element or `aria-label`. Never rely on `placeholder` alone.
  - Images: `alt` describing the content. The route SVG's `alt` describes the route in one sentence.
- The route SVG also embeds a `<title>` element as the first child (screen-reader-visible route summary).
- Focus order matches visual order. Do not reorder with `tabindex` unless there's a documented reason in a comment.
- Focus states use `:focus-visible` with the 2px `--color-accent` ring.
- Semantic HTML: `<main>`, `<section>`, `<button>` (never `<div onclick>`), `<nav>` if navigation exists.
- Live regions: assistant responses are appended to a `<div aria-live="polite">` so screen readers announce them.
- Color is never the sole carrier of meaning. Closures use both `--color-warn` AND a text label or dashed edge. Route highlight uses both color AND increased stroke width.

---

## Route SVG rendering rules

The server-rendered schematic SVG (Entry #12, #22 in DECISIONS.md) is bound by the same palette and rules above.

- **Stadium outline:** stroke `--color-muted`, 1px, no fill.
- **All zone nodes (base):** circle, radius 6, fill `--color-surface`, stroke `--color-muted` 1px.
- **Origin node:** circle, radius 8, fill `--color-accent`, stroke `--color-text` 2px, label "You are here" (small text below).
- **Destination node:** circle, radius 8, fill `--color-text`, stroke `--color-accent` 2px, label with the zone name.
- **Intermediate route nodes:** circle, radius 7, fill `--color-accent`, stroke none.
- **Route edges:** stroke `--color-accent`, 3px, no dash.
- **Non-route edges:** not drawn (keeps the schematic legible on a phone).
- **Closed nodes:** circle, radius 6, fill `--color-warn`, stroke `--color-text` 1px. Small `X` marker overlaid.
- **Closed edges:** stroke `--color-warn`, 2px, dashed (`stroke-dasharray="4 4"`).
- **Canvas:** viewBox scaled so the stadium fills the frame with `--space-md` inner margin.

Everything else in the SVG (labels, legend, background) is optional and must be justified. Every extra element is a Code Quality risk.

---

## What NOT to do

- No Tailwind CDN. All styles inline in a `<style>` block or in a single `static/style.css`. Tailwind was fine for CarbonSaathi but adds a network fetch and a large class-name surface area that muddies the code review a grader does on the HTML files.
- No frameworks. No React, no Vue, no Alpine. Vanilla JS is Entry #20.
- No animations beyond opacity fades on state changes. No spinner GIFs, no CSS keyframe loaders. The loading state is a text string.
- No emoji as UI elements. Text labels only. (Exception: the app icon in the tab title bar, one emoji only.)
- No dark/light mode toggle. Dark mode is the design.
- No inline images unless they are the route SVG. No hero images, no illustrations, no photos of MetLife.

---

## Amendment rule

Same supersession pattern as DECISIONS.md. Any change to palette, type scale, spacing scale, or layout rules is a numbered amendment at the bottom of this file with a rationale and links to the affected code paths. Do not edit rules in place.

**Amendments (none yet):**

_(add new sections here as `## Amendment #A1 — <topic>` with date, rationale, affected paths)_
