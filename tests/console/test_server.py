import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "console"))

import server  # noqa: E402

TOKEN = "test-token"


class FakeManager:
    def __init__(self):
        self.started = []
        self.answered = []
        self.interrupted = []
        self.sent = []

    def start(self, spec):
        self.started.append(spec)
        return "run_abc"

    def send(self, run_id, text):
        self.sent.append((run_id, text))

    def answer(self, run_id, prompt_id, payload):
        self.answered.append((run_id, prompt_id, payload))
        return prompt_id == "p_1"

    def interrupt(self, run_id):
        self.interrupted.append(run_id)

    def set_mode(self, run_id, mode=None, model=None):
        self.mode = (run_id, mode, model)

    def list_runs(self):
        return [{"run_id": "run_abc", "status": "running"}]

    def snapshot(self, run_id):
        return [{"seq": 1, "type": "text", "text": "hi"}]

    def subscribe(self, run_id, since_seq=0):
        yield {"seq": 2, "type": "text", "text": "streamed"}


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dist = pathlib.Path(cls.tmp.name)
        (cls.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
        (cls.dist / "app.js").write_text("console.log(1)", encoding="utf-8")
        cls.manager = FakeManager()
        cls.httpd = server.make_server("127.0.0.1", 0, TOKEN, cls.manager, REPO, cls.dist)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, token=TOKEN, origin=None):
        request = urllib.request.Request(self.url(path))
        if token:
            request.add_header("X-Guild-Token", token)
        if origin:
            request.add_header("Origin", origin)
        return urllib.request.urlopen(request, timeout=5)

    def post(self, path, body, token=TOKEN, origin=None):
        request = urllib.request.Request(
            self.url(path), data=json.dumps(body).encode(), method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Guild-Token", token)
        if origin:
            request.add_header("Origin", origin)
        return urllib.request.urlopen(request, timeout=5)

    def test_api_without_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", token=None)
        self.assertEqual(ctx.exception.code, 401)

    def test_api_with_wrong_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", token="nope")
        self.assertEqual(ctx.exception.code, 401)

    def test_token_may_arrive_as_query_param(self):
        response = self.get(f"/api/catalog?token={TOKEN}", token=None)
        self.assertEqual(response.status, 200)

    def test_cross_origin_is_403(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", origin="https://evil.example")
        self.assertEqual(ctx.exception.code, 403)

    def test_localhost_origin_allowed(self):
        response = self.get("/api/catalog", origin=f"http://localhost:{self.port}")
        self.assertEqual(response.status, 200)

    def test_catalog_returns_agents(self):
        payload = json.loads(self.get("/api/catalog").read())
        self.assertTrue(payload["agents"])
        self.assertIn("stages", payload)

    def test_post_runs_starts_a_run(self):
        payload = json.loads(
            self.post("/api/runs", {"kind": "prompt", "target": "", "text": "hi"}).read()
        )
        self.assertEqual(payload["run_id"], "run_abc")
        self.assertEqual(self.manager.started[-1]["text"], "hi")

    def test_post_runs_rejects_missing_kind(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs", {"text": "hi"})
        self.assertEqual(ctx.exception.code, 400)

    def test_answer_returns_409_when_already_resolved(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs/run_abc/answer", {"prompt_id": "p_2", "behavior": "allow"})
        self.assertEqual(ctx.exception.code, 409)

    def test_answer_ok(self):
        response = self.post(
            "/api/runs/run_abc/answer", {"prompt_id": "p_1", "behavior": "allow"}
        )
        self.assertEqual(response.status, 200)

    def test_interrupt(self):
        self.post("/api/runs/run_abc/interrupt", {})
        self.assertIn("run_abc", self.manager.interrupted)

    def test_message(self):
        self.post("/api/runs/run_abc/message", {"text": "more"})
        self.assertIn(("run_abc", "more"), self.manager.sent)

    def test_run_snapshot(self):
        payload = json.loads(self.get("/api/runs/run_abc").read())
        self.assertEqual(payload["events"][0]["text"], "hi")

    def test_events_stream_is_sse(self):
        response = self.get("/api/runs/run_abc/events")
        self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
        first = response.readline() + response.readline()
        self.assertIn(b"streamed", first)
        response.close()

    def test_index_served_at_root_without_token(self):
        response = urllib.request.urlopen(self.url("/"), timeout=5)
        self.assertIn(b"console", response.read())

    def test_unknown_client_route_falls_back_to_index(self):
        response = urllib.request.urlopen(self.url("/runs/run_abc"), timeout=5)
        self.assertIn(b"console", response.read())

    def test_asset_served_with_mime_type(self):
        response = urllib.request.urlopen(self.url("/app.js"), timeout=5)
        self.assertIn("javascript", response.headers["Content-Type"])

    def test_path_traversal_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/../../VERSION"), timeout=5)
        self.assertIn(ctx.exception.code, (400, 403, 404))


if __name__ == "__main__":
    unittest.main()
