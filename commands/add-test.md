---
description: Plan tests for a class, route, or component — happy path, failure modes, authorization — then hand to qa-engineer to implement.
argument-hint: <Class, route, or component>
allowed-tools: Agent, Read, Bash, Grep, Glob
---

# Add tests — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

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
