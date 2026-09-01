# Guild 2.2.1 Adaptive hop persist — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** On `--adaptive`, persist `docs/delivery/<name>/stages/peer-router.md` and print `handoff: <from> → <to>` so billed Adaptive PASSes, and spawn `peer-router` when a packet exists (writer or fallback), not only when a writer has named one.

**Architecture:** Prompt-layer stickiness. No helper loosen, no new eval case, no new stub. After `peer-router` returns, persist its stage file (byte copy of `skills/delivery-templates/stage-return.md` is already the read-only persist rule), then print `handoff:`. On `valid`, Agent `TO:`. Router copy: packet exists.

**Tech Stack:** Agent markdown, byte-identical Interface, guardrail harness, Gemini/Codex rebuild, billed `claude -p` pin.

**Spec:** [docs/plans/2026-08-31-guild-v2-adaptive-persist-design.md](2026-08-31-guild-v2-adaptive-persist-design.md)

---

## Global constraints

- Branch: `feat/v2.2.1-adaptive-persist`. Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/v221-adaptive-persist`. Create it from `main` (after this plan is on `main`). Do **not** reuse `.claude/worktrees/v220-graph`. After checkout, verify `VERSION` is `2.2.0` and `HEAD` is this branch before editing.
- Do **not** loosen `check_adaptive_peer_router`, `check_adaptive_handoff`, or `check_delivery_close_file`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` / `feature-adaptive` `max_usd` ($8.50), `EVAL_TIMEOUT` (1200), or the 14.5M token ceiling.
- Do **not** accept “Spawning the adaptive hop” as a handoff.
- Interface block stays **byte-identical** across the nine pipeline commands.
- Coordinator `grep -c` needles stay **exactly 1** (grep `-c` counts matching lines; keep Adaptive as one paragraph). Do not put `stages/peer-router.md` or `handoff:` on a second coordinator line. Do **not** repeat `copy skills/delivery-templates/stage-return.md` in the Adaptive paragraph (read-only persist already has that needle at count 1).
- Do **not** bump `VERSION` in a design/plan/guardrail commit. 2.2.1 bump only after Task 6 PASS.
- Billed evals **only** when the user says **run it**.
- Default `/make-feature` stays Supervisor. Specialists never Agent a peer.

Nine pipeline commands (Interface must match on all):

`commands/make-feature.md`, `commands/add-test.md`, `commands/add-policy.md`, `commands/audit-n-plus-one.md`, `commands/optimize-query.md`, `commands/refactor-to-action.md`, `commands/review-pr.md`, `commands/ship-checklist.md`, `commands/upgrade-laravel.md`.

Exact Interface Adaptive sentences after Task 2 (must stay **byte-identical** on all nine). Replace the current three Adaptive sentences. Leave the graph sentence that follows unchanged.

Current (replace this):

`When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer; spawn `peer-router` to validate it; then Agent that peer with the packet as the brief; print a handoff line on the board; hops count against the spawn cap. If no writer packet exists, the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.`

Replacement:

`When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, Write `docs/delivery/<name>/stages/peer-router.md`; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.`

Exact coordinator **Adaptive** paragraph after Task 2 (keep existing needles on this same paragraph; do not repeat the stage-return copy phrase):

`**Adaptive** — when `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer: copy skills/delivery-templates/packet.md, then fill after the colons. If no writer packet exists, the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run. Spawn `peer-router` when a packet exists. `peer-router validates` that packet; after it returns, persist `docs/delivery/<name>/stages/peer-router.md`. Then print a handoff line `handoff: <from> → <to>` on the board; on valid, Agent the named peer with the packet as the brief; hops count against the spawn cap. Specialists never Agent a peer. Without `--adaptive`, ignore `packets/` and never spawn peer-router without --adaptive.`

Existing coordinator needles that must remain count **1**: `peer-router validates`, `print a handoff line`, `one fallback packet per run`, `never spawn peer-router without --adaptive`, `next queued specialist else tech-lead`, `copy skills/delivery-templates/stage-return.md`, `after every Agent return, the next Write is close.md`.

New coordinator needles (count **1**): `stages/peer-router.md`, `handoff:`, `when a packet exists`.

Exact `agents/peer-router.md` copy after Task 2:

Frontmatter `description:` — replace `a writer has named a peer packet` with `a packet exists` and add `(writer or coordinator fallback)` after the packet path:

`Validates Adaptive no-re-ask peer packets. Use **only** when `--adaptive` is on and a packet exists at `docs/delivery/<name>/packets/<from>-to-<peer>.md` (writer or coordinator fallback). Do **not** use on the default Supervisor /make-feature path. Checks FROM/TO are registered agent types, employee/task ids are masked, PATHS are owned paths, and STAGE is the peer stage path. Returns valid or reject. Does not spawn peers. Does not write code.`

Body first paragraph — replace `a writer has named a peer packet` with `a packet exists (writer or coordinator fallback)`:

`Read-only. Spawned **only** when `--adaptive` is on and a packet exists (writer or coordinator fallback). Not on the default Supervisor `/make-feature` path. Validate the packet; return `valid` or `reject`. Never Agent a peer. Never Write or Edit. Never mutate files via Bash (`sed -i`, `git checkout/reset`, redirects, `pint` without `--test`). The coordinator persists your artifacts and, on `valid`, is the only one who Agent-spawns the named peer.`

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1: Write the failing expects**

After `Interface block requires graph stub byte copy`, add (no backticks in the needle — avoids SC2016):

```bash
expect "Interface block requires peer-router stage persist" "9" \
  "$(grep -l 'stages/peer-router.md' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
expect "Interface block requires handoff colon line" "9" \
  "$(grep -l 'handoff:' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

After `coordinator Adaptive hop TO must be a node` (keep graph byte-copy expect where it is), add:

```bash
expect "coordinator persists peer-router.md after router return" "1" \
  "$(grep -c 'stages/peer-router.md' "$COORD")"
expect "coordinator prints handoff colon line" "1" \
  "$(grep -c 'handoff:' "$COORD")"
expect "coordinator spawns peer-router when a packet exists" "1" \
  "$(grep -c 'when a packet exists' "$COORD")"
```

After the four-read-only expect, add:

```bash
expect "peer-router does not require a writer-named packet" "0" \
  "$(grep -c 'writer has named' "$SCRIPT_DIR/agents/peer-router.md")"
expect "peer-router spawns when a packet exists" "2" \
  "$(grep -c 'a packet exists' "$SCRIPT_DIR/agents/peer-router.md")"
```

Inline JSON, no extra locals. Do not edit agents or commands in this task.

**Step 2: Run test to verify it fails**

```bash
./tests/guardrails.test.sh
```

Expected: those seven FAIL. Everything else still GREEN.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet Adaptive hop persist and packet-exists FLAG"
```

---

### Task 2: Interface + coordinator + peer-router copy

**Files:**
- Modify: the nine pipeline commands listed above (Interface Adaptive sentences only)
- Modify: `agents/delivery-coordinator.md` — Adaptive paragraph only
- Modify: `agents/peer-router.md` — description + first body paragraph
- Modify: `scripts/body_budget.json` — only if Task 2’s check exceeds; raise **only** exceeded entries (likely `peer-router` `description_chars`). Do not full `--reseed`.

**Step 1: Apply the exact replacements** in Global constraints. Confirm `1 distinct Interface lines`:

```bash
grep -h '^> \*\*Interface:\*\*' commands/*.md | sort -u | wc -l
```

Expected: `1`.

Do not touch the Graph paragraph. Do not touch packet/close/graph stubs. Do not repeat `copy skills/delivery-templates/stage-return.md` in Adaptive.

**Step 2: Run tests to verify they pass**

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails ALL GREEN. Body budget: if `peer-router` `description_chars` exceeds 443, edit that one cap in `scripts/body_budget.json` (actual + ~10% like the last reseed) and re-run. Inventory may FAIL only on `coordinator_hash` until Task 6.

**Step 3: Commit**

```bash
git add commands/*.md agents/delivery-coordinator.md agents/peer-router.md scripts/body_budget.json
git commit -m "feat: persist peer-router.md and print handoff: on Adaptive hops"
```

Omit `scripts/body_budget.json` from the add if it did not change.

---

### Task 3: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` — fill `[Unreleased]`. Do **not** retitle to `[2.2.1]`. Do not claim the billed gate passed.
- Modify: `docs/README.md` — add a Guild v2 2.2.1 row; put “Adaptive hop persist (run 20 miss)” under Open until Task 6.

User-consequence: `--adaptive` persists `stages/peer-router.md` and prints `handoff:`; `peer-router` accepts writer or fallback packets.

**Step 1: Write Unreleased**

```markdown
## [Unreleased]

`--adaptive` persists `stages/peer-router.md` after the router returns and
prints `handoff: <from> → <to>`. Spawn `peer-router` when a packet exists
(writer or coordinator fallback), not only when a writer has named one.
Default `/make-feature` stays Supervisor.

### Changed

- **Adaptive hop persist.** After `peer-router` returns, the coordinator
  Writes `docs/delivery/<name>/stages/peer-router.md`, then prints
  `handoff:`. On `valid`, Agent the `TO:`.
- **`peer-router` FLAG.** Spawn when `--adaptive` is on and a packet
  exists (writer or fallback). Still read-only. Never Agent a peer.
```

**Step 2: Commit**

```bash
git add CHANGELOG.md docs/README.md
git commit -m "docs: Unreleased 2.2.1 Adaptive hop persist"
```

---

### Task 4: Gemini / Codex mirrors

**Files:**
- Generated: `gemini/`, `codex/` (only if rebuild diffs)

**Step 1: Rebuild**

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

**Step 2: Commit only if diff**

```bash
git add gemini/ codex/
git commit -m "chore: rebuild Gemini and Codex mirrors for Adaptive persist"
```

If no diff, do not empty-commit.

---

### Task 5: Local verification (no billed run)

**Step 1:**

```bash
./tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
```

Expected: guardrails GREEN. Body budget GREEN. Inventory FAIL only on `coordinator_hash` (and version strings still 2.2.0). `VERSION` still `2.2.0`.

**Step 2:** Do not commit unless a check forced a missed edit. Stop here until the user says **run it**.

---

### Task 6: Billed `feature-adaptive` pin

**Do not run until Tasks 1–5 are green locally. Do not run until the user says `run it`.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-adaptive
```

Receipt: `docs/evals/2026-08-31-run-22.md` (or next date). Record: packet PASS/FAIL, `peer-router.md` six labels, `handoff` on `$FULL_LOG` or `close.md`, close, whether the packet was writer-filed or coordinator fallback, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`. Harvest miss does not block.

**If Adaptive file checks PASS** and close PASSes: bump `VERSION` + manifests to **2.2.1** (`VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`, `gemini/gemini-extension.json`). Retitle changelog `[2.2.1]`. Close the Open row on `docs/README.md`. Commit `release: 2.2.1 — Adaptive hop persist`.

**If they FAIL:** pin the hash anyway, leave VERSION at 2.2.0, leave Unreleased. Commit `docs: eval run 22 — <what missed>`. Do not loosen helpers. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- YAML / JSON graph parser
- Seventh guardrail script
- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M
- Loosening Adaptive or close helpers
- Accepting “Spawning the adaptive hop” as a handoff
- Specialists Agent-ing a peer
- Making Adaptive the default `/make-feature`
- A new eval case
- Recreating `feat/close-md-hook`
- Full `body_budget.json --reseed`
