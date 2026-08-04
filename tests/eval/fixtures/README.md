# Eval fixtures

Real `claude -p --output-format stream-json --verbose` transcripts, captured
2026-08-04 against this repo with Claude Code 2.1.221. They exist because
writing a parser from an assumed wire format is how v1.27.0 shipped a console
that emitted zero events with 62/62 tests green. The shape gets recorded first,
from the dependency, and `scripts/eval-cost.py` is written against what is
recorded here.

Hook `output` / `stdout` / `stderr` strings longer than 200 chars are replaced
with `<redacted for the fixture: N chars of hook output>` — they carried ~130KB
of this project's own session-memory dump, which a usage parser never reads. No
other field is altered; every `usage` object is byte-original.

| File | Prompt | Why |
| --- | --- | --- |
| `stream-json-sample.jsonl` | "List the files in the current directory, then stop." | Baseline shape: line types, keys, where usage and the final answer live. |
| `stream-json-subagent.jsonl` | Delegate one `general-purpose` subagent, report what it returned. | The per-agent attribution question. The baseline probe spawns no subagent, so it **cannot** answer it — that is why there are two. |

## Observed line types

From `stream-json-sample.jsonl` (12 lines):

| `type` | count | keys |
| --- | --- | --- |
| `system` | 7 | `agents`, `analytics_disabled`, `apiKeySource`, `capabilities`, `claude_code_version`, `cwd`, `exit_code`, `fast_mode_disabled_reason`, `fast_mode_state`, `hook_event`, `hook_id`, `hook_name`, `mcp_servers`, `memory_paths`, `model`, `outcome`, `output`, `output_style`, `permissionMode`, `plugins`, `product_feedback_disabled`, `session_id`, `skills`, `slash_commands`, `stderr`, `stdout`, `subtype`, `tools`, `type`, `uuid` |
| `assistant` | 2 | `message`, `parent_tool_use_id`, `request_id`, `session_id`, `timestamp`, `type`, `uuid` |
| `user` | 1 | `message`, `parent_tool_use_id`, `session_id`, `timestamp`, `tool_use_result`, `type`, `uuid` |
| `rate_limit_event` | 1 | `rate_limit_info`, `session_id`, `type`, `uuid` |
| `result` | 1 | `api_error_status`, `duration_api_ms`, `duration_ms`, `fast_mode_state`, `is_error`, `modelUsage`, `num_turns`, `permission_denials`, `result`, `session_id`, `stop_reason`, `subtype`, `terminal_reason`, `time_to_request_ms`, `total_cost_usd`, `ttft_ms`, `ttft_stream_ms`, `type`, `usage`, `uuid` |

`stream-json-subagent.jsonl` adds `system` subtypes `task_started`, `task_progress`,
`task_updated`, `task_notification`.

**Where the final answer text lives:** the `result` key on the single
`type: "result"` line. This is exactly what plain `claude -p` prints, which is
why the harness can rebuild `$LOG` from it and leave the answer key untouched.

**Where token usage lives:** `message.usage` on `type: "assistant"` lines, with
four separate counts — `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`, `output_tokens`. The `result` line carries the
run-total equivalent under `usage`, plus per-model totals and dollars under
`modelUsage.<model>.{inputTokens,outputTokens,cacheReadInputTokens,cacheCreationInputTokens,costUSD}`,
plus `total_cost_usd` for the whole run.

**Cache tokens dominate, and this is the trap.** In the baseline probe the raw
`input_tokens` is **4**, against 20,522 cache-creation and 50,873 cache-read
tokens. A parser that prices only `input_tokens` + `output_tokens` reports
~$0.009 where the CLI reports $0.2397 — a 26× undercount. Any rate table must
carry the cache tiers.

**Which model billed each turn:** `message.model` on `assistant` lines. This is
preferred over the `model:` frontmatter in `agents/*.md` — it records what
actually billed, not what the pack declares, so a mis-tiered agent shows up as
a cost anomaly instead of being silently priced at its intended rate.

**Where the acting agent is identified:** there is **no** `agent` or
`agent_type` field on any line. Attribution is two-hop:

1. A `system` line with `subtype: "task_started"` carries `tool_use_id` plus
   `subagent_type` (and `description`, `prompt`, `task_id`).
2. Every `assistant` / `user` line produced inside that subagent carries
   `parent_tool_use_id` equal to that `tool_use_id`. Main-thread lines carry
   `parent_tool_use_id: null`.

So `task_started` builds `tool_use_id -> subagent_type`, and turns are
attributed by looking up their `parent_tool_use_id`; unmatched means `main`.
The same `tool_use_id` also appears as the `id` of the `Agent` `tool_use` block
on the spawning assistant turn, whose `input.subagent_type` agrees — a
redundant second source, deliberately unused because `task_started` states it
directly.

**Where tool calls appear:** `message.content[]` entries with
`type: "tool_use"` and a `.name`. Subagent spawns are `name: "Agent"` with
`input.subagent_type`.

## Verified pricing model

Cache-aware pricing reproduces the CLI's own `total_cost_usd` **exactly** on the
baseline probe (0.2397265, matching to 7 decimal places):

```
20522 * 2.0  * 5/1e6   # cache creation, 1h TTL -> 2x base input
+ 50873 * 0.1 * 5/1e6   # cache read            -> 0.1x base input
+   362 * 25/1e6        # output
+     4 * 5/1e6         # uncached input
= 0.2397265
```

Multipliers (cache write 1.25x at 5m / 2x at 1h, cache read 0.1x) come from the
`claude-api` skill and are confirmed by that identity. Note Claude Code writes
**1h** cache entries here (`cache_creation.ephemeral_1h_input_tokens` is
populated, `ephemeral_5m_input_tokens` is 0), so the 2x multiplier is the one
that applies in practice — assuming 1.25x would undercount every cache write.

Because the identity holds, `scripts/eval-cost.py` reports both its derived
total and the CLI's `total_cost_usd`, and flags any divergence. That is the
guard against a stale rate table: if Anthropic changes prices and
`tests/eval/model-rates.json` is not updated, the reconciliation drifts and says
so instead of silently reporting a wrong number.

## Re-capturing

Run the two commands in `docs/superpowers/plans/2026-08-04-agent-accuracy-and-cost.md`
Task 1, re-apply the hook redaction, and update this file. Do it whenever the
CLI's stream-json format changes — the parser is written against this record,
so a stale record becomes a parser bug.
