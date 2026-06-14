---
description: Plan and stage a Laravel framework version upgrade — detect current, inventory breaking changes, check first-party packages, produce a staged migration plan.
argument-hint: <target-version e.g. 11 or 12>
allowed-tools: Read, Bash, Grep, Glob
---

# Upgrade Laravel — to `{{args}}`

Plan and stage an upgrade to Laravel `{{args}}`. Produce a staged, verifiable migration plan. You plan + inventory; `backend-developer` + `devops-engineer` implement, `tech-lead` reviews. Do not edit code.

## Prefer Laravel Boost for the framework bump

For major **first-party** version jumps, Laravel's official tool is [Laravel Boost](https://github.com/laravel/boost) — it ships maintained, codebase-aware upgrade slash commands. Don't hand-roll what Boost automates. Check for it first:

```
grep -q 'laravel/boost' composer.json && echo "Boost present" || echo "Boost absent"
```

- **If Boost is present** (requires `^2.0`), recommend running its upgrade command for the matching jump, then come back for the surrounding work (package compat, structural migration audit, verification):
  - Laravel 12 → 13: `/upgrade-laravel-v13`
  - Livewire 3 → 4: `/upgrade-livewire-v4`
  - Inertia v2 → v3: `/upgrade-inertia-v3`
- **If Boost is absent**, suggest installing it for the bump: `composer require laravel/boost --dev && php artisan boost:install`.
- **If no Boost command covers this jump** (older targets, or non-framework work), use the staged plan below directly.

Either way, this command owns the parts Boost doesn't: PHP-runtime readiness, first-party package compatibility, the structural 10 → 11 migration audit, and the per-stage verification checkpoints. Frame the output as "Boost handles the framework diff; here's everything around it."

## What you do

1. **Detect the current version.**
   - `php artisan --version`
   - `grep -E '"laravel/framework"|"php"' composer.json`
   - Note current PHP version (`php -v`) vs what target Laravel `{{args}}` requires. PHP bump is often the real blocker.

2. **Read the official upgrade guide.** Consult `laravel.com/docs/{{args}}/upgrade` for the authoritative breaking-change list and required-vs-optional changes. Treat it as source of truth; everything below is how you map it onto *this* codebase.

3. **Inventory breaking changes against the codebase.** For each item in the guide, grep for affected usage:
   - **Deprecated / removed helpers + methods** — search `app/`, `routes/`, `tests/`, `config/` for the removed signatures.
   - **Changed method signatures** — middleware, validation rules, casts, contracts.
   - **Config changes** — diff your `config/*.php` against the target skeleton; note new keys + changed defaults.
   - **If coming from Laravel 10 → 11+:** the structural migration is the big one. `bootstrap/app.php` replaces `app/Http/Kernel.php` + `app/Console/Kernel.php` (middleware, exception handling, scheduling move there). `routes/console.php` for the scheduler. New streamlined `config/` (only published files override). Inventory custom Kernel middleware, exception handler customizations, and scheduled tasks that must move.
   - **PHP version bump** — readiness of `declare(strict_types)`, enums, readonly usage.

4. **Check first-party package compatibility.** For each present in `composer.json`, confirm a release line supports target `{{args}}` and note required version + its own breaking changes:
   - Sanctum, Passport, Fortify, Breeze/Jetstream
   - Horizon, Telescope, Pulse, Pennant
   - Nova, Cashier (Stripe/Paddle), Scout, Reverb, Octane, Socialite
   - Also: Livewire / Inertia, Filament, and any Spatie packages — these gate on the framework version too.
   ```
   composer why-not laravel/framework <target> 2>&1
   composer outdated "laravel/*" "livewire/*" "spatie/*"
   ```

5. **Produce the staged migration plan.** One stage at a time, each with a verify checkpoint:

   ```
   # Laravel upgrade plan — <current> → {{args}}

   ## Pre-flight
   - PHP: <current> → <required>. Owner: devops-engineer.
   - Branch: feature/upgrade-laravel-{{args}}. Full green suite on current version first (baseline).

   ## Stage 1 — PHP runtime
   - Changes: <...>
   - Verify: composer install clean, full suite green, `php artisan about`.

   ## Stage 2 — First-party packages
   - Bump: <pkg → version> each, per their upgrade notes.
   - Verify: suite green after each bump (bump one at a time, not all at once).

   ## Stage 3 — Framework bump
   - `composer require laravel/framework:^{{args}} -W`
   - Apply guide's required changes (config, signatures, helpers).
   - Verify: suite green, `pint --test`, `phpstan analyse`.

   ## Stage 4 — Structural migration (only 10 → 11+)
   - Migrate Kernels → bootstrap/app.php, scheduler → routes/console.php.
   - Verify: middleware order intact (`php artisan route:list`), schedule intact (`php artisan schedule:list`), exceptions still rendered correctly.

   ## Stage 5 — Cleanup + final verify
   - Remove deprecated shims. Re-cache config/routes.
   - Verify: full suite, `composer audit`, manual smoke on critical flows.

   ## Risks / unknowns
   - <packages without a compatible release, custom code with no clear migration path>
   ```

6. **Route implementation.**
   - Code changes per stage → **backend-developer**.
   - PHP runtime, CI matrix, deploy config, server PHP version → **devops-engineer**.
   - Plan + final diff review → **tech-lead**.

7. **Do not edit code.** This command produces the plan; the agents above execute it stage by stage with the suite green at every checkpoint.
