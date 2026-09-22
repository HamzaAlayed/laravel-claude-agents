# Design — Guild 4.0 console desk

**Status:** approved 2026-09-22. Major on 3.3.0. Adopter-facing: `/console` opens on a delivery desk. A delivery can start its Claude run from that desk. A per-delivery watch toggle asks GitHub once a minute and reopens one stage when a check fails or a new review comment appears.

**Goal:** The console is the workplace. The company floor remains the live run.

**Why a major:** 3.3 opens on the call sheet, with a kernel form underneath. 4.0 opens on the deliveries in `kernel.json`. The floor, the spotlight, and the launcher stay. They are no longer the front door.

VERSION stays **3.3.0** in the design and plan commits. Bump to **4.0.0** only after local gates (kernel units, console units, console UI tests, guardrails, inventory, dist rebuild). No billed eval.

## Locked choices

| Question | Choice |
| --- | --- |
| Home | Desk, when no run is active |
| Live run | Floor and spotlight, unchanged |
| Freeform run | Launcher stays, opened from the desk as New run |
| Run a delivery | Existing `POST /api/runs`, kind `command`, target `make-feature`, text `<name>` plus `--issue <n>` when the kernel stored an issue number. Mode `default` |
| Watch | Per delivery, off until toggled on. One tick, one event |
| GitHub | The server runs `gh` through the kernel. The browser cannot send a command or a root |
| Merge | No button. No `gh pr merge`. No `gh pr create` |
| Poll | Only watched deliveries that already have a recorded pull request |

Default `/make-feature` stays Supervisor. Adaptive stays opt-in. Do not raise `EVAL_TIMEOUT` (1200), `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`.

## Architecture

Same kernel, same console process.

- **List.** `GET /api/kernel/deliveries` reads `docs/delivery/*/kernel.json` under `os.getcwd()`. A directory whose name fails `^[A-Za-z0-9][A-Za-z0-9_-]*$` is skipped. Each row is `name`, `status`, `done_when`, `issue` url, `pr` url and state, and the kernel board line. The client supplies no path.
- **Desk.** Replaces the call sheet as the idle scene. `KernelStrip` is removed from the call sheet. Selecting a row shows lanes and the reopen controls that already call `POST /api/kernel/ingest`.
- **Run.** The desk calls the existing launch path. The floor takes over. Approvals stay in the spotlight.
- **Watch.** `POST /api/kernel/watch` with `{name, enabled}` stores the name in process memory. A thread in the console process wakes every 60 seconds and calls `kernel.watch_once` for each enabled name. Turning the console off stops the thread. A delivery with no recorded pull request cannot be watched.
- **`watch_once`.** Loads the delivery. No pull request, delivery `stopped` or `done`, or no `done` stage: return without `gh`. Otherwise run the same check and review commands `ingest` uses. Apply at most one event. Prefer the first failing check whose name is not in `seen_checks`. Otherwise the first review comment id not in `seen_comments`. The target stage is the last `done` writer in board order, else the last `done` stage. While that stage is `running`, return `wait` and do not ingest. A successful reopen appends the check name or comment id. A second event still stops the delivery, and the server then disables watch for that name.
- **Memory.** `Delivery.seen_checks` and `seen_comments` default to `[]` in `load()` so a 3.3 `kernel.json` still loads.

## Data flow

**Open the console.**

1. No run is active. The desk lists deliveries.
2. The user selects one. Lanes, issue, and pull request render from the list payload.
3. New run opens the existing launcher. That path does not watch anything.

**Run this delivery.**

1. The user presses Run on a row named `tag` whose issue number is 42.
2. The console POSTs `{kind: "command", target: "make-feature", text: "tag --issue 42", mode: "default"}`.
3. The floor and spotlight behave as they do in 3.3.

**Watch.**

1. The user turns Watch on for `tag`. The server accepts it only when `pr.number` is set.
2. Every 60 seconds `watch_once` runs. A new failing check reopens the last done writer once.
3. The next tick, while that stage is `running`, does not call `gh`.
4. After the stage is `done` again, a further new failure or comment stops the delivery and the server clears the watch.

## Error handling

| Case | Behavior |
| --- | --- |
| Delivery directory name fails the name regex | Omitted from the list |
| `kernel.json` is unreadable | Omitted from the list. The rest still return |
| Watch with no recorded pull request | 400. Watch stays off |
| Client sends `root` or a `gh` command | Ignored. Root is `os.getcwd()` |
| `gh` exits non-zero | That tick returns an error. Watch stays on. Nothing is reopened |
| Stage is `running` | `wait`. No second ingest |
| Second event on that stage | Delivery `stopped`. Watch turns off |
| No `done` stage | No `gh`. Watch stays on |
| Missing token or non-local Origin | Existing 401 / 403 |

## Testing

Local only. No billed pin to ship 4.0.

- **Kernel.** 3.3 JSON loads with empty `seen_checks` and `seen_comments`. `list` shape is covered by the server test against a temp root. `watch_once` reopens once on a failing check, records the check name, waits while the stage is `running`, and a later new failure stops the delivery. A green check writes nothing. A new comment id reopens when no unseen check is failing. An id already in `seen_comments` does not. No pull request does not call `capture`.
- **Console server.** List ignores a bad directory name and a client `root` query. Watch rejects a delivery with no pull request. Enabling watch records the name. The tick test calls `watch_once` through an injected clock, not a 60 second sleep.
- **UI.** Desk renders rows. Run posts the make-feature spec and does not send `root`. Watch posts `{name, enabled: true}`. Idle scene is the desk. A live run is still the floor. The call sheet no longer mounts `KernelStrip`.
- **Inventory.** Agents **18**, commands **16**, guardrails **9**. No new slash command.

## Non-goals (4.0)

- Opening or merging a pull request
- Polling every delivery while the console is up
- Linear or any tracker besides the issue already stored on the delivery
- Parsing an issue body into stages
- Replacing the floor, the spotlight, or the launcher
- Worktrees, Agent Teams, LangGraph
- A billed eval, uncommenting `check_subagent_log`, raising ceilings

## Versioning

| Field | 4.0.0 |
| --- | --- |
| Semver | Major — the console's front door is the desk |
| Adopter action | Plugin update. Open `/console`. Local `/make-feature` without the desk is unchanged |
| Do not bump | In the design or plan commit. Bump after local gates GREEN |
