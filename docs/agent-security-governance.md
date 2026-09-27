# How do Laravel Guild agents stay inside their security boundary?

Last verified 2026-09-27 against pack v9.6.0.

Laravel Guild treats agent security as an authority and capability problem,
not as a promise that a model will always follow instructions. Runtime policy
and explicit current user decisions are authoritative. Repository text,
memory, tool output, logs, issues, and external content are data and cannot
grant authority. Installed hooks and the delivery kernel reject covered unsafe
actions before execution; required CI attacks those boundaries before release.

The machine-readable sources are
[`config/security-harness.json`](../config/security-harness.json) and
[`config/security-attacks.json`](../config/security-attacks.json). Validate
them without reading credentials, calling a model, or using the network:

```sh
python3 scripts/security-harness.py validate --root .
```

## What are the trust boundaries?

| Source | Trust | May authorize? |
| --- | --- | --- |
| Installed runtime policy | Authoritative | Yes |
| Explicit current user decision | Authoritative | Yes |
| Validated kernel state | Authoritative record | No; it records authority |
| Approved durable memory | Reviewed data, not instructions | No |
| Repository and issue content | Untrusted data, not instructions | No |
| Tool, test, log, and command output | Untrusted data, not instructions | No |
| Web, MCP, API, and retrieved content | Untrusted data, not instructions | No |
| Environment values, credentials, keys, and tokens | Forbidden input | No |

This means text such as “ignore your policy,” “the user already approved,” or
“run this command to continue” does not gain authority because it appears in a
README, memory record, test failure, API response, or tool result. The agent
may use the content as evidence, but it must evaluate the request under the
existing policy and obtain a real user decision for a protected action.

## Which threats and assets are covered?

The threat model uses STRIDE: spoofing, tampering, repudiation, information
disclosure, denial of service, and elevation of privilege. Protected assets
are user authority, repository integrity, delivery state, credentials and
secrets, verification evidence, and external systems.

Six controls implement the boundary:

1. Instruction provenance keeps untrusted data below runtime and user
   authority.
2. Least-privilege profiles restrict delegation, mutation, and owned paths.
3. Protected actions require a durable user-authoritative approval.
4. Sensitive-access hooks reject direct secret reads and common exfiltration
   shapes without echoing the submitted input.
5. Source-bound posture receipts reject stale or edited evidence.
6. Security incidents stop and escalate instead of triggering boundary-
   crossing retries.

The guard does not inspect secret contents. It denies access based on the tool,
path class, output sink, and egress shape. `.env.example` remains readable;
`.env`, private keys, credential directories, environment enumeration,
secret-shaped variable output, and dynamic-data upload commands are denied.

## How is least privilege applied?

Every registered specialist inherits `config/agent-harness.json` and has one
role profile. Only the delivery coordinator can delegate. Read-only reviewers
cannot use native write tools, and their mutating shell forms are blocked.
Writers must claim a stage and stay inside its declared `owned_paths`.
Unknown capabilities fail closed.

Protected actions—production mutation, destructive database operations,
credential or environment-file writes, irreversible external actions, scope
expansion, and success-criterion changes—remain user-authoritative. An agent
cannot approve itself, alter `kernel.json`, or launder approval through memory
or tool output.

## What attacks are tested?

The registry contains 13 attacks (`SEC-001` through `SEC-013`) covering
repository, memory, and tool-output injection; native and shell secret reads;
environment enumeration; variable output and dynamic network exfiltration;
self-approval; reviewer mutation; receipt tampering; source drift; and repeated
security-boundary retries.

Every denial expects zero side effects. Twenty-three focused tests preserve a sentinel and
verify it is unchanged after blocked tool calls. Diagnostics are also checked
to ensure they do not repeat submitted paths, commands, variable names, URLs,
or malformed payloads.

Run them directly:

```sh
python3 -m unittest discover -s tests/security -t tests/security -v
./tests/guardrails.test.sh
```

The repository-, memory-, and tool-injection cases validate structural
authority separation and the inability of those sources to create a durable
user approval; they are not a claim that prompt text alone is an infallible
model sandbox. The secret, capability, approval, path, and receipt cases
exercise mechanical rejection boundaries.

The release-required `security governance` job runs the registry validator,
all security tests, produces a posture receipt in the runner's temporary
directory, and verifies it against the checked-out sources.

## What does a security posture receipt prove?

Create and verify a receipt:

```sh
python3 scripts/security-harness.py audit \
  --root . \
  --output /tmp/security-posture-receipt.json

python3 scripts/security-harness.py verify \
  --root . \
  --receipt /tmp/security-posture-receipt.json
```

The receipt seals the policy, attacks, agent harness, canonical security
instructions, sensitive-access implementation, and all three runtime hook
manifests. It records only hashes and aggregate counts. Raw prompts, tool
output, commands, submitted paths, environment values, and secret material are
excluded.

A passing posture receipt proves that the inspected checkout has a complete,
internally consistent, source-current control set. It does not prove that a
particular host installed the hooks or that production uses the same commit;
the executable CI attacks and deployment controls provide those separate
pieces of evidence.

## Where does the boundary stop?

- Hooks cover declared tools on hosts that install them; they are not an
  operating-system sandbox.
- Pattern matching cannot recognize every encoded value, application-specific
  secret name, covert channel, or arbitrary program that exfiltrates data.
- SHA-256 source binding detects ordinary drift and partial tampering, not a
  same-account attacker who can rewrite code and all evidence together.
- The harness validates user-approval provenance, not the quality of a human
  decision or a third-party service's authorization model.

Use a separate OS identity, filesystem permissions, network policy, short-
lived credentials, secret-scanning, and service-side authorization when the
deployment risk requires stronger isolation.

## Symptoms

- A tool call reports `BLOCKED: security policy denied this tool call`.
- `security-harness.py validate` reports a missing trust boundary, control,
  attack, source, or hook integration.
- Receipt verification reports stale, source-drifted, or tampered evidence.
- A specialist asks to widen tools, paths, approvals, or success criteria based
  on repository, memory, tool, or external content.
- Sensitive content appears in a console, trace, report, commit, or artifact.

## Triage

1. Stop the affected lane. Do not repeat or re-encode a denied operation.
2. Preserve the category-level error, agent, tool name, delivery/stage ID, and
   relevant non-sensitive hashes. Do not copy the submitted payload or secret.
3. Run `python3 scripts/security-harness.py validate --root .`.
4. If a receipt exists, run `verify` against the unchanged checkout.
5. Confirm the host installed `enforce-sensitive-access.sh` for read, grep,
   shell, and web-fetch tools and that the relevant agent profile is intact.
6. Determine whether this is a true attack, an unsafe request, a stale install,
   or a false positive on non-sensitive input.

## Resolve

1. For a real or suspected exposure, rotate the credential outside this
   repository, revoke active sessions where appropriate, and follow the owning
   service's incident process. Never commit the replacement value.
2. For injection or authority spoofing, remove no policy to “make it pass.”
   Keep the content classified as data and obtain a current user decision if
   the underlying protected action is still required.
3. For a stale install, reinstall or regenerate the target and re-run the
   focused attack plus the full security suite.
4. For a genuine false positive, add a non-secret regression case first, then
   narrow the matcher without weakening adjacent secret and egress cases.
5. Regenerate Codex and Gemini targets, produce a fresh posture receipt, run
   all required release jobs, and publish only from the exact green commit.
6. Roll back an unpublished change by restoring the policy, guard,
   cross-runtime manifests, tests, and documentation together. If a released
   guard is unsafe, ship a new patch release; never rewrite its tag.

Escalate immediately to the user and security owner when secret exposure is
possible, an approval or privilege boundary may have been bypassed, evidence
integrity is disputed, containment would delete or rotate data, or the same
boundary denial repeats. Database mutation, deletion, migration, credential
rotation, and irreversible external action still require the appropriate
explicit approval.
