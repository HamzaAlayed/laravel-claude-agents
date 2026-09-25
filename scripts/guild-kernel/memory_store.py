"""Approval-gated durable memory and bounded retrieval. Stdlib only."""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import tempfile
from datetime import datetime, timezone


class MemoryError(ValueError):
    """The memory request or durable store is invalid."""


MANIFEST_FIELDS = {
    "schemaVersion", "storeSchemaVersion", "storePath", "defaultMaxTokens",
    "minimumMaxTokens", "maximumMaxTokens", "tokenEstimator", "trimStrategy",
    "hashAlgorithm", "staleEvidencePolicy", "conflictPolicy", "deletionPolicy",
    "authorityOrder", "memoryTypes", "scopes", "excludedPathParts",
    "secretPatterns",
}
STORE_FIELDS = {"schemaVersion", "records", "deletionRequests", "events", "storeHash"}
RECORD_FIELDS = {
    "id", "type", "scope", "agent", "topic", "statement", "source",
    "evidence", "confidence", "status", "createdAt", "approvedAt",
    "expiresAt", "supersededBy", "contentHash",
}
EVIDENCE_FIELDS = {"path", "sha256"}
REQUEST_FIELDS = {"id", "recordId", "reason", "status", "requestedAt", "approvedAt"}
EVENT_FIELDS = {"seq", "type", "recordId", "requestId", "at", "previousHash", "eventHash"}
ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
AGENT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"][^'\"\r\n]{20,}['\"]"),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value):
    if not isinstance(value, bytes):
        value = _canonical(value).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _tokens(value):
    return math.ceil((len(_canonical(value).encode("utf-8")) + 1) / 4)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value, label, *, max_length=4000):
    if not isinstance(value, str) or not value.strip():
        raise MemoryError(f"{label} must be a nonempty string")
    value = value.strip()
    if len(value) > max_length:
        raise MemoryError(f"{label} exceeds {max_length} characters")
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise MemoryError(f"secret-shaped content is forbidden in {label}")
    return value


def _root(root):
    result = pathlib.Path(root).resolve()
    if not result.is_dir():
        raise MemoryError("root must be an existing directory")
    return result


def _manifest(root):
    path = root / "config" / "memory-harness.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryError(f"cannot load memory harness: {exc}") from exc
    if not isinstance(data, dict) or set(data) != MANIFEST_FIELDS:
        raise MemoryError("memory harness fields do not match schema")
    expected = {
        "schemaVersion": 1,
        "storeSchemaVersion": 1,
        "storePath": "docs/team/memory.json",
        "tokenEstimator": "canonical-json-utf8-bytes-divided-by-four-ceiling",
        "trimStrategy": "whole-optional-memory-lowest-rank-first",
        "hashAlgorithm": "sha256",
        "staleEvidencePolicy": "exclude",
        "conflictPolicy": "explicit-supersession",
        "deletionPolicy": "two-step-tombstone",
        "authorityOrder": ["user", "project", "runtime", "agent"],
        "memoryTypes": ["authoritative-decision", "project-fact", "procedure", "episode"],
        "scopes": ["project", "agent"],
        "secretPatterns": ["private-key-block", "aws-access-key", "github-token", "long-secret-assignment"],
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise MemoryError(f"memory harness {key} is invalid")
    limits = [data.get("minimumMaxTokens"), data.get("defaultMaxTokens"), data.get("maximumMaxTokens")]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in limits):
        raise MemoryError("memory harness token limits must be integers")
    if not 0 < limits[0] <= limits[1] <= limits[2]:
        raise MemoryError("memory harness token limits are invalid")
    excluded = data.get("excludedPathParts")
    if not isinstance(excluded, list) or not {".git", ".env", "node_modules", "vendor", "storage"}.issubset(excluded):
        raise MemoryError("memory harness excluded paths are incomplete")
    return data


def _store_path(root, manifest):
    return root.joinpath(*pathlib.PurePosixPath(manifest["storePath"]).parts)


def _store_hash(store):
    unsigned = dict(store)
    unsigned["storeHash"] = ""
    return _hash(unsigned)


def _empty_store():
    store = {
        "schemaVersion": 1,
        "records": [],
        "deletionRequests": [],
        "events": [],
        "storeHash": "",
    }
    store["storeHash"] = _store_hash(store)
    return store


def _record_hash(record):
    unsigned = dict(record)
    unsigned["contentHash"] = ""
    return _hash(unsigned)


def _event_hash(event):
    unsigned = dict(event)
    unsigned["eventHash"] = ""
    return _hash(unsigned)


def _safe_evidence(root, raw, manifest):
    raw = _text(raw, "evidence path", max_length=500)
    pure = pathlib.PurePosixPath(raw)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise MemoryError("evidence path must be project-relative")
    excluded = {item.lower() for item in manifest["excludedPathParts"]}
    if any(part.lower() in excluded or part.lower().startswith(".env.") for part in pure.parts):
        raise MemoryError(f"evidence path is excluded: {raw}")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise MemoryError(f"evidence is missing or escapes the project: {raw}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise MemoryError("evidence must be a regular non-symlink file")
    return {"path": pure.as_posix(), "sha256": _hash(candidate.read_bytes())}


def _parse_time(value, label, *, allow_empty=True):
    if value == "" and allow_empty:
        return None
    value = _text(value, label, max_length=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MemoryError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise MemoryError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_record(record, manifest, label):
    if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
        raise MemoryError(f"{label} fields do not match schema")
    if not ID_RE.fullmatch(record.get("id", "")):
        raise MemoryError(f"{label}.id is invalid")
    if record.get("type") not in manifest["memoryTypes"]:
        raise MemoryError(f"{label}.type is invalid")
    if record.get("scope") not in manifest["scopes"]:
        raise MemoryError(f"{label}.scope is invalid")
    agent = record.get("agent")
    if record["scope"] == "agent" and (not isinstance(agent, str) or not AGENT_RE.fullmatch(agent)):
        raise MemoryError(f"{label}.agent is required for agent scope")
    if record["scope"] == "project" and agent != "":
        raise MemoryError(f"{label}.agent must be empty for project scope")
    if not TOPIC_RE.fullmatch(record.get("topic", "")):
        raise MemoryError(f"{label}.topic is invalid")
    if record.get("source") not in manifest["authorityOrder"]:
        raise MemoryError(f"{label}.source is invalid")
    if record.get("status") not in {"candidate", "approved", "superseded", "deleted"}:
        raise MemoryError(f"{label}.status is invalid")
    statement = record.get("statement")
    if record["status"] == "deleted":
        if statement != "[deleted]" or record.get("evidence") != []:
            raise MemoryError(f"{label} deleted record must be a tombstone")
    else:
        _text(statement, f"{label}.statement")
    confidence = record.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise MemoryError(f"{label}.confidence must be between 0 and 1")
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        raise MemoryError(f"{label}.evidence must be a list")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise MemoryError(f"{label}.evidence[{index}] is invalid")
        raw_path = item.get("path")
        pure = pathlib.PurePosixPath(raw_path) if isinstance(raw_path, str) else None
        excluded = {part.lower() for part in manifest["excludedPathParts"]}
        unsafe_path = (
            pure is None or pure.is_absolute() or not pure.parts or ".." in pure.parts
            or any(part.lower() in excluded or part.lower().startswith(".env.") for part in pure.parts)
        )
        if unsafe_path or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise MemoryError(f"{label}.evidence[{index}] is invalid")
    _parse_time(record.get("createdAt"), f"{label}.createdAt", allow_empty=False)
    if record["status"] in {"approved", "superseded"} and not record.get("approvedAt"):
        raise MemoryError(f"{label}.approvedAt is required")
    if record.get("approvedAt"):
        _parse_time(record["approvedAt"], f"{label}.approvedAt", allow_empty=False)
    if record.get("expiresAt"):
        _parse_time(record["expiresAt"], f"{label}.expiresAt", allow_empty=False)
    if record["status"] == "superseded" and not record.get("supersededBy"):
        raise MemoryError(f"{label}.supersededBy is required")
    if not re.fullmatch(r"[0-9a-f]{64}", record.get("contentHash", "")) or record["contentHash"] != _record_hash(record):
        raise MemoryError(f"{label}.contentHash is invalid")


def _validate_store(store, manifest):
    if not isinstance(store, dict) or set(store) != STORE_FIELDS or store.get("schemaVersion") != 1:
        raise MemoryError("memory store fields do not match schema")
    for field in ("records", "deletionRequests", "events"):
        if not isinstance(store.get(field), list):
            raise MemoryError(f"memory store {field} must be a list")
    ids = set()
    for index, record in enumerate(store["records"]):
        _validate_record(record, manifest, f"records[{index}]")
        if record["id"] in ids:
            raise MemoryError("memory store contains duplicate record ids")
        ids.add(record["id"])
    request_ids = set()
    for index, request in enumerate(store["deletionRequests"]):
        label = f"deletionRequests[{index}]"
        if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
            raise MemoryError(f"{label} fields do not match schema")
        if not ID_RE.fullmatch(request.get("id", "")) or request["id"] in request_ids:
            raise MemoryError(f"{label}.id is invalid or duplicated")
        request_ids.add(request["id"])
        if request.get("recordId") not in ids or request.get("status") not in {"pending", "approved"}:
            raise MemoryError(f"{label} target or status is invalid")
        _text(request.get("reason"), f"{label}.reason", max_length=1000)
        _parse_time(request.get("requestedAt"), f"{label}.requestedAt", allow_empty=False)
        if request["status"] == "approved" and not request.get("approvedAt"):
            raise MemoryError(f"{label}.approvedAt is required")
        if request.get("approvedAt"):
            _parse_time(request["approvedAt"], f"{label}.approvedAt", allow_empty=False)
    previous = ""
    for index, event in enumerate(store["events"]):
        label = f"events[{index}]"
        if not isinstance(event, dict) or set(event) != EVENT_FIELDS or event.get("seq") != index + 1:
            raise MemoryError(f"{label} fields or sequence are invalid")
        if event.get("previousHash") != previous or event.get("eventHash") != _event_hash(event):
            raise MemoryError(f"{label} hash chain is invalid")
        _parse_time(event.get("at"), f"{label}.at", allow_empty=False)
        previous = event["eventHash"]
    if not re.fullmatch(r"[0-9a-f]{64}", store.get("storeHash", "")) or store["storeHash"] != _store_hash(store):
        raise MemoryError("memory store hash is invalid")
    return store


def _load(root):
    root = _root(root)
    manifest = _manifest(root)
    path = _store_path(root, manifest)
    if not path.exists():
        _write(path, _empty_store())
    try:
        store = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryError(f"cannot load memory store: {exc}") from exc
    return root, manifest, path, _validate_store(store, manifest)


def _write(path, store):
    store["storeHash"] = _store_hash(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=".memory-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(store, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw, path)
    except Exception:
        pathlib.Path(raw).unlink(missing_ok=True)
        raise


def _append_event(store, kind, *, record_id="", request_id=""):
    event = {
        "seq": len(store["events"]) + 1,
        "type": kind,
        "recordId": record_id,
        "requestId": request_id,
        "at": _now(),
        "previousHash": store["events"][-1]["eventHash"] if store["events"] else "",
        "eventHash": "",
    }
    event["eventHash"] = _event_hash(event)
    store["events"].append(event)


def _record(store, record_id):
    found = next((record for record in store["records"] if record["id"] == record_id), None)
    if found is None:
        raise MemoryError(f"memory {record_id} is missing")
    return found


def propose(root, *, record_id, memory_type, scope, topic, statement, source, agent="", evidence=(), confidence=1.0, expires_at=""):
    root, manifest, path, store = _load(root)
    if not ID_RE.fullmatch(record_id or ""):
        raise MemoryError("memory id is invalid")
    if any(item["id"] == record_id for item in store["records"]):
        raise MemoryError(f"memory {record_id} already exists")
    if memory_type not in manifest["memoryTypes"] or scope not in manifest["scopes"]:
        raise MemoryError("memory type or scope is invalid")
    if not TOPIC_RE.fullmatch(topic or ""):
        raise MemoryError("topic must be lower-kebab-case")
    if source not in manifest["authorityOrder"]:
        raise MemoryError("memory source is invalid")
    if scope == "agent":
        if not AGENT_RE.fullmatch(agent or ""):
            raise MemoryError("agent scope requires a lower-kebab agent")
    elif agent:
        raise MemoryError("project scope cannot name an agent")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise MemoryError("confidence must be between 0 and 1")
    if expires_at:
        _parse_time(expires_at, "expires-at", allow_empty=False)
    evidence_records = [_safe_evidence(root, item, manifest) for item in evidence]
    if source != "user" and not evidence_records:
        raise MemoryError("non-user memory requires repository evidence")
    record = {
        "id": record_id,
        "type": memory_type,
        "scope": scope,
        "agent": agent,
        "topic": topic,
        "statement": _text(statement, "statement"),
        "source": source,
        "evidence": evidence_records,
        "confidence": confidence,
        "status": "candidate",
        "createdAt": _now(),
        "approvedAt": "",
        "expiresAt": expires_at,
        "supersededBy": "",
        "contentHash": "",
    }
    record["contentHash"] = _record_hash(record)
    store["records"].append(record)
    _append_event(store, "proposed", record_id=record_id)
    _write(path, store)
    return record


def _conflicts(store, record):
    return [item["id"] for item in store["records"] if item["status"] == "approved" and item["topic"] == record["topic"] and item["scope"] == record["scope"] and item["agent"] == record["agent"] and item["statement"] != record["statement"]]


def approve(root, record_id):
    _, _, path, store = _load(root)
    record = _record(store, record_id)
    if record["status"] != "candidate":
        raise MemoryError("only a candidate memory can be approved")
    conflicts = _conflicts(store, record)
    if conflicts:
        raise MemoryError("memory conflicts with approved record(s); use supersede: " + ", ".join(conflicts))
    record["status"] = "approved"
    record["approvedAt"] = _now()
    record["contentHash"] = _record_hash(record)
    _append_event(store, "approved", record_id=record_id)
    _write(path, store)
    return record


def supersede(root, old_id, replacement_id):
    _, _, path, store = _load(root)
    old = _record(store, old_id)
    replacement = _record(store, replacement_id)
    if old["status"] != "approved" or replacement["status"] != "candidate":
        raise MemoryError("supersede requires an approved old memory and candidate replacement")
    if (old["topic"], old["scope"], old["agent"]) != (replacement["topic"], replacement["scope"], replacement["agent"]):
        raise MemoryError("replacement must use the same topic and scope")
    other = [item for item in _conflicts(store, replacement) if item != old_id]
    if other:
        raise MemoryError("replacement conflicts with other approved record(s): " + ", ".join(other))
    at = _now()
    old["status"] = "superseded"
    old["supersededBy"] = replacement_id
    old["contentHash"] = _record_hash(old)
    replacement["status"] = "approved"
    replacement["approvedAt"] = at
    replacement["contentHash"] = _record_hash(replacement)
    _append_event(store, "superseded", record_id=old_id)
    _append_event(store, "approved", record_id=replacement_id)
    _write(path, store)
    return {"superseded": old_id, "replacement": replacement_id}


def delete_request(root, record_id, request_id, reason):
    _, _, path, store = _load(root)
    record = _record(store, record_id)
    if record["status"] == "deleted":
        raise MemoryError("memory is already deleted")
    if not ID_RE.fullmatch(request_id or "") or any(item["id"] == request_id for item in store["deletionRequests"]):
        raise MemoryError("deletion request id is invalid or duplicated")
    request = {"id": request_id, "recordId": record_id, "reason": _text(reason, "reason", max_length=1000), "status": "pending", "requestedAt": _now(), "approvedAt": ""}
    store["deletionRequests"].append(request)
    _append_event(store, "delete-requested", record_id=record_id, request_id=request_id)
    _write(path, store)
    return request


def delete_approve(root, request_id):
    _, _, path, store = _load(root)
    request = next((item for item in store["deletionRequests"] if item["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise MemoryError("pending deletion request is missing")
    record = _record(store, request["recordId"])
    if record["status"] == "deleted":
        raise MemoryError("memory is already deleted")
    at = _now()
    request["status"] = "approved"
    request["approvedAt"] = at
    record["status"] = "deleted"
    record["statement"] = "[deleted]"
    record["evidence"] = []
    record["supersededBy"] = ""
    record["contentHash"] = _record_hash(record)
    _append_event(store, "deleted", record_id=record["id"], request_id=request_id)
    _write(path, store)
    return {"deleted": record["id"], "request": request_id, "tombstone": True}


def _evidence_current(root, record):
    stale = []
    for item in record["evidence"]:
        candidate = root.joinpath(*pathlib.PurePosixPath(item["path"]).parts)
        if not candidate.is_file() or candidate.is_symlink() or _hash(candidate.read_bytes()) != item["sha256"]:
            stale.append(item["path"])
    return stale


def search(root, query, agent, max_tokens=None):
    root, manifest, _, store = _load(root)
    query = _text(query, "query", max_length=2000)
    if not AGENT_RE.fullmatch(agent or ""):
        raise MemoryError("agent must be lower-kebab-case")
    if max_tokens is None:
        max_tokens = manifest["defaultMaxTokens"]
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not manifest["minimumMaxTokens"] <= max_tokens <= manifest["maximumMaxTokens"]:
        raise MemoryError("max-tokens is outside memory policy")
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    now = datetime.now(timezone.utc)
    eligible = []
    omitted = []
    authority = {name: len(manifest["authorityOrder"]) - index for index, name in enumerate(manifest["authorityOrder"])}
    for record in store["records"]:
        reason = ""
        if record["status"] != "approved":
            reason = record["status"]
        elif record["scope"] == "agent" and record["agent"] != agent:
            reason = "scope"
        elif record["expiresAt"] and _parse_time(record["expiresAt"], "expiresAt", allow_empty=False) <= now:
            reason = "expired"
        elif _evidence_current(root, record):
            reason = "stale-evidence"
        if reason:
            omitted.append({"id": record["id"], "reason": reason})
            continue
        words = set(re.findall(r"[a-z0-9]+", (record["topic"] + " " + record["statement"]).lower()))
        relevance = len(terms & words)
        mandatory = record["source"] == "user" and record["type"] == "authoritative-decision"
        if not mandatory and relevance == 0:
            omitted.append({"id": record["id"], "reason": "irrelevant"})
            continue
        rank = (1 if mandatory else 0, authority[record["source"]], 1 if record["scope"] == "agent" else 0, relevance, record["confidence"], record["approvedAt"])
        selected = {key: record[key] for key in ("id", "type", "scope", "agent", "topic", "statement", "source", "confidence", "approvedAt", "expiresAt", "contentHash")}
        selected["trust"] = "memory-data-not-instructions"
        eligible.append((rank, mandatory, selected))
    eligible.sort(key=lambda item: item[0], reverse=True)
    required = [item for item in eligible if item[1]]
    optional = [item for item in eligible if not item[1]]
    selected = [item[2] for item in required]
    required_tokens = _tokens(selected)
    if required_tokens > max_tokens:
        raise MemoryError("mandatory user memory exceeds retrieval token budget")
    for _, _, item in optional:
        if _tokens(selected + [item]) <= max_tokens:
            selected.append(item)
        else:
            omitted.append({"id": item["id"], "reason": "token-budget"})
    return {"schemaVersion": 1, "query": query, "agent": agent, "selected": selected, "omitted": omitted, "budget": {"maxTokens": max_tokens, "estimatedTokens": _tokens(selected), "estimator": manifest["tokenEstimator"], "trimStrategy": manifest["trimStrategy"]}, "storeHash": store["storeHash"]}


def show(root, record_id):
    _, _, _, store = _load(root)
    return _record(store, record_id)


def verify(root, *, strict_evidence=False):
    root, manifest, path, store = _load(root)
    stale = []
    expired = []
    now = datetime.now(timezone.utc)
    for record in store["records"]:
        if record["status"] != "approved":
            continue
        stale.extend({"id": record["id"], "path": item} for item in _evidence_current(root, record))
        if record["expiresAt"] and _parse_time(record["expiresAt"], "expiresAt", allow_empty=False) <= now:
            expired.append(record["id"])
    conflicts = []
    approved = [item for item in store["records"] if item["status"] == "approved"]
    for index, left in enumerate(approved):
        for right in approved[index + 1:]:
            if (left["topic"], left["scope"], left["agent"]) == (right["topic"], right["scope"], right["agent"]) and left["statement"] != right["statement"]:
                conflicts.append([left["id"], right["id"]])
    if conflicts:
        raise MemoryError("approved memory conflicts exist")
    if strict_evidence and stale:
        raise MemoryError("approved memory has stale evidence")
    return {"status": "valid", "path": path.relative_to(root).as_posix(), "records": len(store["records"]), "approved": len(approved), "staleEvidence": stale, "expired": expired, "storeHash": store["storeHash"]}


def store_hash(root):
    return _load(root)[3]["storeHash"]
