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

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GEMINI_SKIPPED_COMMANDS = {"board.md", "console.md"}  # kept in sync with build-gemini-extension.py
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
    m = re.search(r"^ALL_CASES=\(([^)]*)\)", (ROOT / "tests/eval/run-evals.sh").read_text(), re.M)
    eval_cases = len(m.group(1).split()) if m else 0
    return {
        "agents": agents,
        "commands": commands,
        "skills": skills,
        "guardrails": guardrails,
        "gemini_commands": commands - len(GEMINI_SKIPPED_COMMANDS),
        "codex_hooks": codex_hooks,
        "eval_cases": eval_cases,
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
    (".cursor-plugin/marketplace.json", "specialist count", NUM + r" specialists", "agents"),
    (".cursor-plugin/marketplace.json", "command count", NUM + r" workflow commands", "commands"),
    (".cursor-plugin/marketplace.json", "guardrail count", NUM + r" production guardrail hooks", "guardrails"),
    ("scripts/build-gemini-extension.py", "gemini command count", NUM + r" workflow commands", "gemini_commands"),
    ("scripts/build-gemini-extension.py", "agent count", NUM + r"-agent Laravel", "agents"),
    ("README.md", "install agent count", r"all " + NUM + r" agents", "agents"),
    ("README.md", "install command count", r"the " + NUM + r" slash commands", "commands"),
    ("README.md", "guardrail count", NUM + r" guardrail hooks \(wired through", "guardrails"),
    ("README.md", "skills count", r"\*\*" + NUM + r" skills\*\*", "skills"),
    ("README.md", "gemini command count", r"the " + NUM + r" commands as slash commands", "gemini_commands"),
    ("README.md", "codex hook count", r"the " + NUM + r" guardrail hooks as `PreToolUse`", "codex_hooks"),
    ("README.md", "eval case count", r"the " + NUM + r" eval cases", "eval_cases"),
]


# Manifests whose declared version must equal VERSION. `.cursor-plugin/
# marketplace.json` sat at 1.17.0 for ten releases because nothing checked it:
# the release sed listed the files by hand and this one fell off the list.
VERSIONED = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".cursor-plugin/marketplace.json",
    "gemini/gemini-extension.json",
]


def _versions(node):
    """Every `version` string in a manifest, at any nesting depth.

    Walked rather than indexed because plugin.json declares it at the top level
    while marketplace.json nests it under `plugins[]` — and a check that only
    looked where it expected the field is how this drifted in the first place.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "version" and isinstance(value, str):
                yield value
            else:
                yield from _versions(value)
    elif isinstance(node, list):
        for item in node:
            yield from _versions(item)


def check_versions(expected: str) -> int:
    fail = 0
    for rel in VERSIONED:
        found = list(_versions(json.loads((ROOT / rel).read_text(encoding="utf-8"))))
        if not found:
            print(f"::error file={rel}::no version field found — moved or renamed? "
                  f"update scripts/check_inventory_sync.py in the same commit")
            fail = 1
        for value in found:
            if value != expected:
                print(f"::error file={rel}::declares version {value}, VERSION says {expected}")
                fail = 1
    return fail


def main() -> int:
    counts = actuals()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    fail = check_versions(version)
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
        print(f"ok: every manifest declares {version}; inventory claims match disk — " +
              ", ".join(f"{k}={v}" for k, v in counts.items()))
    return fail


if __name__ == "__main__":
    sys.exit(main())
