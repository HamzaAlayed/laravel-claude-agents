#!/usr/bin/env python3
"""Deny direct secret reads and common secret-exfiltration tool calls.

The hook deliberately emits only a category-level reason. It never echoes the
submitted path, command, URL, environment value, or matched secret material.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlsplit


ALLOW_ENV = {".env.example", ".env.example.stub"}
SECRET_PARTS = {
    ".aws", ".docker", ".gnupg", ".kube", ".ssh",
    "credentials", "credential", "secrets", "secret",
}
SECRET_BASENAMES = {
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "authorized_keys",
    "known_hosts",
    "credentials.json",
    "credentials",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "service-account.json",
}
SECRET_QUERY = re.compile(r"(?:^|[_-])(api[_-]?key|token|secret|password|credential)(?:$|[_-])", re.I)
SECRET_VARIABLE = re.compile(r"\$(?:\{|)(?:[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL)[A-Z0-9_]*)(?:\}|)", re.I)
SENSITIVE_PATH_TEXT = re.compile(
    r"(?:^|[\\/\s'\"])(?:\.env(?:\.(?!example\b)[A-Za-z0-9_.-]+)?|\.ssh(?:[\\/]|$)|"
    r"(?:\.aws|\.docker|\.gnupg|\.kube|secrets?|credentials?)(?:[\\/]|$)|"
    r"(?:\.git-credentials|\.netrc|\.npmrc|\.pypirc|auth\.json)(?:$|[\s'\"])|"
    r"id_(?:rsa|ed25519|ecdsa|dsa)(?:\.pub)?(?:$|[\s'\"])|"
    r"[^/\\\s'\"]+\.(?:pem|p12|pfx|key))(?:$|[\s'\"\\/])",
    re.I,
)
ENV_ENUMERATION = re.compile(
    r"(?:^|[;&|]\s*)(?:env|printenv|export\s+-p|set)(?:\s|$)", re.I
)
OUTPUT_SINK = re.compile(r"(?:^|[;&|]\s*)(?:echo|printf|curl|wget|nc|ncat|scp)\b", re.I)
NETWORK_SINK = re.compile(r"(?:^|[;&|]\s*)(?:curl|wget|nc|ncat|scp)\b", re.I)
UPLOAD_FLAG = re.compile(r"(?:\s|^)(?:-d|--data(?:-[a-z]+)?|-F|--form|--upload-file|-T)(?:\s|=)", re.I)
SECRET_LITERAL = re.compile(r"(?:gh[oprsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")


def sensitive_path(raw: object) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    normalized = raw.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    lower_parts = [part.lower() for part in path.parts]
    base = lower_parts[-1] if lower_parts else ""
    if base in ALLOW_ENV:
        return False
    if base == ".env" or (base.startswith(".env.") and base not in ALLOW_ENV):
        return True
    if base in SECRET_BASENAMES or base.endswith((".pem", ".p12", ".pfx", ".key")):
        return True
    return any(part in SECRET_PARTS for part in lower_parts)


def command_denial(command: object) -> str | None:
    if not isinstance(command, str):
        return "malformed-command"
    if "\x00" in command:
        return "malformed-command"
    if SENSITIVE_PATH_TEXT.search(command):
        return "sensitive-path-access"
    if ENV_ENUMERATION.search(command):
        return "environment-enumeration"
    if OUTPUT_SINK.search(command) and SECRET_VARIABLE.search(command):
        return "secret-variable-output"
    if OUTPUT_SINK.search(command) and SECRET_LITERAL.search(command):
        return "secret-literal-output"
    if NETWORK_SINK.search(command) and UPLOAD_FLAG.search(command) and (
        "$" in command or "`" in command or "$(" in command
    ):
        return "dynamic-data-egress"
    if NETWORK_SINK.search(command) and SECRET_LITERAL.search(command):
        return "secret-literal-egress"
    return None


def url_denial(raw: object) -> str | None:
    if not isinstance(raw, str):
        return "malformed-url"
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "malformed-url"
    if parsed.username or parsed.password:
        return "credential-in-url"
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if value and SECRET_QUERY.search(key):
            return "credential-in-url"
    if SECRET_LITERAL.search(raw):
        return "secret-literal-egress"
    return None


def decision(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "malformed-hook-input"
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "malformed-hook-input"
    if not isinstance(tool, str) or not tool:
        if "command" in tool_input:
            tool = "Bash"
        elif "url" in tool_input:
            tool = "WebFetch"
        elif any(key in tool_input for key in ("file_path", "path", "paths")):
            tool = "Read"

    if tool in {"Read", "Grep", "read_file", "read_many_files", "search_file_content"}:
        for key in ("file_path", "path", "paths"):
            value = tool_input.get(key)
            values = value if isinstance(value, list) else [value]
            if any(sensitive_path(item) for item in values):
                return "sensitive-path-access"
        return None
    if tool in {"Bash", "run_shell_command"}:
        return command_denial(tool_input.get("command"))
    if tool in {"WebFetch", "web_fetch"}:
        return url_denial(tool_input.get("url"))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        reason = "malformed-hook-input"
    else:
        reason = decision(payload)
    if reason:
        print(
            "BLOCKED: security policy denied this tool call "
            f"({reason}). Sensitive input was omitted from this message.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
