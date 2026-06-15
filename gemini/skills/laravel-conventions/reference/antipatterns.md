# Antipatterns this pack refuses to ship

Grouped by layer. Each is paired with the idiomatic fix. These are the rules the
`backend-developer`, `frontend-developer`, `tech-lead`, and `performance-engineer`
agents enforce.

## HTTP layer

| Antipattern | Fix |
|---|---|
| `$request->validate()` in a non-trivial controller | Form Request with `rules()` + `authorize()` |
| Returning a model / raw array as JSON | API Resource / Resource Collection |
| Ad-hoc ownership checks (`if ($x->user_id === auth()->id())`) | Policy method + `$this->authorize()` |
| Inconsistent error shapes | One envelope (RFC 7807 if adopted); correct status codes (`201`/`204`/`409`/`422`/`429`) |
| Mixed pagination styles in one API | Pick cursor or offset deliberately; be consistent |

## Eloquent & data

| Antipattern | Fix |
|---|---|
| N+1 in a list endpoint | Eager-load: `with`/`withCount`/`withExists`/`withAggregate` |
| `$guarded = []` on user input | Deliberate `$fillable` |
| Multi-row mutation inside a model method | Extract to an Action, wrap in `DB::transaction` |
| `->get()` then `->count()` / `->first()` in PHP | Push it into the query |
| `DB::raw($input)` / concatenated SQL | Bindings, query builder, or Eloquent |
| `chunk()` while mutating | `chunkById()` |
| Returning Eloquent models from APIs | API Resource |

## Config, runtime & concurrency

| Antipattern | Fix |
|---|---|
| `env()` outside `config/*.php` | `config('group.key')` (survives `config:cache`) |
| Gating behavior on `app()->environment()` | Pennant feature flags |
| Static / request state in an Octane singleton | `scoped()` services; no captured request data |
| Dispatching inside a transaction without `->afterCommit()` | `->afterCommit()` |
| Read-modify-write without a lock | `lockForUpdate()` / `Cache::lock()` / unique constraint |

## Code clarity (preserve behavior)

| Antipattern | Fix |
|---|---|
| Nested ternaries | `match (true)`, `switch`, or if/else chain |
| Deep `if` pyramids | Early returns / guard clauses |
| Clever dense one-liners | Explicit, readable code — clarity over brevity |
| Missing param/return types | Type everything; avoid `mixed` |
| Comments restating the code | Delete; let names carry intent |
| Generic `\Exception` | Typed, app-specific exceptions |

## Jobs & errors

| Antipattern | Fix |
|---|---|
| Job without `$tries` / `$backoff` / `$timeout` / `failed()` | Set them; design for retry |
| External HTTP without `retry()` + `timeout()` | `Http::retry(3, 200)->connectTimeout(3)->timeout(10)` |
| `catch (\Throwable)` then silent log | Handle, rethrow typed, or surface |
| Long work in the request cycle | Dispatch to a queue |

## Debug & hygiene

| Antipattern | Fix |
|---|---|
| `dd()`, `dump()`, `ray()` committed | Remove before commit |
| Writing to `.env*` / secrets to add a key | Document in `.env.example` + `GEMINI.md`; human updates the live env |
| `migrate:fresh` / `db:wipe` near production | Never against prod; the guardrail hooks block it |
