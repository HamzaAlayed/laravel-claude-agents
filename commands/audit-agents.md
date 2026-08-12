---
description: Audit the agent pack's own orchestration contract — Interface-block placement, tool-grant coverage, stage-return consistency, artifact routing, and read-only enforcement — across every agent and command definition.
argument-hint: [base-branch]
allowed-tools: Agent, Read, Write, Grep, Glob, Bash
---

# Audit agents — orchestration contract check

> **Note on scope:** unlike the pack's other fan-out commands, this one has no target-Laravel-project stack facts or delivery artifact to harvest — it reviews the pack's own prompt files, not application code. It deliberately omits the shared `> **Interface:**` progress-board/harvest block that `review-pr` and the other 8 fan-out commands carry; a later audit run should treat this note, not a missing block, as satisfying dimension 3's Interface-consistency check.

Checks the agent pack's own orchestration contract for drift across 5 dimensions, each targeting a documented historical bug shape (see `docs/superpowers/specs/2026-08-12-agent-orchestration-audit-design.md`). Fans out to 5 ad hoc reviewers, aggregates, returns one verdict. Never edits files.

## What you do

1. **Determine scope.**
   ```
   BASE="${ARGS:-}"
   if [ -n "$BASE" ]; then
     git fetch origin "$BASE" --quiet
     FILES=$(git diff --name-only "$BASE"...HEAD -- 'agents/*.md' 'commands/*.md' 'hooks/**')
   fi
   ```
   - `$BASE` given and `$FILES` empty → print `CLEAN — no agent-facing files changed vs $BASE` and stop. Do not spawn reviewers.
   - `$BASE` given and `$FILES` non-empty → scope is `$FILES`.
   - No `$BASE` → full scan: scope is `agents/*.md`, `commands/*.md`, `hooks/hooks.json`, `scripts/*.sh`, `docs/read-only-by-design.md`.

2. **Fan out** (run in parallel; each reviewer gets the scoped file list from step 1 as `{FILE_LIST}`, reads the files itself, returns findings only — no severity, no fix):

   - **Dimension 1 — Interface placement:**
     ```
     You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each file, determine whether it states a rule that is meant to govern behavior the MAIN THREAD performs inline when a human runs a slash command directly — as opposed to a rule that only binds a spawned subagent. If such a rule exists, check whether it is stated inside the file's own `> **Interface:**` blockquote (the block that is meant to be byte-identical across every multi-stage command), or only inside an agent's own body section (for example agents/delivery-coordinator.md) that a command-driven run never loads. A rule that needs to bind main-thread command behavior but lives only in an agent body is the exact bug shape fixed in v1.41.0 (see docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md and CHANGELOG.md's [1.41.0] entry) — flag it. Report every instance found as: `file:line — <the rule, quoted or paraphrased> — governs: <main-thread / subagent / both> — currently placed in: <Interface block / agent body / elsewhere>`. Do not assign a severity or propose a fix — findings only.
     ```
   - **Dimension 2 — Tool-grant correctness:**
     ```
     You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each command or agent file, list every obligation stated in its Interface block or body that requires a write, edit, or run action — for example 'persist docs/team/stack.md', 'maintain the delivery log', 'run php artisan test'. For each obligation, check that same file's YAML frontmatter (`tools:` for an agent file, `allowed-tools:` for a command file) and confirm the specific tool that action needs (Write, Edit, Bash, etc.) is actually listed there. Flag every obligation whose required tool is missing from the frontmatter grant. This is the exact gap fixed in v1.41.0: the harvest clause required Write/Edit that the 9 commands' `allowed-tools` did not originally list, and a test run under `--dangerously-skip-permissions` had wrongly been treated as proof it worked, when that flag bypasses tool permission checks entirely and proves only that the model complies, not that the grant exists (see CHANGELOG.md's [1.41.0] entry). Do not accept a permissive test run as proof of a real grant — check only the declared frontmatter. Report every gap as: `file:line (frontmatter) — obligation: <text> — requires: <tool> — granted: yes/no`. Findings only, no severity or fix proposal.
     ```
   - **Dimension 3 — Stage-return & progress-board contract compliance:**
     ```
     You are auditing the Laravel Guild agent pack's own prompt files for internal consistency. Read every file in this list: {FILE_LIST}. Identify every file that contains a `> **Interface:**` blockquote. These are supposed to be byte-identical across all files that carry one. Compare their exact text and report any file whose Interface block differs from the others, quoting the differing line(s). Separately, identify every command or agent that fans out to 2 or more subagents but has NO `> **Interface:**` blockquote at all. For each one found, check whether that same file contains its own explicit note explaining why it deliberately omits the shared Interface contract (for example, a note that it has no target-project stack facts or delivery artifact to harvest). If such a documented exception exists, do NOT report it as a finding. If no such note exists, report it as a finding. Report as: `file — Interface block differs: <quoted differing text>` or `file — fans out to N subagents, no Interface block, no documented exception`. Findings only, no severity or fix proposal.
     ```
   - **Dimension 4 — Artifact routing accuracy** (skip if `agents/delivery-coordinator.md` is not in the scoped file list):
     ```
     You are auditing the Laravel Guild agent pack's own prompt files for consistency between what's promised and what's implemented. Read agents/delivery-coordinator.md and find its artifact routing table (the table with columns Phase / Owner / Artifact). For each row, find the specialist agent file or command file that is the named Owner, and check whether that owner's own file references writing to the stated Artifact path anywhere in its body (grep for the path string or its containing directory). Report any table row whose Artifact path is not referenced anywhere in the Owner's own file — the table promises a delivery step nothing implements. Separately, read every other file in this list: {FILE_LIST}. For each one, note every docs/ path it says it writes to, and report any such path that does not appear anywhere in delivery-coordinator.md's routing table — an undocumented artifact. Report as: `table row: <Phase>/<Owner>/<Artifact> — referenced in <owner file>: yes/no` and separately `undocumented write: <file> writes to <path>, not in routing table`. Findings only, no severity or fix proposal.
     ```
   - **Dimension 5 — Read-only enforcement** (skip unless one of `agents/tech-lead.md`, `agents/security-engineer.md`, `agents/performance-engineer.md`, `hooks/hooks.json`, `scripts/enforce-reviewer-readonly.sh` is in the scoped file list):
     ```
     You are auditing the Laravel Guild agent pack's read-only-reviewer guarantee. Read agents/tech-lead.md, agents/security-engineer.md, agents/performance-engineer.md, and docs/read-only-by-design.md. For each of the three agent files, confirm all three of: (1) its YAML frontmatter includes `disallowedTools: Edit, Write` (or an equivalent explicit denial) even though `memory: project` would otherwise auto-grant Write/Edit; (2) its `tools:` list contains no `Write` or `Edit` entry; (3) its body contains an explicit statement that it does not modify files. Then read hooks/hooks.json and scripts/enforce-reviewer-readonly.sh, and confirm the script still contains logic that detects when the calling agent is one of these three read-only types before blocking write-shaped Bash. Report any of the three agent files missing any of the three properties above, and report if the guard script no longer contains a mechanism to identify these agent types. Report as: `file — missing: <property>` or `scripts/enforce-reviewer-readonly.sh — no longer detects read-only agent types`. Findings only, no severity or fix proposal.
     ```

3. **Aggregate.** For each returned finding, assign severity:
   - **Blocking** — a tool-grant gap (Dimension 2) or an Interface-placement bug (Dimension 1) that will cause a real run to fail its own contract.
   - **Should-fix** — a stage-return/board mismatch (Dimension 3) or an artifact-routing inconsistency (Dimension 4) that degrades quality without breaking a run.
   - **Nit** — everything else, including a dimension a reviewer could not check (see step 4).

   Format:
   ```
   # Agent orchestration audit — <date>

   **Verdict:** CLEAN / DRIFT-FOUND

   ## Blocking
   - [dimension] file:line — <finding> → <proposed fix>

   ## Should-fix
   - ...

   ## Nits
   - ...
   ```

4. **A reviewer that fails or times out** is not silently dropped — record it as its own Nit: `[dimension N] could not be checked — <reason>`.

5. **Decide verdict.** Any Blocking or Should-fix finding → **DRIFT-FOUND**. Otherwise → **CLEAN**.

6. **Persist only on DRIFT-FOUND.** Write the report to `docs/evals/$(date +%F)-audit-agents.md` (overwrite if a run already happened today). A CLEAN result is printed only, nothing written.

7. **Do not edit files.** Findings route to a human to apply as a separate step.
