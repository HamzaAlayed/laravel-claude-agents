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

import hashlib
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
    evals_src = (ROOT / "tests/eval/run-evals.sh").read_text()
    m = re.search(r"^ALL_CASES=\(([^)]*)\)", evals_src, re.M)
    eval_cases = len(m.group(1).split()) if m else 0
    return {
        "agents": agents,
        "commands": commands,
        "skills": skills,
        "guardrails": guardrails,
        "gemini_commands": commands - len(GEMINI_SKIPPED_COMMANDS),
        "codex_hooks": codex_hooks,
        "eval_cases": eval_cases,
        "eval_answer_checks": count_eval_answer_checks(evals_src),
    }


def count_eval_answer_checks(evals_src: str) -> int:
    """Count the individual CHECKs the answer key dispatches, one per logical
    check — matched against docs/evals/2026-08-06-check-audit.md's own
    "Tally: N checks" sentence via the CLAIMS table below.

    Restricted to the section after the answer-key marker (checks_* function
    definitions only) so a `check_*` mention in a helper's own comment or an
    unrelated `record` call above it can't inflate the count. Three line
    shapes cover every check in the current file, and each contributes
    exactly one count per logical check:
      - `check_<name> ...`  — the ordinary call-site style (one line, one check).
      - `record $? ...`     — hygiene's inline non-if/else style (one line, one check).
      - `record 0 ...`      — the PASS branch of an if/else inline check
        (teach_delivery's style). Counting only the `record 0` line — never
        `record 1` too — is deliberate: each if/else pair emits BOTH a
        `record 0` and a `record 1` line for the SAME logical check, so
        counting both would double-count it.
    A check written in any other shape (a loop, a case statement, a helper
    that calls `record` conditionally without either literal) will not match
    any of the three and silently falls out of this count — but it can't fall
    out silently for long: the CLAIMS row below binds this number to the audit
    doc's own tally sentence, so the two drifting apart fails CI, mentioning
    the audit doc, until one of them is corrected in the same commit.
    """
    marker = "# ------------------------------------------------------------- answer key ----"
    if marker not in evals_src:
        return 0
    section = evals_src[evals_src.index(marker):]
    calls = re.findall(r"^[ \t]+check_[a-z_]+ ", section, re.M)
    inline_single = re.findall(r"^[ \t]+record \$\? ", section, re.M)
    inline_if_else = re.findall(r"^[ \t]+record 0 ", section, re.M)
    return len(calls) + len(inline_single) + len(inline_if_else)


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
    ("docs/evals/2026-08-06-check-audit.md", "audit tally",
     r"Tally: " + NUM + r" checks", "eval_answer_checks"),
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


def coordinator_hash(root: Path) -> str:
    """sha256 over the surfaces that steer delegation: the coordinator body,
    plus each distinct `> **Interface:**` line from commands/*.md (sorted).

    Whole-command hashing would fire on prose edits that change no behaviour;
    the Interface line is the only part of a command the eval `feature` case's
    checks depend on. Dropping a command's Interface block entirely would not
    move this hash (set of distinct lines, not per-file), but that blind spot
    is covered by two guardrails ratchets, not this one: `tests/guardrails.
    test.sh` pins the carrier count ("all 9 pipeline commands carry the
    Interface block" == 9, so a drop trips 9->8) and the block's byte-identity
    across all nine commands ("Interface block is byte-identical across them"
    == 1).
    """
    parts = [(root / "agents" / "delivery-coordinator.md").read_bytes()]
    lines = set()
    for path in sorted((root / "commands").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("> **Interface:**"):
                lines.add(line)
    parts.extend(line.encode("utf-8") for line in sorted(lines))
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def check_coordinator_hash(root: Path) -> int:
    """The `feature` eval case's trigger, made deterministic.

    'Run it when coordinator behaviour changes' had no named judge and would
    silently never fire (2026-08-05 review, gap: feature-case trigger). CI
    cannot run billed evals; it can refuse to let delegation-steering surfaces
    ship changed unless a human records a re-run (update sha256/as_of) or a
    dated waiver in tests/eval/baseline.json.
    """
    baseline = json.loads(
        (root / "tests" / "eval" / "baseline.json").read_text(encoding="utf-8"))
    pinned = baseline.get("coordinator_hash")
    if not pinned:
        print("::error file=tests/eval/baseline.json::coordinator_hash pin is "
              "missing — seed it from scripts/check_inventory_sync.py "
              "coordinator_hash() and record as_of + note")
        return 1
    current = coordinator_hash(root)
    accepted = {pinned.get("sha256")}
    for waiver in pinned.get("waivers", []):
        # The message below promises "a dated waiver with a reason"; enforce it,
        # or the audit trail the waiver shape exists for is honor-system.
        if waiver.get("date") and waiver.get("reason"):
            accepted.add(waiver.get("sha256"))
    if current in accepted:
        return 0
    print(f"::error file=agents/delivery-coordinator.md::delegation-steering "
          f"surfaces changed since the feature case last ran (hash "
          f"{current[:12]}… is neither pinned nor waived) — run "
          f"./tests/eval/run-evals.sh feature and update coordinator_hash in "
          f"tests/eval/baseline.json, or add a dated waiver with a reason")
    return 1


def main() -> int:
    counts = actuals()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    fail = check_versions(version)
    if check_coordinator_hash(ROOT):
        fail = 1
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
