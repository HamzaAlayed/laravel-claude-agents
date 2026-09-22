#!/usr/bin/env python3
"""Fail a live eval when a committed duration, token, or dollar ceiling is hit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(case_name, duration, baseline, cost, *, check_duration=True):
    case = (baseline.get("cases") or {}).get(case_name)
    if not isinstance(case, dict):
        return [f"baseline: FAIL no ceiling for {case_name}"]
    failures = []
    if check_duration:
        cap = case.get("max_seconds")
        if cap is None or duration > cap:
            failures.append(
                f"baseline: FAIL {cap}s ceiling ({duration}s)"
                if cap is not None else "baseline: FAIL duration ceiling unseeded"
            )
        else:
            print(f"   baseline: within {cap}s ceiling ({duration}s)")

    if not isinstance(cost, dict):
        failures.append("baseline: FAIL cost summary missing")
        return failures
    billed = (cost.get("billed") or {}).get("usd")
    usd_cap = case.get("max_usd")
    if billed is None or usd_cap is None:
        failures.append("baseline: FAIL billed USD or cost ceiling missing")
    elif billed > usd_cap:
        failures.append(
            f"baseline: FAIL ${usd_cap:.2f} cost ceiling (${billed:.2f} billed)"
        )
    else:
        print(f"   baseline: within ${usd_cap:.2f} cost ceiling (${billed:.2f} billed)")

    token_cap = case.get("max_tokens")
    actual = (((cost.get("attributed") or {}).get("total") or {}).get("tokens"))
    if actual is None or token_cap is None:
        failures.append("baseline: FAIL token total or ceiling missing")
    elif actual > token_cap:
        failures.append(
            f"baseline: FAIL {token_cap:,}-token ceiling ({actual:,} tokens)"
        )
    else:
        print(f"   baseline: within {token_cap:,}-token ceiling ({actual:,} tokens)")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--duration", required=True, type=int)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--cost", required=True, type=Path)
    parser.add_argument("--ignore-duration", action="store_true")
    args = parser.parse_args(argv)
    try:
        baseline = json.loads(args.baseline.read_text())
        cost = json.loads(args.cost.read_text())
    except (OSError, ValueError) as exc:
        print(f"   baseline: FAIL unreadable budget evidence: {exc}")
        return 1
    failures = evaluate(
        args.case,
        args.duration,
        baseline,
        cost,
        check_duration=not args.ignore_duration,
    )
    for failure in failures:
        print(f"   {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
