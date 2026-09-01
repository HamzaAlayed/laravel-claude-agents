# Design — Guild 2.2.1 Adaptive hop persist

**Status:** approved 2026-08-31. Follow-up to [2.2.0 graph](2026-08-24-guild-v2-adaptive-graph-design.md) after [v2.2.0](https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v2.2.0) and [run 20](../evals/2026-08-27-run-20.md) / [run 21](../evals/2026-08-27-run-21.md). Patch only. Closes leftovers 1 and 2.

**Goal:** Make `--adaptive` persist `docs/delivery/<name>/stages/peer-router.md` and print a `handoff:` line so the billed Adaptive gate can PASS, and drop the `peer-router` FLAG that spawn requires a writer-named packet.

**Why a patch:** 2.2.0 already shipped default `graph.md` and on-graph hops. Run 20 spawned `peer-router` and Agent-ed `security-engineer` but skipped the stage file and the `handoff:` line. The helpers already score those files. This is prompt-layer stickiness, not a new artifact family.

## Evidence (2.2.0)

| Contract | On disk / eval |
| --- | --- |
| Default `graph.md` + close | [Run 21](../evals/2026-08-27-run-21.md) PASS (`13/13`). Tag `v2.2.0` on `74f1aa6` |
| Adaptive packet | Run 20 PASS — coordinator fallback `backend-developer-to-security-engineer.md`; `TO:` is a node |
| Adaptive `peer-router` spawn | Run 20 did spawn (cost ledger sonnet-5, $0.19, 7 turns). First packet rejected (`WHY:` vs `SUMMARY:`); coordinator fixed; “Packet validated. Spawning the adaptive hop.” |
| `stages/peer-router.md` | Run 20 FAIL — helper found 0. Do not drop the six-label file check |
| Handoff | Run 20 FAIL — no `handoff` on `$FULL_LOG` or `close.md`. Live board used “Spawning the adaptive hop” |
| FLAG | `agents/peer-router.md` still says spawn only when **a writer has named** a packet. Did not block run 19 (writer-filed) or run 20 (fallback ran anyway). Still wrong for a fallback-only run |
| Close | Run 20 PASS. Harvest FAIL. `backend-developer.md` had `FLAGS (` not `FLAGS:` — do not accept that |
| VERSION | **2.2.0** tagged |

Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_adaptive_peer_router`, `check_adaptive_handoff`, or `check_delivery_close_file`. Do not accept “Spawning the adaptive hop” as a handoff.

## Architecture

Prompt-layer stickiness. No helper loosen, no new eval case, no ceiling raise, no YAML parser, no seventh guardrail.

After `peer-router` returns, the coordinator’s next Write is `docs/delivery/<name>/stages/peer-router.md` — a byte copy of `skills/delivery-templates/stage-return.md`, then fill after the colons. Then print `handoff: <from> → <to>`. On `valid`, Agent the `TO:` and count the hop against `M`. On `reject`, no spawn; re-brief the author once or ✖ the hop.

Router copy: spawn when `--adaptive` is on **and a packet exists** (writer or coordinator fallback), not “writer has named.” Still read-only. Never Agent a peer.

Persist is already declared (peer-router in the four read-only list; copy the stage-return stub). Stickiness is the Adaptive paragraph + Interface + router description naming the file and the `handoff:` line so a hop cannot skip them.

Default `/make-feature` stays Supervisor. VERSION **2.2.1** only after billed `feature-adaptive` PASSes `peer-router.md` + handoff + close.

## Components

- **Interface** (all nine, byte-identical): persist `stages/peer-router.md`, then print `handoff:`. Without `--adaptive`, ignore `packets/`, never spawn `peer-router`. Graph sentence unchanged.
- **Coordinator Adaptive:** persist the router stage file **before** Agent-ing `TO:`; then `handoff: <from> → <to>`. One fallback packet per run; `TO:` still a graph node. Existing needles stay count **1**: `peer-router validates`, `print a handoff line`, `one fallback packet per run`, `never spawn peer-router without --adaptive`. Close-file cadence unchanged (`after every Agent return, the next Write is close.md` still holds after the read-only persist).
- **`peer-router.md`:** packet exists (writer or fallback). Still read-only. Never Agent a peer. Never Write or Edit.
- **Unchanged:** packet stub, close stub, graph stub, spawn cap, eval helpers, ceilings, four read-only agents include `peer-router`.

## Data flow (`--adaptive`)

1. Plan + `graph.md` as 2.2.0.
2. Packet (writer, or one coordinator fallback if none exists and this run has not hopped). `TO:` is a graph node.
3. Spawn `peer-router`.
4. Persist `stages/peer-router.md` (byte copy of the stage-return stub, fill after the colons). Overwrite `close.md` as today.
5. On `valid`: print `handoff: <from> → <to>`; Agent `TO:`; count the hop against `M`.
6. On `reject`: no spawn; re-brief once or ✖ the hop. Fallback still fires later if no hop has succeeded.
7. Without `--adaptive`: ignore `packets/`; never spawn `peer-router`.

## Error handling

| Case | Behavior |
| --- | --- |
| `--adaptive` off | Ignore `packets/`; never spawn `peer-router` |
| Packet `TO:` unknown / not a graph node | Router `reject`; persist `peer-router.md`; no hop |
| Writers file nothing | One coordinator fallback packet (`TO:` next queued **node**, else `tech-lead` if that node exists) |
| Router `reject` | Persist the stage file; no Agent; re-brief author once or ✖ the hop |
| Coordinator skips persist / prints “adaptive hop” with no `handoff` | Contract miss — eval FAIL. Do not widen the helper |
| Spawn cap `M` | `close.md` `STATUS: stopped` (already) |
| Timeout | Latest `close.md` is the scorecard; `peer-router.md` may exist with hop still `▶` |
| `VERIFIED (` / Bash `close.md` | Still bounce |

## Testing

**Guardrails (untouched helpers, new needles).** Do not change `check_adaptive_peer_router`, `check_adaptive_handoff`, `check_delivery_close_file`, or uncomment `check_subagent_log`. Keep existing coordinator needles at count **1**: `peer-router validates`, `print a handoff line`, `one fallback packet per run`, `never spawn peer-router without --adaptive`. Add three coordinator needles (also count **1** — do not mention the path string twice): persist `stages/peer-router.md` after the router returns; print the literal `handoff:`; spawn when a packet exists (writer or fallback). `peer-router.md` description + body drop “writer has named”; expect a packet-exists phrase instead. Four read-only agents still include `peer-router`. Interface stays byte-identical across the nine commands.

**Eval.** No new case. Gate is billed `KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-adaptive`. PASS = packet + `peer-router.md` six labels + `handoff` on `$FULL_LOG` or `close.md` + close. Harvest miss does not block. Pin `coordinator_hash`. `waivers: []`. Same ceilings (`$8.50` / 1200s / 14.5M). Do not grep `stream.jsonl`. Do not accept “Spawning the adaptive hop” as a handoff. Do not run until the user says **run it**. Receipt `docs/evals/2026-08-31-run-22.md` (or next date).

**Ship.** Those four PASS → VERSION **2.2.1**. FAIL → pin hash, stay **2.2.0** / Unreleased. Default `feature` is not the gate (graph + close already passed on 2.2.0).

## Inventory

- Agents still **18**. Commands still **14**. Guardrails still **6**.
- No new stub file. Stage-return stub already used for read-only persist.
- Gemini / Codex rebuild in the same change as the Interface / router copy.

## Non-goals

- YAML / JSON graph parser
- Seventh guardrail script
- Uncomment `check_subagent_log`
- Raise `$8.50` / 1200s / 14.5M
- Loosen `check_adaptive_peer_router`, `check_adaptive_handoff`, or `check_delivery_close_file`
- Accept “Spawning the adaptive hop” as a handoff
- Specialists Agent-ing a peer
- Making Adaptive the default `/make-feature`
- A new eval case
- Recreating `feat/close-md-hook`

## Versioning

| Field | 2.2.1 |
| --- | --- |
| Semver | Patch — persist + `handoff:` stickiness on an existing opt-in; FLAG copy fix |
| Adopter action | Plugin update; `--adaptive` writes `stages/peer-router.md` and prints `handoff:` |
| Do not bump | In the design or plan commit. Bump only after billed Adaptive PASS |
