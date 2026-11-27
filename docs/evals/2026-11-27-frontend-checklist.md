# Frontend checklist eval on a Laravel catalog

The committed [per-trial scores](2026-11-27-checklist-trials.jsonl) and
[fixture evidence](2026-11-27-checklist-evidence.json) cover the original
comparison and both list-rendering follow-ups.

- **Date** November 27, 2026
- **Fixture** Laravel 13.43.0, Blade, plain JavaScript and CSS, and a Lighthouse CI configuration
- **Comparison** Guild profiles at `31dfca0` versus the working-tree checklist updates

## Method

Claude Code 2.1.326 ran Bella (`claude-sonnet-5-5`) and Omar
(`claude-opus-5-5`) as named custom agents, with three runs per profile
version. Each pair used the same read-only audit prompt, model, low effort,
fixture, and tool access (Read, Glob, Grep). The before/after order was
reversed in round two. Sessions ran serially from a disposable directory
and had no access to the scoring key through the fixture. The test
measures specialist audit coverage. It does not run Guild scheduling or
test the agents' ability to implement fixes.

The [scoring key](../../tests/eval/fixtures/frontend-checklist/answer-key.md)
covers 13 issues and three clean controls. Each point requires a concrete
location, a correct mechanism, and a fix that addresses it. Results were
scored against this key by reading the final reports. Findings can score
wherever they appear in a report. A targeted check appearing under
“needs measurement” can still score when its source evidence and fix are given.

All ten local HTTP probes returned 200. They captured the two greeting
variants with shared-cache headers, the 90,469-byte items response, the
hashed JavaScript's revalidation policy, and the 1,143,919-byte hero image.
The fixture provides source and HTTP captures. Quantifying production
latency, field Core Web Vitals, or CDN cache behavior would require
separate measurements.

## Original checklist results

| Agent | Profile | Round scores (of 13) | Total | Median wall time | Median estimated cost |
| --- | --- | --- | ---: | ---: | ---: |
| Bella (frontend) | Before | 13, 11, 12 | 36/39 | 27.1 s | $0.061 |
| Bella (frontend) | After | 12, 12, 12 | 36/39 | 29.2 s | $0.067 |
| Omar (performance) | Before | 12, 12, 12 | 36/39 | 40.5 s | $0.143 |
| Omar (performance) | After | 12, 12, 12 | 36/39 | 38.8 s | $0.131 |

Total estimated cost $1.33.

| Planted issue | Bella before | Bella after | Omar before | Omar after |
| --- | ---: | ---: | ---: | ---: |
| First-view content missing from initial HTML | 3/3 | 3/3 | 3/3 | 3/3 |
| Runtime CSS import chain | 3/3 | 3/3 | 3/3 | 3/3 |
| Oversized hero with no responsive sources | 3/3 | 3/3 | 3/3 | 3/3 |
| Lazy loading on the likely LCP hero | 3/3 | 3/3 | 3/3 | 3/3 |
| Optional video configured to preload automatically | 3/3 | 3/3 | 3/3 | 3/3 |
| Blocking font display | 3/3 | 3/3 | 3/3 | 3/3 |
| Sort handler alternates layout reads and writes | 3/3 | 3/3 | 3/3 | 3/3 |
| All 180 rows inserted together | 1/3 | 0/3 | 0/3 | 0/3 |
| Fingerprint-named JS must revalidate | 3/3 | 3/3 | 3/3 | 3/3 |
| Viewer-specific response marked shareable | 3/3 | 3/3 | 3/3 | 3/3 |
| Unused history field in the listing payload | 3/3 | 3/3 | 3/3 | 3/3 |
| Independent API fetches run in sequence | 3/3 | 3/3 | 3/3 | 3/3 |
| Missing enforced Lighthouse budget for the catalog | 2/3 | 3/3 | 3/3 | 3/3 |

Costs are Claude Code's list-price estimates. Wall time measures the
Claude Code subprocess, including CLI startup. The sample comprises one
fixture and three runs per profile version. Prompt-cache usage varied
across runs.

Both updated agents scored 12 of 13 in all three runs. Both matched
their previous profile's aggregate of 36 actionable findings out of 39.
Bella gave an actionable Lighthouse fix in all three updated runs. Her
previous profile spotted the misconfigured target in all three and
omitted the change in one. All three updated Bella runs also tied the
optional hero preload to waterfall evidence.

The main coverage gap was list rendering. Every report found
`listing_history` overfetching and the repeated layout work in the sort
handler. Only one baseline Bella report explicitly linked the one-shot
insertion of all 180 list items to its own fix. Pagination mentioned
only as an API payload remedy did not earn credit for DOM size.

Among the 36 control opportunities, one updated Bella report
misread the secondary image's responsive choices. The 320w candidate
already serves a 160px slot at DPR 2. Several reports also inferred
the JPEG's intrinsic dimensions from its HTML attributes, and some
described the full MP4 as a page-load download based on a direct file
probe. FFprobe identified the JPEG as 1920×1080. The HTTP capture
establishes the video file's size, and the Blade attribute establishes
the preload policy. A browser waterfall is needed to measure how much
video loads during a visit.

The runner and fixture passed syntax checks. The repository checks
passed 552 guardrails and 97 evaluation unit tests.

## Reproduce

Install the fixture's Composer dependencies and use a signed-in Claude
Code CLI with the two named models available. The runner requires PHP,
FFmpeg, and Python 3.12 or later. Supply an unused output directory.

```sh
composer --working-dir=tests/fixture-app install
python3 tests/eval/run-frontend-checklist.py \
  --baseline 31dfca0 \
  --vendor tests/fixture-app/vendor \
  --output tests/eval/results/frontend-checklist-repeat
```

Raw Claude Code reports, profile digests, the prompt, and local HTTP
captures from this run are in
`tests/eval/results/20261127-frontend-checklist-live/`.

## Follow-up on initial list rendering

Both profiles now trace the collection into the template loop or DOM
insertion. The audit calls for a finding tied to the row count and render
site, with a rendering fix independent of the API field selection.

The retest used 12 fresh Claude Code sessions with the same fixture,
prompt, scoring key, models, tool access, and run order as above. Its
baseline was the exact checklist profiles that previously scored 0/3
on the DOM issue. The profile digests matched the previous run's
candidate digests. The HTTP captures matched apart from the generated
asset modification dates.

The existing rubric credits identifying the mass DOM insertion and
proposing a fix for it. A combined item can score if it distinguishes
the rendering and payload mechanisms and fixes. The follow-up also
records whether the agent gave each issue its own report entry.

### First pass

| Agent | Profile | DOM catch | Standalone DOM finding | Checklist scores | Median wall time | Median estimated cost |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Bella | Before | 0/3 | 0/3 | 12, 12, 11 | 27.7 s | $0.062 |
| Bella | After | 2/3 | 1/3 | 13, 13, 12 | 28.5 s | $0.067 |
| Omar | Before | 0/3 | 0/3 | 12, 12, 12 | 38.9 s | $0.128 |
| Omar | After | 3/3 | 3/3 | 13, 13, 13 | 36.8 s | $0.132 |

Total estimated cost $1.20.

Omar gave the DOM mount its own entry in all three updated runs. Bella
identified the full mount in all three runs. Her first run grouped both
issues while proposing separate fixes, her second gave the mount its own
entry and put pagination in the adjacent payload entry, and her third
listed the mount as an observation and explicitly declined a rendering
fix. That third run did not earn F8 credit.

Bella's profile was then tightened to name separate **Initial list
rendering** and **API payload** entries. The rendering entry must
propose a bound on mounted rows. Source evidence establishes the mount,
and the browser trace establishes its timing impact. Omar's profile
stayed at the revision used in the paired retest.

### Frontend confirmation

| Agent | Profile | DOM catch | Standalone DOM finding | Checklist scores | Median wall time | Median estimated cost |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Bella | Final | 3/3 | 2/3 | 13, 13, 13 | 30.9 s | $0.067 |

Three confirmation runs $0.22, and all 15 follow-up runs $1.41 at Claude Code list-price estimates.

The three confirmation runs used the same fixture, prompt, and
frontend model. They ran the final Bella profile and reused the paired
run's baseline results for comparison. Every report cited the
`replaceChildren` call in `catalog.js:13–18`, identified the 180
`<li>` elements, and proposed rendering one page first. Two reports
gave the rendering issue its own numbered entry. The other used
distinct **API payload** and **Initial list rendering** subentries
within one numbered item. The rendering time was unmeasured in all
three. Omar's unchanged profile already had three standalone
findings in three runs.

Fresh verification passed all 552 guardrails, 97 evaluation unit
tests, and the 26 agent and skill body budgets.

### Reproduce the follow-up

The previous profiles are saved in the original run directory. With the
current profiles in the checkout, run the same comparison with that
snapshot as baseline.

```sh
python3 tests/eval/run-frontend-checklist.py \
  --baseline-profiles tests/eval/results/20261127-frontend-checklist-live/checklist-profiles \
  --vendor tests/fixture-app/vendor \
  --output tests/eval/results/initial-dom-repeat
```

The raw reports, profile digests, and individual scores from the
paired run are in `tests/eval/results/20261127-initial-dom-live/`. The
three frontend confirmation results are in
`tests/eval/results/20261127-initial-dom-confirm/`.
