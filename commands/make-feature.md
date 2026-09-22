---
description: Scaffold a full Laravel feature end-to-end — migration, model, factory, Form Request, Resource, controller/action, route, Policy, and feature test — by delegating to the right specialists.
argument-hint: <feature-name> [--inertia|--livewire|--api|--blade|--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Make feature — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `ready` to fetch the bounded dependency-ready wave, `claim --stage <id>` before each Agent, then dispatch every claimed lane concurrently, and `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. `plan` must pass a nonempty `--done-when` and every typed `--stage-json` must carry success criteria and `owned_paths`; use `--max-parallel` to set the WIP ceiling. If a sprint is running, attach it (`--sprint <id>` or the kernel attaches the single running sprint). Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Never compose `docs/sprints/<id>/sprint.md` (the kernel renders that view). `plan` prints `RULES:` only for user-approved learned rules; brief every `RULES:` line. Never compose `docs/team/lessons.md` (the kernel renders that view). When the command includes `--issue <n>`, `plan` passes `--issue <n>`. Call `pr --number <n>` once a pull request exists; the kernel re-fetches it. Call `ingest` only for a failing check or a review comment the kernel confirms. Never compose issue or pr fields. A workplace delivery stays running until the recorded PR state is open. Never merge. Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are JSON verification records (`{"runner":"artisan-test","args":["--filter=TagTest"]}`); the kernel accepts only registered runners and executes argv without a shell; prose and legacy command strings are rejected. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

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
