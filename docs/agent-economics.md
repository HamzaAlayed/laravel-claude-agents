# How do agents spend less without lowering quality?

Last verified 2026-09-27 against pack v9.9.0.

Optimize the cost of a successful, verified outcome—not token count, request
price, or one lucky run. The deterministic harness in
`scripts/economics-harness.py` routes work before dispatch and compares actual
billed evidence before a cheaper configuration becomes the accepted default.
Its policy is `config/economics-harness.json`; its executable examples are
`config/economics-scenarios.json`; and its focused evidence is
`tests/economics/test_economics_harness.py`.

## What decisions does the harness make?

Routing emits `route` or `hold`. A routed workload receives the highest tier
floor required by complexity, risk, and context:

| Project tier | Selector | Intended use |
| --- | --- | --- |
| `economy` | `haiku` | Routine, low-risk, bounded work with explicit checks. |
| `standard` | `sonnet` | Normal implementation, tool use, or long-context work. |
| `premium` | `opus` | Complex, high-risk, or protected reasoning. |

These are project aliases, not claims about a provider's current price,
availability, intelligence, or context window. A protected workload without
approval, an unknown classification, or any estimated budget breach emits
`hold` and no selector.

Comparison emits exactly one decision:

| Decision | Meaning | Next action |
| --- | --- | --- |
| `adopt-candidate` | Representative evidence proves materially lower cost per successful outcome inside every quality and operational boundary. | Adopt the exact measured configuration. |
| `keep-baseline` | The candidate is unsafe, worse, over budget, or saves too little. | Keep the current configuration. |
| `hold` | The sample, baseline, criteria, or configuration is not comparable. | Repair the evidence and compare again. |

## What must a workload declare?

Every schema-version-1 workload declares its complexity, risk, capabilities,
estimated time, tokens, tools, retries, USD, long-context need, stable reusable
prefix, batch shape, side effects, protected-action approval, required
criteria, and a task budget. The task budget may narrow but never raise the
shared defaults in `config/agent-harness.json`.

Start with one of the ten registered workloads, save it under the delivery,
then run:

```bash
python3 scripts/economics-harness.py route \
  --root . \
  --workload docs/delivery/<delivery>/economics-workload.json \
  --output docs/delivery/<delivery>/economics-route-receipt.json

python3 scripts/economics-harness.py verify \
  --root . \
  --receipt docs/delivery/<delivery>/economics-route-receipt.json
```

The receipt binds the workload and every policy source with SHA-256. It does
not retain prompts, assistant text, commands, responses, tool payloads, or
secrets.

## When are caching, batching, and early stopping allowed?

Cache reuse is only eligible when at least 2,000 input tokens form a stable
hash-bound prefix. Secrets, credentials, untrusted instructions, and volatile
authorization state are never cache material.

Batching is eligible only for two to eight independent items with one shared
authority scope and no side effects. Anything else stays separate.

Early stopping is not “the answer looks good.” It is allowed only after every
required criterion and verification passes. A safety violation, missing
protected-action approval, hard budget breach, or corrupt evidence stops
immediately; early stopping never skips verification, a security boundary, an
approval, or receipt sealing.

## How is a real saving proven?

Capture at least five representative baseline runs and five candidate runs
using the observation schema enforced by the harness. A run records required
and passing criteria, success, safety violations, duration, actual billed USD,
token categories, tool calls, retries, and human intervention. Use actual
billed totals when available; a price table is not the metric of record.

```bash
python3 scripts/economics-harness.py compare \
  --root . \
  --baseline docs/delivery/<delivery>/economics-baseline.json \
  --candidate docs/delivery/<delivery>/economics-candidate.json \
  --output docs/delivery/<delivery>/economics-comparison-receipt.json

python3 scripts/economics-harness.py verify \
  --root . \
  --receipt docs/delivery/<delivery>/economics-comparison-receipt.json
```

`adopt-candidate` requires at least 15% lower total billed USD per successful
outcome, no completion or criterion-pass regression, zero safety violations,
no added retries or human intervention, and median duration and tool calls no
more than 25% above baseline. A cheap failed run still contributes cost but no
successful outcome, which prevents “saving money” by silently doing less.

## Symptoms

- `economics error: ...` exits with status 1.
- A route receipt says `hold` and names one or more reasons.
- A comparison says `keep-baseline` or `hold`.
- Receipt verification reports tampering, stale evidence, or source drift.
- The hosted `agent economics` job fails.

## Triage

1. Validate the policy and replay every registered scenario:

   ```bash
   python3 scripts/economics-harness.py validate --root .
   python3 scripts/economics-harness.py exercise --root .
   ```

2. Run the focused adversarial suite:

   ```bash
   python3 -m unittest discover -s tests/economics -t tests/economics -v
   ```

3. Verify the exact delivery receipt:

   ```bash
   python3 scripts/economics-harness.py verify \
     --root . \
     --receipt docs/delivery/<delivery>/<receipt>.json
   ```

Source drift means the old conclusion is stale. Tampering means the receipt no
longer matches its seal. Do not edit either condition away.

## Resolve

1. For an unknown classification, classify complexity and risk explicitly.
2. For missing protected-action approval, obtain the exact user approval or
   remove the protected action from scope.
3. For an estimated or hard budget breach, reduce the workload or ask the user
   to authorize a new delivery budget; never rewrite recorded usage downward.
4. For `insufficient-evidence`, collect at least five representative runs per
   variant with the same workload and criteria.
5. For `configuration-not-changed`, change one declared lever—tier, context,
   cache, batch size, or attempts—before claiming a comparison.
6. For quality, safety, duration, tool, retry, or intervention regressions,
   keep the baseline and repair the candidate rather than weakening the gate.
7. For insufficient cost-per-success reduction, keep the baseline until a new
   measured candidate clears the material threshold.
8. For drift, rebuild the source evidence and receipt from the reviewed state.

Rollback is the last accepted exact configuration. The harness does not invoke
models, buy credits, change provider settings, approve protected actions, or
perform database work.

## What does this not prove?

The harness cannot prove that a sample represents production, that provider
billing is correct, that a declared cache or batch executes safely, or that a
tier alias still maps to a particular provider model. Source hashes detect
drift but are not signatures against a same-account attacker who can rewrite
the implementation and evidence together. Operators still own workload
selection, telemetry completeness, provider configuration, and approvals.
