"""HTTP + SSE surface for the Guild console. Holds no SDK knowledge.

Security posture: this process can execute arbitrary tools, so /api requires a
per-start token and rejects any cross-origin request. A hostile page on another
origin must not be able to launch agents against the developer's checkout, and
`Origin` checking is what stops fetch() and DNS rebinding from doing that.
"""

from __future__ import annotations

import concurrent.futures
import json
import mimetypes
import posixpath
import re
import secrets
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from catalog import load_catalog

LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")
RUN_ROUTE = re.compile(r"^/api/runs/(?P<run_id>[A-Za-z0-9_]+)(?P<rest>/[a-z]+)?$")

# concurrent.futures.TimeoutError is an alias of the builtin from 3.11 on, but
# not on 3.10 (serve.py's MIN_PYTHON) -- catch both so a wedged engine loop can
# never become a dropped connection.
TIMEOUTS = (TimeoutError, concurrent.futures.TimeoutError)


def write_or_drop(wfile, data: bytes) -> bool:
    """Write bytes to a client. A disconnect is not a server error.

    Catch at the write/flush site so a non-keep-alive client that closes early
    does not produce a BrokenPipeError traceback from handle_error.
    """
    try:
        wfile.write(data)
        wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        return False
    return True


class _Server(ThreadingHTTPServer):
    """ThreadingHTTPServer without HTTPServer.server_bind's reverse-DNS lookup.

    HTTPServer.server_bind calls socket.getfqdn(host) purely to populate
    self.server_name (used only for CGI's SERVER_NAME). On a machine whose
    resolver is slow to reverse-map 127.0.0.1 -- wildcard .test/.localhost dev
    TLDs, dnsmasq, Docker/OrbStack, split-DNS VPN -- that blocks for tens of
    seconds (35.0s measured on the author's machine) BEFORE serve.py can print
    the tokenized URL, so the console's only entry point looks hung. The same
    call is what made tests/console/test_server.py cost 35s per process.
    """

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def make_server(host: str, port: int, token: str, manager, catalog_root: Path,
                dist_dir: Path) -> _Server:
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
            if supplied is None:
                return False
            # compare_digest, not `==`: a byte-by-byte comparison that exits on
            # the first mismatch leaks how much of the token the caller guessed.
            # Both sides are encoded first because compare_digest rejects
            # non-ASCII str outright, and a caller controls this string.
            try:
                return secrets.compare_digest(supplied.encode("utf-8"), token.encode("utf-8"))
            except (AttributeError, UnicodeError):
                return False

        def _content_length(self) -> int:
            try:
                return max(0, int(self.headers.get("Content-Length") or 0))
            except ValueError:
                return 0

        def _drain(self):
            """Read and discard the request body.

            protocol_version is HTTP/1.1, so this connection is reused: a body
            left unread is parsed as the beginning of the NEXT request on it, and
            the caller gets an inexplicable 400 for a well-formed request.
            Refusing a request is not a reason to skip reading it.
            """
            remaining = self._content_length()
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    return
                remaining -= len(chunk)

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            write_or_drop(self.wfile, body)

        def _read_body(self) -> dict:
            length = self._content_length()
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return {}

        def _guard(self, query: dict) -> bool:
            if not self._origin_ok():
                self._drain()
                self._json(403, {"error": "cross-origin requests are refused"})
                return False
            if not self._token_ok(query):
                self._drain()
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
            # Validate BEFORE the status line. manager.subscribe is a generator,
            # so its KeyError for an unknown run does not fire until the first
            # next() -- by which point a 200 plus event-stream headers are
            # already on the wire, and EventSource treats a clean close of a
            # successful stream as "retry", looping forever on an empty 200.
            # A 404 fails the connection once, which is the truth.
            if not manager.is_live(run_id):
                return self._json(404, {"error": "no such live run"})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for event in manager.subscribe(run_id, since_seq=since_seq):
                    chunk = f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"
                    if not write_or_drop(self.wfile, chunk.encode()):
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
                except TIMEOUTS:
                    return self._json(504, {"error": "the Claude Code CLI did not respond in "
                                                     "time; the run was not started"})
                except Exception as exc:
                    # A rejected model string, a missing CLI, a bad option --
                    # all are the caller's spec being unusable, and all used to
                    # kill this handler thread (connection reset, "Failed to
                    # fetch" in the browser) instead of naming the problem.
                    return self._json(400, {"error": f"could not start the run: {exc}"})
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
            except TIMEOUTS:
                # Every RunManager crossing into the engine loop is a bounded
                # .result(timeout=...); a wedged or slow CLI raises here. Say so
                # instead of dying and resetting the connection.
                return self._json(504, {"error": "the engine did not respond in time"})
            except Exception as exc:
                return self._json(500, {"error": str(exc)})
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
            write_or_drop(self.wfile, data)

    return _Server((host, port), Handler)
