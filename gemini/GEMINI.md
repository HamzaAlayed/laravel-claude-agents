# GEMINI.md — Project Conventions

Read this every session. Every agent reads this. Keep terse, current, accurate. Stale guidance costs more than no guidance.

---

## Mission

<!-- TODO: one sentence — what does this product do, for whom, why -->

## Tech stack

- **PHP** 8.4
- **Laravel** 13
- **Frontend:** Inertia v3 + React 19
- **Styling:** Tailwind CSS v4
- **Build:** Vite + Wayfinder Vite plugin (`@laravel/vite-plugin-wayfinder` v0)
- **Routing types:** Wayfinder (`laravel/wayfinder` v0) — auto-generates TypeScript from controllers + routes
- **Auth:** Fortify (`laravel/fortify` v1)
- **AI:** `laravel/ai` v0 (first-party AI SDK)
- **MCP:** `laravel/mcp` v0 (server) + Laravel Boost MCP (`laravel/boost` v2, dev)
- **Testing:** Pest v4 + PHPUnit v12
- **Formatting:** Pint v1 — run with `--format agent`
- **Linting (JS):** ESLint v9 + Prettier v3
- **Logging tail:** Pail (`laravel/pail` v1) — `php artisan pail`
- **Local dev:** Sail (`laravel/sail` v1)
- **Console UX:** `laravel/prompts` v0 for interactive Artisan commands
- **Database:** TODO (Postgres vN / MySQL vN)
- **Cache + queue:** TODO (Redis / DB / SQS)
- **Queue manager:** TODO (Horizon / Supervisor / Vapor / none)
- **Runtime:** TODO (PHP-FPM / Octane + Swoole|RoadRunner|FrankenPHP / Vapor)
- **Search:** TODO (Scout + Meilisearch / Typesense / Algolia / none)
- **Mobile:** TODO (iOS / Android / RN / Expo / none)
- **Hosting:** TODO (Forge / Vapor / Envoyer / Kamal / k8s / bare)
- **CI/CD:** TODO (GitHub Actions / GitLab / etc.)
- **Observability:** TODO (Pulse / Telescope / Sentry / Datadog / OpenTelemetry)

## Boost is your first tool

Laravel Boost is an MCP server tailored to this app. Prefer Boost tools over shell + file reads:

- **`search-docs`** — version-specific docs. **Use before every code change.** Multiple broad queries: `["rate limiting", "routing"]`. Don't include package names in query (already scoped). Words = AND. `"quoted phrases"` = exact order. Multiple queries = OR.
- **`database-query`** — read-only SQL. Use instead of tinker for inspection.
- **`database-schema`** — inspect tables before writing migrations or models.
- **`get-absolute-url`** — resolve URL scheme + port. Use before sharing URLs.
- **`browser-logs`** — recent browser errors / exceptions. Ignore old entries.
- **`tinker`** — execute PHP in app context, sparingly. Single quotes for shell wrapper: `php artisan tinker --execute 'User::where("active", true)->count();'`. No new models without approval. Prefer Artisan commands.

## Skills (auto-trigger by domain)

Activate when working in matching domain. Don't wait until stuck.

- **`laravel-best-practices`** — any Laravel PHP work (controllers, models, migrations, Form Requests, Policies, jobs, queries, caching, authz, validation, queues, routes)
- **`inertia-react-development`** — React pages, forms, `<Link>`, `<Form>`, `useForm`, `useHttp`, `setLayoutProps`, `router`, deferred props, prefetching, optimistic updates, polling
- **`tailwindcss-development`** — any HTML / JSX with Tailwind classes. Skip for pure backend, build config, vanilla CSS.
- **`pest-testing`** — any test work in `tests/Feature/`, `tests/Unit/`, `tests/Browser/`. Pest 4 features. Smoke testing. Architecture tests. Browser testing (`visit`, `click`, `fill`).
- **`wayfinder-development`** — frontend calls backend. Generate typed routes. Import from `@/actions` / `@/routes`. **Never hardcode URLs.**
- **`fortify-development`** — login, register, password reset, email verification, 2FA, password confirmation, profile updates. `app/Actions/Fortify/`. `config/fortify.php`.
- **`ai-sdk-development`** — `Laravel\Ai\` namespace. Agents, chat, generation, embeddings, RAG, streaming, tools, provider failover.
- **`mcp-development`** — Laravel MCP only. `make:mcp-*`, `mcp:inspector`, `routes/ai.php`, Tool / Resource / Prompt classes.
- **`php-mcp-server-generator`** — generate full PHP MCP server project with official SDK.

## Agent delivery model

14 specialist agents available. Launch orchestrator with `@delivery-coordinator`. It routes work to specialists. Direct agent calls also OK.

| Phase | Agent | Output |
|---|---|---|
| Discovery | `business-analyst` | `docs/requirements/<slug>.md` |
| Prioritization | `product-owner` | `docs/backlog/<story-id>.md`, roadmap |
| Architecture | `solution-architect` (Opus) | `docs/adr/NNNN-*.md` |
| Design | `ui-ux-designer` | `docs/design/<feature>/*` |
| Breakdown | `tech-lead` (Opus) | `docs/breakdowns/<epic>.md` |
| Backend impl | `backend-developer` | Controllers, FormRequests, Resources, Actions, Jobs, tests |
| Database impl | `database-developer` | Migrations, models, factories, seeders |
| Frontend impl | `frontend-developer` | Inertia React pages + tests |
| Mobile impl | `mobile-developer` | iOS / Android / RN + tests |
| Package dev | `package-developer` | Composer package, tests, README |
| Code review | `tech-lead` (Opus, read-only) | Review findings |
| Security review | `security-engineer` (read-only) | `docs/security/<feature>.md` |
| Test design + run | `qa-engineer` | Pest suite + `docs/qa/release-*.md` |
| CI/CD + infra | `devops-engineer` | Pipeline, IaC, runbooks |
| Docs | `technical-writer` | API ref, guides, release notes |
| Delivery rhythm | `scrum-master` (Haiku) | Sprint plan, blockers, retros |

`tech-lead` + `security-engineer` are read-only. Produce findings, not edits.

## Repository layout

```
app/
  Actions/                <!-- domain logic (preferred over fat controllers) -->
  Actions/Fortify/        <!-- CreateNewUser, UpdateUserProfileInformation, etc. -->
  Http/
    Controllers/
    Requests/             <!-- Form Requests -->
    Resources/            <!-- API Resources -->
    Middleware/
  Models/
  Policies/
  Providers/
  Jobs/
  Events/
  Listeners/
bootstrap/
  app.php                 <!-- L11+ middleware, exceptions, routing -->
config/
database/
  migrations/
  factories/
  seeders/
docs/
  adr/
  architecture/
  requirements/
  design/
  qa/
  runbooks/
  delivery/
resources/
  js/
    pages/                <!-- Inertia React pages -->
    actions/              <!-- Wayfinder-generated typed action calls -->
    routes/               <!-- Wayfinder-generated typed named routes -->
  css/
routes/
  web.php
  api.php
  console.php             <!-- L11+ scheduler -->
  ai.php                  <!-- MCP routes (if used) -->
tests/
  Feature/
  Unit/
  Browser/                <!-- Pest 4 browser tests, no Dusk -->
```

## Conventions

### Code

- **Style:** PSR-12 via Pint. Run `vendor/bin/pint --dirty --format agent` before finalizing. Never `--test`. Just fix.
- **Static analysis:** Larastan / PHPStan at level TODO. Config: `phpstan.neon`.
- **Strict types:** `declare(strict_types=1);` every new PHP file.
- **Control structures:** always curly braces, even single-line bodies.
- **Constructors:** PHP 8 promotion — `public function __construct(public GitHub $github) {}`. No empty `__construct()` unless private.
- **Types:** explicit return types + param types on every method. `function isAccessible(User $user, ?string $path = null): bool`
- **Enum keys:** TitleCase — `FavoritePerson`, `BestLake`, `Monthly`.
- **Comments:** PHPDoc blocks over inline. Inline only for exceptionally complex logic. Array shapes in PHPDoc.
- **Names:** descriptive. `isRegisteredForDiscounts`, not `discount()`.
- **Reuse:** check existing components before writing new.
- **Errors:** typed exceptions extending framework or project base. Generic `\Exception` = finding.
- **Logging:** structured `Log::info('event.name', ['context' => '...'])`. Lowercase.dot.notation. No interpolation.

### Laravel-specific

- **Artisan make:** always for new files. `--no-interaction` always. `--help` to discover params.
- **Generic class:** `php artisan make:class`.
- **New models:** create factory + seeder too. Ask user about other options via `make:model --help`.
- **APIs:** Eloquent API Resources + API versioning by default. Unless existing routes don't, then follow convention.
- **URLs:** named routes via `route()`. Frontend: Wayfinder typed functions. **No hardcoded URLs anywhere.**
- **Mass assignment:** `$fillable` set deliberately. Never `Model::create($request->all())` without Form Request filtering.
- **Authz:** Policy + `authorize()` for every state-changing endpoint. No ad-hoc ownership checks.
- **Response:** API Resources. Never raw model serialization.
- **Transactions:** multi-row writes wrap in `DB::transaction(...)`. Jobs dispatched inside transactions use `->afterCommit()`.
- **Config:** `config('feature.key')`. **Never `env()` outside `config/*.php`** — breaks `config:cache`.

### Inertia v3 + React 19

- Pages in `resources/js/pages`. Server: `Inertia::render('Page', [...])`.
- Use v3 features: `useHttp` for standalone HTTP, optimistic updates with auto-rollback, `useLayoutProps`, instant visits, `@inertiajs/vite` SSR.
- **`Inertia::lazy()` removed → use `Inertia::optional()`.** Works with dot-notation paths in nested arrays.
- Deferred props need empty state with pulsing / animated skeleton.
- Axios removed. Use built-in XHR client. Install Axios separately only if needed.
- Event renames: `invalid` → `httpException`, `exception` → `networkError`.
- `router.cancel()` → `router.cancelAll()`.
- No `future` config namespace (v2 future options always enabled).

### Wayfinder

- Frontend imports from `@/actions/` (controllers) or `@/routes/` (named routes).
- Methods: `.url()`, `.get()`, `.post()`, `.form()`. Query params + route model binding supported.
- Regenerate: `php artisan wayfinder:generate` (or via Vite plugin auto-watch).
- Tree-shaking works. Don't worry about bundle size from unused routes.

### Testing (Pest 4)

- **Every change programmatically tested.** Write or update a test. Run it. Pass.
- Create: `php artisan make:test --pest <Name>` (feature) or `--unit` (unit). Most tests = feature.
- Run minimum needed: `php artisan test --compact --filter=<Name>`.
- **Do not delete tests without approval.**
- Factories with custom states preferred over manual model setup.
- Faker: match existing convention (`$this->faker->word()` or `fake()->randomDigit()`).
- Browser tests in `tests/Browser/`. Pest 4 native (`visit`, `click`, `fill`, etc.). No Dusk.
- Use Laravel fakes instead of mocking framework: `Mail::fake()`, `Queue::fake()`, `Http::fake()`, `Event::fake([...])`, `Storage::fake()`.

### Git

- Branch: TODO (e.g. `feat/<ticket>-short-slug`)
- Commit: TODO (Conventional Commits?)
- PR: TODO (size limit, description template, linked issue)

### Architecture

- ADRs in `docs/adr/`. Read before structural changes.
- High-level diagram: `docs/architecture/overview.md`.

## Frontend bundling

User doesn't see frontend change → ask if they ran `npm run build`, `npm run dev`, or `composer run dev`.

`Illuminate\Foundation\ViteException: Unable to locate file in Vite manifest` → run `npm run build`, or ask user.

## Hard constraints

- **No documentation files unless explicitly requested.**
- **No verification scripts when tests cover it.** Unit + feature tests prove correctness.
- **Secrets never in repo, `.env.*` committed to git, or logs.** Live in TODO (Vault / Forge env / Vapor env).
- **No `php artisan migrate:fresh`, `db:wipe`, or `tinker` against prod.** Guarded by `scripts/block-prod-artisan.sh`.
- **No destructive SQL on `prod-*` databases.** Guarded by `scripts/block-prod-destructive-sql.sh`.
- **`APP_DEBUG=true` in prod = P0.**
- **No `env()` outside `config/*.php`** — breaks `config:cache`.
- **No major-version bumps of Laravel, PHP, or first-party packages without an ADR.**
- **No new `composer require` without checking license + updating `composer.lock` deliberately.**
- **No new base folders without approval.** Stick to existing structure.
- **No dependency changes without approval.**

## Definition of done

Change done when:

1. `vendor/bin/pint --dirty --format agent` clean
2. `vendor/bin/phpstan analyse` clean at project level
3. `php artisan test --compact` green (relevant filter, then full suite)
4. `npm run build` clean (if frontend changed)
5. Wayfinder regenerated if controllers / routes changed
6. New env vars in `.env.example` + documented here
7. Affected docs updated (`docs/`, `README.md`, `CHANGELOG.md`)
8. PR description names user-visible change + links story

## Human checkpoints

Always require human decision before proceeding:

- Architecture changes with multi-year cost or vendor-lock-in implications
- Schema changes touching regulated data (PII, PHI, PCI). Any destructive migration.
- Changes to authn (Fortify), authz (Policies / Gates), billing (Cashier), audit logging
- New mass-mail or push-notification campaigns
- App-store submissions (mobile)
- Public-facing brand or legal language
- Active security incidents. Decisions to accept residual risk.
- `APP_KEY` rotation. DNS / TLS changes. Production `terraform apply`.

## Replies

- Concise. Focus on what matters. Skip obvious details.

## Glossary

<!-- TODO: domain terms not obvious from code. List Eloquent model names mapped to domain concepts. -->

## Useful commands

```bash
# Quality
./vendor/bin/sail vendor/bin/pint --dirty --format agent      # format dirty files only
vendor/bin/phpstan analyse                  # static analysis
./vendor/bin/sail artisan test --compact                  # full suite
./vendor/bin/sail artisan test --compact --filter=<Name>  # filtered

# Generate
./vendor/bin/sail artisan make:test --pest <Name>         # Pest feature test
./vendor/bin/sail artisan make:test --pest --unit <Name>  # Pest unit test
./vendor/bin/sail artisan make:controller <Name> --help   # discover make: options
./vendor/bin/sail artisan wayfinder:generate              # regenerate TS routes / actions

# Inspect
./vendor/bin/sail artisan route:list                      # all routes
./vendor/bin/sail artisan route:list --except-vendor      # project routes only
./vendor/bin/sail artisan db:show                         # database overview
./vendor/bin/sail artisan db:table <name>                 # column info
./vendor/bin/sail artisan about                           # framework / config / cache state
./vendor/bin/sail artisan config:show <key>               # config value (dot notation)

# Local
./vendor/bin/sail artisan serve & npm run dev             # dev server + Vite
./vendor/bin/sail artisan pail                            # tail logs (live)
./vendor/bin/sail artisan queue:listen                    # process queue
./vendor/bin/sail artisan tinker                          # PHP in app context (sparingly)

# MCP (Boost)
# Prefer Boost tools over shell. Use the MCP, not manual cat / grep / curl:
# search-docs, database-query, database-schema, get-absolute-url, browser-logs
```
