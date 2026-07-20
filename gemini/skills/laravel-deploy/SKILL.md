---
name: laravel-deploy
description: "The Laravel deployment cookbook — platform detection, zero-downtime release checklist, queue-worker + scheduler topology, rollback drill, post-deploy smoke. Use when building or reviewing a deploy pipeline, changing worker / scheduler topology, preparing a release, or writing an incident runbook's technical steps."
---

# Laravel Deployment

Every deployment rollbackable, or it isn't ready. Build once, deploy many — one artifact promoted across environments.

## Platform detection

`vapor.yml` → Vapor · `.forge/` or Forge env markers → Forge · Laravel Cloud project → Cloud (first-party default for new apps) · `Envoy.blade.php` → Envoy the task runner (Envoyer, the hosted service, leaves no repo marker — confirm with the user) · `kamal/` or `config/deploy.yml` → Kamal · `Dockerfile` + `helm/`/`k8s/` → containers. Nothing detected → ask; never invent a pipeline for a platform the project doesn't use.

## Zero-downtime release checklist

1. **Migrations backward-compatible** with the still-running old code: additive first (new nullable column → deploy → backfill → enforce). Destructive changes span two releases minimum.
2. `php artisan optimize` in CI (compiles config/route/event/view caches in one command — no separate `view:cache` — and catches `env()`-outside-config and route breakage before prod does).
3. **Long-running services restart on deploy**: L13 ships `php artisan reload` — terminates workers, Reverb, and Octane in one command (Laravel Cloud does this automatically). Older: `queue:restart` (signal) or `horizon:terminate`. Old workers hold old code; a worker running yesterday's job class against today's schema is the classic silent corruption. Caveat: `Queue::withoutInterruptionPolling()` (or `Worker::$restartable = false`) makes `queue:restart`/`queue:pause` silently no-ops — hard-restart via Supervisor then.
4. OPcache reset on release switch (FPM reload or `opcache_reset()` hook); Octane: `octane:reload`.
5. Symlinked releases (Forge/Envoyer style): `storage/` + `.env` shared, `current` symlink flipped last.
6. Health-check endpoint (`/up`, L11+ ships one) gated into the load balancer before traffic shifts. `/up` dispatches `DiagnosingHealth` — a listener that probes DB/cache and throws turns it into a real dependency check, not just a boot check.

## Worker + scheduler topology

- Horizon: one `horizon` process per box under Supervisor/systemd (`stopwaitsecs` > longest job `$timeout`); balance `auto`; queue priorities explicit (`high,default,low`).
- Plain workers: `queue:work --queue=high,default --max-time=3600 --tries=3` under Supervisor, `numprocs` sized to DB connection budget.
- Scheduler: one crontab entry `* * * * * php artisan schedule:run`; multi-server → `onOneServer()` on every closure/command that must not double-fire; `withoutOverlapping()` on anything slow. Sub-minute tasks defined → `php artisan schedule:interrupt` in the deploy script, or the in-flight `schedule:run` keeps executing old code until the minute ends.
- Long-running processes leak: `--max-time` / `--max-jobs` recycling beats chasing memory.

## Rollback drill

Rollback = redeploy previous artifact + **decide the migration story**: migrations that shipped stay (they were backward-compatible, right?) — `migrate:rollback` in prod only with the specific `down()` verified non-destructive. During the incident, `queue:pause` (resume with `queue:continue`) beats flushing — stop processing while you decide. Queue backlog: failed jobs from the bad release → `queue:retry` after fix, or `queue:flush` with a written reason. Document the actual rollback command per platform in the runbook — during an incident nobody remembers flags.

## Post-deploy smoke

`php artisan about` sane · health endpoint 200 · one real authenticated request · `horizon:status` / worker count · `schedule:list` shows expected entries · error tracker (Sentry) quiet for 10 minutes · log tail clean of new exception classes.

## Pipeline hygiene

Pin runtimes (`shivammathur/setup-php@<sha> # v2` — actions SHA-pinned, version from `composer.json require.php`). Cache `vendor/` + npm keyed on lockfile hashes. Stage order: install → Pint → Larastan → tests → build assets → `optimize` → deploy. Secrets from the platform store, never repo or logs.
