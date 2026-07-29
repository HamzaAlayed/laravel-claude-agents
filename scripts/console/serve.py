#!/usr/bin/env python3
"""Entry point for the Guild web console.

  python3 scripts/console/serve.py [--port 8378] [--no-open]

Bootstraps a venv holding claude-agent-sdk (the only pip dependency), mints a
per-start token, and serves the committed React bundle plus the JSON/SSE API on
loopback. Re-execs itself inside the venv so the SDK import succeeds.
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
PACK_ROOT = HERE.parent.parent
VENV = ROOT / ".claude" / "console" / "venv"
DEFAULT_PORT = 8378
MIN_PYTHON = (3, 10)


def die(message: str) -> None:
    print(f"guild-console: {message}", file=sys.stderr)
    raise SystemExit(1)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> Path:
    python = venv_python()
    if python.exists():
        return python
    print("guild-console: creating venv and installing claude-agent-sdk…")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--upgrade",
                        "pip", "claude-agent-sdk"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        die(f"could not create the venv ({exc}). Install python3-venv and pip, then retry.")
    return python


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 40):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    die(f"no free port in {preferred}-{preferred + 39}")
    return 0


def pack_root() -> Path:
    """Where the Guild pack lives, for the SDK's `plugins` option."""
    if (PACK_ROOT / ".claude-plugin" / "plugin.json").is_file():
        return PACK_ROOT
    for candidate in sorted(Path.home().glob(".claude/plugins/**/laravel-team")):
        if (candidate / ".claude-plugin" / "plugin.json").is_file():
            return candidate
    return PACK_ROOT


def sdk_client_factory(options: dict):
    """Wrap ClaudeSDKClient so the engine speaks dicts and never imports the SDK."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

    engine_callback = options.pop("can_use_tool")

    async def can_use_tool(tool_name, input_data, context):
        decision = await engine_callback(tool_name, input_data, context)
        if decision.get("behavior") != "allow":
            return PermissionResultDeny(message=decision.get("message") or "Denied by the user.")
        # Allow MUST echo updated_input — an omitted one was rejected outright
        # before Claude Code v2.1.207.
        if decision.get("persist") == "localSettings":
            persist = [
                suggestion
                for suggestion in (getattr(context, "suggestions", None) or [])
                if getattr(suggestion, "destination", None) == "localSettings"
            ]
            if persist:
                return PermissionResultAllow(
                    updated_input=decision["updated_input"], updated_permissions=persist
                )
        return PermissionResultAllow(updated_input=decision["updated_input"])

    sdk_options = ClaudeAgentOptions(
        cwd=options["cwd"],
        permission_mode=options["permission_mode"],
        can_use_tool=can_use_tool,
        plugins=[{"type": "local", "path": str(pack_root())}],
        **({"model": options["model"]} if options.get("model") else {}),
    )
    return ClaudeSDKClient(options=sdk_options)


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        die(f"python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {sys.version.split()[0]}")

    parser = argparse.ArgumentParser(prog="guild-console")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--in-venv", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not args.in_venv:
        python = ensure_venv()
        os.execv(str(python), [str(python), str(Path(__file__).resolve()),
                               "--port", str(args.port),
                               *(["--no-open"] if args.no_open else []), "--in-venv"])

    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        die("claude-agent-sdk is missing from the venv. Delete "
            f"{VENV} and rerun to rebuild it.")

    sys.path.insert(0, str(HERE))
    from engine import RunManager
    from server import make_server

    # Subagent text and thinking blocks, at every nesting depth — without this
    # the board can show that a subagent ran but not what it did.
    os.environ.setdefault("CLAUDE_CODE_FORWARD_SUBAGENT_TEXT", "1")

    dist = HERE / "dist"
    if not (dist / "index.html").is_file():
        die(f"console bundle missing at {dist}/index.html — "
            "run: cd console-ui && npm ci && npm run build")

    token = secrets.token_urlsafe(24)
    port = free_port(args.port)
    manager = RunManager(ROOT, sdk_client_factory)
    httpd = make_server("127.0.0.1", port, token, manager, pack_root(), dist)
    url = f"http://127.0.0.1:{port}/?token={token}"

    print(f"guild-console: serving {ROOT}")
    print(f"guild-console: {url}")
    print("guild-console: stop with Ctrl-C")
    if not args.no_open:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nguild-console: shutting down")
    finally:
        httpd.shutdown()
        manager.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
