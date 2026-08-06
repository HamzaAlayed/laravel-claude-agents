"""Unit tests for scripts/eval-cost.py.

The synthetic transcripts here mirror the key paths recorded in
tests/eval/fixtures/README.md, captured from a real
`claude -p --output-format stream-json --verbose` run. If the CLI format
changes, re-capture the fixtures, update that README, and update these
builders -- do not invent a shape.

The strongest test in this file is TestRealFixture.test_reconciles_with_the_cli_own_total:
the CLI computes its own `total_cost_usd`, so the rate table can be checked
against the dependency's arithmetic instead of against our belief about it.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "eval" / "fixtures"
RATES_PATH = ROOT / "tests" / "eval" / "model-rates.json"

spec = importlib.util.spec_from_file_location("eval_cost", ROOT / "scripts" / "eval-cost.py")
eval_cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_cost)

RATES = json.loads(RATES_PATH.read_text())


def assistant_line(
    input_tokens=0,
    output_tokens=0,
    cache_1h=0,
    cache_5m=0,
    cache_read=0,
    tools=(),
    parent=None,
    model="claude-opus-5",
):
    """One assistant turn. Key paths per fixtures/README.md.

    Note `parent` is `parent_tool_use_id`: None on the main thread, and the
    spawning Agent tool_use id inside a subagent. There is no `agent` field.
    """
    content = [{"type": "text", "text": "ok"}]
    for name in tools:
        content.append({"type": "tool_use", "name": name, "input": {}})
    return json.dumps({
        "type": "assistant",
        "parent_tool_use_id": parent,
        "message": {
            "model": model,
            "content": content,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_1h + cache_5m,
                "cache_creation": {
                    "ephemeral_1h_input_tokens": cache_1h,
                    "ephemeral_5m_input_tokens": cache_5m,
                },
            },
        },
    })


def task_started_line(tool_use_id, subagent_type):
    """The system line that names a subagent. This is the attribution source."""
    return json.dumps({
        "type": "system",
        "subtype": "task_started",
        "tool_use_id": tool_use_id,
        "subagent_type": subagent_type,
        "task_id": "aa1",
    })


def result_line(text, total_cost_usd=None):
    obj = {"type": "result", "subtype": "success", "result": text}
    if total_cost_usd is not None:
        obj["total_cost_usd"] = total_cost_usd
    return json.dumps(obj)


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

    def test_the_fallback_excludes_user_turn_text(self):
        # Caught by running the harness against a result-less transcript: user
        # lines carry the prompt and tool results as text blocks. Folding those
        # into the rebuilt log lets an answer-key grep match the eval's own
        # prompt and report a false PASS on a timed-out run.
        user_line = json.dumps({
            "type": "user",
            "message": {"content": [{"type": "text", "text": "PROMPT-SENTINEL"}]},
        })
        lines = [user_line, assistant_line(10, 5)]
        text = eval_cost.final_text(lines)
        self.assertEqual(text, "ok")
        self.assertNotIn("PROMPT-SENTINEL", text)

    def test_the_fallback_excludes_tool_result_text_from_the_real_fixture(self):
        # Same guard, against the recorded transcript rather than a synthetic one:
        # the subagent probe's user turns carry the delegated prompt verbatim.
        lines = [
            l for l in (FIXTURES / "stream-json-subagent.jsonl").read_text().splitlines()
            if l.strip() and json.loads(l).get("type") != "result"
        ]
        text = eval_cost.final_text(lines)
        self.assertIsNotNone(text)
        self.assertNotIn("Run pwd and report", text)


class TestFullText(unittest.TestCase):
    """full_text() backs checks that assert on something the run says EARLY
    (e.g. a board header printed before any agent spends tokens) -- which
    `final_text`'s `result`-line shortcut structurally cannot see, because
    `result` is only ever the CLOSING turn. Run 7 (docs/evals/2026-08-06-run-7.md
    finding 3) found two checks scoring false negatives for exactly this reason.
    """

    def test_concatenates_every_assistant_turn_not_just_the_last(self):
        lines = [assistant_line(10, 5), result_line("closing summary")]
        # final_text short-circuits to the result line; full_text must not.
        self.assertEqual(eval_cost.final_text(lines), "closing summary")
        self.assertEqual(eval_cost.full_text(lines), "ok")

    def test_multiple_assistant_turns_all_appear_in_order(self):
        first = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "4 stages, done when: X"}]},
        })
        second = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "closing summary"}]},
        })
        text = eval_cost.full_text([first, second, result_line("closing summary")])
        self.assertIn("done when: X", text)
        self.assertIn("closing summary", text)

    def test_returns_none_on_an_empty_transcript(self):
        self.assertIsNone(eval_cost.full_text([]))

    def test_excludes_user_turn_text(self):
        # Same false-PASS risk final_text's fallback guards against: a user
        # turn's tool-result text must not leak into an answer-key grep.
        user_line = json.dumps({
            "type": "user",
            "message": {"content": [{"type": "text", "text": "PROMPT-SENTINEL"}]},
        })
        text = eval_cost.full_text([user_line, assistant_line(10, 5)])
        self.assertNotIn("PROMPT-SENTINEL", text)

    def test_excludes_subagent_turn_text(self):
        # check_log_anywhere asserts on something the ORCHESTRATOR says (a
        # board header it alone prints). Subagent turns are `assistant`-type
        # lines too, distinguished only by `parent_tool_use_id` -- folding
        # them in would let a specialist's own text satisfy an Interface
        # contract that only binds the orchestrator (final review finding 4).
        main_line = json.dumps({
            "type": "assistant",
            "parent_tool_use_id": None,
            "message": {"content": [{"type": "text", "text": "MAIN-THREAD-TEXT"}]},
        })
        subagent_line = json.dumps({
            "type": "assistant",
            "parent_tool_use_id": "toolu_subagent_1",
            "message": {"content": [{"type": "text", "text": "SUBAGENT-SENTINEL"}]},
        })
        text = eval_cost.full_text([main_line, subagent_line])
        self.assertIn("MAIN-THREAD-TEXT", text)
        self.assertNotIn("SUBAGENT-SENTINEL", text)

    def test_matches_final_text_on_a_timed_out_transcript(self):
        # A timed-out run never emits a `result` line: final_text() falls
        # back to concatenating assistant text, and (per this same finding)
        # that fallback must be indistinguishable from full_text()'s result
        # here -- otherwise a timed-out run's $LOG and $FULL_LOG would
        # silently diverge in a way no check could catch. This is the
        # equivalence run 7's addendum relies on to say a timed-out
        # teach-delivery re-run cannot confirm the check_log_anywhere fix.
        lines = [assistant_line(10, 5), assistant_line(3, 2)]
        self.assertEqual(eval_cost.final_text(lines), eval_cost.full_text(lines))


class TestPricing(unittest.TestCase):
    def test_totals_all_four_token_classes_separately(self):
        lines = [
            assistant_line(input_tokens=100, output_tokens=20, cache_1h=1000, cache_5m=500, cache_read=7000),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        t = out["attributed"]["total"]
        self.assertEqual(t["input_tokens"], 100)
        self.assertEqual(t["output_tokens"], 20)
        self.assertEqual(t["cache_write_1h_tokens"], 1000)
        self.assertEqual(t["cache_write_5m_tokens"], 500)
        self.assertEqual(t["cache_read_tokens"], 7000)

    def test_prices_output_at_five_times_input(self):
        # 1M input + 1M output on opus 5 = 5.0 + 25.0
        lines = [assistant_line(input_tokens=1_000_000, output_tokens=1_000_000), result_line("x")]
        out = eval_cost.summarize(lines, RATES)
        self.assertAlmostEqual(out["attributed"]["total"]["usd"], 30.0, places=4)

    def test_prices_the_two_cache_write_tiers_differently(self):
        # This is the defect the recorded fixtures caught: a single multiplier
        # on aggregate cache_creation is wrong whenever both TTLs appear, which
        # is every run that delegates (main writes 1h, subagents write 5m).
        one_hour = eval_cost.summarize([assistant_line(cache_1h=1_000_000), result_line("x")], RATES)
        five_min = eval_cost.summarize([assistant_line(cache_5m=1_000_000), result_line("x")], RATES)
        self.assertAlmostEqual(one_hour["attributed"]["total"]["usd"], 10.0, places=4)   # 2.0x * $5
        self.assertAlmostEqual(five_min["attributed"]["total"]["usd"], 6.25, places=4)   # 1.25x * $5

    def test_prices_cache_reads_at_a_tenth_of_input(self):
        out = eval_cost.summarize([assistant_line(cache_read=1_000_000), result_line("x")], RATES)
        self.assertAlmostEqual(out["attributed"]["total"]["usd"], 0.5, places=4)

    def test_prices_each_turn_at_the_model_that_billed_it(self):
        # message.model, not the agents/*.md frontmatter -- a re-tiered or
        # mis-tiered agent must show up as a cost anomaly, not be priced at
        # the rate the pack intended.
        lines = [
            assistant_line(input_tokens=1_000_000, model="claude-opus-5"),
            assistant_line(input_tokens=1_000_000, model="claude-haiku-4-5"),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertAlmostEqual(out["attributed"]["total"]["usd"], 6.0, places=4)  # 5.0 + 1.0

    def test_lists_unknown_models_instead_of_pricing_them_silently(self):
        lines = [assistant_line(input_tokens=10, model="claude-not-a-model"), result_line("x")]
        out = eval_cost.summarize(lines, RATES)
        self.assertIn("claude-not-a-model", out["unpriced_models"])

    def test_known_models_produce_no_unpriced_entries(self):
        lines = [assistant_line(input_tokens=10, model="claude-opus-5"), result_line("x")]
        self.assertEqual(eval_cost.summarize(lines, RATES)["unpriced_models"], [])

    def test_prices_a_dated_full_model_id_at_its_alias_rate(self):
        # Eval run 6's first case: real transcripts report the dated full id
        # (claude-haiku-4-5-20251001) while the rate table and agent frontmatter
        # use the alias. The dated id missed the table, fell through to the
        # default Opus rate, and priced scrum-master 5x too high.
        dated = eval_cost.summarize(
            [assistant_line(input_tokens=1_000_000, model="claude-haiku-4-5-20251001"),
             result_line("x")], RATES)
        alias = eval_cost.summarize(
            [assistant_line(input_tokens=1_000_000, model="claude-haiku-4-5"),
             result_line("x")], RATES)
        self.assertAlmostEqual(dated["attributed"]["total"]["usd"], 1.0, places=4)
        self.assertEqual(dated["attributed"]["total"]["usd"], alias["attributed"]["total"]["usd"])
        self.assertEqual(dated["unpriced_models"], [])

    def test_a_dated_id_with_no_alias_in_the_table_is_still_reported(self):
        # Normalising must not paper over a genuinely unknown model.
        out = eval_cost.summarize(
            [assistant_line(input_tokens=10, model="claude-nonexistent-9-20260101"),
             result_line("x")], RATES)
        self.assertEqual(out["unpriced_models"], ["claude-nonexistent-9-20260101"])

    def test_every_model_the_pack_pins_is_priceable(self):
        # A re-tier that points an agent at a model the table lacks would price
        # that agent at the default rate on every future run.
        import pathlib as _p
        pinned = set()
        for path in sorted((ROOT / "agents").glob("*.md")):
            block = path.read_text().split("---")[1]
            for line in block.splitlines():
                if line.startswith("model:"):
                    pinned.add(line.split(":", 1)[1].strip())
        self.assertTrue(pinned, "no pinned models found")
        table = RATES["rates"]
        missing = sorted(m for m in pinned if not eval_cost._resolve_rate(m, table, "")[1])
        self.assertEqual(missing, [], f"agents pin models absent from model-rates.json: {missing}")


class TestAttribution(unittest.TestCase):
    def test_attributes_turns_to_the_subagent_that_produced_them(self):
        lines = [
            assistant_line(input_tokens=10, tools=["Agent"]),
            task_started_line("toolu_1", "qa-engineer"),
            assistant_line(input_tokens=1_000_000, parent="toolu_1"),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertIn("qa-engineer", out["attributed"]["agents"])
        self.assertEqual(out["attributed"]["agents"]["qa-engineer"]["input_tokens"], 1_000_000)

    def test_main_thread_turns_land_under_main(self):
        out = eval_cost.summarize([assistant_line(input_tokens=10), result_line("x")], RATES)
        self.assertEqual(out["attributed"]["agents"]["main"]["input_tokens"], 10)

    def test_separates_two_subagents(self):
        lines = [
            task_started_line("toolu_a", "qa-engineer"),
            task_started_line("toolu_b", "security-engineer"),
            assistant_line(input_tokens=111, parent="toolu_a"),
            assistant_line(input_tokens=222, parent="toolu_b"),
            result_line("x"),
        ]
        agents = eval_cost.summarize(lines, RATES)["attributed"]["agents"]
        self.assertEqual(agents["qa-engineer"]["input_tokens"], 111)
        self.assertEqual(agents["security-engineer"]["input_tokens"], 222)

    def test_unmapped_parent_id_does_not_vanish(self):
        # If task_started was lost (truncated feed, killed run), the tokens are
        # still real. They must be reported, not silently dropped.
        lines = [assistant_line(input_tokens=999, parent="toolu_orphan"), result_line("x")]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(out["attributed"]["total"]["input_tokens"], 999)

    def test_counts_tool_calls_by_name(self):
        lines = [
            assistant_line(tools=["Read", "Read", "Bash"]),
            assistant_line(tools=["Read"]),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(out["tools"]["Read"], 3)
        self.assertEqual(out["tools"]["Bash"], 1)

    def test_counts_tool_calls_per_agent(self):
        # The headline question for the next milestone is *why* qa-engineer
        # spends what it spends, and per-agent tool counts are what answers it.
        lines = [
            task_started_line("toolu_a", "qa-engineer"),
            assistant_line(tools=["Read", "Bash"], parent="toolu_a"),
            assistant_line(tools=["Grep"]),
            result_line("x"),
        ]
        agents = eval_cost.summarize(lines, RATES)["attributed"]["agents"]
        self.assertEqual(agents["qa-engineer"]["tools"], {"Bash": 1, "Read": 1})
        self.assertEqual(agents["main"]["tools"], {"Grep": 1})


class TestRobustness(unittest.TestCase):
    def test_counts_unparsable_lines_instead_of_crashing(self):
        # The harness redirects stderr into the same stream, so a warning line
        # can land mid-transcript. One bad line must not lose the run's data.
        lines = [assistant_line(input_tokens=10), "some stderr warning", result_line("x")]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(out["parse_errors"], 1)
        self.assertEqual(out["attributed"]["total"]["input_tokens"], 10)

    def test_survives_a_turn_with_no_usage_object(self):
        lines = [json.dumps({"type": "assistant", "message": {"content": []}}), result_line("x")]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(out["attributed"]["total"]["input_tokens"], 0)

    def test_survives_null_token_counts(self):
        # SubagentStop payloads carry explicit nulls (v1.25.0 finding); assume
        # the same is possible here rather than trusting ints.
        line = json.dumps({
            "type": "assistant",
            "message": {"model": "claude-opus-5", "content": [],
                        "usage": {"input_tokens": None, "output_tokens": None}},
        })
        out = eval_cost.summarize([line, result_line("x")], RATES)
        self.assertEqual(out["attributed"]["total"]["input_tokens"], 0)

    def test_reports_billed_total_as_none_when_the_run_emitted_no_result(self):
        out = eval_cost.summarize([assistant_line(input_tokens=10)], RATES)
        self.assertIsNone(out["billed"]["usd"])

    def test_treats_a_non_dict_json_value_as_a_parse_error(self):
        # A line can be valid JSON without being an object. These reached
        # obj.get(...) and raised AttributeError, losing the whole run's cost
        # data -- the earlier tests only covered *invalid* JSON, which is why
        # this survived to ship in 1.31.0.
        for bad in ('"just a string"', "[1,2,3]", "42", "null", "true"):
            with self.subTest(line=bad):
                out = eval_cost.summarize(
                    [bad, assistant_line(input_tokens=10), result_line("x")], RATES
                )
                self.assertEqual(out["parse_errors"], 1)
                self.assertEqual(out["attributed"]["total"]["input_tokens"], 10)

    def test_non_dict_json_does_not_break_final_text_either(self):
        self.assertEqual(eval_cost.final_text(["42", result_line("the answer")]), "the answer")


class TestAsyncAgentVisibility(unittest.TestCase):
    """A launched subagent must never silently disappear from the summary."""

    def test_an_async_only_agent_stays_visible_with_zero_tokens(self):
        # Runs 3 and 5 both saw `policy` go fully async: the subagent is launched
        # but its turns never land in the transcript. Omitting it makes the
        # summary read "main did all the work", which is the exact invisibility
        # this instrument exists to end.
        lines = [
            task_started_line("toolu_1", "security-engineer"),
            assistant_line(input_tokens=10),
            result_line("x", total_cost_usd=0.01),
        ]
        out = eval_cost.summarize(lines, RATES)
        agents = out["attributed"]["agents"]
        self.assertIn("security-engineer", agents)
        self.assertEqual(agents["security-engineer"]["tokens"], 0)
        self.assertEqual(agents["security-engineer"]["turns"], 0)

    def test_names_launched_agents_that_produced_no_measured_turns(self):
        lines = [
            task_started_line("toolu_1", "security-engineer"),
            task_started_line("toolu_2", "qa-engineer"),
            assistant_line(input_tokens=10, parent="toolu_2"),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(
            out["attributed"]["launched_without_measured_turns"], ["security-engineer"]
        )

    def test_a_task_started_without_a_subagent_type_is_not_an_agent(self):
        # Eval run 6: three cases spawned no subagent at all (board feed empty)
        # yet reported a phantom `unknown-agent`, which the harness announced as
        # "launched but unmeasured (async?)" -- inventing a lane in the one
        # report that is supposed to be authoritative about lanes.
        lines = [
            json.dumps({"type": "system", "subtype": "task_started", "tool_use_id": "toolu_x"}),
            assistant_line(input_tokens=10),
            result_line("x"),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(sorted(out["attributed"]["agents"]), ["main"])
        self.assertEqual(out["attributed"]["launched_without_measured_turns"], [])

    def test_a_named_task_started_alongside_an_unnamed_one_still_counts(self):
        lines = [
            json.dumps({"type": "system", "subtype": "task_started", "tool_use_id": "toolu_x"}),
            task_started_line("toolu_y", "qa-engineer"),
            assistant_line(input_tokens=10),                      # main thread
            assistant_line(input_tokens=20, parent="toolu_y"),     # the named subagent
            result_line("x"),
        ]
        agents = eval_cost.summarize(lines, RATES)["attributed"]["agents"]
        self.assertEqual(sorted(agents), ["main", "qa-engineer"])
        self.assertEqual(agents["qa-engineer"]["input_tokens"], 20)

    def test_counts_turns_per_agent(self):
        lines = [
            task_started_line("toolu_1", "qa-engineer"),
            assistant_line(input_tokens=1, parent="toolu_1"),
            assistant_line(input_tokens=1, parent="toolu_1"),
            assistant_line(input_tokens=1),
            result_line("x"),
        ]
        agents = eval_cost.summarize(lines, RATES)["attributed"]["agents"]
        self.assertEqual(agents["qa-engineer"]["turns"], 2)
        self.assertEqual(agents["main"]["turns"], 1)


class TestRealFixture(unittest.TestCase):
    """The point of the fixtures: a real transcript parses, and the rate table
    agrees with the CLI's own accounting."""

    def _summary(self, name):
        lines = (FIXTURES / name).read_text().splitlines()
        return lines, eval_cost.summarize(lines, RATES)

    def test_parses_both_recorded_transcripts_without_errors(self):
        for name in ("stream-json-sample.jsonl", "stream-json-subagent.jsonl"):
            with self.subTest(fixture=name):
                lines, out = self._summary(name)
                self.assertEqual(out["parse_errors"], 0, f"{name} had unparsable lines")
                self.assertGreater(out["attributed"]["total"]["cache_read_tokens"], 0)
                self.assertIsNotNone(eval_cost.final_text(lines))
                self.assertEqual(out["unpriced_models"], [], f"{name} names an unpriced model")

    def test_reconciles_with_the_cli_own_total(self):
        # The CLI reports total_cost_usd from its own billing ledger. Repricing
        # its reported token counts with our rate table must bracket it, and the
        # cache-write multiplier that implies must be a real tier -- that is what
        # proves the per-MTok rates and multipliers are right rather than merely
        # plausible. If Anthropic changes a price and model-rates.json is not
        # updated, this fails instead of the summary reporting a wrong number.
        for name in ("stream-json-sample.jsonl", "stream-json-subagent.jsonl"):
            with self.subTest(fixture=name):
                _, out = self._summary(name)
                check = out["billed"]["rate_table_check"]
                self.assertIsNotNone(check["repriced_usd_max"], "no billed usage to reprice")
                self.assertTrue(
                    check["agrees"],
                    f"{name}: CLI billed {check['billed_usd']}, rate table brackets it as "
                    f"[{check['repriced_usd_min']}, {check['repriced_usd_max']}] with implied "
                    f"cache-write multiplier {check['implied_cache_write_multiplier']} "
                    f"-- model-rates.json is stale or wrong",
                )

    def test_the_implied_cache_write_multiplier_is_a_declared_tier(self):
        # The 1h/5m blend is the one quantity modelUsage does not report. Both
        # fixtures must imply a value inside the declared range -- the sample
        # writes pure 1h (2.0), the subagent probe blends main-thread 1h with
        # subagent 5m and lands between the tiers.
        lo = RATES["multipliers"]["cache_write_5m"]
        hi = RATES["multipliers"]["cache_write_1h"]
        for name in ("stream-json-sample.jsonl", "stream-json-subagent.jsonl"):
            with self.subTest(fixture=name):
                _, out = self._summary(name)
                implied = out["billed"]["rate_table_check"]["implied_cache_write_multiplier"]
                self.assertIsNotNone(implied)
                self.assertGreaterEqual(implied, lo - 0.01)
                self.assertLessEqual(implied, hi + 0.01)

    def test_attributes_the_subagent_fixture_to_its_named_agent(self):
        _, out = self._summary("stream-json-subagent.jsonl")
        self.assertIn("general-purpose", out["attributed"]["agents"])
        self.assertIn("main", out["attributed"]["agents"])

    def test_reports_what_fraction_of_billed_cost_the_attribution_covers(self):
        # Per-turn usage excludes thinking tokens, so attribution never sums to
        # the billed total. The instrument must say so rather than imply the
        # per-agent split is the whole bill.
        _, out = self._summary("stream-json-sample.jsonl")
        coverage = out["attributed"]["coverage_of_billed"]
        self.assertIsNotNone(coverage)
        self.assertGreater(coverage, 0.5)
        self.assertLessEqual(coverage, 1.0)


class TestCLI(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "eval-cost.py"), *args],
            capture_output=True, text=True,
        )

    def test_prints_json_and_exits_zero(self):
        proc = self._run("--transcript", str(FIXTURES / "stream-json-sample.jsonl"),
                         "--rates", str(RATES_PATH))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        json.loads(proc.stdout)

    def test_text_only_prints_the_answer_text(self):
        proc = self._run("--transcript", str(FIXTURES / "stream-json-sample.jsonl"),
                         "--rates", str(RATES_PATH), "--text-only")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("laravel-claude-agents", proc.stdout)
        self.assertNotIn('"type":', proc.stdout, "stream-json leaked into the log text")

    def test_exits_two_on_a_missing_transcript(self):
        proc = self._run("--transcript", "/nonexistent/nope.jsonl", "--rates", str(RATES_PATH))
        self.assertEqual(proc.returncode, 2)

    def test_exits_two_when_text_only_finds_no_text(self):
        empty = FIXTURES / "empty-for-test.jsonl"
        empty.write_text("")
        try:
            proc = self._run("--transcript", str(empty), "--rates", str(RATES_PATH), "--text-only")
            self.assertEqual(proc.returncode, 2)
        finally:
            empty.unlink()

    def test_full_text_includes_an_earlier_turn_text_only_would_drop(self):
        multi = FIXTURES / "multi-turn-for-test.jsonl"
        multi.write_text("\n".join([
            json.dumps({"type": "assistant",
                        "message": {"content": [{"type": "text", "text": "4 stages, done when: X"}]}}),
            json.dumps({"type": "assistant",
                        "message": {"content": [{"type": "text", "text": "closing summary"}]}}),
            json.dumps({"type": "result", "subtype": "success", "result": "closing summary"}),
        ]))
        try:
            text_only = self._run("--transcript", str(multi), "--rates", str(RATES_PATH), "--text-only")
            full_text = self._run("--transcript", str(multi), "--rates", str(RATES_PATH), "--full-text")
            self.assertEqual(text_only.returncode, 0, text_only.stderr)
            self.assertEqual(full_text.returncode, 0, full_text.stderr)
            self.assertNotIn("done when: X", text_only.stdout)
            self.assertIn("done when: X", full_text.stdout)
            self.assertIn("closing summary", full_text.stdout)
        finally:
            multi.unlink()

    def test_exits_two_when_full_text_finds_no_text(self):
        empty = FIXTURES / "empty-for-full-text-test.jsonl"
        empty.write_text("")
        try:
            proc = self._run("--transcript", str(empty), "--rates", str(RATES_PATH), "--full-text")
            self.assertEqual(proc.returncode, 2)
        finally:
            empty.unlink()

    def test_text_only_and_full_text_are_mutually_exclusive(self):
        proc = self._run("--transcript", str(FIXTURES / "stream-json-sample.jsonl"),
                         "--rates", str(RATES_PATH), "--text-only", "--full-text")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not allowed with argument", proc.stderr)


if __name__ == "__main__":
    unittest.main()


class TestModelIdVariants(unittest.TestCase):
    """Both variants below were found in real transcripts, not imagined."""

    def test_prices_a_bracketed_context_variant_at_its_base_rate(self):
        # `claude-opus-4-8[1m]` appears only in the result line's modelUsage ledger.
        # It missed the table and fell back to the default Opus rate, which happened
        # to be correct because Opus 4.8 and Opus 5 share $5/$25 — so a real
        # long-context premium would have been absorbed in silence.
        rate, priced = eval_cost._resolve_rate(
            "claude-opus-4-8[1m]", RATES["rates"], RATES["_default"])
        self.assertTrue(priced)
        self.assertEqual(rate, RATES["rates"]["claude-opus-4-8"])

    def test_prices_a_bracketed_sonnet_variant(self):
        rate, priced = eval_cost._resolve_rate(
            "claude-sonnet-5[1m]", RATES["rates"], RATES["_default"])
        self.assertTrue(priced)
        self.assertEqual(rate, RATES["rates"]["claude-sonnet-5"])

    def test_an_unknown_bracketed_model_is_still_reported(self):
        _, priced = eval_cost._resolve_rate(
            "claude-nonexistent-9[1m]", RATES["rates"], RATES["_default"])
        self.assertFalse(priced)

    def test_an_unpriceable_ledger_model_blocks_a_clean_agreement(self):
        # The repriced bracket would be built on a defaulted guess, so `agrees`
        # must not read as a pass.
        lines = [
            assistant_line(input_tokens=10, output_tokens=1),
            json.dumps({
                "type": "result", "subtype": "success", "result": "x",
                "total_cost_usd": 0.5,
                "modelUsage": {"totally-unknown-model": {
                    "inputTokens": 1_000_000, "outputTokens": 0,
                    "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
                    "costUSD": 0.5}},
            }),
        ]
        out = eval_cost.summarize(lines, RATES)
        self.assertEqual(out["billed"]["unpriced_in_ledger"], ["totally-unknown-model"])
        self.assertFalse(out["billed"]["rate_table_check"]["agrees"])
