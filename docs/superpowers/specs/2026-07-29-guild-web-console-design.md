# Design — Guild web console (v1.27.0)

**Goal:** drive the Guild from a browser instead of the terminal — launch a
command, a specialist, or a freeform task; watch every agent work as a pipeline
board; answer approvals and checkpoint questions as real UI; interrupt a run.
Local, single-developer, one project per console.

**Non-goal:** authoring the pack from the browser, an eval cockpit, a
multi-project daemon, or hosted multi-user access. Those are separate specs
(see [Scope boundary](#scope-boundary)). This spec also changes **no agent
bodies**, so it cannot confound the outstanding eval run 5 or the held
[literature-gap tranche](../../plans/2026-07-29-literature-gap-tranche.md).

---

## Verified platform facts

Every architectural choice below rests on these, checked against current docs
on 2026-07-29. Recorded so they are not re-derived.

- **Streaming input is the only interactive mode.** Queued follow-up messages,
  mid-run interruption, and surfaced permission requests exist only in
  streaming mode; single-shot `-p` has none of them.
  ([streaming-vs-single-mode](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode))
- **In Python, `can_use_tool` requires an open input stream.** Passing a finite
  prompt generator closes the stream before the callback can fire. Connecting
  with **no prompt** and sending through `ClaudeSDKClient.query()` keeps it open
  and needs no dummy-hook workaround.
  ([user-input](https://code.claude.com/docs/en/agent-sdk/user-input))
- **`PermissionResultAllow` must echo `updated_input`.** Before v2.1.207 an
  allow result omitting it was rejected as a validation error.
- **`AskUserQuestion` always reaches the callback**, even when an allow rule
  matches — but `dontAsk` mode *denies* it. `AskUserQuestion` is **not
  available in subagents** spawned via the Agent tool.
- **Hooks outrank every permission mode.** Hooks run before deny rules, ask
  rules, mode, and allow rules; a hook deny holds even in `bypassPermissions`.
  The five guardrail hooks therefore stay effective whatever mode the console
  runs in. ([permissions](https://code.claude.com/docs/en/agent-sdk/permissions))
- **Subagents inherit the parent permission mode**, and `bypassPermissions`,
  `acceptEdits`, and `auto` cannot be overridden per subagent.
- **Full subagent transcripts are reconstructible.** Messages carry
  `parent_tool_use_id`; `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT` (env equivalent of
  `--forward-subagent-text`) adds subagent text and thinking blocks, at every
  nesting depth. ([headless](https://code.claude.com/docs/en/headless))
- **`system/init` reports what loaded** — `plugins`, `plugin_errors`,
  `mcp_servers`, `mcp_server_errors`, and a `capabilities` array. `api_retry`
  events report retry progress.
- **`setting_sources` defaults to loading all sources** (user, project, local)
  plus project `CLAUDE.md` — the same context a terminal session gets.
- **`ClaudeSDKClient` exposes `interrupt()`, `set_permission_mode()`, and
  `set_model()`** mid-session.
  ([python reference](https://code.claude.com/docs/en/agent-sdk/python))
- **The SDK has no session-wide equivalent of the CLI's `--agent` flag.** The
  `agents` option defines subagents for delegation, not session identity. See
  [Specialist runs](#specialist-runs) for the consequence.

---

## Architecture

### Process model

`/console [port]` starts `scripts/console/serve.py`, bound to `127.0.0.1`.
First run creates a venv at `.claude/console/venv` holding `claude-agent-sdk`;
if python3 or pip cannot support it the console prints a plain diagnostic and
exits rather than half-starting. Port busy → increment, as `/board` does.

Two threads of control:

- **stdlib `ThreadingHTTPServer`** serves the built SPA, the JSON API, and
  per-run SSE. It holds no SDK knowledge.
- **One dedicated asyncio loop thread** owns every `ClaudeSDKClient`. Commands
  cross in via `asyncio.run_coroutine_threadsafe`; events cross out via a
  `queue.SimpleQueue` per SSE subscriber.

An asyncio HTTP server would mean hand-writing HTTP parsing; a thread per SDK
client would scatter interrupt and answer routing across supervision contexts.
One loop, one server, one bridge.

### Per-run session

One `ClaudeSDKClient` per run. `connect()` with **no prompt**, then `query()`
per user message — the shape required for `can_use_tool`. The client is not
closed at `ResultMessage`; it stays connected so follow-ups continue the same
session.

`ClaudeAgentOptions` per run:

| Option | Value | Why |
| --- | --- | --- |
| `cwd` | console launch directory | one project per console |
| `setting_sources` | default (unset) | loads project/local/user settings and `CLAUDE.md`, matching a terminal session |
| `plugins` | `[pack_root]` | explicit load of the Guild pack |
| `permission_mode` | `"default"`, per-run toggle to `"acceptEdits"` | see below |
| `can_use_tool` | engine callback | approvals and questions |
| env | `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT=1` | subagent transcripts |

`pack_root` resolves to the repo root when it contains
`.claude-plugin/plugin.json`, otherwise the installed plugin directory. On the
`init` event the console asserts the pack loaded: `plugin_errors` empty **and**
`laravel-team` present in `plugins`. Those are what `init` actually reports — it
carries no agent inventory — so the check is stated in those terms rather than
in agent counts, and a failure raises a banner.

### Permission posture

Default `default`: every call not pre-approved by settings reaches the browser,
**with one measured exception** — see "What the CLI decides before we are asked"
below. A per-run selector also offers `acceptEdits` and `plan`, and either can be
changed mid-run. `plan` is included because clarifying questions are most
common there, which is exactly what the console renders best.

#### What the CLI decides before we are asked

`can_use_tool` is not the first gate. Claude Code resolves some Bash calls
itself and never consults the callback, so no `prompt` event is emitted and the
browser is never asked. Two such paths exist in CLI 2.1.220:

1. **Read-only commands** (`READ_ONLY_AUTO_ALLOW_REASON`, "Read-only command is
   allowed"). A command the CLI classifies as read-only is allowed before the
   callback runs. Measured against this console: `echo hello` produced
   `tool_use` → `tool_result` with **zero** `prompt` events, while
   `mkdir -p /tmp/…` produced `prompt` → `prompt_resolved` normally. There is no
   SDK option or settings key that turns this off; only a `PreToolUse` hook sees
   every call. The console still shows *that* the command ran — as a `tool_use`
   event — just not that nobody was asked.
2. **Sandboxed commands** (`SANDBOX_AUTO_ALLOW_REASON`). When bash sandboxing is
   on, `sandbox.autoAllowBashIfSandboxed` (SDK default `True`) auto-approves
   sandboxed commands the same way. This one *is* configurable, so
   `sdk_client_factory` sets `sandbox={"autoAllowBashIfSandboxed": False}`
   explicitly and `tests/guardrails.test.sh` pins it. The CLI's own
   `sandbox.enabled` default is `False`, so this is insurance for the case where
   user, project or managed settings turn sandboxing on.

Containment is unaffected either way: hooks outrank every permission mode, so
the five guardrail hooks still fire on an auto-approved call. What is affected is
visibility, and the honest statement of it is this section.

`bypassPermissions` is **not offered in the UI** — subagents inherit it and
cannot override it, so one toggle would grant seventeen agents unattended
system access. `dontAsk` is never used: it denies `AskUserQuestion`, which is
how checkpoint prompts arrive.

The five guardrail hooks are untouched and remain authoritative. The console
cannot be used to route around `block-prod-artisan.sh`,
`block-prod-destructive-sql.sh`, `enforce-reviewer-readonly.sh`,
`enforce-sail.sh`, or `protect-env-files.sh`.

### Security

The console is a loopback server that can execute arbitrary tools, so:

- bind `127.0.0.1` only
- a random token minted per start, required on every `/api` route; the browser
  receives it in the opened URL
- `Origin` rejected unless absent or localhost — defends against a hostile page
  fetching the loopback, and against DNS rebinding
- no wildcard CORS; no path parameter that resolves outside the project root

---

## Components

```
console-ui/                        # SOURCE — contributors only, not installed
├── package.json  vite.config.ts  tailwind.config.ts  components.json
└── src/
    ├── lib/reducer.ts             # pure: flat events → run tree (vitest)
    ├── lib/api.ts                 # token header, SSE resume via Last-Event-ID
    ├── components/ui/*            # shadcn primitives, copied in
    ├── Launcher.tsx               # command / specialist / freeform picker
    ├── Board.tsx                  # pipeline columns
    ├── StageColumn.tsx  AgentCard.tsx
    ├── ApprovalBar.tsx  DecisionSheet.tsx
    ├── FocusRun.tsx               # solo-run layout
    └── Transcript.tsx

scripts/console/
├── serve.py                       # entry: venv bootstrap, token, wiring
├── server.py                      # HTTP + SSE + static assets only
├── engine.py                      # asyncio loop, SDK clients, can_use_tool
├── events.py                      # normalized schema + pure reducer
├── catalog.py                     # parses agents / commands / skills
└── dist/                          # BUILT, COMMITTED, served by serve.py
```

**Stack:** React 19 + TypeScript, Vite, Tailwind v4, shadcn/ui, `motion` for
animation, `lucide-react`, vitest.

Node is a **build-time dependency only**. The bundle is committed and served by
the python process, so installing users need no Node — the same pattern as the
generated Gemini and Codex mirrors, guarded the same way by a CI drift check.

**`catalog.py`** — `load_catalog(root) -> {agents, commands, skills}`. Reads
`agents/*.md` frontmatter for slug, model, tools, and description, lifting the
human name from the description prefix (`"Adam — the Guild's…"`), plus
`commands/*.md` and `skills/*/SKILL.md`. It introduces **no new name registry**;
a sixth place to register an agent would fight `check_inventory_sync.py`.

Card colour comes from each agent's existing `color:` frontmatter field, which
all seventeen already declare. Eight hue families cover seventeen agents, so
families collide (three purples, two each of red, orange, cyan, green, blue,
pink, yellow). The console resolves a collision by assigning each member of a
family a distinct shade from a four-step ramp, indexed by the agent's position
in the alphabetically sorted list of that family's members — deterministic,
reviewable, and distinct for every agent. Colours will not match
`board.html`'s hand-picked hex map; that is cosmetic and accepted.

**`engine.py`** — `RunManager` with surface `start(spec) -> run_id`, `send`,
`interrupt`, `answer`, `set_mode`, `set_model`, `subscribe(run_id, since_seq)`.
It owns `can_use_tool`: mints a `prompt_id`, emits a `prompt` event, and awaits
an `asyncio.Future` resolved by an HTTP POST. No timeout — the callback may
pend indefinitely by design. The `defer` hook decision is deliberately unused;
the console stays running.

**`events.py`** — normalized events `{seq, run_id, ts, type, …}` of type
`init`, `text`, `thinking`, `tool_use`, `tool_result`, `agent_start`,
`agent_end`, `prompt`, `prompt_resolved`, `api_retry`, `result`, `error`.
Normalization is a pure function over one SDK message plus prior state, so it
is testable from recorded fixtures at zero API spend.

Each run persists **raw SDK messages and normalized events** to
`.claude/console/runs/<run_id>.jsonl`. That gives replay, SSE catch-up, and the
fixture corpus for tests.

**`server.py`** routes:

| Route | Purpose |
| --- | --- |
| `GET /` | built SPA (SPA fallback for client routes) |
| `GET /api/catalog` | agents, commands, skills |
| `POST /api/runs` | `{kind: "command"｜"specialist"｜"prompt", target, text, mode, model}` → `{run_id}` |
| `GET /api/runs` | run list from disk |
| `GET /api/runs/{id}` | replay |
| `GET /api/runs/{id}/events` | SSE, resumable via `Last-Event-ID` |
| `POST /api/runs/{id}/message` | follow-up into the live session |
| `POST /api/runs/{id}/answer` | resolve a pending prompt |
| `POST /api/runs/{id}/interrupt` | interrupt the run |
| `POST /api/runs/{id}/mode` | `{mode?, model?}` → `set_permission_mode` and/or `set_model` |

---

## The board

### Column derivation

The console sees subagent spawns, never stage labels, so columns come from a
role→stage map held in the console:

| Column | Agents |
| --- | --- |
| Discover | business-analyst, product-owner, scrum-master |
| Design | solution-architect, ui-ux-designer |
| Build | database-developer, backend-developer, frontend-developer, mobile-developer, package-developer |
| Review | tech-lead, security-engineer, performance-engineer |
| Test | qa-engineer |
| Ship | devops-engineer |
| Docs | technical-writer |
| Working | any agent the map does not know (fail-soft) |

`delivery-coordinator` is not a card; it is the board's own header. An agent
working outside its home column still shows its real task on the card — the
column is role home, not a claim about the run's phase.

Emitting true stage markers is deliberately rejected: it would require editing
the `Interface` block that is byte-identical across the nine pipeline commands
and guarded by a test.

### Focus mode

A run that involves one agent renders as a single full-width agent with its
transcript, not five mostly-empty columns. The switch is automatic and never a
user setting, resolved in two steps:

- **At launch by kind.** `specialist` and `prompt` runs open in Focus mode;
  `command` runs open on the board.
- **Promoted at runtime.** A Focus run that spawns a second distinct agent
  promotes to the board, animating the existing card into its column. Promotion
  is one-way — a board run never demotes to Focus.

### Where an approval presents

A run genuinely freezes until answered, so the pending state is unmissable:

1. A **persistent bar** at the top of the board — cannot be scrolled away or
   covered by a sheet — naming the agent and tool.
2. The waiting **card** is marked and pulsing in its column.
3. Clicking either opens a **decision sheet** with full context: command or
   diff, working directory, and the choices — allow once, allow always (echoing
   a `localSettings` suggestion from `context.suggestions` so future sessions
   skip the prompt), deny with a message back to the agent.

`AskUserQuestion` uses the same channel with a question card: 1–4 questions,
2–4 options each, multi-select where the tool says so, an "Other" free-text
field per question, and a dismiss-and-reply box that maps to the optional
`response` field. Answers return as
`{questions, answers: {question_text: label | [labels]}}`.

### Specialist runs

With no SDK equivalent of `--agent`, launching "Adam" sends a delegation prompt
to the main thread (`Use the backend-developer subagent to: …`) so the agent's
real body loads from the plugin with no prompt duplication.

Consequence, stated plainly: **subagents cannot use `AskUserQuestion`**, so
specialist runs produce no question cards — clarifications arrive as text and
the user replies with a follow-up message. Command runs, coordinator runs, and
freeform prompts are main-thread and do get question cards.

---

## Data flow

1. `POST /api/runs` → token and `Origin` validated → `RunManager.start`
   submitted to the engine loop.
2. Engine builds options, `connect()`s with no prompt, `query(text)`.
3. `async for msg in client.receive_messages()` → normalize → append raw and
   normalized to the run jsonl → fan out to subscriber queues → SSE.
4. On `init`, verify the pack loaded; emit a banner event if not.
5. `can_use_tool` fires → `prompt` event → bar, card, sheet → `POST /answer`
   resolves the future → `PermissionResultAllow(updated_input=…)` or
   `PermissionResultDeny(message=…)`.
6. `ResultMessage` ends the turn; the client stays connected. `POST /message`
   continues the same session.

---

## Failure modes

| Condition | Behaviour |
| --- | --- |
| SDK or CLI missing / incompatible | diagnostic page, not a 500 |
| `plugin_errors` non-empty, or `laravel-team` absent from `plugins` | red banner, run proceeds — fail loud, not fail closed |
| `api_retry` event | surfaced on the card ("retrying, attempt 2/5") so it never looks hung |
| SSE disconnect | reconnect with `Last-Event-ID`; server replays from the run jsonl |
| Server killed mid-run | SDK child process dies with it; on restart disk runs show `interrupted`, never a false `running` |
| Interrupt while a prompt is pending | resolve that future with a deny **first**, then `client.interrupt()` — otherwise the loop parks behind an unanswerable card |
| Two browser tabs | both subscribe; first answer wins, the second receives `prompt_resolved` and dismisses |
| Browser closed while parked | run stays parked; reopening shows the bar again |
| Port busy | increment until free |

---

## Testing

**Python units.** Catalog parsing against the real seventeen agents;
`normalize` and tree reconstruction from recorded fixtures; token and `Origin`
rejection; prompt-future resolution including interrupt-while-pending and
double-answer.

**Vitest.** `reducer.ts` — flat events to run tree, including out-of-order
arrival and nested subagents.

**Guardrails suite.** New cases: console binds loopback only;
`bypassPermissions` appears nowhere in the built bundle.

**CI.** A Node job runs `npm ci && vitest run && npm run build`, then
`git diff --exit-code scripts/console/dist` as a drift guard — the same shape
as the Gemini mirror check.

**Manual smoke.** One real run against `tests/fixture-app`, exercising an
approval, a checkpoint question, and an interrupt.

---

## Release obligations

- The console adds a **13th command**, so `scripts/check_inventory_sync.py`
  CLAIMS and the README counts move in the **same commit**. Stale counts shipped
  at 1.10.0 and were caught late at 1.20.0.
- Version bump touches `VERSION` and all four plugin manifests; Gemini and
  Codex mirrors regenerate via `scripts/build-*.py`. Bump `VERSION` before
  running the Gemini build.
- Gemini and Codex **skip the console** — no Agent SDK there, the same decision
  as `/board`. The Gemini command count stays deliberately lower.
- `.gitignore` gains `.claude/console/` and `.superpowers/`.
- `scripts/board.html` and `scripts/emit-agent-events.sh` are **not modified**.
  They still cover terminal-launched runs, and the eval harness copies that feed
  verbatim.

---

## Scope boundary

Deferred to their own specs, in this order:

1. **Pack manager** — edit agent bodies and frontmatter, model tiers, hook
   toggles, and run `validate-frontmatter.py`, `check_body_budget.py`,
   `check_inventory_sync.py`, and the guardrails suite from the UI.
2. **Eval cockpit** — drive `tests/eval/run-evals.sh`, live case progress,
   scorecard diff against `tests/eval/baseline.json`.
3. **Distribution beyond v1** — multi-project daemon, terminal-run visibility,
   session resume across a server restart.

Also out of scope here: mobile layout (desktop-first), authentication, and any
hosted or multi-user mode.

---

## Decided fallbacks to confirm during implementation

Neither blocks the plan; both have a chosen path.

- **Session-wide agent selection.** If `ClaudeAgentOptions` turns out to expose
  a main-thread agent selector, specialist runs use it and gain question cards.
  Until proven, they use the delegation prompt above.
- **Board animation at scale.** `motion` layout animations are specified for
  card flight between columns. If a wide run (20+ cards) drops frames, cards
  outside the active column fall back to opacity and transform transitions
  only. Measured during implementation, not assumed.
