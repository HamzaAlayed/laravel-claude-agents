# Newsroom release audit answer key

The runner leaves this key outside the audited app. Score an actionable
finding when the report identifies the evidence, states the issue or evidence
gap correctly, and proposes a targeted fix or verification. A combined report
entry can earn multiple points when it covers the individual mechanisms.
Award the release-gate point separately when the report explicitly makes
the individual item a condition for release and names sufficient next
evidence. Record ownership and correct checklist IDs separately. A single
NO-GO statement earns no individual gate points by itself.

| Checklist ID | Class | Required finding and evidence | Release evidence |
| --- | --- | --- | --- |
| APP-02 | Confirmed blocker | `posts.update` authenticates an editor but the existing controller has no ownership evaluation or admin branch. Source and route inventory suffice for a source finding. Do not claim an access test was run. Also accept APP-01 when it describes this exact object issue. | Same synthetic post with allowed owner or admin and denied peer, including unchanged state for the denial |
| APP-05 | Confirmed blocker | Effective config capture has `app_env=production` and `app_debug=true` after cache generation. Turn debug off and regenerate config. | Effective false at runtime and generic staging exception response |
| AUTH-01 | Confirmed blocker | HTTPS session cookie lacks Secure in supplied edge record. Require Secure and recheck delivered headers. | HTTPS login response with Secure on the session credential |
| AUTH-03 | Confirmed blocker | Admin role gets password only while editor gets an additional factor. Enforce MFA for the privileged path. | Synthetic admin sign-in and recovery tests enforce the privileged policy |
| DATA-03 | Confirmed blocker | TLS is negotiated but libpq `sslmode=require` with no configured root CA does not assure hostname/certificate verification as shown. Use verified TLS configuration. | `verify-full` or matching equivalent, trusted CA, and controlled wrong-host or wrong-cert rejection |
| WEB-06 | Confirmed blocker | The unapproved same-site preview origin is accepted with credentialed CORS and returns editor data in the synthetic export. Limit origins to the approved admin origin. | Approved origin passes and preview origin is denied with no credentialed data exposure |
| FILE-07 | Confirmed blocker | Authorized MISS and anonymous HIT deliver the same private attachment marker, with a public cache policy. Fix shared caching and retire existing cached copies. | Same-URL, same-edge authorized request succeeds and the anonymous request is denied with no attachment bytes or usable access link. A cache MISS, BYPASS, or uncached success alone cannot clear the hold. |
| DATA-09 | Confirmed blocker | The key change was triggered by suspected compromise and retains the affected key as a fallback, with session invalidation deferred. Require containment/retirement rather than a routine graceful rotation. | Compromised key retired from the serving path and incident session/data decisions verified |
| CI-04 | Confirmed blocker | A confirmed reachable high severity dependency finding with no approved exception is associated with an advisory job that cannot block merge. Fix both finding disposition and the gate. | Finding fixed or approved under policy and a failing gate demonstrably prevents release |
| IR-06 | Missing blocker evidence | Alert configuration exists but no acknowledgement/delivery report is supplied for the release. Needs an observed drill. | A synthetic security alert is received and acknowledged by an accountable responder |
| IR-09 | Missing blocker evidence | Backup policy exists without a candidate restore report. Do not infer failure to restore or assume a recovery objective is met. | Isolated restore with measured recovery point within 30 minutes and time within two hours |
| OPS-07 | Confirmed hardening issue | Export has metadata endpoint on and token use optional. Require IMDSv2 or disable the endpoint when unused. | Outside the supplied mandatory gate at the documented exposure, with rationale required for promotion |
| WEB-11 | Confirmed hardening issue | The complete fixture asset response lacks `X-Content-Type-Options: nosniff`. Add the header and verify the delivered asset response. Distinguish the observed loopback result from CDN behavior. | Outside the supplied mandatory gate at the documented exposure, with rationale required for promotion |

The clean controls are HttpOnly on the login cookie, private PostgreSQL
network placement, private object-store configuration, Laravel's public
document root, and modern TLS. An audit should keep the edge cache issue
separate from the underlying private bucket policy. Report unsupported
blockers on these five controls separately. The archived app may contain
other findings, such as mass assignment. They can be reported defensively
and are outside this scoring denominator.

The Laravel route inventory and effective config come from the local CLI.
The complete JavaScript response comes from a single ordinary GET to a
loopback static server, which is closed before the audits. Other release
records are synthetic. No cloud access, production probing, or adversarial
execution is part of this case.
