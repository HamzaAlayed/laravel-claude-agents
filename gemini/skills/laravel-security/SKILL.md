---
name: laravel-security
description: "The Laravel security-review cookbook — STRIDE, application security checks, advisory lookup, finding format, and production readiness. Use for threat modeling, sensitive PR review, production security audits, or vulnerability triage. Findings only — fixes land with the owning builder after human awareness."
---

# Laravel Security Review

Verify before asserting. Trace the exploit path (route → middleware, incl. `#[Middleware]`/`#[Authorize]` controller attributes on L13 → FormRequest → Policy → query) before reporting — a grep over routes/middleware alone misses attribute-based coverage. Unverifiable → mark **Suspected** + the evidence needed. Never invent CVE IDs or CVSS scores — cite only advisories actually fetched.

For release readiness, open the [production security checklist](references/production-security-checklist.md). Record applicable check IDs, verified evidence, and blocker owners.

## STRIDE on Laravel primitives

| Threat | Laravel check |
|---|---|
| **S**poofing | Guard per route group correct (`config/auth.php`); session fixation (`Session::regenerate()` on login); Sanctum SPA cookie domain matches frontend origin; password-reset tokens single-use + time-bound |
| **T**ampering | Mass assignment (`$fillable` deliberate, no `$guarded = []` on user input); hidden-field trust; signed URLs (`URL::signedRoute()`) for out-of-band links; Livewire scalar props client-settable → `#[Locked]` on IDs used in authz |
| **R**epudiation | State-changing actions logged with actor + tenant; audit records append-only |
| **I**nfo disclosure | API Resources (never raw models — hidden columns leak); error pages / debug mode (`APP_DEBUG` prod), stack traces in responses, source maps; logs redact PII + secrets |
| **D**oS | Unbounded queries (no pagination), upload size/count limits, queue flooding, missing `RateLimiter::for()` on auth / OTP / expensive endpoints |
| **E**levation | Policy on every state-changing route (`can:` middleware, FormRequest `authorize()`, `Gate::authorize()`, or L13 `#[Authorize]` attribute); policy registration includes `#[UsePolicy]` on models alongside auto-discovery; IDOR — route-model binding scoped (`->scopeBindings()` or tenant global scope); `Gate::before` not granting wholesale |

Document trust boundaries crossed + data sensitivity at each.

## The checklist beyond STRIDE

- **SQL / query**: no `DB::raw` with concatenated input — bindings only; `orderBy(request('sort'))` is injection — allowlist the column.
- **XSS**: `{!! !!}` only with a written safety argument; user HTML → sanitize (mews/purifier or equivalent); JSON in Blade via `@js` / `Js::from`.
- **Uploads**: validate `mimetypes:` (server-side, not extension), size; store on non-public disk; never trust client filename (`hashName()`); images → strip EXIF where PII-relevant.
- **CSRF**: web routes covered; deliberate exceptions (`preventRequestForgery(except:)` in `bootstrap/app.php` on L13 — `validateCsrfTokens` is the deprecated L11/12 alias, middleware class renamed `VerifyCsrfToken` → `PreventRequestForgery`) each justified. L13 verifies origin via `Sec-Fetch-Site` first, token fallback second — HTTPS-only, so check reverse proxies/CDNs don't strip the header, and test exclusions reference `PreventRequestForgery::class`.
- **Secrets**: keep secrets out of the repo and logs. Read effective settings via `config()`. Use the installed secret scanner with redaction. Rehearse `APP_PREVIOUS_KEYS` for planned rotation. Suspected `APP_KEY` compromise calls for the incident procedure, including containment and retirement of the compromised key from serving systems.
- **Jobs / queues**: PII-bearing jobs `ShouldBeEncrypted`; failed-job payloads (`failed_jobs.payload`) hold serialized PII — retention policy exists.
- **Headers / CORS**: inspect effective CORS settings and delivered responses. Credentialed requests need explicit origins. Check `Secure`, `HttpOnly`, and `SameSite` on session cookies.

## Advisory lookup

1. `composer audit` (uses the packagist advisory DB) — zero known-vulnerable deps to pass.
2. For a specific package/version: GitHub Security Advisories + the package's own security policy. Fetch, don't recall.
3. Framework CVEs: laravel/framework security releases — check the project's exact major is still patched.

## Finding format

One finding = severity (CVSS 4.0 estimate — 3.1 when that's all the advisory carries — or Critical/High/Med/Low + why) + OWASP Top 10:2025 tag + CWE ID · exploit path (concrete route/file:line chain) · blast radius (data / tenants affected) · remediation naming the Laravel primitive ("add `OrderPolicy::update` + `can:update,order` on the route", not "add authorization"). Sort by severity. **Suspected** section separate from **Confirmed**.
