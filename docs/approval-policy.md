# Runtime stage approvals

Laravel Guild turns each agent profile's approval categories into a delivery
gate. The planner declares sensitive actions before dispatch. The kernel then
keeps that lane paused until the user explicitly approves every declared
category.

## Declare sensitive work

Use only categories registered for the selected agent in
`config/agent-harness.json`. The kernel rejects misspelled, duplicate, and
cross-agent categories.

```sh
python3 scripts/guild-kernel/guild.py plan \
  --root . \
  --name prune-legacy-orders \
  --done-when "legacy orders are removed safely" \
  --stage-json '{"id":"database","agent":"database-developer","role":"writer","success_criteria":["rollback path is documented"],"criterion_ids":["rollback-documented"],"depends_on":[],"owned_paths":["database/migrations"],"approval_categories":["destructive migration"]}'
```

Use `"approval_categories":[]` only when no category from that agent's profile
applies. Declaring no category is a planning assertion; it is not a wildcard
approval.

## Review and grant

List approvals after planning:

```sh
python3 scripts/guild-kernel/guild.py approval list \
  --root . --name prune-legacy-orders
```

Pending lanes display `⏸`, do not appear in `ready`, and cannot be claimed.
After the human accepts the stated blast radius, the main thread records the
decision:

```sh
python3 scripts/guild-kernel/guild.py approval grant \
  --root . \
  --name prune-legacy-orders \
  --stage database \
  --category "destructive migration"
```

The command is idempotent. It stores the exact category, `by: user`, and a UTC
timestamp in `docs/delivery/prune-legacy-orders/kernel.json`. That record
survives interruption and resume.

The main thread is the approval trust boundary. The kernel proves that a
main-thread grant was recorded and prevents subagent self-grants; it cannot
cryptographically prove that a person read the prompt. The orchestration
contract therefore requires a numbered human checkpoint before the grant.

## Enforcement boundary

On Claude Code, `enforce-kernel-approvals.sh`:

- blocks a Guild subagent while its active stage is unclaimed or has pending
  approval;
- denies every subagent attempt to invoke `approval grant`;
- denies native writes to `docs/delivery/*/kernel.json` for every caller; and
- denies common Bash write forms that target kernel state directly.

The existing production guards remain stricter. Approval does not bypass a
production `migrate:fresh`, destructive production SQL, credential write, or
another deny-rule. Run those operations from a separately privileged operator
session when the guard's message requires it.

The kernel gate applies to planned deliveries. Direct single-specialist work
has no stage to approve, so the agent's prompt checkpoint remains the control
on that fast path. The coordinator must not use the fast path when a registered
approval category applies.

Gemini receives the profile categories and orchestration instructions, but its
hook payload does not identify the calling subagent, so identity-aware runtime
enforcement is Claude Code-specific. Codex Core does not ship the Guild
subagent team.
