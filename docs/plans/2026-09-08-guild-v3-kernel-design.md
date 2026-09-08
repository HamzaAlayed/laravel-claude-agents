# Design — Guild 3.0 kernel + Laravel truth

**Status:** approved 2026-09-08. New program. Not a follow-on to Guild v2 prompt slices. Major. Adopter-facing: `VERIFIED` is a command that exited 0; join / skip / cap / resume are kernel rules a prompt cannot outrank.

**Goal:** A pack-local Python kernel owns delivery state. Specialists still write Laravel. The coordinator still Supervises. Done means the app proved it.

**Why a major:** The 2.x Interface is nine byte-identical encyclopedias plus billed evals that grep labels a model typed. That architecture is exhausted (run 25: join/verify in prose outranked skip). 3.0.0 is a re-install: the board is a view of `kernel.json`; eval’s feature gate is Pest on the planted app.

VERSION stays **2.3.0** until a billed `feature` pin PASSes the 3.0 gate. Do not bump in the design or plan commit.

## Roadmap (this program)

| Release | Theme | This design? |
| --- | --- | --- |
| **3.0.0** | Kernel + Laravel truth | **Yes.** |
| **3.1.0** | Compounding company (auto-teach from FLAGS, mechanical memory retrieval) | No. Unsafe until kernel truth exists. |
| **3.2.0** | Cheap craft (`/pair`, trace-replay evals) | No. |
| **3.3.0** | Workplace (console as control plane, tracker intake) | No. |

Default `/make-feature` stays Supervisor. Adaptive stays opt-in. Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`.

## Evidence (2.3.0)

| Contract | On disk / eval |
| --- | --- |
| Resume skip | [Run 26](../evals/2026-09-04-run-26.md) 14/14 PASS |
| Close print | [Run 23](../evals/2026-09-02-run-23.md) 13/13 PASS |
| `NOT-CHECKED` load-bearing | Still a footnote. Literature gap 1 in [2026-07-29 audit](../research/2026-07-29-agent-literature-audit.md) |
| `VERIFIED` | A line the model types. Feature eval greps the word, then also checks Tag files exist |
| Join / skip / cap | Prompt needles. Run 25 showed skip losing to join/verify |

v2 artifacts (`close.md`, `graph.md`, stage files, `--adaptive`) stay **views or opt-in**. This design does not add more needles for them.

## Architecture

A small **local Python kernel** next to `scripts/console/` (stdlib only, no SaaS, no LangGraph). It is the source of truth for one delivery.

- State file: `docs/delivery/<name>/kernel.json`
- CLI: `python3 scripts/guild-kernel/guild.py <plan|next|report|board|status>`
- Coordinator job: parse the ask, call the kernel, Agent who `next` names, hand the stage file to `report`. It does not invent `✔`.
- Specialist job: write Laravel, run named checks, Write a schema-valid stage file whose `VERIFIED:` lines are commands.
- `close.md` is a **kernel-rendered view** of the same state (four helper labels) so humans and today’s close-file helper still read a file. The coordinator does not compose it.
- `graph.md` remains a plan-time view. The kernel records nodes / edges / parallel / on-fail from the plan. Coordinator must not spawn a type the kernel did not `next`.

Kernel language is Python because the pack already runs Python 3.10+ for `/console` and eval. VERIFIED commands run **in the adopter Laravel workdir** (artisan, pint, phpstan, pest). The kernel shells out there and stores exit codes. It is not an Artisan package inside the app (that is program shape B, rejected).

Nine pipeline commands stay byte-identical, but the Interface **shrinks** to the kernel contract. v2 encyclopedia needles (resume paragraph, skip-beats-join sentence, close-print, graph stub copy, Adaptive persist, …) are replaced by: call the kernel; print `board`; do not Write `close.md` yourself; do not Agent except whom `next` returned.

## Components

- **`scripts/guild-kernel/`** — `guild.py` CLI + state machine. Commands: `plan` (create/update state, cap `M` = stage count + 2), `next` (stdout: agent type or `STOP`), `report` (path to `stages/<agent>.md` — schema + VERIFIED commands + NOT-CHECKED vs that stage’s success criteria), `board` (print header + lanes), `status` (`running` / `done` / `stopped`).
- **Stage schema** — same six labels as `skills/delivery-templates/stage-return.md`. Hook bounces a Write that is not helper shape (extend `enforce-close-file.sh` or a sibling `enforce-stage-return.sh` on `docs/delivery/*/stages/*.md`).
- **Command-backed VERIFIED** — each `VERIFIED:` line is a shell command in the workdir. `report` re-runs it. Exit ≠ 0 → reject, stage stays `▶`. A `VERIFIED:` line that is not a command → reject.
- **Load-bearing NOT-CHECKED** — each stage has enumerated `success_criteria` from `plan`. If a criterion string is listed in `NOT-CHECKED:`, `report` fails the stage (`✖` / re-brief once). Thin verification cannot `✔`.
- **Thin Interface** — all nine pipeline commands. Kernel calls + print board. No copied v2 encyclopedia.
- **Coordinator Working interface** — same kernel calls. Still never writes a **writer’s** stage file. Still persists read-only stage files by copying `stage-return.md` then `report`. Renders close via kernel, not a coordinator-authored heredoc.
- **Eval** — billed `feature` (Tag `--api`). Gate: Tag Pest/HTTP still land **and** `kernel.json` exists **and** every `✔` stage has at least one VERIFIED command with exit 0 in state. `check_delivery_close_file` stays (kernel view). Do not uncomment `check_subagent_log`. Do not grep `stream.jsonl`.
- **Unchanged until 3.1+:** `/teach`, `/console` as viewer, `--adaptive`, agent count 18, command count 14.

## Data flow

1. `/make-feature Tag --api` → coordinator `plan` with `done_when` and stages (Elena → Adam → Dina → Tariq; `--api` skips Bella).
2. `next` → `database-developer`. Coordinator Agent-spawns. Writer Writes code + runs checks + Writes `stages/database-developer.md`.
3. `report` that path. Kernel validates schema, re-runs VERIFIED commands, checks NOT-CHECKED against that stage’s criteria. Pass → mark `✔`, render `close.md`, print `board`. Fail → stay `▶`, re-brief once, second fail → `✖` that lane.
4. Repeat until `next` prints `STOP` (`done when:` met, or cap hit, or a blocking `✖`).
5. Harvest (`docs/team/stack.md`, `docs/delivery/<name>/log.md`) still runs when ≥2 specialists have `✔`. Kernel does not replace harvest files.
6. Resume: second `/make-feature Tag` → `plan` is a no-op if `kernel.json` is `running`. `next` returns only non-skippable stages. Skip is code: writer `✔` with artifacts named in `DID:` still on disk; read-only `✔` from stage file `STATUS: done`. A prompt cannot Agent a skipped type.
7. Direct invoke, no delivery slug: no kernel, no `kernel.json`. Unchanged.

## Error handling

| Case | Behavior |
| --- | --- |
| `VERIFIED:` is prose, not a command | `report` reject. Re-brief once. |
| Named command exit ≠ 0 | `report` reject. Stage stays `▶`. |
| `NOT-CHECKED:` names a success criterion | `report` reject. Lane does not `✔`. |
| Join: dependent `next` while upstream not `✔` | `next` does not name the dependent. |
| Skip vs join | Skip wins in the kernel for that writer. Files `DID:`/`VERIFIED:` did not name are not a skip-breaker. |
| Spawn cap `M` hit, `done when:` unmet | `status` `stopped`. `next` is `STOP`. Render close. |
| `kernel.json` missing on resume | Treat as fresh `plan`. |
| `STATUS: done` / `stopped` | `board` + close view, no Agent. |
| Coordinator Writes `close.md` itself | Hook still bounces non-helper shape. Kernel is the only writer of that path after 3.0. |
| Bash writes `close.md` | Still denied. |
| Direct invoke | No kernel. |

## Testing

**Kernel units (no billed run).** `tests/kernel/` stdlib unittest, same pattern as `tests/console/`. Cover: plan cap, `next` order and joins, skip, command-backed VERIFIED (fake runner), NOT-CHECKED stop, cap → stopped, resume `next` omits skippable writers, `close.md` view has four labels.

**Guardrails.** Replace v2 encyclopedia Interface greps with kernel-contract greps (count **9** on the nine commands). Coordinator needles count **1** per new clause: call `guild.py`, do not compose `close.md`, Agent only `next`. Stage-return hook tests sit next to close-file tests. `check_subagent_log` stays commented.

**Eval.** Gate is billed `KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature`. Same ceilings as today. Pin `coordinator_hash`. `waivers: []`. New helper `check_kernel_state` reads `docs/delivery/tag/kernel.json` — never the raw transcript. Existing Tag file checks stay. PASS → VERSION **3.0.0**. FAIL → pin hash, stay **2.3.0** / Unreleased. Do not run until the user says **run it**.

**CI.** Add kernel unittest job next to `console python units`. Guardrail job already covers hooks.

## Inventory

- Agents still **18**. Commands still **14**. Default sweep still **5** cases. Opt-in cases unchanged (`feature`, `teach`, `teach-delivery`, `feature-adaptive`, `feature-resume`).
- Guardrails: **6** scripts today. 3.0 adds stage-return enforcement (7th script) **or** extends `enforce-close-file.sh` without a new file — prefer a sibling script so close tests stay boring.
- Gemini / Codex rebuild in the same change as the Interface.
- New Python tree must stay in inventory claims (`scripts/check_inventory_sync.py`, README).

## Non-goals (3.0)

- Program shapes B (Composer/Artisan in the app) and C (Studio-first)
- 3.1 auto-teach, 3.2 `/pair` and replay evals, 3.3 console control plane
- LangGraph / Kore SDK / Guild Cloud
- Adaptive as default `/make-feature`
- Uncomment `check_subagent_log`
- Raise `$8.50` / 1200s / 14.5M
- New default agent
- Re-opening Adaptive / graph / close-print / resume as prompt slices (kernel may reimplement their rules)

## Versioning

| Field | 3.0.0 |
| --- | --- |
| Semver | Major — Interface is a kernel contract; `VERIFIED` is a command result |
| Adopter action | Re-install / plugin update. Read the thin Interface. `close.md` is still there as a view. |
| Do not bump | In the design or plan commit. Bump only after billed `feature` PASS |
