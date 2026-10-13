---
name: ui-finish
description: >-
  Applies premium, restrained aesthetics (Linear, Raycast, Stripe), visual engineering, and design token contracts. Use when applying UI polish, designing micro-interactions, refining typography, or creating design tokens.
---

# UI & Visual Design Architect (Restrained Visual Engineering)

Enforces high-craft production UI paradigms (Linear, Raycast, Stripe) by rejecting generic AI aesthetic defaults and mandating strict design token contracts.

## JIT Tool Directives (Execute this FIRST)
1. **Detect Ecosystem**: Check the project root for the ecosystem package file (`{{PACKAGE_FILE}}`).
2. **Load Ecosystem Canon**: `view_file .agents/canons/ecosystems/{{FRAMEWORK}}/{{FRAMEWORK}}-ui-patterns.md`
3. **Mandatory Knowledge Routing**:
    - **Visual/Prompt Engineering**: `view_file .agents/skills/ui-finish/references/visual_engineering.md`
    - **Component Recipes & Cookbook**: `view_file .agents/skills/ui-finish/references/component_recipes.md`
    - **Visual Craft Floor & Category Refusals**: `view_file .agents/skills/ui-finish/references/craft_floor.md`
    - **Aesthetic Archetypes & Design Systems**: `view_file .agents/skills/ui-finish/references/aesthetic_archetypes.md`
    - **Bento Grids & Asymmetric Macrostructures**: `view_file .agents/skills/ui-finish/references/bento_and_macrostructures.md`
4. Search for theme/color definitions to maintain visual harmony.
5. Check responsive layout usage to ensure responsiveness is preserved.
6. **CI Gatekeeper**: Execute `python .agents/evals/audit_aesthetics.py --dir <target_path>` at the end of every UI task.

## Operational Posture: Restraint Over Novelty
Production UI prioritizes clarity over novelty. Interfaces mandate solid backgrounds, crisp 1px borders, verified WCAG contrast, and zero decorative animations or AI aesthetic tells.


## Critical Validations (Universal)
- **Disambiguation (UI-Finish vs Frontend-Experience)**: Use `ui-finish` STRICTLY for visual engineering, creative polish, and aesthetic craftsmanship. Do NOT use this skill for analytical widget tree debugging, state management, or structural layout fixing. For structural fixes, delegate to the `frontend-experience` skill.
- **Depth & Restraint**: NEVER use floating glassmorphism panels, oversized rounded corners (20px+), or gradient backgrounds as decoration. Use solid backgrounds with subtle borders.
- **Inclusive Visuals**: NEVER accept "Clone Faces." Mandate distinct facial structures and authentic attire.
- **Performance**: NEVER use metric-card grids as default dashboards or floating widgets unless required by product.
- **Accessibility & Semantics**:
  - NEVER ignore "Reduce Motion" / "prefers-reduced-motion" settings.
  - ALWAYS add semantic labels to icon-only buttons or custom interactive elements.
  - Ensure focus states are clearly visible for keyboard/D-pad navigation.
  - Wrap decorative images with appropriate exclusions or provide alt text for informative images.

## Purposeful Aesthetics & Structural Ergonomics (The High-Craft Standard)
- **Semantic Iconography**: Forbid generic sparkle, magic wand, or floating orb icons as thoughtless ornamentation. Every icon must represent its actual domain entity or action. 16–20px, monochrome or subtle color, no decorative backgrounds.
- **Distinct Harmonic Palettes**: Reject generic blue-to-purple / cyan-to-magenta default hero gradients. Palettes must be drawn from project design tokens (`DESIGN.md`) or concrete brand semantics. True dark mode (`#0f172a`), no blue-black gradient premium fakes.
- **Restraint Over Trend-Stacking**: Never blindly stack glassmorphism + mesh gradients + glowing borders + pill buttons. Restrict UI to solid backgrounds, subtle 1px borders, and a maximum box-shadow of `0 2px 8px rgba(0,0,0,0.08)`.
- **Cadence & Rhythm**: Avoid monotonous consecutive KPI 3-box grids. Ensure clean page structure with predictable grid/flex layouts. No asymmetric creative chaos.
- **Mobile Ergonomics**: Enforce minimum 44×44px interactive boundaries for touch targets. Guarantee zero unintentional horizontal overflow across 320px mobile to 4K displays. Stack correctly without cramming.
- **Mandatory State Triad**: Every interactive UI surface must explicitly implement the complete state triad: **Loading**, **Empty**, and **Error** states with actionable recovery.

## 🏛️ Structural Macrostructures (Rhythm Variety)
To prevent every web page or app screen from sharing an identical hero → 3-card grid → CTA rhythm, select one of 6 structural macrostructures matching product intent:
1. **Asymmetric Split-Masthead**: Left-column conceptual narrative paired with a right-column live interactive card, terminal, or graphic viewport.
2. **Data-Dense Cockpit**: Operational tools and dashboards; compact navigation, high-density status feeds, inline controls, zero marketing fluff.
3. **Editorial Dossier**: High-contrast typography-first layout, generous asymmetric margins, elegant pull-quotes, and deep content hierarchy.
4. **Interactive Playground**: Interactive sandbox or canvas anchored front-and-center, with documentation or presets docked below.
5. **Stepped Narrative**: Chronological progression matching the product's actual workflow (never forced into arbitrary 1-2-3 circular badges).
6. **Minimalist Utility**: Single focused focal interface with distraction-free layout and immediate utilitarian utility.

## 🎛️ Component-Scope 8-State Contract
When building standalone interactive components (buttons, cards, inputs, selects, modals), implement code for all **8 states**:
1. `default`: Baseline resting state.
2. `hover`: Subtle tactile elevation or surface shift.
3. `:focus-visible`: High-contrast visible focus ring (minimum 2px offset for keyboard navigation).
4. `:active`: Pressed/spring compression feedback (`scale(0.98)`).
5. `disabled`: Reduced opacity, `pointer-events: none` or `disabled` attribute, accessible ARIA state.
6. `loading`: Skeleton or contained spinner; maintain component dimensions; `aria-busy="true"`.
7. `error`: High-contrast error token, clear recovery messaging, inline validation icon.
8. `success`: Affirmative completion indicator or feedback transition.

## 📐 Dimensional & Restraint Standards (Mathematical Geometry Boundaries)
When structuring layouts and interface elements, enforce strict physical restraint:
- **Sidebar & Panels**: 240–260px fixed width, solid background, 1px border-right. No floating shells or rounded outer desktop window frames.
- **Card Radii**: 8–12px maximum radius. Subtle 1px border. Shadow maximum: `0 2px 8px rgba(0,0,0,0.08)`. Forbid universal 24px+ floating pill containers.
- **Buttons**: Solid fill or subtle 1px border, 6–10px radius max. No arbitrary gradients or oversized capsules.
- **Spacing Scale**: Strict mathematical cadence across all margins/padding: `4px / 8px / 12px / 16px / 24px / 32px / 48px / 64px`. No random arbitrary gaps (`margin: 19px`).
- **Transitions**: 100–200ms ease, opacity and color shifts only. No bouncy transforms or wobbling on static containers.

## 🧭 Visitor Interaction Modes & Surface Intent
Determine the visitor's core objective before drafting code:
- **Persuade**: Landing pages, marketing, pricing surfaces. Design IS the product; earn attention and drive conversion. Bold visual worlds, evidenced claims, no category habit.
- **Operate**: App UI, dashboards, admin portals, editors, operational tools. Task completion, density, scanability, and native OS ergonomics outrank decorative expression.
- **Read**: Documentation, changelogs, technical guides, articles. Content comprehension, clear typographic hierarchy, quiet contrast, zero distraction.
- **Experience**: Portfolios, showcases, creative galleries. Interface recedes; authentic visual artifacts lead from the initial viewport.

## 🔎 Brief Inference & Design Read
Before writing code or adjusting styling dials, infer authentic context and emit a single-line declaration:
1. **Signal Intake**: Page kind (SaaS, consumer, devtool, portfolio, editorial), vibe vocabulary, reference signals, audience, and quiet regulatory/accessibility constraints.
2. **Ambiguity Gate**: If the brief genuinely diverges, ask exactly ONE clarifying question. Otherwise, infer directly.
3. **Mandatory 1-Line Design Read**: Output before generation:
   `Reading this as: <page kind> for <audience>, with a <vibe> language, leaning toward <design system or aesthetic family>.`
4. **Anti-Default Discipline**: Consciously avoid generic AI defaults (purple glows, centered hero over dark mesh, 3 equal feature cards, Inter + slate-900).

## 🎛️ The 10-Point Visual Dials & Strategy Pre-Flight

Before any UI implementation (Flutter or Web), declare:
```
[VISUAL PRE-FLIGHT]:
- Mode: {Persuade | Operate | Read | Experience}
- Design Read: Reading this as: {kind} for {audience}, with {vibe} language.
- Color Strategy: {dominant}:{accent}:{neutral} ratio (e.g., 60:30:10) | Palette: {Token / Rotation Set}
- Typography: {scale} + {weights} (e.g., Golden Ratio, w400/w600/w800)
- Macrostructure: {Asymmetric Split | Cockpit | Editorial | Playground | Stepped | Minimalist}
- Restraint: {1px borders} + {solid bg} + {max 8px radius}
- Dials: VARIANCE {1-10} / MOTION {1-10} / DENSITY {1-10}
- Bounded Passes: Batch 1 (Desktop + Mobile) -> 1 Fix Pass -> 1 Confirm Pass (Max 2 Passes)
- Source of truth: {DESIGN.md or token name}
```
**Coding begins ONLY after this block is output.**

### 10-Point Dial Configuration
- **`DESIGN_VARIANCE: 1–10`**: 1 = Strict symmetry/uniformity, 10 = High editorial/asymmetric variation.
- **`MOTION_INTENSITY: 1–10`**: 1 = Static, 10 = Rich spring physics and scroll-driven choreography.
- **`VISUAL_DENSITY: 1–10`**: 1 = Airy art gallery, 10 = High-density operational cockpit.

| Use Case Preset | VARIANCE | MOTION | DENSITY | Primary Mode |
| :--- | :---: | :---: | :---: | :--- |
| **Landing (B2B SaaS / Devtool)** | 7 | 6 | 4 | Persuade |
| **Landing (Creative / Agency)** | 9 | 8 | 3 | Persuade |
| **Landing (Premium Consumer)** | 7 | 6 | 3 | Persuade |
| **Operational Dashboard / Tool** | 3 | 2 | 8 | Operate |
| **Portfolio (Developer)** | 6 | 5 | 4 | Experience |
| **Portfolio (Designer / Studio)** | 8 | 7 | 3 | Experience |
| **Documentation / Technical Guide** | 3 | 2 | 6 | Read |

## 🛡️ Bounded Inspection Pass Mandate (Anti-Token Burn)
Verify in bounded, deterministic passes—NEVER in an open-ended loop:
1. **Pass 1 (Batched Build & Inspect)**: Build completely. Inspect desktop and mobile viewports simultaneously. Compile all defects (contrast, spacing, responsiveness) into a single batch.
2. **Pass 2 (Batched Remediation)**: Apply all fixes in one unified code edit.
3. **Pass 3 (Confirmation)**: Run final confirmation sweep. CEASE polishing immediately. Open-ended self-QA loops burn context and degrade code.

## 📐 Layout & Viewport Restraint Standards
- **Hero Viewport Fit**: Primary headline max 2 lines desktop, subtext max 20 words (max 3–4 lines). Primary CTA must be visible without scrolling. Hero top padding capped at `pt-24`.
- **Hero Text Element Cap**: Maximum 4 text elements total (Eyebrow OR brand strip, Headline, Subtext, CTAs). No "trusted by" logo walls inside the hero container—render logo walls in a dedicated section below.
- **Eyebrow Restraint**: Small uppercase wide-tracking labels (`uppercase tracking-[0.2em]`) are capped at **maximum 1 eyebrow per 3 sections**. Count total instances across the page; drop where not needed.
- **Section Layout Diversity**: Each layout family (split text/image, bento, full-width callout, metric list) may appear at most ONCE per page. Alternating zigzag layouts ("image-left then text-left") are capped at maximum 2 consecutive sections.
- **Bento Cell Count Discipline**: A grid must have exactly as many cells as valid content items (3 items = 1+2 split; 5 items = 2+3 split). Zero blank or empty placeholder cards. Bento background diversity: at least 2–3 cells must carry distinct visual texture, gradient, or imagery.
- **Viewport Stability**: NEVER use `h-screen` for full-height heroes (causes layout jump on mobile address bar collapse); ALWAYS use `min-h-[100dvh]`.
- **Split-Header Ban**: Avoid default "left big headline + right body paragraph" headers. Stack vertically (`max-w-[65ch]`) unless the right column carries interactive controls.

## 🪟 Browser Surfaces Theming (High-Craft Polish)
Unstyled browser defaults signal uncurated templates. Theme all native browser surfaces from project tokens:
- **Selection Highlight**: Custom `::selection` background and text color matching brand tokens.
- **Caret Color**: Explicit `caret-color` aligned with theme accent.
- **Tabular Data Numerals**: Apply `font-variant-numeric: tabular-nums` (`tabular-nums`) to all metric tables, counters, and telemetry readouts.
- **Custom Scrollbars**: Constrained, themed scrollbars (`scrollbar-color` or subtle WebKit scrollbar track) to prevent harsh system gray scrollbars.

## 🔨 Tactical Refinement Directives
When refining existing surfaces, invoke explicit tactical verbs:
- **`bolder`**: Amplify safe or timid layouts with punchy typographic scale, high contrast, and distinctive asymmetrical balance.
- **`quieter`**: Tone down overstimulating UIs; strip decorative halos, gratuitous badges, and hyperactive animations.
- **`distill`**: Strip complexity to absolute essence; eliminate redundant wrapper cards, flatten visual hierarchy.
- **`harden`**: Ensure production resilience; implement error boundaries, keyboard focus traps, and long-text i18n overflow handling.
- **`onboard`**: Design purposeful first-run states, activation pathways, and empty-state guidance.

## 🧬 Visual DNA Extraction (Reference Analysis)
When a user provides a reference URL or screenshot:
1. **Macrostructure Extraction**: Identify the spatial layout rhythm and dominant content flow.
2. **Typographic Anchor**: Extract heading-to-body scale ratio and letterform tone (Grotesque, Monospace, Humanist, Editorial Serif).
3. **Harmonic Anchor**: Extract the primary brand color, background neutral shade, and accent contrast ratio.
4. **Synthesis**: Generate or update the project's `DESIGN.md` with these extracted tokens. **Never copy layout pixels, fake device chrome, or proprietary graphics verbatim.**

## 🛡️ The Visual Critique Gates & Anti-Cliché Sweep (Pre-Emit Audit)

Run this checklist before delivering any frontend emit. Every condition must be satisfied:

### 1. Visual Integrity & Palettes
- [ ] **No Default Hero Gradients**: Zero purple-to-blue or cyan-to-magenta linear gradients across heroes, buttons, or text.
- [ ] **No Pure Black Base**: Canvas uses layered obsidian/charcoal (`#0D0F12`, `#111318`) with surface tint, never raw `#000000`.
- [ ] **Accent Footprint Clamped**: Primary brand accent covers <= 5% of any viewport (used for focus rings, status, primary CTAs; never whole section backgrounds).
- [ ] **No Fake Device Frames**: Zero drawn macOS traffic-light dots or browser search bars embedded in web views.
- [ ] **Icon Discipline**: Single icon library (e.g. Lucide), zero emoji glyphs (✨, 🚀, ⚡) used as feature icons.

### 2. Structural & Layout Craft
- [ ] **Asymmetric Variance**: Zero uniform 3-card equal-width grids (`grid-cols-3` without breakpoint spans). Use 2×2, 70/30, or masonry spans.
- [ ] **Off-Axis Hero Alignment**: Eyebrow label or CTA button sits off-axis from the headline (margin-aligned or numeral-anchored, never 100% centered-everything).
- [ ] **No Card-in-Card Nesting**: Cards sit cleanly on canvas or section surfaces without nested outer boxes.
- [ ] **Viewport Clipping**: Zero horizontal scrollbars between 320px and 1920px viewports (`overflow-x: clip` applied on page root).

### 3. Typography & Microinteractions
- [ ] **The 2+1 Font Rule**: Maximum 3 font families across the entire page (Display + Body + max 1 outlier for mono/wordmark).
- [ ] **Display Headings Roman**: All headings upright roman (`font-style: normal`); zero italicized emphasis words inside display titles.
- [ ] **No Default Serifs**: Forbid reaching for generic default serifs (`Fraunces`, `Instrument Serif`). Default sans display; reach for serifs only when brief explicitly justifies heritage/literary tone.
- [ ] **Italic Descender Clearance**: When italic display type contains descenders (`y g j p q`), enforce `leading-[1.1]` minimum with `pb-1` reserve to prevent clipping.
- [ ] **Anti-Beige/Brass Default Lock**: On premium consumer briefs, forbid defaulting to warm beige/cream (`#f5f1ea`) + brass/clay/oxblood accents. Rotate through Cold Luxury, Forest, Black & Tan, or Cobalt & Cream.
- [ ] **Depth Without Halos**: Shadows carry realistic vertical offset (`2px–8px`) and soft blur. Zero-offset colored glowing halos (`0 0 20px`) are forbidden.
- [ ] **Measure Clamped**: Reading prose bounded between 45ch and 75ch (`max-width: 68ch`).
- [ ] **Specific Transitions**: Use explicit transition properties (`transition-colors`, `transition-opacity`), never broad `transition-all`.
- [ ] **Instant Focus Indicators**: Focus rings appear instantaneously with 2px offset for keyboard navigation (zero transition fade).
- [ ] **Restrained Interaction**: Single hover signal per element (border highlight OR background tint, never simultaneous scale + tilt + shadow).

## 4-Block Delivery Gate (Pre-Ship Certification)
Before declaring a UI task complete, certify:
```
[DELIVERY GATE: UI & FIDELITY AUDIT]
• Pre-Emit   : [PASS] - Critique: Hierarchy 5/5, Restraint 5/5, Resilience 5/5, Variety 5/5.
• Visual     : [PASS] - Zero unearned glow, trend-stacking, or default purple gradients.
• Copy       : [PASS] - Zero hype buzzwords, fabricated stats, or fake testimonials.
• Function   : [PASS] - All buttons/links wired; Loading/Empty/Error states handled; 8 component states verified.
• Resilience : [PASS] - WCAG contrast compliant; responsive reflow verified; no comment bloat.
```

## Workflow Patterns (Universal)
1. **The Brief Intake**: Identify both technical UI requirements and the human story for visual assets.
2. **Design Specification (DESIGN.md)**: Before coding, define the visual identity using the `DESIGN.md` format (YAML tokens + Markdown prose). Reference `.agents/skills/ui-finish/references/visual_engineering.md` for details.
3. **Implementation**: Use patterns from ecosystem canons and the `DESIGN.md` spec to build surfaces and animations.
4. **Prompt Engineering**: Use the annotation framework from `.agents/skills/ui-finish/references/visual_engineering.md` for AI-generated visual assets.

## Troubleshooting (Universal)
- **Scrolling stutters**: Excessive blur effects. Consolidate blurs.
- **AI generates identical faces**: Lack of specified variance in prompt description.
- **Skin tones washed out**: Lighting defaults to lighter skin physics. Specify melanin-friendly lighting.

---
*Generated by Portable Brainvibing Infrastructure - UI & Visual Suite*
