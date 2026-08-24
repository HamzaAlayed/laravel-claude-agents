# Design — Guild 2.1 Adaptive (opt-in peer handoff)

**Status:** approved 2026-08-23. Follow-up to [Guild v2 roadmap](2026-08-20-guild-v2-design.md) after [v2.0.0](https://github.com/HamzaAlayed/laravel-claude-agents/releases/tag/v2.0.0). Not 2.2 graph.

**Goal:** Opt-in Adaptive routing — peer handoff, a `peer-router` validator, and a no-re-ask packet — without making Adaptive the default `/make-feature` path, without specialists spawning peers, and without loosening 2.0 close-file helper.

**Why this is a minor:** 2.0 already shipped Supervisor complete (close file, joins, spawn cap, need-to-know briefs). 2.1 adds an **opt-in flag** on the existing nine pipeline commands. Default routing stays Supervisor. Adopters who never pass `--adaptive` see the 2.0 Interface.

## Evidence (2.0)

| Contract | On disk / eval |
| --- | --- |
| Close file helper | [Run 17](../evals/2026-08-21-run-17.md) PASS |
| Default routing | Coordinator Agent-spawns; specialists do not Agent peers |
| Spawn cap | Board header `N stages · cap: M spawns · done when:` |
| v2 non-goal | No new **default** agent on `/make-feature` |

VERSION stays **2.0.0** until the billed Adaptive pin’s Adaptive checks PASS. Do not raise `EVAL_TIMEOUT`, `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`. Do not start 2.2 `graph.md`.

## Architecture

**Opt-in.** `--adaptive` on all nine pipeline commands (`argument-hint` grows). Interface stays **byte-identical**. Without the flag: ignore `docs/delivery/*/packets/`, never spawn `peer-router`.

**Packet.** Writer may Write `docs/delivery/<name>/packets/<from>-to-<peer>.md` by copying `skills/delivery-templates/packet.md` then filling after the colons. From/to basenames are registered agent types (same ratchet as stage files: no `-fixes`). Fields: `FROM:` / `TO:` / `SUMMARY:` (employee/task ids masked) / `PATHS:` · `STAGE:` (exact peer stage path).

**Router.** New agent `peer-router` (18th). Spawned **only** when `--adaptive` is on. Read-only (`disallowedTools: Edit, Write`); coordinator persists `docs/delivery/<name>/stages/peer-router.md` like tech-lead. Reads the packet; returns `valid` or `reject`. Include in `enforce-reviewer-readonly.sh` `REVIEWERS` so Bash is not a write vector. Not on the default `/make-feature` path.

**Handoff.** Coordinator still Agent-spawns. After a writer’s stage file: if `--adaptive` and a packet names a registered peer and `peer-router` says valid → Agent that peer with the packet as the brief (no re-ask of stack/diffs) → print a **handoff** line on the board → ✔ from the peer’s stage file. Specialists never Agent a peer. Hops count against spawn cap `M`. Invalid / unknown `TO:` → no peer spawn; re-brief the writer once or ✖ that hop.

**Close file / harvest.** Unchanged 2.0 helpers. Adaptive does not replace `close.md`.

## Inventory

- Agents **18** (was 17). Read-only agents **4** (was 3). Writers stay **13**.
- Commands still **14**. Guardrails still **6**.
- Gemini / Codex rebuild in the same change as the agent + Interface.

## Error handling

| Case | Response |
| --- | --- |
| `--adaptive` absent | Supervisor; ignore `packets/`; never spawn `peer-router` |
| Packet `TO:` not a registered agent | `peer-router` reject; no peer spawn |
| Invalid / unmasked ids / missing labels | reject; re-brief writer once or ✖ the hop |
| Spawn cap hit | `close.md` `STATUS: stopped` (already) |
| Timeout | Latest `close.md` is still the 2.0 scorecard |

## Testing

**Guardrails (no billed run).** Interface `--adaptive` sentence count **9** and byte-identical. Coordinator needles count **1** each: packet path, `peer-router` validates, handoff line, hops count against the cap, never spawn `peer-router` without `--adaptive`. Read-only count **4**. Packet stub prefixes. `peer-router.md` exists and defers the stage file. Reviewer-readonly includes `peer-router`.

**Eval.** Default `feature` unchanged (`/make-feature Tag --api`). New opt-in `feature-adaptive`: `/make-feature Tag --api --adaptive`. Same $8.50 / 1200s / 14.5M. Assert: packet file + registered FROM/TO, `peer-router.md` six labels, a handoff line on `$LOG`/`close.md` `BOARD:`, `check_delivery_close_file` still PASS. Pin `coordinator_hash` from that run. `waivers: []`. Receipt `docs/evals/2026-08-23-run-18.md` (or next date).

**Release.** Bump `VERSION` + five manifests to **2.1.0** only after those Adaptive checks PASS. Changelog `[2.1.0]`. Move the Open row: 2.1 closed; 2.2 graph waits.

## Non-goals

- Do not start 2.2 `graph.md`
- Do not uncomment `check_subagent_log`
- Do not raise ceilings
- Do not loosen `check_delivery_close_file`
- Do not let specialists Agent a peer
- Do not spawn `peer-router` on the default path
- Do not add a seventh guardrail script
- Do not make Adaptive the default `/make-feature`

## Versioning

| Field | 2.1.0 |
| --- | --- |
| Semver | Minor — opt-in flag + one agent; default Interface path unchanged |
| Adopter action | Plugin update; pass `--adaptive` to opt in |
| Do not bump | In the design or plan commit |
