# Guild 2.1.1 required hop, then 2.2.0 graph — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 2.1.1 makes `--adaptive` hop at least once (coordinator fallback packet). 2.2.0, only after 2.1.1 is tagged, adds default labeled `graph.md` and keeps Adaptive hops on-graph.

**Architecture:** Labeled markdown stubs. No YAML parser. Coordinator still Agent-spawns; specialists never Agent a peer. Fallback is one packet per `--adaptive` run: `FROM:` the writer who just returned, `TO:` next queued specialist else `tech-lead`. 2.2 `graph.md` is written after the plan, before the first Agent.

**Tech Stack:** Agent markdown, byte-identical Interface, guardrail harness, Gemini/Codex rebuild, billed `claude -p` pins.

**Spec:** [docs/plans/2026-08-24-guild-v2-adaptive-graph-design.md](2026-08-24-guild-v2-adaptive-graph-design.md)

---

## Global constraints

- Branch: `feat/v2.1.1-adaptive-hop`. Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/v211-graph`.
- Do **not** land `graph.md` (stub, Interface, eval, coordinator graph sentences) in any 2.1.1 commit.
- Do **not** start Phase B until **2.1.1 is tagged** (`git rev-parse v2.1.1` succeeds on `main`).
- Do **not** loosen `check_delivery_close_file`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` / `feature-adaptive` `max_usd` ($8.50), `EVAL_TIMEOUT` (1200), or the 14.5M token ceiling.
- Interface block stays **byte-identical** across the nine pipeline commands.
- Do **not** bump `VERSION` in a design/plan/guardrail commit. 2.1.1 bump only after Task 5 PASS. 2.2.0 bump only after Task 12 PASS.
- Billed evals **only** when the user says **run it**.

Exact Interface Adaptive sentences after Task 2 (must stay **byte-identical** on all nine). Replace the current two Adaptive sentences with:

`When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer; spawn `peer-router` to validate it; then Agent that peer with the packet as the brief; print a handoff line on the board; hops count against the spawn cap. If no writer packet exists, the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.`

Exact coordinator **Adaptive** paragraph after Task 2 (keep the `peer-router validates` needle and `never spawn peer-router without --adaptive`):

`**Adaptive** — when `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer: copy skills/delivery-templates/packet.md, then fill after the colons. `peer-router validates` that packet; then Agent the named peer with the packet as the brief; print a handoff line on the board; hops count against the spawn cap. If no writer packet exists, the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; then `peer-router validates`; then Agent. Specialists never Agent a peer. Without `--adaptive`, ignore `packets/` and never spawn peer-router without --adaptive.`

---

# Phase A — 2.1.1

### Task 1: Failing ratchets for required hop

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1:** After `Interface block requires adaptive opt-in`, add (no backticks in the needle — avoids SC2016):

```bash
expect "Interface block requires adaptive fallback hop" "9" \
  "$(grep -l 'one fallback packet per run' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

After `coordinator never spawns peer-router without --adaptive`, add:

```bash
expect "coordinator names one fallback packet per run" "1" \
  "$(grep -c 'one fallback packet per run' "$COORD")"
expect "coordinator fallback TO is next queued specialist else tech-lead" "1" \
  "$(grep -c 'next queued specialist else tech-lead' "$COORD")"
```

Inline JSON, no extra locals. Do not edit agents or commands in this task.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected: those three FAIL. Everything else still GREEN (currently 232).

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet Adaptive required hop and fallback packet"
```

---

### Task 2: Interface + coordinator fallback

**Files:**
- Modify: `commands/add-policy.md`, `commands/add-test.md`, `commands/audit-n-plus-one.md`, `commands/make-feature.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md` — only the two Adaptive sentences at the end of `> **Interface:**` (see Global constraints).
- Modify: `agents/delivery-coordinator.md` — replace the `**Adaptive**` paragraph (see Global constraints).

Do not add `graph.md`. Do not edit `peer-router.md`. Do not bump VERSION.

**Step 1:** Apply the exact sentences. Confirm one distinct Interface line:

```bash
python3 -c "
from pathlib import Path
blocks=set()
for p in Path('commands').glob('*.md'):
    for line in p.read_text().splitlines():
        if line.startswith('> **Interface:**'):
            blocks.add(line)
print(len(blocks), 'distinct Interface lines')
"
```

Expected: `1 distinct Interface lines`.

**Step 2:** `./tests/guardrails.test.sh` — ALL GREEN.

**Step 3: Commit**

```bash
git add commands/*.md agents/delivery-coordinator.md
git commit -m "feat: --adaptive requires one hop (coordinator fallback packet)"
```

---

### Task 3: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`
- Modify: `docs/README.md` Open 2.1.1 row if the wording drifted; keep 2.2 waiting until tagged

Do **not** retitle to `[2.1.1]`. Do not claim the billed gate passed. User-consequence: `--adaptive` hops at least once; coordinator files a fallback packet if writers do not.

```bash
git add CHANGELOG.md docs/README.md
git commit -m "docs: Unreleased 2.1.1 Adaptive required hop"
```

---

### Task 4: Gemini / Codex mirrors

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

If rebuild diffs, commit `chore: rebuild Gemini and Codex mirrors for required hop`. If no diff, do not empty-commit.

---

### Task 5: Billed `feature-adaptive` pin

**Do not run until Tasks 1–4 are green locally. Do not run until the user says `run it`.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-adaptive
```

Receipt: `docs/evals/2026-08-24-run-19.md` (or next date). Record: packet PASS/FAIL, `peer-router.md`, handoff, close, basename, whether the packet was writer-filed or coordinator fallback, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If Adaptive file checks PASS** and close PASSes: bump `VERSION` + five manifests to **2.1.1**. Retitle changelog `[2.1.1]`. Move Open: 2.1.1 closed; 2.2 still waits. Commit `release: 2.1.1 — Adaptive required hop`.

**If they FAIL:** pin the hash anyway, leave VERSION at 2.1.0, leave Unreleased. Commit `docs: eval run 19 — <what missed>`. Do not loosen helpers. Do not raise ceilings. Do **not** start Phase B.

Do not tag until CI is green on the PR.

---

# Phase B — 2.2.0

**Hard gate:** `git merge-base --is-ancestor $(git rev-parse v2.1.1^{commit}) HEAD` on `main` after the 2.1.1 tag exists. If `v2.1.1` is missing, stop.

Exact 2.2 Interface sentence (append inside `> **Interface:**`, all nine, once, after the Adaptive sentences):

`After the plan, Write \`docs/delivery/<name>/graph.md\` from skills/delivery-templates/graph.md; do not spawn a type that is not a NODES: entry; an Adaptive hop TO: must be a node.`

Use this literal (backticks as in other Interface path sentences):

`After the plan, Write `docs/delivery/<name>/graph.md` from skills/delivery-templates/graph.md; do not spawn a type that is not a NODES: entry; an Adaptive hop TO: must be a node.`

---

### Task 6: Failing graph ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

After the 2.1.1 fallback expects, add:

```bash
expect "Interface block requires delivery graph.md" "9" \
  "$(grep -l 'do not spawn a type that is not a NODES:' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

After coordinator fallback expects, add:

```bash
expect "coordinator Writes graph.md after the plan" "1" \
  "$(grep -c 'Write \`docs/delivery/<name>/graph.md\`' "$COORD" || grep -c 'docs/delivery/<name>/graph.md' "$COORD")"
```

Prefer a backtick-free needle if SC2016 fires:

```bash
expect "coordinator Writes graph.md after the plan" "1" \
  "$(grep -c 'docs/delivery/<name>/graph.md' "$COORD")"
expect "coordinator never spawns off-graph" "1" \
  "$(grep -c 'do not spawn a type that is not a NODES:' "$COORD")"
expect "coordinator Adaptive hop TO must be a node" "1" \
  "$(grep -c 'an Adaptive hop TO: must be a node' "$COORD")"
```

After packet stub expects, add (FAIL until Task 7 — file missing):

```bash
GRAPH="$SCRIPT_DIR/skills/delivery-templates/graph.md"
expect "graph stub prefixes NODES:" "1" \
  "$(grep -c '^NODES:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes EDGES:" "1" \
  "$(grep -c '^EDGES:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes PARALLEL:" "1" \
  "$(grep -c '^PARALLEL:' "$GRAPH" 2>/dev/null || echo 0)"
expect "graph stub prefixes ON-FAIL:" "1" \
  "$(grep -c '^ON-FAIL:' "$GRAPH" 2>/dev/null || echo 0)"
```

Do not edit agents, commands, or add the stub in this task.

**Step 2:** `./tests/guardrails.test.sh` — new expects FAIL.

**Step 3: Commit** `test(guardrails): ratchet delivery graph.md`

---

### Task 7: Graph stub

**Files:**
- Create: `skills/delivery-templates/graph.md`

```
NODES: <registered agent types, comma-separated>
EDGES: <from -> to, comma-separated>
PARALLEL: none
ON-FAIL: stop
```

Modify `skills/delivery-templates/SKILL.md` — one short Packet-style section: copy `graph.md`, fill after the colons, after the plan, before the first Agent.

**Step 1:** Add the files. `./tests/guardrails.test.sh` — stub expects PASS; Interface/coordinator graph expects still FAIL.

**Step 2: Commit** `feat: labeled graph.md delivery stub`

---

### Task 8: Interface + coordinator graph

**Files:**
- Modify: the same nine `commands/*.md` — append the 2.2 Interface sentence (Global Phase B).
- Modify: `agents/delivery-coordinator.md` — after **Adaptive**, add **Graph**: copy stub after the plan, before the first Agent; `docs/delivery/<name>/graph.md`; do not spawn a type that is not a `NODES:` entry; an Adaptive hop `TO:` must be a node; fallback `TO:` is the next queued **node**.

Confirm `1 distinct Interface lines`. `./tests/guardrails.test.sh` ALL GREEN.

Commit `feat: default graph.md after the plan; hops on-graph`

---

### Task 9: Eval graph helper

**Files:**
- Modify: `tests/eval/run-evals.sh` — `check_delivery_graph_file`: `docs/delivery/*/graph.md` exists; `NODES:` / `EDGES:` / `PARALLEL:` / `ON-FAIL:`; each `NODES:` token is a registered `agents/*.md`. Call from `checks_feature` and `checks_feature_adaptive`. Adaptive: hop `TO:` (packet) is a node (can live inside the helper when `--adaptive` case runs).
- Modify: `docs/evals/2026-08-06-check-audit.md` tally to match `count_eval_answer_checks`.
- Isolation expects in `tests/guardrails.test.sh` for the new helper (PASS path + missing-file FAIL). Do not grep `stream.jsonl`. Do not uncomment `check_subagent_log`.

```bash
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
```

Inventory may FAIL only on `coordinator_hash` until Task 12. Tally must match.

Commit `feat: eval asserts graph.md labels and registered nodes`

---

### Task 10: Changelog Unreleased (2.2)

Do not retitle `[2.2.0]`. Do not claim billed graph PASS.

Commit `docs: Unreleased 2.2.0 delivery graph.md`

---

### Task 11: Gemini / Codex rebuild

Same as Task 4. Commit only if diff: `chore: rebuild Gemini and Codex mirrors for graph.md`

---

### Task 12: Billed pin (2.2)

**Do not run until Tasks 6–11 are green. Do not run until the user says `run it`.**

Default `feature` first (`/make-feature Tag --api`) — asserts `graph.md` + close. Then `feature-adaptive` if you also need hop-on-graph in the same release pin.

Receipt: next dated `docs/evals/`. Pin `coordinator_hash`. `waivers: []`.

**If graph file check PASS** and close PASSes: bump VERSION + five manifests to **2.2.0**. Retitle changelog. Move Open: 2.2 closed. Commit `release: 2.2.0 — delivery graph.md`.

**If FAIL:** pin hash, leave VERSION at 2.1.1, leave Unreleased. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- YAML / JSON graph parser
- Seventh guardrail script
- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M
- Accepting `VERIFIED (`
- Specialists Agent-ing a peer
- Making Adaptive the default `/make-feature`
- `graph.md` in a 2.1.1 commit
- Starting Phase B before `v2.1.1` exists
