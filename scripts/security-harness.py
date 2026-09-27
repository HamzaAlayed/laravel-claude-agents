#!/usr/bin/env python3
"""Validate Agent Security & Governance policy and issue source-bound receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from typing import Any


DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY_PATH = pathlib.PurePosixPath("config/security-harness.json")
ATTACK_PATH = pathlib.PurePosixPath("config/security-attacks.json")
STRIDE = {
    "spoofing",
    "tampering",
    "repudiation",
    "information-disclosure",
    "denial-of-service",
    "elevation-of-privilege",
}
CONTROL_FIELDS = {
    "id", "threats", "mode", "implementation", "evidence", "failure", "limitation"
}
ATTACK_FIELDS = {
    "id", "name", "threat", "control", "vector", "expectedDecision", "expectedSideEffects"
}


class SecurityHarnessError(ValueError):
    """A policy, attack registry, or receipt is unsafe or inconsistent."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical(value))


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecurityHarnessError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SecurityHarnessError(f"{label} must be a JSON object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SecurityHarnessError(f"{label} must be nonempty text")
    return value.strip()


def strings(value: Any, label: str, *, exact: set[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise SecurityHarnessError(f"{label} must be a nonempty string list")
    if len(value) != len(set(value)):
        raise SecurityHarnessError(f"{label} contains duplicates")
    if exact is not None and set(value) != exact:
        raise SecurityHarnessError(f"{label} inventory mismatch")
    return value


def repo_file(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    path = pathlib.PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise SecurityHarnessError(f"{label} must stay inside the repository")
    candidate = root.joinpath(*path.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise SecurityHarnessError(f"{label} is missing or escapes the repository") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise SecurityHarnessError(f"{label} must be a regular non-symlink file")
    return resolved


def validate(root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_json(root / POLICY_PATH, str(POLICY_PATH))
    attacks = load_json(root / ATTACK_PATH, str(ATTACK_PATH))
    if policy.get("schemaVersion") != 1 or policy.get("receiptSchemaVersion") != 1:
        raise SecurityHarnessError("security policy schema versions must be 1")
    policy_id = text(policy.get("policyId"), "policyId")
    text(policy.get("scope"), "scope")

    model = policy.get("threatModel")
    if not isinstance(model, dict) or model.get("framework") != "STRIDE":
        raise SecurityHarnessError("threatModel.framework must be STRIDE")
    strings(model.get("categories"), "threatModel.categories", exact=STRIDE)
    strings(model.get("assets"), "threatModel.assets")
    limitations = strings(model.get("limitations"), "threatModel.limitations")
    if len(limitations) < 4:
        raise SecurityHarnessError("threatModel.limitations must name at least four boundaries")
    boundaries = model.get("boundaries")
    if not isinstance(boundaries, list) or len(boundaries) < 6:
        raise SecurityHarnessError("threatModel.boundaries must enumerate trust sources")
    boundary_ids: set[str] = set()
    authorizers: set[str] = set()
    for index, boundary in enumerate(boundaries):
        if not isinstance(boundary, dict) or set(boundary) != {"id", "source", "trust", "canAuthorize"}:
            raise SecurityHarnessError(f"threatModel.boundaries[{index}] has invalid fields")
        boundary_id = text(boundary["id"], f"boundary {index} id")
        text(boundary["source"], f"boundary {index} source")
        text(boundary["trust"], f"boundary {index} trust")
        if not isinstance(boundary["canAuthorize"], bool):
            raise SecurityHarnessError(f"boundary {boundary_id} canAuthorize must be boolean")
        if boundary_id in boundary_ids:
            raise SecurityHarnessError(f"duplicate boundary: {boundary_id}")
        boundary_ids.add(boundary_id)
        if boundary["canAuthorize"]:
            authorizers.add(boundary_id)
    if authorizers != {"runtime-policy", "user-decision"}:
        raise SecurityHarnessError("only runtime policy and explicit user decisions may authorize")

    authority = policy.get("authority")
    expected_authority = {
        "instructionOrder": ["runtime-policy", "user-decision", "validated-project-policy", "task-plan", "untrusted-data"],
        "protectedActionApprovalAuthority": "user",
        "selfApprovalAllowed": False,
        "incidentAction": "stop-and-escalate",
    }
    if authority != expected_authority:
        raise SecurityHarnessError("authority policy is not the fail-closed canonical contract")
    capabilities = policy.get("capabilities")
    if capabilities != {
        "agentRegistry": "config/agent-harness.json",
        "defaultSecretAccess": "deny",
        "mutationScope": "declared-owned-paths",
        "unknownCapability": "deny",
        "networkEgressWithDynamicData": "deny",
    }:
        raise SecurityHarnessError("capability policy is not least privilege")

    controls = policy.get("controls")
    if not isinstance(controls, list) or len(controls) < 6:
        raise SecurityHarnessError("controls must contain at least six entries")
    control_ids: set[str] = set()
    covered_threats: set[str] = set()
    for index, control in enumerate(controls):
        label = f"controls[{index}]"
        if not isinstance(control, dict) or set(control) != CONTROL_FIELDS:
            raise SecurityHarnessError(f"{label} has invalid fields")
        control_id = text(control["id"], f"{label}.id")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", control_id) or control_id in control_ids:
            raise SecurityHarnessError(f"{label}.id is invalid or duplicated")
        control_ids.add(control_id)
        threats = set(strings(control["threats"], f"{label}.threats"))
        if not threats <= STRIDE:
            raise SecurityHarnessError(f"{label}.threats contains a non-STRIDE category")
        covered_threats |= threats
        text(control["mode"], f"{label}.mode")
        text(control["failure"], f"{label}.failure")
        text(control["limitation"], f"{label}.limitation")
        for field in ("implementation", "evidence"):
            for raw in strings(control[field], f"{label}.{field}"):
                repo_file(root, raw, f"{label}.{field}")
    if covered_threats != STRIDE:
        raise SecurityHarnessError("controls must cover every STRIDE category")

    if policy.get("attackManifest") != str(ATTACK_PATH):
        raise SecurityHarnessError("attackManifest must name the canonical registry")
    if attacks.get("schemaVersion") != 1 or attacks.get("policyId") != policy_id:
        raise SecurityHarnessError("attack registry schema or policyId mismatch")
    rows = attacks.get("attacks")
    if not isinstance(rows, list) or len(rows) < 12:
        raise SecurityHarnessError("attack registry must contain at least twelve attacks")
    attack_ids: set[str] = set()
    attacked_controls: set[str] = set()
    attacked_threats: set[str] = set()
    for index, attack in enumerate(rows):
        label = f"attacks[{index}]"
        if not isinstance(attack, dict) or set(attack) != ATTACK_FIELDS:
            raise SecurityHarnessError(f"{label} has invalid fields")
        attack_id = text(attack["id"], f"{label}.id")
        if not re.fullmatch(r"SEC-[0-9]{3}", attack_id) or attack_id in attack_ids:
            raise SecurityHarnessError(f"{label}.id is invalid or duplicated")
        attack_ids.add(attack_id)
        attacked_controls.add(text(attack["control"], f"{label}.control"))
        attacked_threats.add(text(attack["threat"], f"{label}.threat"))
        for field in ("name", "vector", "expectedDecision", "expectedSideEffects"):
            text(attack[field], f"{label}.{field}")
        if attack["expectedSideEffects"] != "none":
            raise SecurityHarnessError(f"{label} must require zero side effects")
    if attacked_controls != control_ids:
        raise SecurityHarnessError("every control must have at least one registered attack")
    if attacked_threats != STRIDE:
        raise SecurityHarnessError("attacks must exercise every STRIDE category")

    receipt = policy.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("kind") != "security-posture":
        raise SecurityHarnessError("receipt contract is missing")
    if receipt.get("algorithm") != "sha256-canonical-json" or receipt.get("status") != "pass-only":
        raise SecurityHarnessError("receipt must be canonical, source-bound, and pass-only")
    sources = strings(receipt.get("sourceFiles"), "receipt.sourceFiles")
    for raw in sources:
        repo_file(root, raw, "receipt source")
    excluded = set(strings(receipt.get("excludedRawData"), "receipt.excludedRawData"))
    if not {"prompts", "tool output", "commands", "environment values", "secret material"} <= excluded:
        raise SecurityHarnessError("receipt exclusion policy may not retain sensitive raw inputs")
    text(receipt.get("artifactPattern"), "receipt.artifactPattern")

    agent_harness = load_json(root / "config/agent-harness.json", "agent harness")
    shared = agent_harness.get("shared", {})
    if shared.get("securityPolicy") != {
        "manifest": "config/security-harness.json",
        "sourceTrust": "untrusted-data-not-instructions",
        "secretAccess": "deny",
        "protectedActionAuthority": "user",
        "incidentPolicy": "stop-and-escalate",
        "receipt": "security-posture",
    }:
        raise SecurityHarnessError("agent harness is not bound to the security policy")

    contract = (root / "config/orchestration-contract.md").read_text(encoding="utf-8")
    if contract.count("> **Security boundary:**") != 1:
        raise SecurityHarnessError("canonical orchestration contract lacks one security boundary")
    for relative in ("hooks/hooks.json", "gemini/hooks/hooks.json", "codex/.codex/hooks.json"):
        body = repo_file(root, relative, relative).read_text(encoding="utf-8")
        if "enforce-sensitive-access.sh" not in body:
            raise SecurityHarnessError(f"{relative} does not wire sensitive-access enforcement")
    return policy, attacks


def build_receipt(root: pathlib.Path, policy: dict[str, Any], attacks: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, str] = {}
    for raw in policy["receipt"]["sourceFiles"]:
        path = repo_file(root, raw, "receipt source")
        sources[raw] = digest_bytes(path.read_bytes())
    receipt: dict[str, Any] = {
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": policy["receipt"]["kind"],
        "policyId": policy["policyId"],
        "status": "pass",
        "summary": {
            "boundaries": len(policy["threatModel"]["boundaries"]),
            "controls": len(policy["controls"]),
            "attacks": len(attacks["attacks"]),
            "strideCategories": len(STRIDE),
            "sideEffectPolicy": "none-on-deny",
        },
        "sources": sources,
    }
    receipt["receiptHash"] = digest_json(receipt)
    return receipt


def verify_receipt(root: pathlib.Path, receipt: dict[str, Any], policy: dict[str, Any], attacks: dict[str, Any]) -> None:
    expected = build_receipt(root, policy, attacks)
    if receipt != expected:
        raise SecurityHarnessError("security posture receipt is stale, source-drifted, or tampered")


def write_receipt(path: pathlib.Path, receipt: dict[str, Any], root: pathlib.Path, policy: dict[str, Any]) -> None:
    candidate = path.expanduser()
    if candidate.is_symlink() or (candidate.exists() and not candidate.is_file()):
        raise SecurityHarnessError("receipt output must be a regular non-symlink file")
    try:
        parent = candidate.parent.resolve(strict=True)
    except OSError as exc:
        raise SecurityHarnessError("receipt output parent does not exist") from exc
    if not parent.is_dir():
        raise SecurityHarnessError("receipt output parent must be a directory")
    resolved = parent / candidate.name
    protected = {
        repo_file(root, raw, "receipt source").resolve()
        for raw in policy["receipt"]["sourceFiles"]
    }
    if resolved.resolve(strict=False) in protected:
        raise SecurityHarnessError("receipt output cannot replace a sealed source")
    if candidate.exists() and candidate.stat().st_size:
        raise SecurityHarnessError("receipt output already exists and is nonempty")
    body = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=parent, prefix=f".{candidate.name}.", delete=False
    ) as handle:
        temporary = pathlib.Path(handle.name)
        try:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, resolved)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("validate", "audit", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
        if name == "audit":
            command.add_argument("--output", type=pathlib.Path, required=True)
        if name == "verify":
            command.add_argument("--receipt", type=pathlib.Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    try:
        policy, attacks = validate(root)
        if args.command == "audit":
            receipt = build_receipt(root, policy, attacks)
            write_receipt(args.output, receipt, root, policy)
            print(f"PASS: security posture receipt written ({len(attacks['attacks'])} attacks registered)")
        elif args.command == "verify":
            if args.receipt.is_symlink() or not args.receipt.is_file():
                raise SecurityHarnessError("security posture receipt must be a regular non-symlink file")
            receipt = load_json(args.receipt, "security posture receipt")
            verify_receipt(root, receipt, policy, attacks)
            print("PASS: security posture receipt is authentic and source-current")
        else:
            print(
                f"PASS: {len(policy['controls'])} controls, {len(attacks['attacks'])} attacks, "
                f"and {len(policy['threatModel']['boundaries'])} trust boundaries are valid"
            )
    except (OSError, SecurityHarnessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
