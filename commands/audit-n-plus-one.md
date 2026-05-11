---
description: Audit a route, Inertia page, or Livewire component for N+1 queries and report the fixes.
argument-hint: <route-or-component-name>
allowed-tools: Read, Bash, Grep, Glob
---

# Audit N+1 — `{{args}}`

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
