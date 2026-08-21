# Guild 2.0 close.md Bash write deny Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deny Bash that writes `docs/delivery/*/close.md`, so the existing Write|Edit shape hook can see the payload — then billed-pin. Do not ship 2.0.0 unless `check_delivery_close_file` PASSes.

**Architecture:** Run 16 wrote close.md with `cat > … <<'EOF'`; the Write|Edit hook never fired. This slice registers `enforce-close-file.sh` on the Bash matcher and denies those write vectors without parsing the heredoc. Helper stays `^VERIFIED:`. Interface unchanged. No seventh script.

**Tech Stack:** Bash hook + guardrail harness, Gemini/Codex rebuild, one billed `claude -p` `feature` run.

**Spec:** [docs/plans/2026-08-21-guild-v2-close-bash-design.md](2026-08-21-guild-v2-close-bash-design.md)

---

## Global constraints

- Stay on `feat/close-md-bash`. This is a 2.0 follow-up, not 2.1 / 2.2.
- Do **not** loosen `check_delivery_close_file` to accept `VERIFIED (`.
- Do **not** uncomment `check_subagent_log`.
- Do **not** raise `feature` `max_usd` ($8.50), `EVAL_TIMEOUT` (1200), or the 14.5M token ceiling.
- Do **not** drop existing overwrite / next-Write / ban / stub-copy / Write|Edit bounce expects.
- Do **not** add a seventh guardrail script.
- Interface block stays byte-identical. Do not edit `commands/*.md`.
- Do **not** bump `VERSION` until Task 6’s billed close-file helper PASSes.
- Worktree: `/Users/developer/Projects/Personal/laravel-claude-agents/.claude/worktrees/close-md-bash`.

---

### Task 1: Failing ratchets

**Files:**
- Modify: `tests/guardrails.test.sh`

**Step 1:** After the existing `enforce-close-file.sh` Write|Edit expects, add Bash fixtures. Inline JSON like the neighbors (no extra locals). `BLOCK=2` `ALLOW=0` already defined.

```bash
expect "close.md Bash cat-redirect blocks" "$BLOCK" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"cat > docs/delivery/tag/close.md <<EOF\njournal\nEOF"}}')"
expect "close.md Bash read allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"cat docs/delivery/tag/close.md"}}')"
expect "php artisan test allows" "$ALLOW" \
  "$(run_hook enforce-close-file.sh '{"tool_input":{"command":"php artisan test --compact"}}')"
expect "FALLBACK (no jq/python3): close.md Bash write still blocks" "$BLOCK" \
  "$(run_hook_noparsers enforce-close-file.sh '{"tool_input":{"command":"cat > docs/delivery/tag/close.md <<EOF\nx\nEOF"}}')"
```

Those four are **red** until Task 2 (today a Bash payload is not a close.md Write path, so the script exits 0 — `close.md Bash cat-redirect blocks` expected 2 got 0).

Next to the existing coordinator hook-bounce expect, add:

```bash
expect "coordinator forbids Bash writes of close.md" "1" \
  "$(grep -c 'Bash must not write close.md' "$COORD")"
```

That needle is **0** today. Keep the six Write|Edit expects unchanged.

**Step 2:**

```bash
./tests/guardrails.test.sh
```

Expected FAIL on the four new Bash expects plus the coordinator needle.

**Step 3: Commit**

```bash
git add tests/guardrails.test.sh
git commit -m "test(guardrails): ratchet Bash must not write close.md"
```

---

### Task 2: Bash deny in enforce-close-file.sh + wiring

**Files:**
- Modify: `scripts/enforce-close-file.sh`
- Modify: `hooks/hooks.json` (add the same script to the Bash matcher list)
- Modify: `install.sh` (`desired`: `("PreToolUse", "Bash", "./scripts/enforce-close-file.sh")`)
- Modify: `README.md` Guardrail table row for `enforce-close-file.sh` — also Bash writes, not only Write|Edit. Example JSON: add the command under the Bash matcher if that example lists every Bash hook.

**Step 1:** In the script, after extracting the Write|Edit path/body (or before, branching on presence of `tool_input.command`):

- If `tool_input.command` is set (Bash): flatten newlines. If it **writes** `docs/delivery/` … `close.md` (`>`, `>>`, `tee`, heredoc `<<` onto that path) → same `deny` (or a sibling message: use the Write tool; copy the stub). Do not parse heredoc labels.
- Read-only `cat docs/delivery/tag/close.md` with no redirect → exit 0.
- Empty command → fall through; if no close.md Write path either, exit 0.
- No-parser fallback: if raw stdin looks like a write of `docs/delivery` + `close.md` (`>` or `tee` or `<<`) → deny.

Keep the existing Write|Edit shape check. Do not match `skills/delivery-templates/close.md`.

**Step 2:** Wire Bash matcher. Do not duplicate the script file.

**Step 3:**

```bash
./tests/guardrails.test.sh
python3 scripts/check-hook-sync.py
```

Expected: six Write|Edit + four Bash fixtures PASS. Coordinator needle still FAIL until Task 3. Hook-sync still **7** names.

**Step 4: Commit**

```bash
git add scripts/enforce-close-file.sh hooks/hooks.json install.sh README.md
git commit -m "feat: Bash must not write close.md"
```

---

### Task 3: Coordinator needle + Gemini/Codex

**Files:**
- Modify: `agents/delivery-coordinator.md` (Close file block)
- Modify: `gemini/hooks/hooks.json` (`run_shell_command` matcher, next to the other Bash guards)
- Modify: `scripts/build-gemini-extension.py` if regen would wipe that list
- Modify: `scripts/build-codex-extension.py` (add enforce-close-file.sh to the Codex Bash matcher)

**Step 1:** Coordinator, exact bytes **once**: `Bash must not write close.md`. Keep overwrite / next-Write / ban / stub-copy / Write|Edit bounce (each count 1). Do not edit `commands/*.md`.

**Step 2:** Gemini + Codex generators. Rebuild:

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
python3 scripts/check_inventory_sync.py
python3 scripts/check-hook-sync.py
```

Expected: ALL GREEN guardrails. Inventory fails on `coordinator_hash` until Task 6 — do not pin. Inventory counts stay guardrails=6, codex_hooks=5. If body_budget trips, raise coordinator lines only as much as needed.

**Step 3: Commit**

```bash
git add agents/delivery-coordinator.md gemini/ scripts/build-gemini-extension.py scripts/build-codex-extension.py scripts/body_budget.json
git commit -m "feat: coordinator forbids Bash writes of close.md"
```

(Omit body_budget.json if unchanged. Include generated `codex/` / `gemini/` diffs.)

---

### Task 4: Changelog Unreleased

**Files:**
- Modify: `CHANGELOG.md` under `[Unreleased]`

Do **not** retitle to `[2.0.0]`. Add a Changed bullet: Bash must not write `close.md`; use Write so the shape hook can see the payload. Do not claim the billed gate passed.

```bash
git add CHANGELOG.md
git commit -m "docs: Unreleased close.md Bash write deny"
```

---

### Task 5: Gemini coordinator mirror (if Task 3 rebuild already included it, skip empty commit)

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
./tests/guardrails.test.sh
```

```bash
git add gemini/ codex/
git commit -m "chore: rebuild Gemini and Codex mirrors for close.md Bash deny"
```

If no diff, do not empty-commit.

---

### Task 6: Billed `feature` pin

**Do not run until Tasks 1–5 are green locally.**

```sh
KEEP_TRANSCRIPT=1 KEEP_WORKDIR=1 ./tests/eval/run-evals.sh feature
```

Receipt: `docs/evals/2026-08-21-run-17.md` (or next date). Record: close file PASS/FAIL, whether transcript still has Bash `cat > close.md`, basename, cost vs $8.50, timeout, tokens vs 14.5M. Pin `coordinator_hash`. `waivers: []`.

**If `check_delivery_close_file` PASSes** and basename PASSes: bump `VERSION` + five manifests to **2.0.0**. Retitle changelog `[2.0.0]`. Move the Open row to Closed. Commit `release: 2.0.0 — Supervisor complete (close file on disk)`.

**If either file check FAILs:** pin the hash anyway, leave VERSION at 1.45.0, leave Unreleased. Commit `docs: eval run 17 — <what missed>`. Do not loosen the helper. Do not raise ceilings.

Do not tag until CI is green on the PR.

---

## Out of bounds

- Uncommenting `check_subagent_log`
- Raising `$8.50` / 1200s / 14.5M tokens
- Accepting `VERIFIED (`
- Editing the nine-command Interface block
- A seventh guardrail script
- Parsing heredoc labels to allow Bash writes
- Peer handoff, router agent, `graph.md`
