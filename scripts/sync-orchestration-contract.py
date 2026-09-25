#!/usr/bin/env python3
"""Materialize the canonical orchestration contract into every runtime carrier.

Claude slash commands do not load the delivery-coordinator agent body, while a
direct coordinator session does not load a slash command. The contract must
therefore remain inline in both surfaces. This script makes those copies
generated artifacts backed by one reviewed source.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = pathlib.Path("config/orchestration-contract.md")
START = "<!-- BEGIN GENERATED ORCHESTRATION CONTRACT -->"
END = "<!-- END GENERATED ORCHESTRATION CONTRACT -->"
LABELS = (
    "> **Interface:**",
    "> **Durable checkpoints:**",
    "> **Loop guard:**",
    "> **Retry transitions:**",
    "> **Feedback routing:**",
    "> **Interruption recovery:**",
    "> **Delivery observability:**",
    "> **Context packets:**",
    "> **Outcome benchmarks:**",
)
LEGACY_LABELS = LABELS[:6]
COMMANDS = (
    "commands/add-policy.md",
    "commands/add-test.md",
    "commands/audit-n-plus-one.md",
    "commands/make-feature.md",
    "commands/optimize-query.md",
    "commands/refactor-to-action.md",
    "commands/review-pr.md",
    "commands/ship-checklist.md",
    "commands/upgrade-laravel.md",
)
CARRIERS = COMMANDS + ("agents/delivery-coordinator.md",)


class ContractError(RuntimeError):
    """The canonical contract or a generated carrier is structurally invalid."""


def load_contract(root: pathlib.Path) -> str:
    path = root / SOURCE
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read canonical contract: {SOURCE}") from exc
    if not raw.endswith("\n") or raw.endswith("\n\n"):
        raise ContractError("canonical contract must end with exactly one newline")
    contract = raw[:-1]
    if START in contract or END in contract:
        raise ContractError("canonical contract must not contain generated markers")
    lines = contract.splitlines()
    for label in LABELS:
        if sum(line.startswith(label) for line in lines) != 1:
            raise ContractError(f"canonical contract requires exactly one {label}")
    positions = [next(i for i, line in enumerate(lines) if line.startswith(label))
                 for label in LABELS]
    if positions != sorted(positions):
        raise ContractError("canonical contract headings are out of order")
    if any(line and not line.startswith("> ") for line in lines):
        raise ContractError("canonical contract may contain only blockquotes and blanks")
    return contract


def generated(contract: str) -> str:
    return f"{START}\n{contract}\n{END}"


def marker_span(text: str, relative: str) -> tuple[int, int]:
    if text.count(START) != 1 or text.count(END) != 1:
        raise ContractError(f"{relative}: requires exactly one generated marker pair")
    start = text.index(START)
    end_at = text.index(END)
    if end_at < start:
        raise ContractError(f"{relative}: generated markers are reversed")
    end = end_at + len(END)
    return start, end


def legacy_span(text: str, relative: str) -> tuple[int, int]:
    """Locate an unmarked orchestration block for one-time migration."""
    starts = list(re.finditer(r"^> \*\*Interface:\*\*", text, re.MULTILINE))
    end_label = next(
        (
            label
            for label in reversed(LABELS)
            if re.search(rf"^{re.escape(label)}", text, re.MULTILINE)
        ),
        "> **Interruption recovery:**",
    )
    ends = list(re.finditer(rf"^{re.escape(end_label)}.*$", text, re.MULTILINE))
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].start():
        raise ContractError(f"{relative}: cannot locate the legacy contract block")
    block = text[starts[0].start():ends[0].end()]
    for label in LEGACY_LABELS:
        if block.count(label) != 1:
            raise ContractError(f"{relative}: legacy contract is incomplete")
    return starts[0].start(), ends[0].end()


def render(text: str, contract: str, relative: str, *, migrate: bool) -> str:
    try:
        start, end = marker_span(text, relative)
    except ContractError:
        if not migrate or START in text or END in text:
            raise
        start, end = legacy_span(text, relative)
    return text[:start] + generated(contract) + text[end:]


def discovered_carriers(root: pathlib.Path) -> set[str]:
    found = set()
    for directory in ("commands", "agents"):
        for path in (root / directory).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"^> \*\*Interface:\*\*", text, re.MULTILINE):
                found.add(path.relative_to(root).as_posix())
    return found


def sync(root: pathlib.Path, *, write: bool) -> list[str]:
    root = pathlib.Path(root)
    contract = load_contract(root)
    expected_carriers = set(CARRIERS)
    discovered = discovered_carriers(root)
    if discovered != expected_carriers:
        missing = sorted(expected_carriers - discovered)
        unexpected = sorted(discovered - expected_carriers)
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected: " + ", ".join(unexpected))
        # During the one-time coordinator migration, its empty marker pair has
        # no Interface line until --write materializes it.
        if not (write and missing == ["agents/delivery-coordinator.md"] and not unexpected):
            raise ContractError("contract carrier set changed (" + "; ".join(detail) + ")")

    changed = []
    for relative in CARRIERS:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ContractError(f"cannot read contract carrier: {relative}") from exc
        rendered = render(text, contract, relative, migrate=write)
        if rendered != text:
            changed.append(relative)
            if write:
                path.write_text(rendered, encoding="utf-8")
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sync-orchestration-contract.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail when a carrier drifted")
    mode.add_argument("--write", action="store_true", help="regenerate every carrier")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        changed = sync(ROOT, write=args.write)
    except ContractError as exc:
        print(f"orchestration contract invalid: {exc}", file=sys.stderr)
        return 2
    if changed and args.check:
        for relative in changed:
            print(
                f"::error file={relative}::generated orchestration contract is stale; "
                "run python3 scripts/sync-orchestration-contract.py --write"
            )
        return 1
    action = "updated" if changed else "verified"
    print(f"{action}: canonical orchestration contract across {len(CARRIERS)} carriers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
