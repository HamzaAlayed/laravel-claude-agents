# Production security checklist eval

The committed [per-trial scores](2026-11-27-checklist-trials.jsonl) and
[fixture evidence](2026-11-27-checklist-evidence.json) cover both security
comparisons.

**Date** November 27, 2026

## Method

The comparison uses the Guild security engineer profile and security skill at
`31dfca0` versus the current profile and skill with the production checklist.
Native Claude Code 2.1.326 runs Felix as a named custom agent on
`claude-opus-5-5`, with matched medium effort, the same prompt, and Read,
Glob, and Grep. Each run receives the versioned skill as an ordinary file
inside the fixture, with the production checklist available for the updated
profile. This measures the guidance when supplied to the agent. Skill
autoloading and the default effort of the installed profile are outside the
comparison.

The Newsroom fixture uses application source from `tests/fixture-app`.
Laravel 13.43.0 generated a local route inventory and a snapshot of the
effective configuration after caching. The edge, identity, AWS, CI, and
operational records are synthetic. The fixture has no network listener.
No application, cloud, or production endpoints were probed.

Three before/after pairs used fresh sessions, with order reversed in round
two. An interrupted setup trial was excluded after correcting the simulated
browser origin to be unapproved and same-site. The interrupted trial has
no Claude Code cost receipt.

The [answer key](../../tests/eval/fixtures/security-checklist/answer-key.md)
defines 11 confirmed issues, two required evidence gaps, 11 applicable
release blockers, and five clean controls. A finding earns credit for a
correct location, mechanism, and targeted defensive fix or next verification.
A named hold requires an explicit release condition tied to the individual
item and a clearance check. Unsafe alternatives in clearance criteria are
scored separately. The audit can score on equivalent wording.
Checklist IDs and responsible roles are tracked separately.

## Results

| Profile and guide | Confirmed issues | Evidence gaps | Named holds | Holds without unsafe exits | No-go decisions | Median audit wall time | Median estimated cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before | 30/33 | 6/6 | 27/33 | 25/33 | 3/3 | 130.1 s | $0.409 |
| After | 30/33 | 6/6 | 33/33 | 32/33 | 3/3 | 98.7 s | $0.603 |

Six completed Claude Code runs cost $2.91 at estimated list prices.

| ID | Scored check | Before found | After found | Before held | After held |
| --- | --- | ---: | ---: | ---: | ---: |
| APP-02 | Missing post ownership check | 3/3 | 3/3 | 3/3 | 3/3 |
| APP-05 | Debug enabled after config caching | 3/3 | 3/3 | 3/3 | 3/3 |
| AUTH-01 | Session cookie lacks Secure | 3/3 | 3/3 | 0/3 | 3/3 |
| AUTH-03 | Privileged sign-in allows password only | 3/3 | 3/3 | 3/3 | 3/3 |
| DATA-03 | Database TLS lacks verified server identity | 3/3 | 3/3 | 0/3 | 3/3 |
| WEB-06 | Credentialed CORS accepts the preview origin | 3/3 | 3/3 | 3/3 | 3/3 |
| FILE-07 | Shared cache returned a private attachment | 3/3 | 3/3 | 3/3 | 3/3 |
| DATA-09 | Suspected compromised key remains accepted | 3/3 | 3/3 | 3/3 | 3/3 |
| CI-04 | Confirmed high dependency issue does not block merge | 3/3 | 3/3 | 3/3 | 3/3 |
| IR-06 | No acknowledged security alert drill | 3/3 | 3/3 | 3/3 | 3/3 |
| IR-09 | No restore drill with measured RTO/RPO | 3/3 | 3/3 | 3/3 | 3/3 |
| OPS-07 | EC2 metadata tokens optional | 3/3 | 3/3 | — | — |
| WEB-11 | Missing nosniff on the script response | 0/3 | 0/3 | — | — |

All runs made a no-go decision. The updated guidance changed blocker
classification while leaving issue recall flat. The baseline always found the
missing Secure flag and incomplete database server authentication and
treated them as advisory. The checklist-guided agent made both release
conditions every time. It used the expected ID for each of the 36
actionable findings or evidence gaps across its three runs.

Each checklist-guided audit distinguished the required alert and restore
evidence gaps from verified failures. It correctly treated optional IMDS
tokens as hardening in the fixture's scope. The JavaScript response record
showed only Content-Type. All reports noticed that the header evidence was
thin and none made missing `nosniff` an actionable confirmed finding. This
receipt did not explicitly say whether its header map was exhaustive.

The named-hold counts credit an identified blocker with a named clearance
check. The stricter column excludes two unsafe baseline clearance proposals and one
unsafe proposal in the updated runs. One baseline would allow a temporary compromise-key
fallback in the serving path. One baseline and one updated audit allowed
the private attachment hold to clear if the anonymous response was a cache
miss or was uncached. The anonymous request must also be denied. The
updated runs consistently required retirement of the compromised key
from serving systems.

No report made an unsupported hold out of the five scored clean controls.
The extra source findings, including mass assignment, are outside the
denominators above. Time and cost summarize this one fixture and the
chosen settings, with variable prompt-cache usage. They are descriptive.

Both runners compiled and 97 evaluation tests and 552 guardrails passed.

## Original invocation

This was the original invocation. The runner now emits the complete asset capture described below.

```sh
composer --working-dir=tests/fixture-app install
python3 tests/eval/run-security-checklist.py \
  --baseline 31dfca0 \
  --vendor tests/fixture-app/vendor \
  --output tests/eval/results/security-checklist-repeat
```

The original run's prompt, source digests, synthetic evidence, and Claude
Code transcripts are in `tests/eval/results/20261127-security-checklist-scored/`.

## Follow-up on attachment clearance and response headers

Felix and FILE-07 now require a same-URL staging retest through the CDN.
An authorized actor must receive the attachment and an anonymous actor
must be denied with no attachment bytes or usable access link. Cache
status supplements the authorization evidence.

The runner requests the benign editor JavaScript file once from an
isolated loopback static server and saves the complete observed response
headers. The server is closed before Felix runs. The former partial
response in the synthetic edge export is replaced by this receipt.
It establishes the fixture's header behavior. CDN behavior remains
unmeasured. The private attachment, identity, database, CI, and
operations evidence is unchanged.

The comparison uses the previous checklist-guided profile and guide
from the first eval as its baseline. Source digests match the first
eval's candidate digests. Both arms receive the revised fixture and
the original prompt, model, effort, and read-only tools. Three
before/after pairs run in separate fixture copies in parallel, with
the order within the second pair reversed again. Cost is reported
at the CLI's estimated list prices. Wall time is excluded from the
comparison because the pairs ran concurrently.

The FILE-07 follow-up scores a clear requirement for a paired
authorized success and anonymous denial. Ambiguous advice that
also accepts an uncached anonymous success does not score. WEB-11
requires a confirmed finding from the complete asset receipt and
a fix or delivered-response check. The other scored controls use the
original criteria.

### Follow-up results

| Profile and evidence | Reports requiring anonymous denial | Missing nosniff observed locally | Confirmed issues | Evidence gaps | Named holds | No-go decisions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous, partial header record | 2/3 | 0/3 | 30/33 | 6/6 | 33/33 | 3/3 |
| Previous, complete receipt | 2/3 | 3/3 | 33/33 | 6/6 | 33/33 | 3/3 |
| Updated, complete receipt | 3/3 | 3/3 | 33/33 | 6/6 | 33/33 | 3/3 |

Six completed follow-up runs cost $2.89 at estimated list prices.
Median before estimated cost $0.478.
Median after estimated cost $0.455.

The complete receipt changed header detection in both arms. Six of six
follow-up audits identified the missing header on the fixture asset and
asked for separate CDN evidence. The historical partial receipt yielded
zero detections in three audits with the prior checklist profile.

The previous profile required explicit anonymous denial in two of three
follow-up audits. Its remaining report asked for “no replay” and
`no-store` without specifying a denied anonymous response. Each updated
report required the authorized actor to receive the file and the
anonymous actor to be denied on the same CDN URL, without bytes or a
usable link. All still held the fixture release. The eval did not exercise
the private attachment route or clear the real-world control.

The captured headers and profile digests were verified. All 552
guardrails, 97 eval tests and 26 body-budget checks passed.

### Reproduce the follow-up

Use Python 3.12 or later, PHP, and a signed-in Claude Code CLI.
The previous profile, skill, and checklist snapshot is in the first
run's results directory.

```sh
composer --working-dir=tests/fixture-app install
python3 tests/eval/run-security-checklist.py \
  --baseline 31dfca0 \
  --baseline-files tests/eval/results/20261127-security-checklist-scored/checklist-profile \
  --vendor tests/fixture-app/vendor \
  --parallel-rounds 3 \
  --output tests/eval/results/security-clearance-repeat
```

The follow-up's full receipt, profile digests, transcripts, and scores
are in `tests/eval/results/20261127-security-clearance-live/`.
