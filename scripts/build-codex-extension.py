#!/usr/bin/env python3
"""Generate the Codex CLI 'Core' target under codex/ from the canonical pack.

Codex has no one-command extension install — config is spread across AGENTS.md,
.agents/skills/, and .codex/. This produces a self-contained codex/ tree plus an
install script that copies it into a target project. Regenerate after editing the
template, skill, or guard scripts, so the Codex target never drifts.

    python3 scripts/build-codex-extension.py

Produces (under codex/):
  AGENTS.md                         from CLAUDE.md.template (Codex's native context)
  .agents/skills/laravel-conventions/  the skill, verbatim (agentskills.io standard)
  .codex/hooks.json                 PreToolUse wiring (git-root-resolved script paths)
  .codex/hooks/*.sh                 block-prod-* (verbatim) + codex apply_patch-aware .env guard
  (install-codex.sh is hand-authored and left untouched.)

Deterministic: no network, no LLM.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODEX = os.path.join(ROOT, "codex")

AGENT_DELIVERY_OLD = (
    "14 specialist agents available. Launch orchestrator with "
    "`claude --agent delivery-coordinator`. It routes work to specialists. "
    "Direct agent calls also OK."
)
AGENT_DELIVERY_NEW = (
    "This Codex install ships the 8 Laravel skills (`laravel-conventions`, "
    "`laravel-testing`, `eloquent-performance`, `laravel-security`, `laravel-deploy`, "
    "`delivery-templates`, `accessibility-design`, `docs-authoring`) and the guardrail "
    "hooks below. The full 17-agent specialist team runs on Claude Code and Gemini CLI."
)

SANITIZE = [
    (AGENT_DELIVERY_OLD, AGENT_DELIVERY_NEW),
    # Codex ships no slash commands — the ledger is maintained by hand there.
    ("(via `/teach` or a mid-task correction)", "(via a mid-task correction — record it by hand in the same shape)"),
    ("scripts/block-prod-artisan.sh", ".codex/hooks/block-prod-artisan.sh"),
    ("scripts/block-prod-destructive-sql.sh", ".codex/hooks/block-prod-destructive-sql.sh"),
    ("scripts/enforce-sail.sh", ".codex/hooks/enforce-sail.sh"),
    ("CLAUDE.md", "AGENTS.md"),  # generic sweep last
]


def sanitize(text):
    for old, new in SANITIZE:
        text = text.replace(old, new)
    return text


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def build_agents_md():
    with open(os.path.join(ROOT, "CLAUDE.md.template")) as f:
        write(os.path.join(CODEX, "AGENTS.md"), sanitize(f.read()))


def build_skill():
    dst = os.path.join(CODEX, ".agents", "skills")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(ROOT, "skills"), dst)
    for root, _dirs, files in os.walk(dst):
        for fn in files:
            if fn.endswith((".md", ".txt")):
                p = os.path.join(root, fn)
                with open(p) as f:
                    txt = f.read()
                write(p, sanitize(txt))


def build_hooks():
    hooks_dir = os.path.join(CODEX, ".codex", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    # block-prod-* and enforce-sail port verbatim (Bash matcher, .tool_input.command, exit 2).
    for fn in ("block-prod-destructive-sql.sh", "block-prod-artisan.sh", "enforce-sail.sh"):
        with open(os.path.join(ROOT, "scripts", fn)) as f:
            txt = sanitize(f.read())
        out = os.path.join(hooks_dir, fn)
        write(out, txt)
        os.chmod(out, 0o755)
    # Codex apply_patch-aware .env guard, installed as protect-env-files.sh.
    with open(os.path.join(ROOT, "scripts", "codex-protect-env-files.sh")) as f:
        txt = sanitize(f.read())
    out = os.path.join(hooks_dir, "protect-env-files.sh")
    write(out, txt)
    os.chmod(out, 0o755)

    git_root = "$(git rev-parse --show-toplevel)"
    hooks_json = '''{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "%(r)s/.codex/hooks/block-prod-destructive-sql.sh", "statusMessage": "Checking for destructive prod SQL" },
          { "type": "command", "command": "%(r)s/.codex/hooks/block-prod-artisan.sh", "statusMessage": "Checking for prod-affecting artisan" },
          { "type": "command", "command": "%(r)s/.codex/hooks/enforce-sail.sh", "statusMessage": "Routing PHP tooling through Sail" }
        ]
      },
      {
        "matcher": "apply_patch|Edit|Write",
        "hooks": [
          { "type": "command", "command": "%(r)s/.codex/hooks/protect-env-files.sh", "statusMessage": "Protecting .env / secret files" }
        ]
      }
    ]
  }
}
''' % {"r": git_root}
    write(os.path.join(CODEX, ".codex", "hooks.json"), hooks_json)


def main():
    os.makedirs(CODEX, exist_ok=True)
    build_agents_md()
    build_skill()
    build_hooks()
    print("codex target built: AGENTS.md + 8 skills + 4 PreToolUse guardrail hooks")


if __name__ == "__main__":
    sys.exit(main())
