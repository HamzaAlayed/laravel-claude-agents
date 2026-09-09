# Design — Guild 3.1 SDLC / Scrum kernel

**Status:** approved 2026-09-09. Minor on 3.0.0. Adopter-facing: a story cannot `plan` without light DoR; a sprint (optional) owns Goal, WIP, and attached deliveries as kernel state. Files under `docs/sprints/` that are the board are views.

**Goal:** The Guild respects SDLC and Scrum Guide 2020 with two clocks — a **sprint** owns many **deliveries** — without turning `/make-feature Tag --api` into a fake two-week ceremony. The same rules apply to adopter Laravel apps and to this pack.

**Why a minor:** 3.0 already made `VERIFIED` a command exit 0 and the delivery board a view of `kernel.json`. 3.1 extends that kernel (`scripts/guild-kernel/`, one CLI) so DoR / DoD / Sprint Goal / WIP cannot be outranked by coordinator prose. Not a new package. Not nested deliveries.

VERSION stays **3.0.0** in the design and plan commits. Bump to **3.1.0** only after local gates (kernel units, guardrails, inventory). No billed `feature` pin.

## Locked choices

| Question | Choice |
| --- | --- |
| Whose lifecycle | **Both** — adopter delivery and this repository |
| Clocks | **Two kernel objects** — sprint owns many deliveries |
| Enforcement | **Kernel rules** — markdown boards are views |
| Solo `/make-feature` | **Sprint optional; light DoR always** |
| Shape | **A — extend `guild.py`** |

Default `/make-feature` stays Supervisor. Adaptive stays opt-in. Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_kernel_state`. Compounding-company (old 3.1 theme) waits.

## Roadmap (this program)

| Release | Theme | This design? |
| --- | --- | --- |
| **3.0.0** | Kernel + Laravel truth | Shipped. |
| **3.1.0** | SDLC / Scrum kernel | **Yes.** |
| Later | Compounding company, `/pair`, workplace | No. |

## Architecture

One Python kernel, two objects.

- **Delivery** stays `docs/delivery/<name>/kernel.json` — stages, cap, skip, command-backed `VERIFIED`. `/make-feature` still Supervises one story.
- **Sprint** is `docs/sprints/<id>/sprint.json` — `id`, `goal`, `wip`, `stories[]` (delivery names), `status` (`running` / `done` / `stopped`). Created only when someone starts a sprint (`/sprint` or `guild.py sprint start`).
- **Light DoR** is always on `plan`: nonempty `done_when`, and every stage has at least one `success_criteria` item. Fail → no `kernel.json` write. Solo Tag `--api` still works; it cannot `plan` a board with empty criteria.
- **DoD** is delivery `status=done`: every non-skipped stage has ≥1 `verified` command with exit 0, and no success criterion was listed in that stage’s `NOT-CHECKED` (already a 3.0 `report` reject).
- **Join:** if exactly one sprint is `running`, `plan` attaches the delivery to it (explicit `--sprint <id>` or implicit). WIP full or unknown/done sprint id → reject. Zero running sprints → `plan` is 3.0 plus light DoR. Two or more running sprints → reject until `close` leaves one.
- **Views:** kernel still renders `close.md`. Sprint kernel renders `docs/sprints/<id>/sprint.md` (GOAL / WIP / BOARD / STATUS) beside `sprint.json` so retro files are not hooked. Coordinator does not compose either file. Petra/Hana do not invent sprint state in the board file.
- **This repo** runs a real sprint for 3.1 implementation work. Adopter apps do not have to.
- **Ship as 3.1.0.** Additive CLI + Interface sentences. Commands 14 → 15 (`/sprint`).

YAGNI: no RICE in JSON, no Monte Carlo in the kernel, no Linear write. Tracker MCP stays Hana/Petra’s read path.

## Components

Stay inside `scripts/guild-kernel/` (already copied by `install.sh`).

- **`plan` light DoR** — `done_when` nonempty; every stage has ≥1 criterion. Empty → `PlanError` / `SystemExit`, no file write.
- **`report` DoD** — do not set delivery `status=done` unless every non-skipped stage has nonempty `verified` with exit 0. A criterion in `NOT-CHECKED` already rejects the stage.
- **Sprint CLI** — `guild.py sprint start|board|status|close`. `plan --sprint <id>` optional. `sprint next` prints `STOP` or a delivery **name** that is still `running` and under WIP — it does not pick specialists; delivery `next` still does that.
- **`Delivery.sprint`** — optional id string on `kernel.json` (missing key loads as `""` so 3.0 files still `load`).
- **Sprint view** — `write_sprint_view` → `docs/sprints/<id>/sprint.md`. Hook: clone close-file helper-shape on that path (four labels at line start). Bash write deny. Retro stays `docs/sprints/<id>/retro.md` (unhooked). Backlog/roadmap stay Hana files, not kernel JSON.
- **`/sprint`** — 15th workflow command. Emre/Petra/Hana call the sprint CLI. Standup summaries and retro essays are specialist files; not kernel JSON.
- **Interface** — one extra sentence on the nine pipeline commands (still byte-identical): `plan` must carry `done_when` and per-stage criteria; if a sprint is running, attach. Never compose `docs/sprints/<id>/sprint.md`. Coordinator Working interface matches. Gemini / Codex rebuild in the same Interface change.
- **Unchanged** — agents 18, Adaptive opt-in, `/console` as viewer, `check_subagent_log` commented, ceilings untouched.

## Data flow

**Solo delivery (no sprint)** — `/make-feature Tag --api` plus light DoR:

1. Coordinator supplies testable `done_when` and stages with criteria.
2. `plan` validates DoR → `kernel.json` + `close.md`. Reject → numbered options, no Agent.
3. `next` → Agent → stage file → `report`.
4. Repeat until `next` is `STOP`. Harvest unchanged.

**Sprint on:**

1. `sprint start --id <id> --goal "…" --wip N`. Renders `sprint.md`. Status `running`. A second `start` while one is running is a no-op (does not reset stories or WIP).
2. Attaching a story is `plan --name <story> --sprint <id> …` or implicit attach when exactly one sprint is running. WIP = count of attached deliveries with `status=running`. At cap → `plan` rejects.
3. Delivery `next` / `report` unchanged. Sprint `board` lists attached stories as `✔/▶/·/✖` from each `kernel.json`.
4. Delivery `done` → sprint view refreshes. Sprint `close` only if every attached story is `done` or `stopped`, unless `--force` → sprint `stopped`.
5. Resume: existing `kernel.json` still no-ops `plan`. Existing running `sprint.json` still no-ops `sprint start`.

**This pack:** start sprint `3.1` with goal “SDLC/Scrum kernel.” Each implementation slice is a `plan --sprint 3.1` story.

## Error handling

| Case | Behavior |
| --- | --- |
| `plan` with empty `done_when` or a stage with no criteria | Reject. No `kernel.json` write. |
| `report` with a criterion in `NOT-CHECKED` | Unchanged 3.0: reject, lane stays `▶`. |
| Delivery would go `done` with a done stage that has no `verified` exit 0 | Reject. Stay `running`. |
| `plan` while a sprint is `running` and WIP is full | Reject. Sprint `board` printed. No new `kernel.json`. |
| `plan --sprint` id missing / `done` / `stopped` | Reject. |
| Two+ `running` sprints | Any attaching `plan` rejects until one `close`. |
| `sprint start` when one sprint is already `running` | No-op (load + rewrite view). |
| `sprint close` with a story still `running` | Reject unless `--force` → sprint `stopped`. |
| Coordinator Writes `close.md` or `docs/sprints/<id>/sprint.md` as a journal | Hook bounce. |
| Direct invoke, no delivery slug | No kernel, no sprint. Unchanged. |
| `/make-feature` with no sprint on disk | Solo path + light DoR. Not an error. |
| Petra/Hana Write a sprint **board** that disagrees with `sprint.json` | Ignored by `next`/`plan`. They persist retro/backlog other files. |

## Testing

Local only. No billed pin to ship 3.1. Do not loosen `check_kernel_state`.

- **Kernel units** — TDD in `tests/kernel/`: DoR reject; criteria still write; DoD on delivery `done`; `sprint start` + helper view; second start no-op; attach / WIP / missing sprint; solo `plan` with zero running sprints; implicit attach when one running; two running → reject; `close` vs `--force`.
- **Guardrails** — Interface still one unique blockquote across **9** pipeline commands. New sentence inside that block. Coordinator needles count **1** per new clause. Sprint-view hook tests next to close-file. Command count **15** in inventory + manifests + README. Gemini commands: 12 stays 12 unless `/sprint` is added to the Gemini builder list — **add it** (13) or document skip; prefer add so Cursor/Claude/Gemini share the command.
- **CI** — existing `kernel-python` job. No new billed job.
- **Eval** — default `feature` stays Tag `--api` with light DoR on `plan`. Do not plant a sprint. No `feature-sprint` case in 3.1.

## Inventory

- Agents **18**. Commands **15** (`/sprint`). Skills **8**. Guardrails **7** plus sprint-view hook (**8**) if we add a sibling script (prefer sibling `enforce-sprint-file.sh` so close tests stay boring). Codex hook count follows the generator (close-file analogue). Gemini commands **13** if `/sprint` is included.
- Rebuild Gemini and Codex in the Interface change.
- `scripts/check_inventory_sync.py` CLAIMS must move with the counts.

## Non-goals (3.1)

- Compounding company / auto-teach
- `/pair`, trace-replay evals, console as control plane
- Nested deliveries (rejected shape B)
- `scripts/guild-sprint/` second package (rejected shape C)
- RICE / WSJF / Monte Carlo in the kernel
- Linear/Jira as source of truth
- Adaptive as default
- Uncomment `check_subagent_log`
- Raise ceilings
- New default agent
- Billed `feature` or `feature-sprint` pin

## Versioning

| Field | 3.1.0 |
| --- | --- |
| Semver | Minor — additive kernel commands and Interface sentence |
| Adopter action | Plugin update. Solo `/make-feature` must pass light DoR. Optional `/sprint`. |
| Do not bump | In the design or plan commit. Bump after local gates GREEN. |
