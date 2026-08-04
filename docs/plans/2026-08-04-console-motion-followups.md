# Console motion upgrade — held follow-ups

Everything the motion/usability upgrade (merge `4367ab2`, spec
`docs/superpowers/specs/2026-08-03-console-motion-usability-design.md`)
knowingly left behind. Nothing here blocks a release; each entry says why it
was held so the next person does not re-derive the reasoning.

## Found by driving a real browser, not by the suite

**The approval bar's Review button is occluded while a transcript panel is
open.** `LanePanel` is pinned right at `sm:max-w-md` (448 px, full height,
`z-50`); the approval bar is `sticky top-0 z-30` with Review right-aligned,
so the panel covers exactly that button. Reproduced: park a decision, dismiss
the sheet with Escape, open any agent card, then try to click Review —
Playwright times out with the panel's own content intercepting the pointer.

Scope is narrower than it sounds. A decision *arriving* closes the panel
(`onEvent` clears `selected`), and clicking Review when it is reachable also
closes it — so this needs the specific order: decision already parked → sheet
dismissed → panel opened. It is recoverable without knowing a trick: Escape
closes the panel and Review works immediately (verified, with the submit gate
correctly re-armed afterwards). The bar's *text* stays visible throughout, so
the run never looks silent — only the button is unreachable by mouse.

Held rather than fixed because every fix is a layout judgment the pack's owner
should make, not a mechanical patch:

- Raise the bar above the panel (`z-50`+) — the bar would then cover the
  panel's own header and its Close button.
- Offset or narrow the panel so the bar's right edge stays clear — changes the
  panel's proportions for a state that is rare.
- Refuse to open the panel while a decision is parked — worst of the three:
  reading an agent's transcript to *decide how to answer* is exactly when the
  panel earns its place.

## Ride-along minors from the whole-branch review

All triaged CAN RIDE; grouped by where they'd naturally be fixed.

- **LanePanel's frame pops on close.** `open` is hardcoded `true`, so Base UI's
  `data-ending-style` slide-out never runs; the inner `motion.div` fades over
  200 ms and then the frame disappears. Content animates, chrome does not.
- **`splitJsonKey` misses keys containing escaped quotes** (`"my\"key":`) —
  `[^"]+` stops at the backslash. Cosmetic tint false-negative only; verified
  it cannot false-positive on `JSON.stringify` output.
- **"Decision 1 of N" is a countdown, not a position** — the `1` is hardcoded,
  so a three-deep queue reads 1 of 3 → 1 of 2 → hidden. As specified; revisit
  the wording if it reads wrong in practice.
- **A11y pass, three items together:** the Target select's accessible name
  (`aria-label="Target"`) differs from its visible label (Command/Specialist),
  which is WCAG 2.5.3 — the aria-label was pinned by the upgrade's own
  constraints, so renaming needs both sides moved at once; the kind and mode
  captions share one `<p>` and read as a run-on to a screen reader; and
  neither LanePanel nor DecisionSheet restores focus on close (pre-existing
  pattern, no trigger element to return to).
- **Test coverage gaps:** no regression test for "switching kind resets
  target" (behavior verified correct by hand), and none for the `MotionConfig`
  wrap in `main.tsx` (a test there would assert framework behavior).
- **`ago()` renders a future `started_at` as "just now"** — benign clock-skew
  fallback, untested and unspecified.
- **`server.py` logs a `BrokenPipeError` traceback** when a non-keep-alive
  client closes early. Pre-existing, surfaced by a smoke script; outside this
  branch's no-server-changes constraint.

## Verified live, so do not re-check

Driven in a real browser against the built bundle with a scripted live run
(two parallel lanes, two simultaneous approvals): the header chip ticks
(9.0s → 11s) with its dot pulsing; both parked cards run `attention-pulse`
2s infinite in their own agent colors, with the border mid-interpolation
proving the keyframe is live; the approval bar names the right agent and
counts "2 waiting on you"; the sheet auto-opens showing "Decision 1 of 2"
with tinted JSON keys; answering posts exactly `{behavior: "allow"}`, the
queue advances to the second decision, the answered lane stops pulsing, and
the end state clears bar, sheet and pulses while the run stays live.
