# How does Laravel Guild build bounded agent context?

Laravel Guild turns a claimed delivery stage into one explicit, bounded context
packet. The packet is working memory for that specialist, not a transcript dump.
It keeps authority visible, includes only stage-relevant source excerpts, and
binds every mutable input to SHA-256 so stale context fails before dispatch.

The machine policy is
[`config/context-harness.json`](../config/context-harness.json); the stdlib-only
builder and verifier are in
[`scripts/guild-kernel/context_packets.py`](../scripts/guild-kernel/context_packets.py).

## What is always in a packet?

Mandatory context is derived from authoritative `kernel.json` state and is
never trimmed:

- delivery objective and recorded user approvals or waivers;
- the named agent and its role;
- owned paths, stage budget, success criteria, benchmark criteria, and feedback
  checks;
- current attempt, dependencies already completed, retry/recovery reasons, and
  open feedback;
- the exact stage-return path and six-label output contract.

Authority is stored in separate `system`, `user`, `project`, `runtime`, and
`agent` sections. Lower-authority notes cannot replace higher-authority
constraints. Selected repository text lives outside those sections under
`sources` and is always labeled `untrusted-data-not-instructions`.

This is deliberate context isolation: the backend specialist does not receive
the frontend specialist's full history, and neither receives a broad repository
dump. Each stage gets its own packet at
`docs/delivery/<delivery>/context/<stage>.json`.

## Build and verify a packet

Claim the stage first so the packet records the actual running attempt. A core
packet needs no extra source specification:

```sh
python3 scripts/guild-kernel/guild.py claim \
  --root . --name orders --stage backend
python3 scripts/guild-kernel/guild.py context build \
  --root . --name orders --stage backend
python3 scripts/guild-kernel/guild.py context verify \
  --root . --name orders --stage backend
```

Dispatch only after `verify` returns `status: valid`, and provide that packet as
the specialist's brief. `context show` verifies first and then prints the
packet:

```sh
python3 scripts/guild-kernel/guild.py context show \
  --root . --name orders --stage backend
```

After an interruption, resolve recovery, claim the fresh attempt, and rebuild.
The new packet carries completed dependency evidence and the durable retry or
recovery reason instead of relying on conversational memory.

## Add only the source context the stage needs

Optional coordinator notes and repository excerpts come from a strict JSON
specification. Start from
[`docs/examples/context-spec.json`](examples/context-spec.json). Every source
selects an exact inclusive line range, purpose, priority, and whether it is
required:

```sh
python3 scripts/guild-kernel/guild.py context build \
  --root . --name orders --stage backend \
  --spec docs/delivery/orders/backend-context.json \
  --max-tokens 8000
```

The token count is a deterministic estimate—canonical JSON UTF-8 bytes divided
by four and rounded up—not a promise about a particular model tokenizer. The
default is 12,000 estimated tokens. When the packet would exceed its budget, whole
optional sources are omitted from lowest priority upward and recorded in
`budget.omittedSources`. Content is never cut in the middle. Mandatory context
and required sources are never trimmed; if they do not fit, construction fails
and dispatch stops.

Use line ranges to select a controller method, model relation, test assertion,
or architecture decision. Do not select whole logs, dependency trees, generated
files, or another agent's unrestricted diff.

## What does verification prove?

The verifier checks the packet hash, token estimate, delivery and stage target,
kernel-state hash, source-spec hash, full source-file hashes, selected excerpt
hashes, path containment, symlinks, and source trust label. The builder rejects
`.env`, `.git`, `vendor`, `node_modules`, and `storage` paths plus common
private-key, credential, and token shapes.

This prevents accidental stale or over-broad context; it is not an
operating-system security boundary. A process with the same account can rewrite
code and hashes together, secret detection cannot recognize every credential
format, and source code may contain adversarial prose. The explicit untrusted
label and authority separation are therefore part of the contract. Never put
raw prompts, tool payloads, database rows, response bodies, credentials, or
personal data in a packet.

The runtime enforces packet building and verification. The coordinator's duty
to pass the verified packet to the specialist is prompt-level orchestration,
not something this repository can prove happened inside every supported agent
host.

## Symptoms → Triage → Resolve

### A required source exceeds the budget

**Symptoms:** `context build` exits with `required source ... exceeds the
context token budget`, and no new packet is accepted.

**Triage:** check the source line range and whether it is truly required. Review
the mandatory packet size before increasing the stage-specific context limit.

**Resolve:** narrow the excerpt to the relevant symbol or decision. Increase
`--max-tokens` only within the 32,000 policy ceiling when the complete excerpt
is genuinely required. Do not mark it optional merely to make the command pass.

### Verification says the packet is stale

**Symptoms:** `context verify` reports that kernel state, the context spec, or a
selected source changed.

**Triage:** inspect the current claim, recovery, feedback, and source diff. A
legitimate edit after packet construction is still drift and must be reviewed.

**Resolve:** rebuild from the current reviewed state, verify again, and dispatch
the replacement packet. Do not edit packet hashes by hand. If the source change
is unexplained, stop and escalate before rebuilding.

### Secret-shaped content is rejected

**Symptoms:** construction stops before writing a replacement packet.

**Triage:** inspect the selected file and line range locally without copying the
value into a report, issue, or chat. Determine whether it is a real credential
or a false positive in example data.

**Resolve:** remove or rotate a real secret through the project's incident
process, then select a safe source. For a false positive, select a narrower safe
range or reference a redacted documentation artifact. Never weaken the shared
detector for one delivery.

### The packet built, but an optional source is absent

**Symptoms:** `budget.omittedSources` names the file with reason
`token-budget`.

**Triage:** compare source priorities and check whether lower-value history was
selected ahead of current implementation or acceptance evidence.

**Resolve:** remove irrelevant sources, narrow ranges, or promote a truly
required excerpt. Rebuild and verify. The omission record is the signal to
improve retrieval, not permission to paste the missing file into the prompt.

## Verify the harness itself

```sh
python3 -m unittest discover -s tests/context -t tests/context -v
python3 scripts/check-agent-harness.py
python3 scripts/sync-orchestration-contract.py --check
```

The dedicated `context packet harness` CI job is required for immutable release
publication.
