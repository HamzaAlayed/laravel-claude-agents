---
description: Teach the agent team a project rule or preference — records it in docs/team/conventions.md so every agent applies it from now on.
argument-hint: <rule, preference, or correction — or empty to harvest this session's corrections>
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Teach the team — `{{args}}`

Record a user-taught rule in the team conventions ledger at `docs/team/conventions.md`. Every agent in this pack reads that ledger before starting work and treats its entries as overrides of their defaults — this is how a correction given once stops being given twice.

## What you do

1. **Get the rule.**
   - `{{args}}` provided → that's the rule. Capture the user's wording; tighten, don't reinterpret.
   - No args → scan this conversation for corrections the user made (approach overridden, preference stated, "no, use X", a repeated instruction). List the candidates with your proposed entry for each and ask which to record. Nothing found → say so and stop.

2. **Read the ledger.** `docs/team/conventions.md` missing → create it with this header:

   ```markdown
   # Team conventions — taught rules

   Rules the user taught the agent team. Every agent reads this file before
   starting work; entries here override agent defaults. Maintain via /teach
   (or edit by hand — the shape below is the contract).
   ```

3. **Check for conflicts.** A new rule that contradicts or refines an existing entry → update that entry in place (keep the newest rule, note what changed and when). Never leave two entries that disagree. Exact duplicate → say it's already recorded, change nothing.

4. **Append the entry** in this shape:

   ```markdown
   ## <short imperative title>
   - **Rule:** <the rule, one or two sentences, imperative>
   - **Why:** <the user's reason; ask if it isn't obvious — a rule without a why gets misapplied>
   - **Scope:** <which agents / areas it binds — e.g. database-developer + backend-developer (migrations, models); "all agents" when truly global>
   - **Source:** user, <YYYY-MM-DD>
   ```

5. **Confirm back.** Show the recorded entry, name the agents it binds, and remind: it takes effect on each agent's next invocation. If the rule belongs in `CLAUDE.md` instead (a hard project constraint, not an agent-behavior preference), say so and offer to put it there.

## Rules

- One entry per rule. No essays — an entry longer than ~5 lines is two rules or a doc.
- Don't record what the repo already enforces (Pint config, CLAUDE.md constraints, committed configs) — point at the existing source instead.
- Secrets, credentials, or environment-specific values never go in the ledger.
- You write only `docs/team/conventions.md` (and `CLAUDE.md` if the user explicitly picks that in step 5). Nothing else.
