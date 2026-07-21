#!/usr/bin/env python3
"""Ratchet budget: agent bodies, descriptions, and skills must not outgrow the
committed baseline (scripts/body_budget.json).

Why: bodies creep a little every release; each addition looks harmless and the
sum degrades routing (descriptions) and per-invocation cost (bodies, skills).
The budget freezes the current size + headroom; CI fails on any regression.

  python3 scripts/check_body_budget.py            # check against baseline
  python3 scripts/check_body_budget.py --reseed   # rewrite baseline = actual +10%

Over budget  -> ::error annotation, exit 1.
Under budget by >15% -> notice suggesting --reseed to lock in the win (exit 0).
No dependencies beyond the stdlib.
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET_FILE = Path(__file__).resolve().parent / "body_budget.json"
HEADROOM = 1.10  # reseed baseline = actual +10%
TIGHTEN_AT = 0.85  # actual below 85% of budget -> suggest reseeding


def measure() -> dict:
    actual = {"agents": {}, "skills": {}}
    for f in sorted((ROOT / "agents").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        desc = next(
            (l for l in text.splitlines() if l.startswith("description:")), ""
        )
        actual["agents"][f.stem] = {
            "lines": text.count("\n"),
            "description_chars": len(desc),
        }
    for f in sorted((ROOT / "skills").glob("*/SKILL.md")):
        actual["skills"][f.parent.name] = {"lines": f.read_text(encoding="utf-8").count("\n")}
    return actual


def reseed(actual: dict) -> None:
    budget = {
        "_policy": (
            "ratchet: CI fails when any actual exceeds its budget; "
            "reseed with --reseed after a deliberate, reviewed size change"
        ),
        "agents": {
            name: {k: math.ceil(v * HEADROOM) for k, v in m.items()}
            for name, m in actual["agents"].items()
        },
        "skills": {
            name: {k: math.ceil(v * HEADROOM) for k, v in m.items()}
            for name, m in actual["skills"].items()
        },
    }
    BUDGET_FILE.write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
    print(f"reseeded {BUDGET_FILE.relative_to(ROOT)} (actual +{int((HEADROOM-1)*100)}%)")


def check(actual: dict) -> int:
    if not BUDGET_FILE.exists():
        print(f"::error::{BUDGET_FILE.relative_to(ROOT)} missing — run --reseed and commit it")
        return 1
    budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
    fail = 0
    for kind in ("agents", "skills"):
        for name, metrics in actual[kind].items():
            b = budget.get(kind, {}).get(name)
            path = f"{kind}/{name}" + ("/SKILL.md" if kind == "skills" else ".md")
            if b is None:
                print(f"::error file={path}::new {kind[:-1]} '{name}' has no budget — add it via --reseed")
                fail = 1
                continue
            for metric, value in metrics.items():
                cap = b.get(metric)
                if cap is None:
                    continue
                if value > cap:
                    print(f"::error file={path}::{metric} {value} exceeds budget {cap} — trim, or reseed deliberately")
                    fail = 1
                elif value < cap * TIGHTEN_AT:
                    print(f"notice: {path} {metric} {value} is well under budget {cap} — consider --reseed to lock it in")
        for name in budget.get(kind, {}):
            if name not in actual[kind]:
                print(f"::error::budget entry '{kind}/{name}' has no file — remove it via --reseed")
                fail = 1
    if fail == 0:
        n = len(actual["agents"]) + len(actual["skills"])
        print(f"ok: {n} bodies/skills within budget")
    return fail


def main() -> int:
    actual = measure()
    if "--reseed" in sys.argv:
        reseed(actual)
        return 0
    return check(actual)


if __name__ == "__main__":
    sys.exit(main())
