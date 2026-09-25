---
description: Refactor a fat controller method (or Livewire action) into a single-responsibility Action class, with tests.
argument-hint: <Controller@method>  or  <LivewireComponent::action> [--adaptive]
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
---

# Refactor to Action — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

<!-- BEGIN GENERATED ORCHESTRATION CONTRACT -->
> **Interface:** Call `python3 scripts/guild-kernel/guild.py` for this delivery — `plan` before any Agent, `ready` to fetch the bounded dependency-ready wave, `claim --stage <id>` before each Agent, then dispatch every claimed lane concurrently, and `report` on `docs/delivery/<name>/stages/<agent>.md` after each return, `board` to print state plus the per-stage `criteria[id:✓|~|·]` evidence matrix. `plan` must pass a nonempty `--done-when` and every typed `--stage-json` must carry success criteria, parallel one-to-one stable `criterion_ids`, `benchmark_criteria` (empty unless an outcome claim requires a benchmark), `owned_paths`, and `approval_categories` (an empty array only when no profile category applies); use `--max-parallel` to set the WIP ceiling. Every stage snapshots the shared default budget unless `budget` overrides are supplied; `ready` returns the effective budget and criterion rows, so include both in the specialist brief. On Claude Code, the budget hook meters synchronous Agent calls automatically; on another runtime that returns all five totals, only the main thread calls `budget record` before `report`. A claimed lane cannot report without completion telemetry. Before `report`, call `criterion list`; every unwaived criterion needs a passing record. If evidence is genuinely impossible, stop for a numbered human checkpoint; only the main thread may call `criterion waive --reason <why>`, and a waiver is an auditable exception. `budget_exceeded` is terminal pending human direction. After `plan`, call `approval list`; for every pending category ask the human with numbered options, and only the main thread may call `approval grant`. Unapproved lanes stay paused and are excluded from `ready`. If a sprint is running, attach it (`--sprint <id>` or the kernel attaches the single running sprint). Never invent a checkmark; never compose `docs/delivery/<name>/close.md` (the kernel renders that view). Never compose `docs/sprints/<id>/sprint.md` (the kernel renders that view). `plan` prints `RULES:` only for user-approved learned rules; brief every `RULES:` line. Never compose `docs/team/lessons.md` (the kernel renders that view). When the command includes `--issue <n>`, `plan` passes `--issue <n>`. Call `pr --number <n>` once a pull request exists; the kernel re-fetches it. Call `ingest` only for a failing check or a review comment the kernel confirms. Never compose issue or pr fields. A workplace delivery stays running until the recorded PR state is open. Never merge. Writers Write the six fields `STATUS / DID / VERIFIED / NOT-CHECKED / FLAGS / NEXT` (≤12 lines) as their last act; never write a writer's stage file for them. Read-only specialists — persist their stage file from the report you already file, then `report`. `VERIFIED:` lines are JSON verification records (`{"criterion":"tests-pass","runner":"artisan-test","args":["--filter=TagTest"]}`); each line names a declared criterion ID, every criterion must be covered, and the kernel accepts only registered runners and executes argv without a shell; prose and legacy command strings are rejected. `NOT-CHECKED:` that names an unwaived stage success criterion is a reject; specialists may never waive their own criteria. Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph. **Your own final answer closes the same way** — a `VERIFIED` line carrying the commands you actually ran, then `NOT-CHECKED` naming what you did not verify (≤3 lines, or "none"). **Once ≥2 specialists have reported, this delivery harvests too** — persist `docs/team/stack.md` (verified project facts + where-things-live, `delivery-templates` skill shape) from what they've reported, and maintain `docs/delivery/<name>/log.md` (phase by phase, agent by agent, artifact by artifact). Both exist before your final answer, not after. A single-specialist ask has nothing to harvest — skip both. **You do not build and you do not patch** — Write/Edit only under `docs/**`; never edit a specialist's files to "just fix it" (re-brief or escalate). When `--adaptive` is in the command arguments, a writer may Write a no-re-ask packet at `docs/delivery/<name>/packets/<from>-to-<peer>.md` naming a registered peer, or the coordinator Writes one fallback packet FROM that writer TO the next queued specialist else tech-lead — one fallback packet per run; spawn `peer-router` when a packet exists; after it returns, persist `docs/delivery/<name>/stages/peer-router.md` and `report` it; print a handoff line `handoff: <from> → <to>` on the board; then Agent that peer with the packet as the brief; hops count against the spawn cap. Without `--adaptive`, ignore `packets/` and never spawn `peer-router`.

> **Durable checkpoints:** After `plan` and at every start or resume, call `checkpoint list`. Before asking for a human decision, only the main thread calls `checkpoint open` with the exact question, risk, 2–5 typed options, and recommended option; then present that stored prompt. After the human answers, only the main thread calls `checkpoint resolve` with the selected option and any modification as `--note`. A pending checkpoint pauses only its stage: continue dispatching independent `ready` lanes. On resume, present the pending record exactly as stored; never reconstruct it. A resolved checkpoint is not asked again—re-brief a continued lane with its durable answer.

> **Loop guard:** The runtime hashes every tool name plus input for a claimed specialist. If the exact same 1–4-step cycle reaches three repetitions, it blocks the repeated call, fails that lane, and stops the delivery without storing raw input. On `unproductive ... tool cycle`, call `loop list`, print `board`, and stop dispatch. Never retry the same sequence; a new attempt requires an explicitly changed brief or plan.

> **Retry transitions:** At every start or resume, call `retry list` and `transition list`. A queued lane cannot `report`; only a freshly claimed `running` lane with completion telemetry may report. For an incomplete or failed specialist return, only the main thread calls `retry request --stage <id> --source stage-return|verification --reason <why> --event-id <stable-id>` after telemetry is recorded. The first distinct request invalidates stale stage evidence and requeues the same owner; the next `ready` row carries attempt 2 plus the retry reason, and a normal atomic `claim` starts it. A duplicate event ID is a no-op. A second distinct failure marks the stage `failed` and the delivery `stopped`; print the board and ask the human instead of dispatching again. Confirmed CI and review feedback ingested by the kernel uses this same lifecycle.

> **Feedback routing:** Every typed stage declares globally unique `feedback_checks` for the CI jobs it owns (empty only when it owns no check). At every start or resume and after PR polling, call `feedback list`. `ingest` derives CI ownership from the exact check name and review ownership from the longest matching `owned_paths`; `--stage` is only an assertion and never selects the owner. Unmatched feedback becomes durable `route_required` and blocks dispatch. Only the main thread may call `feedback assign --event-id <id> --stage <id>` after verifying ownership. All open items for one lane attach to one repair attempt, and a passing `report` resolves them. Duplicate external events are no-ops; new feedback after the allowed reopen stops the delivery. Never route by last writer or arbitrary availability.

> **Interruption recovery:** At every start or resume, call `recovery list` before `ready`. Its `active_claims` are live only when the current runtime still owns them; after a confirmed user interrupt, process exit, runtime error, or host restart, only the main thread calls `recovery interrupt --stage <id> --source <source> --reason <why> --event-id <stable-id>`. The kernel freezes the claim at its last observed activity, preserves known cumulative seconds and tool calls, and records unavailable completion metrics instead of inventing them. Resolve the durable event with `recovery resolve --event-id <id> --action continue|stop`: `continue` requeues for a fresh atomic claim without consuming the retry, while `stop` fails the stage and stops delivery. Duplicate events and resolutions are idempotent. Never reclaim by editing state, reusing the old report, or fabricating telemetry.

> **Delivery observability:** Every persisted kernel mutation emits one typed, monotonic, hash-chained event with delivery/stage correlation and aggregate usage; raw prompts, tool inputs, report bodies, and secret values never enter that ledger. `kernel.json` remains authoritative while `events.jsonl` and `observability.md` are deterministic views. At every start or resume and again before the final answer, call `observe verify`; `unhealthy` stops dispatch and closure until the mismatch is resolved. `unavailable` is acceptable only for a legacy delivery before its next persisted mutation. Use `observe list` to inspect the typed trail—never treat console traces or generated views as authority.

> **Context packets:** After each atomic `claim` and before dispatch, build the claimed stage's bounded brief with `context build --stage <id> [--spec <project-relative.json>]`, then require `context verify --stage <id>` to pass and give that one stage-specific packet to the named specialist. The packet keeps system, user, project, runtime, and agent authority separate; objective, approvals, owned paths, budgets, criteria, current state, and the output contract are mandatory and never trimmed. Optional repository excerpts are admitted only as hash-bound, untrusted data and are dropped whole from lowest priority when the budget is full; required excerpts that do not fit stop dispatch. A changed source, spec, kernel state, secret-shaped value, path escape, symlink, or packet hash stops dispatch until the coordinator rebuilds from reviewed inputs. On resume, rebuild after recovery resolution so completed dependencies, retry/recovery reasons, open feedback, and the next action are current. Never paste broad repository history, raw tool payloads, environment files, dependencies, or another specialist's unrestricted diff into a brief.

> **Outcome benchmarks:** Any criterion that claims fewer queries or lower latency while preserving behavior must appear in the stage's `benchmark_criteria`. Collect read-only baseline and candidate captures against the same scenario, dataset fingerprint, and runtime fingerprint, with warmups plus at least seven measured runs; never persist raw SQL, responses, rows, events, jobs, or secrets. Run `python3 scripts/outcome-benchmark.py compare --root . --baseline <baseline.json> --candidate <candidate.json> --output <docs/delivery/.../receipt.json>`, then bind that receipt to the criterion with runner `outcome-benchmark`. A failed, missing, tampered, behavior-changing, or source-drifted receipt leaves the criterion unverified. Never substitute one manual timing, an average, or an intuition for the receipt; the operator still owns dataset realism and capture-instrumentation quality.
<!-- END GENERATED ORCHESTRATION CONTRACT -->

Extract the logic in `{{args}}` into a dedicated Action class, leaving the caller as thin glue.

## What you do

1. **Locate the source.**
   - For `Controller@method`: find `app/Http/Controllers/<Controller>.php` and the `<method>` body
   - For `LivewireComponent::action`: find the matching public method on the component
   - Read the method end to end before proposing anything

2. **Decide the Action's name and signature.** The verb-noun pattern is canonical:
   - `CreateOrderAction`, `PublishPostAction`, `RefundChargeAction`
   - Place under `app/Actions/<Domain>/<Name>Action.php` — match the project's directory convention if different
   - The Action exposes a single entry point — `execute(...)` or `__invoke(...)`. Pick whichever the project uses; default to `execute`.
   - Parameters are typed primitives or DTOs/Eloquent models — never the `Request`. Validation stays in the Form Request.

3. **Delegate to `backend-developer`** to:
   - Generate the Action class with `declare(strict_types=1);` and explicit return type
   - Move the logic, preserving behaviour
   - Wrap multi-write paths in `DB::transaction(...)` if not already
   - Move side-effects (mail, events, jobs) into the Action; the controller no longer dispatches them
   - Update the original method to:
     ```php
     public function store(StoreXRequest $request, CreateXAction $action): RedirectResponse
     {
         $x = $action->execute($request->validated(), $request->user());
         return redirect()->route('x.show', $x);
     }
     ```
   - Update any other caller currently inlining the same logic

4. **Delegate to `qa-engineer`** to:
   - Add a unit test for the Action (no HTTP, real DB or transactional)
   - Keep the existing feature test green
   - Add an edge-case test for at least one failure path the original method handled (or didn't handle correctly)

5. **Delegate to `tech-lead`** for review focused on:
   - The Action is genuinely single-responsibility (if `execute()` has internal branches that change semantics, it's actually two Actions)
   - No leaked controller concerns (request parsing, redirects) inside the Action
   - Transactional integrity preserved
   - Tests cover what the refactor changed

## Guardrails

- Don't refactor if the original method is already thin (< ~15 lines of meaningful logic). Say so and stop.
- Don't introduce Actions in a project that doesn't already use them without a heads-up — propose the pattern and wait for confirmation.

## Output

- New Action class path
- All call sites updated (with file:line)
- Test results before and after
- Diff summary
