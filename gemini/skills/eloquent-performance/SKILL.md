---
name: eloquent-performance
description: "The query-performance cookbook — reading EXPLAIN plans, diagnosing + fixing N+1 without overfetching, pagination and chunking choices, the caching decision tree (remember vs flexible vs lock), measurement discipline. Use when an endpoint or query is slow, before adding an index or cache, or when reviewing query-shape changes. Diagnosis recipes — the fix lands with the owning builder (backend / database developer)."
---

# Eloquent + Query Performance

Measure first. A number without a baseline is a guess; p95/p99, not mean. Reproduce under realistic volume — a plan on 100 rows lies about 10M.

## Reading EXPLAIN

`EXPLAIN ANALYZE <query>` (MySQL 8+ / Postgres). Red flags, in order of blood pressure:

- **rows examined ≫ rows returned** — the query scans and discards; index or rewrite.
- **type=ALL / Seq Scan** on a large table — full scan. Check: is there an index the planner *can't* use? Function-on-column (`WHERE DATE(created_at) = …`) and leading-wildcard `LIKE '%x'` kill index use — rewrite as a range (`created_at BETWEEN …`).
- **filesort / temporary table** — sort not served by an index; composite index matching `WHERE` + `ORDER BY` order.
- **Postgres**: `Rows Removed by Filter` high → same discard problem; check `work_mem` spills on sorts/hashes.

Index handoff to `database-developer`: the EXPLAIN plan, the query pattern + frequency, and the target verdict — never "add an index" bare.

## N+1

- Detect: `Model::shouldBeStrict()` in non-prod throws on lazy loads; Pulse Slow Queries / Telescope Queries tab show the repeat pattern; `DB::listen(fn ($q) => Log::info('sql', ['sql' => $q->sql, 'ms' => $q->time]))` around a reproduction counts them.
- Fix at source: `with()`, `withCount`, `withExists`, `withAggregate` on the list query; `loadMissing()` post-hoc; `whereRelation()` for single-column constraints.
- **Check overfetch after the fix**: eager-loading a fat relation to render one field, on 10k rows, trades N+1 for a memory bomb. Constrain: `with('author:id,name')`. Measure both ways.

## Reading big, writing big

- Iterate large sets: `chunkById()` (safe under mutation — `chunk()` is not), `lazy()`, `cursor()` (single query, no eager loads).
- Bulk writes: `upsert()`, `insertOrIgnore()` — no model events fire; if Observers matter, loop in a transaction and say why.
- Select only needed columns. Cursor pagination for infinite scroll / large offsets; offset pagination only when total counts matter and the table is small.

## Caching decision tree

1. Recomputed per request, cheap to invalidate → `Cache::remember($key, $ttl, $fn)`.
2. Stampede-prone (hot key, expensive recompute) → `Cache::flexible($key, [$fresh, $stale], $fn)` — serves stale, recomputes in background.
3. Staleness unacceptable → `Cache::lock($key)->block($seconds, $fn)` around the recompute.

Every cache entry states three things or it doesn't ship: **key, TTL, exact invalidation trigger**. A cache without an invalidation story is a bug with latency. Capture hit ratio for any cache added or touched.

Redis: pipeline batched ops, tag caches for group invalidation, know the eviction policy (`maxmemory-policy`) before trusting TTLs.

## Measurement discipline

- Wall-clock endpoints: `wrk -t4 -c50 -d30s <url>` or a k6 script → p50/p95/p99 + req/s. Local or dedicated staging only; shared/prod targets need human sign-off.
- PHP-level: Xdebug → KCachegrind, or Blackfire / Tideways for call graph + memory.
- State every result as a number with units, before and after. No before/after delta → it didn't happen.
- Cheapest win first: eager-load > index > cache > rewrite > scale. Exhaust a layer before escalating.
