# 🏛️ The Visual Craft Floor: Mechanics & Category Refusals

A pinned brief or committed visual world overrides anything here; habitual defaults do not. The craft floor defines the non-negotiable baseline of production-grade UI design.

---

## 1. Mechanical Verification Floor

Run these checks together in batched inspection passes:

- **Contrast Ratios (WCAG AA Strict)**:
  - Body copy & placeholder text: $\ge 4.5:1$ against background.
  - Large display text ($\ge 18\text{pt}$ or bold $\ge 14\text{pt}$): $\ge 3:1$.
  - Interactive controls, focus rings, icons: $\ge 3:1$.
  - *Colored Surfaces*: Tint secondary text using foreground/surface hue; never generic washed-out gray `#6b7280`.
- **Depth & Elevation**:
  - Shadows MUST carry an intentional vertical offset (`y: 2px..16px`) and soft proportional blur (`blur: 4px..32px`).
  - *Refusal*: Zero-offset colored glowing halos (`box-shadow: 0 0 15px rgba(...)`) are cheap decoration, not depth.
  - *Elevation Singularity*: Declare elevation with EITHER a subtle border OR a shadow, never both stacked with equal prominence (the "ghost card").
- **Spacing Rhythm & Hierarchy**:
  - Tight related groups (`gap-1` to `gap-2`), generous section separation (`py-16` to `py-24`).
  - *Heading Asymmetry*: Always provide significantly more whitespace ABOVE a heading than below it (e.g., `mt-12 mb-4`), binding headings to their downstream content.
- **Typography Standards**:
  - *Measure*: Body copy MUST stay within comfortable reading width: $45\text{ch} - 75\text{ch}$ ($65\text{ch}$ optimal). Never span prose across a full $1200\text{px}$ container.
  - *Web Body Floor*: $1\text{rem}$ ($16\text{px}$) minimum for standard reading text.
  - *3-Axis Dark Mode Compensation*: Light text on dark backgrounds visually bleeds. Compensate along three axes:
    1. Line height: $+0.05$ leading.
    2. Tracking: $+0.01\text{em}$ to $+0.02\text{em}$ letter spacing.
    3. Font weight: step down slightly if bold, or up if ultra-thin.
  - *Tracking Floor*: Never exceed $-0.04\text{em}$. $-0.02\text{em}$ to $-0.03\text{em}$ yields tight, legible display type.
- **Motion & Micro-interactions**:
  - One decisive authored moment per scroll region, not scattered micro-effects.
  - Exponential ease-out (`cubic-bezier(0.16, 1, 0.3, 1)`) or spring physics from an already-visible default.
  - Accessible fallback: mandatory `@media (prefers-reduced-motion: reduce)` wrapping.
- **Browser Surfaces Theming**:
  - Theme native elements that default to OS/browser styles:
    - Text selection: `::selection { background: var(--accent-subtle); color: var(--accent-fg); }`
    - Carets: `caret-color: var(--primary);`
    - Tabular numerals: `font-variant-numeric: tabular-nums;` for data columns, prices, and metrics.
    - Custom scrollbars: thin, restrained, matching surface palette.
    - Focus rings: clean 2px offset ring `outline-2 outline-offset-2`.

---

## 2. Category Default Refusals (Anti-Default Discipline)

These patterns represent lazy model defaults. Refuse them unless explicitly demanded by the user:

### Scaffold Refusals:
1. **Identical Card Grids**: Reject 3 equal-width boxes containing an icon, title, and 2 lines of text. Use asymmetrical layouts, bento arrangements, or split lists instead.
2. **Hero-Metric Formula**: Reject the generic formula (huge stat number + tiny subtitle + glowing icon). Integrate metrics into real workflow narratives.
3. **Eyebrow Inflation**: Forbid kicker/eyebrow labels above every single heading. The heading must carry its own authority.
4. **Numbered Sequence Markers**: Forbid artificial `01 / 02 / 03` prefixes on feature cards unless presenting a chronological step-by-step pipeline.
5. **Reflex Modals**: Reject dialogs for tasks that need neither interruption nor protected focus. Prefer inline expansion or drawer panels.

### Surface Refusals:
1. **Gradient Text**: Reject rainbow/purple-to-cyan gradient text. Typographic authority stems from scale, weight, and contrast.
2. **Default Glassmorphism**: Forbid decorative `backdrop-blur` layered across opaque content. Glass is valid only for floating overlays, fixed navbars, and HUD elements.
3. **Thick Accent Borders**: Forbid thick left borders (`border-l-4`) on alert cards and list items. Use subtle 1px surface borders or tone washes.
4. **Fake Neobrutalist Block Shadows**: Reject hard `box-shadow: 4px 4px 0px #000` unless the committed design direction is explicitly Brutalist.
5. **Emoji as Icons**: Forbid unicode emoji in place of a drawn, single-weight vector icon set (Lucide, Radix, Phosphor).
6. **Fake Mobile Viewports**: Reject `h-screen` which breaks on mobile browser address bar collapse. Use `min-h-[100dvh]`.

### Authenticity Refusals:
1. **Drawn Fake Chrome**: NEVER render fake browser window headers, traffic-light dots (red/yellow/green circles), or artificial smartphone bezels inside web viewports. Let the native OS/browser render natural viewports.
2. **Fabricated Social Proof**: NEVER render fictional 5-star ratings, synthetic testimonial avatars, or generic placeholder partner logos without explicit data records.
3. **Non-Functional Controls**: Every button, link, and interactive widget must either perform an authentic operational action or be omitted. Forbid `#` dead-ends and dummy handlers.
4. **Resilient State Triad**: Every interactive surface must explicitly implement the complete state triad: **Loading**, **Empty**, and **Error** states with actionable recovery.

---

## 3. Four Visitor Interaction Modes

Every interface addresses one dominant visitor mode. Tune density, variance, and motion accordingly:

| Mode | Intent | Visual Treatment | Density & Typography |
| :--- | :--- | :--- | :--- |
| **Persuade** | Landing pages, marketing, conversion | Expressive typography, decisive hero contrast, kinetic physics, atmospheric lighting. | Airy density, display scales up to `5rem`, 60-30-10 color ratio. |
| **Operate** | SaaS apps, admin dashboards, tools | Scanability, predictable spatial locations, immediate feedback, tabular numbers. | Compact/high density, fixed role scales, subdued accents for status only. |
| **Read** | Documentation, blogs, knowledge bases | Typographic stability, $65\text{ch}$ measure, generous leading, distraction-free surfaces. | Relaxed density, zero decorative animation, strict contrast compliance. |
| **Experience** | Portfolios, creative agency, interactive | Authorial voice, unconventional layouts, kinetic cursor/scroll interactions. | Custom density, custom display lettering, experiential shaders/canvas. |
