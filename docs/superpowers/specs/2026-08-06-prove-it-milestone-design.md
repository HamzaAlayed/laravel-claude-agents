# "Prove it" milestone — trust, capability, adoption (v1.39 → v1.42)

**Renumbered 2026-08-07:** what this doc calls "Release 1.41.0 — Adoption"
below actually ships as **v1.42.0**. v1.41.0 went to an unplanned fix run 7
exposed — moving team-memory harvest into the shared Interface block
(`docs/superpowers/specs/2026-08-07-harvest-interface-fix-design.md`) — not
described anywhere in this document, because it wasn't part of the original
milestone. Adoption's own content is unchanged; only its version number
moved.

Design approved 2026-08-06. Sequenced from the
[2026-08-05 project-state review](../../requirements/2026-08-05-project-state-review.md),
which is the requirements document for this milestone: its six gaps are the
backlog, and this spec decides which land, in what order, and why.

## Why this shape

The pack's behaviour is mature — the
[literature audit](../../research/2026-07-29-agent-literature-audit.md) found it
independently converged on published practice, and its four gaps have all since
shipped. What is left is not behaviour. Three things keep the pack from being
*provable*:

1. Its flagship team-memory feature (`docs/team/`, `/teach`, the
   end-of-delivery harvest) has **zero example instances anywhere** — the README
   claims behaviour no artifact demonstrates (review, gap 4).
2. Its eval checks carry a known fragility pattern — exact-word greps against
   nondeterministic prose. v1.37.0 fixed one instance the hard way, after the
   rubric judge correctly failed the key; nobody has audited the other checks
   for the same disease (review, gap 5).
3. Nothing outward-facing shows any of it. The docs corpus is entirely
   inward — there is no quickstart with evidence, and as of v1.38.0 the console
   is actually worth showing.

The order is trust → capability → adoption because of one dependency: the
dog-fooding work in the middle release changes coordinator-adjacent behaviour,
which is exactly what the opt-in `feature` case exists to catch and exactly
what run 7 will judge — so the instrument gets hardened *before* the runs whose
verdicts we intend to publish. Adoption goes last so it demos the finished
thing.

One decision this spec makes that the review left open: **"run 7" is the teach
delivery** (§1.40 below). The review's gap 1 showed the "run-7 checklist" was a
closed retrospective wearing a forward-looking name, with no artifact defining
what a run 7 would test. It now has a hypothesis.

## Release 1.39.0 — Trust. Instrument only; no agent body changes.

**Check-fragility audit.** Inventory every check `run-evals.sh` dispatches
across the six cases (five default + opt-in `feature`). Classify each as
*artifact-based* (inspects files/code the run produced) or *prose-grep*
(matches words in the transcript — the `check_log 'update'` disease). Convert
the prose-greps to artifact checks in the `check_update_guarded` style:
inspect the code for the behaviour the check means, accept the idiomatic
placements, reject vacuous satisfactions (a guard that authorizes everything is
not a guard). Every conversion is documented in the eval docs with its old and
new form, and gets a negative control where one is cheap (the `feature` case's
inline-stub pattern). The intent of each check is frozen; only the evidence
source moves. This is the same change v1.37.0 made to one check, applied as an
audit instead of waiting for the judge to catch the next one in production.

**Metric-of-record.** One documented tie-break rule, written into
`tests/eval/baseline.json`'s `_policy` notes and the README's eval section:
**`max_usd` is the cost metric of record.** Token totals are >99% cache reads,
so they measure conversation shape, not spend; wall-clock measures the
experience, not the bill (run 6 finding: security-engineer was 53% of wall
clock and a sixth of the bill); `policy` and `action` remain bimodal-excepted
(check the agent list for delegation before calling a regression). Seconds and
tokens stay as ceilings — they catch different regressions — but when ceilings
disagree, dollars win.

**Feature-case trigger, made deterministic.** The review's gap: "run it when
coordinator behaviour changes" has no named judge and will silently never
fire. Fix: a guardrails test records a content hash of
`agents/delivery-coordinator.md` plus the nine commands' shared Interface
block, seeded at the last billed `feature` run. If the hash drifts and
`tests/eval/baseline.json` carries neither a newer feature-run record nor an
explicit dated waiver, the build fails with instructions
(`./tests/eval/run-evals.sh feature`). CI cannot run billed evals; it can
refuse to let coordinator changes ship unmeasured without a human saying so in
writing. Seeding note: the v1.36.0 Interface-block edit (stage budget) landed
the same evening as the feature case's billed run, so the rule is seeded at
**current** content with that drift recorded as the first dated waiver — 1.40
re-runs the case anyway, which retires it.

**Run-7 scope stub.** `docs/evals/` gains the hypothesis document, so the next
sweep finally names a question. Hypothesis: *teach → override → harvest works
end to end on a real delivery* — a taught rule visibly changes what the agents
build, and the coordinator's harvest writes the team ledger without being
asked. The stub also states what run 7 deliberately does not re-test (run 6's
closed findings).

## Release 1.40.0 — Capability. The billed run, and the missing artifact.

**Run 7 is the teach delivery.** Scripted against a throwaway copy of
`tests/fixture-app`, using the harness's existing copy-install-run pattern.
Nothing is committed into the fixture — run 5's finding 1 (committed fixture
telemetry polluting later feeds) is the standing constraint. Shape:

1. Seed the workdir's `docs/team/conventions.md` via `/teach` with 2–3 rules
   chosen so a default is visibly overridden — e.g. "money is integer cents,
   never floats" and "ULIDs, not auto-increment ids". Rules must be ones the
   agents would *not* pick by default, or the override proves nothing.
2. Run one delivery (`/make-feature`-shaped, sized nearer `action` than
   `feature`) whose natural implementation crosses both rules.
3. Assert, artifact-based from day one: the taught rules are reflected in the
   produced migration/model/code; `docs/team/` grew from the coordinator's
   end-of-delivery harvest (decisions and/or conventions appended, not merely
   preserved); the delivery log exists and names the stages. `EVAL_JUDGE=1`
   rides along as it has since run 5.
4. Ceilings for the case are **seeded from the first accepted run**, not
   guessed — the `feature`-case precedent.

**The example instance.** The run's `docs/team/` output and delivery log are
captured out-of-tree and committed under `docs/examples/team-memory/`, linked
from the README paragraph that claims the harvest behaviour. This is the
artifact the review said does not exist. It is a *captured instance*, clearly
dated and labelled with the pack version that produced it — not a living
document.

**Fixes the run exposes land here.** If the harvest half-works (likely — it
has never been exercised), the body-level fixes ship in this release,
re-measured by the same case. The 1.39 hash rule decides whether the `feature`
case must also run; its answer is recorded either way.

## Release 1.41.0 — Adoption. Show the receipts.

- **Quickstart with evidence.** README restructure: a five-minute quickstart at
  the top (install → first command → what you see), with real screenshots of
  the console — the actor board mid-run — and a GIF of a live run, recordable
  from the pose harness or captured during run 7. The current README explains
  the design; the new top shows the product.
- **`docs/README.md` index.** One page mapping the corpus: what lives where,
  what is a spec vs a plan vs an eval record, what is closed vs open. The
  project-state review had to reverse-engineer exactly this; the index makes
  the next review (human or agent) start warm.
- **Onboarding guide** for adopting teams: install, first delivery, teaching
  the first rule, reading the eval scorecard. Where it duplicates the
  quickstart, it links rather than repeats.
- **Optional rider:** the six CAN-RIDE console minors from the
  [motion follow-ups](../../plans/2026-08-04-console-motion-followups.md) may
  ride if the screenshot work already has the console open; none blocks the
  release.

## Verification

The jcode-arc rule: every release ships with its own verification.

- **1.39** — converted checks pass against run 6's kept artifacts where
  available; each conversion's negative control fails its stub; the hash rule
  has a test proving it fires on a coordinator edit and stays quiet otherwise;
  full guardrails + unit suites stay green.
- **1.40** — run 7 itself is the verification. Composition, so the scorecard
  stays comparable: the standard five-case sweep (~$12.50, unchanged
  denominator) **plus** the new teach case (single delivery, ~$5–8, `action`'s
  shape) **plus** the `feature` case if the 1.39 hash rule demands it (~$7).
  Worst case ≈ $27, inside the milestone budget; `EVAL_TIMEOUT` bounds the
  downside. The example artifact is checked by CI for existence and link
  integrity once committed.
- **1.41** — README links and image paths checked in CI where cheap; the
  quickstart walked once by hand before release.

## Risks

- **The teach-delivery's cost is unmeasured.** Bounded by `EVAL_TIMEOUT`;
  ceilings seeded after, never before. Budgeted ~$25–30 across the milestone.
- **A check conversion could silently weaken the key.** Mitigated by
  per-conversion documentation and negative controls; the rubric judge stays on
  as the independent dissenter.
- **The harvest may genuinely not work.** That is not a risk to the milestone;
  it is the milestone. Finding it on the fixture costs a re-run; a user finding
  it first costs trust.
- **Run comparability.** Run 7 runs on hardened checks; its scorecard says so,
  and the per-conversion docs are the bridge back to runs 1–6. The five-case
  denominator is unchanged.

## What this milestone does not do

- **No model-tier changes, no body slimming, no qa-engineer tuning** — the
  v1.38 accuracy-and-cost spec's non-goals stand.
- **No new agents, commands, or skills.** The pack's surface is stable; this
  milestone proves what exists.
- **No docs site, demo video, or marketplace push.** Expansive-adoption scope
  was explicitly declined; if 1.41's quickstart creates pull, that is the next
  conversation.
- **No separate demo repository.** The fixture delivery is the demo; a second
  repo is a recurring cost forever.
- **No re-litigating the audit's rejected patterns** (debate, voting,
  decentralized handoff, frameworks) — the refusals in the
  [literature audit](../../research/2026-07-29-agent-literature-audit.md) stand.
