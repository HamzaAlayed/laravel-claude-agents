# Design — Guild console as a company floor (two-act theater)

**Approved 2026-08-19.** Replaces the v1.27–1.43 shadcn-on-white dashboard. Same local console, same Python server, same events.

**Goal:** a brand-new visual identity and UX flow so `/console` feels like a small studio production, not a generic admin app.

**Approach chosen:** two-act console (A). Rejected: one-floor scene changes (still one crowded room) and separate routes (too much reconnect/focus cost for a single-window local tool).

## What the user approved

| Fork | Choice |
| --- | --- |
| What’s wrong | Look **and** flow |
| Home during a run | **Run theater** — start screen, then full-screen pipeline; launcher gone until the run ends |
| Approval interrupt | **Decision takes the stage** — floor dims; you answer in the main canvas |
| Identity | **Company** — studio floor, specialists as a cast, the run is a production |
| Cast | **Keep the existing actor sprites** — restage, don’t redraw |

## Non-goals

- No agent-body, command, or eval-harness edits
- No new HTTP/SSE API, no new permission modes
- No hosted/multi-user console
- No acid-green-on-black, cream-and-serif template, or Geist-on-white shadcn look
- Do not uncomment `check_subagent_log`
- Do not merge `feat/agent-cost-instrument`

## Constraints (keep)

- Loopback + token; Bash still parks
- `reduce`, `submitGate` (one click, one decision), `write_or_drop`
- Sprite hover is **sm-only**; tooltip trigger is a **`span`** (nested-button contract)
- `{n} remaining` hidden at 1; `splitJsonKey` escaped quotes; `ago()` clamps future
- One blessed Node from `.nvmrc`; committed `scripts/console/dist`; `python3 scripts/check_inventory_sync.py` inventory phrases untouched
- `prefers-reduced-motion: reduce` skips house-light dim (hard cut between scenes)

## Two acts

**Act I — Call sheet (`call`).** Full-screen empty floor. One job: start a production. Kind (freeform / command / specialist), target, mode, Start, past shows. No board, no follow-up, no run chrome.

**Act II — Floor (`floor`).** Launcher is gone. Full viewport: BUILD / VERIFY stations, sprites at marks, elapsed time, cue state on parked agents. Header is the show: production title, running/parked/done, Stop. Follow-up is one quiet line (`CueLine`). Click a **non-parked** station → `Sides` (transcript rail). Click a **parked** station → re-enter spotlight (this replaces today’s Review button on the amber bar).

**Spotlight (`spotlight`).** Not a route. Floor stays mounted and dims. Parked sprite + tool/command + Allow / Deny / custom fill the canvas. Queue count `{n} remaining` when n > 1. `submitGate` still lives in `App` and remounts per `prompt_id`. Failed POST restores that prompt and stays in spotlight.

**Recorded runs:** `floor` only, read-only. Prompts never become answerable spotlight. Past shows on the call sheet open recordings.

**After Stop or run over:** back to `call`, with that show in past shows.

## Scene rules

`Scene = "call" | "floor" | "spotlight"`. Not URLs.

| Condition | Scene |
| --- | --- |
| No live run, not viewing a recording | `call` |
| Recording open | `floor` |
| Live run, `spotlightOpen`, at least one unanswered prompt | `spotlight` |
| Live run, otherwise | `floor` |

- First `prompt` event → `spotlightOpen = true`
- Answer with queue remaining → stay in spotlight, next prompt (gate re-arms)
- Last answer, or dismiss without answering → `spotlightOpen = false` (floor). Parked stations still show cue; clicking one sets `spotlightOpen = true`
- Start → `floor`. Stop / `isRunOver` → `call`

Focus restore: dismiss spotlight → `#cue-line` if the floor is up, else `#guild-call-sheet`.

## Look

Daylit rehearsal studio. House lights warm and a bit dusty. Dark floor, plaster walls. The only bright thing is a person.

| Token | Hex | Use |
| --- | --- | --- |
| `plaster` | `#B7AFA4` | Act I ground, walls |
| `floor` | `#2F2C28` | Act II ground |
| `ink` | `#1C1917` | Type on plaster |
| `paper` | `#E6E1D6` | Call sheet, inputs |
| `tungsten` | `#CC8A3A` | Running / live practical |
| `cue` | `#A33B32` | Parked / needs you |

**Type:** Syne extra-bold (production title only), Source Sans 3 (body), IBM Plex Mono (Bash, tools, routes). Drop Geist.

**Signature:** on a decision, house lights drop. The rest of the floor goes dim; one sprite stands in a tungsten cone. No modal, no amber bar.

Stations are marks on the floor, not shadcn cards-in-a-grid. Keep the sprite SVG and pose CSS.

## Components (map from today)

| Today | Tomorrow |
| --- | --- |
| `Launcher` (always on) | `CallSheet` — Act I only |
| Header chip + run picker | `ShowHeader` — Act II only |
| `Board` / `AgentCard` | `Floor` / `Station` |
| `ApprovalBar` | **deleted** |
| `DecisionSheet` (modal) | `Spotlight` — same `buildAnswers` / `splitJsonKey` / `queueLength` |
| `LanePanel` | `Sides` — transcript rail; not used for parked-answer |
| Follow-up composer | `CueLine` |
| `FocusRun` | Keep for single-lane runs, restyled to the floor |

`App.tsx` owns scene + `spotlightOpen` + `submitGate`. Helpers `buildAnswers`, `splitJsonKey`, `armGate` stay; they are safety, not chrome.

## Errors

Catalog or SSE failure: one line on the call sheet (Act I) or show header (Act II), not a toast. Failed Allow: prompt returns to the queue, spotlight stays. Stop lives only in `ShowHeader`.

## Tests and capture

Keep: sprite click-through, no `lg` hover, remaining-count, kind-reset, `splitJsonKey` escaped quotes, `submitGate`.

Add: Start → `floor`; `prompt` → `spotlight`; last answer → `floor`; dismiss → `floor` with cue still on the station; recorded never submits; parked-station click re-opens spotlight.

Rebuild `scripts/console/dist` with `.nvmrc` Node. Recapture `docs/images/console-board-mid-run.png` from Act II (and optionally spotlight), fixture-driven, honest caption. Update README / onboarding image if the board no longer matches.

## Out of this slice

New sprite art, GIF, dark-theme toggle, multi-run theater, changing Bash-always-asks.
