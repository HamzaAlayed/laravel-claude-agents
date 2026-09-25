# Which Laravel Guild guarantees are actually enforced?

Last verified 2026-09-25 against pack v9.0.0.

This map separates mechanically enforced controls from pre-tool hooks, release-gated evidence, operator decisions, and prompt guidance across the Laravel Guild engineering loop.

This page is generated from
[`config/enforcement-map.json`](../config/enforcement-map.json). Edit the
manifest, then run `python3 scripts/check-enforcement-map.py --write`.
A prompt instruction is never presented as a hard control on its own.

## Enforcement levels

| Level | Meaning |
| --- | --- |
| `runtime` | A state machine or command rejects the operation before accepting the transition. |
| `pre-tool-hook` | An installed host hook rejects a covered tool call before the tool executes. |
| `ci` | A named job required by immutable release publication tests or validates the control. |
| `operator` | A human decision or external observation is authoritative and must be recorded; software validates the record but cannot make the decision. |
| `prompt` | Generated agent instructions describe the procedure; this level guides behavior but is not a security boundary by itself. |

## Control summary

| Control | Enforcement | Failure mode |
| --- | --- | --- |
| [`adversarial-gate`](#adversarial-gate) — Versioned attack matrix | `ci` | Fail hosted CI and prevent immutable release publication for the exact commit. |
| [`agent-policy-profiles`](#agent-policy-profiles) — Shared and role-specific harness policy | `runtime`, `pre-tool-hook`, `ci`, `prompt` | Reject an unknown, incomplete, or contradictory profile before release or planned execution. |
| [`bounded-retries`](#bounded-retries) — One auditable retry | `runtime`, `ci`, `operator`, `prompt` | Requeue once with stale evidence invalidated, then fail the stage and stop delivery on exhaustion. |
| [`criterion-evidence`](#criterion-evidence) — Criterion-linked verification | `runtime`, `ci`, `operator`, `prompt` | Reject the report and leave the stage nonterminal when evidence coverage is missing or untrusted. |
| [`delivery-observability`](#delivery-observability) — Correlated delivery event integrity | `runtime`, `ci`, `operator`, `prompt` | Report unhealthy, refuse authoritative-chain growth, and block dispatch or closure until integrity is restored. |
| [`durable-checkpoints`](#durable-checkpoints) — Typed human checkpoints | `runtime`, `ci`, `operator`, `prompt` | Keep the affected stage paused and exclude it from ready work until a valid resolution exists. |
| [`feedback-routing`](#feedback-routing) — Ownership-derived PR and CI routing | `runtime`, `ci`, `operator`, `prompt` | Persist route_required and block new dispatch, or reject a caller-asserted wrong owner without recording it. |
| [`human-approvals`](#human-approvals) — Durable protected-action approval | `runtime`, `pre-tool-hook`, `ci`, `operator`, `prompt` | Keep the stage queued and reject claim or mutation until the approval exists. |
| [`immutable-releases`](#immutable-releases) — Exact-commit release publication | `runtime`, `ci`, `operator` | Refuse publication or a conflicting rerun without force, deletion, or tag replacement. |
| [`interruption-recovery`](#interruption-recovery) — Durable interrupted-claim recovery | `runtime`, `ci`, `operator`, `prompt` | Keep the lane interrupted and unavailable until a valid resolution is recorded. |
| [`loop-detection`](#loop-detection) — Exact repeated-tool-cycle stop | `runtime`, `pre-tool-hook`, `ci`, `prompt` | Fail the lane, stop the delivery, and deny the repeated call before execution. |
| [`orchestration-contract`](#orchestration-contract) — Canonical lifecycle instructions | `ci`, `prompt` | Fail synchronization or CI when a carrier is stale, missing, duplicated, or structurally corrupt. |
| [`path-ownership`](#path-ownership) — Claimed path ownership | `runtime`, `pre-tool-hook`, `ci`, `prompt` | Deny the claim, native write, or stage report without accepting an out-of-scope output. |
| [`runtime-budgets`](#runtime-budgets) — Measured stage budgets | `runtime`, `pre-tool-hook`, `ci`, `operator`, `prompt` | Set stage and delivery to budget_exceeded, deny further dispatch, and reject a success report. |

## Control details

### adversarial-gate

**Versioned attack matrix.** Known malformed, replayed, concurrent, stale, and filesystem-indirected attacks assert their exact safe post-state in a release-required suite.

- Enforced by: `ci`
- Implementation: [`config/adversarial-harness.json`](../config/adversarial-harness.json), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- Evidence: [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py)
- Required CI: `adversarial engineering loop`
- Failure mode: Fail hosted CI and prevent immutable release publication for the exact commit.
- Operator action: Add a stable attack ID and regression before accepting a newly discovered bypass as fixed.
- Limitation: The committed matrix covers named threat families and is not a proof against unknown attacks or same-account arbitrary code execution.

### agent-policy-profiles

**Shared and role-specific harness policy.** Every registered agent has one complete policy profile, and read-only roles align with tool denial while only the coordinator receives delegation authority.

- Enforced by: `runtime`, `pre-tool-hook`, `ci`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/check-agent-harness.py`](../scripts/check-agent-harness.py), [`scripts/enforce-reviewer-readonly.sh`](../scripts/enforce-reviewer-readonly.sh)
- Evidence: [`tests/kernel/test_agent_policy.py`](../tests/kernel/test_agent_policy.py), [`tests/guardrails.test.sh`](../tests/guardrails.test.sh)
- Required CI: `agent & command frontmatter`, `guardrail tests`, `guild kernel units`
- Failure mode: Reject an unknown, incomplete, or contradictory profile before release or planned execution.
- Operator action: Choose the registered specialist whose authority matches the requested work; do not widen a profile inside a task.
- Limitation: Direct shell access outside installed hooks is not converted into an operating-system sandbox by this profile.

### bounded-retries

**One auditable retry.** Only the main thread may request one fresh atomic claim after a distinct failure; a second distinct failure stops the delivery.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/kernel/test_retry_policy.py`](../tests/kernel/test_retry_policy.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py)
- Required CI: `guild kernel units`, `adversarial engineering loop`
- Failure mode: Requeue once with stale evidence invalidated, then fail the stage and stop delivery on exhaustion.
- Operator action: Review the typed failure and approve a new delivery if the exhausted work should continue under a new scope.
- Limitation: The retry classifier relies on the main thread to describe the failure source and reason accurately.

### criterion-evidence

**Criterion-linked verification.** Every success criterion has a stable ID and must have passing registered-runner evidence or a durable user waiver before completion.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/kernel/test_criterion_policy.py`](../tests/kernel/test_criterion_policy.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py)
- Required CI: `guild kernel units`, `adversarial engineering loop`
- Failure mode: Reject the report and leave the stage nonterminal when evidence coverage is missing or untrusted.
- Operator action: Supply the missing check or explicitly accept the exact gap through a user-authored waiver.
- Limitation: A passing registered command proves only what that command actually tests; semantic test quality remains a review concern.

### delivery-observability

**Correlated delivery event integrity.** Every persisted delivery mutation emits a typed, monotonic, hash-chained event and deterministic derived views without raw payloads.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/observability-harness.json`](../config/observability-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/observability/test_delivery_observability.py`](../tests/observability/test_delivery_observability.py)
- Required CI: `observability contract`, `guild kernel units`
- Failure mode: Report unhealthy, refuse authoritative-chain growth, and block dispatch or closure until integrity is restored.
- Operator action: Repair derived views only from a healthy authoritative chain; restore invalid kernel state from a known-good checkpoint.
- Limitation: The hash chain detects accidental or partial tampering but is not a signature against deliberate same-account rewriting.

### durable-checkpoints

**Typed human checkpoints.** Questions raised after dispatch pause the affected lane with typed options, and only a recorded user choice can continue or stop it.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/kernel/test_checkpoint_policy.py`](../tests/kernel/test_checkpoint_policy.py), [`tests/kernel/test_cli.py`](../tests/kernel/test_cli.py)
- Required CI: `guild kernel units`
- Failure mode: Keep the affected stage paused and exclude it from ready work until a valid resolution exists.
- Operator action: Select one presented option after reviewing the persisted question, risk, and recommendation.
- Limitation: The harness preserves the choice but cannot decide whether the human's risk judgment was correct.

### feedback-routing

**Ownership-derived PR and CI routing.** CI failures route by exact declared check and review comments by longest owned-path match; unmatched events block dispatch.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/kernel/test_feedback_policy.py`](../tests/kernel/test_feedback_policy.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py)
- Required CI: `guild kernel units`, `adversarial engineering loop`
- Failure mode: Persist route_required and block new dispatch, or reject a caller-asserted wrong owner without recording it.
- Operator action: Assign an unmatched event from the main thread after confirming the responsible stage.
- Limitation: External polling and event delivery remain host responsibilities; the kernel can route only feedback it receives.

### human-approvals

**Durable protected-action approval.** A stage with a declared protected category cannot be claimed until the main thread records a user grant for that exact category.

- Enforced by: `runtime`, `pre-tool-hook`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/enforce-kernel-approvals.py`](../scripts/enforce-kernel-approvals.py), [`scripts/enforce-kernel-approvals.sh`](../scripts/enforce-kernel-approvals.sh)
- Evidence: [`tests/kernel/test_approval_policy.py`](../tests/kernel/test_approval_policy.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py), [`tests/guardrails.test.sh`](../tests/guardrails.test.sh)
- Required CI: `guild kernel units`, `adversarial engineering loop`, `guardrail tests`
- Failure mode: Keep the stage queued and reject claim or mutation until the approval exists.
- Operator action: Approve or decline the exact requested category after reviewing its scope and risk.
- Limitation: The system validates declared categories; it cannot detect a planner that omitted a material protected category from the plan.

### immutable-releases

**Exact-commit release publication.** A stable release requires synchronized artifacts, a clean main commit, every named CI job green, an annotated immutable tag, and a retained receipt.

- Enforced by: `runtime`, `ci`, `operator`
- Implementation: [`config/release-harness.json`](../config/release-harness.json), [`scripts/release.py`](../scripts/release.py), [`.github/workflows/release.yml`](../.github/workflows/release.yml)
- Evidence: [`tests/release/test_release.py`](../tests/release/test_release.py)
- Required CI: `release automation`
- Failure mode: Refuse publication or a conflicting rerun without force, deletion, or tag replacement.
- Operator action: Dispatch the manual workflow with the exact version and canonical title after hosted CI succeeds.
- Limitation: Repository administrators and hosting-provider controls remain outside the publisher's threat boundary.

### interruption-recovery

**Durable interrupted-claim recovery.** A confirmed orphaned claim freezes at its last observed activity and requires a main-thread continue or stop resolution before reclaim.

- Enforced by: `runtime`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/guild-kernel/guild.py`](../scripts/guild-kernel/guild.py)
- Evidence: [`tests/kernel/test_recovery_policy.py`](../tests/kernel/test_recovery_policy.py), [`tests/kernel/test_cli.py`](../tests/kernel/test_cli.py)
- Required CI: `guild kernel units`
- Failure mode: Keep the lane interrupted and unavailable until a valid resolution is recorded.
- Operator action: Confirm the prior process no longer owns the claim, inspect partial outputs, then choose continue or stop.
- Limitation: The kernel cannot independently prove that an external process died or reconstruct completion telemetry it never received.

### loop-detection

**Exact repeated-tool-cycle stop.** The runtime blocks the call that would complete a third identical one-to-four-step tool cycle and stores only bounded signatures.

- Enforced by: `runtime`, `pre-tool-hook`, `ci`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/enforce-kernel-budgets.py`](../scripts/enforce-kernel-budgets.py)
- Evidence: [`tests/kernel/test_loop_policy.py`](../tests/kernel/test_loop_policy.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py), [`tests/guardrails.test.sh`](../tests/guardrails.test.sh)
- Required CI: `guild kernel units`, `adversarial engineering loop`, `guardrail tests`
- Failure mode: Fail the lane, stop the delivery, and deny the repeated call before execution.
- Operator action: Inspect the loop record and create a materially changed plan rather than replaying the same sequence.
- Limitation: Semantically repetitive work with changing tool names or inputs is not classified as an exact cycle.

### orchestration-contract

**Canonical lifecycle instructions.** The shared lifecycle text is authored once and materialized byte-for-byte into all registered command and coordinator carriers.

- Enforced by: `ci`, `prompt`
- Implementation: [`config/orchestration-contract.md`](../config/orchestration-contract.md), [`scripts/sync-orchestration-contract.py`](../scripts/sync-orchestration-contract.py)
- Evidence: [`tests/orchestration/test_sync_contract.py`](../tests/orchestration/test_sync_contract.py), [`tests/guardrails.test.sh`](../tests/guardrails.test.sh)
- Required CI: `agent & command frontmatter`, `guardrail tests`, `guild kernel units`
- Failure mode: Fail synchronization or CI when a carrier is stale, missing, duplicated, or structurally corrupt.
- Operator action: Edit the canonical source, regenerate carriers, and review the generated diff rather than patching one carrier.
- Limitation: Synchronized prompt text guides agents but does not replace runtime checks for protected transitions.

### path-ownership

**Claimed path ownership.** A mutation-capable stage declares project-relative owned paths, claims them atomically, and cannot report outputs outside them.

- Enforced by: `runtime`, `pre-tool-hook`, `ci`, `prompt`
- Implementation: [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/enforce-agent-paths.py`](../scripts/enforce-agent-paths.py), [`scripts/enforce-agent-paths.sh`](../scripts/enforce-agent-paths.sh)
- Evidence: [`tests/kernel/test_kernel.py`](../tests/kernel/test_kernel.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py), [`tests/guardrails.test.sh`](../tests/guardrails.test.sh)
- Required CI: `guild kernel units`, `adversarial engineering loop`, `guardrail tests`
- Failure mode: Deny the claim, native write, or stage report without accepting an out-of-scope output.
- Operator action: Split overlapping work into non-overlapping stages or change the approved plan before dispatch.
- Limitation: The native-write hook covers Write, Edit, and NotebookEdit; Bash mutation safety also depends on the installed command guardrails.

### runtime-budgets

**Measured stage budgets.** Time and tool calls are checked before tool execution, completion telemetry supplies turns, tokens, and cost, and a breach becomes terminal.

- Enforced by: `runtime`, `pre-tool-hook`, `ci`, `operator`, `prompt`
- Implementation: [`config/agent-harness.json`](../config/agent-harness.json), [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), [`scripts/enforce-kernel-budgets.py`](../scripts/enforce-kernel-budgets.py), [`scripts/enforce-kernel-budgets.sh`](../scripts/enforce-kernel-budgets.sh)
- Evidence: [`tests/kernel/test_budget_policy.py`](../tests/kernel/test_budget_policy.py), [`tests/console/test_engine.py`](../tests/console/test_engine.py), [`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py)
- Required CI: `guild kernel units`, `console python units`, `adversarial engineering loop`, `guardrail tests`
- Failure mode: Set stage and delivery to budget_exceeded, deny further dispatch, and reject a success report.
- Operator action: Start a newly approved delivery with a justified budget when additional work is warranted; never edit the receipt downward.
- Limitation: Cost is conservative when the host provides tokens but not a billed total, and unsupported runtimes must provide all five dimensions explicitly.

## What this map does not prove

- No repository control protects against arbitrary code executing as the same operating-system account and deliberately rewriting code, state, and evidence together.
- Pre-tool hooks cover the tools and hosts that install them; unsupported runtimes must call the kernel explicitly and provide complete telemetry.
- CI proves the committed fixtures and named invariants, not every application-specific behavior or production environment.
- Human approvals, interruption confirmation, manual speed checks, and merge decisions remain operator judgments; the harness preserves and validates their durable records.

## Verify the map

```sh
python3 scripts/check-enforcement-map.py
```

A healthy checkout reports `14 controls` and exits `0`. The checker validates
the exact control inventory, safe repository-local evidence paths, release-gated CI
job names, enforcement-level ordering, and byte-for-byte agreement with this page.
It does not execute commands stored in data files.

## Symptoms

- The checker reports an unknown control, missing evidence path, or non-release CI job.
- This page differs from the deterministic render of the manifest.
- A control's implementation or evidence moved without an enforcement-map update.
- A statement is marked only as `prompt` but is described elsewhere as guaranteed.

## Triage

1. Run the checker and preserve its first error.
2. Inspect the named control in `config/enforcement-map.json`.
3. Confirm the implementation still rejects the documented failure case and that the
   cited test exercises that boundary.
4. Confirm every named CI job remains in `config/release-harness.json`.
5. If only this generated page is stale, compare its diff before regenerating it.

## Resolve

1. Correct the manifest or restore the missing implementation/evidence file.
2. Regenerate this page with `python3 scripts/check-enforcement-map.py --write`.
3. Run the checker, the cited focused tests, and the full release gates.
4. If a hard control became prompt-only, stop the release and either restore enforcement
   or explicitly document the reduced guarantee as a breaking change.
5. Roll back an unpublished map by restoring the manifest and generated page together.
   Never preserve a stronger claim than the implementation and evidence support.

Escalate to the release owner when a control has no executable evidence, a trust boundary
is disputed, a required CI job must be removed, or the safe failure mode changed.
