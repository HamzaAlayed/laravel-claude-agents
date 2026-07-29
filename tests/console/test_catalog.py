import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import catalog  # noqa: E402


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.load_catalog(REPO)
        cls.agents = {a["slug"]: a for a in cls.cat["agents"]}

    def test_parses_every_agent_on_disk(self):
        self.assertEqual(len(self.cat["agents"]), len(list((REPO / "agents").glob("*.md"))))

    def test_backend_developer_fields(self):
        a = self.agents["backend-developer"]
        self.assertEqual(a["name"], "Adam")
        self.assertEqual(a["model"], "sonnet")
        self.assertEqual(a["stage"], "Build")
        self.assertIn("Read", a["tools"])
        self.assertIn("mcp__laravel-boost", a["tools"])

    def test_name_lifted_from_description_prefix(self):
        self.assertEqual(self.agents["qa-engineer"]["name"], "Dina")
        self.assertEqual(self.agents["security-engineer"]["name"], "Felix")

    def test_pinned_model_ids_survive(self):
        self.assertEqual(self.agents["solution-architect"]["model"], "claude-opus-5")

    def test_coordinator_is_not_a_column(self):
        self.assertIsNone(self.agents[catalog.COORDINATOR]["stage"])

    def test_unknown_agent_falls_back_to_working(self):
        self.assertEqual(catalog.stage_for("brand-new-agent"), "Working")

    def test_every_agent_gets_a_distinct_colour(self):
        colours = [a["color"] for a in self.cat["agents"]]
        self.assertEqual(len(set(colours)), len(colours))

    def test_colour_is_stable_across_calls(self):
        again = {a["slug"]: a["color"] for a in catalog.load_catalog(REPO)["agents"]}
        self.assertEqual(again["scrum-master"], self.agents["scrum-master"]["color"])

    def test_commands_and_skills_parsed(self):
        self.assertEqual(len(self.cat["commands"]), len(list((REPO / "commands").glob("*.md"))))
        board = next(c for c in self.cat["commands"] if c["slug"] == "board")
        self.assertEqual(board["argument_hint"], "[port]")
        self.assertTrue(all(s["description"] for s in self.cat["skills"]))

    def test_skill_description_quotes_stripped(self):
        testing = next(s for s in self.cat["skills"] if s["slug"] == "laravel-testing")
        self.assertFalse(testing["description"].startswith('"'))


if __name__ == "__main__":
    unittest.main()
