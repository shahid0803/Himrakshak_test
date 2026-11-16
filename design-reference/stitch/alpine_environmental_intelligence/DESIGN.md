---
name: Alpine Environmental Intelligence
colors:
  surface: '#f9f9ff'
  surface-dim: '#cddaf8'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e8eeff'
  surface-container-high: '#dfe8ff'
  surface-container-highest: '#d7e3ff'
  on-surface: '#0e1c31'
  on-surface-variant: '#404945'
  inverse-surface: '#243147'
  inverse-on-surface: '#ecf0ff'
  outline: '#707974'
  outline-variant: '#c0c9c3'
  surface-tint: '#376757'
  primary: '#003629'
  on-primary: '#ffffff'
  primary-container: '#1b4d3e'
  on-primary-container: '#8abda9'
  inverse-primary: '#9ed1bd'
  secondary: '#27695c'
  on-secondary: '#ffffff'
  secondary-container: '#abeddc'
  on-secondary-container: '#2c6d60'
  tertiary: '#002480'
  on-tertiary: '#ffffff'
  tertiary-container: '#1439a9'
  on-tertiary-container: '#9caeff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#baeed9'
  primary-fixed-dim: '#9ed1bd'
  on-primary-fixed: '#002117'
  on-primary-fixed-variant: '#1d4f40'
  secondary-fixed: '#aeefdf'
  secondary-fixed-dim: '#92d3c3'
  on-secondary-fixed: '#00201a'
  on-secondary-fixed-variant: '#025045'
  tertiary-fixed: '#dde1ff'
  tertiary-fixed-dim: '#b8c4ff'
  on-tertiary-fixed: '#001453'
  on-tertiary-fixed-variant: '#173bab'
  background: '#f9f9ff'
  on-background: '#0e1c31'
  surface-variant: '#d7e3ff'
  background-canvas: '#F6F8FA'
  surface-card: '#FFFFFF'
  border-subtle: '#E2E8F0'
  text-muted: '#64748B'
  status-safe: '#15803D'
  status-warning: '#D97706'
  status-critical: '#DC2626'
  status-inactive: '#64748B'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
  data-metric:
    fontFamily: JetBrains Mono
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.03em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style
The design system powers an industrial mission-critical telemetry command center dedicated to geological hazard monitoring and landslide early warnings along steep Himalayan transit corridors.

The aesthetic marries **Tactile Industrial Precision** with **Modern Scientific Minimalism**. The interface prioritizes extreme data legibility, low cognitive friction during high-stress alert states, and a calm, authoritative command presence during routine monitoring. Visual structures evoke ruggedized field hardware, geographic surveying apparatus, and low-latency digital telemetry consoles. It avoids decorative consumer flourishes in favor of structured data ribbons, razor-sharp status indicators, and deterministic visual feedback.

## Colors
The palette balances field ecology with austere telemetry engineering:
- **Primary (`#1B4D3E` - Alpine Pine):** Represents environmental stability and Himalayan montane forest canopies. Used for primary navigation states, structural anchors, and key action points.
- **Secondary (`#2E6F62` - Muted Slate Teal):** Functions as supporting instrumentation accents, secondary toolbars, and contextual data groupings.
- **Tertiary (`#1E40AF` - Engineering Blue):** Dedicated strictly to network telemetry, LoRa mesh routing nodes, packet transmissions, and radio frequency communication indicators.
- **Neutral (`#152238` - Deep Slate):** The primary typographic ink and boundary anchor, offering maximum contrast without the harsh glare of pure `#000000`.
- **Canvas & Surface (`#F6F8FA`, `#FFFFFF`):** High-clarity, non-reflective base layers that allow dense visual metrics and status badges to emerge immediately.
- **Semantic Indicators (`#15803D`, `#D97706`, `#DC2626`, `#64748B`):** Reserved strictly for threat categorization, sensor threshold alerts, pore-water pressure spikes, and simulated/offline node state representation.

## Typography
Typographic discipline is central to preventing telemetry misinterpretation:
- **Inter** provides neutral, optical clarity across UI headers, section framing, and narrative disaster-management advisories.
- **JetBrains Mono** is mandatory for all numerical sensor readouts, timestamps, coordinates, LoRa packet diagnostics, signal RSSI ratings, and tabular data columns. Fixed character widths eliminate horizontal jitter during real-time streaming data updates.
- All uppercase sensor codes and alert state tags should leverage `label-sm` or `label-md` with positive letter tracking for legibility at small sizes.

## Layout & Spacing
The layout employs an analytical 12-column grid system optimized for dense operational views and multi-panel telemetry monitoring:
- **Desktop (1280px+):** 12 columns with `1.5rem` gutters and `2rem` screen margins. Layout supports simultaneous persistent sidebars (mesh topology status), central interactive contour maps, and real-time streaming telemetry drawers.
- **Tablet (768px - 1279px):** 8 columns with `1rem` gutters. Peripheral telemetry collates into collapsible tab sheets or segmented drawers.
- **Mobile (<768px):** 4 columns with `1rem` gutters and margins. Visualizations stack vertically; high-priority sensor alert strips remain pinned to the upper viewport boundary.
- **Grid Discipline:** Metric widgets, charts, and parameter cards must adhere to standard 4px/8px modular vertical rhythms. Compact components prioritize space efficiency to display maximum context above the fold.

## Elevation & Depth
In alignment with industrial instrumentation design, visual hierarchy relies primarily on **low-contrast outlines, crisp panel dividers, and tonal planar layering** rather than heavy drop shadows:
- **Base Canvas:** `#F6F8FA` sets an unembellished baseline.
- **Level 1 (Panels and Instrument Cards):** Pure `#FFFFFF` background with a crisp `1px` border of `#E2E8F0`. Shadows are restrained to `0 1px 3px rgba(21, 34, 56, 0.05)`.
- **Level 2 (Overlays, Floating Control Trays, Active Nodes):** Surface `#FFFFFF` enclosed by a `1px` border of `#CBD5E1` with a calibrated drop shadow `0 4px 12px -2px rgba(21, 34, 56, 0.08)`.
- **Level 3 (Modal Dialogs & Critical Warning Overlays):** Pinned foreground elevation backed by a dimming mask (`rgba(16, 28, 44, 0.45)`) and bounded by a `1px` border using contextual alert semantics (e.g., `#DC2626` for emergency protocols).

## Shapes
To reinforce an industrial telemetry device aesthetic, shape radii are kept strictly disciplined at **Soft (`1`)**:
- Standard inputs, panels, instrument cards, and action buttons adopt a `4px` (`0.25rem`) corner radius.
- Larger map overlays, floating telemetry docks, and alert banners leverage `8px` (`0.5rem`).
- Radii never exceed `8px`, avoiding casual or playful appearances. Pill shapes are strictly forbidden except for tiny circular status beacon indicators.

## Components

### Buttons & Operational Triggers
- **Primary Button:** Background `#1B4D3E`, label `#FFFFFF` in `Inter` Medium (`14px`), `4px` corner radius, `8px 16px` padding. On hover: `#143B30`. On active: `#0E2A22`.
- **Engineering / Action Button (Tertiary Accent):** Background `#1E40AF`, label `#FFFFFF`. Used specifically for network ping tests, mesh re-routing, and telemetry data export.
- **Secondary / Outline Button:** Surface transparent, `1px` solid `#CBD5E1`, text `#152238`. On hover: background `#F1F5F9`.
- **Destructive Trigger:** Border and background `#DC2626`, text `#FFFFFF`. Used strictly for hazard sirens, public warning broadcasts, and manual system overrides.

### Telemetry Cards & Metric Containers
- Surface `#FFFFFF`, border `1px solid #E2E8F0`, padding `1rem`.
- Header consists of a subdued section title in `Inter` (`12px`, uppercase, `#64748B`) paired with a live status beacon or node ID (`JetBrains Mono`).
- Telemetry figures use `data-metric` (`28px` mono) paired with a subtext showing historical variance or delta rate per hour.

### Status Indicators & Badges
- **Safe:** Background `#ECFDF5`, border `#A7F3D0`, text `#15803D`.
- **Warning:** Background `#FFFBEB`, border `#FDE68A`, text `#D97706`.
- **Critical Hazard:** Background `#FEF2F2`, border `#FECACA`, text `#DC2626`.
- **Offline / Simulated Mesh:** Background `#F8FAFC`, border `#E2E8F0`, text `#64748B`.
- Badges feature a `6px` solid status circle positioned to the left of the uppercase monospaced descriptor.

### Data Tables & Sensor Logs
- Header rows feature a faint `#F8FAFC` fill, `1px` bottom border `#E2E8F0`, and uppercase `11px` mono column titles.
- Data rows feature alternating or clean white rows with `1px` border dividers `#F1F5F9`.
- Numerical readouts align to the right edge with tabular monospaced numbers.

### Inputs & Controls
- Form controls and frequency selectors feature `#FFFFFF` background, `1px` solid `#CBD5E1`, and focus ring of `2px` `#1B4D3E` with `0px` offset.
- Checkboxes and radio toggles utilize `#1B4D3E` for checked states with rigid, non-deformable alignment.

### Specialized Hardware Component: LoRa Node Signal Ribbon
- Horizontal telemetry strip showing signal health: frequency (MHz), RSSI (dBm), SNR, packet drop percentage, and battery voltage. Rendered completely in `JetBrains Mono` with subtle vertical dividers (`#E2E8F0`).