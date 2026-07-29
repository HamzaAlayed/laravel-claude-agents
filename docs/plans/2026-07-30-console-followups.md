# Console follow-ups — held after v1.27.0

Everything below was found during the build of the Guild web console
([spec](../superpowers/specs/2026-07-29-guild-web-console-design.md),
[plan](../superpowers/plans/2026-07-29-guild-web-console.md)) and deliberately **not** fixed in that
branch. Nothing here blocks the console from working; the branch shipped with 85 python tests, 37
frontend tests, 101 guardrail tests, and a verified end-to-end run.

Ordered by what I'd do first.

---

## 1. Approval visibility has a permanent hole (documented, partly unfixable)

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

## 2. The UI has never been exercised by a test

~480 lines of React have never been mounted. `jsdom` is configured but unused; the 37 frontend tests
cover pure functions only (`reducer`, `buildAnswers`/`mergeFreeText`, `submitGate`). The smoke test ran
no JS at all.

Specifically untested: the `disabled` plumbing on the decision sheet, the interrupt path's
`finally { setStopped(true) }`, the follow-up composer, and the whole board render. A reviewer did
confirm in a real browser that the page renders, `/api/catalog` returns 200, there are no console
errors, and the no-token path degrades cleanly — but every interactive path is unverified.

**Fix:** add `@testing-library/react` and mount the four flows that can strand a user — parked
approval, queued approvals, run error, interrupt.

## 3. `SSE resume` doesn't do what the spec says

The spec's failure-mode table promises "the server replays from the run jsonl". It replays from
`run.buffer` **in memory**. Reconnecting mid-run works; reconnecting after a console restart silently
returns nothing. Either implement the jsonl replay or amend the spec.

## 4. Prompt→agent attribution can name the wrong agent

`engine.py` attributes a prompt to a lane via `context.tool_use_id` (exact), then falls back to the
newest still-open lane (heuristic). With two lanes open the heuristic can flag the wrong card, and the
confidence level never reaches the browser. It did not fire in any observed run.

**Fix:** send the attribution confidence in the `prompt` event and have the bar say "possibly" when it
is a guess.

## 5. Missing escape hatches

- `api.setMode` is wired server-side and tested, but nothing in the UI calls it — there is no mid-run
  permission-mode switch, so the spec's "either can be changed mid-run" is only true over the API.
- There is no server-side *abandon* route. Interrupt is the only exit, and it kills the turn.
- A `connect()` failure emits no `error` event at all; the UI only recovers via the interrupt path.

## 6. Guardrail ratchets grep raw file content

The console ratchets match raw bytes with no code/comment distinction. `grep -c '0\.0\.0\.0'`
expecting 0 means a future comment like `# never bind 0.0.0.0` reddens the build. Two docstrings in
`engine.py` already mention `claude_agent_sdk` for exactly that kind of reason. Restrict to
non-comment lines.

## 7. Small CI and hygiene items

- `console-ui` job runs `npx tsc --noEmit` explicitly and again inside `npm run build`. Drop one.
- **Bundle determinism risk, unverified:** CI pins node 22; the committed bundle was built on node
  26.5.0. `vite`/`rollup`/`esbuild` are pinned by `package-lock`, so output *should* be identical. If
  the `dist/` staleness gate fails on the first CI run, pin CI's node to match rather than
  rebuild-and-commit blindly.
- `.cursor-plugin/marketplace.json` has been stuck at version `1.17.0` for 10+ releases —
  pre-existing, unrelated to the console. All five other manifests read 1.27.0 and
  `check_inventory_sync` passes, because it never checks marketplace versions.
- `install_console` copies `__pycache__` into installs.
- `~24` further Minors are itemised in the branch's final review (non-constant-time token comparison,
  undrained request body on 401, raw SDK message duplicated on every event line, same-slug lanes
  double-receiving events, the coordinator rendered as a card).

## 8. Local scratch to clear

- `.playwright-mcp/` — untracked, 3 files, left by the reviewer's browser check. `rm -rf` was
  permission-denied for the agents.
- `tests/fixture-app/.claude/console/venv` — ~300MB, gitignored, created by the smoke test.

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
