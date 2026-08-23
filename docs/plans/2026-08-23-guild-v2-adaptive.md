# Guild 2.1 Adaptive Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Opt-in `--adaptive` peer handoff with a no-re-ask packet and a `peer-router` validator. Default `/make-feature` stays Supervisor. Do not ship 2.1.0 unless the billed Adaptive checks PASS.

**Architecture:** Writer Writes `docs/delivery/<name>/packets/<from>-to-<peer>.md`. Coordinator (only when `--adaptive`) spawns read-only `peer-router` to validate, then Agent-spawns the named peer with that packet as the brief, prints a handoff line, still owns `✔`. Specialists never Agent a peer. Hops count against spawn cap `M`.

**Tech Stack:** Agent markdown, byte-identical Interface, guardrail harness, Gemini/Codex rebuild, one billed `claude -p` `feature-adaptive` run.

**Spec:** [docs/plans/2026-08-23-guild-v2-adaptive-design.md](2026-08-23-guild-v2-adaptive-design.md)

---

## Global constraints

- Stay on `feat/adaptive-21`. This is 2.1, not 2.2.
- Do **not** loosen `check_delivery_close_file`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` / `feature-adaptive` `max_usd` ($8.50), `EVAL_TIMEOUT` (1200), or the 14.5M token ceiling.
- Do **not** drop existing close.md / spawn-cap / join Interface expects.
- Do **not** let specialists Agent a peer.
- Do **not** spawn `peer-router` on the default (no `--adaptive`) path.
- Interface block stays **byte-identical** across the nine pipeline commands.
- Do **not** bump `VERSION` until Task 8’s billed Adaptive checks PASS.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/adaptive-21`.

Exact Interface sentence (append inside the existing `> **Interface:**` blockquote, all nine commands, once):

`When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer; spawn `peer-router` to validate it; then Agent that peer with the packet as the brief; print a handoff line on the board; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.`

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1:** After `Interface block caps specialist spawns`, add:

```bash
expect "Interface block requires adaptive opt-in" "9" \
  "$(grep -l 'Without `--adaptive`, ignore' "$SCRIPT_DIR"/commands/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

Change the read-only expect from `"3"` to `"4"` (it will FAIL until Task 3):

```bash
expect "four read-only agents defer the stage file to the coordinator" "4" \
  "$(grep -l 'coordinator persists your stage file' "$SCRIPT_DIR"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
```

Keep the thirteen-writer expect at `13`.

After `coordinator forbids Bash writes of close.md`, add:

```bash
expect "coordinator names the packet path" "1" \
  "$(grep -c 'docs/delivery/<name>/packets/' "$COORD")"
expect "coordinator has peer-router validate" "1" \
  "$(grep -c 'peer-router validates' "$COORD")"
expect "coordinator prints a handoff line" "1" \
  "$(grep -c 'print a handoff line' "$COORD")"
expect "coordinator counts hops against the spawn cap" "1" \
  "$(grep -c 'hops count against the spawn cap' "$COORD")"
expect "coordinator never spawns peer-router without --adaptive" "1" \
  "$(grep -c 'never spawn peer-router without --adaptive' "$COORD")"
```

After the close stub expects, add packet stub expects (file missing today → FAIL):

```bash
PACKET="$SCRIPT_DIR/skills/delivery-templates/packet.md"
expect "packet stub prefixes FROM:" "1" \
  "$(grep -c '^FROM:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes TO:" "1" \
  "$(grep -c '^TO:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes SUMMARY:" "1" \
  "$(grep -c '^SUMMARY:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes PATHS:" "1" \
  "$(grep -c '^PATHS:' "$PACKET" 2>/dev/null || echo 0)"
expect "packet stub prefixes STAGE:" "1" \
  "$(grep -c 'STAGE:' "$PACKET" 2>/dev/null || echo 0)"
```

After reviewer-readonly fixtures, add (FAIL until Task 3: `peer-router` not in `REVIEWERS`):

```bash
expect "peer-router sed -i blocks" "$BLOCK" \
  "$(run_hook enforce-reviewer-readonly.sh '{"agent_type":"peer-router","tool_input":{"command":"sed -i s/a/b/ file.php"}}')"
```

Inline JSON, no extra locals. Do not edit agents or commands in this task.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected FAIL on the new expects (Interface 0/9, coordinator needles 0, packet stub missing, read-only still 3, peer-router hook allow).

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet --adaptive packet, peer-router, handoff"
```

---

### Task 2: Packet stub

**Files:**
- Create: `skills/delivery-templates/packet.md`
- Modify: `skills/delivery-templates/SKILL.md` (one short section pointing at the stub; do not rewrite the skill)

**Step 1:** `packet.md` exactly four content lines plus `STAGE` on the PATHS line:

```
FROM: <registered agent>
TO: <registered agent>
SUMMARY: <investigation, employee/task ids masked>
PATHS: <owned paths> · STAGE: docs/delivery/<name>/stages/<peer>.md
```

**Step 2:** `./tests/guardrails.test.sh` — packet stub expects PASS; Interface / coordinator / read-only still FAIL.

**Step 3: Commit**

```bash
git add skills/delivery-templates/packet.md skills/delivery-templates/SKILL.md
git commit -m "feat: no-re-ask packet stub"
```

---

### Task 3: `peer-router` agent + reviewer Bash guard

**Files:**
- Create: `agents/peer-router.md`
- Modify: `scripts/enforce-reviewer-readonly.sh` (`REVIEWERS` regex adds `peer-router`; comment “three” → “four”)
- Modify: `docs/read-only-by-design.md` if it lists the three reviewers by name — add `peer-router`

**Step 1:** Frontmatter like tech-lead: `disallowedTools: Edit, Write`, tools `Read, Bash, Grep, Glob, Skill`. `model: sonnet`. Description must say: use **only** when `--adaptive` and a packet names a peer; do **not** use on the default Supervisor path. Body: Read the packet; `STATUS: done` + `VERIFIED:` valid or reject (unknown TO, missing labels, unmasked ids); never Agent a peer; `coordinator persists your stage file`. No `isolation: worktree`.

**Step 2:** `REVIEWERS='(tech-lead|security-engineer|performance-engineer|peer-router)'`

**Step 3:** `./tests/guardrails.test.sh` — read-only count 4 and peer-router sed-i block PASS. Interface / coordinator needles still FAIL.

Inventory will FAIL on agent count 18 vs claims 17 until Task 5. Do not pin hash. Do not bump VERSION.

**Step 4: Commit**

```bash
git add agents/peer-router.md scripts/enforce-reviewer-readonly.sh docs/read-only-by-design.md
git commit -m "feat: peer-router validates Adaptive packets"
```

---

### Task 4: Interface + coordinator

**Files:**
- Modify: all nine pipeline `commands/*.md` Interface blockquotes (byte-identical). Also `argument-hint` where present: add `--adaptive`.
- Modify: `agents/delivery-coordinator.md` Working interface — the five needles from Task 1, each count **1**. Copy-then-fill the packet stub. Do not spawn `peer-router` unless `--adaptive`. Do not let specialists Agent a peer.

The nine carriers are the commands that already grep for `Close file on disk` (same set).

**Step 1:** Append the exact Interface sentence from Global constraints. Verify:

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

**Step 2:** `./tests/guardrails.test.sh` — Interface + coordinator needles PASS. ALL GREEN except inventory agent-count / `coordinator_hash`.

**Step 3: Commit**

```bash
git add commands/*.md agents/delivery-coordinator.md
git commit -m "feat: --adaptive packet handoff on the Interface"
```

---

### Task 5: Inventory 18 + eval case wiring

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json` — `17-agent` / `17 specialists` → `18` (version stays **2.0.0**)
- Modify: `README.md` claims that inventory greps (`all 17 agents`, Gemini `17 specialists`)
- Modify: `scripts/build-gemini-extension.py` if it claims `17-agent`
- Modify: `tests/eval/run-evals.sh` — `OPT_IN_CASES` adds `feature-adaptive`; `case_prompt` `/make-feature Tag --api --adaptive`; `case_desc`; `checks_feature_adaptive` (call `checks_feature`, then packet + handoff checks)
- Modify: `docs/evals/2026-08-06-check-audit.md` `Tally: 45` → new count (45 + the new `check_*` lines)
- Modify: `tests/eval/baseline.json` — add `feature-adaptive` ceilings copied from `feature` ($8.50 / 1900s / 14.5M). Do **not** pin `coordinator_hash` yet.
- Modify: `tests/eval/README.md` if it lists opt-in cases
- Modify: `scripts/body_budget.json` if `peer-router` or coordinator lines trip `check_body_budget.py`

Packet helper (eval, Adaptive case only): `docs/delivery/*/packets/*-to-*.md` exists; file contains `FROM:`, `TO:`, `SUMMARY:`, `PATHS:`; `TO:` basename is a registered `agents/*.md`. Handoff: `grep -qiE 'handoff' "$LOG" || grep -qiE 'handoff' close.md`. Do not grep `stream.jsonl`.

**Step 1:** Implement. Rebuild:

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 scripts/check-hook-sync.py
python3 scripts/check_body_budget.py
```

Expected: guardrails ALL GREEN. Inventory FAIL only on `coordinator_hash`. Counts: agents=18, guardrails=6, read-only 4.

**Step 2: Commit**

```bash
git add .claude-plugin/ .cursor-plugin/ README.md scripts/build-gemini-extension.py tests/eval/ docs/evals/2026-08-06-check-audit.md gemini/ scripts/body_budget.json
git commit -m "feat: 18-agent inventory and feature-adaptive eval case"
```

---

### Task 6: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`
- Modify: `docs/README.md` Open row — 2.1 in progress citing this design; 2.2 still waits

Do **not** retitle to `[2.1.0]`. Do not claim the billed gate passed.

```bash
git add CHANGELOG.md docs/README.md
git commit -m "docs: Unreleased 2.1 Adaptive opt-in"
```

---

### Task 7: Gemini / Codex mirrors

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

If rebuild diffs, commit `chore: rebuild Gemini and Codex mirrors for Adaptive`. If no diff, do not empty-commit.

---

### Task 8: Billed `feature-adaptive` pin

**Do not run until Tasks 1–7 are green locally.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature-adaptive
```

Receipt: `docs/evals/2026-08-23-run-18.md` (or next date). Record: packet PASS/FAIL, `peer-router.md`, handoff line, close file, basename, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If Adaptive file checks PASS** and close file PASSes: bump `VERSION` + five manifests to **2.1.0**. Retitle changelog `[2.1.0]`. Move Open: 2.1 closed, 2.2 waits. Commit `release: 2.1.0 — Adaptive opt-in (packet + peer-router)`.

**If they FAIL:** pin the hash anyway, leave VERSION at 2.0.0, leave Unreleased. Commit `docs: eval run 18 — <what missed>`. Do not loosen helpers. Do not raise ceilings. Do not start 2.2.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M tokens
- Accepting `VERIFIED (`
- Specialists Agent-ing a peer
- Spawning `peer-router` without `--adaptive`
- `graph.md` / 2.2
- A seventh guardrail script
- Making Adaptive the default `/make-feature`
