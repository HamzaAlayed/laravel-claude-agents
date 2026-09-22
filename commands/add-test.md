---
description: Plan tests for a class, route, or component — happy path, failure modes, authorization — then hand to qa-engineer to implement.
argument-hint: <Class, route, or component> [--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Add tests — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `next` to choose whom to Agent, `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print `✔ done / ▶ running / · queued / ✖ failed`. `plan` must pass a nonempty `--done-when` and every `--stage` must carry success criteria. If a sprint is running, attach it (`--sprint <id>` or the kernel attaches the single running sprint). Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Never compose `docs/sprints/<id>/sprint.md` (the kernel renders that view). Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are shell commands the kernel re-runs; prose is a reject. `NOT-CHECKED:` that names a stage success criterion is a reject. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

Build a test plan for `{{args}}` (a class name, route name/path, Livewire component, or Inertia page), then hand it to `qa-engineer` to implement. You plan; you do not write the tests.

## What you do

1. **Detect the test framework.**
   - `grep -E '"pestphp/pest"|"phpunit/phpunit"' composer.json` — Pest or PHPUnit?
   - Read `phpunit.xml` for suites + env. Read `tests/Pest.php` if Pest (uses, helpers, global `beforeEach`).
   - `RefreshDatabase` vs `DatabaseTransactions` — which does this project use? Match it. Do not introduce a new strategy.

2. **Find the existing style.** Read 2–3 sibling tests near where this one will live (`tests/Feature`, `tests/Unit`).
   - Pest `it()/test()/describe()` vs PHPUnit `test_*` methods.
   - Factory + state usage, `actingAs` patterns, custom assertions/expectations, datasets.
   - Match naming, structure, and helpers exactly.

3. **Locate + classify the subject.**
   - Route / path → `php artisan route:list | grep '{{args}}'` → controller + middleware → **feature test**.
   - Action / Service / value object → **unit test**.
   - Job → unit test the effect (invoke `handle()`), assert dispatch with `Bus::fake()`.
   - Livewire / Inertia component → feature test (`Livewire::test(...)` / Inertia assertions).
   - Read the subject to enumerate inputs, branches, dependencies, side effects.

4. **Draft the test plan.** Cover, at minimum:

   ### Happy path
   - Valid input → expected status / state. Assert `assertJsonStructure` / `assertJsonPath`, `assertDatabaseHas`, dispatched jobs/events/mail/notifications.

   ### Failure modes
   - Validation errors (`assertInvalid`, 422), missing/malformed input, boundary values.
   - Not-found (404), conflict (409), rate limit (429) where applicable.
   - External-call failure: `Http::fake()` returning 4xx / 5xx / timeout. Assert graceful handling.
   - Concurrency / idempotency where the subject claims it.

   ### Authorization (both directions)
   - Allowed: the right user/role/ability succeeds.
   - Denied: unauthenticated → 401, wrong owner/role → 403. Assert Policy is actually enforced, not just the happy actor.

   List required fakes (`Bus`, `Http`, `Mail`, `Notification`, `Event` with explicit allowlist, `Storage`), factories + states, and `freezeTime`/`travelTo` needs.

5. **Emit the plan:**

   ```
   # Test plan — {{args}}

   Framework: <Pest|PHPUnit>   Suite: <Feature|Unit>   DB: <RefreshDatabase|DatabaseTransactions>
   File: tests/<Feature|Unit>/<...>Test.php

   ## Cases
   | # | Case | Type | Arrange (factories/fakes) | Act | Assert |
   |---|------|------|---------------------------|-----|--------|
   | 1 | happy path | ... | ... | ... | ... |
   | 2 | validation fails | ... | ... | ... | ... |
   | 3 | authz denied | ... | ... | ... | ... |
   | ... |

   ## Gaps / open questions for the implementer
   - ...
   ```

6. **Hand off to `qa-engineer`** to implement against the existing style. Do not write or edit test files yourself.
