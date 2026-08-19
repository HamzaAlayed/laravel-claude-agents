# Console company-theater Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restage `/console` as a two-act company floor (call sheet → theater → spotlight) without changing the Python server, reducer, or submit-gate safety.

**Architecture:** One React app, three scenes (`call` | `floor` | `spotlight`) derived in `App` from a small pure helper plus `spotlightOpen`. Existing `reduce` / `submitGate` / SSE stay. ApprovalBar and the modal DecisionSheet chrome go away; their logic moves into Spotlight. Dist is rebuilt with `.nvmrc` Node and committed.

**Tech Stack:** React 19, Vite 8, Tailwind 4, Base UI, motion, Vitest, existing `scripts/console/server.py`.

**Spec:** `docs/plans/2026-08-19-console-company-theater-design.md`

**Do not edit:** `agents/`, `commands/` (except screenshot captions in README/onboarding), `tests/eval/`, `VERSION`, plugin manifests, `scripts/console/server.py` (unless a test proves a chrome-only bug).

---

### Task 1: Pure scene helper

**Files:**
- Create: `console-ui/src/lib/scene.ts`
- Create: `console-ui/src/lib/scene.test.ts`

**Step 1: Write the failing tests**

```ts
import { describe, expect, it } from "vitest";
import { sceneOf } from "./scene";

const idle = {
  runActive: false,
  recorded: false,
  pending: 0,
  spotlightOpen: false,
};

describe("sceneOf", () => {
  it("is call when nothing is running", () => {
    expect(sceneOf(idle)).toBe("call");
  });

  it("is floor for a live run with no spotlight", () => {
    expect(sceneOf({ ...idle, runActive: true })).toBe("floor");
  });

  it("is spotlight only when live, open, and a prompt waits", () => {
    expect(
      sceneOf({ runActive: true, recorded: false, pending: 1, spotlightOpen: true }),
    ).toBe("spotlight");
  });

  it("stays floor when the human dismissed but a prompt still waits", () => {
    expect(
      sceneOf({ runActive: true, recorded: false, pending: 1, spotlightOpen: false }),
    ).toBe("floor");
  });

  it("never spotlights a recording", () => {
    expect(
      sceneOf({ runActive: false, recorded: true, pending: 1, spotlightOpen: true }),
    ).toBe("floor");
  });
});
```

**Step 2: Run to verify fail**

```bash
cd console-ui && npx vitest run src/lib/scene.test.ts
```

Expected: FAIL — cannot resolve `./scene`.

**Step 3: Minimal implementation**

```ts
export type Scene = "call" | "floor" | "spotlight";

export type SceneInput = {
  runActive: boolean;
  recorded: boolean;
  pending: number;
  spotlightOpen: boolean;
};

export function sceneOf(input: SceneInput): Scene {
  if (input.recorded) return "floor";
  if (!input.runActive) return "call";
  if (input.spotlightOpen && input.pending > 0) return "spotlight";
  return "floor";
}
```

**Step 4: Tests pass**

```bash
cd console-ui && npx vitest run src/lib/scene.test.ts
```

Expected: 5 passed.

**Step 5: Commit**

```bash
git add console-ui/src/lib/scene.ts console-ui/src/lib/scene.test.ts
git commit -m "feat(console): derive call / floor / spotlight from run state"
```

---

### Task 2: Studio tokens and fonts

**Files:**
- Modify: `console-ui/package.json` (add font packages, remove Geist)
- Modify: `console-ui/src/index.css`
- Modify: `console-ui/src/main.tsx` (font imports)

**Step 1:** From `console-ui/`:

```bash
npm uninstall @fontsource-variable/geist
npm install @fontsource-variable/syne @fontsource-variable/source-sans-3 @fontsource/ibm-plex-mono
```

**Step 2:** In `main.tsx`, replace Geist import with:

```ts
import "@fontsource-variable/syne";
import "@fontsource-variable/source-sans-3";
import "@fontsource/ibm-plex-mono";
```

**Step 3:** In `index.css` `@theme inline` / `:root`, set:

- `--font-sans: "Source Sans 3 Variable", sans-serif;`
- `--font-heading: "Syne Variable", sans-serif;`
- `--font-mono: "IBM Plex Mono", ui-monospace, monospace;`
- `--background` / `--foreground` from plaster/ink on Act I; Act II will set `data-scene=floor` on `<html>` to swap `--background` to `#2F2C28` and light type
- Named colors as custom props: `--plaster: #B7AFA4; --floor: #2F2C28; --ink: #1C1917; --paper: #E6E1D6; --tungsten: #CC8A3A; --cue: #A33B32;`
- Spotlight dim: `[data-scene=spotlight] [data-floor] { opacity: 0.28; }` gated with `@media (prefers-reduced-motion: no-preference)` for the transition only; under reduce, still dim instantly
- Keep `[data-pose][data-hover]:hover { transform: scale(1.12) }` sm-only contract

Do not invent extra tokens. Drop unused shadcn chart/sidebar variables only if a test or build proves they are unused — otherwise leave them.

**Step 4:**

```bash
cd console-ui && npx vitest run
```

Expected: existing 180 tests still pass (tokens only).

**Step 5: Commit**

```bash
git add console-ui/package.json console-ui/package-lock.json console-ui/src/index.css console-ui/src/main.tsx
git commit -m "feat(console): rehearsal-studio tokens and type"
```

---

### Task 3: CallSheet (Act I)

**Files:**
- Modify: `console-ui/src/components/Launcher.tsx` (keep `LaunchSpec` + `roleOf`; restyle as call sheet, `id="guild-call-sheet"`)
- Modify: `console-ui/src/components/Launcher.test.tsx`

Keep: segmented kind, visible target label = aria-label, kind-reset target test, Cmd/Ctrl+Enter, `roleOf`.

Change: full-viewport call sheet on plaster; production title in Syne; Start is the only primary button; captions stay. Do not render a board.

**Step 1:** Extend `Launcher.test.tsx` with `expect(document.getElementById("guild-call-sheet")).toBeTruthy()`.

**Step 2:** Run `npx vitest run src/components/Launcher.test.tsx` — fail if id missing.

**Step 3:** Restyle markup; keep props `{ catalog, busy, busyReason, onLaunch }`.

**Step 4:** Tests pass.

**Step 5: Commit** `feat(console): restage launcher as the call sheet`

---

### Task 4: Spotlight (decision takes the stage)

**Files:**
- Create: `console-ui/src/components/Spotlight.tsx`
- Modify: `console-ui/src/components/DecisionSheet.tsx` — keep exporting `buildAnswers`, `mergeFreeText`, `splitJsonKey`; UI becomes a thin re-export or Spotlight uses those helpers
- Modify: `console-ui/src/components/DecisionSheet.test.tsx` (helpers stay)
- Create: `console-ui/src/components/Spotlight.test.tsx`

**Behavior:**
- Same props as today’s DecisionSheet (`pending`, `queueLength`, `onAnswer`, `onClose`, gate via disabled buttons from `canSubmit`)
- Not a Base UI `Sheet`. Full main canvas. Large `Actor` `size="lg"` for the parked agent (no hover/`elapsed` — existing lg contract)
- `{n} remaining` hidden at 1 (copy DecisionSheet tests)
- `key={pending.prompt_id}` still applied by App

**Step 1:** Port the remaining-count tests onto Spotlight; keep helper tests on DecisionSheet.

**Step 2:** Fail, then implement Spotlight using the helpers.

**Step 3:** Commit `feat(console): spotlight scene for parked approvals`

---

### Task 5: Floor stations

**Files:**
- Modify: `console-ui/src/components/Board.tsx`, `StageColumn.tsx`, `AgentCard.tsx`, `AgentCard.test.tsx`, `Actor.tsx` (no pose SVG edits)
- Optional rename in a later commit if tests stay green — **this task restyles in place** (`data-station`, floor colors). Do not rename files yet (smaller diff).

Stations sit on `--floor`. Parked = `cue` mark + existing attention pulse. Hover tooltip unchanged (sm, span trigger). `aria-label` still `Adam: add the export job`.

**Step 1:** `AgentCard.test.tsx` already clicks the sprite — must still fire `onSelect`.

**Step 2:** Restyle card chrome only.

**Step 3:** `npx vitest run src/components/AgentCard.test.tsx src/components/Actor.test.tsx`

**Step 4:** Commit `feat(console): restage board cards as floor stations`

---

### Task 6: ShowHeader, CueLine, Sides

**Files:**
- Create: `console-ui/src/components/ShowHeader.tsx`
- Modify: `console-ui/src/App.tsx` follow-up to `id="cue-line"`
- Modify: `console-ui/src/components/LanePanel.tsx` — restyle as `Sides` (can keep export name `LanePanel` to avoid a wide rename)

ShowHeader: Syne title (`formatRunLabel` / launch text), clock (`StatusChip` restyled tungsten), Stop (`Square`). No run-picker on the floor — past shows live on the call sheet only. (Move the recorded `<select>` into CallSheet in Task 7.)

**Step 1:** Test that Stop calls `onStop` and the header does not include `#guild-launcher`.

**Step 2:** Implement.

**Step 3:** Commit `feat(console): show header and cue line for Act II`

---

### Task 7: Wire scenes in App; delete ApprovalBar

**Files:**
- Modify: `console-ui/src/App.tsx`
- Modify: `console-ui/src/App.test.tsx`
- Delete: `console-ui/src/components/ApprovalBar.tsx`

**App state:** `spotlightOpen` boolean. `onEvent` `prompt` → `setSpotlightOpen(true)`. `answer` last-in-queue → `setSpotlightOpen(false)`. Spotlight `onClose` → `setSpotlightOpen(false)` without resolving the prompt. `onSelect`: if `parkedLaneIds(view).has(lane.toolUseId)` then `setSpotlightOpen(true)` and do not open Sides; else `setSelected(lane)`.

Set `document.documentElement.dataset.scene = sceneOf(...)`.

Render:
- `call` → CallSheet + error line + past-shows select
- `floor` / `spotlight` → ShowHeader + Floor (data-floor) + CueLine + Sides + result/failure. Spotlight mounted on top when scene is spotlight.

Do not mount ApprovalBar. Do not mount CallSheet during a live run.

**Tests to add in App.test.tsx** (extend existing fakeServer launch helpers):

1. After `launch()`, call sheet is gone (`guild-call-sheet` null), floor/header present
2. Emitting `prompt` shows Spotlight (Allow once / tool name), not a “Review” bar
3. Dismiss (Close) hides Spotlight; a parked card remains; clicking it shows Spotlight again
4. Recorded `openRecorded` never shows Allow

Keep: remaining-count test, kind-reset (now only on call sheet), interrupt, harvest-unrelated checks.

**Step 1:** Write the four tests, run, fail.

**Step 2:** Wire App.

**Step 3:** `cd console-ui && npx vitest run` — all green.

**Step 4:** Commit `feat(console): two-act scene wiring; drop the approval bar`

---

### Task 8: Pose capture and docs image

**Files:**
- Modify: `console-ui/src/dev/poseBoard.tsx` — wait for floor stations, not the old launcher-on-board stack; optionally a second pose for spotlight
- Recapture: `docs/images/console-board-mid-run.png`
- Modify: `README.md` / `docs/onboarding.md` captions if the still is now Act II

Recipe unchanged: `npm run dev` + `npm install --no-save playwright` + `node src/dev/capture.mjs`. Do not `npm run build` from the pose entry. Honest caption: fixture-driven, not billed live `/console`.

**Commit:** `docs: recapture console board as the company floor`

---

### Task 9: Dist, changelog, corpus Open

**Files:**
- Rebuild: `scripts/console/dist/**` with `PATH` including Node 22 from `.nvmrc`
- Modify: `CHANGELOG.md` `[Unreleased]` Added/Changed — two-act console, drop approval bar
- Modify: `docs/README.md` Open row already added with the design; leave until the slice ships

```bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"   # or nvm use
node -v   # 22.x
cd console-ui && npm run build
cd .. && git diff --stat scripts/console/dist
python3 scripts/check_inventory_sync.py
./tests/guardrails.test.sh
cd console-ui && npx vitest run
python3 -m unittest discover -s tests/console -t tests/console -p 'test_*.py'
```

Expected: inventory ok at 1.43.0, guardrails green, Vitest green, dist hashes committed, `git diff --exit-code -- scripts/console/dist` after the commit.

Do not bump `VERSION` in this slice (next minor after it lands).

**Commit:** `feat(console): commit theater bundle and changelog`

---

## Self-check

- Scene helper is the only new logic; everything else is chrome around existing events
- submitGate still in App
- ApprovalBar deleted in Task 7, not before Spotlight exists
- Dist rebuild is last so CI’s stale-bundle gate sees one hash
