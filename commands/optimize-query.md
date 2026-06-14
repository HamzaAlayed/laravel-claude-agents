---
description: Optimize a slow query or endpoint — capture, EXPLAIN, diagnose, produce a fix plan, hand to database/backend developer.
argument-hint: <route, query, or model method>
allowed-tools: Read, Bash, Grep, Glob
---

# Optimize query — `{{args}}`

Diagnose why `{{args}}` (a route name/path, raw query, or `Model::method`) is slow and produce a fix plan with measured evidence. Measure first. You diagnose; builders apply.

## What you do

1. **Locate the subject.**
   - Route / path → `php artisan route:list | grep '{{args}}'` → controller → the queries it triggers.
   - `Model::method` → read the model + scope. Raw query → take it as given.
   - Identify the table(s), relations, and the call site.

2. **Capture the query + timing.** Before touching anything:
   - Wrap a reproduction with `DB::listen(fn ($q) => Log::info('sql', ['sql' => $q->sql, 'bindings' => $q->bindings, 'ms' => $q->time]))`. Record query count + total ms.
   - Or read Telescope's Queries tab / Pulse slow-queries for the live numbers.
   - Pull the actual SQL (`->toSql()` / Telescope) and run `EXPLAIN ANALYZE <sql>` (MySQL 8 / Postgres). Read: access type (`ALL` = full scan), rows examined vs returned, filesort, temporary table, key used.

3. **Diagnose.** Match against the usual suspects:
   - **Missing index** — `WHERE` / `JOIN` / `ORDER BY` column not indexed. `EXPLAIN` shows `type=ALL` / large rows-examined.
   - **N+1** — query count scales with row count. Relation accessed in a loop / Resource / Blade without eager load.
   - **`SELECT *`** — pulling fat / TEXT / BLOB columns the caller never reads.
   - **Unbounded result set** — no `LIMIT`, whole table into memory.
   - **Missing pagination** — list endpoint returning everything.
   - **Function-on-column** — `WHERE DATE(created_at) = ?`, `WHERE LOWER(email) = ?` — defeats the index. Rewrite to a range / generated column / store normalized.
   - **Leading-wildcard `LIKE '%x'`** — can't use a B-tree index; consider full-text / different access.
   - **Bad join order / cartesian** — duplicated rows from `whereHas` vs `whereRelation`, or a many-to-many fanout.

4. **Produce the fix plan:**

   ```
   # Query optimization — {{args}}

   ## Baseline
   - Query count: <n>   Total DB time: <ms>   p95 endpoint: <ms>
   - Worst query: <sql>
   - EXPLAIN: <access type, rows examined vs returned, key, filesort?>

   ## Diagnosis
   - Root cause: <pattern from above>

   ## Fix plan
   1. <change> — owner: <database-developer | backend-developer>
   2. ...

   ## Projected result + verification
   - Expected: <n→m queries / ms→ms>. Re-run DB::listen + EXPLAIN after to confirm.
   ```

5. **Route the fix.**
   - Index changes, schema, generated columns → **database-developer** (attach the EXPLAIN plan + target).
   - Eager-load, query-shape, `select()` narrowing, pagination, scope rewrites → **backend-developer**.
   - Caching as a fix (after the query is as good as it gets) → loop in **performance-engineer** for the invalidation strategy.

6. **Do not edit code.** Hand the plan to the owners above.
