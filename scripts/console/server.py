"""HTTP + SSE surface for the Guild console. Holds no SDK knowledge.

Security posture: this process can execute arbitrary tools, so /api requires a
per-start token and rejects any cross-origin request. A hostile page on another
origin must not be able to launch agents against the developer's checkout, and
`Origin` checking is what stops fetch() and DNS rebinding from doing that.
"""

from __future__ import annotations

import json
import mimetypes
import posixpath
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalog import load_catalog

LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")
RUN_ROUTE = re.compile(r"^/api/runs/(?P<run_id>[A-Za-z0-9_]+)(?P<rest>/[a-z]+)?$")


def make_server(host: str, port: int, token: str, manager, catalog_root: Path,
                dist_dir: Path) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GuildConsole/1.0"
        protocol_version = "HTTP/1.1"

        # ---- helpers ----
        def log_message(self, fmt, *args):  # quiet by default
            pass

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or bool(LOCAL_ORIGIN.match(origin))

        def _token_ok(self, query: dict) -> bool:
            supplied = self.headers.get("X-Guild-Token") or (query.get("token") or [None])[0]
            return supplied == token

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return {}

        def _guard(self, query: dict) -> bool:
            if not self._origin_ok():
                self._json(403, {"error": "cross-origin requests are refused"})
                return False
            if not self._token_ok(query):
                self._json(401, {"error": "missing or invalid token"})
                return False
            return True

        # ---- GET ----
        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if not parsed.path.startswith("/api/"):
                return self._static(parsed.path)
            if not self._guard(query):
                return
            if parsed.path == "/api/catalog":
                return self._json(200, load_catalog(catalog_root))
            if parsed.path == "/api/runs":
                return self._json(200, {"runs": manager.list_runs()})
            match = RUN_ROUTE.match(parsed.path)
            if match and match.group("rest") is None:
                return self._json(200, {"events": manager.snapshot(match.group("run_id"))})
            if match and match.group("rest") == "/events":
                return self._sse(match.group("run_id"), query)
            return self._json(404, {"error": "no such route"})

        def _sse(self, run_id: str, query: dict):
            since = self.headers.get("Last-Event-ID") or (query.get("since") or ["0"])[0]
            try:
                since_seq = int(since)
            except ValueError:
                since_seq = 0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for event in manager.subscribe(run_id, since_seq=since_seq):
                    chunk = f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            except KeyError:
                return

        # ---- POST ----
        def do_POST(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if not self._guard(query):
                return
            body = self._read_body()
            if parsed.path == "/api/runs":
                if body.get("kind") not in ("command", "specialist", "prompt"):
                    return self._json(400, {"error": "kind must be command, specialist or prompt"})
                if not (body.get("text") or body.get("target")):
                    return self._json(400, {"error": "text or target is required"})
                try:
                    return self._json(200, {"run_id": manager.start(body)})
                except ValueError as exc:
                    return self._json(400, {"error": str(exc)})
            match = RUN_ROUTE.match(parsed.path)
            if not match:
                return self._json(404, {"error": "no such route"})
            run_id, rest = match.group("run_id"), match.group("rest")
            try:
                if rest == "/message":
                    manager.send(run_id, body.get("text") or "")
                    return self._json(200, {"ok": True})
                if rest == "/interrupt":
                    manager.interrupt(run_id)
                    return self._json(200, {"ok": True})
                if rest == "/mode":
                    manager.set_mode(run_id, mode=body.get("mode"), model=body.get("model"))
                    return self._json(200, {"ok": True})
                if rest == "/answer":
                    prompt_id = body.pop("prompt_id", "")
                    if manager.answer(run_id, prompt_id, body):
                        return self._json(200, {"ok": True})
                    return self._json(409, {"error": "prompt unknown or already answered"})
            except KeyError:
                return self._json(404, {"error": "no such run"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            return self._json(404, {"error": "no such route"})

        # ---- static ----
        def _static(self, path: str):
            if ".." in path.split("/"):
                return self._json(403, {"error": "refused"})
            clean = posixpath.normpath(path)
            if clean.startswith(".."):
                return self._json(403, {"error": "refused"})
            candidate = (dist_dir / clean.lstrip("/")).resolve()
            index = (dist_dir / "index.html").resolve()
            try:
                candidate.relative_to(dist_dir.resolve())
            except ValueError:
                return self._json(403, {"error": "refused"})
            if not candidate.is_file():
                candidate = index  # SPA fallback
            if not candidate.is_file():
                return self._json(404, {"error": "console bundle missing"})
            data = candidate.read_bytes()
            ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return ThreadingHTTPServer((host, port), Handler)
