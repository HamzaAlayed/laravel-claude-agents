# Agent Accuracy & Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the eval harness a trustworthy per-agent cost measurement, land the three held literature-gap tranche items, and settle whether per-subagent effort is a lever — so the next cost decision is made from data instead of intuition.

**Architecture:** The harness gains one flag (`--output-format stream-json --verbose`) whose transcript is parsed by a new standalone Python script into a per-case cost summary, then discarded. Because the answer key greps the human-readable log, the log is reconstituted from the transcript's `result` field rather than replaced — scoring must not change. The three tranche items are prose appended to `agents/delivery-coordinator.md` alone. The effort spike is research with two fully-specified outcomes.

**Tech Stack:** bash (the harness), python3 stdlib only (the parser — no pip installs; macOS ships python3 and CI has it), JSON for the rate table and baselines.

## Global Constraints

- **Accuracy first, then cost, then speed.** Cost savings come from waste, never from less checking.
- **No answer-key changes and no new eval cases.** Run 6 must stay comparable to run 5. `ALL_CASES` stays `(n-plus-one policy action tests hygiene)`; every `checks_*` function keeps its current regexes and keeps reading `$LOG`.
- **No model-tier changes and no agent-body slimming.** Argued and rejected in the spec.
- **Only `agents/delivery-coordinator.md`** changes among agent bodies (prose). The 9 pipeline commands' byte-identical `Interface` block must stay byte-identical — a guardrail test enforces this.
- **python3 stdlib only.** No `pip install`. CI runs `python3 -m unittest`; there is no requirements file for test deps.
- **Do not hand-edit `gemini/` or `codex/`** — regenerate with `scripts/build-gemini-extension.py` and `scripts/build-codex-extension.py`.
- **The guardrail test idiom is `expect "<name>" "<expected>" "<actual>"`** in `tests/guardrails.test.sh`. Run the suite with `bash tests/guardrails.test.sh`; it prints `total: N passed, 0 failed` and `ALL GREEN`.
- **Eval run 6 is NOT part of this plan.** It makes real billed `claude -p` calls. The deliverable is a harness that would produce a clean baseline, verified against a recorded fixture.
- Run every command from the repo root: `/Users/developer/Projects/Personal/laravel-claude-agents`.

---

### Task 1: Capture one real stream-json transcript and record its shape

**Files:**
- Create: `tests/eval/fixtures/stream-json-sample.jsonl`
- Create: `tests/eval/fixtures/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/eval/fixtures/stream-json-sample.jsonl` — a real recorded transcript that Task 2's parser is written against and its tests run on. Also produces a documented record of which JSON keys carry usage and tool-call data.

**Why this is its own task.** In v1.27.0 this repo shipped a console where `events.normalize` was written against the CLI's stream-json format while the Python SDK actually yields typed dataclasses. 62/62 tests passed and the browser received zero events, because the fixtures were written from the spec instead of from the dependency. Do not write the parser from an assumed shape. Record the real thing first.

- [ ] **Step 1: Capture a real transcript**

The prompt is deliberately trivial and read-only — this is a shape probe, not an eval. It should cost cents and finish in seconds.

```bash
cd /Users/developer/Projects/Personal/laravel-claude-agents
mkdir -p tests/eval/fixtures
claude -p "List the files in the current directory, then stop." \
  --output-format stream-json --verbose \
  > /tmp/stream-probe.jsonl 2>&1
wc -l /tmp/stream-probe.jsonl
```

If `claude` is not on PATH, use the same override the harness uses: `CLAUDE_BIN`. If the command fails for auth reasons, STOP and report BLOCKED — every later task depends on this shape.

- [ ] **Step 2: Inspect the shape and write down what you find**

```bash
python3 -c "
import json,sys,collections
types=collections.Counter(); keys={}
for line in open('/tmp/stream-probe.jsonl'):
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except json.JSONDecodeError: print('NON-JSON LINE:', line[:120]); continue
    t=o.get('type','<no type>'); types[t]+=1
    keys.setdefault(t,set()).update(o.keys())
for t,n in types.most_common():
    print(f'{t:24} x{n}  keys={sorted(keys[t])}')
"
```

Then find where token usage lives and whether a final result string exists:

```bash
python3 -c "
import json
for line in open('/tmp/stream-probe.jsonl'):
    line=line.strip()
    if not line: continue
    o=json.loads(line)
    if 'usage' in json.dumps(o)[:2000] or o.get('type')=='result':
        print(json.dumps(o)[:900]); print('---')
"
```

- [ ] **Step 3: Save the sample and document the shape**

Copy the probe to the fixtures directory. If it contains absolute paths from your machine, that is fine — it is a shape fixture, not an assertion fixture.

```bash
cp /tmp/stream-probe.jsonl tests/eval/fixtures/stream-json-sample.jsonl
```

Write `tests/eval/fixtures/README.md` recording exactly what you observed. **Every `<...>` below is a slot for a value you just read off the two commands in Step 2 — none of them are decisions or deferrals.** This file is the contract Task 2 codes against, so a guessed value here becomes a parser bug there:

```markdown
# Eval fixtures

## stream-json-sample.jsonl

A real `claude -p --output-format stream-json --verbose` transcript, captured
<DATE> against this repo with the prompt "List the files in the current
directory, then stop." It exists because writing a parser from an assumed wire
format is how v1.27.0 shipped a console that emitted zero events with a green
suite.

Observed line types and the keys each carries:

| `type` | count | keys |
| --- | --- | --- |
| <type> | <n> | <keys> |

**Where the final answer text lives:** <exact path, e.g. the `result` key on the
single `type: "result"` line>

**Where token usage lives:** <exact path, e.g. `usage.input_tokens` /
`usage.output_tokens` on `type: "assistant"` lines>

**Where the acting agent is identified (if at all):** <exact path, or "not
present — see Task 2's fallback">

**Where tool calls appear:** <exact path, e.g. `message.content[].type ==
"tool_use"` with `.name`>

Re-capture with the command in the plan's Task 1 if the CLI's format changes.
```

- [ ] **Step 4: Commit**

```bash
git add tests/eval/fixtures/
git commit -m "test(eval): record a real stream-json transcript before parsing one

Writing a parser from an assumed wire format is how 1.27.0 shipped a console
that emitted zero events with 62/62 green. The shape gets recorded first."
```

---

### Task 2: `scripts/eval-cost.py` — transcript to cost summary

**Files:**
- Create: `scripts/eval-cost.py`
- Create: `tests/eval/model-rates.json`
- Create: `tests/eval/test_eval_cost.py`
- Read: `tests/eval/fixtures/README.md` (Task 1's shape record — this is your spec)

**Interfaces:**
- Consumes: `tests/eval/fixtures/stream-json-sample.jsonl` and the shape documented in `tests/eval/fixtures/README.md`.
- Produces:
  - CLI: `python3 scripts/eval-cost.py --transcript <path> --rates <path> [--agent-model <json>] ` printing the summary JSON to stdout, exit 0 on success and 2 on an unparsable transcript.
  - `summarize(lines: list[str], rates: dict, agent_models: dict) -> dict` returning `{"total": {...}, "agents": {...}, "tools": {...}, "final_text": str|None, "parse_errors": int}`.
  - `final_text(lines: list[str]) -> str | None` — the reconstituted answer text, used by Task 3.

- [ ] **Step 1: Write the rate table**

`tests/eval/model-rates.json` — dollars per million tokens, with its source and date so a stale price is visible rather than silently wrong:

```json
{
  "_source": "Anthropic model catalog via the claude-api skill, checked 2026-08-04. Sonnet 5 list price; the $2/$10 introductory rate through 2026-08-31 is deliberately NOT used — a baseline built on a promo price silently regresses on 2026-09-01.",
  "_unit": "USD per 1,000,000 tokens",
  "rates": {
    "claude-opus-5":    { "input": 5.0, "output": 25.0 },
    "claude-opus-4-8":  { "input": 5.0, "output": 25.0 },
    "claude-fable-5":   { "input": 10.0, "output": 50.0 },
    "sonnet":           { "input": 3.0, "output": 15.0 },
    "claude-sonnet-5":  { "input": 3.0, "output": 15.0 },
    "haiku":            { "input": 1.0, "output": 5.0 },
    "claude-haiku-4-5": { "input": 1.0, "output": 5.0 }
  },
  "_default": "sonnet"
}
```

- [ ] **Step 2: Write the failing tests**

`tests/eval/test_eval_cost.py`. These run under `python3 -m unittest` with no third-party imports. **Before writing the assertions about the real fixture, open `tests/eval/fixtures/README.md` and use the key paths it records** — the synthetic transcripts below must be built from those same paths, or the tests pass against a format the CLI does not emit.

```python
"""Unit tests for scripts/eval-cost.py.

The synthetic transcripts here mirror the key paths recorded in
tests/eval/fixtures/README.md. If the CLI format changes, re-capture the
fixture, update the README, and update these builders -- do not invent a shape.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "eval_cost", ROOT / "scripts" / "eval-cost.py"
)
eval_cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_cost)

RATES = json.loads((ROOT / "tests" / "eval" / "model-rates.json").read_text())


def assistant_line(input_tokens, output_tokens, tools=(), agent=None):
    """One assistant turn. Key paths per fixtures/README.md."""
    content = [{"type": "text", "text": "ok"}]
    for name in tools:
        content.append({"type": "tool_use", "name": name, "input": {}})
    obj = {
        "type": "assistant",
        "message": {
            "content": content,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        },
    }
    if agent is not None:
        obj["agent"] = agent
    return json.dumps(obj)


def result_line(text):
    return json.dumps({"type": "result", "subtype": "success", "result": text})


class TestFinalText(unittest.TestCase):
    def test_returns_the_result_field(self):
        lines = [assistant_line(10, 5), result_line("the final answer")]
        self.assertEqual(eval_cost.final_text(lines), "the final answer")

    def test_falls_back_to_concatenated_assistant_text_when_no_result(self):
        # A timed-out or killed run never emits a result line. Run 4 had a
        # timeout; the log must not come back empty in that case.
        lines = [assistant_line(10, 5)]
        self.assertEqual(eval_cost.final_text(lines), "ok")

    def test_returns_none_on_an_empty_transcript(self):
        self.assertIsNone(eval_cost.final_text([]))


class TestSummarize(unittest.TestCase):
    def test_totals_input_and_output_separately(self):
        lines = [assistant_line(1000, 200), assistant_line(500, 100), result_line("x")]
        out = eval_cost.summarize(lines, RATES, {})
        self.assertEqual(out["total"]["input_tokens"], 1500)
        self.assertEqual(out["total"]["output_tokens"], 300)

    def test_prices_output_at_five_times_input_on_sonnet(self):
        # 1M input + 1M output at sonnet = 3.0 + 15.0
        lines = [assistant_line(1_000_000, 1_000_000), result_line("x")]
        out = eval_cost.summarize(lines, RATES, {})
        self.assertAlmostEqual(out["total"]["usd"], 18.0, places=4)

    def test_uses_each_agent_pinned_model_rate(self):
        lines = [
            assistant_line(1_000_000, 0, agent="security-engineer"),
            assistant_line(1_000_000, 0, agent="qa-engineer"),
            result_line("x"),
        ]
        out = eval_cost.summarize(
            lines, RATES,
            {"security-engineer": "claude-opus-5", "qa-engineer": "sonnet"},
        )
        self.assertAlmostEqual(out["agents"]["security-engineer"]["usd"], 5.0, places=4)
        self.assertAlmostEqual(out["agents"]["qa-engineer"]["usd"], 3.0, places=4)

    def test_unknown_agent_falls_back_to_the_default_rate(self):
        lines = [assistant_line(1_000_000, 0, agent="not-a-real-agent"), result_line("x")]
        out = eval_cost.summarize(lines, RATES, {})
        self.assertAlmostEqual(out["agents"]["not-a-real-agent"]["usd"], 3.0, places=4)

    def test_counts_tool_calls_by_name(self):
        lines = [
            assistant_line(10, 5, tools=["Read", "Read", "Bash"]),
            assistant_line(10, 5, tools=["Read"]),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES, {})
        self.assertEqual(out["tools"]["Read"], 3)
        self.assertEqual(out["tools"]["Bash"], 1)

    def test_counts_unparsable_lines_instead_of_crashing(self):
        # The harness redirects stderr into the same stream, so a warning line
        # can land in the middle of the transcript. One bad line must not lose
        # the whole run's cost data.
        lines = [assistant_line(10, 5), "some stderr warning", result_line("x")]
        out = eval_cost.summarize(lines, RATES, {})
        self.assertEqual(out["parse_errors"], 1)
        self.assertEqual(out["total"]["input_tokens"], 10)


class TestRealFixture(unittest.TestCase):
    def test_parses_the_recorded_transcript_without_errors(self):
        fixture = ROOT / "tests" / "eval" / "fixtures" / "stream-json-sample.jsonl"
        lines = fixture.read_text().splitlines()
        out = eval_cost.summarize(lines, RATES, {})
        # The whole point of the fixture: a real transcript parses cleanly.
        self.assertEqual(out["parse_errors"], 0, "real transcript had unparsable lines")
        self.assertGreater(out["total"]["input_tokens"], 0, "no usage found in a real run")
        self.assertIsNotNone(eval_cost.final_text(lines), "no final text in a real run")


class TestCLI(unittest.TestCase):
    def test_prints_json_and_exits_zero(self):
        fixture = ROOT / "tests" / "eval" / "fixtures" / "stream-json-sample.jsonl"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "eval-cost.py"),
             "--transcript", str(fixture),
             "--rates", str(ROOT / "tests" / "eval" / "model-rates.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)  # raises if not valid JSON

    def test_exits_two_on_a_missing_transcript(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "eval-cost.py"),
             "--transcript", "/nonexistent/nope.jsonl",
             "--rates", str(ROOT / "tests" / "eval" / "model-rates.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' -v`
Expected: FAIL — `scripts/eval-cost.py` does not exist, so `spec_from_file_location` raises at import.

- [ ] **Step 4: Implement the parser**

`scripts/eval-cost.py`. **Adjust the key paths in `_usage_of`, `_agent_of`, and `_tools_of` to match what `tests/eval/fixtures/README.md` recorded** — the bodies below encode the expected shape, and the real fixture test in Step 2 is what proves you got it right.

```python
#!/usr/bin/env python3
"""Turn one `claude -p --output-format stream-json --verbose` transcript into a
per-agent cost summary.

Why this exists: the eval harness measured correctness and latency but never
cost, and the only cost signal it did emit (per-agent totals on the board feed)
carries no input/output split. Output costs 5x input on every tier, so a total
without the split cannot be priced -- it can only be guessed at.

Key paths are documented in tests/eval/fixtures/README.md, recorded from a real
transcript rather than assumed. If the CLI format changes, re-capture the
fixture and update both.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys

PER_MILLION = 1_000_000


def _iter_objects(lines):
    """Yield (obj, ok) for each non-blank line. Bad lines yield (None, False).

    The harness redirects stderr into the same stream, so a warning can land
    mid-transcript. One bad line must not cost the whole run's data.
    """
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line), True
        except json.JSONDecodeError:
            yield None, False


def _usage_of(obj):
    """(input_tokens, output_tokens) for one object, or None if it carries none."""
    usage = (obj.get("message") or {}).get("usage") or obj.get("usage")
    if not isinstance(usage, dict):
        return None
    return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)


def _agent_of(obj):
    """Which agent produced this turn. `main` when the transcript does not say.

    The CLI does not necessarily label turns by subagent; when it does not,
    everything lands under `main` and the per-agent breakdown degrades to a
    single bucket. That is a documented limitation, not a silent one -- the
    summary's `agents` map will simply have one key.
    """
    return obj.get("agent") or obj.get("agent_type") or "main"


def _tools_of(obj):
    """Tool names invoked in this turn."""
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [
        block.get("name")
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name")
    ]


def _text_of(obj):
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text") or ""
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def final_text(lines):
    """The run's final answer, matching what plain `claude -p` prints.

    Plain `-p` output IS the result field, so taking it keeps the answer key's
    greps reading exactly what they read before this change. A run that times
    out or is killed never emits a result line -- run 4 had a timeout -- so fall
    back to the concatenated assistant text rather than returning nothing.
    """
    assistant_text = []
    for obj, ok in _iter_objects(lines):
        if not ok:
            continue
        if obj.get("type") == "result" and isinstance(obj.get("result"), str):
            return obj["result"]
        assistant_text.append(_text_of(obj))
    joined = "".join(assistant_text)
    return joined or None


def summarize(lines, rates, agent_models):
    """Per-agent input/output tokens, dollars, and tool-call counts."""
    table = rates.get("rates", {})
    default_model = rates.get("_default", "sonnet")
    agents = collections.defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})
    tools = collections.Counter()
    parse_errors = 0

    for obj, ok in _iter_objects(lines):
        if not ok:
            parse_errors += 1
            continue
        usage = _usage_of(obj)
        if usage:
            agent = _agent_of(obj)
            agents[agent]["input_tokens"] += usage[0]
            agents[agent]["output_tokens"] += usage[1]
        for name in _tools_of(obj):
            tools[name] += 1

    out_agents = {}
    total_in = total_out = 0
    total_usd = 0.0
    for agent, counts in sorted(agents.items()):
        model = agent_models.get(agent, default_model)
        rate = table.get(model) or table.get(default_model) or {"input": 0.0, "output": 0.0}
        usd = (
            counts["input_tokens"] * rate["input"] / PER_MILLION
            + counts["output_tokens"] * rate["output"] / PER_MILLION
        )
        out_agents[agent] = {
            "model": model,
            "input_tokens": counts["input_tokens"],
            "output_tokens": counts["output_tokens"],
            "usd": round(usd, 6),
        }
        total_in += counts["input_tokens"]
        total_out += counts["output_tokens"]
        total_usd += usd

    return {
        "total": {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "tokens": total_in + total_out,
            "usd": round(total_usd, 6),
        },
        "agents": out_agents,
        "tools": dict(sorted(tools.items())),
        "final_text": final_text(lines),
        "parse_errors": parse_errors,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--rates", required=True)
    ap.add_argument(
        "--agent-model",
        default="{}",
        help='JSON object mapping agent slug -> model id, e.g. {"qa-engineer":"sonnet"}',
    )
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

    with open(args.rates, encoding="utf-8") as fh:
        rates = json.load(fh)

    if args.text_only:
        text = final_text(lines)
        if text is None:
            return 2
        print(text)
        return 0

    print(json.dumps(summarize(lines, rates, json.loads(args.agent_model)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py' -v`
Expected: PASS, all cases. If `TestRealFixture` fails, the key paths in `_usage_of` / `_agent_of` / `_tools_of` do not match what the CLI actually emits — fix them against `tests/eval/fixtures/README.md`, not by loosening the test.

- [ ] **Step 6: Wire the new suite into CI**

`.github/workflows/ci.yml` already runs the console python units. Find that step and add a sibling step so the eval-cost suite runs too. Read the file first and match its existing style:

```yaml
      - name: eval cost parser units
        run: python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
```

- [ ] **Step 7: Commit**

```bash
git add scripts/eval-cost.py tests/eval/model-rates.json tests/eval/test_eval_cost.py .github/workflows/ci.yml
git commit -m "feat(eval): price a run from its transcript, input and output split

Output costs 5x input on every tier, so a per-agent total without the split
cannot be priced. Parses the real recorded transcript shape; a stderr line
landing mid-stream costs one line, not the run."
```

---

### Task 3: Harness captures the transcript, rebuilds the log, writes the cost summary

**Files:**
- Modify: `tests/eval/run-evals.sh` (the `run_case` function, around lines 383–445)
- Modify: `tests/guardrails.test.sh` (new ratchets near the existing eval-harness ones, around line 396)

**Interfaces:**
- Consumes: `scripts/eval-cost.py` CLI from Task 2 — `--transcript`, `--rates`, `--agent-model`, `--text-only`; exit 2 on failure.
- Produces: `<results>/<case>.cost.json` per case; `$LOG` unchanged in *format* (still the final answer text). No new interface for later tasks.

**The load-bearing risk.** `--output-format stream-json` makes `claude -p` emit JSON lines instead of the answer text. Every `checks_*` function greps `$LOG` for answer-key patterns. If `$LOG` becomes JSON, the answer key silently starts matching against tool inputs and thinking text, and run 6 stops being comparable to run 5 — which the Global Constraints forbid. So: capture the stream to a separate file, rebuild `$LOG` from its `result` field (plain `-p` output *is* that field), and only then run the checks.

- [ ] **Step 1: Write the failing ratchets**

Append to `tests/guardrails.test.sh`, in the eval-harness section near the existing `"the eval harness starts each feed empty"` assertion:

```bash
# The answer key greps $LOG. If stream-json landed in $LOG directly, every
# check_log would start matching tool inputs and thinking text, and run 6 would
# stop being comparable to run 5. The transcript goes to its own file and $LOG
# is rebuilt from the result field.
expect "the eval harness captures stream-json to its own file" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'output-format stream-json')"
expect "the eval harness rebuilds the log from the transcript" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'eval-cost\.py.*--text-only')"
expect "the eval harness writes a per-case cost summary" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'cost\.json')"
# Megabytes per case, and tests/eval/results/ is committed.
expect "the eval harness discards the raw transcript" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'rm -f .*stream\.jsonl')"
# Checks must read the human-readable log, never the transcript.
expect "no checks function reads the raw transcript" "0" \
  "$(sed -n '/^checks_/,/^}/p' "$SCRIPT_DIR/tests/eval/run-evals.sh" \
     | grep -cE 'stream\.jsonl' || true)"
```

- [ ] **Step 2: Run the suite to verify the new ratchets fail**

Run: `bash tests/guardrails.test.sh`
Expected: FAIL — 4 of the 5 new assertions report `0` where `1` is expected (the last one already passes trivially, which is correct: it is a regression guard, not a new feature).

- [ ] **Step 3: Change the capture in `run_case`**

In `tests/eval/run-evals.sh`, find this block inside `run_case` (currently around line 417):

```bash
  local -a cmd=("$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions)
  if [ -n "${EVAL_MODEL:-}" ]; then
    cmd+=(--model "$EVAL_MODEL")
  fi

  local start=$SECONDS rc=0
  (cd "$WORK" && run_with_timeout "$EVAL_TIMEOUT" "${cmd[@]}") >"$LOG" 2>&1 || rc=$?
  local dur=$((SECONDS - start))
```

Replace it with:

```bash
  # stream-json (not plain text) so the transcript carries per-turn `usage` with
  # the input/output split -- the only way to price a run rather than guess at
  # it. It does NOT go to $LOG: the answer key greps $LOG, and JSON there would
  # silently start matching tool inputs. $LOG is rebuilt below from the result
  # field, which is exactly what plain `-p` prints.
  local -a cmd=("$CLAUDE_BIN" -p "$prompt" --dangerously-skip-permissions
                --output-format stream-json --verbose)
  if [ -n "${EVAL_MODEL:-}" ]; then
    cmd+=(--model "$EVAL_MODEL")
  fi

  local stream="$results/$name.stream.jsonl"
  local start=$SECONDS rc=0
  (cd "$WORK" && run_with_timeout "$EVAL_TIMEOUT" "${cmd[@]}") >"$stream" 2>&1 || rc=$?
  local dur=$((SECONDS - start))

  # Rebuild the human-readable log the checks and the findings doc both read. A
  # timed-out run emits no result line, so eval-cost falls back to concatenated
  # assistant text; if even that is empty it exits 2 and we keep the raw stream
  # as the only evidence rather than leaving an empty log with no explanation.
  if python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
       --rates "$ROOT/tests/eval/model-rates.json" --text-only >"$LOG" 2>/dev/null; then
    :
  else
    echo "   WARNING: no final text in the transcript — keeping $name.stream.jsonl"
    cp "$stream" "$results/$name.stream-kept.jsonl"
  fi

  # Per-agent input/output tokens, tool-call counts, dollars at each agent's
  # pinned model rate.
  python3 "$ROOT/scripts/eval-cost.py" --transcript "$stream" \
    --rates "$ROOT/tests/eval/model-rates.json" \
    --agent-model "$(agent_model_map)" >"$results/$name.cost.json" 2>/dev/null \
    || echo "   WARNING: could not summarise cost for $name"

  # Megabytes per case, and tests/eval/results/ is committed. The derived
  # summary is the artifact; the raw stream is scaffolding.
  rm -f "$stream"
```

- [ ] **Step 4: Add the agent→model map helper**

The rate table needs to know each agent's pinned model. Read it from the bodies rather than duplicating it — a hardcoded copy drifts the moment someone re-tiers an agent. Add this function to `tests/eval/run-evals.sh` just above `run_case`:

```bash
# agent slug -> pinned model, read from the bodies so a re-tier cannot silently
# leave the cost summary pricing the old model.
agent_model_map() {
  python3 - "$ROOT/agents" <<'PY'
import json, pathlib, re, sys
out = {}
for path in sorted(pathlib.Path(sys.argv[1]).glob("*.md")):
    head = path.read_text(encoding="utf-8").split("---")
    block = head[1] if len(head) > 2 else ""
    match = re.search(r"^model:\s*(\S+)\s*$", block, re.M)
    if match:
        out[path.stem] = match.group(1)
print(json.dumps(out))
PY
}
```

- [ ] **Step 5: Print the cost line in the per-case output**

Immediately after the existing verdict line in `run_case` (currently `echo "   $verdict — $CHECK_PASS/$((CHECK_PASS + CHECK_FAIL)) checks, ${dur}s"`), add:

```bash
  if [ -s "$results/$name.cost.json" ]; then
    python3 - "$results/$name.cost.json" <<'PY' || true
import json, sys
d = json.load(open(sys.argv[1]))
t = d["total"]
print(f"   cost: {t['tokens']:,} tokens ({t['input_tokens']:,} in / {t['output_tokens']:,} out), ${t['usd']:.2f}")
top = sorted(d["agents"].items(), key=lambda kv: -kv[1]["input_tokens"] - kv[1]["output_tokens"])[:3]
for agent, a in top:
    print(f"         {agent:22} {a['input_tokens'] + a['output_tokens']:>9,} tok  ${a['usd']:.2f}  ({a['model']})")
PY
  fi
```

- [ ] **Step 6: Run the guardrail suite to verify the ratchets pass**

Run: `bash tests/guardrails.test.sh`
Expected: PASS — `ALL GREEN`, with the total up by 5 from its previous value.

- [ ] **Step 7: Verify the harness is still syntactically valid and shellcheck-clean**

CI runs strict shellcheck where info-level findings fail the build.

```bash
bash -n tests/eval/run-evals.sh && echo "SYNTAX OK"
shellcheck tests/eval/run-evals.sh && echo "SHELLCHECK CLEAN"
```

If shellcheck flags the heredocs inside a function (SC2329/SC2317 are already suppressed elsewhere in this file for dynamically-dispatched functions — check how), follow the existing suppression style in the file rather than inventing a new one.

- [ ] **Step 8: Commit**

```bash
git add tests/eval/run-evals.sh tests/guardrails.test.sh
git commit -m "feat(eval): capture the transcript, price the run, keep the log intact

The answer key greps \$LOG, so stream-json goes to its own file and the log is
rebuilt from the result field -- which is exactly what plain -p prints. Run 6
stays comparable to run 5. Raw transcripts are megabytes and results/ is
committed, so the derived summary is the artifact and the stream is discarded."
```

---

### Task 4: Token ceilings in `baseline.json`

**Files:**
- Modify: `tests/eval/baseline.json`
- Modify: `tests/eval/run-evals.sh` (the ceiling comparison, currently around lines 451–465)
- Modify: `tests/guardrails.test.sh`

**Interfaces:**
- Consumes: `<results>/<case>.cost.json` from Task 3.
- Produces: nothing later tasks depend on.

**Why `null` and not a number.** Every token figure from runs 1–5 is contaminated by the fixture debris described in the spec, so there is no honest number to seed with. `null` means *unseeded*, the harness says so out loud, and run 6 fills it in. A guessed ceiling would be worse than none: it would either always read REGRESSED or never fire, and run 5 already established that a ceiling which always reads REGRESSED stops carrying information.

- [ ] **Step 1: Write the failing ratchets**

Append to the eval section of `tests/guardrails.test.sh`:

```bash
# Cost had no ceiling at all, so a cost regression was invisible. Token ceilings
# ride alongside the duration ones and start null -- every token figure from
# runs 1-5 is contaminated (run-5 finding 1), so there is nothing honest to seed
# with until run 6.
expect "every eval case has a token-ceiling key" "" \
  "$(python3 - "$SCRIPT_DIR/tests/eval/baseline.json" "$SCRIPT_DIR/tests/eval/run-evals.sh" <<'PY'
import json, re, sys
base = json.load(open(sys.argv[1]))
cases = re.search(r"^ALL_CASES=\((.*)\)$", open(sys.argv[2]).read(), re.M).group(1).split()
missing = [c for c in cases if "max_tokens" not in base["cases"].get(c, {})]
print(" ".join(missing))
PY
)"
expect "the harness compares tokens against the ceiling" "1" \
  "$(sed 's/#.*//' "$SCRIPT_DIR/tests/eval/run-evals.sh" | grep -cE 'max_tokens')"
```

- [ ] **Step 2: Run the suite to verify they fail**

Run: `bash tests/guardrails.test.sh`
Expected: FAIL — the first prints all five case names, the second prints `0`.

- [ ] **Step 3: Add the ceilings**

Rewrite `tests/eval/baseline.json`, keeping every existing `max_seconds` and `basis` value byte-identical and adding `max_tokens` plus a token basis to each case:

```json
{
  "_source": "sequential run 5 (docs/evals/2026-07-31-run-5.md); parallel runs excluded — API contention inflates per-case durations 2-6x (run 3 finding)",
  "_policy": "soft ceilings: run-evals.sh prints 'within'/'REGRESSED', never fails the case; update ceilings after each accepted sequential run",
  "_tokens": "max_tokens is null until eval run 6. Every token figure from runs 1-5 is contaminated: three cases that delegated nothing each report an identical 48,895 qa-engineer tokens (run-5 finding 1, fixed for future runs in f12ad7c). A guessed ceiling would either always read REGRESSED or never fire; null means unseeded and the harness says so.",
  "cases": {
    "n-plus-one": { "max_seconds": 250, "basis": "run 5: 178s + headroom; creeping across runs (96 -> 157 -> 178)", "max_tokens": null, "tokens_basis": "unseeded — run 6 is the first clean measurement" },
    "policy":     { "max_seconds": 1100, "basis": "run 5: 994s, identical to run 4 — a stable cost, not a fluke. Deliberately accepts a 46% regression vs run 2's 681s rather than leaving a ceiling that always reads REGRESSED; the driver (security-engineer, 526s of the 994s) is run-5 finding 2, kept on the record instead of hidden by this number", "max_tokens": null, "tokens_basis": "unseeded — decontaminated run 5 suggests ~183k (backend 41,495 + qa 52,959 + security 88,625), but that is a subtraction, not a measurement" },
    "action":     { "max_seconds": 600, "basis": "run 5: 420s with NO delegation (the coordinator fast path took the case). The old 1200s was set when this case timed out. If the fast path stops taking it, this reads REGRESSED the first time it delegates again — that is the intended signal, not a false alarm", "max_tokens": null, "tokens_basis": "unseeded — run 5's figure for this case was entirely fixture debris (it delegated nothing)" },
    "tests":      { "max_seconds": 950, "basis": "run 5: 806s and 4/4. The old 800s came from run 2's 681s, and run 4's 298s was a case that skipped the authorization work it now does", "max_tokens": null, "tokens_basis": "unseeded — decontaminated run 5 suggests ~138k in a single qa-engineer invocation, the largest single lane in the run and this milestone's headline measurement target" },
    "hygiene":    { "max_seconds": 200, "basis": "run 5: 91s (scrum-master, read-only ledger scan) + headroom", "max_tokens": null, "tokens_basis": "unseeded — run 5's figure for this case was entirely fixture debris (it delegated nothing)" }
  }
}
```

- [ ] **Step 4: Extend the ceiling comparison**

In `tests/eval/run-evals.sh`, find the sequential-only baseline block (currently around line 451) and extend the inline python so it reports tokens too. Read the existing block first and keep its structure; the python body becomes:

```python
import json, sys
name, dur, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cost_path = sys.argv[4] if len(sys.argv) > 4 else None
case = json.load(open(path))["cases"].get(name)
cap = (case or {}).get("max_seconds")
if cap:
    state = "within" if dur <= cap else "REGRESSED vs"
    print(f"   baseline: {state} {cap}s ceiling ({dur}s)")
tok_cap = (case or {}).get("max_tokens")
actual = None
if cost_path:
    try:
        actual = json.load(open(cost_path))["total"]["tokens"]
    except Exception:
        actual = None
if actual is None:
    pass
elif tok_cap is None:
    print(f"   baseline: token ceiling unseeded ({actual:,} tokens this run)")
else:
    state = "within" if actual <= tok_cap else "REGRESSED vs"
    print(f"   baseline: {state} {tok_cap:,}-token ceiling ({actual:,} tokens)")
```

Pass the cost file as a fourth argument at the call site, alongside the existing three:

```bash
      python3 - "$name" "$dur" "$ROOT/tests/eval/baseline.json" "$results/$name.cost.json" <<'PY' || true
```

**One thing worth noticing while you are here.** The whole baseline block is gated on `[ "$MODE" = "sequential" ]`, because run 3 established that parallel API contention inflates per-case durations 2–6× — so parallel runs are documented as pass/fail smoke only. **Token counts do not inflate that way.** Contention costs wall-clock, not tokens: the same work bills the same either way. So the cost summary written in Step 3 of Task 3 is valid in parallel mode even though the duration ceiling is not, which makes a parallel run newly useful for cost measurement. Leave the gate as it is for now — moving the token comparison outside it is a judgment call for whoever reads run 6's numbers, and guessing at it here would be the blind tuning this milestone exists to avoid. Note it in the run-6 findings doc instead.

- [ ] **Step 5: Run the guardrail suite and shellcheck**

```bash
bash tests/guardrails.test.sh
bash -n tests/eval/run-evals.sh && shellcheck tests/eval/run-evals.sh && echo CLEAN
```
Expected: `ALL GREEN`, total up by 2 from Task 3's value, shellcheck clean.

- [ ] **Step 6: Commit**

```bash
git add tests/eval/baseline.json tests/eval/run-evals.sh tests/guardrails.test.sh
git commit -m "feat(eval): token ceilings ride alongside the duration ones

Cost had no ceiling, so a cost regression was invisible while a latency one
failed loudly. Ceilings start null on purpose: every token figure from runs 1-5
is contaminated, and a guessed ceiling either always reads REGRESSED or never
fires."
```

---

### Task 5: The three tranche items

**Files:**
- Modify: `agents/delivery-coordinator.md` (steps 3, 5, and 7, plus the closing checkpoint line)
- Modify: `scripts/body_budget.json` (reseed — the body grows)
- Modify: `tests/guardrails.test.sh`
- Regenerate: `gemini/**`, `codex/**` via the build scripts

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks depend on.

**Read first:** `docs/plans/2026-07-29-literature-gap-tranche.md` carries the full rationale and risk analysis for each item. The exact prose to insert is reproduced below so you do not have to cross-reference, but the risk notes there are worth reading before you touch the file.

- [ ] **Step 1: Write the failing ratchets**

Append to `tests/guardrails.test.sh`, near the other coordinator assertions:

```bash
# Literature-gap tranche (docs/plans/2026-07-29-literature-gap-tranche.md), gate
# cleared by eval run 5. Escalation fired on category only; NOT-CHECKED was
# collected and never consumed. Nothing bounded a run's total stages. A
# checkpoint wrote no resume state, so a delivery resumed tomorrow replayed work.
COORD="$SCRIPT_DIR/agents/delivery-coordinator.md"
expect "low confidence is its own stop trigger" "1" \
  "$(grep -c 'Low confidence is a stop trigger in its own right' "$COORD")"
expect "the board declares a stage budget" "1" \
  "$(grep -c 'State the stage budget on the board' "$COORD")"
expect "checkpoints flush resume state" "1" \
  "$(grep -c 'flush the resume state' "$COORD")"
# All three edit the coordinator ONLY. The 9 pipeline commands share a
# byte-identical Interface block; if a tranche edit leaked into it, these would
# diverge and delegation contracts would drift per command.
expect "the tranche touched no other agent body" "0" \
  "$(grep -l 'State the stage budget on the board' "$SCRIPT_DIR"/agents/*.md \
     | grep -cv 'delivery-coordinator.md' || true)"
```

- [ ] **Step 2: Run the suite to verify they fail**

Run: `bash tests/guardrails.test.sh`
Expected: FAIL — the first three print `0`.

- [ ] **Step 3: Item 1 — `NOT-CHECKED` becomes an escalation trigger**

Open `agents/delivery-coordinator.md` and find step 5 (integrate + persist). After its existing verification sentence, insert this paragraph verbatim:

```markdown
A return whose `NOT-CHECKED` covers the substance of its own brief is not a
completed stage — it is an unverified one wearing a `STATUS: done`. Treat it
like a failed success criterion: re-brief once naming the unchecked surface,
and if it comes back unchecked again, stop the lane and surface it as a
checkpoint. Low confidence is a stop trigger in its own right, independent of
the checkpoint categories.
```

Then find the closing **Human checkpoint required:** line and extend its preamble so category and confidence read as peers rather than one list — append to the existing categories, leaving them unchanged:

```markdown
— plus any stage that cannot verify the core of its own brief.
```

**The risk to be aware of:** over-triggering. A specialist that dumps every adjacent surface into `NOT-CHECKED` could stall a lane. The scoping words *the substance of its own brief* are load-bearing — do not broaden them to "any non-empty value".

- [ ] **Step 4: Item 2 — a declared stage budget**

Find step 3 (plan + print the board) and append this paragraph verbatim:

```markdown
State the stage budget on the board — the number of stages you expect this
delivery to take, and the condition that ends it (`done when: <the observable
thing>`). The board is a plan the human approved, so growing past that budget
is a re-plan, not a continuation: reprint the board with the new count and the
reason it grew, and get agreement before spending the extra stages. Three
re-plans on one delivery is a scoping failure — stop and hand the shape of the
problem back to the human.
```

Then find the board example in the same body and add the budget to its header line:

```
▶ invoices — make-feature · 4 stages · done when: subscription upgrade covered by green feature tests
```

- [ ] **Step 5: Item 3 — resume state at a blocking checkpoint**

Find step 7 (surface checkpoints) and append this paragraph verbatim:

```markdown
Before you block on a checkpoint, flush the resume state to
`docs/delivery/<feature>/log.md`: the board as printed, which lanes are open
and which paths they own, the exact question pending, and the options offered.
A checkpoint can outlive the session — a resumed delivery that has to
reconstruct its own position from a transcript it no longer has replays work
the human already paid for.
```

- [ ] **Step 6: Reseed the body budget**

The coordinator body grew, and `scripts/check_body_budget.py` is a ratchet that fails when any body exceeds its recorded size. A deliberate, reviewed growth is exactly what `--reseed` is for, and the convention is that it lands in the same commit.

```bash
python3 scripts/check_body_budget.py --reseed
git diff --stat scripts/body_budget.json
```

Expected: only `delivery-coordinator` grows. If any other agent's numbers move, you edited a file you should not have — revert it.

- [ ] **Step 7: Regenerate the mirrors**

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
git status --porcelain gemini/ codex/
```

Expected: the gemini coordinator body changes. Never hand-edit either tree.

- [ ] **Step 8: Run every gate**

```bash
bash tests/guardrails.test.sh
python3 scripts/check_body_budget.py
python3 scripts/check_inventory_sync.py
python3 scripts/check-hook-sync.py
```

Expected: `ALL GREEN` with the total up by 4 from Task 4's value; all three checkers print `ok:`. Counts do not change, so `check_inventory_sync.py` should be a no-op — if it complains, a claim drifted independently of this change and needs its own fix.

Also confirm the shared Interface block did not drift:

```bash
grep -l 'Your own final answer closes the same way' commands/*.md | wc -l
```
Expected: `9`.

- [ ] **Step 9: Commit**

```bash
git add agents/delivery-coordinator.md scripts/body_budget.json gemini/ codex/ tests/guardrails.test.sh
git commit -m "feat(agents): NOT-CHECKED escalates, the board declares a budget, checkpoints persist

The three held items from the 2026-07-29 literature audit, whose gate cleared
when eval run 5 reported. Escalation fired on category only while NOT-CHECKED
was collected and never consumed; nothing bounded a run's total stages; a
checkpoint wrote no resume state, so a delivery resumed tomorrow replayed work
the human already paid for. All three edit the coordinator alone."
```

---

### Task 6: The effort spike — settle it either way

**Files:**
- Modify: `docs/authoring-agents.md` (record the finding either way)
- Modify (branch A only): all 17 `agents/*.md` frontmatter, `scripts/body_budget.json`, `gemini/**`, `codex/**`, `tests/guardrails.test.sh`
- Modify (branch B only): nothing further

**Interfaces:**
- Consumes: nothing.
- Produces: a recorded verified-or-refuted fact, following the pack's existing convention for Claude Code facts.

**The question.** Does Claude Code subagent frontmatter accept an effort or thinking-depth setting? Current frontmatter across all 17 agents uses exactly six keys — `color`, `description`, `memory`, `model`, `name`, `tools` — and `effort` appears nowhere in the pack. If supported, it is the largest cost lever available, because effort scales thinking depth *and* tool-call volume, and this pack's agents differ enormously in failure cost. If unsupported, it must be recorded as a non-option rather than left as folklore someone re-derives next quarter.

- [ ] **Step 1: Check the official documentation**

Do not guess and do not infer from the Agent SDK or the Messages API — subagent frontmatter is a Claude Code surface with its own schema. Fetch the current subagents reference:

```
WebFetch https://code.claude.com/docs/en/sub-agents.md
  prompt: "List every field accepted in a subagent's YAML frontmatter, with its
  type and whether it is required. State explicitly whether any field controls
  reasoning effort, thinking depth, or token budget."
```

If that URL 404s, find the current one from `https://code.claude.com/docs/en/` rather than assuming a path. Also check the settings reference for a global or per-agent effort setting.

- [ ] **Step 2: Decide the branch and record the finding**

Append to `docs/authoring-agents.md` under its frontmatter documentation. **Branch A** if a field exists, **Branch B** if not. Write the observed field list either way — that list is worth having recorded regardless of the outcome:

```markdown
### Reasoning effort per agent

Checked against <URL> on <DATE>. The frontmatter fields Claude Code accepts are:
<the observed list>.

<Branch A:> `<field>` controls reasoning effort, so each agent declares one —
see the tiering table below.

<Branch B:> **No frontmatter field controls reasoning effort, thinking depth, or
token budget.** Effort is therefore not a per-agent lever in this pack; the only
depth control is the model tier in `model:`. Do not add an `effort:` key on the
strength of the Messages API's `output_config.effort` — that is a different
surface, and an unrecognised frontmatter key is silently ignored rather than
rejected, which would leave the pack looking tuned while changing nothing.
```

- [ ] **Step 3 (Branch A only): Apply the tiering**

If and only if Step 1 confirmed the field. Set it per agent by failure cost, not by convenience — the user's ruling was accuracy first, so the expensive reviewers keep their depth and the cheap reporters lose theirs:

| agents | effort | why |
| --- | --- | --- |
| security-engineer, solution-architect | highest supported | highest failure cost; a missed authz flaw or a wrong 3-year architecture call costs more than the tokens |
| tech-lead, performance-engineer, qa-engineer, backend-developer, database-developer | the documented default | review and build work; no evidence yet that either direction is right |
| scrum-master, product-owner, business-analyst, technical-writer | lowest supported | summarising, scoring, and drafting from artifacts others produced; low failure cost, cheap to redo |
| the rest | the documented default | leave alone absent evidence |

Add a guardrail ratchet asserting every agent declares the field, then reseed the body budget and regenerate the mirrors exactly as in Task 5 steps 6–8.

```bash
python3 scripts/check_body_budget.py --reseed
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
bash tests/guardrails.test.sh
python3 scripts/validate-frontmatter.py   # needs PyYAML; use a scratchpad venv
```

- [ ] **Step 4: Commit**

Branch A:

```bash
git add docs/authoring-agents.md agents/ scripts/body_budget.json gemini/ codex/ tests/guardrails.test.sh
git commit -m "feat(agents): declare reasoning effort per agent, by failure cost

Verified against the Claude Code subagent docs. The expensive reviewers keep
their depth; the summarisers lose theirs. Accuracy first, so the saving comes
from agents whose work is cheap to redo."
```

Branch B:

```bash
git add docs/authoring-agents.md
git commit -m "docs: reasoning effort is not a per-agent frontmatter lever

Checked against the Claude Code subagent docs rather than assumed. Recorded as a
non-option so nobody re-derives it, and specifically so nobody adds an effort:
key on the strength of the Messages API parameter -- an unrecognised frontmatter
key is ignored, not rejected, which would look tuned while changing nothing."
```

---

### Task 7: Release

**Files:**
- Modify: `VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`, `CHANGELOG.md`
- Regenerate: `gemini/gemini-extension.json` via the build script

**Interfaces:**
- Consumes: everything above.
- Produces: a tagged, pushed release.

**Version:** 1.31.0 — new capability (cost measurement) plus agent-behavior changes, no breaking change.

- [ ] **Step 1: Bump VERSION and the four hand-maintained manifests**

Bump `VERSION` **before** running the gemini build, since the mirror's manifest is generated from it. Since v1.28.0 `check_inventory_sync.py` walks all five manifests for `version` at any depth and fails if any differs — that check is what caught `.cursor-plugin/marketplace.json` sitting ten releases behind.

```bash
printf '1.31.0\n' > VERSION
for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json \
         .cursor-plugin/plugin.json .cursor-plugin/marketplace.json; do
  sed -i '' 's/"version": "1\.30\.0"/"version": "1.31.0"/' "$f"
done
grep -rn '"version"' .claude-plugin/*.json .cursor-plugin/*.json
```

- [ ] **Step 2: Regenerate the mirrors**

```bash
python3 scripts/build-gemini-extension.py
python3 scripts/build-codex-extension.py
grep -n '"version"' gemini/gemini-extension.json
```

- [ ] **Step 3: Write the changelog entry**

Add above the `## [1.30.0]` section in `CHANGELOG.md`, in the file's existing Keep-a-Changelog voice:

```markdown
## [1.31.0] - <DATE>

### Added

- **The eval harness can price a run.** It measured correctness and latency and
  never cost, and the one cost signal it did emit carried no input/output split —
  which matters because output costs five times input on every tier, so a total
  without the split can only be guessed at. Each case now captures its full
  transcript, derives a per-agent summary (input and output tokens, tool-call
  counts, dollars at each agent's pinned model rate), and discards the raw
  stream. `baseline.json` gains token ceilings beside its duration ones, so a
  cost regression fails the way a latency one already did. The ceilings start
  unseeded on purpose: every token figure from runs 1–5 is contaminated by
  committed fixture telemetry, and eval run 6 is the first honest measurement.
  The answer key is untouched — the transcript goes to its own file and the
  human-readable log is rebuilt from its result field, which is exactly what
  plain `claude -p` prints, so run 6 stays comparable to run 5.

### Changed

- **`NOT-CHECKED` now escalates.** Escalation fired on category alone — authn,
  authz, billing, PII, money, tenant isolation — while every stage return
  carried a `NOT-CHECKED` field that nothing consumed. A stage whose
  `NOT-CHECKED` swallowed the substance of its own brief advanced exactly like a
  verified one. It is now re-briefed once, then surfaced as a checkpoint; low
  confidence is a stop trigger in its own right.
- **The board declares a stage budget.** Both existing caps were local — lanes
  ≤2–3, retries ≤1 — and nothing bounded a delivery's total stages. The board
  now states the expected count and the observable condition that ends it, and
  growing past it is a re-plan the human agrees to rather than a continuation.
- **Checkpoints persist resume state.** A blocking checkpoint wrote nothing, so
  a delivery resumed the next day rebuilt its board position, open lanes, and
  pending question from a transcript the new session no longer had. It now
  flushes that state to the delivery log first.
```

- [ ] **Step 4: Run every gate**

```bash
python3 scripts/check_inventory_sync.py
python3 scripts/check_body_budget.py
python3 scripts/check-hook-sync.py
bash tests/guardrails.test.sh
python3 -m unittest discover -s tests/console -t tests/console
python3 -m unittest discover -s tests/eval -t tests/eval -p 'test_*.py'
bash -n tests/eval/run-evals.sh && shellcheck tests/eval/run-evals.sh
```

Expected: every checker prints `ok:`, both python suites `OK`, guardrails `ALL GREEN`, shellcheck silent. Frontmatter validation needs PyYAML:

```bash
SP=/private/tmp/claude-501/-Users-developer-Projects-Personal-laravel-claude-agents/8da544ff-d840-4416-9a47-2f7bcbeafba6/scratchpad
python3 -m venv "$SP/venv" && "$SP/venv/bin/pip" install -q pyyaml
"$SP/venv/bin/python" scripts/validate-frontmatter.py
```

The console bundle is untouched by this plan, so `git diff --exit-code -- scripts/console/dist` should already be clean — no rebuild needed.

- [ ] **Step 5: Commit, tag, push**

```bash
git add VERSION CHANGELOG.md .claude-plugin/ .cursor-plugin/ gemini/ codex/
git commit -m "release: 1.31.0 — cost becomes measurable, and confidence becomes a stop trigger"
git tag -a v1.31.0 -m "1.31.0 — cost becomes measurable, and confidence becomes a stop trigger"
git push origin main && git push origin v1.31.0
gh run watch "$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

- [ ] **Step 6: Create the GitHub release**

Tagging does not create a release, and this repo's "Latest" badge sat four versions stale because of exactly that.

```bash
SP=/private/tmp/claude-501/-Users-developer-Projects-Personal-laravel-claude-agents/8da544ff-d840-4416-9a47-2f7bcbeafba6/scratchpad
awk '/^## \[1\.31\.0\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md > "$SP/notes-1.31.0.md"
gh release create v1.31.0 --title "v1.31.0 — Cost becomes measurable" \
  --notes-file "$SP/notes-1.31.0.md" --latest
gh release list --limit 2
```

---

## After this plan

**Eval run 6** is the verification, and it is a human-run billed step outside this plan. When it runs: sequential, with `EVAL_JUDGE=1` set (the rubric judge shipped in v1.26.0 and has never been exercised against a real run). It measures the tranche's behavioral effect — watch `policy` and `tests`, the only two cases that delegate, for checkpoint over-triggering — and produces the first trustworthy cost baseline, from which `max_tokens` gets seeded and a findings doc written at `docs/evals/<date>-run-6.md`.

**qa-engineer's ~138k tokens in a single invocation** is the headline number to explain. It already carries both rules meant to bound it, so the next milestone's question is *why* — and the per-tool call counts in `<case>.cost.json` are what this plan builds to answer it.
