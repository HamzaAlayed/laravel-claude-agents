---
name: laravel-conventions
description: The idiomatic-Laravel convention reference — which primitive to reach for and which antipattern to refuse, across HTTP, Eloquent, validation, authorization, config, queues, and testing. Use when writing or reviewing Laravel/PHP code and you need the canonical "right way," when choosing between two approaches, or when something feels like it's fighting the framework. Pairs with laravel/agent-skills' laravel-simplifier (which refines after the fact); this guides the choice up front.
---

# Laravel Conventions

Pick the primitive the framework already gives you. Follow the grain; don't fight it. When two approaches both "work," the idiomatic one wins — it's what the next maintainer expects.

This skill is the *up-front* guide (what to reach for while writing). For *after-the-fact* refinement of code that already works, defer to the official `laravel-simplifier` agent from [laravel/agent-skills](https://github.com/laravel/agent-skills).

## Decision shortcuts

| You're about to… | Reach for | Not |
|---|---|---|
| Validate request input | Form Request (`StoreOrderRequest`) | inline `$request->validate()` in a non-trivial controller |
| Return JSON | API Resource (`OrderResource`) | the Eloquent model directly |
| Authorize an action | Policy + `Gate::authorize()` or L13 `#[Authorize('update', 'post')]` attribute | ad-hoc `if ($order->user_id === auth()->id())`; `$this->authorize()` assumes a trait L11+ controllers don't have |
| Controller-scoped middleware (L13) | `#[Middleware('auth')]` on class or method (`only:`/`except:`) | re-declaring per-route in `routes/*` |
| Hold domain logic | Action / Service (`App\Actions\…`) | a fat controller or a model method that mutates many rows |
| Read config / secrets | `config('services.x.key')` | `env()` outside `config/*.php` (breaks under `config:cache`) |
| Branch on many cases | `match (true)` / if-else chain | nested ternaries |
| Long-running work | queued Job — retry controls via L13 `#[Tries]`/`#[Backoff]`/`#[Timeout]` attributes (property forms still work) + `failed()`; rapid re-dispatch → `#[DebounceFor]`; central routing → `Queue::route()` | doing it in the request |
| Feature toggle | Pennant | `app()->environment()` checks |
| Schedule a task (L11+) | `routes/console.php` | the legacy `app/Console/Kernel.php` |
| Wire middleware / exceptions (L11+) | `bootstrap/app.php` | the legacy HTTP/Console Kernels |

## The non-negotiables

- `declare(strict_types=1);` in every new PHP file. Type every parameter and return. Avoid `mixed`.
- **Eager-load list endpoints.** N+1 is zero-tolerance. Turn on `Model::preventLazyLoading()` in non-prod. Use `with`, `withCount`, `withExists`, `withAggregate`.
- **Never return Eloquent models from an API.** Always an API Resource (L13 `make:resource --json-api` when spec compliance matters).
- **`$fillable` set deliberately** (or L13 `#[Fillable([...])]`). No bare `$guarded = []` — and no `#[Unguarded]` — on user input.
- **Authorization on every state-changing endpoint** via Policy + `Gate::authorize()` / `#[Authorize]`; `#[UsePolicy]` on the model when auto-discovery doesn't apply.
- **`env()` only inside `config/*.php`.** Everywhere else: `config()`.
- **Dispatch after commit.** Inside `DB::transaction`, queue with `->afterCommit()`.
- **No debug residue.** No `dd()`, `dump()`, `ray()` committed.

## Choosing the frontend paradigm

Detect from `composer.json` rather than assuming: `livewire/livewire` → Livewire; `inertiajs/inertia-laravel` (+ `@inertiajs/vue3`|`react`) → Inertia; `filament/filament` → Filament (first-class, not a Blade add-on); otherwise server-rendered Blade. Don't mix paradigms in one feature without a stated reason.

## Testing conventions

- Name tests as sentences: `it('refunds the order when the webhook arrives')`.
- Use Laravel fakes, not brittle mocks: `Mail::fake()`, `Queue::fake()`/`Bus::fake()`, `Notification::fake()`, `Http::fake()`, `Storage::fake()`, `Event::fake([Explicit::class])`.
- Every protected endpoint gets both an allowed and a denied authorization test.
- Match the project's runner (Pest vs PHPUnit) and DB strategy (`RefreshDatabase` vs transactions) — don't introduce a new one.

## When in doubt

- Read 3 sibling files (controllers, Actions, components) before introducing a new pattern. Consistency with the codebase beats personal preference.
- Run `php artisan about` and read `composer.json` to learn the stack (queue driver, runtime, auth, search, first-party packages) before deciding.
- The full catalog of antipatterns this pack's agents refuse to ship is in [reference/antipatterns.md](reference/antipatterns.md).
