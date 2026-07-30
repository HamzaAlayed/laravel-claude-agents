import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import events  # noqa: E402


def init_msg():
    return {
        "type": "system",
        "subtype": "init",
        "model": "claude-sonnet-5",
        "plugins": [{"name": "laravel-team", "path": "/p"}],
        "capabilities": ["interrupt_receipt_v1"],
    }


def spawn_msg(tool_use_id="tu_1", subagent="backend-developer", desc="Add Action"):
    return {
        "type": "assistant",
        "parent_tool_use_id": None,
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Delegating."},
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Agent",
                    "input": {"subagent_type": f"laravel-team:{subagent}", "description": desc},
                },
            ],
        },
    }


def tool_result_msg(tool_use_id="tu_1", parent=None, text="done"):
    return {
        "type": "user",
        "parent_tool_use_id": parent,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": text}],
        },
    }


class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.state = events.RunState("run_1")

    def emit(self, raw):
        return events.normalize(raw, self.state)

    def test_init_reports_plugins_and_capabilities(self):
        out = self.emit(init_msg())
        self.assertEqual([e["type"] for e in out], ["init"])
        self.assertEqual(out[0]["plugins"], ["laravel-team"])
        self.assertEqual(out[0]["plugin_errors"], [])
        self.assertIn("interrupt_receipt_v1", out[0]["capabilities"])

    def test_init_surfaces_plugin_errors(self):
        raw = init_msg()
        raw["plugin_errors"] = [{"plugin": "laravel-team", "type": "missing", "message": "nope"}]
        self.assertEqual(self.emit(raw)[0]["plugin_errors"][0]["plugin"], "laravel-team")

    def test_seq_increases_monotonically(self):
        first = self.emit(init_msg())
        second = self.emit(spawn_msg())
        seqs = [e["seq"] for e in first + second]
        self.assertEqual(seqs, sorted(set(seqs)))

    def test_agent_spawn_emits_tool_use_and_agent_start(self):
        out = self.emit(spawn_msg())
        self.assertEqual([e["type"] for e in out], ["text", "tool_use", "agent_start"])
        start = out[-1]
        self.assertEqual(start["agent"], "backend-developer")
        self.assertEqual(start["task"], "Add Action")
        self.assertEqual(start["tool_use_id"], "tu_1")

    def test_matching_tool_result_closes_the_lane(self):
        self.emit(spawn_msg())
        out = self.emit(tool_result_msg())
        self.assertEqual([e["type"] for e in out], ["tool_result", "agent_end"])
        self.assertEqual(out[-1]["agent"], "backend-developer")

    def test_unrelated_tool_result_does_not_close_a_lane(self):
        out = self.emit(tool_result_msg(tool_use_id="tu_other"))
        self.assertEqual([e["type"] for e in out], ["tool_result"])

    def test_subagent_text_attributed_to_its_lane(self):
        self.emit(spawn_msg())
        raw = {
            "type": "assistant",
            "parent_tool_use_id": "tu_1",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "reading"}]},
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["agent"], "backend-developer")

    def test_nested_spawn_tracks_depth(self):
        self.emit(spawn_msg())
        nested = spawn_msg(tool_use_id="tu_2", subagent="qa-engineer", desc="write tests")
        nested["parent_tool_use_id"] = "tu_1"
        out = self.emit(nested)
        start = next(e for e in out if e["type"] == "agent_start")
        self.assertEqual(start["agent"], "qa-engineer")
        self.assertEqual(start["parent_agent"], "backend-developer")

    def test_thinking_block(self):
        raw = {
            "type": "assistant",
            "parent_tool_use_id": None,
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hm"}]},
        }
        self.assertEqual(self.emit(raw)[0]["type"], "thinking")

    def test_api_retry(self):
        raw = {
            "type": "system",
            "subtype": "api_retry",
            "attempt": 2,
            "max_retries": 5,
            "retry_delay_ms": 800,
            "error": "overloaded",
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["type"], "api_retry")
        self.assertEqual(out[0]["attempt"], 2)

    def test_result_carries_cost_and_duration(self):
        raw = {
            "type": "result",
            "subtype": "success",
            "result": "all done",
            "duration_ms": 4200,
            "total_cost_usd": 0.12,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        out = self.emit(raw)
        self.assertEqual(out[0]["type"], "result")
        self.assertEqual(out[0]["subtype"], "success")
        self.assertEqual(out[0]["duration_ms"], 4200)

    def test_unknown_message_type_is_ignored_not_crashed(self):
        self.assertEqual(self.emit({"type": "who_knows"}), [])

    def test_malformed_message_is_ignored(self):
        self.assertEqual(self.emit({}), [])


if __name__ == "__main__":
    unittest.main()
