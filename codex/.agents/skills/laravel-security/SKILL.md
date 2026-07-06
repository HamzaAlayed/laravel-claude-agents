---
name: laravel-security
description: "The Laravel security-review cookbook — STRIDE applied to Laravel primitives, the authn / authz / mass-assignment / upload / injection checklist, advisory lookup procedure, and the finding format. Use when threat-modeling a feature, reviewing a PR that touches auth / PII / billing / uploads / middleware, or triaging a suspected vulnerability. Findings only — fixes land with the owning builder after human awareness."
---

# Laravel Security Review

Verify before asserting. Trace the exploit path (route → middleware → FormRequest → Policy → query) before reporting. Unverifiable → mark **Suspected** + the evidence needed. Never invent CVE IDs or CVSS scores — cite only advisories actually fetched.

## STRIDE on Laravel primitives

| Threat | Laravel check |
|---|---|
| **S**poofing | Guard per route group correct (`config/auth.php`); session fixation (`Session::regenerate()` on login); Sanctum SPA cookie domain matches frontend origin; password-reset tokens single-use + time-bound |
| **T**ampering | Mass assignment (`$fillable` deliberate, no `$guarded = []` on user input); hidden-field trust; signed URLs (`URL::signedRoute()`) for out-of-band links; Livewire scalar props client-settable → `#[Locked]` on IDs used in authz |
| **R**epudiation | State-changing actions logged with actor + tenant; audit records append-only |
| **I**nfo disclosure | API Resources (never raw models — hidden columns leak); error pages / debug mode (`APP_DEBUG` prod), stack traces in responses, source maps; logs redact PII + secrets |
| **D**oS | Unbounded queries (no pagination), upload size/count limits, queue flooding, missing `RateLimiter::for()` on auth / OTP / expensive endpoints |
| **E**levation | Policy on every state-changing route (`can:` middleware, FormRequest `authorize()`, or `Gate::authorize()`); IDOR — route-model binding scoped (`->scopeBindings()` or tenant global scope); `Gate::before` not granting wholesale |

Document trust boundaries crossed + data sensitivity at each.

## The checklist beyond STRIDE

- **SQL / query**: no `DB::raw` with concatenated input — bindings only; `orderBy(request('sort'))` is injection — allowlist the column.
- **XSS**: `{!! !!}` only with a written safety argument; user HTML → sanitize (mews/purifier or equivalent); JSON in Blade via `@js` / `Js::from`.
- **Uploads**: validate `mimetypes:` (server-side, not extension), size; store on non-public disk; never trust client filename (`hashName()`); images → strip EXIF where PII-relevant.
- **CSRF**: web routes covered; deliberate exceptions (`validateCsrfTokens(except:)` in `bootstrap/app.php`, L11+) each justified.
- **Secrets**: never in repo, `.env.*` committed, or logs. `config()` only — `env()` outside `config/*.php` breaks under cache and hints at drift. Scan diffs: `gitleaks detect`.
- **Jobs / queues**: PII-bearing jobs `ShouldBeEncrypted`; failed-job payloads (`failed_jobs.payload`) hold serialized PII — retention policy exists.
- **Headers / CORS**: `config/cors.php` origins explicit (no `*` with credentials); cookies `Secure`, `HttpOnly`, `SameSite`.

## Advisory lookup

1. `composer audit` (uses the packagist advisory DB) — zero known-vulnerable deps to pass.
2. For a specific package/version: GitHub Security Advisories + the package's own security policy. Fetch, don't recall.
3. Framework CVEs: laravel/framework security releases — check the project's exact major is still patched.

## Finding format

One finding = severity (CVSS 3.1 estimate or Critical/High/Med/Low + why) · exploit path (concrete route/file:line chain) · blast radius (data / tenants affected) · remediation naming the Laravel primitive ("add `OrderPolicy::update` + `can:update,order` on the route", not "add authorization"). Sort by severity. **Suspected** section separate from **Confirmed**.
