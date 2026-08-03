# Console Motion & Usability Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Guild web console calm, purposeful animation and a self-explanatory surface — launcher, run picker, status chip, transcript slide-over, approval-sheet polish — without touching the reducer, submit gate, or API.

**Architecture:** All work is inside `console-ui/`. A shared motion vocabulary (`src/lib/motion.ts`) feeds `motion/react` wrappers around existing conditionals; attention states (parked pulse, count pop, row fade) are CSS-only via `tw-animate-css` and one custom keyframe; the transcript moves from a below-the-board section into a **non-modal** right-side Sheet so the board stays clickable behind it. Spec: `docs/superpowers/specs/2026-08-03-console-motion-usability-design.md`.

**Tech Stack:** React 19, Vite, Tailwind v4, shadcn (Base UI dialogs), `motion` 12, `tw-animate-css`, Vitest + Testing Library with the transport-level fake server (`src/test/fakeServer.ts`).

## Global Constraints

- **No new npm dependencies.** Everything is already in `console-ui/package.json`.
- **No changes to** `src/lib/reducer.ts`, `src/lib/submitGate.ts`, `src/lib/api.ts`, or any POST payload. Presentation only.
- **Keep these accessible names and placeholders exactly** — tests and muscle memory depend on them: aria-labels `Run kind`, `Target`, `Permission mode`, `Open a recorded run`, `Change this run's permission mode`, `Follow-up message`, `Interrupt the running agent`; placeholders `describe the task`, `arguments (optional)`, `Tell the agent why, or what to do instead`, `Other — type your own answer`; every existing `role="alert"`.
- **Existing test suite stays green**: `cd console-ui && npm test`. One narrow exception is allowed: if moving the transcript into a portal makes a *synchronous* `getByRole("heading", …)` query in an existing test flake purely on mount timing, change that query to `await screen.findByRole(…)` — a timing-only adjustment; never weaken what a test asserts.
- **Durations 150–300 ms.** Every animation must sit under the existing global `prefers-reduced-motion` guard in `index.css` (it already zeroes all animation/transition durations — CSS keyframes and tw-animate utilities are covered automatically; the parked pulse must degrade to a static colored border).
- **The committed bundle** lives at `scripts/console/dist/` and must be rebuilt **under Node 22** (`.nvmrc`; the dev machine currently runs 26 — switch with `nvm use` first). CI fails if dist drifts from source.
- Run all commands from `console-ui/` unless a step says otherwise. Commit after every task.

---

### Task 1: Motion presets + animated banners, result, and failure sections

**Files:**
- Create: `console-ui/src/lib/motion.ts`
- Modify: `console-ui/src/App.tsx` (banners, result, failure)
- Modify: `console-ui/src/components/ApprovalBar.tsx` (adopt the preset it already approximates)
- Test: existing `console-ui/src/App.test.tsx` is the safety net — this task changes no behavior, so the cycle is "wrap, then prove the suite still passes"

**Interfaces:**
- Consumes: nothing new.
- Produces: `spring`, `fadeRise`, `fadeDrop` — plain objects spread onto `motion.*` elements, e.g. `<motion.p {...fadeRise}>`. Tasks 6 and 7 import `fadeRise`. Exact shapes below.

- [ ] **Step 1: Create the presets**

```ts
// console-ui/src/lib/motion.ts
/**
 * The console's whole motion vocabulary. Spread onto motion elements:
 * <motion.p {...fadeRise}>. Components do not improvise their own timings.
 */

/** Layout motion — the board's existing card spring, now shared. */
export const spring = { type: "spring", stiffness: 380, damping: 30 } as const;

/** Content appearing in place: banners, the final answer, sheet bodies. */
export const fadeRise = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 8 },
  transition: { duration: 0.2 },
} as const;

/** The sticky approval bar dropping in from above. */
export const fadeDrop = {
  initial: { opacity: 0, y: -12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: { type: "spring", stiffness: 420, damping: 32 },
} as const;
```

- [ ] **Step 2: Wrap App's banners and terminal sections**

In `App.tsx`, import `AnimatePresence, motion` from `"motion/react"` and `fadeRise` from `"@/lib/motion"`. Convert each of these existing conditionals so the element becomes a `motion.*` twin wrapped in its own `AnimatePresence` (each banner keeps its position in the layout — do not group them):

- the recorded-run notice `<p>` → `<AnimatePresence>{recorded && <motion.p {...fadeRise} className="…unchanged…">…</motion.p>}</AnimatePresence>`
- the `packBroken` alert `<p role="alert">` — keep `role="alert"`
- the `error` alert `<p role="alert">` — keep `role="alert"`
- the `view.unasked > 0` note `<p>`
- the `view.retry` note `<p>`
- the final-answer `<section>` → `motion.section` with `{...fadeRise}`
- the failure `<section role="alert">` → `motion.section` — keep `role="alert"`

Nothing else about these blocks changes: same classNames, same children, same order.

- [ ] **Step 3: ApprovalBar adopts `fadeDrop`**

In `ApprovalBar.tsx`, replace the inline `initial/animate/exit/transition` props on the `motion.div` with `{...fadeDrop}` (import from `"@/lib/motion"`). The values are identical to what is there today — this is deduplication, not a behavior change.

- [ ] **Step 4: Run the whole suite**

Run: `npm test`
Expected: PASS — every banner/section assertion already goes through `getByText`/`waitFor`, which tolerate a 200 ms exit. If an *absence* assertion fails because an element now animates out, wrap that single assertion in `waitFor` (the suite already does this for the approval bar at App.test.tsx:201).

- [ ] **Step 5: Commit**

```bash
git add src/lib/motion.ts src/App.tsx src/components/ApprovalBar.tsx
git commit -m "feat(console-ui): one motion vocabulary; banners and outcomes stop teleporting"
```

---

### Task 2: CSS attention layer — parked pulse, count pop, row fade, button feedback

**Files:**
- Modify: `console-ui/src/index.css` (one keyframe + utility)
- Modify: `console-ui/src/components/AgentCard.tsx`, `console-ui/src/components/Board.tsx` (apply pulse to parked card + parked header lane)
- Modify: `console-ui/src/components/ApprovalBar.tsx` (count badge pop)
- Modify: `console-ui/src/components/Transcript.tsx` (row fade-in)
- Modify: `console-ui/src/components/ui/button.tsx` (active micro-scale)
- Test: existing suite; plus one class-level assertion in `App.test.tsx`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: CSS class `animate-attention` driven by CSS variable `--lane-color`. Later tasks don't consume it.

- [ ] **Step 1: Write the failing test**

Append to the `describe("a parked approval", …)` block in `App.test.tsx`:

```tsx
it("pulses the parked card so it can be found without reading", async () => {
    const { server, user } = await launch();
    server.emit({
      type: "agent_start", agent: "qa-engineer",
      tool_use_id: "t2", task: "cover it with tests",
    });
    server.emit(approval("p1", "qa-engineer"));
    await user.click(await screen.findByRole("button", { name: "Close" }));

    // The class is the contract here: the animation itself is CSS.
    expect(button("Dina: cover it with tests").className).toContain("animate-attention");
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `npm test -- App.test`
Expected: FAIL — `className` does not contain `animate-attention`.

- [ ] **Step 3: Implement the CSS + apply it**

Append to `index.css` (before the reduced-motion block):

```css
/*
 * The one looping attention animation in the console: a parked lane breathing
 * its own agent color. --lane-color is set inline by the card/header button.
 * Under prefers-reduced-motion the global guard freezes this at the 0% frame —
 * a static, fully colored 2px border.
 */
@keyframes attention-pulse {
  0%, 100% { border-color: var(--lane-color); }
  50% { border-color: color-mix(in oklab, var(--lane-color) 35%, transparent); }
}
.animate-attention {
  animation: attention-pulse 2s ease-in-out infinite;
}
```

In `AgentCard.tsx`: add the class and the variable when parked —

```tsx
className={`w-full rounded-lg border bg-card p-2.5 text-left focus-visible:ring-2 ${parked ? "animate-attention" : ""}`}
style={{
  ["--lane-color" as string]: color,
  borderColor: parked ? color : undefined,
  borderWidth: parked ? 2 : 1,
}}
```

In `Board.tsx`, the header-lane `<button>` gets the same treatment: append `${parkedLanes.has(lane.toolUseId) ? " animate-attention" : ""}` to its className and add `["--lane-color" as string]: agents[lane.slug]?.color ?? "#64748b"` to its style object.

- [ ] **Step 4: Count badge pop + transcript row fade + button feedback**

In `ApprovalBar.tsx`, give the "waiting on you" span a `key` so it remounts (and replays its entrance) whenever the count changes, plus tw-animate utilities:

```tsx
<span
  key={pending.length}
  className="shrink-0 animate-in fade-in zoom-in-75 duration-200 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-semibold tabular-nums"
>
  {pending.length} waiting on you
</span>
```

In `Transcript.tsx`, the `<li>` gains entrance classes: `className="flex gap-2 animate-in fade-in duration-300"`. (Rows animate once, on mount — CSS only, cheap at any row count.)

In `ui/button.tsx`, add `transition-transform active:scale-[0.98]` to the base class string of the button variants (the first argument of the `cva(...)` call).

- [ ] **Step 5: Run the whole suite**

Run: `npm test`
Expected: PASS, including the new pulse test.

- [ ] **Step 6: Commit**

```bash
git add src/index.css src/components/AgentCard.tsx src/components/Board.tsx src/components/ApprovalBar.tsx src/components/Transcript.tsx src/components/ui/button.tsx src/App.test.tsx
git commit -m "feat(console-ui): parked lanes breathe their agent color; small tactile feedback"
```

---

### Task 3: `formatRunLabel` + a readable run picker

**Files:**
- Create: `console-ui/src/lib/runLabel.ts`
- Create: `console-ui/src/lib/runLabel.test.ts`
- Modify: `console-ui/src/App.tsx` (picker options)

**Interfaces:**
- Consumes: `RunRow` from `@/lib/api` (`{ run_id, status, spec: {kind?…} | null, started_at: number }`).
- Produces: `formatRunLabel(row: RunRow, now?: number): string` — used only by App's picker.

- [ ] **Step 1: Write the failing tests**

```ts
// console-ui/src/lib/runLabel.test.ts
import { describe, expect, it } from "vitest";
import { formatRunLabel } from "./runLabel";
import type { RunRow } from "./api";

const NOW = 1_800_000_000_000;
const row = (over: Partial<RunRow> = {}): RunRow => ({
  run_id: "r1",
  status: "done",
  spec: { kind: "make-feature" },
  started_at: 0,
  ...over,
});

describe("formatRunLabel", () => {
  it("reads kind · status · relative time", () => {
    expect(formatRunLabel(row({ started_at: NOW - 12 * 60_000 }), NOW)).toBe(
      "make-feature · done · 12m ago",
    );
  });

  it("calls the last minute 'just now'", () => {
    expect(formatRunLabel(row({ started_at: NOW - 5_000 }), NOW)).toBe(
      "make-feature · done · just now",
    );
  });

  it("scales to hours and days", () => {
    expect(formatRunLabel(row({ started_at: NOW - 3 * 3_600_000 }), NOW)).toBe(
      "make-feature · done · 3h ago",
    );
    expect(formatRunLabel(row({ started_at: NOW - 2 * 86_400_000 }), NOW)).toBe(
      "make-feature · done · 2d ago",
    );
  });

  it("falls back to 'run' for disk-derived rows whose spec is gone", () => {
    expect(formatRunLabel(row({ spec: null, started_at: NOW - 5_000 }), NOW)).toBe(
      "run · done · just now",
    );
  });

  it("omits the time segment when started_at is missing", () => {
    expect(formatRunLabel(row(), NOW)).toBe("make-feature · done");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npm test -- runLabel`
Expected: FAIL — module `./runLabel` does not exist.

- [ ] **Step 3: Implement**

```ts
// console-ui/src/lib/runLabel.ts
import type { RunRow } from "./api";

const ago = (ms: number): string => {
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
};

/** `make-feature · done · 12m ago` — what a run row is, at a glance. */
export function formatRunLabel(row: RunRow, now = Date.now()): string {
  const kind = row.spec?.kind ?? "run";
  const when = row.started_at ? ` · ${ago(now - row.started_at)}` : "";
  return `${kind} · ${row.status}${when}`;
}
```

- [ ] **Step 4: Run the tests, expect PASS**

Run: `npm test -- runLabel`

- [ ] **Step 5: Wire it into the picker**

In `App.tsx`, import `formatRunLabel` and replace the option label template:

```tsx
{runs.map((row) => (
  <option key={row.run_id} value={row.run_id}>
    {formatRunLabel(row)}
  </option>
))}
```

(Values stay `run_id` — the recorded-run tests select by value and keep passing.)

- [ ] **Step 6: Run the whole suite, expect PASS, commit**

```bash
git add src/lib/runLabel.ts src/lib/runLabel.test.ts src/App.tsx
git commit -m "feat(console-ui): the run picker says what each run was, not its id"
```

---

### Task 4: Header status chip

**Files:**
- Create: `console-ui/src/components/StatusChip.tsx`
- Modify: `console-ui/src/App.tsx` (header, `runStartedAt` state)
- Modify: `docs/superpowers/specs/2026-08-03-console-motion-usability-design.md` (one clarifying phrase — see Step 5)
- Test: `console-ui/src/App.test.tsx`

**Interfaces:**
- Consumes: `useElapsed` from `@/lib/useElapsed` (`(startedAt: number, endedAt: number) => string`).
- Produces: `StatusChip({ live, startedAt, outcome })` with `outcome: "done" | "error" | "stopped" | null`. Used only by App.

- [ ] **Step 1: Write the failing tests**

New `describe` block in `App.test.tsx`:

```tsx
describe("the header status chip", () => {
  it("ticks while the run is live", async () => {
    await launch();
    expect(screen.getByText(/running ·/)).toBeTruthy();
  });

  it("turns into done when the result lands", async () => {
    const { server } = await launch();
    server.emit({ type: "result", subtype: "success", result: "shipped", duration_ms: 10, total_cost_usd: 0 });

    expect(screen.getByText("done")).toBeTruthy();
    expect(screen.queryByText(/running ·/)).toBeNull();
  });

  it("says error when the run dies", async () => {
    const { server } = await launch();
    server.emit({ type: "error", message: "CLINotConnectedError: transport closed" });

    expect(screen.getByText("error")).toBeTruthy();
  });

  it("says stopped after an interrupt", async () => {
    const { user } = await launch();
    await user.click(button("Interrupt the running agent"));

    expect(await screen.findByText("stopped")).toBeTruthy();
  });

  it("shows nothing for a recorded replay", async () => {
    const opened = await open(testCatalog, (s) =>
      s.addRecordedRun({ run_id: "run_old", spec: { kind: "prompt" } }, [
        { type: "result", subtype: "success", result: "old news", duration_ms: 1, total_cost_usd: 0 },
      ]),
    );
    await screen.findByLabelText("Run kind");
    // The runs list lands async — every recorded-run test waits for the picker.
    await waitFor(() =>
      expect(screen.getByLabelText("Open a recorded run")).toBeTruthy(),
    );
    await opened.user.selectOptions(
      screen.getByLabelText("Open a recorded run"), "run_old",
    );
    await screen.findByText(/Viewing a recorded run/);

    expect(screen.queryByText(/running ·/)).toBeNull();
    expect(screen.queryByText("done")).toBeNull();
  });
});
```

- [ ] **Step 2: Run them, expect FAIL** (`npm test -- App.test` — no chip exists)

- [ ] **Step 3: Implement the chip**

```tsx
// console-ui/src/components/StatusChip.tsx
import { useElapsed } from "@/lib/useElapsed";

export type RunOutcome = "done" | "error" | "stopped" | null;

/**
 * The at-a-glance answer to "is it still going?". Deliberately NOT a live
 * region: the elapsed time ticks every second, and announcing that to a screen
 * reader would be noise — the approval bar and alerts carry the urgent states.
 */
export function StatusChip({
  live,
  startedAt,
  outcome,
}: {
  live: boolean;
  startedAt: number;
  outcome: RunOutcome;
}) {
  // (0, 1) when idle: startedAt 0 renders "", endedAt 1 skips the interval.
  const elapsed = useElapsed(live ? startedAt : 0, live ? 0 : 1);
  if (live) {
    return (
      <span className="flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
        <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" aria-hidden />
        running · {elapsed}
      </span>
    );
  }
  if (!outcome) return null;
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs ${
        outcome === "error" ? "border-destructive text-destructive" : "text-muted-foreground"
      }`}
    >
      {outcome}
    </span>
  );
}
```

- [ ] **Step 4: Wire it into App**

In `App.tsx`:
- add state `const [runStartedAt, setRunStartedAt] = useState(0);`
- in `launch()`, next to `setRunId(run_id)`: `setRunStartedAt(Date.now());`
- in the header, right after the `<h1>`:

```tsx
{runId && !recorded && (
  <StatusChip
    live={live}
    startedAt={runStartedAt}
    outcome={view.result ? "done" : view.failure ? "error" : stopped ? "stopped" : null}
  />
)}
```

(`openRecorded` already sets `runId` to null, which is what keeps the chip off replays.)

- [ ] **Step 5: Reconcile the spec's wording**

The spec calls the parked pulse "the only looping animation" and also promises a "pulsing dot" in this chip — a contradiction. In the spec file, change the motion-table cell "the only looping animation" to "the only looping **attention** animation (the header status dot is a passive liveness indicator)".

- [ ] **Step 6: Run the whole suite, expect PASS, commit**

```bash
git add src/components/StatusChip.tsx src/App.tsx src/App.test.tsx ../docs/superpowers/specs/2026-08-03-console-motion-usability-design.md
git commit -m "feat(console-ui): the header answers 'is it still running?'"
```

---

### Task 5: Launcher — segmented kind control, captions, Cmd/Ctrl+Enter

**Files:**
- Rewrite: `console-ui/src/components/Launcher.tsx`
- Create: `console-ui/src/components/Launcher.test.tsx`

**Interfaces:**
- Consumes: `Catalog` from `@/lib/types`; `testCatalog` from `@/test/fakeServer` in tests.
- Produces: unchanged public surface — `Launcher({ catalog, busy, busyReason, onLaunch })` and `LaunchSpec = { kind, target, text, mode }`. App needs no edits. Also exports `roleOf(slug: string): string` (slug → human role, `"backend-developer"` → `"backend developer"`).

- [ ] **Step 1: Write the failing tests**

```tsx
// console-ui/src/components/Launcher.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Launcher, roleOf } from "./Launcher";
import { testCatalog } from "@/test/fakeServer";

const mount = (over: Partial<Parameters<typeof Launcher>[0]> = {}) => {
  const onLaunch = vi.fn();
  render(
    <Launcher catalog={testCatalog} busy={false} busyReason={null} onLaunch={onLaunch} {...over} />,
  );
  return { onLaunch, user: userEvent.setup() };
};

describe("roleOf", () => {
  it("turns a slug into a human role", () => {
    expect(roleOf("backend-developer")).toBe("backend developer");
  });
});

describe("the launcher explains itself", () => {
  it("captions the selected kind, and follows a switch", async () => {
    const { user } = mount();
    expect(screen.getByText(/task in your own words/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Command" }));
    expect(screen.getByText(/pack's slash commands/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Command" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Freeform" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("lists specialists by name and role, coordinator excluded", async () => {
    const { user } = mount();
    await user.click(screen.getByRole("button", { name: "Specialist" }));

    expect(
      screen.getByRole("option", { name: "Adam — backend developer" }),
    ).toBeTruthy();
    expect(screen.queryByRole("option", { name: /Emre/ })).toBeNull();
  });

  it("captions the selected permission mode", async () => {
    const { user } = mount();
    expect(screen.getByText(/Asks before edits and commands/)).toBeTruthy();

    await user.selectOptions(screen.getByLabelText("Permission mode"), "plan");
    expect(screen.getByText(/changes nothing/)).toBeTruthy();
  });
});

describe("Cmd/Ctrl+Enter", () => {
  it("launches from the text field", async () => {
    const { onLaunch, user } = mount();
    await user.type(screen.getByPlaceholderText("describe the task"), "ship it");
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(onLaunch).toHaveBeenCalledWith({
      kind: "prompt", target: "", text: "ship it", mode: "default",
    });
  });

  it("does nothing while a run is live", async () => {
    const { onLaunch, user } = mount({ busy: true, busyReason: "A run is in flight" });
    await user.type(screen.getByPlaceholderText("describe the task"), "ship it");
    await user.keyboard("{Control>}{Enter}{/Control}");

    expect(onLaunch).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run them, expect FAIL** (`npm test -- Launcher` — no `roleOf`, no segmented buttons)

- [ ] **Step 3: Rewrite Launcher.tsx**

```tsx
// console-ui/src/components/Launcher.tsx
import { useState } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Catalog } from "@/lib/types";

export type LaunchSpec = { kind: string; target: string; text: string; mode: string };

const KINDS = [
  { value: "prompt", label: "Freeform", caption: "Give the Guild a task in your own words." },
  { value: "command", label: "Command", caption: "Run one of the pack's slash commands." },
  { value: "specialist", label: "Specialist", caption: "Send a task straight to one specialist." },
] as const;

const MODES = [
  { value: "default", label: "Ask me", caption: "Asks before edits and commands." },
  { value: "acceptEdits", label: "Accept edits", caption: "Edits land without asking." },
  { value: "plan", label: "Plan only", caption: "Plans only, changes nothing." },
] as const;

/** "backend-developer" → "backend developer" — the catalog's slug IS the role. */
export const roleOf = (slug: string) => slug.replace(/-/g, " ");

export function Launcher({
  catalog,
  busy,
  busyReason,
  onLaunch,
}: {
  catalog: Catalog;
  busy: boolean;
  /** Shown next to the disabled Run button — never refuse a press silently. */
  busyReason: string | null;
  onLaunch: (spec: LaunchSpec) => void;
}) {
  const [kind, setKind] = useState<string>("prompt");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<string>("default");

  const targets =
    kind === "command"
      ? catalog.commands.map((command) => ({ value: command.slug, label: `/${command.slug}` }))
      : kind === "specialist"
        ? catalog.agents
            .filter((agent) => agent.stage !== null)
            .map((agent) => ({ value: agent.slug, label: `${agent.name} — ${roleOf(agent.slug)}` }))
        : [];

  const kindCaption = KINDS.find((entry) => entry.value === kind)?.caption ?? "";
  const modeCaption = MODES.find((entry) => entry.value === mode)?.caption ?? "";

  return (
    <form
      className="mb-4 space-y-2 rounded-xl border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return; // implicit submission must not sneak past the disabled button
        onLaunch({ kind, target, text, mode });
      }}
      onKeyDown={(event) => {
        // Cmd/Ctrl+Enter runs from anywhere in the form; the submit handler
        // still holds the busy gate.
        if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
          event.preventDefault();
          event.currentTarget.requestSubmit();
        }
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Run kind" className="flex gap-0.5 rounded-lg border p-0.5">
          {KINDS.map((entry) => (
            <Button
              key={entry.value}
              type="button"
              size="sm"
              variant={kind === entry.value ? "default" : "ghost"}
              aria-pressed={kind === entry.value}
              onClick={() => {
                setKind(entry.value);
                setTarget("");
              }}
            >
              {entry.label}
            </Button>
          ))}
        </div>

        {targets.length > 0 && (
          <label className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">
              {kind === "command" ? "Command" : "Specialist"}
            </span>
            <select
              aria-label="Target"
              className="h-9 max-w-56 rounded-md border bg-background px-2 text-sm"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              required
            >
              <option value="">Choose…</option>
              {targets.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <select
          aria-label="Permission mode"
          className="ml-auto h-9 rounded-md border bg-background px-2 text-sm"
          value={mode}
          onChange={(event) => setMode(event.target.value)}
        >
          {MODES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>

        <Button type="submit" disabled={busy} title={busy ? (busyReason ?? undefined) : undefined}>
          <Play className="mr-1 size-4" aria-hidden /> Run
        </Button>
      </div>

      <Input
        className="w-full"
        placeholder={kind === "command" ? "arguments (optional)" : "describe the task"}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />

      <p className="text-xs text-muted-foreground">
        {kindCaption} {modeCaption} <kbd className="rounded border px-1">⌘↵</kbd> to run.
      </p>

      {busy && busyReason && (
        <p className="text-xs text-muted-foreground">{busyReason}</p>
      )}
    </form>
  );
}
```

Note: `screen.getByLabelText("Run kind")` in App.test's `launch()` helper now resolves to the `role="group"` div via its aria-label — same query, new element, still awaits the catalog render.

- [ ] **Step 4: Run Launcher tests, expect PASS** (`npm test -- Launcher`)

- [ ] **Step 5: Run the whole suite**

Run: `npm test`
Expected: PASS. Watch specifically: "refuses a second launch while a run is live" (typed `{Enter}` in the text field still submits implicitly and is still swallowed by the busy gate — native form submit on Enter-in-input is unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/components/Launcher.tsx src/components/Launcher.test.tsx
git commit -m "feat(console-ui): a launcher that explains itself, and Cmd+Enter to run"
```

---

### Task 6: Transcript slide-over (`LanePanel`)

**Files:**
- Create: `console-ui/src/components/LanePanel.tsx`
- Modify: `console-ui/src/components/ui/sheet.tsx` (additive `showOverlay` prop)
- Modify: `console-ui/src/App.tsx` (replace the below-board section; clear selection when a prompt arrives)
- Test: `console-ui/src/App.test.tsx`

**Interfaces:**
- Consumes: `fadeRise` from Task 1; `Sheet`/`SheetContent`/`SheetHeader`/`SheetTitle`/`SheetDescription` from `@/components/ui/sheet`; `Transcript`.
- Produces: `LanePanel({ lane, agent, onClose }: { lane: Lane; agent?: Agent; onClose: () => void })`. Used only by App.

- [ ] **Step 1: Write the failing tests**

New `describe` block in `App.test.tsx`:

```tsx
describe("the transcript panel", () => {
  const start = (agent: string, toolUseId: string, task: string) => ({
    type: "agent_start", agent, tool_use_id: toolUseId, lane_id: toolUseId, task,
  });

  it("slides over the board and closes on Escape", async () => {
    const { server, user } = await launch();
    server.emit(start("backend-developer", "t1", "add the export job"));

    await user.click(button("Adam: add the export job"));
    expect(await screen.findByRole("heading", { name: "Adam" })).toBeTruthy();

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull(),
    );
  });

  it("keeps the board clickable: another card swaps the panel in place", async () => {
    const { server, user } = await launch();
    server.emit(start("backend-developer", "t1", "add the export job"));
    server.emit(start("qa-engineer", "t2", "cover it with tests"));

    await user.click(button("Adam: add the export job"));
    await screen.findByRole("heading", { name: "Adam" });

    // Non-modal by design — the board must stay reachable behind the panel.
    await user.click(button("Dina: cover it with tests"));
    expect(await screen.findByRole("heading", { name: "Dina" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull();
  });

  it("yields to an arriving decision", async () => {
    const { server, user } = await launch();
    server.emit(start("backend-developer", "t1", "add the export job"));
    await user.click(button("Adam: add the export job"));
    await screen.findByRole("heading", { name: "Adam" });

    server.emit(approval("p1", "backend-developer"));

    // The decision sheet opens; the panel steps aside so exactly one overlay
    // ever owns the screen.
    expect(await screen.findByText("Allow Bash?")).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull(),
    );
  });
});
```

- [ ] **Step 2: Run them, expect FAIL** (`npm test -- App.test` — clicking a second card is blocked / panel is a below-board section, no swap-close semantics)

- [ ] **Step 3: Add `showOverlay` to the sheet**

In `ui/sheet.tsx`, extend `SheetContent`'s props with `showOverlay = true` and render the backdrop conditionally:

```tsx
function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  showOverlay = true,
  ...props
}: SheetPrimitive.Popup.Props & {
  side?: "top" | "right" | "bottom" | "left"
  showCloseButton?: boolean
  showOverlay?: boolean
}) {
  return (
    <SheetPortal>
      {showOverlay && <SheetOverlay />}
      …existing Popup unchanged…
```

- [ ] **Step 4: Implement LanePanel**

```tsx
// console-ui/src/components/LanePanel.tsx
import { motion } from "motion/react";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { fadeRise } from "@/lib/motion";
import { Transcript } from "./Transcript";
import type { Agent, Lane } from "@/lib/types";

/**
 * A lane's transcript as a slide-over instead of a below-the-fold section.
 * Non-modal on purpose: reading one agent must not lock the board — clicking
 * another card swaps this panel's content, and an arriving decision sheet
 * (which IS modal) takes the screen. App closes this one when that happens.
 */
export function LanePanel({
  lane,
  agent,
  onClose,
}: {
  lane: Lane;
  agent?: Agent;
  onClose: () => void;
}) {
  return (
    <Sheet open modal={false} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        showOverlay={false}
        className="w-full data-[side=right]:sm:max-w-md"
      >
        <motion.div {...fadeRise} className="flex min-h-0 flex-1 flex-col">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <span
                className="grid size-6 shrink-0 place-items-center rounded text-[10px] font-bold text-white"
                style={{ background: agent?.color ?? "#64748b" }}
              >
                {(agent?.name ?? lane.slug).slice(0, 2)}
              </span>
              {agent?.name ?? lane.slug}
            </SheetTitle>
            <SheetDescription className="truncate">
              {lane.task || "working…"}
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 px-4 pb-4">
            <Transcript events={lane.events} />
          </div>
        </motion.div>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 5: Rewire App**

In `App.tsx`:
- in `onEvent`, extend the prompt case: `if (event.type === "prompt") { setSheetOpen(true); setSelected(null); }`
- derive the live lane and replace the old `{selected && <section>…</section>}` block:

```tsx
const selectedLane = selected
  ? view.lanes.find((lane) => lane.toolUseId === selected.toolUseId) ?? null
  : null;
…
{selectedLane && (
  <LanePanel
    lane={selectedLane}
    agent={catalog.agents.find((a) => a.slug === selectedLane.slug)}
    onClose={() => setSelected(null)}
  />
)}
```

Remove the now-unused `Transcript` import from App (it lives in LanePanel and FocusRun).

- [ ] **Step 6: Run the whole suite**

Run: `npm test`
Expected: PASS, including the three existing tests that click a card and read a heading ("marks the blocked agent's own card…", "still opens its transcript…"). If one of those fails **only** because the heading now mounts in a portal a tick later, apply the Global-Constraints allowance: make that single query `await screen.findByRole(…)`.

- [ ] **Step 7: Commit**

```bash
git add src/components/LanePanel.tsx src/components/ui/sheet.tsx src/App.tsx src/App.test.tsx
git commit -m "feat(console-ui): the transcript slides over the board instead of hiding below it"
```

---

### Task 7: Decision sheet — queue position, entrance, textarea adjacency, JSON key tint

**Files:**
- Modify: `console-ui/src/components/DecisionSheet.tsx`
- Modify: `console-ui/src/App.tsx` (pass `queueLength`)
- Test: `console-ui/src/components/DecisionSheet.test.tsx` (pure helper) and `console-ui/src/App.test.tsx` (queue indicator)

**Interfaces:**
- Consumes: `fadeRise` from Task 1.
- Produces: `DecisionSheet` gains a required prop `queueLength: number`; exports pure `splitJsonKey(line: string): { key: string | null; rest: string }`.

- [ ] **Step 1: Write the failing tests**

In `DecisionSheet.test.tsx` add:

```tsx
import { splitJsonKey } from "./DecisionSheet";

describe("splitJsonKey", () => {
  it("splits a key line into its key prefix and the rest", () => {
    expect(splitJsonKey('  "command": "ls -la"')).toEqual({
      key: '  "command":',
      rest: ' "ls -la"',
    });
  });

  it("leaves braces and bare lines untouched", () => {
    expect(splitJsonKey("{")).toEqual({ key: null, rest: "{" });
    expect(splitJsonKey("}")).toEqual({ key: null, rest: "}" });
  });
});
```

In `App.test.tsx`, inside `describe("a queue of approvals", …)`:

```tsx
it("tells the user where they are in the queue", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.emit(approval("p2", "qa-engineer", "Write"));

    expect(await screen.findByText("Decision 1 of 2")).toBeTruthy();
});

it("drops the counter when only one decision remains", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));

    await screen.findByText("Allow Bash?");
    expect(screen.queryByText(/Decision 1 of/)).toBeNull();
});
```

- [ ] **Step 2: Run them, expect FAIL** (no `splitJsonKey` export, no counter)

- [ ] **Step 3: Implement**

In `DecisionSheet.tsx`:

Add the pure helper next to `mergeFreeText`:

```tsx
/**
 * `"key": value` → the key prefix and the rest, so the pre block can mute the
 * keys without a highlighting library. Pure and exported for the same reason
 * mergeFreeText is.
 */
export function splitJsonKey(line: string): { key: string | null; rest: string } {
  const match = /^(\s*"[^"]+":)(.*)$/.exec(line);
  return match ? { key: match[1], rest: match[2] } : { key: null, rest: line };
}
```

Add `queueLength: number` to the props. Under `<SheetTitle>`:

```tsx
{queueLength > 1 && (
  <SheetDescription>Decision 1 of {queueLength}</SheetDescription>
)}
```

Wrap each branch's body div (`<div className="space-y-5 py-4">` / `<div className="space-y-4 py-4">`) in a `motion.div {...fadeRise}` (import `motion` from `"motion/react"`, `fadeRise` from `"@/lib/motion"`) — the component remounts per `prompt_id`, so mount IS the queue-advance transition; the gate's arm-after-remount timing is untouched.

Replace the `<pre>` contents:

```tsx
<pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs leading-relaxed">
  {JSON.stringify(pending.input, null, 2).split("\n").map((line, index) => {
    const { key, rest } = splitJsonKey(line);
    return (
      <div key={index}>
        {key && <span className="text-muted-foreground">{key}</span>}
        {rest}
      </div>
    );
  })}
</pre>
```

Reorder both branches so the textarea sits directly **above** its buttons, with a caption; placeholders stay byte-identical. Tool branch becomes: pre → textarea → caption → buttons row, where the caption is:

```tsx
<p className="text-xs text-muted-foreground">
  Sent to the agent with a denial — or use it to say what to do instead.
</p>
```

Question branch becomes: questions → textarea → caption → buttons row, caption:

```tsx
<p className="text-xs text-muted-foreground">
  A freeform reply here is sent by "Reply in my own words" instead of the options.
</p>
```

In `App.tsx`, pass the new prop: `<DecisionSheet … queueLength={queue.length} />`.

- [ ] **Step 4: Run the whole suite**

Run: `npm test`
Expected: PASS — existing sheet tests query by placeholder and button name, both preserved; `findByText("Allow Bash?")` still matches because the counter is a separate `SheetDescription` node, not part of the title text.

- [ ] **Step 5: Commit**

```bash
git add src/components/DecisionSheet.tsx src/components/DecisionSheet.test.tsx src/App.tsx src/App.test.tsx
git commit -m "feat(console-ui): the decision sheet says where you are in the queue"
```

---

### Task 8: Full verification, committed bundle, changelog

**Files:**
- Modify: `scripts/console/dist/**` (build output)
- Modify: `CHANGELOG.md` (repo root)

**Interfaces:**
- Consumes: everything above.
- Produces: a dist/ that CI's bundle-in-sync gate accepts, built on Node 22.

- [ ] **Step 1: Full test + typecheck**

Run: `npm test` then `npx tsc --noEmit`
Expected: all green. Fix anything before proceeding.

- [ ] **Step 2: Rebuild the committed bundle on the blessed Node**

```bash
node --version        # if not v22.x:
nvm use               # reads .nvmrc at the repo root
npm run build         # tsc --noEmit && vite build → ../scripts/console/dist
git -C .. status scripts/console/dist
```

Expected: dist/ changed (new bundle). If `node --version` cannot be switched to 22, STOP and say so rather than committing a bundle CI will reject.

- [ ] **Step 3: Smoke it for real**

From the repo root, launch the console the way a user does (`/laravel-team:console`, or `python3 scripts/console/server.py` if headless) and eyeball: launcher captions switch, a run's banners animate, the chip ticks, a card opens the slide-over, Escape closes it.

- [ ] **Step 4: Changelog entry**

Under a new `## [Unreleased]` section (or the existing one) in `CHANGELOG.md`, following the file's Keep-a-Changelog voice:

```markdown
## [Unreleased]

### Changed

- **The console moves like one thing now.** A single motion vocabulary
  (`console-ui/src/lib/motion.ts`) drives every transition: banners and the
  final answer fade-rise instead of teleporting, a parked lane breathes its
  agent's color (the only looping attention animation — and a static colored
  border under `prefers-reduced-motion`), and the approval-queue badge pops
  when it grows.
- **The launcher explains itself.** A segmented Freeform / Command /
  Specialist control with a live caption, specialists listed by name and
  role, permission modes captioned in plain words, and Cmd/Ctrl+Enter to run.
- **The transcript is a slide-over, not a footnote.** Selecting a card opens
  a non-modal right panel — the board stays clickable, Escape dismisses, and
  an arriving decision sheet takes precedence.
- **Smaller answers to constant questions.** A header chip answers "is it
  still running?" with a ticking elapsed time; the run picker says
  `make-feature · done · 12m ago` instead of a raw run id; the decision sheet
  says "Decision 1 of 3" when a queue is waiting.
```

- [ ] **Step 5: Commit**

```bash
git add ../scripts/console/dist ../CHANGELOG.md
git commit -m "build(console-ui): rebuild the committed bundle; changelog for the motion upgrade"
```
