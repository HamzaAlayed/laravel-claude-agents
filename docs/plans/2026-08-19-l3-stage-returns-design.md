# Design — Make the Interface loop measurable (L3 stage-return files)

**Approved 2026-08-19.** Deepens L3 on the existing pack. Same product shape: a human starts `/make-feature` or `/console`. No daemon, no new command, no new agent.

**Goal:** The six-field specialist return (`STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT`) becomes a file the specialist writes and the coordinator must Read before `✔`, so evals can assert per-stage calibration without grepping nested chat.

**Why this exists:** [Vellum’s agentic ladder](https://www.vellum.ai/blog/levels-of-agentic-behavior) describes L3 as observe → plan → act → evaluate the last step → next step → shut down. The nine pipeline commands already *write* that loop (stage budget, six-field return, verify-before-advance, harvest, then stop). Billed runs do not prove the specialist half. [Run 10](../evals/2026-08-19-run-10.md): 125 nested assistant turns, every one `tool_use` only, `$SUBAGENT_LOG` empty. [The open corpus item](../README.md#open) is that gap. Prompting harder for a text block will not close it on that stream shape.

**Approach chosen:** persist the return as a file (B). Rejected: keep the return in nested chat and uncomment `check_subagent_log` (A — blocked by run 10), and grep only the coordinator’s board line (C — measures the wrong actor).

## What the user approved

| Fork | Choice |
| --- | --- |
| Product | **Deepen L3** — human-started runs, then stop. Not L4 persistence, not L6 companion |
| Center | **Make the existing Interface loop real and measurable.** No new observe-agent, no capability catalog |
| Return surface | **A file** `docs/delivery/<name>/stages/<agent>.md`, written with Write (a tool nested turns already record) |

## Non-goals

- No new command, agent, console scene, or HTTP/SSE API
- No L4 watcher (GitHub / Slack / CI daemon)
- Do not uncomment `check_subagent_log` on the run-10 shape
- Do not raise `max_usd` (stays **$8.50**)
- Do not merge `feat/agent-cost-instrument` or leftover orchestration-audit worktrees
- Do not invent a second paper trail under `stages/` (history stays in `log.md`)

## Constraints (keep)

- Coordinator Write/Edit only under `docs/**`; never patch a specialist’s app files **or** their stage file
- Harvest still skips when fewer than two specialists have reported
- `full_text()` stays main-thread only (run 7 finding 3). Coordinator close greps `$LOG` / `$FULL_LOG`, never a specialist file
- `checks_*` never grep `stream.jsonl`
- Interface block stays byte-identical across the nine pipeline commands (`coordinator_hash`)
- Gemini / Codex rebuild in the same release

## Architecture — the stage-return file

**Path:** `docs/delivery/<name>/stages/<agent>.md`

- `<name>` is the same slug as harvest’s `docs/delivery/<name>/log.md`
- `<agent>` is the registered type (`backend-developer`), not the human name
- Parallel stages stay on disjoint paths by construction (one file per agent type)

**Who writes:** the specialist, as its last Write before it stops. It does not invent the folder. The pipeline brief names the exact path.

**Who skips:** a direct one-shot invoke with no delivery slug writes nothing here. No orphan `docs/delivery/unknown/`.

**Who reads:** the coordinator must Read that file before it prints `✔`. A missing file, empty `VERIFIED`, or missing `NOT-CHECKED` is the existing gap: re-brief once, naming the fields; twice → stop the lane.

**Single-specialist pipeline:** one stage file is required so verify-before-advance has something to Read. Harvest still skips (`<2`).

**Latest return wins.** A re-brief overwrites the stage file. History lives in `log.md` (append-only).

**Internal.** The human still sees the board. Stage files are calibration, not a new UI.

## Components — where the contract binds

Four surfaces, same placement pattern as harvest (v1.41.0) and verify-before-advancing (v1.42.0): the rule lives where the run actually loads it.

1. **Shared Interface** (nine pipeline commands). One new sentence, byte-identical, in the existing blockquote: the brief names `docs/delivery/<name>/stages/<agent>.md`; a stage without that file is not done; the main thread does not write that file for them.
2. **Specialist bodies** (all 17). Closing clause: when the brief names a stage path, Write that file with the six labels (≤12 lines) as the last Write, then stop. Direct invoke with no path: skip. Same clause in `docs/authoring-agents.md`.
3. **Delivery-coordinator Working interface.** Add the file path to the existing stage-return example. Integrate step: Read the stage file, then re-run success criteria, then `✔`.
4. **`delivery-templates` skill.** One template for the stage file, next to the delivery-log template.

**Guardrails:** `coordinator_hash()` will change when Interface bytes change — billed `feature` re-pin in the same release. Pin that the new Interface sentence is identical across the nine, and that every `agents/*.md` contains the closing clause.

## Data flow — one stage

1. **Plan.** Board with stage budget and `done when:`. Pick `<name>` for harvest and stage files.
2. **Brief.** Goal, owned paths, success criteria, exact stage path. Parallel writers: disjoint app paths; stage files already disjoint by agent name.
3. **Act.** Specialist works. Last Write is the stage file. Stop.
4. **Observe.** Coordinator Reads the file, then re-runs that brief’s success criteria itself. `STATUS: done` is a claim.
5. **Advance or loop.** Pass → `✔`, append `log.md`, next stage (or harvest if ≥2 stage files exist). Fail / missing / uncalibrated → re-brief once; overwrite the same file. Second failure → `✖`, checkpoint. No patching.
6. **Close.** Coordinator’s own `VERIFIED` / `NOT-CHECKED` on the commands *it* ran. Process exits.

Re-plan (budget grew) does not delete existing stage files. Same agent used again overwrites its file; `log.md` keeps the earlier line.

## Error handling

| Case | Response |
| --- | --- |
| Missing stage file | Do not infer from the diff. Re-brief once naming the path. Still missing → `✖` + checkpoint. Do not write it for them. |
| Uncalibrated file | Empty `VERIFIED`, missing `NOT-CHECKED`, or `NOT-CHECKED` covering the brief → re-brief once; twice → stop. Overwrite. |
| Verify failed | File complete, coordinator re-run fails → re-brief once with command output; twice → stop. The file is not proof. |
| Parallel collision on a stage path | Coordinator bug. Stop and re-plan. App-path collisions stay the existing disjoint-paths rule. |
| Direct invoke, no slug | Specialist skips the file. |
| Specialist writes the file then keeps going | Not a runtime kill. Evals require the file before coordinator `✔` / close. No new abort hook. |
| Empty `$SUBAGENT_LOG` | Not an error. Do not fail the run. Do not uncomment `check_subagent_log`. |

## Testing

**Unit / guardrails (no billed run).** Interface sentence identical on all nine commands. Every `agents/*.md` contains the closing clause. `delivery-templates` includes the stage-file template. `checks_*` still must not grep `stream.jsonl`. `check_subagent_log` stays commented.

**Eval answer key (`feature`, opt-in billed).** After an inspected `KEEP_TRANSCRIPT=1` run:

- At least two files matching `docs/delivery/*/stages/*.md` (that case already requires ≥2 agents on the board)
- Each file contains the six labels (grep the **file**, not `$SUBAGENT_LOG`)
- Existing harvest + coordinator close checks unchanged
- Coordinator close still unsatisfiable from a specialist file (grep `$LOG` / `$FULL_LOG` only)

**Release proof.** One billed `feature` re-run pins `coordinator_hash` and is the first live assertion that stage files exist. Answer-key file checks land in the same release as the prompt change.

## Versioning

This is a pack-behavior change (orchestrator + specialists + eval answer key). Treat as **minor** when it ships (next after 1.44.0). Do not bump in the design commit.
