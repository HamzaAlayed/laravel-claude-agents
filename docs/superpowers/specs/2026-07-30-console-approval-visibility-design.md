# Design — closing the console's approval-visibility hole

**Goal:** make the Guild web console's central promise true for Bash — that a
human is asked before a Bash command runs — and tell the truth about every other
tool call. Closes item 1 of
[the v1.27.0 follow-ups](../../plans/2026-07-30-console-followups.md).

**Non-goal:** asking about every tool call (a routine run would park 30+ times);
a configurable strictness toggle; fixing the prompt→lane attribution heuristic
(item 4 — see [What this does not fix](#what-this-does-not-fix)).

---

## The hole

`can_use_tool` is not the first gate. Claude Code auto-allows some Bash calls
*before* the callback runs, so no `prompt` event is emitted and the browser is
never asked. Measured during v1.27.0: `echo hello` produced `tool_use` →
`tool_result` with zero `prompt` events, while `mkdir -p /tmp/…` prompted
normally.

Two causes, one already fixed:

- **Sandboxed commands** (`SANDBOX_AUTO_ALLOW_REASON`) — fixed in v1.27.0;
  `sdk_client_factory` sets `sandbox={"autoAllowBashIfSandboxed": False}` and a
  guardrail ratchet pins it.
- **Read-only commands** (`READ_ONLY_AUTO_ALLOW_REASON`) — **not** fixable by any
  SDK option or settings key. This spec.

Containment was never affected: hooks outrank every permission mode, so all five
guardrails fire on an auto-approved call. Visibility is what is affected.

## Verified platform facts

Checked against the installed SDK (`claude_agent_sdk` 0.2.128) on 2026-07-30,
reading its own source rather than the published docs.

- **A `PreToolUse` hook is the documented answer.** The SDK's own shadowing
  warning says so in as many words: *"To gate every tool call, use a PreToolUse
  hook instead."* (`types.py:1706`, `types.py:1723`)
- **The hook can force the ask.** `PreToolUseHookSpecificOutput` accepts
  `permissionDecision: "allow" | "deny" | "ask" | "defer"` plus a
  `permissionDecisionReason` (`types.py:413`).
- **The reason reaches the browser's decision.** When a hook returns `"ask"` with
  a reason, that reason is forwarded to `ToolPermissionContext.decision_reason`
  — i.e. into the same `can_use_tool` call the console already turns into a
  `prompt` event (`types.py:218`).
- **The hook input identifies the call exactly.** `PreToolUseHookInput` carries
  `tool_name`, `tool_input`, and a **required** `tool_use_id`, plus optional
  `agent_id` / `agent_type` (`types.py:309`).
- **Callback shape:** `async (input, tool_use_id, context) -> HookJSONOutput`,
  registered as `hooks={"PreToolUse": [HookMatcher(...)]}` on
  `ClaudeAgentOptions` (`types.py:574`, `types.py:1947`).
- **A hook `ask` outranks allow rules.** This is why it closes the hole — and why
  it breaks "Allow always"; see [Remembered
  signatures](#remembered-signatures).

## Policy

One rule, fixed in code. No toggle, no config surface, no API field.

| tool | hook returns | effect |
|---|---|---|
| `Bash` | `permissionDecision: "ask"` | routes to `can_use_tool` → existing `prompt` event → the browser asks |
| everything else | `{}` (no decision) | falls through untouched; permission rules and mode decide as before |

Bash is the whole of the remaining hole and the only tool that can do damage.
`Read` / `Grep` / `Glob` auto-allowing is not a safety story worth parking a run
for.

**Accepted cost:** every `ls`, `git status`, and `php -v` now parks the run until
answered. This is the price of the promise, chosen deliberately.

## Architecture

`engine.py` gains `_make_pre_tool_use(run)`, mirroring the existing
`_make_can_use_tool(run)`. `serve.py` pops it from the options dict — exactly as
it already pops `can_use_tool` — and wraps it in a `HookMatcher`.

That split is deliberate and matches the existing discipline: **`engine.py` never
imports `claude_agent_sdk`**, so the whole policy stays unit-testable with plain
dicts and no SDK installed.

```
engine.start()
  options["pre_tool_use"] = self._make_pre_tool_use(run)

serve.sdk_client_factory(options)
  hook = options.pop("pre_tool_use")
  ClaudeAgentOptions(..., hooks={"PreToolUse": [HookMatcher(hooks=[wrapped])]})
```

One matcher covering all tools, with the policy as one constant and one branch
inside the callback — not two matchers. The policy is then readable in one place
and provable in one test.

### The `tool_gate` event

Every call emits one event through the existing `_publish`, so it reaches the
buffer, the run jsonl, and SSE with a correct `seq` like every other event. No
new transport, no IPC.

```json
{"type": "tool_gate", "tool": "Read", "tool_use_id": "toolu_…",
 "agent": "backend-developer", "asked": false}
```

`asked` is true when the hook forced the ask, false when the call fell through.
This is what lets the transcript stop implying that every call was approved.

### Remembered signatures

Because a hook `ask` outranks allow rules, "Allow always" would become inert for
Bash: it persists a localSettings rule, then the hook asks anyway on the next
matching call. A button that quietly lies is worse than no button.

So the run keeps a set of remembered signatures:

```
answer(payload with remember: true)
  -> run.remembered.add(("Bash", <exact command string>))

hook(Bash, command)
  -> ("Bash", command) in run.remembered  ->  {}          # falls through
  -> otherwise                            ->  ask
```

Per-run and in-memory: "Allow always" means *stop asking me for the rest of this
run*. The existing localSettings persistence is unchanged and still applies to
future sessions; this only stops the hook from overriding it within the run.

The signature is `("Bash", tool_input["command"])` — an exact string match, not a
pattern, and only ever recorded for Bash, because Bash is the only tool the hook
forces. A signature scheme cleverer than the user's expectation is a way to
auto-approve something they did not mean to approve.

A remembered call therefore reports `tool_gate {asked: false}` and counts toward
the lane's "ran unasked" line. That is intended: the user chose not to be asked,
and the transcript should still say the call was not asked about.

### UI

The reducer counts `tool_gate` events with `asked: false` per lane; `AgentCard`
shows a quiet `N ran unasked` line. No new screen, no new interaction. The
approval path itself is untouched — forced asks arrive as ordinary `prompt`
events and render in the sheet that already exists.

This changes the bundle, so `scripts/console/dist` legitimately churns in this
change (unlike the test-only commit before it, which was byte-identical).

## What this does not fix

**Item 4, prompt→lane attribution.** The hook carries `tool_use_id`, which is
what `lane_by_tool_use` keys on — but the hook fires *earlier* than
`can_use_tool`, so the `MISSING` branch (and its newest-open-lane heuristic) gets
hit more often, not less. `agent_id` would fix attribution properly, but mapping
ids to lanes needs `SubagentStart` hooks; that is its own change and stays open.

**Non-Bash auto-allows.** A tool allowed by a settings rule still runs without an
ask. It is now visible as `tool_gate {asked: false}` rather than silent, which is
the whole of what this promises for those tools.

## Testing

Python first, TDD, in `tests/console/test_engine.py` — all with plain dicts, no
SDK:

1. Bash returns `permissionDecision: "ask"` with a reason.
2. `Read` returns no decision.
3. `tool_gate` is published for both, with `asked` true/false respectively, and
   correct `tool_use_id` and lane attribution.
4. A remembered signature makes Bash fall through.
5. A *different* command with the same tool still asks.

Then `console-ui`: a reducer test for the per-lane count, and one mount test that
the badge appears. Plus a guardrail ratchet pinning that the `PreToolUse` hook is
registered, mirroring how `autoAllowBashIfSandboxed: False` is pinned — a
refactor must not be able to silently drop the gate.

Verification must include a real run, not a green suite: the two worst defects on
this branch both passed their unit tests. The check is that `echo hello` now
parks the run and shows a decision in the browser.

## Docs to correct

- `commands/console.md` — the third user-facing bullet currently states that
  read-only Bash never reaches the browser. That becomes **false** and must be
  rewritten, including what "Allow always" now means for Bash.
- `docs/superpowers/specs/2026-07-29-guild-web-console-design.md` — the
  read-only entry in its failure-mode table (line ~119).
- `docs/plans/2026-07-30-console-followups.md` — item 1 resolved, with the
  attribution caveat above recorded rather than dropped.
