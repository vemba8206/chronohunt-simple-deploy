---
name: Obsidian Luster
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363941'
  surface-container-lowest: '#0b0e15'
  surface-container-low: '#191b23'
  surface-container: '#1d1f27'
  surface-container-high: '#272a32'
  surface-container-highest: '#32353d'
  on-surface: '#e1e2ec'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#e1e2ec'
  inverse-on-surface: '#2d3038'
  outline: '#849495'
  outline-variant: '#3b494b'
  surface-tint: '#00dbe9'
  primary: '#dbfcff'
  on-primary: '#00363a'
  primary-container: '#00f0ff'
  on-primary-container: '#006970'
  inverse-primary: '#006970'
  secondary: '#adc6ff'
  on-secondary: '#002e6a'
  secondary-container: '#0566d9'
  on-secondary-container: '#e6ecff'
  tertiary: '#d8ffe7'
  on-tertiary: '#003824'
  tertiary-container: '#65f2b5'
  on-tertiary-container: '#006d4a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#7df4ff'
  primary-fixed-dim: '#00dbe9'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f54'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#10131a'
  on-background: '#e1e2ec'
  surface-variant: '#32353d'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 56px
    fontWeight: '700'
    lineHeight: 64px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: '0'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Space Grotesk
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.08em
  code-md:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 3rem
  margin-mobile: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes a minimal, hyper-refined dark glassmorphic atmosphere tailored for a premier, high-stakes time-based event. The aesthetic merges precision engineering with atmospheric depth. Rejecting overdone cyberpunk clichés, heavy terminal styling, and saturated neon overdrive, the interface behaves like precision optical glass resting over deep spatial planes.

The interface evokes focus, high intellect, calculated calm, and quiet technical dominance. It provides users with an uncluttered, distraction-free field of vision where structural transparency, controlled light diffusion, and immaculate typography frame the core experience.

Key aesthetic characteristics:
- **Spatial Obsidian Voids**: Pitch dark foundations (#0a0d14) providing infinite perceived depth.
- **Precision Optical Glass**: Layered translucent surfaces with clean backdrop blurs, avoiding muddy gradients.
- **Controlled Luminescence**: Micro-doses of sharp cyan and deep cobalt strictly reserved for interactive state indicators, telemetry metrics, and primary milestones.
- **Clean Architectural Discipline**: Balanced negative space, razor-thin structural perimeters, and deliberate content grouping.

## Colors

The palette relies on a stark value contrast between deep obsidian voids and focused luminescent highlights.

### Surface System
- **Void Base (`#0a0d14`)**: Canvas canvas layer. Absorbs visual fatigue and grounds spatial layers.
- **Glass Base (`rgba(16, 22, 34, 0.65)`)**: Standard resting container surface with optical diffusion.
- **Glass Elevated (`rgba(22, 30, 46, 0.75)`)**: Popovers, active panels, dropdowns, and elevated states.
- **Glass Interactive (`rgba(255, 255, 255, 0.04)`)**: Subtle structural hover and highlight fields.

### Accents & Illumination
- **Primary Cyan (`#00f0ff`)**: Focal point trigger. Used for active progress states, critical telemetry badges, and primary interactive affordances.
- **Secondary Cobalt (`#3b82f6`)**: Structural reinforcement, supporting links, secondary visual anchors, and deep ambient light casts.
- **Tertiary Mint (`#10b981`)**: Verified states, completion markers, and time-positive checkpoints.
- **Caution / Expiry (`#f43f5e`)**: Critical threshold, timer depletion, and destructive actions.

### Neutrals & Text Contrast
- **Text Dominant (`#f8fafc`)**: High readability, headline treatments, and active data.
- **Text Muted (`#94a3b8`)**: Secondary annotations, descriptions, structural labels.
- **Text Dim (`#475569`)**: Inactive metrics, subtle dividers, structural glyphs.
- **Border Subtle (`rgba(255, 255, 255, 0.08)`)**: Universal hairline boundary for standard panels.
- **Border Active (`rgba(0, 240, 255, 0.25)`)**: Hairline boundary denoting focus, selection, or current step.

## Typography

Typography pairs the structural, geometric personality of Space Grotesk for prominent displays, timers, tracking indicators, and headings with the neutral legibility of Inter for body copy, long-form briefs, and multi-line explanations.

Rules of execution:
- Always enforce high letter-spacing tracking on micro labels (`label-sm`) with uppercase transformations to evoke precision telemetry.
- Keep numbers tabular (`tnum` OpenType feature enabled) on all countdown timers, scores, and coordinate readouts.
- Display headlines use slight negative tracking to balance visual weight against glassy translucent backgrounds.

## Layout & Spacing

The layout model is anchored by a responsive fluid 12-column grid on desktop/tablet, collapsing to 4 columns on mobile viewports. Generous negative margins prevent interface density from cluttering the glass planes.

### Grid & Breakpoints
- **Desktop (1280px+)**: 12 columns, 1.5rem (`24px`) gutters, max-width 1280px centered with dynamic page margin >= 3rem.
- **Tablet (768px - 1279px)**: 8 columns, 1.25rem (`20px`) gutters, page margin 2rem.
- **Mobile (under 768px)**: 4 columns, 1rem (`16px`) gutters, page margin 1.25rem.

### Spatial Rhythm
Containers prioritize inner breathing space to accentuate backdrop blur refraction:
- Cards and glass surfaces maintain a minimum internal padding of `space-lg` (`24px`) on desktop and `space-md` (`16px`) on mobile.
- Section vertical rhythm is strictly distributed in steps of `space-xl` (`40px`) or larger multiples to eliminate claustrophobic layouts.

## Elevation & Depth

Depth is defined by physical light refraction through glass surfaces layered above an obsidian background, rather than traditional dark drop shadows.

### Glass Stack Model
- **Base Canvas**: Solid `#0a0d14` background augmented with stationary, ultra-soft radial ambient gradients (`rgba(0, 240, 255, 0.04)` and `rgba(59, 130, 246, 0.03)` with 160px blur).
- **Surface Level 1 (Resting Cards & Panels)**:
  - Background: `rgba(16, 22, 34, 0.65)`
  - Backdrop Filter: `blur(20px) saturate(180%)`
  - Border: 1px solid `rgba(255, 255, 255, 0.08)`
  - Shadow: `0 8px 32px 0 rgba(0, 0, 0, 0.37)`
- **Surface Level 2 (Hovered / Floating Glass / Modals)**:
  - Background: `rgba(22, 30, 46, 0.8)`
  - Backdrop Filter: `blur(28px) saturate(200%)`
  - Border: 1px solid `rgba(0, 240, 255, 0.2)`
  - Shadow: `0 20px 48px -10px rgba(0, 0, 0, 0.6), 0 0 24px 0 rgba(0, 240, 255, 0.08)`

### Specular Edge Lighting
To mimic pristine physical glass, panels feature an inner pseudo-highlight: an inner top border gradient from `rgba(255, 255, 255, 0.12)` fading to transparent at the bottom, conveying a top-down luminescent source without cluttering the canvas.

## Shapes

The design system applies a disciplined `roundedness: 2` (equivalent to base `0.5rem` / `8px` up to `rounded-2xl` / `16px` for structural surfaces).

- **Structural Cards & Glass Panels**: Standardized to `16px` (`rounded-2xl`) corners to soften structural lines and balance the sharp technical typography.
- **Controls & Form Elements**: `8px` to `12px` (`rounded-lg` / `rounded-xl`) corner radiuses for precise, tactical tactile affordance.
- **Badges, Status Pills & Chips**: Fully circular/pill shapes (`rounded-full`) to delineate them from actionable rectangular surfaces.

## Components

### Buttons
- **Primary Action**: Solid `#00f0ff` text over `rgba(0, 240, 255, 0.12)` background, bounded by 1px `rgba(0, 240, 255, 0.35)` border. On hover: background elevates to `#00f0ff` with `#0a0d14` text and `0 0 20px rgba(0, 240, 255, 0.4)` glow.
- **Secondary Glass**: `rgba(255, 255, 255, 0.04)` fill with `1px rgba(255, 255, 255, 0.1)` border. Text `#f8fafc`. On hover: `rgba(255, 255, 255, 0.08)` fill and subtle border transition to cyan tint.
- **Ghost Action**: Transparent fill, muted slate text (`#94a3b8`), transitioning to `#f8fafc` on hover with a micro cyan under-glow dot.

### Glass Cards
- Translucent backdrop container with 16px to 24px blur, thin 1px boundary line (`rgba(255, 255, 255, 0.08)`).
- Padding of `24px` minimum. Interactive cards apply a subtle scale (`1.008`) and transition edge border color to `rgba(0, 240, 255, 0.25)` on cursor hover.

### Form Inputs & Search Fields
- Inset glass styling: Background `rgba(10, 13, 20, 0.6)` with inner shadow `inset 0 2px 4px rgba(0,0,0,0.5)`.
- Resting border: 1px `rgba(255, 255, 255, 0.08)`.
- Focused state: Border illuminates to `rgba(0, 240, 255, 0.5)` with an ultra-soft outer glow `0 0 12px rgba(0, 240, 255, 0.15)`. No harsh browser outlines.

### Chips & Telemetry Badges
- Pill-shaped (`rounded-full`), compact layout: 4px vertical, 10px horizontal padding.
- Text rendered in `label-sm` Space Grotesk.
- Neutral Chip: `rgba(255, 255, 255, 0.05)` fill, `rgba(255, 255, 255, 0.1)` border, `#94a3b8` text.
- Active Stage Chip: `rgba(0, 240, 255, 0.1)` fill, `rgba(0, 240, 255, 0.3)` border, `#00f0ff` text with a 4px pulsing cyan beacon dot.

### Checkboxes & Radios
- Size: 18px × 18px square (checkbox) or circle (radio).
- Base state: Glass fill `rgba(255, 255, 255, 0.05)`, border `rgba(255, 255, 255, 0.15)`.
- Checked state: Fill `#00f0ff` with obsidian `#0a0d14` icon, emitting a 6px diffused cyan shadow.

### Chrono Timer Display
- Dedicated high-precision countdown component.
- Segmented numeric boxes using `Space Grotesk` with tabular figures (`font-variant-numeric: tabular-nums`).
- Semi-transparent glass segment tiles with hairline dividers, topped with micro uppercase unit tags (`SEC`, `MIN`, `HRS`) styled via `label-sm`.