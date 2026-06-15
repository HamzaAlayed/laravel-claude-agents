#!/usr/bin/env python3
"""Strict-YAML validation of agent frontmatter.

Claude Code's frontmatter parser is lenient; Gemini CLI's is strict. A
description with an unquoted colon-space (`Vite: building`) parses under Claude
but breaks Gemini with "bad indentation of a mapping entry". This validates
every agent's frontmatter with a strict YAML parser so that class of bug can't
ship again.

    python3 scripts/validate-frontmatter.py

Validates both the canonical Claude agents (agents/*.md) and the generated
Gemini agents (gemini/agents/*.md). Exits non-zero on any failure.

Requires PyYAML (`pip install pyyaml`). If PyYAML is unavailable it prints a
notice and exits 0 — CI installs it explicitly, so it always runs there.
"""
import glob
import os
import sys

try:
    import yaml
except ImportError:
    print("notice: PyYAML not installed — skipping strict frontmatter validation "
          "(CI installs it). `pip install pyyaml` to run locally.")
    sys.exit(0)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def frontmatter(path):
    text = open(path).read()
    if not text.startswith("---"):
        raise ValueError("no frontmatter")
    return text.split("---", 2)[1]


def main():
    targets = sorted(
        glob.glob(os.path.join(ROOT, "agents", "*.md"))
        + glob.glob(os.path.join(ROOT, "gemini", "agents", "*.md"))
    )
    bad = 0
    for f in targets:
        rel = os.path.relpath(f, ROOT)
        try:
            data = yaml.safe_load(frontmatter(f))
            if not isinstance(data, dict):
                raise ValueError("frontmatter is not a mapping")
            if not data.get("name") or not data.get("description"):
                raise ValueError("missing name or description")
        except Exception as e:  # noqa: BLE001 - report every failure, keep going
            print("FAIL %s: %s" % (rel, e))
            bad += 1
    if bad:
        print("%d frontmatter file(s) failed strict YAML validation" % bad)
        return 1
    print("ok: %d agent frontmatter files parse as strict YAML" % len(targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
