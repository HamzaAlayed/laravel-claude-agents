---
description: Audit a route, Inertia page, or Livewire component for N+1 queries and report the fixes.
argument-hint: <route-or-component-name> [--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Audit N+1 — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Print a progress board after the plan and after every stage — `✔ done / ▶ running / · queued / ✖ failed` + owner + one-line result, so the user never wonders what's running or what's left. The board's header states the stage budget **before** any agent spends tokens — how many stages you expect and the observable condition that ends the run (`N stages · done when: <the observable thing>`); a board that arrives only as a closing summary told the human nothing they could still act on. Growing past that budget is a re-plan: reprint the header with the new count and why it grew. Demand each specialist return `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines; an empty VERIFIED is a claim, a missing NOT-CHECKED is uncalibrated — either → re-brief once naming the gap). **Stage returns land on disk** — brief each specialist with `docs/delivery/<name>/stages/<agent>.md`; writers Write the six fields there as their last act; Read that file before `✔`; never write a writer's stage file for them. Read-only specialists (`disallowedTools: Write`) — persist their stage file from the report you already file, same as their other artifacts. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). **Verify before advancing** — re-run that brief's success criteria yourself; a specialist's `STATUS: done` is a claim, not a `✔`. Stage returns are internal; this is the only calibration the human ever sees, so a run that ends without it is unfinished. **Brief only what the specialist owns** — goal, owned paths, success criteria, stage path, named stack facts; not another specialist's diff. **Join before a dependent stage** — Read every upstream stage file and re-run its criteria before starting a stage that depends on it. Re-brief overwrites `docs/delivery/<name>/stages/<agent>.md`. **Close file on disk** — after the plan and after every stage, overwrite `docs/delivery/<name>/close.md` with coordinator `VERIFIED` / `NOT-CHECKED` / `STATUS` / `BOARD`. A killed run is scored from that file. **Spawn cap in the board header** — `N stages · cap: M spawns · done when:`; `M` defaults to `N+2`; hitting `M` without `done when:` → `close.md` `STATUS: stopped` and stop. When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer; spawn `peer-router` to validate it; then Agent that peer with the packet as the brief; print a handoff line on the board; hops count against the spawn cap. If no writer packet exists, the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

Investigate `{{args}}` (a route name, URL path, Livewire component, or Inertia page) for N+1 query patterns and produce an actionable findings report.

## What you do

1. **Locate the entry point.**
   - If it looks like a URL path → grep `routes/` for the matching definition
   - If it's a route name → `php artisan route:list | grep '{{args}}'`
   - If it's a Livewire component → look under `app/Livewire/` (v3) or `app/Http/Livewire/` (v2)
   - If it's an Inertia page name → grep controllers for `Inertia::render('{{args}}'`

2. **Trace the data graph.** From the entry point, follow:
   - The controller / Livewire / Inertia handler
   - The Eloquent queries it triggers
   - The API Resource or Blade view it returns

3. **Spot the N+1 patterns:**
   - `->each()`, `->map()`, `foreach` over a Collection that accesses a relation without it being eager-loaded
   - API Resources or Blade views that traverse `$model->relation->...` for related fields when the parent collection didn't `->with('relation')`
   - Polymorphic `morphMany` / `morphTo` rendered in a list — these need `morphWith` to be efficient
   - `count()` on relations inside loops — use `withCount`
   - Existence checks inside loops — use `withExists`
   - Nested relations rendered without nested eager loads (`with('relation.subRelation')`)

4. **Run the route under the query log if reachable.** Either:
   - Telescope Queries tab if installed
   - Or wrap a manual reproduction with:
     ```php
     \DB::enableQueryLog();
     // hit the route / call the component
     dd(\DB::getQueryLog());
     ```
   - Or run the relevant feature test with `\DB::listen(...)` enabled

5. **Produce the findings report:**

   ```
   # N+1 audit — {{args}}

   ## Summary
   - Queries observed: <n>
   - N+1 sites found: <n>

   ## Findings

   ### Finding 1 — <file>:<line>
   - Pattern: <pattern>
   - Trigger: <what causes the loop>
   - Fix: <eager-load syntax or pattern change>
   - Estimated query reduction: from <n> to <m>

   ## Recommended diff (paraphrased — do not apply, hand to backend-developer)
   ```php
   // Before
   $users = User::all();
   // After
   $users = User::with(['posts', 'comments'])->get();
   ```

6. **Do not apply the fixes yourself.** Hand the report to `backend-developer` (or `frontend-developer` if the offending access is in a Livewire/Inertia component).
