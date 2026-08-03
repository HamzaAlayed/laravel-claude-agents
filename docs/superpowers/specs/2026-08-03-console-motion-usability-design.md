# Design — console motion and usability upgrade

**Date:** 2026-08-03
**Scope:** `console-ui/` only — the Guild web console.
**Approach chosen:** polish in place, plus one structural fix (the transcript
slide-over). Rejected: a full command-center relayout (too much test churn
around the approval flow's protected invariants) and a motion-only pass (leaves
the launcher and run picker as hard to use as they are).

## Goals

The console works but feels utilitarian and hides state. Four pain points,
all confirmed by the user:

1. **Launching a run** — the launcher is a dense row of unlabeled dropdowns;
   nothing explains what a kind, target, or permission mode means.
2. **Following what's happening** — the transcript renders below the board
   where it is easy to miss; banners pop in as plain text; "is it still
   running?" requires reading the board.
3. **Answering approvals** — noticing a parked agent and moving through a
   queue of decisions could be clearer.
4. **General polish** — state changes teleport instead of transitioning.

Motion character: **calm and purposeful.** 150–300 ms micro-interactions,
motion only where it carries state information, one looping animation in the
whole UI (the parked pulse).

## Constraints

- **No new dependencies.** The repo commits `console-ui/dist/` behind a CI
  bundle-in-sync gate with one blessed Node version; everything needed is
  already in `package.json` (`motion` 12, `tw-animate-css`, shadcn `Sheet`).
- **No reducer, submit-gate, or API changes.** The one-click-one-decision
  invariants in `App.tsx` / `lib/submitGate.ts` and the remount-per-prompt_id
  of `DecisionSheet` stay exactly as written. This upgrade is presentation.
- The global `prefers-reduced-motion` guard in `index.css` must cover every
  new animation, including the parked pulse (collapses to a static 2 px
  colored border).

## The motion system

New file `src/lib/motion.ts` exporting shared presets; components stop
improvising their own transitions:

- `spring` — the existing card spring (`stiffness: 380, damping: 30`),
  adopted for all layout motion.
- `fadeRise` — opacity 0→1 with an 8 px rise, ~200 ms, for content appearing.
- `fadeDrop` — the inverse, for the sticky approval bar (which adopts the
  preset in place of its inline transition).

| Surface | Motion | Meaning |
|---|---|---|
| Status banners (error, pack-broken, retry, unasked, recorded-notice) | `AnimatePresence` fade/rise in and out | "something changed" |
| Final answer / failure section | `fadeRise` on arrival | "the run concluded" |
| Parked agent cards + header lane | 2 s CSS border-color pulse on the agent-colored border | "waiting on you" — the only looping animation |
| Approval bar count badge | scale pop (0.8→1) on count change | "the queue grew" |
| Transcript rows | CSS-only fade-in on new rows | live feed feels live; no motion/react at row scale |
| Buttons (Run, Review, sheet actions) | hover/active micro-scale | tactile feedback |

## Launcher and navigation

**Launcher** (`Launcher.tsx`) — same `LaunchSpec`, self-explanatory chrome:

- Kind: a labeled three-button segmented control replacing the bare select,
  with a caption that updates per kind — "Give the Guild a task in your own
  words" / "Run one of the pack's slash commands" / "Send a task straight to
  one specialist".
- Target: stays a native `<select>` (keyboard and screen-reader friendly),
  gains a visible label; specialists show name + role from the catalog.
- Mode: same caption treatment — "Asks before edits and commands" / "Edits
  land without asking" / "Plans only, changes nothing".
- The task text field becomes the visual anchor: full-width on its own row.
- **Cmd/Ctrl+Enter submits from anywhere in the form.** The disabled-with-
  reason behavior of the Run button is unchanged.

**Run picker** (`App.tsx` header) — options become readable:
`make-feature · done · 12m ago`. Kind from `spec?.kind` (falling back to
"run" for disk-derived rows where `spec` is null), status verbatim, relative
time from `started_at`. Formatting lives in a pure helper `formatRunLabel`
(new, in `lib/`), unit-tested directly.

**Header** — a live status chip next to the title: pulsing dot +
"running · 2m 14s" while live (reusing `useElapsed`), becoming a static
"done" / "error" chip when the run ends. No chip for recorded replays — the
existing read-only notice banner already covers those. Existing mode select
and Interrupt button unchanged in behavior.

## Transcript slide-over

The `selected`-lane section currently rendered below the board moves into the
existing shadcn `Sheet`, `side="right"`, ~28 rem wide, slide-in animated.
Header: agent color chip, name, current task. Body: the `Transcript`
component unchanged — its tail-following behavior is already right. Escape or
the overlay closes it (`selected` → null); clicking a different card while
open swaps content in place. Full-width on small screens. `App`'s `selected`
state and the `onSelect` wiring are untouched; only where it renders changes.

## Approvals

Logic untouched. Three presentation upgrades to `DecisionSheet.tsx`:

1. Sheet title gains a queue position — "1 of 3" — when more than one
   decision waits (the queue length is already available in `App`).
2. The new prompt's content plays `fadeRise` on mount. The remount-per-
   prompt_id IS the transition, so the gate's arm-after-remount timing is
   unaffected.
3. The deny/reply textarea moves visually adjacent to the buttons that use
   it, with a caption clarifying it feeds Deny or "Reply in my own words".
   The tool-input `<pre>` stays `JSON.stringify` output, split on lines and
   rendered with the `"key":` prefix of each line wrapped in a
   `text-muted-foreground` span — no highlighting library, one pure
   function, tested alongside the sheet.

## Error handling

No behavioral changes. Every `role="alert"` stays; banner content stays;
optimistic-revert paths in `App` stay. Animation wraps existing conditionals —
a banner that used to appear still appears, without teleporting.

## Testing

- Existing Vitest suite stays green. motion/react renders in jsdom;
  assertions target presence/absence, never animation timing.
- New tests: `formatRunLabel` (null spec, relative time), launcher captions
  per kind + Cmd/Ctrl+Enter submit, transcript sheet open/swap/close, queue
  position indicator.
- `npm run build` must reproduce the committed `dist/` under the blessed
  Node version per the release checklist — verified, not assumed.
