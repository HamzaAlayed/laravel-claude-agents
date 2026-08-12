# Agent Orchestration Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a one-time, full-system audit of the Guild's orchestration contract (Interface placement, tool grants, stage-return consistency, artifact routing, read-only enforcement) across all 17 agents + 13 commands, then build two repeatable ways to catch the same class of drift going forward: a free static `/audit-agents` command and two new runtime assertions on the existing `feature` eval case.

**Architecture:** The one-time audit fans out 5 dimension-focused review agents in parallel (mirroring `/review-pr`'s own fan-out/aggregate shape) and writes a findings report. The same 5 prompts get baked verbatim into a new `commands/audit-agents.md`, which adds diff-scoping and a CLEAN/DRIFT-FOUND verdict so it can be re-run cheaply after any agent/command edit. A second, independent layer adds two `check_*` assertions to the eval harness's existing `feature` case, since only a real coordinator run — not static file review — can prove the contract is followed, not just declared.

**Tech Stack:** Markdown agent/command prompt files (YAML frontmatter + body), Bash (`tests/eval/run-evals.sh`), the `Agent` tool for fan-out.

## Global Constraints

- **Scope:** `agents/*.md` (17 files), `commands/*.md` (13 files), `hooks/hooks.json` + the guard scripts it wires up, `docs/read-only-by-design.md`. (spec §Scope)
- **Out of scope:** the console UI, the evals cost-tracking scripts, and any change to agent *capabilities*. (spec §Scope)
- **Report-only:** audits/reviewers never edit files during this project — findings are reported, fixes are separate follow-up work reviewed on its own. (spec §1, §Non-goals)
- **No new eval fixture:** layer B rides on the existing opt-in `feature` case in `tests/eval/run-evals.sh`; no new fixture app or case. (spec §3, §Non-goals)
- **No CI/`/ship-checklist` wiring** as part of this project. (spec §Non-goals)
- **`/audit-agents` omits the shared `> **Interface:**` block** that the other 9 fan-out commands carry, and documents why in its own body, so a later audit run doesn't flag its own absence as drift. (spec §2, addendum)

---

## File Structure

- **Create:** `docs/evals/2026-08-12-orchestration-audit.md` — the one-time audit's findings report (Task 2).
- **Create:** `commands/audit-agents.md` — the repeatable static-audit command (Task 3).
- **Modify:** `tests/eval/run-evals.sh` — one new check function (after `check_log_anywhere`, ~line 302) and three new calls inside `checks_feature()` (~line 438) (Task 5).

No other files are created or modified by this plan.

---

### Task 1: Validate the 5 dimension-audit prompts against known historical bugs

**Files:**
- None created or modified — this task produces the finalized wording of 5 review prompts, used verbatim by Task 2 and Task 3.

**Interfaces:**
- Consumes: `CHANGELOG.md`'s `[1.41.0]` entry, commit `64eb589` (harvest interface fix), commit `c41b9f9` (allowed-tools gap fix), `docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md`.
- Produces: the 5 finalized dimension prompts below (verbatim text), consumed by Task 2 step 2 and Task 3 step 1.

- [ ] **Step 1: Read the harvest-placement bug's diff**

Run:
```bash
git show 64eb589 --stat
git show 64eb589
```
Expected: the diff moves a harvest requirement out of `agents/delivery-coordinator.md`'s body and into the shared `> **Interface:**` blockquote replicated across the 9 commands — confirming the bug shape Dimension 1 (below) targets: a rule that must govern main-thread command behavior, stated only in an agent body a command-driven run never loads.

- [ ] **Step 2: Read the tool-grant gap's diff**

Run:
```bash
git show c41b9f9 --stat
git show c41b9f9
```
Expected: the diff adds `Write`/`Edit` to the 9 commands' `allowed-tools` frontmatter, because the harvest clause required writing two files and a `--dangerously-skip-permissions` test run had wrongly been treated as proof the grant existed — confirming the bug shape Dimension 2 (below) targets.

- [ ] **Step 3: Confirm the finalized prompts below would have caught both bugs, then lock them in**

Read the 5 prompts below. Confirm: Dimension 1's prompt, applied to the pre-`64eb589` state, would have flagged the harvest requirement as "governs: main-thread — currently placed in: agent body." Confirm: Dimension 2's prompt, applied to the pre-`c41b9f9` state, would have flagged the harvest clause as "requires: Write/Edit — granted: no." If either prompt would NOT have caught its bug, rewrite it now before proceeding to Task 2. (In practice, the wording below was written to name both bugs explicitly, so this step is a read-through confirmation, not a rewrite.)

**Finalized dimension prompts** (used verbatim in Task 2 and Task 3 — `{FILE_LIST}` is replaced by the concrete scoped file list computed in each task's own step 1):

**Dimension 1 — Interface placement:**
```
You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each file, determine whether it states a rule that is meant to govern behavior the MAIN THREAD performs inline when a human runs a slash command directly — as opposed to a rule that only binds a spawned subagent. If such a rule exists, check whether it is stated inside the file's own `> **Interface:**` blockquote (the block that is meant to be byte-identical across every multi-stage command), or only inside an agent's own body section (for example agents/delivery-coordinator.md) that a command-driven run never loads. A rule that needs to bind main-thread command behavior but lives only in an agent body is the exact bug shape fixed in v1.41.0 (see docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md and CHANGELOG.md's [1.41.0] entry) — flag it. Report every instance found as: `file:line — <the rule, quoted or paraphrased> — governs: <main-thread / subagent / both> — currently placed in: <Interface block / agent body / elsewhere>`. Do not assign a severity or propose a fix — findings only.
```

**Dimension 2 — Tool-grant correctness:**
```
You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each command or agent file, list every obligation stated in its Interface block or body that requires a write, edit, or run action — for example 'persist docs/team/stack.md', 'maintain the delivery log', 'run php artisan test'. For each obligation, check that same file's YAML frontmatter (`tools:` for an agent file, `allowed-tools:` for a command file) and confirm the specific tool that action needs (Write, Edit, Bash, etc.) is actually listed there. Flag every obligation whose required tool is missing from the frontmatter grant. This is the exact gap fixed in v1.41.0: the harvest clause required Write/Edit that the 9 commands' `allowed-tools` did not originally list, and a test run under `--dangerously-skip-permissions` had wrongly been treated as proof it worked, when that flag bypasses tool permission checks entirely and proves only that the model complies, not that the grant exists (see CHANGELOG.md's [1.41.0] entry). Do not accept a permissive test run as proof of a real grant — check only the declared frontmatter. Report every gap as: `file:line (frontmatter) — obligation: <text> — requires: <tool> — granted: yes/no`. Findings only, no severity or fix proposal.
```

**Dimension 3 — Stage-return & progress-board contract compliance:**
```
You are auditing the Laravel Guild agent pack's own prompt files for internal consistency. Read every file in this list: {FILE_LIST}. Identify every file that contains a `> **Interface:**` blockquote. These are supposed to be byte-identical across all files that carry one. Compare their exact text and report any file whose Interface block differs from the others, quoting the differing line(s). Separately, identify every command or agent that fans out to 2 or more subagents but has NO `> **Interface:**` blockquote at all. For each one found, check whether that same file contains its own explicit note explaining why it deliberately omits the shared Interface contract (for example, a note that it has no target-project stack facts or delivery artifact to harvest). If such a documented exception exists, do NOT report it as a finding. If no such note exists, report it as a finding. Report as: `file — Interface block differs: <quoted differing text>` or `file — fans out to N subagents, no Interface block, no documented exception`. Findings only, no severity or fix proposal.
```

**Dimension 4 — Artifact routing accuracy:**
```
You are auditing the Laravel Guild agent pack's own prompt files for consistency between what's promised and what's implemented. Read agents/delivery-coordinator.md and find its artifact routing table (the table with columns Phase / Owner / Artifact). For each row, find the specialist agent file or command file that is the named Owner, and check whether that owner's own file references writing to the stated Artifact path anywhere in its body (grep for the path string or its containing directory). Report any table row whose Artifact path is not referenced anywhere in the Owner's own file — the table promises a delivery step nothing implements. Separately, read every other file in this list: {FILE_LIST}. For each one, note every docs/ path it says it writes to, and report any such path that does not appear anywhere in delivery-coordinator.md's routing table — an undocumented artifact. Report as: `table row: <Phase>/<Owner>/<Artifact> — referenced in <owner file>: yes/no` and separately `undocumented write: <file> writes to <path>, not in routing table`. Findings only, no severity or fix proposal.
```

**Dimension 5 — Read-only enforcement:**
```
You are auditing the Laravel Guild agent pack's read-only-reviewer guarantee. Read agents/tech-lead.md, agents/security-engineer.md, agents/performance-engineer.md, and docs/read-only-by-design.md. For each of the three agent files, confirm all three of: (1) its YAML frontmatter includes `disallowedTools: Edit, Write` (or an equivalent explicit denial) even though `memory: project` would otherwise auto-grant Write/Edit; (2) its `tools:` list contains no `Write` or `Edit` entry; (3) its body contains an explicit statement that it does not modify files. Then read hooks/hooks.json and scripts/enforce-reviewer-readonly.sh, and confirm the script still contains logic that detects when the calling agent is one of these three read-only types before blocking write-shaped Bash. Report any of the three agent files missing any of the three properties above, and report if the guard script no longer contains a mechanism to identify these agent types. Report as: `file — missing: <property>` or `scripts/enforce-reviewer-readonly.sh — no longer detects read-only agent types`. Findings only, no severity or fix proposal.
```

- [ ] **Step 4: No commit** — this task changes no tracked file. Proceed to Task 2 with the 5 prompts above.

---

### Task 2: Run the one-time full-system audit

**Files:**
- Create: `docs/evals/2026-08-12-orchestration-audit.md`

**Interfaces:**
- Consumes: the 5 finalized dimension prompts from Task 1 (reproduced in full below).
- Produces: `docs/evals/2026-08-12-orchestration-audit.md`, read by Task 4 for comparison.

- [ ] **Step 1: Build the scoped file list**

Run:
```bash
ls agents/*.md commands/*.md scripts/*.sh
```
Combine this output with the two fixed files `hooks/hooks.json` and `docs/read-only-by-design.md` into one list — this is `{FILE_LIST}` for every prompt below.

- [ ] **Step 2: Fan out the 5 dimension reviewers in parallel**

Spawn 5 `Agent` tool calls in a single message (subagent_type: `general-purpose`), one per dimension, each given the prompt below with `{FILE_LIST}` replaced by the concrete list from Step 1. Wait for all 5 to return before continuing.

**Dimension 1 — Interface placement:**
```
You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each file, determine whether it states a rule that is meant to govern behavior the MAIN THREAD performs inline when a human runs a slash command directly — as opposed to a rule that only binds a spawned subagent. If such a rule exists, check whether it is stated inside the file's own `> **Interface:**` blockquote (the block that is meant to be byte-identical across every multi-stage command), or only inside an agent's own body section (for example agents/delivery-coordinator.md) that a command-driven run never loads. A rule that needs to bind main-thread command behavior but lives only in an agent body is the exact bug shape fixed in v1.41.0 (see docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md and CHANGELOG.md's [1.41.0] entry) — flag it. Report every instance found as: `file:line — <the rule, quoted or paraphrased> — governs: <main-thread / subagent / both> — currently placed in: <Interface block / agent body / elsewhere>`. Do not assign a severity or propose a fix — findings only.
```

**Dimension 2 — Tool-grant correctness:**
```
You are auditing the Laravel Guild agent pack's own prompt files for a specific, previously-fixed bug shape. Read every file in this list: {FILE_LIST}. For each command or agent file, list every obligation stated in its Interface block or body that requires a write, edit, or run action — for example 'persist docs/team/stack.md', 'maintain the delivery log', 'run php artisan test'. For each obligation, check that same file's YAML frontmatter (`tools:` for an agent file, `allowed-tools:` for a command file) and confirm the specific tool that action needs (Write, Edit, Bash, etc.) is actually listed there. Flag every obligation whose required tool is missing from the frontmatter grant. This is the exact gap fixed in v1.41.0: the harvest clause required Write/Edit that the 9 commands' `allowed-tools` did not originally list, and a test run under `--dangerously-skip-permissions` had wrongly been treated as proof it worked, when that flag bypasses tool permission checks entirely and proves only that the model complies, not that the grant exists (see CHANGELOG.md's [1.41.0] entry). Do not accept a permissive test run as proof of a real grant — check only the declared frontmatter. Report every gap as: `file:line (frontmatter) — obligation: <text> — requires: <tool> — granted: yes/no`. Findings only, no severity or fix proposal.
```

**Dimension 3 — Stage-return & progress-board contract compliance:**
```
You are auditing the Laravel Guild agent pack's own prompt files for internal consistency. Read every file in this list: {FILE_LIST}. Identify every file that contains a `> **Interface:**` blockquote. These are supposed to be byte-identical across all files that carry one. Compare their exact text and report any file whose Interface block differs from the others, quoting the differing line(s). Separately, identify every command or agent that fans out to 2 or more subagents but has NO `> **Interface:**` blockquote at all. For each one found, check whether that same file contains its own explicit note explaining why it deliberately omits the shared Interface contract (for example, a note that it has no target-project stack facts or delivery artifact to harvest). If such a documented exception exists, do NOT report it as a finding. If no such note exists, report it as a finding. Report as: `file — Interface block differs: <quoted differing text>` or `file — fans out to N subagents, no Interface block, no documented exception`. Findings only, no severity or fix proposal.
```

**Dimension 4 — Artifact routing accuracy:**
```
You are auditing the Laravel Guild agent pack's own prompt files for consistency between what's promised and what's implemented. Read agents/delivery-coordinator.md and find its artifact routing table (the table with columns Phase / Owner / Artifact). For each row, find the specialist agent file or command file that is the named Owner, and check whether that owner's own file references writing to the stated Artifact path anywhere in its body (grep for the path string or its containing directory). Report any table row whose Artifact path is not referenced anywhere in the Owner's own file — the table promises a delivery step nothing implements. Separately, read every other file in this list: {FILE_LIST}. For each one, note every docs/ path it says it writes to, and report any such path that does not appear anywhere in delivery-coordinator.md's routing table — an undocumented artifact. Report as: `table row: <Phase>/<Owner>/<Artifact> — referenced in <owner file>: yes/no` and separately `undocumented write: <file> writes to <path>, not in routing table`. Findings only, no severity or fix proposal.
```

**Dimension 5 — Read-only enforcement:**
```
You are auditing the Laravel Guild agent pack's read-only-reviewer guarantee. Read agents/tech-lead.md, agents/security-engineer.md, agents/performance-engineer.md, and docs/read-only-by-design.md. For each of the three agent files, confirm all three of: (1) its YAML frontmatter includes `disallowedTools: Edit, Write` (or an equivalent explicit denial) even though `memory: project` would otherwise auto-grant Write/Edit; (2) its `tools:` list contains no `Write` or `Edit` entry; (3) its body contains an explicit statement that it does not modify files. Then read hooks/hooks.json and scripts/enforce-reviewer-readonly.sh, and confirm the script still contains logic that detects when the calling agent is one of these three read-only types before blocking write-shaped Bash. Report any of the three agent files missing any of the three properties above, and report if the guard script no longer contains a mechanism to identify these agent types. Report as: `file — missing: <property>` or `scripts/enforce-reviewer-readonly.sh — no longer detects read-only agent types`. Findings only, no severity or fix proposal.
```

- [ ] **Step 3: Aggregate the 5 returns**

For every finding across all 5 dimensions, assign one severity:
- **Blocking** — a tool-grant gap (Dimension 2) or an Interface-placement bug (Dimension 1) that will cause a real run to fail its own contract.
- **Should-fix** — a stage-return/board mismatch (Dimension 3) or an artifact-routing inconsistency (Dimension 4) that degrades quality without breaking a run.
- **Nit** — everything else, including read-only-enforcement gaps (Dimension 5) unless one would let a reviewer actually mutate files (then Blocking).

Write a one-line proposed fix for each finding. De-dupe overlaps between dimensions (e.g. the same file:line flagged by both Dimension 1 and Dimension 3).

- [ ] **Step 4: Write the report**

Write `docs/evals/2026-08-12-orchestration-audit.md`:

```markdown
# Agent orchestration audit — 2026-08-12

**Trigger:** docs/superpowers/specs/2026-08-12-agent-orchestration-audit-design.md
— a full-system check for two previously-fixed bug shapes (Interface
placement, tool-grant correctness) plus three adjacent contract-consistency
dimensions.

**Scope:** agents/*.md (17 files), commands/*.md (13 files), hooks/hooks.json
+ scripts/*.sh, docs/read-only-by-design.md.

**Verdict:** <CLEAN / DRIFT-FOUND>

## Dimension 1 — Interface placement

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| <rows, or "No findings.">

## Dimension 2 — Tool-grant correctness

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| <rows, or "No findings.">

## Dimension 3 — Stage-return & progress-board contract compliance

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| <rows, or "No findings.">

## Dimension 4 — Artifact routing accuracy

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| <rows, or "No findings.">

## Dimension 5 — Read-only enforcement

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| <rows, or "No findings.">

## Summary

- Blocking: <N>
- Should-fix: <N>
- Nits: <N>
```

- [ ] **Step 5: Verify structural completeness**

Run:
```bash
grep -c '^## Dimension' docs/evals/2026-08-12-orchestration-audit.md
```
Expected: `5`.

- [ ] **Step 6: Commit**

```bash
git add docs/evals/2026-08-12-orchestration-audit.md
git commit -m "docs(evals): full-system orchestration audit across 17 agents + 13 commands"
```

---

### Task 3: Build the `/audit-agents` command

**Files:**
- Create: `commands/audit-agents.md`

**Interfaces:**
- Consumes: the 5 finalized dimension prompts from Task 1 (reproduced in full below), `commands/review-pr.md`'s structure as template.
- Produces: `commands/audit-agents.md`, exercised in Task 4.

- [ ] **Step 1: Write the command file**

Create `commands/audit-agents.md`:

````markdown
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
````

- [ ] **Step 2: Verify the file is well-formed**

Run:
```bash
head -5 commands/audit-agents.md
```
Expected: the YAML frontmatter block (`---` / `description:` / `argument-hint:` / `allowed-tools:` / `---`) prints correctly with no syntax errors.

- [ ] **Step 3: Commit**

```bash
git add commands/audit-agents.md
git commit -m "feat: add /audit-agents — repeatable static check of the orchestration contract"
```

---

### Task 4: Verify `/audit-agents` against the one-time audit's findings

**Files:**
- None created or modified (the command's own DRIFT-FOUND output file, if generated during verification, is removed at the end of this task — it's a proof-of-function run, not a second official audit report).

**Interfaces:**
- Consumes: `commands/audit-agents.md` (Task 3), `docs/evals/2026-08-12-orchestration-audit.md` (Task 2).
- Produces: verification confidence only.

- [ ] **Step 1: Test the empty-diff short-circuit**

Invoke `/audit-agents HEAD` (diff base = HEAD, which is always empty against itself).

Expected: the command prints `CLEAN — no agent-facing files changed vs HEAD` immediately, with no `Agent` tool calls made (no reviewer spawned).

- [ ] **Step 2: Test the full-scan path**

Invoke `/audit-agents` with no argument.

Expected: it fans out the 5 reviewers and produces a verdict.
- If Task 2's report (`docs/evals/2026-08-12-orchestration-audit.md`) recorded any Blocking or Should-fix findings, this run's verdict must be **DRIFT-FOUND**, and its written report (`docs/evals/<today>-audit-agents.md`) must reference substantially the same files/dimensions Task 2 flagged (exact wording may differ — these are independent LLM judgments — but the same real issues should surface).
- If Task 2's report recorded zero Blocking/Should-fix findings, this run's verdict must be **CLEAN**.

- [ ] **Step 3: Confirm the documented exception is honored**

Run:
```bash
grep -A2 -i "audit-agents.md" docs/evals/*-audit-agents.md 2>/dev/null
```
Expected: `commands/audit-agents.md` is NOT reported as a Dimension-3 finding for lacking an Interface block — its own documented-exception note should have suppressed that flag. If it IS reported as a finding, the Dimension 3 prompt's exception-handling clause needs strengthening: revise the prompt text in both `commands/audit-agents.md` (Task 3's file) and this plan's Task 1/Task 2 copies, then re-run this step.

- [ ] **Step 4: Clean up the verification artifact**

```bash
git status --porcelain docs/evals/
```
If `docs/evals/<today>-audit-agents.md` shows as untracked, remove it — it was generated only to prove the command works, not to stand as a second official report:
```bash
rm -f docs/evals/$(date +%F)-audit-agents.md
```

- [ ] **Step 5: Commit (only if Step 3 required a prompt fix)**

If Step 3 required revising the Dimension 3 prompt in `commands/audit-agents.md`:
```bash
git add commands/audit-agents.md
git commit -m "fix: strengthen dimension-3's documented-exception detection in /audit-agents"
```
If no fix was needed, skip this step — nothing to commit.

---

### Task 5: Add layer-B runtime assertions to the `feature` eval case

**Files:**
- Modify: `tests/eval/run-evals.sh` (new function after `check_log_anywhere`, ~line 302; three new calls inside `checks_feature()`, ~line 438)

**Interfaces:**
- Consumes: the existing `check_log_anywhere`, `check_file`, `check_file_under`, `record` functions and `$FULL_LOG`/`$WORK` variables already defined in `tests/eval/run-evals.sh`.
- Produces: three new passing/failing checks reported by `./tests/eval/run-evals.sh feature`.

This task is independent of Tasks 1–4 and can run before, after, or in parallel with them.

- [ ] **Step 1: Add the new check function**

In `tests/eval/run-evals.sh`, immediately after the `check_log_anywhere` function (ends at line 302, right before `check_file` at line 304), insert:

```bash
check_stage_return_shape() { # check_stage_return_shape <description>
  # Same LOG-vs-FULL_LOG lesson as check_log_anywhere (run 7, finding 3): a
  # stage return happens mid-run, structurally before $LOG's closing-summary
  # text exists, so this must read $FULL_LOG.
  local label ok=0
  for label in 'STATUS:' 'DID:' 'VERIFIED:' 'NOT-CHECKED:' 'FLAGS:' 'NEXT:'; do
    if ! grep -qiE "$label" "$FULL_LOG"; then
      ok=1
      break
    fi
  done
  record $ok "output: $1"
}
```

- [ ] **Step 2: Add the three new checks to `checks_feature()`**

Change:
```bash
checks_feature() {
  check_file_under "database/migrations" "*tags*.php" "tags migration created"
  check_file_under "app/Models" "Tag.php" "Tag model created"
  check_in_files 'tag' "routes" "route registered for tags"
  check_touched "tests/" "feature test added"
  # The point of this case: the coordinator must delegate, not build it inline.
  check_delegated 2 "work was delegated to specialists"
  # Tranche item 2 — the board declares its budget and completion condition.
  check_log_anywhere 'done when:' "board declares a completion condition"
}
```
to:
```bash
checks_feature() {
  check_file_under "database/migrations" "*tags*.php" "tags migration created"
  check_file_under "app/Models" "Tag.php" "Tag model created"
  check_in_files 'tag' "routes" "route registered for tags"
  check_touched "tests/" "feature test added"
  # The point of this case: the coordinator must delegate, not build it inline.
  check_delegated 2 "work was delegated to specialists"
  # Tranche item 2 — the board declares its budget and completion condition.
  check_log_anywhere 'done when:' "board declares a completion condition"
  # Orchestration-audit layer B (docs/superpowers/specs/2026-08-12-agent-orchestration-audit-design.md §3):
  # static file review can't prove the contract is followed at runtime, only declared on paper.
  check_stage_return_shape "every delegated stage returns the full STATUS/DID/VERIFIED/NOT-CHECKED/FLAGS/NEXT shape"
  check_file "docs/team/stack.md" "harvest persisted the stack snapshot (routing-table artifact)"
  check_file_under "docs/delivery" "log.md" "harvest persisted the delivery log (routing-table artifact)"
}
```

- [ ] **Step 3: Static verification — shellcheck and syntax check**

Run:
```bash
shellcheck tests/eval/run-evals.sh
bash -n tests/eval/run-evals.sh
```
Expected: both exit 0, no new warnings introduced by the added function or calls.

- [ ] **Step 4: Ask before the billed dynamic verification**

Running `./tests/eval/run-evals.sh feature` bills a real `claude -p` session against the fixture app — the harness's own README cites `action`, a comparably-sized case, at $5.16 in run 6. Ask the human before running it:

> "The static checks pass. Confirming the two new checks actually fire requires a billed run of `./tests/eval/run-evals.sh feature` (~$5 based on run 6's comparable `action` case). Run it now, or leave it for the next scheduled pre-release sweep?"

- **If approved:** run `./tests/eval/run-evals.sh feature` and confirm all checks pass, including the three new ones. If `check_stage_return_shape` or the two artifact checks fail on an otherwise-correct run, that itself is a real finding — the harvest fix may not cover this path as completely as v1.41.0's CHANGELOG entry claims; escalate to the human rather than silently loosening the check.
- **If declined:** record in the task's own closing note that the two new checks are verified statically (shellcheck + `bash -n`) but not yet exercised against a live run; they'll be proven at the next scheduled sweep the README already calls for before a release.

- [ ] **Step 5: Commit**

```bash
git add tests/eval/run-evals.sh
git commit -m "test(evals): assert the stage-return contract and harvest artifacts on the feature case"
```

---

## Self-Review Notes

- **Spec coverage:** §1 (one-time audit) → Tasks 1–2. §2 (`/audit-agents`) → Task 3, verified in Task 4. §3 (eval-harness extension) → Task 5. Global Constraints line for the Interface-block addendum → Task 3 step 1's command file. All spec sections have a task.
- **Placeholder scan:** no TBD/TODO; every prompt, file path, and code block is complete text, not a description of what to write.
- **Type/name consistency:** `check_stage_return_shape` is defined once (Task 5 step 1) and called with matching name in Task 5 step 2 — no renamed-function drift. `{FILE_LIST}` is used consistently as the one substitution token across all three copies of the 5 prompts (Tasks 1, 2, 3).
