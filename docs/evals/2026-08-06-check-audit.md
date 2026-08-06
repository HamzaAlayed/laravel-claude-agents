# Answer-key check audit — 2026-08-06

Every check the eval harness dispatches, classified by evidence source. Trigger:
v1.37.0 replaced `check_log 'update'` — a grep for one English word in
nondeterministic prose — after the rubric judge correctly failed the key on a
run that closed the planted IDOR without using the word. The
[project-state review](../requirements/2026-08-05-project-state-review.md)
(gap 5) asked whether the other checks carry the same disease. This audit
answers that, check by check, so the classification is never re-derived.

## Classification vocabulary

- **artifact** — inspects files/code/diff the run produced on disk. The gold
  standard: immune to wording.
- **fixture-noun** — greps the transcript for a proper noun or API name from
  the fixture (`PostController`, `withCount`, `LegacyPayments`). Sound: any
  correct report *must* contain these — they are the answer, not a wording
  choice.
- **format-contract** — greps for a string the Interface block mandates
  verbatim (`NOT-CHECKED`, `done when:`). Sound: the contract *is* the string.
- **free-prose** — greps for an ordinary English word the model may synonymise.
  This is the `check_log 'update'` disease. Two instances found; both fixed
  in this release.
- **hardened-prose** — a former free-prose grep whose vocabulary was widened to
  the model's synonyms and ratchet-pinned additive-only. Acceptable ONLY for a
  report-only case with no artifact to inspect; the rubric judge stays on as
  the dissenter for exactly these.

## The table

| Case | Check | Kind | Verdict |
| ---- | ----- | ---- | ------- |
| n-plus-one | `check_log 'with\(\|eager[- ]?load'` | fixture-noun (API) | sound — alternation covers both idioms |
| n-plus-one | `check_log 'withCount'` | fixture-noun (API) | sound |
| n-plus-one | `check_log 'PostController\|index\.blade'` | fixture-noun | sound |
| n-plus-one | `check_log 'comments'` | fixture-noun (relation name) | sound |
| policy | `check_file PostPolicy.php` | artifact | sound |
| policy | `check_in_files 'authorize\|Gate::\|->can\(\|can:'` (controller) | artifact | sound |
| policy | `check_update_guarded` | artifact | sound — the v1.37.0 conversion, keep as reference implementation |
| action | `check_file_under app/Actions *.php` | artifact | sound |
| action | `check_in_files 'Action'` (controller) | artifact | sound — a controller that delegates must reference the class; acceptable breadth |
| action | `check_not_in_files 'Mail::to'` (controller) | artifact | sound |
| action | `check_touched tests/` | artifact | sound |
| tests | `check_touched tests/` | artifact | sound |
| tests | `check_in_files 'posts\.update\|->put\(\|->patch\('` | artifact | sound |
| tests | `check_in_files 'assertForbidden\|403'` | artifact | sound |
| tests | `check_log 'NOT-CHECKED'` | format-contract | sound — the Interface block mandates the literal string |
| feature | `check_file_under database/migrations *tags*.php` | artifact | sound |
| feature | `check_file_under app/Models Tag.php` | artifact | sound |
| feature | `check_in_files 'tag' routes` | artifact | sound |
| feature | `check_touched tests/` | artifact | sound |
| feature | `check_delegated 2` | artifact (board feed) | sound — negative-controlled at introduction (v1.34.0) |
| feature | `check_log 'done when:'` | format-contract | sound — Interface-mandated header string |
| hygiene | `check_log 'duplicate'` | **free-prose → hardened-prose** | **FRAGILE — fixed this release.** A run classifying the UUID twins as "identical"/"redundant" fails the key while being right. Now `'duplicat\|identical\|redundan\|twin'` (stems cover duplicate/duplicated/duplication, redundant/redundancy). |
| hygiene | `check_log 'conflict'` | **free-prose → hardened-prose** | **FRAGILE — fixed this release.** "Contradicts" fails the key. Now `'conflict\|contradict\|disagree\|mutually exclusive'`. |
| hygiene | `check_log 'LegacyPayments'` | fixture-noun | sound |
| hygiene | inline `git diff --quiet -- docs/team/conventions.md` | artifact | sound — headless run must propose, not apply |
| teach | `check_file docs/team/conventions.md` | artifact | sound |
| teach | `check_in_files '\*\*Rule:\*\*'` (ledger) | artifact | sound — the ledger contract is on-disk |
| teach | `check_in_files '\*\*Why:\*\*'` (ledger) | artifact | sound |
| teach | `check_in_files '\*\*Scope:\*\*'` (ledger) | artifact | sound |
| teach | `check_in_files '\*\*Source:\*\* user'` (ledger) | artifact | sound |
| teach | `check_in_files 'ulid'` (ledger) | artifact | sound — the taught content, not a wording choice |

Tally: 31 checks — 22 artifact, 5 fixture-noun, 2 format-contract, 2 hardened-prose (formerly free-prose; 0 free-prose remain). The rubric judge
(`EVAL_JUDGE=1`) stays on as the independent dissenter for the transcript-based
checks; it has been right both times it disagreed with the key.

## Rules this audit sets

1. **New checks prefer artifact evidence.** A transcript grep is acceptable
   only as fixture-noun or format-contract — never for an ordinary English
   word — except as **hardened-prose** in a report-only case with no artifact
   to inspect, synonym-widened and ratchet-pinned. Guardrail ratchets pin the
   two hardened vocabularies.
2. **A conversion documents itself here, in the same commit.** Old form, new
   form, and why the intent is unchanged.
3. **The synonym lists are additive-only** without a documented reason — a
   narrowed vocabulary is how the disease returns.
