#!/usr/bin/env python3
"""Turn one `claude -p --output-format stream-json --verbose` transcript into a
per-agent cost summary.

Why this exists: the eval harness measured correctness and latency but never
cost, and the only cost signal it did emit (per-agent totals on the board feed)
carries no input/output split. Output costs 5x input on every tier and cache
tokens dominate input, so a bare total cannot be priced -- only guessed at.

Every key path here is recorded in tests/eval/fixtures/README.md from a real
transcript rather than assumed. Three findings from that recording drive the
design, and none of them were guessable:

1. Cache tokens dominate. The probe bills 4 raw input tokens against 71k cache
   tokens. Pricing input+output alone undercounts a run ~26x.
2. The two cache-write tiers differ (1h = 2x input, 5m = 1.25x) and BOTH appear
   in one run -- Claude Code writes 1h on the main thread and 5m inside
   subagents -- so a single multiplier on aggregate cache_creation is wrong for
   every case that delegates.
3. There is no `agent` field. Attribution is `parent_tool_use_id` on a turn,
   resolved through a `task_started` system line that maps that id to a
   `subagent_type`.

Two numbers come out, and they are not the same number:

  billed     -- the CLI's own `total_cost_usd`. Authoritative; zero arithmetic
                risk. This is the run's cost.
  attributed -- per-agent shares derived from per-turn usage. Per-turn usage
                excludes thinking tokens and is scoped differently from the
                result line, so this never equals `billed`. It answers "which
                agent dominates", not "what did the run cost", and it reports
                its own coverage of the billed total so the gap is visible.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys

PER_MILLION = 1_000_000
# Real transcripts report the dated model ID (`claude-haiku-4-5-20251001`) where
# the pack's frontmatter and the rate table use the alias (`claude-haiku-4-5`).
# Eval run 6's first case caught this: the dated haiku id missed the table, fell
# back to the default Opus rate, and priced scrum-master 5x too high.
_DATE_SUFFIX = re.compile(r"-\d{8}$")
# The CLI's own total_cost_usd is the oracle; agreement is checked to the cent.
RECONCILE_TOLERANCE_USD = 0.005


def _iter_objects(lines):
    """Yield (obj, ok) for each non-blank line. Bad lines yield (None, False).

    The harness redirects stderr into the same stream, so a warning can land
    mid-transcript. One bad line must not cost the whole run's data.

    A line can also be valid JSON without being an object -- a bare `42`, `null`,
    `"text"`, or `[]`. Those reach `obj.get(...)` and raise, losing the whole
    run's cost data, so a non-dict is treated as a parse error like any other
    unusable line.
    """
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            yield None, False
            continue
        if not isinstance(obj, dict):
            yield None, False
            continue
        yield obj, True


def _int(value):
    """Token counts arrive as ints, but nulls are possible (cf. the v1.25.0
    SubagentStop finding, where every real payload carried ms: null)."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _message(obj):
    msg = obj.get("message")
    return msg if isinstance(msg, dict) else {}


def _usage_of(obj):
    """The five billable token classes for one turn, or None if it has none.

    Deliberately scoped to `assistant` lines and `message.usage`. The result
    line carries a `usage` object of its own and `task_progress` lines carry a
    third shape -- a permissive read counts the run's usage twice over and
    reports ~197% coverage, which is how this scoping got pinned down.
    """
    if obj.get("type") != "assistant":
        return None
    usage = _message(obj).get("usage")
    if not isinstance(usage, dict):
        return None
    creation = usage.get("cache_creation")
    creation = creation if isinstance(creation, dict) else {}
    one_hour = _int(creation.get("ephemeral_1h_input_tokens"))
    five_min = _int(creation.get("ephemeral_5m_input_tokens"))
    aggregate = _int(usage.get("cache_creation_input_tokens"))
    # No TTL breakdown (older CLI, or a shape change): fall back to the
    # aggregate and price it at the 1h tier. That is the more expensive tier, so
    # an unknown blend is over-stated rather than under-stated -- for a cost
    # instrument, a number that is too high is a false alarm while one that is
    # too low is a missed regression.
    if one_hour + five_min == 0 and aggregate:
        one_hour = aggregate
    return {
        "input_tokens": _int(usage.get("input_tokens")),
        "output_tokens": _int(usage.get("output_tokens")),
        "cache_read_tokens": _int(usage.get("cache_read_input_tokens")),
        "cache_write_1h_tokens": one_hour,
        "cache_write_5m_tokens": five_min,
    }


def _tools_of(obj):
    """Tool names invoked in this turn."""
    content = _message(obj).get("content")
    if not isinstance(content, list):
        return []
    return [
        block.get("name")
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name")
    ]


def _text_of(obj):
    content = _message(obj).get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text") or ""
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def final_text(lines):
    """The run's final answer, matching what plain `claude -p` prints.

    Plain `-p` output IS the `result` field, so taking it keeps the eval answer
    key's greps reading exactly what they read before this change. A run that
    times out or is killed never emits a result line -- run 4 had a timeout --
    so fall back to the concatenated assistant text rather than nothing.

    The fallback takes `assistant` lines ONLY. `user` lines carry the prompt and
    tool results as text blocks, and folding those in would let an answer-key
    grep match the eval's own prompt and report a false PASS on a timed-out run
    -- which is the exact failure this whole capture path exists to prevent.
    """
    assistant_text = []
    for obj, ok in _iter_objects(lines):
        if not ok:
            continue
        if obj.get("type") == "result" and isinstance(obj.get("result"), str):
            return obj["result"]
        if obj.get("type") == "assistant":
            assistant_text.append(_text_of(obj))
    return "".join(assistant_text) or None


def _price(counts, rate, multipliers):
    """Cost of one bundle of token counts at one model's rates."""
    per_input = rate["input"] / PER_MILLION
    return (
        counts["input_tokens"] * per_input
        + counts["cache_write_1h_tokens"] * multipliers["cache_write_1h"] * per_input
        + counts["cache_write_5m_tokens"] * multipliers["cache_write_5m"] * per_input
        + counts["cache_read_tokens"] * multipliers["cache_read"] * per_input
        + counts["output_tokens"] * rate["output"] / PER_MILLION
    )


def _resolve_rate(model, table, default_model):
    """(rate, priced) for a model id, tolerating a dated full id.

    Tries the id as given, then with a trailing `-YYYYMMDD` stripped, then the
    table's default. `priced` is False only when nothing matched, so a genuinely
    unknown model is reported rather than silently charged at the default rate.
    """
    for candidate in (model, _DATE_SUFFIX.sub("", model or "")):
        if candidate in table:
            return table[candidate], True
    return table.get(default_model) or {"input": 0.0, "output": 0.0}, False


def _empty_counts():
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cache_write_5m_tokens": 0,
    }


def _subagent_map(lines):
    """tool_use_id -> subagent_type, from `task_started` system lines.

    This is the only place the transcript names an agent. The spawning Agent
    tool_use block carries the same pairing in its `input.subagent_type`, but
    task_started states it directly, so that second source stays unused.
    """
    mapping = {}
    for obj, ok in _iter_objects(lines):
        if not ok or obj.get("type") != "system":
            continue
        if obj.get("subtype") == "task_started" and obj.get("tool_use_id"):
            mapping[obj["tool_use_id"]] = obj.get("subagent_type") or "unknown-agent"
    return mapping


def _billed(lines, rates):
    """The CLI's own cost figure, plus a check that our rate table agrees.

    `modelUsage` on the result line is the CLI's billing ledger: its per-model
    `costUSD` sums to `total_cost_usd` exactly. It does NOT carry the cache-TTL
    breakdown, so the check brackets rather than pins: reprice its counts once
    with every cache write at the 5m tier (cheapest possible) and once at the 1h
    tier (dearest). The billed figure must land inside that bracket, and the
    cache-write multiplier it implies must be a real one. If Anthropic changes a
    price and model-rates.json is not updated, the bracket misses and `agrees`
    goes false instead of the summary quietly reporting a wrong number.
    """
    table = rates.get("rates", {})
    multipliers = rates["multipliers"]
    result = None
    for obj, ok in _iter_objects(lines):
        if ok and obj.get("type") == "result":
            result = obj
    if result is None:
        return {"usd": None, "models": {}, "tokens": None, "rate_table_check": {
            "billed_usd": None, "repriced_usd_min": None, "repriced_usd_max": None,
            "implied_cache_write_multiplier": None, "agrees": None,
        }}

    billed_usd = result.get("total_cost_usd")
    model_usage = result.get("modelUsage")
    model_usage = model_usage if isinstance(model_usage, dict) else {}

    models, totals = {}, _empty_counts()
    low = high = 0.0
    read_and_flat = 0.0
    write_tokens_at_input_rate = 0.0
    for model, entry in sorted(model_usage.items()):
        counts = {
            "input_tokens": _int(entry.get("inputTokens")),
            "output_tokens": _int(entry.get("outputTokens")),
            "cache_read_tokens": _int(entry.get("cacheReadInputTokens")),
            "cache_write_1h_tokens": 0,
            "cache_write_5m_tokens": _int(entry.get("cacheCreationInputTokens")),
        }
        models[model] = dict(counts, usd=entry.get("costUSD"))
        models[model]["cache_write_tokens_ttl_unsplit"] = counts.pop("cache_write_5m_tokens")
        writes = models[model]["cache_write_tokens_ttl_unsplit"]
        for key in totals:
            totals[key] += counts.get(key, 0)
        totals["cache_write_5m_tokens"] += 0  # kept explicit: TTL unknown here

        rate, _ = _resolve_rate(model, table, rates.get("_default", ""))
        per_input = rate["input"] / PER_MILLION
        flat = _price(dict(counts, cache_write_5m_tokens=0, cache_write_1h_tokens=0), rate, multipliers)
        read_and_flat += flat
        write_tokens_at_input_rate += writes * per_input
        low += flat + writes * multipliers["cache_write_5m"] * per_input
        high += flat + writes * multipliers["cache_write_1h"] * per_input

    implied = None
    if billed_usd is not None and write_tokens_at_input_rate > 0:
        implied = round((billed_usd - read_and_flat) / write_tokens_at_input_rate, 4)

    agrees = None
    if billed_usd is not None and model_usage:
        in_bracket = (low - RECONCILE_TOLERANCE_USD) <= billed_usd <= (high + RECONCILE_TOLERANCE_USD)
        multiplier_real = implied is None or (
            multipliers["cache_write_5m"] - 0.01 <= implied <= multipliers["cache_write_1h"] + 0.01
        )
        agrees = bool(in_bracket and multiplier_real)

    return {
        "usd": billed_usd,
        "models": models,
        "tokens": totals,
        "rate_table_check": {
            "billed_usd": billed_usd,
            "repriced_usd_min": round(low, 6) if model_usage else None,
            "repriced_usd_max": round(high, 6) if model_usage else None,
            "implied_cache_write_multiplier": implied,
            "agrees": agrees,
        },
    }


def summarize(lines, rates):
    """Billed cost, per-agent attribution, and tool-call counts for one run."""
    table = rates.get("rates", {})
    multipliers = rates["multipliers"]
    default_model = rates.get("_default", "")

    subagents = _subagent_map(lines)
    per_agent = collections.defaultdict(_empty_counts)
    per_agent_models = collections.defaultdict(collections.Counter)
    per_agent_tools = collections.defaultdict(collections.Counter)
    per_agent_turns = collections.Counter()
    # Seed every agent the run launched, so one that produced no turns in this
    # transcript still appears at zero rather than vanishing. A background
    # (async) subagent is the case that matters: runs 3 and 5 both saw `policy`
    # go fully async, and a summary that silently omits security-engineer reads
    # as "main did all the work" -- the invisibility this instrument exists to
    # end. Zero tokens against a named agent is a measurement; absence is not.
    for agent_name in subagents.values():
        _ = per_agent[agent_name]
    tools = collections.Counter()
    unpriced = set()
    attributed_usd = 0.0
    parse_errors = 0

    for obj, ok in _iter_objects(lines):
        if not ok:
            parse_errors += 1
            continue
        parent = obj.get("parent_tool_use_id")
        agent = "main" if parent is None else subagents.get(parent, f"unattributed:{parent}")

        usage = _usage_of(obj)
        if usage:
            model = _message(obj).get("model") or default_model
            rate, priced = _resolve_rate(model, table, default_model)
            if not priced:
                unpriced.add(model)
            for key, value in usage.items():
                per_agent[agent][key] += value
            per_agent_models[agent][model] += 1
            per_agent_turns[agent] += 1
            attributed_usd += _price(usage, rate, multipliers)

        for name in _tools_of(obj):
            tools[name] += 1
            per_agent_tools[agent][name] += 1

    agents, totals = {}, _empty_counts()
    for agent in sorted(set(per_agent) | set(per_agent_tools)):
        counts = per_agent.get(agent, _empty_counts())
        models = per_agent_models.get(agent, collections.Counter())
        rate_for, _ = _resolve_rate(next(iter(models), default_model), table, default_model)
        agents[agent] = dict(
            counts,
            tokens=sum(counts.values()),
            usd=round(_price(counts, rate_for, multipliers), 6),
            models=sorted(models),
            tools=dict(sorted(per_agent_tools.get(agent, {}).items())),
            turns=per_agent_turns.get(agent, 0),
        )
        for key in totals:
            totals[key] += counts[key]
    # Named by a task_started line but contributing no measured turn -- almost
    # always a background/async subagent. Called out explicitly so a reader is
    # never left inferring it from a zero.
    launched_without_turns = sorted(
        name for name in set(subagents.values()) if per_agent_turns.get(name, 0) == 0
    )

    billed = _billed(lines, rates)
    coverage = None
    if billed["usd"]:
        coverage = round(attributed_usd / billed["usd"], 4)

    return {
        "billed": billed,
        "attributed": {
            "total": dict(totals, tokens=sum(totals.values()), usd=round(attributed_usd, 6)),
            "agents": agents,
            "coverage_of_billed": coverage,
            "launched_without_measured_turns": launched_without_turns,
            "_note": "Per-agent shares derived from per-turn usage. Excludes thinking "
                     "tokens and is scoped differently from the billed ledger, so this "
                     "does not equal `billed.usd`; coverage_of_billed reports the gap "
                     "and can exceed 1.0 when subagent turns are counted here but not "
                     "in the result line's own usage.",
        },
        "tools": dict(sorted(tools.items())),
        "final_text": final_text(lines),
        "unpriced_models": sorted(unpriced),
        "parse_errors": parse_errors,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Price one eval run from its transcript.")
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--rates", required=True)
    ap.add_argument(
        "--text-only",
        action="store_true",
        help="print only the reconstituted final answer text (for rebuilding the log)",
    )
    args = ap.parse_args(argv)

    try:
        with open(args.transcript, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        print(f"eval-cost: cannot read transcript: {exc}", file=sys.stderr)
        return 2

    if args.text_only:
        text = final_text(lines)
        if text is None:
            print("eval-cost: no final text in transcript", file=sys.stderr)
            return 2
        print(text)
        return 0

    with open(args.rates, encoding="utf-8") as fh:
        rates = json.load(fh)

    print(json.dumps(summarize(lines, rates), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
