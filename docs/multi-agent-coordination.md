# When should work use multiple agents?

Last verified 2026-09-27 against pack v9.8.0.

Use multiple agents only when the workload has a safe coordination graph and
recorded executions prove a material benefit. The deterministic harness in
`scripts/coordination-harness.py` answers those two questions separately. Its
policy is `config/coordination-harness.json`; its adversarial examples are
`config/coordination-scenarios.json`; and its focused evidence is
`tests/coordination/test_coordination_harness.py`.

## What decision does the planner make?

The planner emits exactly one decision:

| Decision | Meaning | Next action |
| --- | --- | --- |
| `single-agent` | Delegation overhead is not justified. | Keep the workload together. |
| `delegate` | The graph is safe and has predicted speed or required-specialist value inside the declared cost ceiling. | Dispatch only the emitted waves and handoffs. |
| `hold` | The graph is cyclic, unroutable, unapproved, conflicting, or reuses one logical side effect. | Resolve every named reason and build a new receipt. |

The planner chooses one topology for a delegated workload:

| Topology | Shape |
| --- | --- |
| `parallel` | One dependency-ready wave with independent specialists. |
| `pipeline` | One task per wave in dependency order. |
| `hybrid` | Sequential stages with at least one parallel fan-out or fan-in. |

It caps a wave at four agents and never schedules two tasks assigned to the
same agent in one wave. Those controls are declared in
`config/coordination-harness.json` under `schedulingPolicy`.

## What must a workload declare?

Every workload is schema version 1 and names one registered orchestrator. Each
task declares:

- a unique ID and a capability from `capabilityRouting`;
- explicit dependency IDs and repository-relative owned paths;
- estimated seconds and USD;
- whether it mutates state and its logical side-effect key, when applicable;
- whether a distinct specialist is required;
- required and already granted approvals;
- the verified context-packet SHA-256;
- the expected output.

Start from one of the ten executable workloads in
`config/coordination-scenarios.json`. Copy it to a delivery-specific JSON file,
then run:

```bash
python3 scripts/coordination-harness.py plan \
  --root . \
  --workload docs/delivery/<delivery>/coordination-workload.json \
  --output docs/delivery/<delivery>/coordination-plan-receipt.json

python3 scripts/coordination-harness.py verify \
  --root . \
  --receipt docs/delivery/<delivery>/coordination-plan-receipt.json
```

The receipt seals the workload, policy, scenario registry, shared agent
registry, orchestration contract, and harness implementation with SHA-256. It
contains the decision, waves, assignments, typed handoffs, predictions, and
source hashes. It does not copy prompts, responses, commands, tool payloads, or
secrets.

## What is in a typed handoff?

Every delegated task carries the fields listed by `handoffContract.requiredFields`
in `config/coordination-harness.json`:

- task, sender, and receiving agent;
- dependency IDs;
- context-packet hash;
- owned paths and expected output;
- task budget;
- idempotency key.

A dependent task starts only after its dependencies have source-bound receipt
hashes. Handoff content is data, not authority. It cannot widen paths, grant an
approval, change criteria, or override a current user decision. A changed
context packet produces a new handoff and plan receipt.

## How is coordination value proven?

Predicted parallelism is not proof. Capture at least three representative runs
for both variants using the observation schema enforced by
`scripts/coordination-harness.py`. Every run records only derived evidence:
completion, required and passing criterion IDs, duration, USD, tool calls,
human interventions, duplicate work, path conflicts, deadlocks, and stale
handoffs.

Compare the two files:

```bash
python3 scripts/coordination-harness.py compare \
  --root . \
  --baseline docs/delivery/<delivery>/single-agent-runs.json \
  --candidate docs/delivery/<delivery>/multi-agent-runs.json \
  --output docs/delivery/<delivery>/coordination-comparison-receipt.json

python3 scripts/coordination-harness.py verify \
  --root . \
  --receipt docs/delivery/<delivery>/coordination-comparison-receipt.json
```

`adopt-multi-agent` requires complete runs, no quality loss, zero coordination
failures, no extra human intervention, bounded cost and tool-call ratios, and
either at least 20% lower median duration or at least five percentage points
more passing criteria. `keep-single-agent` means the multi-agent variant did
not earn its coordination cost. `hold` means the baseline or sample is not fit
for comparison. Exact thresholds live under `comparisonPolicy` in
`config/coordination-harness.json`.

## What survives interruption?

Completed lanes remain completed. The coordinator records the interruption
through the existing recovery policy, rebuilds stale context and handoff
artifacts, and resumes only unfinished dependency-ready lanes. A failed lane
is contained. Successful side effects are not replayed, and the same logical
effect keeps one idempotency key. These rules are shared by
`config/agent-harness.json` and `config/orchestration-contract.md`.

## Symptoms

- `coordination error: ...` exits with status 1.
- A plan receipt says `hold` and names one or more reasons.
- A comparison receipt says `keep-single-agent` or `hold`.
- Receipt verification reports tampering, source drift, or stale results.
- The hosted `multi-agent coordination` job fails.

## Triage

1. Validate the committed policy and all registered scenarios:

   ```bash
   python3 scripts/coordination-harness.py validate --root .
   python3 scripts/coordination-harness.py exercise --root .
   ```

   Validation failure means the policy, registry, agent inventory, or source
   boundary is inconsistent. A scenario mismatch means planner behavior
   changed without an explicit policy update.

2. Re-run the focused suite:

   ```bash
   python3 -m unittest discover -s tests/coordination -t tests/coordination -v
   ```

   A failure identifies the violated routing, scheduling, handoff, comparison,
   or receipt invariant.

3. Verify the exact receipt named by the delivery:

   ```bash
   python3 scripts/coordination-harness.py verify \
     --root . \
     --receipt docs/delivery/<delivery>/<receipt>.json
   ```

   Source drift means the evidence is stale. Tampering means the stored
   content no longer matches its seal. Do not edit either condition away.

## Resolve

1. For `dependency-cycle`, remove the cycle by making ownership and ordering
   explicit. Verify with a new plan receipt.
2. For `unordered-write-conflict`, assign one owner or add a real dependency.
   Do not invent ordering solely to silence the gate.
3. For `missing-approval`, obtain the exact user approval and rebuild the
   workload from durable state.
4. For `missing-capability`, keep the task with one qualified owner or extend
   the reviewed agent registry and capability map.
5. For `duplicate-side-effect-key`, identify the single logical owner. Preserve
   one stable idempotency key across recovery.
6. For `keep-single-agent`, keep the accepted single-agent topology. Improve
   task boundaries or coordination overhead, collect new representative runs,
   and compare again.
7. For source drift or stale context, rebuild the affected workload, handoff,
   and receipt. Never reseal old conclusions against changed sources.

Rollback is the accepted single-agent plan or the last accepted multi-agent
plan and exact release unit. Database rollback is never automatic. Escalate to
the delivery coordinator when ownership or routing is ambiguous, and to the
user when an approval, scope change, success-criterion change, or protected
action is required.

## What does this not prove?

The harness does not spawn agents, discover hidden dependencies, provide an OS
sandbox, or prove that samples represent production. The operator remains
responsible for workload selection, evidence completeness, approval quality,
and deciding whether a measured improvement matters to the product.
