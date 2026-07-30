# Console follow-ups — held after v1.27.0

Everything below was found during the build of the Guild web console
([spec](../superpowers/specs/2026-07-29-guild-web-console-design.md),
[plan](../superpowers/plans/2026-07-29-guild-web-console.md)) and deliberately **not** fixed in that
branch. Nothing here blocked the console from working; the branch shipped with 85 python tests, 37
frontend tests, 101 guardrail tests, and a verified end-to-end run.

**Worked off on 2026-07-30.** Items 1–7 are done or resolved; the suites now stand at 98 python, 77
frontend, 103 guardrail. Every fix was mutation-verified — each new test was watched failing against a
deliberately broken version of the behaviour it claims to protect, because tests written against code
that already exists prove nothing by passing.

**Item 1's end-to-end check has now been run** — the one measurement that matters, against a real SDK
run over the real HTTP/SSE API (same method as
[the smoke test](../evals/2026-07-30-console-smoke.md)). `echo hello`, the exact command that used to
produce `tool_use` → `tool_result` with **zero** `prompt` events:

```
init → tool_use Bash → tool_gate Bash asked=True → prompt Bash
     → (answered allow) → prompt_resolved → tool_result → text → result

prompt input: {"command": "echo hello", "description": "Echo hello"}
agent=None  agent_confidence='exact'
```

One `tool_gate`, `asked=True`, and a `prompt` the browser answered. Item 4's confidence field is
visible in the same trace, on the main-thread path where `None` is a fact rather than a guess.

Still open, and each one says so in place:

- **Item 5's abandon route** — not built, on purpose. See the reasoning there.
- **Item 7's node-22 bundle reproducibility**, and the ~24 minors from the branch's final review, which
  this doc does not reproduce.
- **Item 8** — needs a `rm -rf` no agent is permitted to run.

Ordered by what I'd do first, not by what is left.

---

## 1. ~~Approval visibility has a permanent hole~~ — CLOSED 2026-07-30

Fixed as specced in
[the design](../superpowers/specs/2026-07-30-console-approval-visibility-design.md).
A `PreToolUse` hook — registered in-process from `engine.py`, wrapped into a
`HookMatcher` by `serve.py`, so no shell script and no IPC — returns
`permissionDecision: "ask"` for Bash. That routes the call back through
`can_use_tool`, which already emits the `prompt` event the browser answers, so
the entire approval path is reused. Every call also publishes a `tool_gate` event
carrying `asked`, and the UI shows `N ran unasked` per lane and for the main
thread.

`ASK_ALWAYS_TOOLS` is Bash alone: read-only Bash was the whole of the hole and
Bash is the only tool there that can do damage. **Accepted cost:** every `ls` and
`git status` now parks the run.

"Allow always" needed rescuing along the way — a hook `ask` outranks allow rules,
so the persisted settings rule would have been overridden on the very next call.
The run now remembers exact `(Bash, command)` signatures and the hook falls
through for them.

Two guardrail ratchets pin the registration and the Bash policy; both were
confirmed to fail when the gate is removed. 9 engine tests, 8 UI tests.

**Not fixed, and not claimed to be:** item 4 below. The hook fires *earlier* than
`can_use_tool`, so the `MISSING` attribution branch gets hit more often, not less.

<details>
<summary>Original finding</summary>


`can_use_tool` is not the first gate. Claude Code auto-allows some Bash calls before the callback runs,
so **no `prompt` event is emitted and the browser is never asked**:

- **Read-only commands** (`READ_ONLY_AUTO_ALLOW_REASON`). Measured: `echo hello` produced
  `tool_use` → `tool_result` with zero `prompt` events, while `mkdir -p /tmp/…` prompted normally.
  **No SDK option or settings key disables this.** Only a `PreToolUse` hook sees every call.
- **Sandboxed commands** (`SANDBOX_AUTO_ALLOW_REASON`). This one *is* configurable;
  `sdk_client_factory` now sets `sandbox={"autoAllowBashIfSandboxed": False}` and a ratchet pins it.

Containment is unaffected — hooks outrank every permission mode, so all five guardrails still fire on
an auto-approved call. **Visibility** is what's affected, and the spec and `commands/console.md` now
say so plainly.

**Option if you want the promise back in full:** ship a `PreToolUse` hook that emits a console event
for every tool call. That is the only layer that sees all of them.

</details>

## 2. ~~The UI has never been exercised by a test~~ — DONE 2026-07-30

22 mount tests now drive a real `<App />` (`console-ui/src/App.test.tsx`); the suite is 37 → 59.
`fetch` and `EventSource` are faked at the transport boundary (`src/test/fakeServer.ts`) rather than
mocking `lib/api`, so `api`, `reducer`, `submitGate` and every component stay on the real path — the
lesson from the two defects at the bottom of this file.

Covered: the `disabled` plumbing (a held POST proves one double-click cannot resolve two decisions,
and that the gate re-arms after the answer lands), the interrupt path's `finally { setStopped(true) }`
via a failing interrupt, an errored run freeing the Launcher, the follow-up composer both ways, the
board's parked-card marking, and the Other field reaching the wire through the real sheet.

Because the tests were written against code that already existed, passing proved nothing on its own —
each was verified by mutation. Six behaviours were broken one at a time; every one was caught by the
test that should catch it, and only by tests in its own area:

| mutation | caught by |
|---|---|
| sheet buttons never disabled | double-click cannot resolve two decisions |
| `setStopped` moved out of the interrupt's `finally` | failed interrupt is still an ended run |
| `isRunOver` ignores `failure` | errored run ends and frees the Launcher |
| `pending` back to a single slot | 4 queue + question tests |
| free text not merged into answers | typed answer beats the clicked option |
| a prompt no longer opens the sheet | 12 tests |

Two things surfaced while doing it, both now handled:

- **Tailwind was scanning the test files.** Its scanner reads raw bytes, so `static instances` in the
  fake `EventSource` and a comment about content being "hidden" added `.static` and `.hidden` to the
  *shipped* stylesheet — 45 bytes that changed the bundle hash and would have failed CI's
  bundle-in-sync gate for reasons no reviewer could have seen in the diff. `src/index.css` now carries
  `@source not` for `*.test.ts(x)` and `src/test/`, and the rebuilt `dist/` is byte-identical to the
  committed one. Same shape as item 6 — a raw-content scan with no code/comment distinction.
- **A failed answer closes the sheet** while correctly putting the prompt back in the queue. Not a
  strand (the sticky bar still names the agent and `Review` reopens the same decision, re-armed) so
  the behaviour is now pinned by a test rather than changed.

**Still not covered:** anything needing layout or real animation timing (the approval bar's exit is
waited out, not asserted), `Transcript` internals, and the `select`-driven Launcher paths for
command/specialist runs.

## 3. ~~`SSE resume` doesn't do what the spec says~~ — RESOLVED 2026-07-30 (spec amended)

The spec was wrong, not the code. Amended, with the reasoning recorded in the spec's failure-mode
section: replay from the jsonl *does* exist as `GET /api/runs/{id}` (`snapshot()`), and streaming a
dead run's history over SSE and then closing would reintroduce the EventSource retry loop the 404 was
introduced to avoid. The two paths stay separate deliberately.

What was a real bug is that the browser ignored the 404 completely — the page just stopped updating
with the Launcher still disabled behind a run nobody was watching. `api.streamRun` now reports a
stream that reaches `CLOSED`, distinguished from a transient retry (`CONNECTING`), and the console says
so and frees itself. 2 tests, both mutation-verified.

## 4. ~~Prompt→agent attribution can name the wrong agent~~ — DONE 2026-07-30

`_agent_for_prompt` now returns `(agent, confidence)` and both `prompt` and `prompt_resolved` carry
`agent_confidence`. `"exact"` means `tool_use_id` resolved the lane, or `agent_id` was `None` — which
is knowledge (no subagent asked), not absence of it. `"guess"` is the newest-open-lane fallback.

The bar says "Possibly Adam needs approval — Bash" for a guess, and the board marks **no** card,
keeping its promise that a marked card is really the blocked one. A missing `agent_confidence` reads
as exact, so older jsonl replays render unchanged. 3 engine tests, 4 frontend, all
mutation-verified.

<details>
<summary>Original finding</summary>

`engine.py` attributes a prompt to a lane via `context.tool_use_id` (exact), then falls back to the
newest still-open lane (heuristic). With two lanes open the heuristic can flag the wrong card, and the
confidence level never reaches the browser. It did not fire in any observed run.

**Fix:** send the attribution confidence in the `prompt` event and have the bar say "possibly" when it
is a guess.

</details>

## 5. Missing escape hatches — two done, one deliberately not

- ~~`api.setMode` is wired server-side and tested, but nothing in the UI calls it~~ — **done.** A mode
  select sits in the header while a run is live. Optimistic, and reverted if the API refuses, so it
  never shows a mode the run is not on. The spec's "either can be changed mid-run" is now true of the
  UI too. (`model` still has no control — one lever was the promise, and a model switch mid-run has no
  obvious use here.)
- ~~A `connect()` failure emits no `error` event at all~~ — **done.** `_boot` publishes the `error`
  event and marks the run finished, then re-raises so `POST /api/runs` still answers 400 with the
  reason. Previously the run stayed registered as `running` forever with nothing on its stream.
- **No server-side abandon route — not done, on purpose.** Interrupt is the only exit and it kills the
  turn, which is the honest thing to do: an "abandon" that leaves the SDK client connected and billing
  is the zombie-run bug of v1.27.0 by another name. There is also no run-picker UI, so a detached run
  would be unreachable. Revisit if a run list ever lands.

## 6. ~~Guardrail ratchets grep raw file content~~ — DONE 2026-07-30

`console_hits()` drops comment-only lines (`//`, `*`, `/*`, `#`). A trailing comment after real code
still counts — a security ratchet must fail closed, so over-strict beats under-strict. The
`path:line:` prefix is stripped by position, not by regex, so a URL's `//` inside matched text cannot
hide a real hit. Verified both ways on fixtures, for both comment styles.

## 7. Small CI and hygiene items — mostly DONE 2026-07-30

- ~~`console-ui` job runs `npx tsc --noEmit` explicitly and again inside `npm run build`. Drop one.~~
  **Done** — the explicit one is gone; `npm run build` still typechecks before it bundles, so the gate
  is unchanged.
- ~~`.cursor-plugin/marketplace.json` stuck at `1.17.0`~~ — **done**, now `1.27.0`, and
  `check_inventory_sync.py` fails the build if any manifest's declared version drifts from `VERSION`.
  The check walks the JSON for `version` at any depth, because `plugin.json` declares it at the top
  level while `marketplace.json` nests it under `plugins[]` — and a check that only looked where it
  expected the field is how this drifted for ten releases. Verified by putting `1.17.0` back and
  watching it fail.
- ~~`install_console` copies `__pycache__` into installs~~ — **done.** This checkout carries one today,
  so it was really shipping. The selector was verified to match only `__pycache__` directories, at any
  depth, and nothing else.
- **Bundle determinism, half verified (2026-07-30):** a clean-room worktree at `HEAD`, `npm ci` from
  the committed lockfile, reproduces the committed bundle *byte-for-byte* on node 26.5.0 — so the
  committed `dist/` is genuinely in sync with the committed source, and the gate is not already red.
  **CI's node 22 is still unverified** (the docker run to check it was not permitted); if the gate
  fails on the first CI run, pin CI's node rather than rebuild-and-commit blindly.
  Worth knowing before debugging that gate: the entry chunk's hash covers the CSS asset it imports, so
  a Tailwind-only change renames `index-*.js` while its bytes are identical. A changed JS filename is
  therefore not evidence that any JS changed.
- `.cursor-plugin/marketplace.json` has been stuck at version `1.17.0` for 10+ releases —
  pre-existing, unrelated to the console. All five other manifests read 1.27.0 and
  `check_inventory_sync` passes, because it never checks marketplace versions.
- `install_console` copies `__pycache__` into installs.
- `~24` further Minors are itemised in the branch's final review (non-constant-time token comparison,
  undrained request body on 401, raw SDK message duplicated on every event line, same-slug lanes
  double-receiving events, the coordinator rendered as a card).

## 8. Local scratch to clear — needs a human hand

- `.playwright-mcp/` — untracked, 3 files (a 401 console log and two page snapshots from the
  reviewer's no-token check). Still there: `rm -rf` is permission-denied for the agents, main thread
  included. Run `rm -rf .playwright-mcp` to clear it. It is gitignored now, so it cannot be committed
  by accident. Its content is fully superseded by the mount test
  `degrades to a readable message when the API cannot be reached`.
- `tests/fixture-app/.claude/console/venv` — 297MB, gitignored, created by the smoke test.
  **Deliberately left**: it is regenerable, but only by reinstalling `claude-agent-sdk`, and it is what
  makes the real-SDK checks in this branch runnable offline. Delete it when disk matters more than the
  next smoke test's start-up time.

---

## Process lesson worth keeping

Ten defects were found in the implementation plan itself, and the two worst shared a shape: **the tests
agreed with the code because the same author wrote both against the same wrong assumption.**

- The console emitted **zero events** while 62/62 tests passed — `events.normalize` was written for the
  CLI's stream-json wire format, but the Python SDK yields typed dataclasses with no `type` field.
- `RunView.pending` was a single slot while the engine held a dict, so two parallel approvals silently
  lost one — parked forever, unnameable in the UI.

Neither was caught by review of the plan, or by the unit suite. Both were caught by *running the thing*
— the smoke test and a reviewer who traced a concurrent scenario. Budget for end-to-end verification
before believing a green suite, and prefer tests whose fixtures come from the real dependency over
tests whose fixtures come from the spec.
