#!/usr/bin/env python3
"""Inventory-count sync check: every place that *claims* a count (README, the
four manifests, the gemini build script) must match what is actually on disk.

Why: counts drifted in 1.10.0 and the guard was a grep convention held in
memory. This makes it structural. Known deliberate offsets are encoded here:
gemini ships one fewer command (board.md is skipped — no dashboard there) and
codex ships only the PreToolUse guardrail subset.

Exit 1 on any mismatch, or when a claim phrase disappears entirely (a reworded
claim must update this checker in the same change). Stdlib only.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GEMINI_SKIPPED_COMMANDS = {"board.md"}  # kept in sync with build-gemini-extension.py
OBSERVER_HOOKS = {"emit-agent-events.sh"}  # wired in hooks.json but not a guardrail

WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split()
)}
NUM = r"(\d+|" + "|".join(WORDS) + r")"


def to_int(token: str) -> int:
    return int(token) if token.isdigit() else WORDS[token]


def actuals() -> dict:
    agents = len(list((ROOT / "agents").glob("*.md")))
    commands = len(list((ROOT / "commands").glob("*.md")))
    skills = len(list((ROOT / "skills").glob("*/SKILL.md")))
    hooked = set(re.findall(r'"[^"]*/([\w.-]+\.sh)"', (ROOT / "hooks/hooks.json").read_text()))
    guardrails = len(hooked - OBSERVER_HOOKS)
    codex_hooks = len(list((ROOT / "codex/.codex/hooks").glob("*.sh")))
    return {
        "agents": agents,
        "commands": commands,
        "skills": skills,
        "guardrails": guardrails,
        "gemini_commands": commands - len(GEMINI_SKIPPED_COMMANDS),
        "codex_hooks": codex_hooks,
    }


# (file, human label, regex template with one NUM capture, actuals key)
CLAIMS = [
    (".claude-plugin/plugin.json", "agent count", NUM + r"-agent Laravel", "agents"),
    (".claude-plugin/plugin.json", "command count", NUM + r" workflow commands", "commands"),
    (".claude-plugin/plugin.json", "skill count", NUM + r" on-demand skills", "skills"),
    (".claude-plugin/plugin.json", "guardrail count", NUM + r" production guardrail hooks", "guardrails"),
    (".cursor-plugin/plugin.json", "agent count", NUM + r"-agent Laravel", "agents"),
    (".cursor-plugin/plugin.json", "command count", NUM + r" workflow commands", "commands"),
    (".cursor-plugin/plugin.json", "skill count", NUM + r" on-demand skills", "skills"),
    (".cursor-plugin/plugin.json", "guardrail count", NUM + r" production guardrail hooks", "guardrails"),
    (".claude-plugin/marketplace.json", "specialist count", NUM + r" specialists", "agents"),
    (".claude-plugin/marketplace.json", "command count", NUM + r" workflow commands", "commands"),
    (".claude-plugin/marketplace.json", "guardrail count", NUM + r" production guardrail hooks", "guardrails"),
    ("scripts/build-gemini-extension.py", "gemini command count", NUM + r" workflow commands", "gemini_commands"),
    ("scripts/build-gemini-extension.py", "agent count", NUM + r"-agent Laravel", "agents"),
    ("README.md", "install agent count", r"all " + NUM + r" agents", "agents"),
    ("README.md", "install command count", r"the " + NUM + r" slash commands", "commands"),
    ("README.md", "guardrail count", NUM + r" guardrail hooks \(wired through", "guardrails"),
    ("README.md", "skills count", r"\*\*" + NUM + r" skills\*\*", "skills"),
    ("README.md", "gemini command count", r"the " + NUM + r" commands as slash commands", "gemini_commands"),
    ("README.md", "codex hook count", r"the " + NUM + r" guardrail hooks as `PreToolUse`", "codex_hooks"),
]


def main() -> int:
    counts = actuals()
    fail = 0
    for rel, label, pattern, key in CLAIMS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        matches = re.findall(pattern, text)
        if not matches:
            print(f"::error file={rel}::claim phrase for {label} not found — "
                  f"wording changed? update scripts/check_inventory_sync.py in the same commit")
            fail = 1
            continue
        for token in matches:
            claimed = to_int(token)
            if claimed != counts[key]:
                print(f"::error file={rel}::{label} claims {claimed}, disk says {counts[key]}")
                fail = 1
    if fail == 0:
        print("ok: inventory claims match disk — " +
              ", ".join(f"{k}={v}" for k, v in counts.items()))
    return fail


if __name__ == "__main__":
    sys.exit(main())
