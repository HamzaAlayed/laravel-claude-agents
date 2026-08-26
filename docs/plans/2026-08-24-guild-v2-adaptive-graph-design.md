# Design — Guild 2.1.1 required hop, then 2.2.0 graph

**Status:** approved 2026-08-24. Follow-up to [2.1 Adaptive](2026-08-23-guild-v2-adaptive-design.md) after [v2.1.0](https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v2.1.0) and [run 18](../evals/2026-08-23-run-18.md). Two tags, sequenced. Not one 2.2.0 bag.

**Goal:** Make `--adaptive` produce at least one hop so the billed Adaptive gate can PASS (2.1.1), then make every delivery declare a labeled `graph.md` the coordinator must follow, with Adaptive hops on-graph (2.2.0).

**Why two minors:** 2.1.1 is a patch-shaped contract tighten on an opt-in flag (required hop + coordinator fallback). 2.2.0 is a new default artifact (`graph.md`). Mixing them in one billed run repeats run 18’s timeout: extra hops plus a new file on the same $8.50 / 1200s budget.

## Evidence (2.1.0)

| Contract | On disk / eval |
| --- | --- |
| Close file helper | [Run 17](../evals/2026-08-21-run-17.md) PASS; [run 18](../evals/2026-08-23-run-18.md) PASS |
| Adaptive packet / `peer-router.md` / handoff | Run 18 FAIL — `packets/` empty; QA: no peer needed; four Agent launches, none `peer-router` |
| Default routing | Supervisor unless `--adaptive` |
| Spawn cap | Board header `N stages · cap: M spawns · done when:` |
| VERSION | **2.1.0** tagged |

Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not loosen `check_delivery_close_file`. Do not land `graph.md` in the 2.1.1 tag.

## Architecture

Labeled markdown stubs (same family as `close.md` / `packet.md`). No YAML parser. No seventh guardrail script.

**2.1.1 — required hop.** Flag-only. No `graph.md`. When `--adaptive` is on: a writer may still Write a packet; if none exists after a writer returns and this run has not already hopped, the coordinator Writes **one** fallback packet `FROM:` that writer `TO:` the next queued specialist who has not returned, else `tech-lead`. Then `peer-router` validates and the coordinator Agent-spawns that peer, prints a handoff line, counts the hop against `M`. Specialists never Agent a peer. Default `/make-feature` unchanged. VERSION **2.1.1** only if billed packet + `peer-router.md` + handoff + close PASS.

**2.2.0 — default graph.** Starts only after 2.1.1 is tagged. After the plan, before the first Agent, the coordinator Writes `docs/delivery/<name>/graph.md` from `skills/delivery-templates/graph.md`. Nodes are registered agent types. Edges are `after`. `PARALLEL:` groups are the 2.0 join set. `ON-FAIL:` is `stop` | `re-brief` | `checkpoint`. Coordinator must not spawn a type that is not a node. An Adaptive hop `TO:` that is not a node is reject; fallback hop picks the next queued **node**. Eval asserts the file, not nested chat.

## Components

### 2.1.1

- **Interface** (all nine, byte-identical): `--adaptive` requires at least one hop. If no writer packet, coordinator Writes one fallback (`next queued` / `tech-lead`).
- **Coordinator** Working interface: that fallback, then `peer-router` → Agent the `TO:`.
- **Unchanged:** `packet.md`, `peer-router`, close file, spawn cap, ceilings, no `graph.md`.
- **Eval:** existing `feature-adaptive` checks. No new case.

### 2.2.0

- **Stub** `skills/delivery-templates/graph.md` — `NODES:` / `EDGES:` / `PARALLEL:` / `ON-FAIL:`. Copy, fill after the colons.
- **Coordinator** Writes `graph.md` after the plan. Must not spawn off-graph. Adaptive `TO:` must be a node.
- **Interface** one new sentence on all nine. `feature` asserts `graph.md`. `feature-adaptive` also asserts the hop’s `TO:` is a node.

## Data flow

### 2.1.1 (`--adaptive`)

1. Plan and board as today. No graph file.
2. After each writer stage file: if a valid packet exists → `peer-router` → Agent `TO:` → handoff → hops vs `M`.
3. If **no** packet after that writer and this run has **not** already hopped: coordinator Writes one packet (`FROM:` that writer, `TO:` next queued specialist, else `tech-lead`) → `peer-router` → Agent → handoff. One fallback per run.
4. Invalid / unknown `TO:` → reject; no spawn; re-brief the writer once or ✖ that hop. Fallback still fires later if no hop has succeeded.
5. Without `--adaptive`: ignore `packets/`, never spawn `peer-router`.

### 2.2.0

1. After the plan, **before** the first Agent: Write `graph.md`.
2. Every spawn’s type must be a `NODES:` entry. Off-graph → do not Agent; `ON-FAIL` applies.
3. `--adaptive` hop `TO:` must be a node. Fallback `TO:` = next queued **node** (else `tech-lead` if that node exists).
4. Joins still wait on upstream stage files. `PARALLEL:` is the join set, not a second scheduler.
5. Default `/make-feature` writes and follows the graph. `--adaptive` is still the only way to hop.

## Error handling

| Case | 2.1.1 | 2.2.0 |
| --- | --- | --- |
| `--adaptive` off | Ignore `packets/`; never spawn `peer-router` | Write and follow `graph.md`; still no hop |
| Packet `TO:` not a registered agent | `peer-router` reject; no spawn | Same, and also reject if not a node |
| Writers file nothing | One coordinator fallback packet (next queued, else `tech-lead`) | Fallback `TO:` must be a **node** |
| Fallback `TO:` would be off-graph | n/a | Skip that name; next node; if none, `ON-FAIL` |
| Spawn cap `M` | `close.md` `STATUS: stopped` (already) | Same |
| Timeout | Latest `close.md` is the scorecard | Same; `graph.md` may exist with stages still `▶` |
| Missing `graph.md` after plan | n/a | Contract break — do not Agent until it exists |
| Off-graph Agent | n/a | Do not spawn; apply `ON-FAIL:` `stop` \| `re-brief` \| `checkpoint` |
| `ON-FAIL: stop` | n/a | `close.md` `STATUS: stopped` |
| `VERIFIED (` / Bash `close.md` | Still bounce | Still bounce |

## Testing

**2.1.1 guardrails.** Interface needle on all nine — required hop + coordinator fallback. Coordinator needles: `one fallback packet per run`; `next queued specialist else tech-lead`. Packet stub / `peer-router` / close / cap unchanged.

**2.1.1 eval.** `KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-adaptive`. PASS gate = packet + `peer-router.md` six labels + handoff + close. Harvest miss does not block. Pin `coordinator_hash`. `waivers: []`. Receipt `docs/evals/2026-08-24-run-19.md` (or next date). Do not run until the user says **run it**.

**2.1.1 ship.** Those four PASS → VERSION **2.1.1**. FAIL → pin hash, stay 2.1.0 / Unreleased. Do not start 2.2 on that tag.

**2.2.0 guardrails (after 2.1.1 is tagged).** `graph.md` stub prefixes; Interface sentence count 9; coordinator Writes graph after plan; never spawn off-graph; Adaptive `TO:` must be a node.

**2.2.0 eval.** Default `feature` asserts `graph.md` labels + registered nodes. `feature-adaptive` also asserts hop `TO:` is a node. Same ceilings. Do not grep `stream.jsonl`.

**2.2.0 ship.** Graph file check PASS and close still PASS → VERSION **2.2.0**.

## Inventory (2.2.0)

- Agents still **18**. Commands still **14**. Guardrails still **6**.
- New skill stub file only (`graph.md`), not a new skill directory.
- Gemini / Codex rebuild in the same change as the Interface / stub.

## Non-goals

- YAML / JSON graph parser
- Seventh guardrail script
- Uncomment `check_subagent_log`
- Raise `$8.50` / 1200s / 14.5M
- Loosen `check_delivery_close_file`
- Specialists Agent-ing a peer
- Making Adaptive the default `/make-feature`
- Landing `graph.md` in the 2.1.1 tag
- Starting 2.2 before 2.1.1 is tagged
- A second scheduler besides joins + spawn cap

## Versioning

| Field | 2.1.1 | 2.2.0 |
| --- | --- | --- |
| Semver | Patch — required hop on an existing opt-in | Minor — default `graph.md` |
| Adopter action | Plugin update; `--adaptive` now hops at least once | Plugin update; every delivery writes `graph.md` |
| Do not bump | In the design or plan commit | In the 2.1.1 tag |
