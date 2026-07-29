# Design — smarter, faster, more accurate agents (v1.24.0)

**Goal:** raise agent accuracy and cut wall-clock, using only changes traceable
to a measured failure. Every item below cites
[eval run 4](../../evals/2026-07-28-run-4.md).

**Non-goal:** discretionary capability work — model-tier changes, new skills,
new agents. Explicitly out of scope for this tranche; nothing in run 4 points
at them.

## Fix 1 — Builders can run their own gates

*Evidence: finding 1. qa-engineer "wrote suite in worktree (couldn't run — no
vendor/)"; `composer install` appears as a stage in two boards.*

`isolation: worktree` is removed from all eight writers: `backend-developer`,
`frontend-developer`, `database-developer`, `qa-engineer`, `mobile-developer`,
`package-developer`, `devops-engineer`, `ui-ux-designer`.

`git worktree add` checks out tracked files only, so a worktree never contains
`vendor/`, `node_modules/` or `.env`. Every verification gate an agent body
promises — `pint --dirty`, `phpstan analyse`, `artisan test` — is unrunnable
there. Under Sail it fails harder: the container mounts the main project
directory, so an agent in a worktree tests the wrong tree or collides on
container names and ports. `isolation:` is static frontmatter and cannot be made
conditional, so the choice per agent is binary, and verification wins.

`ui-ux-designer` executes nothing and would still satisfy the rewritten rule,
but it loses isolation too: its `docs/design/` artifacts exist to be read by
`frontend-developer`, and whether a *changed* worktree merges back into the
user's tree is unverified. One rule beats an exception resting on an unverified
assumption.

**Replacing the lost guarantee.** Isolation bought parallel-write safety. Two
mechanisms already in the pack take over, now stated explicitly:

- Each writer gains one principle: the brief names the paths you own; a change
  outside that scope goes in FLAGS rather than the diff.
- `delivery-coordinator` already caps parallel lanes at 2–3 and sequences work
  along the dependency chain. Its three worktree-dependent paragraphs (the
  "Worktree writers" note, the Little's-Law line, and the branch-merge
  integration step) are rewritten for a shared tree: parallel lanes must own
  disjoint paths, and integration is verifying one tree rather than merging
  branches.

Documentation carrying the old rule is corrected in the same commit:
`docs/authoring-agents.md` (frontmatter example, the `isolation: worktree`
section, the authoring checklist), `CONTRIBUTING.md` (frontmatter table + rules
list), and `README.md` (seven tree annotations + the "Writers run in isolated
worktrees" paragraph).

## Fix 2 — Calibration reaches the human

*Evidence: finding 2. The `NOT-CHECKED` check failed because the contract binds
specialist returns, which are internal.*

The `Interface` block shared byte-identically across nine commands gains a
clause binding the run's **own final answer**: it closes with `VERIFIED` and
`NOT-CHECKED` for the whole run. `delivery-coordinator`'s integration step gains
the matching requirement.

This changes what is *guaranteed*, not what agents know — run 4 shows they
already report gaps honestly in prose. Labelling makes it observable to the
human and to the eval.

## Fix 3 — Never pin a security hole as expected behavior

*Evidence: finding 3. Dina characterized an unguarded `update` route as
"current behavior" instead of probing 403.*

`qa-engineer.md`'s authorization always-check is rewritten to cover the
unprotected case: when an endpoint has no authorization, the denied case still
asserts the secure outcome (403), is marked todo/incomplete with its reason, and
is named in FLAGS. A matching anti-pattern entry lands in the refuse-to-ship
list.

The rule replaces a judgment call with a deterministic instruction, which is why
this is a rule and not a model-tier change.

## Fix 4 — Test what the app can reach

*Evidence: finding 4. qa wrote pairs for all seven Policy methods; three have
no routes, by its own admission. 634s / 501s stages.*

The existing scope rule gains a checkable criterion: cover abilities with a real
call site; a Policy method no route, command, or component invokes gets one line
in NEXT, not a test pair. Fix 1 independently removes `composer install` from
qa's critical path.

**This tranche does not claim a speed improvement.** Fixes 1 and 4 are reasoned
levers. Only a sequential eval run 5 can confirm them, and `baseline.json`
ceilings are reseeded after that run, not before — the sole exception being a
new `hygiene` ceiling (86s + headroom → 200s), which had none.

## Ratchets

Two static checks join `tests/guardrails.test.sh`, so neither regression can
return silently:

1. No agent body declares `isolation: worktree`.
2. The `Interface` block is byte-identical across all nine pipeline commands and
   contains the final-answer clause.

The eval answer key is deliberately unchanged: fixes 2 and 3 make both failing
`tests` checks legitimately passable, which is the cleanest possible
verification of this tranche.

## Release

Standard checklist: `VERSION` + four manifests to 1.24.0, Gemini and Codex
mirrors regenerated via `scripts/build-*.py` (never hand-edited),
`tests/guardrails.test.sh` + `scripts/validate-frontmatter.py` +
`scripts/check_body_budget.py` (reseed if net lines move) +
`scripts/check_inventory_sync.py`, CHANGELOG in Keep-a-Changelog voice, commit
to `main`.

Inventory counts do not move — no agents, commands, skills, or hooks are added —
so `check_inventory_sync.py`'s CLAIMS list is untouched.
