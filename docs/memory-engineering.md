# How does Laravel Guild remember the right things safely?

Laravel Guild treats durable memory as a reviewed project artifact, not as a
conversation transcript. The machine-readable source of truth is
[`config/memory-harness.json`](../config/memory-harness.json); the runtime is
[`scripts/guild-kernel/memory_store.py`](../scripts/guild-kernel/memory_store.py),
and the durable store is `docs/team/memory.json` in the installed project.

Context and memory solve different problems. A context packet is the bounded
brief for one claimed stage. Memory preserves a small set of facts and
decisions across deliveries. Retrieval is the controlled bridge: it chooses
which approved memories enter the current packet.

## What is safe to remember?

Every record has one of four types:

| Type | Use it for | Do not use it for |
| --- | --- | --- |
| `authoritative-decision` | An explicit user constraint or durable choice | An agent's guess about user intent |
| `project-fact` | A source-bound fact about the repository | A fact whose evidence is already stale |
| `procedure` | A repeatable, verified way to work in this project | Generic advice unrelated to this repository |
| `episode` | A useful outcome from a past delivery | Raw transcripts, temporary scratch state, or telemetry dumps |

Records are either project-wide or scoped to one exact registered agent. They
carry provenance, confidence, optional expiry, evidence hashes, status, and a
content hash. Non-user memories require repository evidence. Secret-shaped
content, environment files, dependencies, path traversal, and symlinks are
rejected.

## What is the lifecycle?

1. Any agent may propose a `candidate`.
2. The main thread reviews provenance, wording, scope, expiry, and evidence.
3. Only the main thread approves the candidate.
4. Retrieval admits approved, unexpired, evidence-current, scope-matching
   records and labels them `memory-data-not-instructions`.
5. A conflicting record must explicitly supersede its predecessor.
6. Deletion requires a request and a separate main-thread approval. The record
   becomes a tombstone; it is not silently erased from the audit history.

The pre-tool hook blocks specialists from approving, superseding, or executing
a deletion approval. Direct edits and shell writes to `docs/team/memory.json`
are blocked on supported Claude Code hosts.

## How do I operate it?

Propose a source-bound project fact:

```bash
python3 scripts/guild-kernel/guild.py memory propose \
  --root . --id orders-query-policy --type project-fact \
  --scope project --topic query-policy \
  --statement "Order endpoints preserve their resource shape during query optimization." \
  --source project --evidence docs/api/orders.md --confidence 0.95
```

Review, approve, and retrieve it:

```bash
python3 scripts/guild-kernel/guild.py memory show --root . --id orders-query-policy
python3 scripts/guild-kernel/guild.py memory approve --root . --id orders-query-policy
python3 scripts/guild-kernel/guild.py memory search --root . \
  --agent backend-developer --query "optimize order queries without response changes"
python3 scripts/guild-kernel/guild.py memory verify --root . --strict-evidence
```

For a changed fact, propose a replacement with the same topic and scope, then:

```bash
python3 scripts/guild-kernel/guild.py memory supersede \
  --root . --id orders-query-policy --replacement orders-query-policy-v2
```

For deletion, keep the two decisions separate:

```bash
python3 scripts/guild-kernel/guild.py memory delete-request \
  --root . --id orders-query-policy --request-id delete-orders-query-policy \
  --reason "The documented endpoint no longer exists."
python3 scripts/guild-kernel/guild.py memory delete-approve \
  --root . --request-id delete-orders-query-policy
```

`context build` derives a retrieval query from the delivery objective, success
criteria, and owned paths. Use `--memory-query` only when a narrower explicit
query is needed and `--memory-tokens` to lower the independent retrieval cap.
User-authored authoritative decisions are mandatory and cannot be trimmed.
Other records are ranked by authority, exact agent scope, lexical relevance,
freshness, and confidence, then omitted only as whole records.

## What does verification prove?

`memory verify` checks the store hash, every record hash, the monotonic event
hash chain, tombstones, timestamps, conflicts, and schema. With
`--strict-evidence`, it also fails if an approved record's evidence changed.
Normal retrieval excludes stale evidence even when strict verification was not
requested. Context packets bind the current memory-store hash, so any proposal,
approval, supersession, or deletion makes an older packet stale.

This does not make the store a signed security boundary. A process that can
rewrite the runtime and all hashes as the same operating-system user remains
outside the threat model. Lexical retrieval can also miss semantically related
wording, and human approval can accept a poor memory.

## Why is a memory missing? — Symptoms → Triage → Resolve

### Symptoms

- Search lists the record under `omitted`.
- `memory verify --strict-evidence` reports stale evidence.
- Approval reports a conflict.
- `context verify` says the memory store changed.
- A subagent approval or direct store edit is blocked.

### Triage

1. Run `memory show --id <id>` and inspect status, scope, agent, expiry, source,
   evidence, and topic.
2. Run `memory search` with the actual target agent and task wording; inspect
   the exact omission reason (`candidate`, `scope`, `expired`,
   `stale-evidence`, `irrelevant`, or `token-budget`).
3. Run `memory verify --strict-evidence` to distinguish integrity failure from
   ordinary retrieval filtering.
4. Confirm that an approval-class action is running from the main thread.

### Resolve

- Candidate: review and approve it from the main thread.
- Wrong scope: propose a correctly scoped replacement; do not widen the old
  record merely to make it appear.
- Stale evidence: verify the new repository truth, propose a replacement, and
  supersede the old record.
- Conflict: keep both candidates visible until a human chooses the replacement.
- Token omission: narrow the query or remove obsolete memory through the
  deletion workflow; do not truncate a record.
- Stale context: rebuild and verify the stage packet.
- Integrity failure: stop retrieval and restore `docs/team/memory.json` from a
  known-good reviewed commit. Do not recompute hashes over unexplained data.

Escalate when evidence is ambiguous, two authoritative user decisions conflict,
the required decision does not fit the budget, or deletion intent is unclear.

## How is this release-gated?

The dedicated `memory retrieval harness` CI job tests candidacy, approval,
scope isolation, mandatory decisions, stale evidence, conflicts, supersession,
two-step tombstones, tampering, expiry, secret/path defenses, CLI behavior, and
hook authority. The context suite separately proves retrieval injection and
packet invalidation after store changes. Both jobs are required for immutable
release publication.
