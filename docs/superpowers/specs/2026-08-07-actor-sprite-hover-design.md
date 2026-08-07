# Interactive actor sprites — hover tooltip + visual reaction

**Goal:** Make the console's actor sprites respond to hover — a tooltip
showing elapsed time and the current tool call, plus a small visual
reaction — without changing what clicking them does (still opens the
transcript panel, same as clicking anywhere else on the card).

**Why:** The actor sprites (shipped v1.38.0) currently render as static
art. Driving a real multi-lane run through the console surfaced that they
give no feedback to a hover — a natural target for feedback, since they're
the most visually prominent element on each card.

**Architecture:** Wrap the sprite's existing `<span>` (inside `Actor.tsx`)
with the codebase's already-present-but-unused shadcn/Base-UI `Tooltip`
primitives (`console-ui/src/components/ui/tooltip.tsx`), rendering the
trigger as a plain `<span>` rather than its default element, and add a
hover-scoped CSS scale transform to the same span. No backend or
`server.py` changes — everything the tooltip needs (elapsed time, current
tool name) is already available on the frontend's `Lane` data.

## Scope

- **Files:** `console-ui/src/components/Actor.tsx`, `console-ui/src/components/AgentCard.tsx`. Possibly `console-ui/src/main.tsx` or `App.tsx` if no `TooltipProvider` currently wraps the app (must check; Base UI's tooltip requires one ancestor provider).
- **Tooltip content: elapsed time + current tool call only.** Live token counts were considered and explicitly excluded — tokens are not currently streamed to the frontend at all (only computed after a run finishes, by the offline `scripts/eval-cost.py`/cost-attribution path); adding them live would need new backend wiring from `server.py`, out of scope for this release.
- **Hover is scoped to the sprite element itself**, not the whole card. CSS `:hover` (or Framer Motion's `whileHover`) naturally only activates while the pointer is within that specific element's box — no special isolation logic needed, just don't place the hover rule on the outer card.
- **Click is unchanged.** The card is a single `<motion.button>` (`AgentCard.tsx`) with the sprite nested inside; clicking the sprite already bubbles to the button's `onClick`. Nothing about adding the tooltip trigger may break this — the trigger must render as a `<span>` (via Base UI's `render` prop: `<TooltipTrigger render={<span />}>`), not its default, since rendering a button (or any element with an implicit interactive role) nested inside the card's own `<button>` would be invalid HTML and Chrome/browsers auto-correct nested buttons in ways that break the existing click handler.

## Data sourcing

- **Elapsed time:** reuse the existing `useElapsed(lane.startedAt, lane.endedAt)` hook, already called in `AgentCard.tsx` and passed down (or recomputed) for the tooltip.
- **Current tool call:** new. `Lane.events` (`GuildEvent[]`) already carries every event for that lane, including `type: "tool_use"` events with a `tool` field (the tool name) and a `tool_use_id`. Confirmed against a real recorded run
  (`.claude/console/runs/*.jsonl`) — the exact shape observed:
  ```json
  {"seq": N, "run_id": "...", "ts": N, "type": "tool_use", "agent": "...", "lane_id": "...", "tool": "Read", "tool_use_id": "...", "input": {...}}
  ```
  A new small selector (e.g. `currentTool(lane: Lane): string | null` in `console-ui/src/lib/`) finds the most recent `tool_use` event in `lane.events` and returns its `tool` field, or `null` if none exists yet (lane just started, no tool called yet). When `null`, the tooltip's tool line reads **"starting…"** rather than being omitted — omitting it would make the tooltip's layout shift height the instant the first tool call lands, which reads as a layout jump on an element the user is actively hovering.
- **Token counts:** confirmed NOT available — `result`-type events carry a `usage` field, but only once, on the single final event when a lane completes; there is no incremental/live token count during execution. This is the concrete evidence behind excluding tokens from scope.

## Visual reaction

A modest scale-up on hover (e.g. `scale(1.12)`), transform-only (no layout shift), applied via a CSS rule scoped to the sprite's own class/data-attribute, or Framer Motion's `whileHover` if kept consistent with the rest of the sprite's existing CSS-keyframe-driven animation approach (`Actor.tsx`'s own docstring: "every pose is CSS keyed off `data-pose`, so nothing ships an animation runtime for it" — a plain CSS `:hover` rule keeps that property; a `whileHover` would introduce Framer Motion where the component currently has none). **Recommendation: plain CSS**, to stay consistent with the sprite's existing zero-runtime-animation design.

Must respect the codebase's existing reduced-motion convention (`MotionConfig reducedMotion="user"` in `main.tsx`, plus whatever CSS-level `prefers-reduced-motion` handling the sprite's keyframes already use) — the hover scale should not fire, or should be instant rather than eased, when the user has reduced motion enabled.

## Testing

- **Vitest, `Actor.test.tsx` or `AgentCard.test.tsx`:** hovering the sprite shows a tooltip; its text includes the elapsed time and the current tool name derived from a synthetic `Lane` fixture with `tool_use` events.
- **The test that actually matters, mutation-style:** clicking the sprite still fires the card's `onSelect` callback, WITH the tooltip wrapper in place. Write this by rendering the real component tree (not a stub), simulating a click directly on the sprite's DOM node, and asserting `onSelect` was called — this is exactly the kind of thing a nested-interactive-element mistake silently breaks, and the existing `App.test.tsx` conventions in this codebase already favor this kind of real-DOM assertion over shallow rendering.
- **Reduced-motion:** a test or manual check (matching this codebase's existing "verify live in a browser" habit for motion work) confirming the hover scale is suppressed or non-animated under `prefers-reduced-motion`.

## What this does not do

- No backend/`server.py` changes.
- No live token counts.
- No change to click behavior, approval flow, or any other part of the board.
- No change to the sprite's rendering at `lg` size (lane panel) — hover is a card-level (`sm` size) affordance only, since the lane panel is already the "more detail" surface.
