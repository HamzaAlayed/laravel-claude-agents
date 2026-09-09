---
description: Add (or audit) a Policy for an Eloquent model — generate the Policy class, wire it, and patch all controllers/Livewire components/routes to use it.
argument-hint: <ModelName> [--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Add Policy — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `next` to choose whom to Agent, `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are shell commands the kernel re-runs; prose is a reject. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

Add or audit the authorization Policy for the `{{args}}` Eloquent model, and ensure every code path that touches the model uses it.

## What you do

1. **Locate the model.** `app/Models/{{args}}.php` (or wherever the project keeps models per its convention). If it doesn't exist, stop and ask.

2. **Find all touch points.** Grep for:
   - `{{args}}::` (static calls — `find`, `findOrFail`, `where`, `create`)
   - `{{args}}\b` in controllers, Livewire components, Filament resources, jobs, and API Resources
   - Routes that bind `{{args}}` via route model binding (look for `{{args}}` lowercased in `routes/`)

3. **Delegate to `backend-developer`** to:
   - Generate `app/Policies/{{args}}Policy.php` via `php artisan make:policy {{args}}Policy --model={{args}}` if not already present
   - Implement `viewAny`, `view`, `create`, `update`, `delete`, `restore`, `forceDelete` with real rules (not stubs)
   - Register the Policy in `App\Providers\AuthServiceProvider::$policies` (or rely on auto-discovery if the project uses it)
   - Patch every touch point to invoke the Policy:
     - In controllers: `$this->authorize('view', $model)` or `Gate::authorize('view', $model)`
     - In Form Requests: implement `authorize()` to delegate to the Policy
     - In Livewire components: `$this->authorize('view', $this->model)` in mount/render
     - In Filament resources: implement the `can*` methods or rely on Filament's auto-detection
     - In API Resources: don't authorize in the Resource — that's the controller's job

4. **Delegate to `qa-engineer`** to write:
   - One "allowed" test and one "denied" test for each Policy method
   - Use `actingAs($user)` and `actingAs($otherUser)` to cover both sides

5. **Delegate to `security-engineer`** for a final review confirming:
   - No protected routes remain without an authorization check
   - The Policy rules match the business rules in `docs/requirements/`
   - Mass-assignment safety is intact on the model

## Output

- Path to the new Policy
- List of files patched
- Test results for the new Policy tests
- Any routes/components that the audit could not auto-patch and need human attention
