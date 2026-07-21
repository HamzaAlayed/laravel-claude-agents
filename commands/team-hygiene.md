---
description: Consolidate the team knowledge base — detect duplicates, conflicts, stale facts, and dead scopes in docs/team/, propose keep/merge/evict, apply only what the human approves.
argument-hint: (no args — sweeps docs/team/)
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Agent, AskUserQuestion
---

# Team knowledge-base hygiene

The `docs/team/` ledger (conventions.md, stack.md, decisions.md) rots between deliveries: rules get re-taught in new words, corrections contradict old entries, verified facts stop being true, scopes point at deleted code. This sweep finds the rot and proposes the cleanup — the human decides. Corrections that die in a stale ledger get re-made next sprint; so does trust in the ledger.

Delegate the scan to **scrum-master** (cheap, fast, has Bash for Verify commands). Apply edits only after approval.

## What you do

1. **Scope check.** No `docs/team/` directory or all three files missing → say so and stop. Nothing to clean is a fine answer.

2. **Scan** (delegate to scrum-master). For every entry in `conventions.md`, `stack.md`, `decisions.md`, classify:
   - **Duplicate** — two entries state the same rule in different words. Propose: merge into the older entry (it has seniority), keep the clearer wording.
   - **Conflict** — two entries disagree; the update-in-place rule failed somewhere. Propose: keep the newer (note what it superseded), evict the older. Can't tell which is current → flag for the human, propose nothing.
   - **Stale fact** — entry has a **Verify** command; run it (read-only commands only — a Verify that mutates is itself a finding). Fails → propose evict, quoting the failing command and output.
   - **Dead scope** — entry's Scope names a path, agent, or area that no longer exists in the repo. Propose evict.
   Healthy entries are not listed — the proposal table is the exceptions, not an inventory.

3. **Propose.** One table, one row per finding:

   | # | Entry | File | Class | Evidence | Proposal |

   Evidence is concrete: the twin entry's title, the failing Verify output, the missing path. Proposals are `keep / merge into #N / evict / rewrite: <one line>`.

4. **Approve.** Present the table and ask which rows to apply — numbered selection, `AskUserQuestion` when available. Headless or no response → output the table and apply **nothing**; the table is the deliverable.

5. **Apply approved rows only.** Merges keep the surviving entry's Source date and add `(merged <date>)`. Evictions are removed from the ledger and one line is appended to `decisions.md` (`evicted: <title> — <class>, <date>`) so the removal itself is remembered. Never silently delete; never touch unapproved rows.

6. **Report** in the stage-return shape — VERIFIED carries the Verify commands actually run, NOT-CHECKED names any file skipped.

## Rules

- Read-only until step 5; nothing changes without an approved row number.
- One sweep per invocation. Findings you're unsure about go in the table with proposal `keep` and the doubt in Evidence — visibility beats false confidence.
- `CLAUDE.md` and committed configs are out of scope — this maintains the taught ledger, not the repo.
