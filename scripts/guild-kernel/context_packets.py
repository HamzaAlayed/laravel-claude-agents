"""Build and verify bounded, source-bound context packets. Stdlib only."""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
import tempfile
from datetime import datetime, timezone

import kernel


class ContextPacketError(ValueError):
    """The packet, source specification, or current source state is unsafe."""


SPEC_FIELDS = {
    "schemaVersion",
    "summary",
    "projectConstraints",
    "completedWork",
    "nextAction",
    "sources",
}
SOURCE_FIELDS = {
    "path",
    "purpose",
    "priority",
    "required",
    "startLine",
    "endLine",
}
PACKET_SOURCE_FIELDS = SOURCE_FIELDS | {
    "trust",
    "fullFileSha256",
    "excerptSha256",
    "content",
}
PACKET_FIELDS = {
    "schemaVersion",
    "kind",
    "generatedAt",
    "delivery",
    "stage",
    "audience",
    "authority",
    "sources",
    "currentState",
    "outputContract",
    "integrity",
    "budget",
    "packetHash",
}
MANIFEST_FIELDS = {
    "schemaVersion",
    "packetSchemaVersion",
    "artifactPattern",
    "defaultMaxTokens",
    "minimumMaxTokens",
    "maximumMaxTokens",
    "tokenEstimator",
    "trimStrategy",
    "hashAlgorithm",
    "staleSourcePolicy",
    "authorityOrder",
    "mandatorySections",
    "sourceTrust",
    "excludedPathParts",
    "secretPatterns",
    "systemRules",
}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*"
        r"['\"][^'\"\r\n]{20,}['\"]"
    ),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _serialized(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _hash_json(value):
    return _hash_bytes(_canonical(value).encode("utf-8"))


def _estimate_tokens(value):
    return math.ceil((len(_serialized(value).encode("utf-8")) + 1) / 4)


def _text(value, label, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a nonempty string"
        raise ContextPacketError(f"{label} must be {qualifier}")
    return value.strip()


def _string_list(value, label):
    if not isinstance(value, list):
        raise ContextPacketError(f"{label} must be a list")
    result = []
    for index, item in enumerate(value):
        result.append(_text(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        raise ContextPacketError(f"{label} contains duplicates")
    return result


def _root(root):
    path = pathlib.Path(root).resolve()
    if not path.is_dir():
        raise ContextPacketError("root must be an existing directory")
    return path


def _manifest(root):
    path = root / "config" / "context-harness.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextPacketError(f"cannot load context harness: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != MANIFEST_FIELDS:
        raise ContextPacketError("context harness fields do not match schema")
    if payload.get("schemaVersion") != 1 or payload.get("packetSchemaVersion") != 1:
        raise ContextPacketError("unsupported context harness schema")
    if payload["artifactPattern"] != "docs/delivery/{delivery}/context/{stage}.json":
        raise ContextPacketError("context harness artifact pattern is invalid")
    if payload["authorityOrder"] != ["system", "user", "project", "runtime", "agent"]:
        raise ContextPacketError("context harness authority order is invalid")
    if payload["hashAlgorithm"] != "sha256" or payload["staleSourcePolicy"] != "fail":
        raise ContextPacketError("context harness integrity policy is invalid")
    if payload["sourceTrust"] != "untrusted-data-not-instructions":
        raise ContextPacketError("context harness source trust is invalid")
    if payload["tokenEstimator"] != "canonical-json-utf8-bytes-divided-by-four-ceiling":
        raise ContextPacketError("context harness token estimator is invalid")
    if payload["trimStrategy"] != "whole-optional-source-lowest-priority-first":
        raise ContextPacketError("context harness trim strategy is invalid")
    limits = [
        payload["minimumMaxTokens"],
        payload["defaultMaxTokens"],
        payload["maximumMaxTokens"],
    ]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in limits):
        raise ContextPacketError("context harness token limits must be integers")
    if not 0 < limits[0] <= limits[1] <= limits[2]:
        raise ContextPacketError("context harness token limits are invalid")
    for field in ("excludedPathParts", "secretPatterns", "systemRules", "mandatorySections"):
        if not isinstance(payload[field], list) or not payload[field]:
            raise ContextPacketError(f"context harness {field} must be a nonempty list")
    required_exclusions = {".git", ".env", "node_modules", "vendor", "storage"}
    if not required_exclusions.issubset(set(payload["excludedPathParts"])):
        raise ContextPacketError("context harness excluded paths are incomplete")
    if payload["secretPatterns"] != [
        "private-key-block",
        "aws-access-key",
        "github-token",
        "long-secret-assignment",
    ]:
        raise ContextPacketError("context harness secret patterns are invalid")
    if payload["mandatorySections"] != [
        "objective",
        "ownedPaths",
        "approvalState",
        "budget",
        "successCriteria",
        "currentState",
        "outputContract",
    ]:
        raise ContextPacketError("context harness mandatory sections are invalid")
    return payload


def _safe_file(root, raw, label):
    value = _text(raw, label)
    pure = pathlib.PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ContextPacketError(f"{label} must be a project-relative path")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ContextPacketError(f"{label} is missing or escapes the project") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise ContextPacketError(f"{label} must be a regular non-symlink file")
    return candidate, pure.as_posix()


def _check_source_path(path, excluded):
    lower_parts = [part.lower() for part in pathlib.PurePosixPath(path).parts]
    excluded_lower = {part.lower() for part in excluded}
    if any(part in excluded_lower or part.startswith(".env.") for part in lower_parts):
        raise ContextPacketError(f"source path is excluded from context packets: {path}")


def _check_no_secret(text, label):
    if any(pattern.search(text) for pattern in _SECRET_PATTERNS):
        raise ContextPacketError(f"secret-shaped content is forbidden in {label}")


def _read_spec(root, raw_path, manifest):
    empty = {
        "schemaVersion": 1,
        "summary": "",
        "projectConstraints": [],
        "completedWork": [],
        "nextAction": "",
        "sources": [],
    }
    if not raw_path:
        return empty, {"path": "", "sha256": ""}
    path, relative = _safe_file(root, raw_path, "context spec")
    _check_source_path(relative, manifest["excludedPathParts"])
    raw = path.read_bytes()
    try:
        decoded = raw.decode("utf-8")
        spec = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContextPacketError(f"context spec is not valid UTF-8 JSON: {exc}") from exc
    _check_no_secret(decoded, "context spec")
    if not isinstance(spec, dict) or set(spec) != SPEC_FIELDS:
        raise ContextPacketError(f"context spec must declare exactly {sorted(SPEC_FIELDS)}")
    if spec["schemaVersion"] != 1:
        raise ContextPacketError("context spec schemaVersion must be 1")
    spec["summary"] = _text(spec["summary"], "summary", allow_empty=True)
    spec["projectConstraints"] = _string_list(
        spec["projectConstraints"], "projectConstraints"
    )
    spec["completedWork"] = _string_list(spec["completedWork"], "completedWork")
    spec["nextAction"] = _text(spec["nextAction"], "nextAction", allow_empty=True)
    if not isinstance(spec["sources"], list):
        raise ContextPacketError("sources must be a list")
    return spec, {"path": relative, "sha256": _hash_bytes(raw)}


def _source_record(root, source, manifest, index):
    label = f"sources[{index}]"
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise ContextPacketError(f"{label} must declare exactly {sorted(SOURCE_FIELDS)}")
    path, relative = _safe_file(root, source["path"], f"{label}.path")
    _check_source_path(relative, manifest["excludedPathParts"])
    purpose = _text(source["purpose"], f"{label}.purpose")
    priority = source["priority"]
    required = source["required"]
    start = source["startLine"]
    end = source["endLine"]
    if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 100:
        raise ContextPacketError(f"{label}.priority must be an integer from 0 to 100")
    if not isinstance(required, bool):
        raise ContextPacketError(f"{label}.required must be boolean")
    if not isinstance(start, int) or isinstance(start, bool) or start < 1:
        raise ContextPacketError(f"{label}.startLine must be a positive integer")
    if not isinstance(end, int) or isinstance(end, bool) or end < start:
        raise ContextPacketError(f"{label}.endLine must be at least startLine")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContextPacketError(f"{label}.path must contain UTF-8 text") from exc
    lines = text.splitlines()
    if end > len(lines):
        raise ContextPacketError(f"{label}.endLine exceeds the file length")
    excerpt = "\n".join(lines[start - 1 : end])
    _check_no_secret(excerpt, f"source {relative}")
    return {
        "path": relative,
        "purpose": purpose,
        "priority": priority,
        "required": required,
        "startLine": start,
        "endLine": end,
        "trust": manifest["sourceTrust"],
        "fullFileSha256": _hash_bytes(raw),
        "excerptSha256": _hash_bytes(excerpt.encode("utf-8")),
        "content": excerpt,
    }


def _stage(delivery, stage_id):
    stage = next((item for item in delivery.stages if item.id == stage_id), None)
    if stage is None:
        raise ContextPacketError(f"stage {stage_id} is missing")
    return stage


def _authoritative_state(delivery, stage):
    dependencies = []
    by_id = {item.id: item for item in delivery.stages}
    for stage_id in stage.depends_on:
        dependency = by_id[stage_id]
        dependencies.append(
            {
                "id": dependency.id,
                "status": dependency.status,
                "did": dependency.did,
                "verified": dependency.verified,
            }
        )
    return {
        "deliveryStatus": delivery.status,
        "stageStatus": stage.status,
        "attempt": stage.attempts + (1 if stage.status == "queued" else 0),
        "lastActivityAt": stage.last_activity_at,
        "dependencies": dependencies,
        "retry": {
            "source": stage.retry_source,
            "reason": stage.retry_reason,
        },
        "recovery": {
            "eventId": stage.recovery_event_id,
            "source": stage.recovery_source,
            "reason": stage.recovery_reason,
        },
        "openFeedbackEventIds": [
            event["event_id"]
            for event in delivery.feedback_events
            if event.get("stage") == stage.id and event.get("status") == "open"
        ],
    }


def _core_packet(delivery, stage, spec, spec_integrity, manifest, max_tokens):
    approval_state = [
        {
            "category": category,
            "approved": any(
                record.get("category") == category for record in stage.approvals
            ),
        }
        for category in stage.approval_categories
    ]
    criteria = [
        {"id": criterion_id, "text": text}
        for criterion_id, text in zip(stage.criterion_ids, stage.success_criteria)
    ]
    state = _authoritative_state(delivery, stage)
    packet = {
        "schemaVersion": manifest["packetSchemaVersion"],
        "kind": "laravel-guild-context-packet",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "delivery": delivery.name,
        "stage": stage.id,
        "audience": {"agent": stage.agent, "role": stage.role},
        "authority": {
            "system": {"rules": list(manifest["systemRules"])},
            "user": {
                "objective": delivery.done_when,
                "approvalState": approval_state,
                "criterionWaivers": list(stage.criterion_waivers),
            },
            "project": {"constraints": spec["projectConstraints"]},
            "runtime": {
                "ownedPaths": list(stage.owned_paths),
                "budget": dict(stage.budget),
                "successCriteria": criteria,
                "benchmarkCriteria": list(stage.benchmark_criteria),
                "feedbackChecks": list(stage.feedback_checks),
            },
            "agent": {
                "summary": spec["summary"],
                "completedWork": spec["completedWork"],
                "nextAction": spec["nextAction"],
                "mayOverrideHigherAuthority": False,
            },
        },
        "sources": [],
        "currentState": state,
        "outputContract": {
            "artifact": f"docs/delivery/{delivery.name}/stages/{stage.id}.md",
            "labels": ["STATUS", "DID", "VERIFIED", "NOT-CHECKED", "FLAGS", "NEXT"],
        },
        "integrity": {
            "algorithm": manifest["hashAlgorithm"],
            "manifest": "config/context-harness.json",
            "spec": spec_integrity,
            "kernelStateSha256": _hash_json(state),
        },
        "budget": {
            "maxTokens": max_tokens,
            "estimatedTokens": 0,
            "estimator": manifest["tokenEstimator"],
            "trimStrategy": manifest["trimStrategy"],
            "omittedSources": [],
        },
        "packetHash": "",
    }
    return packet


def _seal(packet):
    packet["budget"]["estimatedTokens"] = 0
    packet["packetHash"] = ""
    # Token metadata participates in the estimate, so converge before sealing.
    for _ in range(8):
        estimate = _estimate_tokens(packet)
        if packet["budget"]["estimatedTokens"] == estimate:
            break
        packet["budget"]["estimatedTokens"] = estimate
    unsigned = dict(packet)
    unsigned["packetHash"] = ""
    packet["packetHash"] = _hash_json(unsigned)
    final_estimate = _estimate_tokens(packet)
    if final_estimate != packet["budget"]["estimatedTokens"]:
        packet["budget"]["estimatedTokens"] = final_estimate
        unsigned = dict(packet)
        unsigned["packetHash"] = ""
        packet["packetHash"] = _hash_json(unsigned)
    return packet


def _artifact_path(root, delivery, stage):
    try:
        delivery = kernel._safe_identifier(delivery, "delivery name")
        stage = kernel._safe_identifier(stage, "stage id")
    except kernel.PlanError as exc:
        raise ContextPacketError(str(exc)) from exc
    return root / "docs" / "delivery" / delivery / "context" / f"{stage}.json"


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = pathlib.Path(handle.name)
    temporary.replace(path)


def build(root, name, stage_id, *, spec_path="", max_tokens=None):
    root = _root(root)
    manifest = _manifest(root)
    maximum = manifest["maximumMaxTokens"]
    minimum = manifest["minimumMaxTokens"]
    limit = manifest["defaultMaxTokens"] if max_tokens is None else max_tokens
    if not isinstance(limit, int) or isinstance(limit, bool) or not minimum <= limit <= maximum:
        raise ContextPacketError(
            f"max tokens must be an integer from {minimum} to {maximum}"
        )
    try:
        delivery = kernel.load(root, name)
    except (OSError, json.JSONDecodeError, kernel.PlanError) as exc:
        raise ContextPacketError(f"cannot load delivery: {exc}") from exc
    stage = _stage(delivery, stage_id)
    if stage.status != "running":
        raise ContextPacketError(
            f"stage {stage_id} must be claimed and running before context build"
        )
    spec, spec_integrity = _read_spec(root, spec_path, manifest)
    records = [
        _source_record(root, item, manifest, index)
        for index, item in enumerate(spec["sources"])
    ]
    selections = [
        (record["path"], record["startLine"], record["endLine"])
        for record in records
    ]
    if len(selections) != len(set(selections)):
        raise ContextPacketError("source path and line-range selections must be unique")
    records.sort(key=lambda item: (not item["required"], -item["priority"], item["path"]))
    packet = _core_packet(delivery, stage, spec, spec_integrity, manifest, limit)
    for record in records:
        candidate = json.loads(json.dumps(packet))
        candidate["sources"].append(record)
        _seal(candidate)
        if candidate["budget"]["estimatedTokens"] <= limit:
            packet = candidate
            continue
        if record["required"]:
            raise ContextPacketError(
                f"required source {record['path']} exceeds the context token budget"
            )
        packet["budget"]["omittedSources"].append(
            {
                "path": record["path"],
                "purpose": record["purpose"],
                "priority": record["priority"],
                "reason": "token-budget",
            }
        )
    _seal(packet)
    if packet["budget"]["estimatedTokens"] > limit:
        raise ContextPacketError("mandatory context exceeds the context token budget")
    _check_no_secret(_canonical(packet), "context packet")
    path = _artifact_path(root, delivery.name, stage.id)
    _write_atomic(path, _serialized(packet) + "\n")
    return {
        "status": "built",
        "path": path.relative_to(root).as_posix(),
        "packetHash": packet["packetHash"],
        "estimatedTokens": packet["budget"]["estimatedTokens"],
        "omittedSources": len(packet["budget"]["omittedSources"]),
    }


def _load_packet(root, name, stage_id):
    path = _artifact_path(root, name, stage_id)
    try:
        raw = path.read_text(encoding="utf-8")
        packet = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContextPacketError(f"cannot load context packet: {exc}") from exc
    if not isinstance(packet, dict) or set(packet) != PACKET_FIELDS:
        raise ContextPacketError("context packet fields do not match schema")
    return path, packet


def _validate_packet_shape(packet, manifest):
    objects = {
        "audience": {"agent", "role"},
        "integrity": {"algorithm", "manifest", "spec", "kernelStateSha256"},
        "outputContract": {"artifact", "labels"},
        "budget": {
            "maxTokens",
            "estimatedTokens",
            "estimator",
            "trimStrategy",
            "omittedSources",
        },
    }
    for field, expected in objects.items():
        value = packet.get(field)
        if not isinstance(value, dict) or set(value) != expected:
            raise ContextPacketError(f"context packet {field} fields do not match schema")
    authority = packet.get("authority")
    if not isinstance(authority, dict) or list(authority) != manifest["authorityOrder"]:
        raise ContextPacketError("context packet authority order is invalid")
    if any(not isinstance(authority[name], dict) for name in manifest["authorityOrder"]):
        raise ContextPacketError("context packet authority sections must be objects")
    if not isinstance(packet.get("currentState"), dict):
        raise ContextPacketError("context packet currentState must be an object")
    sources = packet.get("sources")
    if not isinstance(sources, list):
        raise ContextPacketError("context packet sources must be a list")
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != PACKET_SOURCE_FIELDS:
            raise ContextPacketError(f"packet source {index} fields do not match schema")
        if (
            not isinstance(source["startLine"], int)
            or isinstance(source["startLine"], bool)
            or not isinstance(source["endLine"], int)
            or isinstance(source["endLine"], bool)
            or source["startLine"] < 1
            or source["endLine"] < source["startLine"]
        ):
            raise ContextPacketError(f"packet source {index} line range is invalid")
        if not isinstance(source["content"], str):
            raise ContextPacketError(f"packet source {index} content is invalid")
    spec = packet["integrity"].get("spec")
    if not isinstance(spec, dict) or set(spec) != {"path", "sha256"}:
        raise ContextPacketError("context packet spec integrity is invalid")
    budget = packet["budget"]
    for field in ("maxTokens", "estimatedTokens"):
        if not isinstance(budget[field], int) or isinstance(budget[field], bool):
            raise ContextPacketError(f"context packet {field} is invalid")
    if not manifest["minimumMaxTokens"] <= budget["maxTokens"] <= manifest["maximumMaxTokens"]:
        raise ContextPacketError("context packet maxTokens is outside policy")
    if not re.fullmatch(r"[0-9a-f]{64}", str(packet.get("packetHash", ""))):
        raise ContextPacketError("context packet hash is invalid")


def verify(root, name, stage_id):
    root = _root(root)
    manifest = _manifest(root)
    path, packet = _load_packet(root, name, stage_id)
    _validate_packet_shape(packet, manifest)
    if packet["schemaVersion"] != manifest["packetSchemaVersion"]:
        raise ContextPacketError("context packet schema is unsupported")
    if packet["kind"] != "laravel-guild-context-packet":
        raise ContextPacketError("context packet kind is invalid")
    if packet["delivery"] != name or packet["stage"] != stage_id:
        raise ContextPacketError("context packet target does not match its path")
    unsigned = dict(packet)
    claimed_hash = unsigned.pop("packetHash", None)
    unsigned["packetHash"] = ""
    if claimed_hash != _hash_json(unsigned):
        raise ContextPacketError("context packet hash does not match")
    budget = packet.get("budget")
    if not isinstance(budget, dict) or budget.get("estimatedTokens") != _estimate_tokens(packet):
        raise ContextPacketError("context packet token estimate does not match")
    if budget["estimatedTokens"] > budget["maxTokens"]:
        raise ContextPacketError("context packet exceeds its token budget")
    _check_no_secret(_canonical(packet), "context packet")
    try:
        delivery = kernel.load(root, name)
    except (OSError, json.JSONDecodeError, kernel.PlanError) as exc:
        raise ContextPacketError(f"cannot load delivery: {exc}") from exc
    stage = _stage(delivery, stage_id)
    state = _authoritative_state(delivery, stage)
    if packet["integrity"].get("kernelStateSha256") != _hash_json(state):
        raise ContextPacketError("context packet is stale: kernel state changed")
    spec = packet["integrity"].get("spec", {})
    if spec.get("path"):
        spec_path, _ = _safe_file(root, spec["path"], "context spec")
        if _hash_bytes(spec_path.read_bytes()) != spec.get("sha256"):
            raise ContextPacketError("context packet is stale: context spec changed")
    for index, source in enumerate(packet["sources"]):
        source_path, _ = _safe_file(root, source.get("path"), f"packet source {index}")
        raw = source_path.read_bytes()
        if _hash_bytes(raw) != source.get("fullFileSha256"):
            raise ContextPacketError(f"context packet is stale: {source['path']} changed")
        try:
            text = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ContextPacketError(
                f"context packet source is no longer UTF-8: {source['path']}"
            ) from exc
        excerpt = "\n".join(text[source["startLine"] - 1 : source["endLine"]])
        if _hash_bytes(excerpt.encode("utf-8")) != source.get("excerptSha256"):
            raise ContextPacketError(f"context packet excerpt is invalid: {source['path']}")
        if source.get("content") != excerpt or source.get("trust") != manifest["sourceTrust"]:
            raise ContextPacketError(f"context packet source content is invalid: {source['path']}")
    return {
        "status": "valid",
        "path": path.relative_to(root).as_posix(),
        "packetHash": packet["packetHash"],
        "estimatedTokens": packet["budget"]["estimatedTokens"],
    }


def show(root, name, stage_id):
    verify(root, name, stage_id)
    _, packet = _load_packet(_root(root), name, stage_id)
    return json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
