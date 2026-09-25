# How are stage budgets enforced?

Laravel Guild turns the shared budget registry into durable policy for every
kernel-planned specialist stage. The source of truth is
[`config/agent-harness.json`](../config/agent-harness.json); the implementation
is [`scripts/guild-kernel/kernel.py`](../scripts/guild-kernel/kernel.py), and the
Claude boundary adapter is
[`scripts/enforce-kernel-budgets.py`](../scripts/enforce-kernel-budgets.py).

## The contract

Every new stage snapshots five limits:

| Limit | Default | Hard ceiling | Evidence |
| --- | ---: | ---: | --- |
| Seconds | 1,800 | 14,400 | Claim timestamp plus Agent duration |
| Tool calls | 200 | 1,000 | Pre-tool counter plus Agent total |
| Assistant turns | 120 | 500 | Agent completion usage |
| Tokens | 5,000,000 | 20,000,000 | Agent completion total |
| USD | 10.00 | 100.00 | Exact total when present, otherwise model-usage estimate |

A stage may override any subset up to the hard ceilings. Missing keys inherit
the defaults. The normalized result is stored in `kernel.json`, so changing the
registry during a delivery cannot move its goalposts.

## The execution sequence

1. `plan` validates and snapshots the effective stage budget.
2. `ready` returns that budget with the stage brief.
3. `claim` records a UTC start timestamp.
4. On Claude Code, each subagent `PreToolUse` checks elapsed seconds and the
   persisted tool-call count before allowing the next tool.
5. A synchronous Agent completion records all five usage dimensions. Repeated
   delivery of the same hook event is idempotent.
6. `report` rejects a claimed stage whose completion telemetry has not cleared
   the claim timestamp.
7. A breach changes both stage and delivery status to `budget_exceeded`, writes
   the reason, renders `⛔` on the board, and makes `ready` and `next` stop.

Inspect a receipt with:

```sh
python3 scripts/guild-kernel/guild.py budget list \
  --root . --name <delivery>
```

## Other runtimes

The kernel is runtime-neutral, but automatic telemetry is not. Claude Code's
synchronous Agent result exposes duration, total tool calls, total tokens, and
model usage. When another runtime exposes equivalent evidence, the main thread
records it before `report`:

```sh
python3 scripts/guild-kernel/guild.py budget record \
  --root . --name <delivery> --stage <stage> \
  --seconds <n> --tool-calls <n> --turns <n> --tokens <n> --usd <n>
```

All five values are required. The coordinator must not substitute zero for an
unknown value. Without a full receipt, the claim timestamp remains and the
kernel rejects the success report.

## Cost estimation

When the runtime supplies an exact total cost, that value wins. Otherwise the
hook prices the runtime's input, output, cache-read, and cache-write counters
using the registry's release-owned table. Unknown models use the most expensive
fallback rate. Cache creation uses the conservative two-times input multiplier.
The table was checked on 2026-09-25 against Anthropic's current
[Sonnet 5](https://www.anthropic.com/news/claude-sonnet-5),
[Opus 5](https://www.anthropic.com/news/claude-opus-5), and
[Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5) prices. The Sonnet
entry deliberately retains the prior $3/$15 rate as an upper bound over the
current $2/$10 list price.
The persisted number is a budget guard, not an invoice; provider billing is the
authority for financial reconciliation.

## Trust and recovery boundaries

- The automatic adapter covers synchronous Claude `Agent`/`Task` calls. The
  coordinator already forbids backgrounded lanes; an async launch has no usable
  completion receipt and therefore cannot report success.
- The hook blocks a Guild subagent from invoking `budget record` for itself.
  The kernel CLI cannot cryptographically prove that another runtime's caller
  is the main thread, so the orchestration contract remains part of that path.
- Direct single-specialist fast-path work has no kernel stage and therefore no
  stage budget. Console-launched work still has the console's independent
  runtime budget watchdog.
- There is deliberately no silent reset command. A budget-exceeded delivery is
  terminal. The human reviews the receipt and starts an explicitly re-planned
  delivery if more budget is justified.
- Usage is cumulative across the one CI/review reopen. Reopening a completed
  stage starts a new active timer but does not erase prior calls, turns, tokens,
  or cost.

Last verified: 2026-09-25.
