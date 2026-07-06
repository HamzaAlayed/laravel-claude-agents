#!/usr/bin/env python3
"""Fail when the guardrail hook list drifts between its three homes.

The same hook set is declared in three places that history shows get edited
independently: the plugin manifest (hooks/hooks.json), the installer merge
list (install.sh), and the README's Guardrail scripts section. This check
makes CI the single enforcer: all three must name exactly the same scripts,
and every named script must exist and be executable.

    python3 scripts/check-hook-sync.py
"""
import json
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_RE = re.compile(r"([a-z0-9-]+\.sh)\b")


def from_hooks_json():
    with open(os.path.join(ROOT, "hooks", "hooks.json")) as f:
        data = json.load(f)
    names = set()
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            for h in entry.get("hooks", []):
                m = SCRIPT_RE.search(h.get("command", ""))
                if m:
                    names.add(m.group(1))
    return names


def from_install_sh():
    with open(os.path.join(ROOT, "install.sh")) as f:
        text = f.read()
    m = re.search(r"desired = \[(.*?)\]", text, re.S)
    if not m:
        raise ValueError("install.sh: `desired = [...]` list not found")
    return set(SCRIPT_RE.findall(m.group(1)))


def from_readme():
    with open(os.path.join(ROOT, "README.md")) as f:
        text = f.read()
    m = re.search(r"## Guardrail scripts\n(.*?)\n## ", text, re.S)
    if not m:
        raise ValueError("README.md: `## Guardrail scripts` section not found")
    # Codex variant is documented in the codex install path, not wired here;
    # install.sh is mentioned as prose, not as a hook script.
    excluded = {"install.sh", "install-codex.sh"}
    return {n for n in SCRIPT_RE.findall(m.group(1))
            if not n.startswith("codex-") and n not in excluded}


def main():
    sources = {
        "hooks/hooks.json": from_hooks_json(),
        "install.sh": from_install_sh(),
        "README.md (Guardrail scripts)": from_readme(),
    }
    union = set().union(*sources.values())
    bad = 0
    for name, found in sources.items():
        missing = union - found
        if missing:
            print("FAIL %s missing: %s" % (name, ", ".join(sorted(missing))))
            bad += 1
    for script in sorted(union):
        path = os.path.join(ROOT, "scripts", script)
        if not os.path.isfile(path):
            print("FAIL scripts/%s named in hook config but does not exist" % script)
            bad += 1
        elif not os.stat(path).st_mode & stat.S_IXUSR:
            print("FAIL scripts/%s is not executable" % script)
            bad += 1
    if bad:
        return 1
    print("ok: %d guardrail scripts in sync across hooks.json, install.sh, README" % len(union))
    return 0


if __name__ == "__main__":
    sys.exit(main())
