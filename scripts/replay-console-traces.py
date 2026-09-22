#!/usr/bin/env python3
"""Replay recorded SDK JSONL through the production console normalizer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "console"))
import events  # noqa: E402


def replay(path: Path):
    state = events.RunState(f"replay:{path.stem}")
    normalized = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            raw = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
        normalized.extend(events.normalize(raw, state))
    sequences = [event["seq"] for event in normalized]
    if sequences != list(range(1, len(sequences) + 1)):
        raise ValueError(f"{path}: normalized sequence is not contiguous")
    for event in normalized:
        if event.get("run_id") != state.run_id:
            raise ValueError(f"{path}: event lost run correlation")
        if event.get("type") in {"tool_use", "tool_result"} and "tool_use_id" not in event:
            raise ValueError(f"{path}: tool event lost tool_use_id")
    return normalized


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    total = 0
    for path in args.paths:
        normalized = replay(path)
        total += len(normalized)
        print(f"PASS {path}: {len(normalized)} normalized events")
    if total == 0:
        print("FAIL: fixtures produced no normalized events", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
