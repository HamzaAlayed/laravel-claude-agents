#!/usr/bin/env python3
"""Generate the Gemini CLI extension under gemini/ from the canonical pack.

The Claude-format agents/commands are the source of truth. This regenerates the
Gemini extension so the two never drift — run it after editing any agent, command,
skill, or guard script, and commit the result.

    python3 scripts/build-gemini-extension.py

What it produces (all under gemini/):
  gemini-extension.json   manifest (name/version/description/contextFileName)
  GEMINI.md               from CLAUDE.md.template
  agents/*.md             Claude subagents -> Gemini subagents (frontmatter rewritten, body verbatim)
  commands/*.toml         Claude .md slash commands -> Gemini TOML ({{args}} kept)
  skills/                 laravel-conventions copied verbatim (shared agentskills.io standard)
  hooks/hooks.json        PreToolUse -> BeforeTool wiring (${extensionPath})
  scripts/*.sh            the four guard scripts, copied (self-contained extension)

Deterministic: no network, no LLM. Bodies are preserved byte-for-byte.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEM = os.path.join(ROOT, "gemini")

# Claude-isms rewritten for the Gemini target (applied to descriptions, bodies,
# and the GEMINI.md context). Order matters: specific phrases before the generic
# CLAUDE.md -> GEMINI.md sweep.
SANITIZE = [
    ("Uses Opus for thorough analysis.", "Reasons deeply — pair it with a high-capability model."),
    ("Uses Opus for deeper reasoning.", "Reasons deeply — pair it with a high-capability model."),
    ("`claude --agent delivery-coordinator`", "`@delivery-coordinator`"),
    (" (worktree)", ""),  # Gemini subagents isolate context, not the git worktree
    ("CLAUDE.md", "GEMINI.md"),
]


def sanitize(text):
    for old, new in SANITIZE:
        text = text.replace(old, new)
    return text


def yaml_dq(s):
    """A YAML double-quoted scalar. Gemini's YAML parser is strict — unquoted
    descriptions break on a colon-space (`Vite: building`), `#`, etc. Quoting
    makes any description content safe."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Claude tool name -> Gemini built-in tool name(s). Verified against
# geminicli.com/docs/tools and /docs/core/subagents.
CLAUDE_TO_GEMINI = {
    "Read": ["read_file", "read_many_files"],
    "Write": ["write_file"],
    "Edit": ["replace"],
    "Bash": ["run_shell_command"],
    "Grep": ["search_file_content"],
    "Glob": ["glob"],
    "WebFetch": ["web_fetch"],
    "WebSearch": ["google_web_search"],
}


def split_frontmatter(text):
    """Return (frontmatter_dict_raw_lines, body). Body preserved verbatim."""
    if not text.startswith("---"):
        raise ValueError("no frontmatter")
    # Find the closing --- of the frontmatter block.
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated frontmatter")
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    return fm_lines, body


def fm_get(fm_lines, key):
    """Get a top-level `key: value` from frontmatter lines (first match)."""
    for ln in fm_lines:
        m = re.match(r"^%s:\s*(.*)$" % re.escape(key), ln)
        if m:
            return m.group(1).strip()
    return None


def parse_tool_list(raw):
    """Parse a comma-separated tool string, dropping any Agent(...) token."""
    if not raw:
        return []
    raw = re.sub(r"Agent\([^)]*\)", "", raw)  # drop the orchestrator's Agent(...) allowlist
    return [t.strip() for t in raw.split(",") if t.strip()]


def map_tools(claude_tools, disallowed):
    effective = [t for t in claude_tools if t not in disallowed]
    out = []
    for t in effective:
        for g in CLAUDE_TO_GEMINI.get(t, []):
            if g not in out:
                out.append(g)
    return out


def build_agents():
    src = os.path.join(ROOT, "agents")
    dst = os.path.join(GEM, "agents")
    os.makedirs(dst, exist_ok=True)
    count = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(src, fn)) as f:
            text = f.read()
        fm, body = split_frontmatter(text)
        name = fm_get(fm, "name")
        desc = sanitize(fm_get(fm, "description"))
        body = sanitize(body)
        tools = parse_tool_list(fm_get(fm, "tools"))
        disallowed = parse_tool_list(fm_get(fm, "disallowedTools"))
        gtools = map_tools(tools, disallowed)
        # Gemini frontmatter: drop model(inherit)/color/isolation/memory/disallowedTools.
        out = ["---", "name: %s" % name, "description: %s" % yaml_dq(desc), "tools:"]
        out += ["  - %s" % g for g in gtools]
        out.append("---")
        new = "\n".join(out) + body if body.startswith("\n") else "\n".join(out) + "\n" + body
        with open(os.path.join(dst, fn), "w") as f:
            f.write(new)
        count += 1
    return count


def toml_basic(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_commands():
    src = os.path.join(ROOT, "commands")
    dst = os.path.join(GEM, "commands")
    os.makedirs(dst, exist_ok=True)
    count = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(src, fn)) as f:
            text = f.read()
        fm, body = split_frontmatter(text)
        desc = sanitize(fm_get(fm, "description") or "")
        hint = fm_get(fm, "argument-hint")
        if hint:
            desc = "%s  (args: %s)" % (desc, hint)
        body = sanitize(body.strip("\n"))
        if "'''" in body:
            raise ValueError("body of %s contains ''' which breaks the TOML literal string" % fn)
        toml = 'description = "%s"\n\nprompt = \'\'\'\n%s\n\'\'\'\n' % (toml_basic(desc), body)
        out = fn[:-3] + ".toml"
        with open(os.path.join(dst, out), "w") as f:
            f.write(toml)
        count += 1
    return count


def copy_tree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build_skills():
    copy_tree(os.path.join(ROOT, "skills"), os.path.join(GEM, "skills"))
    # Sanitize text references (CLAUDE.md -> GEMINI.md) inside the copied skill.
    for root, _dirs, files in os.walk(os.path.join(GEM, "skills")):
        for fn in files:
            if fn.endswith((".md", ".txt")):
                p = os.path.join(root, fn)
                with open(p) as f:
                    txt = f.read()
                with open(p, "w") as f:
                    f.write(sanitize(txt))


def build_scripts():
    src = os.path.join(ROOT, "scripts")
    dst = os.path.join(GEM, "scripts")
    os.makedirs(dst, exist_ok=True)
    for fn in ("block-prod-destructive-sql.sh", "block-prod-artisan.sh", "enforce-sail.sh", "protect-env-files.sh"):
        with open(os.path.join(src, fn)) as f:
            txt = f.read()
        out = os.path.join(dst, fn)
        with open(out, "w") as f:
            f.write(sanitize(txt))  # only rewrites the CLAUDE.md -> GEMINI.md echo text; logic unchanged
        os.chmod(out, 0o755)


def build_context():
    with open(os.path.join(ROOT, "CLAUDE.md.template")) as f:
        text = f.read()
    with open(os.path.join(GEM, "GEMINI.md"), "w") as f:
        f.write(sanitize(text))


def build_hooks():
    dst = os.path.join(GEM, "hooks")
    os.makedirs(dst, exist_ok=True)
    hooks = '''{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "run_shell_command",
        "hooks": [
          { "type": "command", "name": "block-prod-destructive-sql", "command": "${extensionPath}/scripts/block-prod-destructive-sql.sh" },
          { "type": "command", "name": "block-prod-artisan", "command": "${extensionPath}/scripts/block-prod-artisan.sh" },
          { "type": "command", "name": "enforce-sail", "command": "${extensionPath}/scripts/enforce-sail.sh" }
        ]
      },
      {
        "matcher": "write_file|replace",
        "hooks": [
          { "type": "command", "name": "protect-env-files", "command": "${extensionPath}/scripts/protect-env-files.sh" }
        ]
      }
    ]
  }
}
'''
    with open(os.path.join(dst, "hooks.json"), "w") as f:
        f.write(hooks)


def build_manifest():
    with open(os.path.join(ROOT, "VERSION")) as f:
        version = f.read().strip()
    manifest = '''{
  "name": "laravel-team",
  "version": "%s",
  "description": "A 17-agent Laravel-specialized team plus 9 workflow commands, 8 on-demand skills, and production guardrail hooks.",
  "contextFileName": "GEMINI.md"
}
''' % version
    with open(os.path.join(GEM, "gemini-extension.json"), "w") as f:
        f.write(manifest)


def main():
    os.makedirs(GEM, exist_ok=True)
    a = build_agents()
    c = build_commands()
    build_skills()
    build_scripts()
    build_context()
    build_hooks()
    build_manifest()
    print("gemini extension built: %d agents, %d commands, skill+scripts+hooks+manifest+GEMINI.md" % (a, c))


if __name__ == "__main__":
    sys.exit(main())
