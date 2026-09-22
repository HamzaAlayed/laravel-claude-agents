import concurrent.futures
import http.client
import json
import os
import pathlib
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

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
        self.resumed = []

    def start(self, spec):
        # Two failure shapes the engine really produces, keyed off `model` so
        # the fake stays stateless: a bounded crossing into the engine loop
        # timing out, and client_factory rejecting an option.
        if spec.get("model") == "wedged-cli":
            raise concurrent.futures.TimeoutError()
        if spec.get("model") == "no-such-model":
            raise RuntimeError("model 'no-such-model' is not supported")
        self.started.append(spec)
        return "run_abc"

    def send(self, run_id, text):
        if run_id == "run_wedged":
            raise concurrent.futures.TimeoutError()
        self.sent.append((run_id, text))

    def is_live(self, run_id):
        return run_id == "run_abc"

    def answer(self, run_id, prompt_id, payload):
        self.answered.append((run_id, prompt_id, payload))
        return prompt_id == "p_1"

    def interrupt(self, run_id):
        self.interrupted.append(run_id)

    def resume(self, run_id):
        self.resumed.append(run_id)
        return "run_resumed"

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

    def test_a_rejected_post_does_not_poison_the_connection(self):
        """protocol_version is HTTP/1.1, so connections are reused. A 401 that
        never read the request body left it in the socket, and the NEXT request on
        that connection was parsed starting from the leftover JSON."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(
                "POST", "/api/runs",
                body=json.dumps({"kind": "prompt", "text": "x" * 500}),
                headers={"Content-Type": "application/json", "X-Guild-Token": "nope"},
            )
            rejected = conn.getresponse()
            rejected.read()
            self.assertEqual(rejected.status, 401)

            conn.request("GET", "/api/catalog", headers={"X-Guild-Token": TOKEN})
            follow_up = conn.getresponse()
            body = follow_up.read()
            self.assertEqual(follow_up.status, 200)
            self.assertIn(b"agents", body)
        finally:
            conn.close()

    def test_a_non_ascii_token_is_refused_not_a_crash(self):
        # secrets.compare_digest raises TypeError on a non-ASCII str, so the
        # comparison has to encode first. A 500 here would leak that it crashed.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/catalog", token="café-très-long")
        self.assertEqual(ctx.exception.code, 401)

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

    def test_resume(self):
        response = self.post("/api/runs/run_abc/resume", {})
        body = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(body["run_id"], "run_resumed")
        self.assertIn("run_abc", self.manager.resumed)

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

    def test_events_stream_for_an_unknown_run_is_404_not_an_empty_200(self):
        # subscribe() is a generator: its KeyError does not fire until the first
        # next(), which used to be AFTER the 200 and the event-stream headers
        # were on the wire. EventSource then saw a clean close of a successful
        # stream and retry-looped forever on a stream that can never deliver.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/runs/run_nope/events")
        self.assertEqual(ctx.exception.code, 404)
        self.assertNotIn("event-stream", ctx.exception.headers.get("Content-Type", ""))
        self.assertIn("error", json.loads(ctx.exception.read()))

    def test_engine_timeout_becomes_504_not_a_dropped_connection(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs/run_wedged/message", {"text": "hi"})
        self.assertEqual(ctx.exception.code, 504)
        self.assertIn("time", json.loads(ctx.exception.read())["error"])

    def test_start_timeout_becomes_504(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs", {"kind": "prompt", "text": "hi", "model": "wedged-cli"})
        self.assertEqual(ctx.exception.code, 504)

    def test_rejected_client_option_becomes_400_naming_the_reason(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/runs", {"kind": "prompt", "text": "hi", "model": "no-such-model"})
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("no-such-model", json.loads(ctx.exception.read())["error"])


class TestKernelRoutes(unittest.TestCase):
    """Spin a second server with a recording kernel_cli — do not reuse the class server."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = pathlib.Path(self.tmp.name)
        (self.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
        self.calls = []

        def kernel_cli(argv):
            self.calls.append(list(argv))
            return (0, "ok")

        self.httpd = server.make_server(
            "127.0.0.1", 0, TOKEN, FakeManager(), REPO, self.dist, kernel_cli=kernel_cli
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, token=TOKEN):
        request = urllib.request.Request(self.url(path))
        if token:
            request.add_header("X-Guild-Token", token)
        return urllib.request.urlopen(request, timeout=5)

    def post(self, path, body, token=TOKEN):
        request = urllib.request.Request(
            self.url(path), data=json.dumps(body).encode(), method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Guild-Token", token)
        return urllib.request.urlopen(request, timeout=5)

    def test_ingest_rejects_unknown_kind_without_calling_cli(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post(
                "/api/kernel/ingest",
                {"name": "tag", "kind": "nope", "stage": "a", "check": "pint"},
            )
        self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(self.calls, [])

    def test_ingest_ignores_client_root_and_uses_getcwd(self):
        payload = json.loads(
            self.post(
                "/api/kernel/ingest",
                {
                    "name": "tag",
                    "kind": "check",
                    "stage": "a",
                    "check": "pint",
                    "root": "/tmp/evil",
                },
            ).read()
        )
        self.assertEqual(payload, {"ok": True, "text": "ok"})
        self.assertEqual(len(self.calls), 1)
        argv = self.calls[0]
        self.assertIn("ingest", argv)
        root_idx = argv.index("--root")
        self.assertEqual(argv[root_idx + 1], os.getcwd())
        self.assertNotIn("/tmp/evil", argv)
        self.assertEqual(argv[argv.index("--name") + 1], "tag")
        self.assertEqual(argv[argv.index("--kind") + 1], "check")
        self.assertEqual(argv[argv.index("--stage") + 1], "a")
        self.assertEqual(argv[argv.index("--check") + 1], "pint")

    def test_board_returns_cli_stdout(self):
        payload = json.loads(self.get("/api/kernel/board?name=tag").read())
        self.assertEqual(payload, {"text": "ok"})
        self.assertEqual(self.calls[0][0], "board")
        self.assertEqual(self.calls[0][self.calls[0].index("--name") + 1], "tag")

    def test_board_without_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/kernel/board?name=tag", token=None)
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(self.calls, [])


class TestKernelDeliveries(unittest.TestCase):
    """Spin a second server with kernel_root — do not reuse the class server."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")

        tag = self.root / "docs" / "delivery" / "tag"
        tag.mkdir(parents=True)
        (tag / "kernel.json").write_text(
            json.dumps(
                {
                    "name": "tag",
                    "done_when": "POST /api/tags creates a Tag",
                    "cap": 3,
                    "status": "running",
                    "spawns": 0,
                    "sprint": "",
                    "rules_printed": [],
                    "issue": {
                        "number": 42,
                        "title": "Add Tag API",
                        "url": "https://github.com/acme/repo/issues/42",
                    },
                    "pr": {
                        "number": 17,
                        "url": "https://github.com/acme/repo/pull/17",
                        "state": "open",
                    },
                    "stages": [
                        {
                            "id": "a",
                            "agent": "database-developer",
                            "role": "writer",
                            "success_criteria": ["tags migration exists"],
                            "depends_on": [],
                            "status": "queued",
                            "did": [],
                            "verified": [],
                            "flags": [],
                            "pair": "",
                            "awaiting_pair": False,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        bad = self.root / "docs" / "delivery" / "bad name"
        bad.mkdir(parents=True)
        (bad / "kernel.json").write_text(
            json.dumps({"name": "bad name", "status": "running", "done_when": "x", "cap": 1, "stages": []}),
            encoding="utf-8",
        )

        self.httpd = server.make_server(
            "127.0.0.1",
            0,
            TOKEN,
            FakeManager(),
            REPO,
            self.dist,
            kernel_root=str(self.root),
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, token=TOKEN):
        request = urllib.request.Request(self.url(path))
        if token:
            request.add_header("X-Guild-Token", token)
        return urllib.request.urlopen(request, timeout=5)

    def test_list_deliveries_includes_tag_skips_invalid_name(self):
        payload = json.loads(self.get("/api/kernel/deliveries").read())
        names = [row["name"] for row in payload["deliveries"]]
        self.assertIn("tag", names)
        self.assertNotIn("bad name", names)
        tag = next(row for row in payload["deliveries"] if row["name"] == "tag")
        self.assertEqual(tag["status"], "running")
        self.assertEqual(tag["done_when"], "POST /api/tags creates a Tag")
        self.assertEqual(tag["issue_number"], 42)
        self.assertEqual(tag["steps"], [{"who": "Database Developer", "state": "Waiting"}])
        self.assertEqual(tag["issue_url"], "https://github.com/acme/repo/issues/42")
        self.assertEqual(tag["pr_url"], "https://github.com/acme/repo/pull/17")
        self.assertEqual(tag["pr_state"], "open")
        self.assertTrue(tag["board"])

    def test_list_deliveries_ignores_client_root_query(self):
        payload = json.loads(self.get("/api/kernel/deliveries?root=/tmp/evil").read())
        names = [row["name"] for row in payload["deliveries"]]
        self.assertEqual(names, ["tag"])

    def test_list_deliveries_without_token_is_401(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.get("/api/kernel/deliveries", token=None)
        self.assertEqual(ctx.exception.code, 401)


_VALID_TAG_KERNEL = {
    "name": "tag",
    "done_when": "POST /api/tags creates a Tag",
    "cap": 3,
    "status": "running",
    "spawns": 0,
    "sprint": "",
    "rules_printed": [],
    "issue": {"number": 42, "title": "Add Tag API", "url": "https://github.com/acme/repo/issues/42"},
    "pr": {"number": 17, "url": "https://github.com/acme/repo/pull/17", "state": "open"},
    "stages": [
        {
            "id": "a",
            "agent": "database-developer",
            "role": "writer",
            "success_criteria": ["tags migration exists"],
            "depends_on": [],
            "status": "queued",
            "did": [],
            "verified": [],
            "flags": [],
            "pair": "",
            "awaiting_pair": False,
        }
    ],
}


class TestKernelDeliverySymlinks(unittest.TestCase):
    """Second server: refuse docs/delivery and kernel.json that symlink out of root."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "kernel"
        self.root.mkdir()
        self.outside = pathlib.Path(self.tmp.name) / "outside"
        self.outside.mkdir()
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")
        self.httpd = None

    def tearDown(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.tmp.cleanup()

    def _start(self):
        self.httpd = server.make_server(
            "127.0.0.1",
            0,
            TOKEN,
            FakeManager(),
            REPO,
            self.dist,
            kernel_root=str(self.root),
        )
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _get(self, path):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        request.add_header("X-Guild-Token", TOKEN)
        return urllib.request.urlopen(request, timeout=5)

    def test_delivery_root_symlink_outside_lists_empty(self):
        escaped = self.outside / "delivery" / "tag"
        escaped.mkdir(parents=True)
        (escaped / "kernel.json").write_text(json.dumps(_VALID_TAG_KERNEL), encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "delivery").symlink_to(self.outside / "delivery")
        self._start()
        payload = json.loads(self._get("/api/kernel/deliveries").read())
        self.assertEqual(payload["deliveries"], [])

    def test_kernel_json_symlink_outside_skips_row(self):
        secret = self.outside / "stolen.json"
        secret.write_text(json.dumps(_VALID_TAG_KERNEL), encoding="utf-8")
        tag = self.root / "docs" / "delivery" / "tag"
        tag.mkdir(parents=True)
        (tag / "kernel.json").symlink_to(secret)
        self._start()
        payload = json.loads(self._get("/api/kernel/deliveries").read())
        names = [row["name"] for row in payload["deliveries"]]
        self.assertNotIn("tag", names)


class TestKernelWatch(unittest.TestCase):
    """Second server with temp kernel_root — watch toggle and tick_watches."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<h1>console</h1>", encoding="utf-8")

        tag = self.root / "docs" / "delivery" / "tag"
        tag.mkdir(parents=True)
        (tag / "kernel.json").write_text(json.dumps(_VALID_TAG_KERNEL), encoding="utf-8")

        no_pr = self.root / "docs" / "delivery" / "nopr"
        no_pr.mkdir(parents=True)
        bare = dict(_VALID_TAG_KERNEL)
        bare["name"] = "nopr"
        bare["pr"] = {}
        (no_pr / "kernel.json").write_text(json.dumps(bare), encoding="utf-8")

        self.watch_calls = []

        def watch_once(root, name):
            self.watch_calls.append((root, name))
            return {"action": "noop"}

        self.httpd = server.make_server(
            "127.0.0.1",
            0,
            TOKEN,
            FakeManager(),
            REPO,
            self.dist,
            kernel_root=str(self.root),
            watch_once=watch_once,
        )
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, token=TOKEN):
        request = urllib.request.Request(self.url(path))
        if token:
            request.add_header("X-Guild-Token", token)
        return urllib.request.urlopen(request, timeout=5)

    def post(self, path, body, token=TOKEN):
        request = urllib.request.Request(
            self.url(path), data=json.dumps(body).encode(), method="POST"
        )
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Guild-Token", token)
        return urllib.request.urlopen(request, timeout=5)

    def _watching(self, name):
        payload = json.loads(self.get("/api/kernel/deliveries").read())
        row = next(r for r in payload["deliveries"] if r["name"] == name)
        return row["watching"]

    def test_enable_watch_with_pr_number(self):
        payload = json.loads(
            self.post("/api/kernel/watch", {"name": "tag", "enabled": True}).read()
        )
        self.assertEqual(payload, {"ok": True, "watching": True})
        self.assertTrue(self._watching("tag"))

    def test_enable_watch_without_pr_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/api/kernel/watch", {"name": "nopr", "enabled": True})
        self.assertEqual(ctx.exception.code, 400)
        self.assertFalse(self._watching("nopr"))

    def test_tick_watches_stopped_removes_name(self):
        self.post("/api/kernel/watch", {"name": "tag", "enabled": True})

        def watch_once(root, name):
            return {"action": "stopped"}

        self.httpd.watch_once = watch_once
        self.httpd.tick_watches()
        self.assertFalse(self._watching("tag"))

    def test_tick_watches_reopen_leaves_name(self):
        self.post("/api/kernel/watch", {"name": "tag", "enabled": True})

        def watch_once(root, name):
            return {"action": "reopen"}

        self.httpd.watch_once = watch_once
        self.httpd.tick_watches()
        self.assertTrue(self._watching("tag"))

    def test_watch_post_ignores_client_root(self):
        payload = json.loads(
            self.post(
                "/api/kernel/watch",
                {"name": "tag", "enabled": True, "root": "/tmp/evil"},
            ).read()
        )
        self.assertEqual(payload, {"ok": True, "watching": True})
        self.assertTrue(self._watching("tag"))


class TestWriteOrDrop(unittest.TestCase):
    def test_swallows_broken_pipe(self):
        wfile = mock.Mock()
        wfile.write.side_effect = BrokenPipeError()
        self.assertFalse(server.write_or_drop(wfile, b"hi"))

    def test_swallows_connection_reset(self):
        wfile = mock.Mock()
        wfile.flush.side_effect = ConnectionResetError()
        self.assertFalse(server.write_or_drop(wfile, b"hi"))

    def test_writes_when_the_client_is_still_there(self):
        wfile = mock.Mock()
        self.assertTrue(server.write_or_drop(wfile, b"hi"))
        wfile.write.assert_called_once_with(b"hi")
        wfile.flush.assert_called_once()


class TestServerBind(unittest.TestCase):
    def test_bind_does_not_reverse_resolve_the_host(self):
        """HTTPServer.server_bind calls socket.getfqdn purely to fill in
        server_name, and that reverse lookup measured 35.0s on the author's
        machine -- paid before serve.py can print the tokenized URL, and once
        per process in this module's setUpClass. Assert the call is gone, not
        merely that it is currently fast."""
        with mock.patch.object(socket, "getfqdn", wraps=socket.getfqdn) as getfqdn:
            httpd = server.make_server("127.0.0.1", 0, TOKEN, FakeManager(), REPO,
                                       pathlib.Path(__file__).parent)
            try:
                self.assertFalse(getfqdn.called)
                self.assertEqual(httpd.server_name, "127.0.0.1")
                self.assertEqual(httpd.server_port, httpd.server_address[1])
            finally:
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
