# Design — Guild 3.2 craft layer

**Status:** approved 2026-09-22. Minor on 3.1.0. Adopter-facing: a repeated `FLAGS` line becomes a taught lesson the next `plan` must print; `/pair` can hold one stage until a reviewer command exits 0. `feature-replay` is opt-in and is not a ship gate.

**Goal:** The next delivery is better because the kernel remembered a lesson, an optional pair can review one stage, and a replay case can prove a planted violation did not recur.

**Why a minor:** 3.1 already made DoR, DoD, and sprints kernel rules. 3.2 extends the same `guild.py` so lessons and pair waits cannot be outranked by coordinator prose. Not a new package. Not a new agent. Not a default ceremony on `/make-feature`.

VERSION stays **3.1.0** in the design and plan commits. Bump to **3.2.0** only after local gates (kernel units, guardrails, inventory). No billed `feature-replay` pin.

## Locked choices

| Question | Choice |
| --- | --- |
| What compounds | A `FLAGS` line that is not `none`, seen on a second delivery |
| Where it lives | `docs/team/lessons.json` is truth. `lessons.md` is a kernel view |
| Human rules | `/teach` still owns `docs/team/conventions.md`. The kernel does not rewrite it |
| Who sees the lesson | `plan` prints `RULES:` for every taught lesson whose scope includes a stage agent |
| Pair | Explicit `/pair` only. A flag does not auto-insert a reviewer |
| Proof | Opt-in `feature-replay`. Same ceilings as `feature`. Not in the default sweep |
| Shape | Extend `guild.py` |

Default `/make-feature` stays Supervisor. Adaptive stays opt-in. Do not raise `EVAL_TIMEOUT` (1200), `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_kernel_state`.

## Roadmap (this program)

| Release | Theme | This design? |
| --- | --- | --- |
| **3.0.0** | Kernel + Laravel truth | Shipped. |
| **3.1.0** | SDLC / Scrum kernel | Shipped. |
| **3.2.0** | Craft layer (lessons, `/pair`, replay) | **Yes.** |
| Later | Workplace (console as control plane, tracker intake) | No. |

## Architecture

One Python kernel, three additions.

- **Lessons.** `report` stores each real flag on the stage. The second delivery that cites the same normalized text marks the lesson `taught`. The kernel renders `docs/team/lessons.md`. `plan` prints `RULES:` and records what it printed on the delivery. The coordinator does not write `lessons.json` or `lessons.md`.
- **Pair.** `/pair` marks one stage with a reviewer. After the writer reports, the lane stays `▶` and `next` returns the reviewer. The reviewer's exit 0 marks the lane `✔`. Solo `/make-feature` does not pair.
- **Replay.** Opt-in eval plants a taught lesson and a violation. Pass means the delivery recorded that `plan` printed the rule, and the planted check passed. Local kernel units ship 3.2.

## Components

Stay inside `scripts/guild-kernel/`. Agents **18**. Commands **16**. `/pair` is not a pipeline command and must not carry the Interface blockquote.

- **Lesson store** — `docs/team/lessons.json`: `norm`, first-seen `text`, `scope` (agent types who filed it), `status` (`seen` / `taught`), `deliveries` (names). Identity is normalized text: strip, lowercase, collapse whitespace. `none`, empty, and whitespace are not lessons.
- **View** — `docs/team/lessons.md`. Zero taught lessons: a line `LESSONS: none`. Each taught lesson: `RULE:` (first-seen wording), `SCOPE:`, `STATUS: taught`. A ninth guardrail (`enforce-lessons-file.sh`) bounces a journal Write and a Bash write of that path. `/teach` and `conventions.md` stay as they are.
- **`plan` output** — one stdout line per taught lesson whose scope intersects the board: `RULES: <text>`. No match: `RULES: none`. The same lines are stored on the delivery as `rules_printed` so eval can read kernel state, not a transcript.
- **Pair fields** on `StageSpec`, defaulted so 3.1 `kernel.json` files still load: `flags` `[]`, `pair` `""`, `awaiting_pair` false. Delivery `rules_printed` defaults to `[]`.
- **`guild.py pair --root --name <delivery> --stage <id> [--reviewer tech-lead]`** — sets `pair` on a queued or running stage. Reviewer must be one of the 18 agent types and must not be the stage's own agent. A different reviewer rejects. The same reviewer is a no-op.
- **`next` / `report`** — a running stage with `awaiting_pair` makes `next` return `stage.pair`. `report` matches `stages/<reviewer>.md` to that waiting stage only. Writer verified commands stay; the reviewer's exit-0 commands are appended. The board lane names the reviewer while the writer mark stays `▶`.
- **Interface** — one extra sentence on the nine pipeline commands (still one block): brief every `RULES:` line `plan` printed; never compose `docs/team/lessons.md`. Coordinator Kernel paragraph says that once. Gemini and Codex rebuild in the same change. Gemini commands **14** (16 minus `board` and `console`).
- **`/pair`** — command file with no Interface blockquote. Call the pair CLI. Do not invent a reviewer `next` did not return.

## Data flow

**A lesson, no pair.**

1. `plan` writes `kernel.json` as today, prints `RULES:`, and saves `rules_printed`.
2. The coordinator copies those lines into the specialist brief. It does not write the lesson files.
3. `report` stores each real `FLAGS` line on the stage.
4. First delivery to cite that text: status `seen`. `lessons.md` lists taught lessons only, so a `seen` lesson does not print on the next `plan`.
5. A later delivery citing the same text: status `taught`, view rewritten, next `plan` prints it.

**A pair.**

1. `/pair` while the stage is queued or running sets `pair`. It does not spawn anyone.
2. The writer reports with a command that exited 0. The lane stays `▶`, `awaiting_pair` is set, and the board names the reviewer.
3. `next` returns that reviewer, not the writer and not the next dependent.
4. The reviewer writes `stages/<reviewer>.md`. Exit 0 clears `awaiting_pair` and marks the lane `✔`. Dependents can run.
5. A second `/pair` with the same reviewer is a no-op.

**Replay** does not change this flow. It plants a taught lesson before the run.

## Error handling

A reject leaves the board where it was. Nothing in this table writes `lessons.json` or marks a lane `✔`.

| Case | Behavior |
| --- | --- |
| `FLAGS:` is `none`, empty, or whitespace | No lesson. Report otherwise proceeds. |
| Same flag text again on the same delivery | Stay `seen`. A second delivery promotes `taught`. |
| `lessons.json` missing | `plan` prints `RULES: none`. Not an error. |
| Coordinator writes `docs/team/lessons.md` as a journal | Hook bounce. |
| `/pair` with no delivery, an unknown stage, or a stage already `done` or `skipped` | Reject. No field change. |
| Reviewer unknown, or the same agent as the writer | Reject. |
| `/pair` again with a different reviewer | Reject. The same reviewer is a no-op. |
| Writer reports again while `awaiting_pair` | Reject. The lane stays `▶`. |
| Reviewer file arrives when that stage is not waiting | Reject. |
| Reviewer `VERIFIED` is prose or exits non-zero | Existing `ReportError`. Lane stays `▶` and `awaiting_pair`. |
| Spawn cap hits while a pair is still waiting | `next` is `STOP`, delivery `stopped`. The lane stays `▶`. |
| Direct invoke, no delivery slug | No lesson store and no pair. Unchanged. |

The writer's verified commands stay on the stage when the reviewer's are appended. Definition of done still requires an exit 0.

## Testing

Local only. No billed pin to ship 3.2. Do not loosen `check_kernel_state`.

- **Kernel units** — `FLAGS: none` writes no lesson. First real flag is `seen` and `plan` prints `RULES: none`. Same text on a second delivery is `taught`, the view has `LESSONS` / `RULE` / `SCOPE` / `STATUS`, and `plan` prints that rule and stores `rules_printed`. Same delivery twice stays `seen`. `/pair` sets the reviewer; rejects unknown, self, finished stage, and a different reviewer; same reviewer is a no-op. After the writer reports, the lane stays `▶` and `next` returns the reviewer. Reviewer exit 0 marks `✔` and keeps the writer's verified commands. Prose, non-zero exit, a reviewer file when nobody is waiting, and a second writer report while waiting all reject. Cap hit while waiting stops the delivery. Missing `lessons.json` prints `RULES: none`.
- **Guardrails** — Interface sentence on all **9** pipeline commands. Coordinator needle count **1**. `/pair` has no Interface block. Lessons-file hook: helper write allows, journal write blocks, Bash write blocks.
- **Inventory** — agents **18**, commands **16**, guardrails **9**, gemini commands **14**, Codex hooks **8**. Pin `coordinator_hash` after the Interface edit. `waivers: []`. Note: billed `feature-replay` is not a ship gate. Do not raise ceilings.
- **Eval** — add `feature-replay` to `OPT_IN_CASES` only. Copy the `feature` ceilings (1900s, 14.5M, $8.50). Do not raise `EVAL_TIMEOUT`. The seed writes a taught lesson `Do not call Model::all()` scoped to `backend-developer`. Pass: `rules_printed` contains that text, and no planted PHP file contains `Model::all()`. The check reads the workdir, never the raw transcript. Do not run the case to ship.

## Inventory

- Agents **18**. Commands **16** (`/pair`). Skills **8**. Guardrails **9** (`enforce-lessons-file.sh`). Gemini commands **14**. Codex `*.sh` hooks **8**.
- Rebuild Gemini and Codex in the Interface change.
- `scripts/check_inventory_sync.py` counts move with the files; do not hard-code a second source of truth beyond the existing CLAIMS patterns.

## Non-goals (3.2)

- Workplace / console as control plane / tracker intake
- Auto-pair on every flag
- Kernel writes to `docs/team/conventions.md`
- Billed `feature-replay` as a ship gate
- Uncomment `check_subagent_log`
- Raise ceilings
- New default agent
- Adaptive as default

## Versioning

| Field | 3.2.0 |
| --- | --- |
| Semver | Minor — additive lesson store, `/pair`, Interface sentence |
| Adopter action | Plugin update. `plan` prints `RULES:`. Optional `/pair`. |
| Do not bump | In the design or plan commit. Bump after local gates GREEN. |
