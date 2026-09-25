#!/usr/bin/env python3
"""Validate and render the Laravel Guild enforcement map. Stdlib only."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "config" / "enforcement-map.json"
DOCUMENT = ROOT / "docs" / "enforcement-map.md"
LEVEL_ORDER = ["runtime", "pre-tool-hook", "ci", "operator", "prompt"]
REQUIRED_CONTROL_IDS = {
    "agent-policy-profiles",
    "path-ownership",
    "human-approvals",
    "criterion-evidence",
    "durable-checkpoints",
    "runtime-budgets",
    "loop-detection",
    "bounded-retries",
    "interruption-recovery",
    "feedback-routing",
    "orchestration-contract",
    "adversarial-gate",
    "delivery-observability",
    "outcome-benchmark",
    "laravel-benchmark-capture",
    "context-packets",
    "durable-memory-retrieval",
    "immutable-releases",
}
CONTROL_FIELDS = {
    "id",
    "title",
    "guarantee",
    "enforcement",
    "implementation",
    "evidence",
    "ciJobs",
    "failureMode",
    "operatorAction",
    "limitation",
}


class EnforcementMapError(ValueError):
    """The committed enforcement map is unsafe, incomplete, or stale."""


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "possibly empty " if allow_empty else "nonempty "
        raise EnforcementMapError(f"{label} must be a {qualifier}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise EnforcementMapError(f"{label} must contain nonempty strings")
    if len(value) != len(set(value)):
        raise EnforcementMapError(f"{label} contains duplicates")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnforcementMapError(f"{label} must be a nonempty string")
    return value.strip()


def _repo_file(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    path = pathlib.PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise EnforcementMapError(f"{label} must stay inside the repository: {raw}")
    candidate = root.joinpath(*path.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise EnforcementMapError(f"{label} is missing or escapes the repository: {raw}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise EnforcementMapError(f"{label} must be a regular non-symlink file: {raw}")
    return resolved


def load_manifest(path: pathlib.Path = MANIFEST) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnforcementMapError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EnforcementMapError("enforcement map must be a JSON object")
    return payload


def validate(
    payload: dict[str, Any], *, root: pathlib.Path = ROOT
) -> list[dict[str, Any]]:
    if payload.get("schemaVersion") != 1:
        raise EnforcementMapError("schemaVersion must be 1")
    _text(payload.get("scope"), "scope")
    limitations = _strings(payload.get("globalLimitations"), "globalLimitations")
    if len(limitations) < 3:
        raise EnforcementMapError("globalLimitations must state at least three trust boundaries")

    levels = payload.get("levels")
    if not isinstance(levels, dict) or list(levels) != LEVEL_ORDER:
        raise EnforcementMapError(
            "levels must declare runtime, pre-tool-hook, ci, operator, and prompt in order"
        )
    for name in LEVEL_ORDER:
        _text(levels[name], f"levels.{name}")

    try:
        release = json.loads(
            (root / "config" / "release-harness.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise EnforcementMapError(f"cannot read release harness: {exc}") from exc
    required_jobs = set(
        _strings(release.get("requiredCiJobs"), "release-harness requiredCiJobs")
    )

    controls = payload.get("controls")
    if not isinstance(controls, list) or not controls:
        raise EnforcementMapError("controls must be a nonempty list")

    seen: set[str] = set()
    for index, control in enumerate(controls):
        label = f"controls[{index}]"
        if not isinstance(control, dict) or set(control) != CONTROL_FIELDS:
            raise EnforcementMapError(
                f"{label} must declare exactly {sorted(CONTROL_FIELDS)}"
            )
        control_id = _text(control["id"], f"{label}.id")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", control_id):
            raise EnforcementMapError(f"{label}.id is not lower-kebab-case: {control_id}")
        if control_id in seen:
            raise EnforcementMapError(f"duplicate control id: {control_id}")
        seen.add(control_id)
        for field in ("title", "guarantee", "failureMode", "operatorAction", "limitation"):
            _text(control[field], f"{label}.{field}")

        enforcement = _strings(control["enforcement"], f"{label}.enforcement")
        unknown_levels = set(enforcement) - set(LEVEL_ORDER)
        if unknown_levels:
            raise EnforcementMapError(f"{label}.enforcement has unknown levels: {sorted(unknown_levels)}")
        if enforcement != [level for level in LEVEL_ORDER if level in enforcement]:
            raise EnforcementMapError(f"{label}.enforcement must follow the declared level order")
        if set(enforcement) == {"prompt"}:
            raise EnforcementMapError(f"{label} cannot claim enforcement from prompt text alone")

        for field in ("implementation", "evidence"):
            for raw in _strings(control[field], f"{label}.{field}"):
                _repo_file(root, raw, f"{label}.{field}")

        ci_jobs = _strings(control["ciJobs"], f"{label}.ciJobs", allow_empty=True)
        if "ci" in enforcement and not ci_jobs:
            raise EnforcementMapError(
                f"{label}.ciJobs is required when CI is an enforcement level"
            )
        if "ci" not in enforcement and ci_jobs:
            raise EnforcementMapError(f"{label}.ciJobs requires the ci enforcement level")
        unknown_jobs = set(ci_jobs) - required_jobs
        if unknown_jobs:
            raise EnforcementMapError(f"{label}.ciJobs are not release gates: {sorted(unknown_jobs)}")

    missing = REQUIRED_CONTROL_IDS - seen
    extra = seen - REQUIRED_CONTROL_IDS
    if missing or extra:
        raise EnforcementMapError(
            f"control inventory mismatch; missing={sorted(missing)} extra={sorted(extra)}"
        )
    return sorted(controls, key=lambda item: item["id"])


def _links(paths: list[str]) -> str:
    return ", ".join(f"[`{path}`](../{path})" for path in paths)


def render(payload: dict[str, Any], controls: list[dict[str, Any]]) -> str:
    lines = [
        "# Which Laravel Guild guarantees are actually enforced?",
        "",
        "Last verified 2026-09-25 against pack v9.4.0.",
        "",
        payload["scope"].strip(),
        "",
        "This page is generated from",
        "[`config/enforcement-map.json`](../config/enforcement-map.json). Edit the",
        "manifest, then run `python3 scripts/check-enforcement-map.py --write`.",
        "A prompt instruction is never presented as a hard control on its own.",
        "",
        "## Enforcement levels",
        "",
        "| Level | Meaning |",
        "| --- | --- |",
    ]
    for level in LEVEL_ORDER:
        lines.append(f"| `{level}` | {payload['levels'][level]} |")

    lines.extend([
        "",
        "## Control summary",
        "",
        "| Control | Enforcement | Failure mode |",
        "| --- | --- | --- |",
    ])
    for control in controls:
        levels = ", ".join(f"`{level}`" for level in control["enforcement"])
        lines.append(
            f"| [`{control['id']}`](#{control['id']}) — {control['title']} "
            f"| {levels} | {control['failureMode']} |"
        )

    lines.extend(["", "## Control details", ""])
    for control in controls:
        jobs = ", ".join(f"`{job}`" for job in control["ciJobs"]) or "None"
        levels = ", ".join(f"`{level}`" for level in control["enforcement"])
        lines.extend([
            f"### {control['id']}",
            "",
            f"**{control['title']}.** {control['guarantee']}",
            "",
            f"- Enforced by: {levels}",
            f"- Implementation: {_links(control['implementation'])}",
            f"- Evidence: {_links(control['evidence'])}",
            f"- Required CI: {jobs}",
            f"- Failure mode: {control['failureMode']}",
            f"- Operator action: {control['operatorAction']}",
            f"- Limitation: {control['limitation']}",
            "",
        ])

    lines.extend([
        "## What this map does not prove",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["globalLimitations"])
    lines.extend([
        "",
        "## Verify the map",
        "",
        "```sh",
        "python3 scripts/check-enforcement-map.py",
        "```",
        "",
        f"A healthy checkout reports `{len(controls)} controls` and exits `0`. The checker validates",
        "the exact control inventory, safe repository-local evidence paths, release-gated CI",
        "job names, enforcement-level ordering, and byte-for-byte agreement with this page.",
        "It does not execute commands stored in data files.",
        "",
        "## Symptoms",
        "",
        "- The checker reports an unknown control, missing evidence path, or non-release CI job.",
        "- This page differs from the deterministic render of the manifest.",
        "- A control's implementation or evidence moved without an enforcement-map update.",
        "- A statement is marked only as `prompt` but is described elsewhere as guaranteed.",
        "",
        "## Triage",
        "",
        "1. Run the checker and preserve its first error.",
        "2. Inspect the named control in `config/enforcement-map.json`.",
        "3. Confirm the implementation still rejects the documented failure case and that the",
        "   cited test exercises that boundary.",
        "4. Confirm every named CI job remains in `config/release-harness.json`.",
        "5. If only this generated page is stale, compare its diff before regenerating it.",
        "",
        "## Resolve",
        "",
        "1. Correct the manifest or restore the missing implementation/evidence file.",
        "2. Regenerate this page with `python3 scripts/check-enforcement-map.py --write`.",
        "3. Run the checker, the cited focused tests, and the full release gates.",
        "4. If a hard control became prompt-only, stop the release and either restore enforcement",
        "   or explicitly document the reduced guarantee as a breaking change.",
        "5. Roll back an unpublished map by restoring the manifest and generated page together.",
        "   Never preserve a stronger claim than the implementation and evidence support.",
        "",
        "Escalate to the release owner when a control has no executable evidence, a trust boundary",
        "is disputed, a required CI job must be removed, or the safe failure mode changed.",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="regenerate docs/enforcement-map.md"
    )
    args = parser.parse_args(argv)
    try:
        payload = load_manifest()
        controls = validate(payload)
        expected = render(payload, controls)
        if args.write:
            DOCUMENT.write_text(expected, encoding="utf-8")
            print(
                f"wrote {DOCUMENT.relative_to(ROOT)} from {MANIFEST.relative_to(ROOT)}"
            )
            return 0
        try:
            actual = DOCUMENT.read_text(encoding="utf-8")
        except OSError as exc:
            raise EnforcementMapError(f"cannot read {DOCUMENT}: {exc}") from exc
        if actual != expected:
            raise EnforcementMapError(
                "docs/enforcement-map.md is stale; run scripts/check-enforcement-map.py --write"
            )
    except EnforcementMapError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"ok: {len(controls)} enforcement controls have safe evidence "
        "and current documentation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
