---
description: Scaffold a full Laravel feature end-to-end — migration, model, factory, Form Request, Resource, controller/action, route, Policy, and feature test — by delegating to the right specialists.
argument-hint: <feature-name> [--inertia|--livewire|--api|--blade]
allowed-tools: Agent, Read, Bash, Grep, Glob, AskUserQuestion
---

# Make feature — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Print a progress board after the plan and after every stage — `✔ done / ▶ running / · queued / ✖ failed` + owner + one-line result, so the user never wonders what's running or what's left. Demand each specialist return `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines; an empty VERIFIED is a claim, a missing NOT-CHECKED is uncalibrated — either → re-brief once naming the gap). Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph.

Scaffold the feature described by `{{args}}` end-to-end, using the right specialist for each layer. Default to the frontend paradigm already used in the project unless explicitly overridden.

## Plan

1. **Detect the frontend paradigm.**
   - `inertiajs/inertia-laravel` in `composer.json` → Inertia
   - `livewire/livewire` → Livewire
   - Neither → Blade (or `--api` for headless)
   Override via the flag if present in `{{args}}`.

2. **Brief `business-analyst`** *only if* the feature ask is vague. Otherwise skip — this is a scaffold, not discovery.

3. **Delegate in dependency order — not one long chain.** Stage a first (everything reads its schema). Stages b and c run **in parallel** — they touch disjoint paths (backend owns `app/` + `routes/`, frontend owns `resources/`), and the migration's field list + planned route names are contract enough for the frontend to build against. Carry the paradigm detected in step 1 and the stack snapshot in **every** brief so no specialist re-reads `composer.json`/configs.

   ### a. `database-developer`
   - Design and write the migration (reversible, indexed, constraints explicit)
   - Update or create the Eloquent model (with `$fillable`, `$casts`, relations, scopes)
   - Update or create the factory

   ### b. `backend-developer`
   - Form Request (`Store<Feature>Request`, `Update<Feature>Request`) with validation rules
   - API Resource (`<Feature>Resource`, `<Feature>Collection` if list endpoint)
   - Policy with `viewAny`, `view`, `create`, `update`, `delete`
   - Controller (resourceful) or Action classes per the project's pattern
   - Route registration in `routes/web.php`, `routes/api.php`, or both
   - Wire the Policy in `AuthServiceProvider` if the project doesn't auto-discover

   ### c. `frontend-developer` (skipped for `--api`; runs in parallel with b — brief it with the field list + route names as its contract)
   - **Inertia:** page components in `resources/js/Pages/<Feature>/{Index,Show,Create,Edit}.{vue,jsx,tsx}` with `useForm`, server-driven validation errors, and shared layout
   - **Livewire:** components under `app/Livewire/<Feature>/` with computed properties, `#[Rule]` attributes, loading/error states
   - **Blade:** views under `resources/views/<feature>/` using existing component library

   ### d. `qa-engineer` (starts once b + c land)
   - Feature test covering happy path, validation failure, authorization denial, and DB state
   - Factory state used; `RefreshDatabase` per the project pattern
   - Livewire/Inertia assertion helpers as appropriate

4. **Brief `tech-lead`** for review of the implementation diff **in parallel with stage d** — review needs the b + c diff, not the tests; qa's tests are verified by running them. Run the full suite once, after both return — not after every stage.

## Guardrails

- Match the project's conventions, do not import new patterns
- If the project doesn't have `app/Actions/` and uses controllers-with-methods, follow that — don't impose Actions
- If the project uses `app/Services/`, follow that too
- Don't introduce new packages without checking `CLAUDE.md` for any constraint

## Output

After all phases complete, summarise:
- Files created and their paths
- Routes added (`php artisan route:list` excerpt)
- Tests passing (`php artisan test --filter=<Feature>` output)
- Any human checkpoints surfaced
