# Agent orchestration audit — 2026-08-12

**Trigger:** docs/superpowers/specs/2026-08-12-agent-orchestration-audit-design.md
— a full-system check for two previously-fixed bug shapes (Interface
placement, tool-grant correctness) plus three adjacent contract-consistency
dimensions.

**Scope:** agents/*.md (17 files), commands/*.md (13 files, as of the pre-`/audit-agents` tree), hooks/hooks.json
+ scripts/*.sh, docs/read-only-by-design.md.

**Verdict:** DRIFT-FOUND

## Dimension 1 — Interface placement

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| agents/delivery-coordinator.md | 22 | Rule "Write/Edit only under `docs/**` — … never to build" governs the orchestrating main thread in a command-driven run, but lives only in delivery-coordinator.md's body. None of the 9 pipeline commands' shared `> **Interface:**` block states this write-scope restriction, so a command-driven main thread has no explicit prohibition against editing app code itself — the same "rule needed by main thread, stranded in an unloaded agent body" shape fixed in v1.41.0. | Blocking | Add "Write/Edit only under `docs/**`, never to build app code" to the shared Interface block in all 9 commands. |
| agents/delivery-coordinator.md | 98 | Rule "`docs/team/decisions.md` exists → check the ask doesn't re-litigate a recorded rejection" governs main-thread briefing behavior but is absent from the shared Interface block and from every command body. | Nit | Add a one-line "check `docs/team/decisions.md` before re-proposing a rejected approach" note to the shared Interface block. |
| agents/delivery-coordinator.md | 99 | Rule "Three re-plans on one delivery is a scoping failure — stop and hand the shape of the problem back to the human" (re-plan escalation threshold) governs main-thread behavior but is absent from the shared Interface block, which only states that growing past budget is a re-plan, with no escalation threshold. | Nit | Add the 3-re-plan escalation threshold to the shared Interface block's re-plan sentence. |
| agents/delivery-coordinator.md | 105 | Rule that a specialist brief must "quote the taught rules from `docs/team/conventions.md` that bind this stage's work" governs what the main thread's own brief must contain, but is absent from the shared Interface block. | Nit | Add "quote binding `docs/team/conventions.md` rules in each specialist brief" to the shared Interface block. |
| agents/delivery-coordinator.md | 109 | Rule "A subagent's 'done' is a claim, not a fact. Verify before advancing: artifact exists at the stated path; run the brief's success criteria yourself" governs main-thread behavior. The 9 commands' Interface block only requires re-briefing on an empty `VERIFIED` / missing `NOT-CHECKED`; it never requires the main thread to independently re-run success criteria before its own closing `VERIFIED` line — risking a closing `VERIFIED` that relays an unrun claim rather than commands the orchestrator itself ran. | Blocking | Add "verify before advancing — re-run the brief's own success criteria yourself, don't just accept a specialist's `STATUS: done`" to the shared Interface block. |
| agents/delivery-coordinator.md | 109 | Rule treating a substantive (not merely missing) `NOT-CHECKED` as an unverified stage requiring re-brief/escalation is absent from the shared Interface block, which only handles the missing-field case. | Nit | Extend the Interface block's `NOT-CHECKED` handling to cover a substantive `NOT-CHECKED`, not just a missing one. |
| agents/delivery-coordinator.md | 110, 135 | Rule "Never patch a subagent's work" / "Builder/reviewer work yourself? … Stop. Delegate." governs main-thread behavior but is not echoed anywhere in commands/: `grep -rn "patch a subagent" commands/` returns nothing. The shared `> **Interface:**` block (byte-identical across all 9 pipeline commands) contains no such guard either. The 4 build commands (make-feature.md, add-policy.md, refactor-to-action.md, ship-checklist.md) carry no equivalent rule anywhere in their bodies. So none of the 9 pipeline commands have a stated guard against the main thread patching a specialist's work directly — the rule lives only in delivery-coordinator.md's body, unreachable by a command-driven run. | Blocking | Move "never patch a subagent's work — re-brief or escalate instead" into the shared Interface block so all 9 commands carry it uniformly. |
| agents/delivery-coordinator.md | 111 | Rule to flush resume state (board as printed, open lanes + owned paths, pending question, options offered) to `docs/delivery/<feature>/log.md` before blocking on a checkpoint governs main-thread behavior but is absent from the shared Interface block's checkpoint guidance. | Nit | Add "flush resume state to the delivery log before blocking on a checkpoint" to the shared Interface block. |
| agents/delivery-coordinator.md | 111 | Rule that a stale `▶` lane (aging past its expected envelope) must be chased, never left stale across a whole exchange, governs main-thread behavior but is absent from the shared Interface block's board guidance. | Nit | Add a staleness-chasing sentence for aging `▶` lanes to the shared Interface block. |

## Dimension 2 — Tool-grant correctness

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| No findings. | | | | |

Every write/edit/run obligation stated in an Interface block or agent body has its required tool present in that same file's frontmatter grant. In particular the v1.41.0 harvest clause ("persist `docs/team/stack.md`", "maintain `docs/delivery/<name>/log.md`") is present verbatim in all 9 commands' Interface blocks (e.g. commands/make-feature.md:11), and each of those 9 commands' `allowed-tools:` line 4 includes `Write, Edit` — the originally-fixed gap remains closed. The reviewer confirmed this from frontmatter alone, not from a `--dangerously-skip-permissions` run.

## Dimension 3 — Stage-return & progress-board contract compliance

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| agents/delivery-coordinator.md | 25–61 | Fans out to 16 specialist subagents (per its own Phase/Owner/Artifact table) but carries no `> **Interface:**` blockquote and no documented note explaining the deliberate omission. Its `## Working interface` section (lines 25–61) is a richer superset covering the same ground (progress board, stage-return shape, checkpoint prompt) but nothing states this is an intentional substitution rather than a missed contract. | Should-fix | Add a one-line note under `## Working interface` stating it is delivery-coordinator's own superset of the shared Interface contract, so the blockquote's absence reads as deliberate. |

All 9 command files carrying a `> **Interface:**` block (commands/add-policy.md:11, add-test.md:11, audit-n-plus-one.md:11, make-feature.md:11, optimize-query.md:11, refactor-to-action.md:11, review-pr.md:11, ship-checklist.md:11, upgrade-laravel.md:11) are byte-identical (md5 `bfa19afc57ad77b54791c91823eff20c`) — no drift found there. commands/board.md, commands/console.md, and commands/teach.md fan out to at most one specialist or none, so the "2+ subagents, no Interface block" check does not apply to them.

## Dimension 4 — Artifact routing accuracy

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| agents/tech-lead.md | 29 | Writes `docs/tech-debt.md`; no corresponding row exists in delivery-coordinator.md's Phase/Owner/Artifact table (no "tech debt" phase at all). | Should-fix | Add a "Tech debt / tech-lead / `docs/tech-debt.md`" row to the routing table. |
| agents/database-developer.md | 71 | Writes `docs/db/<migration>.md`; the table's "Database impl" row (delivery-coordinator.md:75) lists only "Migrations, models, factories, seeders" with no docs/ path. | Should-fix | Add `docs/db/<migration>.md` to the "Database impl" row's Artifact column. |
| agents/ui-ux-designer.md | 28, 36 | Writes/updates `docs/design/system.md`; the table's "Design" row (delivery-coordinator.md:72) only covers the per-feature `docs/design/<feature>/*` pattern, not the shared `system.md` file. | Should-fix | Add `docs/design/system.md` to the "Design" row's Artifact column. |
| agents/product-owner.md | 37 | Writes `docs/backlog/backlog.md`; the table's "Prioritization" row (delivery-coordinator.md:70) only lists the per-story `docs/backlog/<story-id>.md` pattern. | Should-fix | Add `docs/backlog/backlog.md` to the "Prioritization" row's Artifact column. |
| agents/scrum-master.md | 50, 52 | Writes `docs/sprints/<sprint-id>-retro.md` and `docs/sprints/health-<yyyy>-W<ww>.md`; the table's "Delivery rhythm" row (delivery-coordinator.md:85) names only the generic "blockers, retros" text, not these literal filename patterns. | Nit | Spell out the retro and sprint-health filename patterns in the "Delivery rhythm" row's Artifact column. |
| agents/delivery-coordinator.md:104,111–113; commands/add-policy.md, add-test.md, audit-n-plus-one.md, make-feature.md, optimize-query.md, refactor-to-action.md, review-pr.md, ship-checklist.md, upgrade-laravel.md (each :11); commands/teach.md:9; commands/team-hygiene.md:32 | various | Coordinator-level bookkeeping writes (`docs/team/stack.md`, `docs/team/conventions.md`, `docs/team/decisions.md`, `docs/delivery/<name>/log.md`) appear nowhere in delivery-coordinator.md's Phase/Owner/Artifact table, which is scoped to specialist-owned deliverables. | Nit | Add a documentation line noting the routing table covers specialist deliverables only, and that team-ledger bookkeeping is the coordinator's own cross-cutting responsibility (or add an explicit "Bookkeeping / delivery-coordinator / `docs/team/*`, `docs/delivery/*/log.md`" row). |

All 17 rows of delivery-coordinator.md's routing table (lines 67–85) were cross-checked against their named Owner's own file — every Artifact path is referenced in its Owner's file. No table row promises a step nothing implements.

## Dimension 5 — Read-only enforcement

| File | Line | Finding | Severity | Proposed fix |
| ---- | ---- | ------- | -------- | ------------ |
| No findings. | | | | |

agents/tech-lead.md, agents/security-engineer.md, agents/performance-engineer.md each carry `disallowedTools: Edit, Write` (line 5), have no `Write`/`Edit` in their `tools:` list (line 4), and state explicitly in their bodies that they never modify files (tech-lead.md:30,121; security-engineer.md:28; performance-engineer.md:26). scripts/enforce-reviewer-readonly.sh still detects the three read-only agent types via its `REVIEWERS='(tech-lead|security-engineer|performance-engineer)'` pattern (line 19) and the `AGENT_TYPE` extraction from the PreToolUse payload (line 37), scoping the write-shaped-Bash block to exactly those three types (line 51). hooks/hooks.json:17 wires the script into the `PreToolUse` `Bash` matcher.

## Summary

- Blocking: 3
- Should-fix: 5
- Nits: 8
