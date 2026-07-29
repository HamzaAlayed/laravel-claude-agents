# Console smoke test — API-level, no browser (2026-07-30)

Task 11 of the guild-web-console plan, run against `feat/guild-web-console`
(server at commit `131f99b`, which fixed the critical `_as_dict` defect a
prior attempt at this task uncovered — the console previously produced zero
events because SDK message objects were never translated into the wire format
`events.normalize()` reads).

**This run had no human available to click Allow/Deny in a browser.** Every
scenario below was driven directly over the HTTP/SSE API with `curl` and small
Python scripts (`urllib`, no dependencies) instead. That adaptation was
pre-authorized. Nothing here should be read as a browser end-to-end pass —
see section (c) for what a browser pass would additionally have to cover.

Server: `cd tests/fixture-app && python3 -u ../../scripts/console/serve.py --port 8392 --no-open`,
backgrounded. Token captured from the startup banner (see the timing note
under Defects). All 8 launched runs used the real Claude Agent SDK against
the real Anthropic API (model `claude-opus-5[1m]`) — real money was spent:
**7 paid runs, ≈ $1.29 total** (`run_bccafad50198` $0.1701, `run_4bab05d76191`
$0.1754, `run_9feb32cef88a` $0.1717, `run_37f4cc4927be` $0.1680,
`run_7aeb0044c713` $0.1712, `run_0d7af808afbb` $0.1612, `run_51d275b9a0c7`
$0.2678). Server killed at the end; `.claude/console/venv` left in place.

## (a) What got REAL end-to-end coverage

- The full launch → SDK connect → model turn → tool call → permission park →
  HTTP answer → resume → real tool execution → transcript pipeline, for both
  **allow** (a file was actually written to `/tmp` and its contents verified
  outside the run) and **deny** (the model's next message genuinely
  acknowledged the refusal instead of retrying).
- A genuine **race**: two real concurrent HTTP POSTs to `/api/runs/<id>/answer`
  for the same `prompt_id`, fired from two threads with a barrier so they hit
  the engine as close to simultaneously as possible. Exactly one landed (200),
  the other got 409.
- A genuine **interrupt** against a live, connected SDK client with a prompt
  actually pending — not a fixture. Round-trip timed at 85 ms; no hang.
- A genuine **specialist/subagent dispatch** (`qa-engineer`, via the real
  `Agent`/`Task` tool), producing real `agent_start`/`agent_end` events around
  a real nested subagent turn.
- A genuine **dropped-and-resumed SSE connection** mid-run: connection 1 was
  killed by `timeout` after 7 events while the run was still in flight
  (mid-subagent-dispatch), connection 2 reconnected with `?since=7` while the
  run kept going, and the two connections' events concatenate to exactly the
  full, contiguous 1–9 sequence with no duplicates and no gaps.
- The security guard (401/403/200 origin and token checks) against the actual
  running `http.server` instance, not a mock.
- Direct, isolated execution of `scripts/block-prod-artisan.sh` with synthetic
  PreToolUse JSON on stdin, to determine its exact blocking boundary (see
  Defect 3) — this is real hook code, just invoked directly rather than via a
  live tool call.

## (b) What got API-LEVEL-ONLY coverage

Everything above was driven through `/api/*` and the SSE stream directly;
none of it went through the console's own HTTP client code, its event
reducers/store, or its rendering — only the server side of the contract was
exercised. Specifically API-level-only:

- Every scenario's request/response shape and every event's field names —
  verified by direct JSON inspection, never by the UI parsing them.
- The run list (`GET /api/runs`) — verified as raw JSON, not as rendered rows.
- The catalog endpoint — verified as raw JSON (agent/command/skill counts and
  the `stages` array), never rendered into a board or picker.

## (c) What is NOT covered at all

An API-only test cannot exercise, and none of the following were touched in
any way this run:

- Browser rendering of anything — the board, the focus-mode lane, the
  decision sheet, the amber "needs you" bar.
- Motion/animation, including whether `prefers-reduced-motion` is honored.
- The decision sheet's own UI (the human-facing Allow/Deny card) — only its
  server-side counterpart (the `prompt` event and the `/answer` endpoint)
  was exercised.
- Keyboard navigation of any kind.
- The pipeline board's visual layout, column assignment rendering, or lane
  promotion from focus mode to board mode.
- Anything client-side-only: no JS ran, no CSS was loaded, no accessibility
  tree was inspected.

## (d) Scenario-by-scenario results

| # | Scenario | Verdict | Notes |
|---|----------|---------|-------|
| 1 | Catalog | **PASS** | |
| 2 | Security | **PASS** | |
| 3 | Parked approval → allow | **PASS (adapted)** | literal prompt text did not park — see Defect 1 |
| 4 | Deny with a reason | **PASS (adapted)** | same caveat as #3 |
| 5 | Double-answer 409 | **PASS** | |
| 6 | Interrupt while parked | **PASS** | |
| 7 | Guardrail still bites | **IMPORTANT FINDING** | outcome held, but not via the hook — see Defect 3 |
| 8 | SSE resume | **PASS** | |
| 9 | Run list | **PASS, with a caveat** | see Defect 5 |
| 10 | Agent lane | **PASS** | |

### 1. CATALOG — PASS

`GET /api/catalog` with the correct token: HTTP 200,
`{"agents": 17 items, "commands": 13 items, "skills": 8 items, "stages": ["Discover", "Design", "Build", "Review", "Test", "Ship", "Docs", "Working"]}`.

### 2. SECURITY (free) — PASS

| Check | Result |
|---|---|
| No token | 401 |
| Wrong token, header | 401 |
| Wrong token, `?token=` query | 401 |
| `Origin: https://evil.example` + valid token | 403, body `{"error": "cross-origin requests are refused"}` |
| `Origin: http://localhost:8392` + valid token | 200 |
| `Origin: http://127.0.0.1:8392` + valid token | 200 |
| `GET /api/runs/<id>/events`, no token | 401 |
| `GET /api/runs/<id>/events`, wrong token | 401 |

### 3. PARKED APPROVAL → ALLOW — PASS, adapted

Launched **exactly** the specified body —
`{"kind":"prompt","target":"","text":"Run the shell command \`echo hello\` and report its output.","mode":"default"}`
— and it did **not** park. `run_bccafad50198`'s events went
`init → thinking → tool_use(Bash) → tool_result → text → result` with **zero**
`prompt` events; the run finished normally, output `hello`, cost $0.1701. This
is a genuine, reproducible finding, not an implementation slip — see Defect 1.

To still exercise the park → allow → resume path the brief is actually
testing, I adapted the body to a tool call that cannot be silently
auto-approved (`Use the Write tool to create /tmp/guild_console_smoke_3.txt
containing exactly: hello-3`), launched as `run_4bab05d76191`:

- `tool_use(Write)` → `prompt` event (`prompt_id: p_50643d06db`) arrived at
  seq 4. Confirmed parked: re-fetching the run 3s later showed no new events
  and `GET /api/runs` reported `status: "running"` (not finished, not
  interrupted).
- `POST /api/runs/run_4bab05d76191/answer {"prompt_id":"p_50643d06db","behavior":"allow"}`
  → `200 {"ok": true}`.
- Run resumed: `prompt_resolved(allow)` → `tool_result` (file created) →
  final `text`/`result`. Confirmed outside the run:
  `/tmp/guild_console_smoke_3.txt` exists, contents `hello-3`.

### 4. DENY WITH A REASON — PASS, adapted

Same adaptation, fresh run (`run_9feb32cef88a`, file
`guild_console_smoke_4.txt`). Parked at `prompt_id: p_848312fe92`. Answered:
`{"prompt_id":"p_848312fe92","behavior":"deny","message":"Do not run shell commands; just explain."}`
→ 200.

- `prompt_resolved(deny)` → `tool_result` with `is_error: true`, content
  **exactly** `"Do not run shell commands; just explain."`
- The model's next message: *"The write was blocked — this session is
  configured to explain only, not to run tools that modify the filesystem. ...
  If you want it done, you can run it yourself: `echo 'hello-4' >
  /tmp/guild_console_smoke_4.txt`"* — a genuine acknowledgment, not a silent
  retry. Confirmed `/tmp/guild_console_smoke_4.txt` was never created.

### 5. DOUBLE-ANSWER 409 — PASS

Fresh run `run_7aeb0044c713`, parked at `prompt_id: p_4068514b38`. Fired two
POSTs to `/api/runs/<id>/answer` for the **same** `prompt_id`
(`behavior: allow` and `behavior: deny`) from two Python threads released by a
`threading.Barrier` so they hit the server as close to simultaneously as
possible:

```
allow_call: (409, {'error': 'prompt unknown or already answered'})
deny_call:  (200, {'ok': True})
```

Exactly one 200, one 409 — the invariant `RunManager.answer()`'s
non-suspending-coroutine design is supposed to guarantee. (An earlier,
separate attempt at this same test on `run_37f4cc4927be` accidentally
resolved via a single non-concurrent call before the race fired — not a
finding, just why that run doesn't appear as race evidence; a second run was
used for the actual concurrent test.)

### 6. INTERRUPT WHILE PARKED — PASS

The same `run_7aeb0044c713`, after the race above, self-retried its denied
Write and parked again at a new `prompt_id` (`p_cb7438b759`) — the synthetic
`"race loser"` deny message wasn't a realistic user correction, so the model
just tried again, which conveniently gave a second, real parked state to
interrupt without spending on a fresh run.

- Confirmed parked and live: `GET /api/runs` → `status: "running"`.
- `POST /api/runs/run_7aeb0044c713/interrupt {}` → 200, **85 ms** round trip.
- 2s later: `status: "interrupted"`. Events show `prompt_resolved(deny)` →
  `tool_result(is_error: true)` → `result(subtype: "error_during_execution")`
  landing within milliseconds of each other. No hang — the exact failure mode
  `_interrupt`'s deny-pending-first ordering exists to prevent did not occur.

Minor observation (not the hang failure mode, see Defect 4): the denied
prompt's `tool_result` content was the SDK's generic cancellation boilerplate,
not `_interrupt()`'s own `"Run interrupted by the user."` string.

### 7. GUARDRAIL STILL BITES — held, but not via the hook (IMPORTANT FINDING)

Launched exactly the specified body (`run_0d7af808afbb`). Result: the model
refused in its own first message —
*"I'm not going to run that. `php artisan migrate:fresh --force` against
production drops every table..."* — and **never called any tool**. Events:
`init → text → result`. No `tool_use`, no `prompt` event, no approval card of
any kind. In that narrow sense the requirement ("the console should never get
the chance to ask") held.

But this is not evidence the hook fired — a `PreToolUse` hook only runs when
a tool is actually invoked, and Bash was never invoked. I tested
`scripts/block-prod-artisan.sh` directly to find out what it would actually
have done:

```
$ echo '{"tool_input":{"command":"php artisan migrate:fresh --force --env=production"}}' \
  | ./scripts/block-prod-artisan.sh; echo "exit: $?"
blocked: destructive artisan command targeting production.
exit: 2

$ echo '{"tool_input":{"command":"php artisan migrate:fresh --force"}}' \
  | ./scripts/block-prod-artisan.sh; echo "exit: $?"
warn: 'migrate:fresh' / 'db:wipe' detected. confirm this is the local DB before proceeding.
exit: 0
```

The hard block requires the literal command string to contain
`--env=production` (or `prod`/`live`, or `APP_ENV=...`). The bare form a model
would most naturally type for "run migrate:fresh against the production
database" — since Laravel's production-ness is normally implicit in the
deployed `.env`, not a CLI flag — only trips the **soft warn** branch and is
**allowed through** to the normal permission flow. See Defect 3.

### 8. SSE RESUME — PASS

Combined with scenario 10 to avoid a second paid run. Connection 1
(`?since=0`) was cut by `timeout 5` after capturing seq 1–7 (mid-run, while
the qa-engineer subagent had been dispatched but hadn't returned). Connection
2 reconnected with `?since=7` and received exactly seq 8–9. Full snapshot via
`GET /api/runs/<id>` afterward: seqs `[1..9]`, contiguous, no gaps. Comparing
conn1 ∪ conn2 to the full snapshot: identical, no duplicates.

### 9. RUN LIST — PASS, with a caveat

`GET /api/runs` listed all 8 runs created this session plus one pre-existing
disk-derived run (`run_a9c74c35056e`, left over from the earlier `_as_dict`
fix verification, owned by a since-dead process on a different port) —
correctly reported `"interrupted"` since this process doesn't own it. The
run we explicitly interrupted (`run_7aeb0044c713`) correctly reports
`"interrupted"`. The one confirmed live/parked-mid-run (before we
interrupted it) correctly reported `"running"`, never `"interrupted"` — the
literal requirement.

Caveat, not a confirmed defect but worth the maintainer's attention: **every
run that completed its turn (reached a final `result` event) still reports
`status: "running"`, indefinitely** — none of the 6 completed runs in this
session ever showed `"finished"`, including one that finished several minutes
earlier. See Defect 5 for why, and whether it's intended.

### 10. AGENT LANE — PASS

`{"kind":"specialist","target":"qa-engineer","text":"In one sentence, say what you would test first. Do not read files.","mode":"default"}`
→ `run_51d275b9a0c7`. Events included `tool_use(Agent, subagent_type:
"laravel-team:qa-engineer")` → **`agent_start`** (`agent: "qa-engineer"`) →
subagent `text` events tagged `agent: "qa-engineer"` → `tool_result` →
**`agent_end`** (`agent: "qa-engineer"`, `is_error: false`). Real nested
subagent turn, real one-sentence answer, no file reads (as instructed).

## (e) Defects found

**1. (Important) A class of Bash tool calls silently bypasses `can_use_tool`
— no `prompt` event, no visible signal that a decision was auto-made.**
Repro: launch `{"kind":"prompt","text":"Run the shell command \`echo hello\` and report its output.","mode":"default"}`.
Observed events: `init → thinking → tool_use(Bash) → tool_result → text →
result` — no `prompt`/`prompt_resolved` pair at all, despite
`permission_mode: "default"` and a registered `can_use_tool` callback.
Investigated the installed `claude_agent_sdk` (0.2.128) source directly:
`types.py` defines `SandboxSettings.autoAllowBashIfSandboxed` ("Auto-approve
bash commands when sandboxed", default `True`) and a
`CanUseToolShadowedWarning` class whose docstring literally reads *"can_use_tool
is set but some tool calls are auto-approved before it runs."* This matches
what was observed. `scripts/console/serve.py`'s `sdk_client_factory()` sets
no `sandbox` option on `ClaudeAgentOptions`, so the console does not control
(and cannot distinguish, in its event stream) whether a given Bash call was
denied the callback because it was sandboxed-and-safe versus never attempted
at all. For a console whose entire purpose is visibility into permission
decisions, a class of decisions that never produces an event is worth a
deliberate call, not silent inheritance of an SDK default.

**2. (Informational — corrects the task brief's premise, per instruction to
"state it plainly") `init.plugins` resolves `laravel-team` to THIS working
tree, not the installed marketplace copy.** Checked the raw `system/init`
payload (not just the normalized `plugins: [name]` list) across four separate
runs (`run_bccafad50198`, `run_4bab05d76191`, `run_51d275b9a0c7`,
`run_0d7af808afbb`): every one shows
`{"name": "laravel-team", "path": "/Users/developer/Projects/Personal/laravel-claude-agents", "source": "laravel-team@inline", "version": "1.27.0"}`
— the branch's own working tree, not `.../laravel-team/1.26.0` from
`~/.claude/plugins/cache`. Reading `scripts/console/serve.py`'s `pack_root()`:
it checks `(PACK_ROOT / ".claude-plugin" / "plugin.json").is_file()` first,
where `PACK_ROOT` is always the repo root computed from `__file__`
regardless of cwd; that file exists on this branch (currently version
1.27.0, from the already-merged `b17ca05` release commit), so `pack_root()`
returns the working tree and never falls through to the marketplace-glob
fallback. **This contradicts the brief's assumption that the console runs
agents from the installed pack rather than the branch under test** — under
the current branch/commit state, it does not. Stating this plainly per
instruction, not fixing anything.

**3. (Important) `block-prod-artisan.sh`'s hard-block condition does not
cover the realistic phrasing of a production `migrate:fresh`.** See scenario
7 above for the exact repro (`echo '{"tool_input":{"command":"php artisan
migrate:fresh --force"}}' | ./scripts/block-prod-artisan.sh` → exit 0, warn
only). The hook requires a literal `--env=production`/`APP_ENV=production`
marker in the command string; Laravel projects don't typically pass
environment as a Bash-visible CLI flag, so the realistic dangerous invocation
would sail through to a soft warning and the normal permission flow. In this
run, Claude's own judgment was the actual, sole backstop — the hook was
never reached because no tool call was ever attempted. This is a real gap in
the guardrail's coverage, independent of the console.

**4. (Low) On interrupt, the pending prompt's denial message is generic SDK
boilerplate, not `RunManager._interrupt()`'s own `"Run interrupted by the
user."` string.** `_interrupt()` sets `future.set_result({"behavior": "deny",
"message": "Run interrupted by the user."})` before calling
`client.interrupt()`, but the transcript's `tool_result` content that follows
is *"The user doesn't want to proceed with this tool use... STOP what you are
doing..."* — the SDK/CLI's own generic cancellation text, not the custom
message. Purely cosmetic; the actual guarantee under test (no hang) held —
interrupt resolved in 85 ms.

**5. (Worth a decision, not confirmed a bug) `GET /api/runs` never reports
`"finished"` — status stays `"running"` indefinitely once a turn completes.**
All 6 runs in this session that reached a final `result` event (including one
finished several minutes prior) still reported `status: "running"` in the
last `GET /api/runs` of the session. Reading `engine.py`'s `_pump()`: it only
sets `run.status = "finished"` in a `finally` block that runs when the `async
for message in run.client.receive_messages()` loop itself exits — which,
for a persistent multi-turn `ClaudeSDKClient` (the console explicitly
supports sending more messages to the same run via `/message`), does not
happen just because one turn's `result` arrived; the connection is meant to
stay open for the next turn. So `"running"` may be intentional ("this run's
session is alive"), but the API currently has no way to say "done with this
turn, idle" versus "actively computing" — worth a maintainer decision on
whether the frontend needs a third state, or derives idle-ness from the last
event type client-side (untested here, no browser).

## (f) On `init.plugins` and the branch-under-test question

Stated plainly, per instruction: **the assumption in the task brief — that
`init.plugins` would show `laravel-team` resolving to the installed
marketplace copy at `.../laravel-team/1.26.0` rather than this working tree —
did not hold in this run.** Every run inspected (4 of 8) showed
`laravel-team` resolving via `source: "laravel-team@inline"` to this exact
working tree, at version 1.27.0 (this branch's already-current
`.claude-plugin/plugin.json`), not to the cached 1.26.0 marketplace copy.
`scripts/console/serve.py`'s `pack_root()` finds this branch's own
`.claude-plugin/plugin.json` before ever considering the marketplace
fallback path, so on this branch, at this commit, the console runs agents
from the branch under test. This may have been true at an earlier point in
this branch's history (e.g. before the 1.27.0 release commit landed, or in
whatever state the first, stalled attempt at this task observed) but it is
not what this run observed. Not fixing anything — just correcting the
premise as instructed.

## Cleanup

- Server killed (`kill` on the PID bound to :8392); `lsof -nP -iTCP:8392
  -sTCP:LISTEN` returns nothing.
- `tests/fixture-app/.claude/console/venv` left in place, untouched.
- `git status --short` shows only `.claude/agents-board.jsonl` modified
  (unrelated human telemetry, left unstaged per instructions).
- Scratch files created under `/tmp/guild_console_smoke_*.txt` during
  scenarios 3–5 were removed after verification; `tests/fixture-app/.claude/console/runs/*.jsonl`
  is gitignored (`tests/fixture-app/.gitignore`) and was left as-is.
- Note: the server was stopped with `kill` (SIGTERM), not Ctrl-C (SIGINT), so
  `serve.py`'s `except KeyboardInterrupt` / graceful-shutdown branch
  (`manager.shutdown()` disconnecting each run's SDK client) was likely not
  exercised — the port was confirmed free regardless, which is what cleanup
  required, but this means the graceful-shutdown code path itself remains
  unverified by this run.

## Process note (matches the earlier fix report, reproduced independently)

The startup banner carrying the token sat in stdout's buffer for roughly a
minute even with `python3 -u` on the initial invocation — because
`serve.py` re-execs itself into the venv via `os.execv()` with a fresh argv
that does not include `-u`, so the flag from the original invocation doesn't
survive the exec. Setting `PYTHONUNBUFFERED=1` as an environment variable
(which does survive `execv`, unlike a command-line flag) before starting the
process is the reliable way to get the banner promptly; this run used exactly
that after the first attempt (with only `-u`, no env var) sat empty for over
40 seconds.
