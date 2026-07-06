---
name: accessibility-design
description: "The WCAG 2.2 AA audit cookbook for Laravel front-ends and mobile — concrete thresholds (contrast, target size, focus), Livewire / Inertia focus-management specifics, screen-reader semantics, reduced motion, mobile a11y (VoiceOver / TalkBack, dynamic type). Use when designing screens, auditing UI for accessibility, or reviewing frontend / mobile work for the accessibility part of done."
---

# Accessibility (WCAG 2.2 AA)

Accessibility is part of done, not a follow-up ticket. Audit against thresholds, not impressions.

## The thresholds

- **Contrast**: text 4.5:1; large text (≥ 24px, or ≥ 18.66px bold) 3:1; UI components + graphical objects 3:1. Check disabled-looking-but-active states — they fail most often.
- **Target size**: ≥ 24×24 CSS px (2.5.8) — spacing counts toward it; mobile: 44pt iOS / 48dp Android.
- **Focus visible** (2.4.7 + 2.4.11): every interactive element has a visible focus indicator that isn't fully obscured by sticky headers/footers. Never `outline: none` without a replacement.
- **Focus order** follows reading order; modals trap focus and return it on close.
- **Dragging** (2.5.7): any drag interaction has a single-pointer alternative.
- **Redundant entry** (3.3.7): don't ask for the same info twice in one flow.

## Semantics

- Native elements first: `<button>`, `<a href>`, `<label for>` — ARIA is the fallback, not the default. No `role="button"` on a div when a button works.
- Every input labeled (visible label > placeholder-as-label, which fails). Errors: `aria-describedby` pointing at the message + `aria-invalid`; error text states *what to do*, not just "invalid".
- Landmark structure: one `<main>`, `<nav>` labeled when repeated, headings hierarchical without skips.
- Images: `alt` says function in context; decorative → `alt=""`.

## Livewire / Inertia specifics

- **Livewire updates don't move focus** — after an action replaces DOM the user was in, restore focus explicitly (`$this->js('...focus()')` or Alpine `x-ref` + `$nextTick`). Announce async results in an `aria-live="polite"` region (`wire:loading` states included).
- **Inertia navigations don't announce**: on `router.on('navigate')` set focus to the page `<h1>` (tabindex="-1") or a skip target, and announce the page title in a live region. Client-side routing that leaves focus on a vanished element strands screen-reader users.
- Skip link first focusable element on every layout.

## Motion + preference

`prefers-reduced-motion: reduce` → kill parallax, auto-playing carousels, large translate/scale transitions; keep opacity fades. Respect `prefers-color-scheme` if the app themes.

## Mobile

- iOS: VoiceOver labels/traits on custom controls, Dynamic Type (test at largest accessibility size — layouts must reflow, not truncate), `accessibilityElement` grouping on composite cells.
- Android: TalkBack `contentDescription`, touch targets 48dp, font scale 200% test.
- React Native: `accessibilityRole`, `accessibilityLabel`, `accessibilityState` on every touchable.

## Audit procedure + finding format

Keyboard-only walk (every action reachable, no traps) → screen-reader pass on the changed flow → contrast sweep (browser devtools or Polypane) → `prefers-reduced-motion` toggle → automated pass (Pest v4 `assertNoAccessibilityIssues()`, axe, or Lighthouse) — automated catches ~40%, it supplements, never replaces the manual walk.

Finding: WCAG criterion number · element (`file:line` or route + selector) · who it blocks (keyboard / SR / low-vision / motor) · concrete fix. Severity: blocks-task > degrades-task > polish.
