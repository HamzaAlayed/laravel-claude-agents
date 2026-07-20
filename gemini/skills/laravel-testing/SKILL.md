---
name: laravel-testing
description: "The Laravel test-authoring cookbook — fakes with exact assertion syntax, Pest v4 browser testing vs Dusk, factory states + sequences, time control, DB strategies. Use when writing or reviewing Pest / PHPUnit tests, reproducing a bug as a regression test, choosing between fakes and mocks, or setting up browser tests. Recipes only — test strategy and Ship / Hold verdicts stay with qa-engineer."
---

# Laravel Testing Cookbook

Match the project first: Pest vs PHPUnit from `composer.json`, DB strategy from existing tests (`RefreshDatabase` — transaction-based, skips migrating when the schema is current — vs `DatabaseMigrations` / `DatabaseTruncation`, both slower full resets needed for browser tests). Seeding: prefer L13's `#[Seed]` / `#[Seeder(OrderStatusSeeder::class)]` attributes over manual `$this->seed()` boilerplate; `#[UnitTest]` on a pure-logic method skips booting the app for just that test. Never introduce a second runner or strategy.

## Fakes — assertion syntax

Fake the framework primitive, assert the interaction. Never mock what Laravel fakes.

| Primitive | Setup | Assert |
|---|---|---|
| Mail | `Mail::fake()` | `Mail::assertSent(OrderShipped::class, fn ($m) => $m->hasTo($user->email))` · `assertQueued` · `assertNothingSent` |
| Notification | `Notification::fake()` | `Notification::assertSentTo($user, InvoicePaid::class, fn ($n, $channels) => in_array('mail', $channels))` |
| Queue / Bus | `Queue::fake()` / `Bus::fake()` | `Bus::assertDispatched(ProcessOrder::class, fn ($job) => $job->order->is($order))` · `assertChained` · `assertBatched` · `assertNotDispatched` |
| Event | `Event::fake([OrderShipped::class])` | `Event::assertDispatched(OrderShipped::class)` — **always pass the allowlist**: a bare `Event::fake()` suppresses model events and factories break silently |
| HTTP | `Http::fake(['api.stripe.com/*' => Http::response(['id' => 'ch_1'], 200)])` | `Http::assertSent(fn (Request $r) => $r->url() === … && $r['amount'] === 500)`. Fake success, 4xx, 5xx, and `Http::failedConnection()` timeout |
| Storage | `Storage::fake('avatars')` | `Storage::disk('avatars')->assertExists($path)` · `assertMissing` |
| Process | `Process::fake(['git *' => Process::result('ok')])` | `Process::assertRan(fn ($p) => str_contains($p->command, 'git'))` |

Jobs: `Bus::fake()` proves dispatch; invoking `$job->handle()` directly proves effect. Test both, plus `failed()`.

## Time

`$this->travelTo(now()->addDays(30))`, `$this->freezeTime()`, `$this->travelBack()`. Any TTL, expiry, or scheduling logic gets a time-travel test — never `sleep()`.

## Factories

- States for variants: `OrderFactory::new()->paid()->forUser($user)`. Never hand-build models in tests.
- `Sequence` for controlled variation: `->state(new Sequence(['status' => 'active'], ['status' => 'churned']))`.
- Relationships: `->has(Post::factory()->count(3))` / `->for($team)`. `recycle($tenant)` to share one parent across the tree — the multi-tenant test essential.
- `Model::factory()->make()->getAttributes()` for validation-payload arrays (doc-backed; `->raw()` exists but is undocumented).

## Browser tests

Detect first, then match: `pestphp/pest-plugin-browser` (Pest v4 — current) vs `laravel/dusk` (legacy — keep, don't migrate mid-PR).
Pest v4: `visit('/dashboard')->assertSee(…)`, plus free checks Dusk lacks — `assertNoJavascriptErrors()`, `assertNoConsoleLogs()`, `assertNoAccessibilityIssues()`. Use them on every page test.

## Livewire / Inertia / Filament

- Livewire: `Livewire::test(CreateOrder::class)->set('email', 'x@y.z')->call('save')->assertHasNoErrors()->assertDispatched('order-created')`.
- Inertia: `$this->get(route('orders.index'))->assertInertia(fn (Assert $page) => $page->component('Orders/Index')->has('orders', 3))`.
- Filament: `livewire(CreateOrder::class)->fillForm([...])->call('create')->assertNotified()`.

## Coverage that must exist

- Every protected endpoint: one allowed + one denied authorization test (403), and an unauthenticated test (401) for APIs.
- Every validation rule that guards money, quantity, or state: a failing-input test asserting `assertJsonValidationErrors` (APIs) or `assertInvalid` / `assertRedirectBackWithErrors` (classic web forms).
- Every production bug: a regression test that fails on the old code. Name it after the bug.
- Feature tests assert three layers: status, shape (`assertJsonPath`, `assertJsonStructure`), and DB state (`assertDatabaseHas`, `assertDatabaseCount`).
