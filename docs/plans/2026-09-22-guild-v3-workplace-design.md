# Design — Guild 3.3 workplace loop

**Status:** approved 2026-09-22. Minor on 3.2.0. Adopter-facing: `/make-feature --issue <n>` makes a GitHub issue the delivery identity, the kernel records the pull request by re-running `gh`, and a failing check or a confirmed review comment reopens that stage once. Merge stays a person.

**Goal:** Work that starts from a GitHub issue can leave the repo and come back. Local `/make-feature` without an issue is unchanged.

**Why a minor:** 3.2 already owns lessons and `/pair`. 3.3 adds opt-in fields and three kernel commands. It does not change the default board, the agent count, or the command count.

VERSION stays **3.2.0** in the design and plan commits. Bump to **3.3.0** only after local gates (kernel units, guardrails, inventory, console). No billed eval.

## Locked choices

| Question | Choice |
| --- | --- |
| Entry | Opt-in `--issue <n>` on `plan`. No issue means today's delivery |
| Who talks to GitHub | The kernel re-runs `gh`. A coordinator sentence is not evidence |
| What is stored from the issue | `number`, `title`, `url`. The body is not parsed into stages |
| Pull request | `pr` records an existing PR. The kernel does not open or merge it |
| Done | A workplace delivery stays `running` until every stage is `✔` and the recorded PR `state` is `open` |
| Comeback | `ingest` reopens one `done` stage once. The second event stops the delivery |
| Console | Shows the kernel board line and posts `ingest`. It does not start the delivery or merge |
| Isolation | Shared working tree. No worktree. No Agent Teams |

Default `/make-feature` stays Supervisor. Adaptive stays opt-in. Do not raise `EVAL_TIMEOUT` (1200), `max_usd` ($8.50), or the 14.5M token ceiling. Do not uncomment `check_subagent_log`.

## Architecture

Same `scripts/guild-kernel/`. `runner.capture(cwd, cmd) -> (code, stdout)` is new and used only by workplace commands. `runner.run` stays exit-code-only so existing `report` tests stay put.

`Delivery` gains `issue` (dict), `pr` (dict), and `repo` (string). `StageSpec` gains `reopens` (int). `load()` defaults them so a 3.2 `kernel.json` still loads. Empty `issue` means this delivery is not a workplace delivery.

- **`plan --issue N`** runs `gh issue view N --json number,title,url`. Exit 0 and a matching number store the issue. Anything else raises `PlanError` and writes no file. A delivery file that already exists stays a no-op and does not refetch.
- **`pr --number N`** requires an issue. It runs `gh repo view --json nameWithOwner` and `gh pr view N --json number,url,state`. A non-zero exit leaves `pr` untouched. State is stored lowercased (`open`, `closed`, `merged`).
- **`ingest`** requires an issue and a recorded PR. `--kind check --stage <id> --check <name>` runs `gh pr checks <pr> --json name,bucket,link`. Bucket `fail` on that name reopens the stage. Any other bucket returns the delivery unchanged. `--kind review --stage <id> --comment <id>` runs `gh api repos/<repo>/pulls/<pr>/comments --jq .[].id`. The id must be a full stdout line.
- **Reopen.** The stage must be `done` and `reopens` must be 0. Status returns to `running`, `reopens` becomes 1, delivery status returns to `running`, and `cap` becomes `max(cap, spawns + 1)` so the fix spawn is allowed. A second ingest on that stage sets delivery `stopped` and does not change the stage.
- **Done.** `report` still requires exit 0 on every non-skipped stage. When `issue` is set and `pr.state` is not `open`, status stays `running` and the stage save still happens. `next` is `STOP` while every stage is finished. `pr` promotes `running` to `done` once the PR is `open` and the stages already pass DoD. A delivery with no issue becomes `done` as it does today.
- **Views.** `close.md` keeps the four labels and appends `ISSUE:` and `PR:` (`none` when empty). The kernel renders both. The coordinator does not write them.
- **Console.** `GET /api/kernel/board?name=` and `POST /api/kernel/ingest` use the console token and the process cwd as `--root`. The client cannot choose a root. A strip shows the board line and posts check or review ingest.

## Data flow

**Issue in, PR recorded.**

1. `/make-feature Tag --api --issue 42`. The coordinator still writes `done_when` and the stage list.
2. `plan --issue 42` stores the issue. `RULES:` still print.
3. Specialists run. `next` / `report` are unchanged.
4. A pull request exists. `pr --number 17` stores url, state, and `repo`.
5. The last `✔` with an open PR sets `done`. If the PR is recorded after the stages finish, `pr` itself sets `done`.

**A check comes back.**

1. Console or the coordinator calls `ingest --kind check --stage a --check pint`.
2. The kernel re-runs `gh pr checks`. Bucket `fail` reopens stage `a` once.
3. `next` returns that stage's agent. The spawn cap allows that one extra spawn.
4. A second failure on stage `a` sets the delivery `stopped`.

## Error handling

A reject leaves the file where it was, except a second reopen, which saves `stopped`.

| Case | Behavior |
| --- | --- |
| `--issue` and `gh issue view` exits non-zero, or the number mismatches | `PlanError`. No `kernel.json` |
| Resume `plan` while the file exists | No-op. Does not refetch. Does not swap the issue |
| `pr` with no issue | `PlanError` |
| `gh pr view` exits non-zero | `pr` stays `{}` |
| `ingest` with no issue or no PR | `PlanError` |
| Check name missing, or `gh` exits non-zero | `PlanError`. No reopen |
| Check bucket is not `fail` | No reopen. File unchanged |
| Review comment id absent from `gh` stdout | `PlanError`. No reopen |
| Reopen a stage that is not `done` | `PlanError` |
| Second ingest on a stage | Delivery `stopped`. Stage stays as it was |
| Delivery with no issue | `ingest` rejects. `report` can still set `done` without a PR |
| Client posts a `root` path | Ignored. The console uses its cwd |
| Direct invoke, no delivery slug | No workplace fields |

## Testing

Local only. No billed pin to ship 3.3. Do not loosen `check_kernel_state`. The default `feature` case does not pass `--issue`.

- **Kernel units** — 3.2 JSON loads with empty `issue`, `pr`, `repo`, and `reopens` 0. `close.md` gains `ISSUE: none` and `PR: none`. `plan --issue` stores number, title, and url from captured stdout. Non-zero `gh` writes no file. A second `plan` does not call `gh`. `pr` stores a lowercased `open` state and `nameWithOwner`. A failed `gh pr view` leaves `pr` empty. A workplace delivery with every stage `✔` and no open PR stays `running`, and `pr` then sets `done`. A delivery with no issue still reaches `done` with `pr` empty. A failing check reopens once, raises `cap` when `spawns` already meet it, and `next` returns that agent. A green check does not write. A second check stops the delivery. A review id that `gh` prints reopens. A missing id, a missing issue, and a missing PR reject.
- **CLI** — `plan --issue`, `pr --number`, `ingest --kind check|review` call those functions with `ProcessRunner`.
- **Guardrails** — the new Interface sentence on all **9** pipeline commands. Coordinator needle `Do not merge.` count **1**.
- **Console** — token-guarded board and ingest routes. Ingest name, kind, and stage are checked. Root comes from the server. UI strip posts the ingest body and renders the board line.
- **Inventory** — agents **18**, commands **16**, guardrails **9**. Pin `coordinator_hash` after the Interface edit. `waivers: []`.

## Inventory

- Agents **18**. Commands **16**. Skills **8**. Guardrails **9**. Gemini commands **14**. Codex `*.sh` hooks **8**.
- No new slash command. Workplace is `guild.py` plus one Interface sentence.
- Rebuild Gemini and Codex in the Interface change.
- Rebuild `scripts/console/dist` in the console change (`cd console-ui && npm run build`).

## Non-goals (3.3)

- Linear, Jira, or any tracker besides one GitHub issue number
- Kernel opens a pull request, merges, or polls GitHub on a timer
- Parsing an issue body into `done_when` or stages
- Console starts or stops a delivery
- Worktrees, Agent Teams, teammate chat, voting, LangGraph
- A new guardrail script
- Billed eval, uncommenting `check_subagent_log`, raising ceilings
- New default agent, Adaptive as default

## Versioning

| Field | 3.3.0 |
| --- | --- |
| Semver | Minor — opt-in issue, recorded PR, one reopen |
| Adopter action | Plugin update. Pass `--issue` to use the loop. Local make-feature stays the same |
| Do not bump | In the design or plan commit. Bump after local gates GREEN |
