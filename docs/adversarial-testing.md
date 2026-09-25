# How do adversarial engineering-loop tests fail closed?

Last verified 2026-09-25 against pack v8.8.0.

Laravel Guild runs a versioned attack matrix against the delivery kernel before
every release. The authoritative case list is
[`config/adversarial-harness.json`](../config/adversarial-harness.json), and the
executable scenarios are in
[`tests/adversarial/test_engineering_loop.py`](../tests/adversarial/test_engineering_loop.py).
The test module rejects drift between those two sources.

## Threat model

The gate covers malformed, replayed, concurrent, and filesystem-indirected
inputs presented to the engineering loop. It assumes the kernel and guardrails
still execute under the project account. It does not claim to defend against
arbitrary code execution by another process with that same operating-system
account, or direct state modification after every guardrail has already been
bypassed. Those are host-isolation problems, not orchestration claims.

## Protected invariants

- Kernel-owned delivery, sprint, and lesson files stay below the project root,
  including when an intermediate directory is a symlink.
- A report is accepted only from
  `docs/delivery/<name>/stages/<registered-agent>.md`; a substituted or
  symlinked report is rejected before any verifier runs.
- Structured verification never evaluates arbitrary shell text.
- Approval, criterion, measurement, budget, feedback ownership, and terminal
  state remain kernel decisions.
- Duplicate external events and concurrent claims produce at most one legal
  state transition.

## Attack families

| Cases | Family | Proof |
| --- | --- | --- |
| ADV-001–004, ADV-017 | Path containment | Traversal and symlink attacks create no file outside the project. |
| ADV-005–007 | Artifact and evidence integrity | Foreign reports and shell-shaped evidence are rejected before execution. |
| ADV-008, ADV-016 | Authority | An agent cannot claim pending sensitive work or impersonate user/main authority through kernel APIs. |
| ADV-009–011 | Measurement and terminality | Missing telemetry, exhausted budgets, and repeated tool cycles cannot report or dispatch more work. |
| ADV-012, ADV-014–015 | Replay, concurrency, stale state | Duplicate retry delivery, double claim, and pre-retry reports cannot create a second transition. |
| ADV-013 | Feedback routing | A caller assertion cannot redirect a known CI check to another owner. |
| ADV-018 | Trace integrity | Control characters cannot enter stage identifiers or generated state views. |

## Run the gate

From the repository root:

```sh
python3 -m unittest discover -s tests/adversarial -t tests/adversarial -v
```

Expected result: 19 tests pass, representing 18 named attacks plus the manifest
coverage check. The `adversarial engineering loop` CI job runs the same command
and is listed in `config/release-harness.json`; an immutable release cannot
publish without it.

## Symptoms

- A test named `test_adv_NNN_...` fails.
- The manifest coverage test reports missing or unexpected attack IDs.
- CI reports `adversarial engineering loop` as failed or missing.
- Release preflight reports that the required adversarial job did not pass.

## Triage

1. Run the command above and identify the first attack ID that fails.
2. Read that ID in `config/adversarial-harness.json` to confirm the expected
   denial and no-mutation outcome.
3. Inspect the persisted `kernel.json` or outside-path assertion from the test.
   A raised exception alone is insufficient: the resulting state must exactly
   match the case's safe post-condition.
4. Run the ordinary kernel suite to distinguish a perimeter regression from a
   broader lifecycle regression:

   ```sh
   python3 -m unittest discover -s tests/kernel -t tests/kernel -v
   ```

## Resolve

1. Add or preserve a failing adversarial reproduction before changing kernel
   behavior.
2. Fix the shared kernel boundary rather than special-casing the test payload.
3. Prove both the expected denial and the no-mutation assertion.
4. Run the adversarial and ordinary kernel suites, then the full CI-equivalent
   verification set.
5. If a legitimate identifier or artifact path is newly rejected, revert the
   unpublished change and redesign the boundary. Do not weaken a containment
   assertion merely to restore compatibility.

Escalate to the release owner when an attack requires host-level isolation,
when the fix would broaden agent authority, or when a published compatibility
contract conflicts with containment.
