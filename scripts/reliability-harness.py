#!/usr/bin/env python3
"""Evaluate agent reliability evidence and issue source-bound health receipts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import sys
import tempfile
from typing import Any


DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY_PATH = pathlib.PurePosixPath("config/reliability-harness.json")
SCENARIO_PATH = pathlib.PurePosixPath("config/reliability-scenarios.json")
ATTEMPT_KEYS = {
    "id", "operationId", "attempt", "outcome", "durationSeconds", "costUsd",
    "humanIntervention", "safetyViolations", "idempotencyKey", "sideEffect",
}
SCENARIO_KEYS = {
    "id", "name", "fault", "attempts", "expectedFinalDecision",
    "expectedCircuitState", "expectedAppliedSideEffects",
}
SCENARIO_ATTEMPT_KEYS = {"outcome", "sideEffect", "idempotencyKey"}
SIDE_EFFECTS = {"none", "applied", "deduplicated"}


class ReliabilityError(ValueError):
    """Reliability policy, evidence, or receipt failed closed."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical(value))


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReliabilityError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReliabilityError(f"{label} must be a JSON object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReliabilityError(f"{label} must be nonempty text")
    return value.strip()


def number(value: Any, label: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise ReliabilityError(f"{label} must be a number >= {minimum}")
    return float(value)


def string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise ReliabilityError(f"{label} must be a nonempty string list")
    if len(value) != len(set(value)):
        raise ReliabilityError(f"{label} contains duplicates")
    return value


def repo_file(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ReliabilityError(f"{label} must stay inside the repository")
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise ReliabilityError(f"{label} is missing or escapes the repository") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ReliabilityError(f"{label} must be a regular non-symlink file")
    if not resolved.is_file():
        raise ReliabilityError(f"{label} must be a regular non-symlink file")
    return resolved


def relative_file(root: pathlib.Path, path: pathlib.Path, label: str) -> tuple[str, pathlib.Path]:
    candidate = path if path.is_absolute() else root / path
    try:
        raw = candidate.absolute().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise ReliabilityError(f"{label} must stay inside the repository") from exc
    return raw, repo_file(root, raw, label)


def _validate_threshold(rule: Any, key: str, field: str) -> None:
    if not isinstance(rule, dict) or set(rule) != {field}:
        raise ReliabilityError(f"{key} must define exactly {field}")
    number(rule[field], f"{key}.{field}")


def validate(root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_json(root / POLICY_PATH, str(POLICY_PATH))
    scenarios = load_json(root / SCENARIO_PATH, str(SCENARIO_PATH))
    if policy.get("schemaVersion") != 1 or policy.get("receiptSchemaVersion") != 1:
        raise ReliabilityError("reliability policy schema versions must be 1")
    policy_id = text(policy.get("policyId"), "policyId")
    text(policy.get("scope"), "scope")
    outcomes = set(string_list(policy.get("outcomes"), "outcomes"))
    required_outcomes = {
        "success", "tool-unavailable", "timeout", "rate-limited", "partial-outage",
        "corrupt-state", "application-failure", "safety-violation",
    }
    if outcomes != required_outcomes:
        raise ReliabilityError("outcomes inventory is incomplete")

    retry = policy.get("retryPolicy")
    if not isinstance(retry, dict) or set(retry) != {
        "retryable", "stopImmediately", "maxAttempts", "requiresIdempotencyKeyAfterSideEffect"
    }:
        raise ReliabilityError("retryPolicy fields are invalid")
    retryable = set(string_list(retry["retryable"], "retryPolicy.retryable"))
    stopped = set(string_list(retry["stopImmediately"], "retryPolicy.stopImmediately"))
    if retryable & stopped or retryable | stopped | {"success"} != outcomes:
        raise ReliabilityError("every non-success outcome must have exactly one retry policy")
    if not isinstance(retry["maxAttempts"], int) or isinstance(retry["maxAttempts"], bool) or retry["maxAttempts"] < 1:
        raise ReliabilityError("retryPolicy.maxAttempts must be a positive integer")
    if retry["requiresIdempotencyKeyAfterSideEffect"] is not True:
        raise ReliabilityError("side-effect retries must require idempotency")

    slo = policy.get("serviceLevelObjectives")
    if not isinstance(slo, dict) or set(slo) != {
        "minimumOperations", "completionRate", "p95DurationSeconds", "p95CostUsd",
        "humanInterventionRate", "recoveryRate", "safetyViolationRate", "duplicateSideEffectRate",
    }:
        raise ReliabilityError("serviceLevelObjectives inventory is invalid")
    if not isinstance(slo["minimumOperations"], int) or isinstance(slo["minimumOperations"], bool) or slo["minimumOperations"] < 1:
        raise ReliabilityError("minimumOperations must be a positive integer")
    for key in ("completionRate", "recoveryRate"):
        _validate_threshold(slo[key], key, "minimum")
        if slo[key]["minimum"] > 1:
            raise ReliabilityError(f"{key}.minimum must be <= 1")
    for key in ("p95DurationSeconds", "p95CostUsd", "humanInterventionRate", "safetyViolationRate", "duplicateSideEffectRate"):
        _validate_threshold(slo[key], key, "maximum")
    for key in ("humanInterventionRate", "safetyViolationRate", "duplicateSideEffectRate"):
        if slo[key]["maximum"] > 1:
            raise ReliabilityError(f"{key}.maximum must be <= 1")

    breaker = policy.get("circuitBreaker")
    if breaker != {
        "consecutiveRetryableFailures": 3,
        "tripOnSafetyViolation": True,
        "tripOnDuplicateSideEffect": True,
        "afterOpen": "deny-new-attempts-until-operator-reset",
    }:
        raise ReliabilityError("circuitBreaker must preserve the fail-closed contract")

    canary = policy.get("canaryPolicy")
    if not isinstance(canary, dict) or canary.get("decisions") != ["promote", "hold", "rollback"]:
        raise ReliabilityError("canaryPolicy must expose promote, hold, and rollback in order")
    expected_canary = {
        "baselineMustMeetSlo": True,
        "candidateMustMeetSlo": True,
        "openCircuitDecision": "rollback",
        "insufficientEvidenceDecision": "hold",
        "materialRegressionDecision": "rollback",
    }
    for key, expected in expected_canary.items():
        if canary.get(key) != expected:
            raise ReliabilityError(f"canaryPolicy.{key} must remain {expected!r}")
    thresholds = canary.get("regressionThresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != {
        "completionRate", "p95DurationSeconds", "p95CostUsd", "humanInterventionRate", "recoveryRate"
    }:
        raise ReliabilityError("canary regression thresholds are incomplete")
    _validate_threshold(thresholds["completionRate"], "completionRate", "maximumDecrease")
    _validate_threshold(thresholds["humanInterventionRate"], "humanInterventionRate", "maximumIncrease")
    _validate_threshold(thresholds["recoveryRate"], "recoveryRate", "maximumDecrease")
    for key, delta in (("p95DurationSeconds", "minimumIncrease"), ("p95CostUsd", "minimumIncrease")):
        rule = thresholds[key]
        if not isinstance(rule, dict) or set(rule) != {"ratio", delta}:
            raise ReliabilityError(f"{key} regression threshold is malformed")
        if number(rule["ratio"], f"{key}.ratio") <= 1:
            raise ReliabilityError(f"{key}.ratio must exceed 1")
        number(rule[delta], f"{key}.{delta}")

    rollback = policy.get("rollbackUnit")
    if not isinstance(rollback, dict) or rollback.get("databaseAction") != "never-automatic" or rollback.get("operatorApprovalRequired") is not True:
        raise ReliabilityError("rollbackUnit must never automate database action and must require operator approval")
    if len(string_list(rollback.get("atomicComponents"), "rollbackUnit.atomicComponents")) < 5:
        raise ReliabilityError("rollbackUnit must bind all five versioned components")
    if policy.get("failureManifest") != str(SCENARIO_PATH):
        raise ReliabilityError("failureManifest must point to the canonical scenario registry")
    receipt = policy.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("kind") != "agent-operational-health" or receipt.get("algorithm") != "sha256-canonical-json":
        raise ReliabilityError("receipt contract is invalid")
    sources = string_list(receipt.get("sourceFiles"), "receipt.sourceFiles")
    if str(POLICY_PATH) not in sources or str(SCENARIO_PATH) not in sources:
        raise ReliabilityError("receipt sources must seal policy and scenarios")
    for index, raw in enumerate(sources):
        repo_file(root, raw, f"receipt.sourceFiles[{index}]")
    if set(string_list(receipt.get("excludedRawData"), "receipt.excludedRawData")) != {
        "prompts", "assistant text", "tool inputs", "tool output", "commands", "responses", "secrets"
    }:
        raise ReliabilityError("receipt privacy exclusions are incomplete")
    if len(string_list(policy.get("limitations"), "limitations")) < 4:
        raise ReliabilityError("limitations must name at least four boundaries")

    if scenarios.get("schemaVersion") != 1 or scenarios.get("policyId") != policy_id:
        raise ReliabilityError("scenario registry must use schema 1 and the policy id")
    rows = scenarios.get("scenarios")
    if not isinstance(rows, list) or len(rows) < 9:
        raise ReliabilityError("scenario registry must contain at least nine degraded-condition cases")
    ids: set[str] = set()
    covered: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != SCENARIO_KEYS:
            raise ReliabilityError(f"scenario {index} fields are invalid")
        scenario_id = text(row["id"], f"scenario {index}.id")
        if not re.fullmatch(r"REL-[0-9]{3}", scenario_id) or scenario_id in ids:
            raise ReliabilityError(f"scenario id is invalid or duplicate: {scenario_id}")
        ids.add(scenario_id)
        covered.add(text(row["fault"], f"{scenario_id}.fault"))
        attempts = row["attempts"]
        if not isinstance(attempts, list) or not attempts or len(attempts) > retry["maxAttempts"]:
            raise ReliabilityError(f"{scenario_id}.attempts must fit the retry budget")
        for attempt in attempts:
            if not isinstance(attempt, dict) or set(attempt) != SCENARIO_ATTEMPT_KEYS:
                raise ReliabilityError(f"{scenario_id} has a malformed attempt")
            if attempt["outcome"] not in outcomes or attempt["sideEffect"] not in SIDE_EFFECTS:
                raise ReliabilityError(f"{scenario_id} has an unknown outcome or side effect")
            if attempt["sideEffect"] != "none" and not text(attempt["idempotencyKey"], f"{scenario_id}.idempotencyKey"):
                raise ReliabilityError(f"{scenario_id} side effects require an idempotency key")
            if attempt["sideEffect"] == "none" and attempt["idempotencyKey"] is not None:
                raise ReliabilityError(f"{scenario_id} no-op must not carry an idempotency key")
        if row["expectedFinalDecision"] not in {"complete", "stop", "rollback"}:
            raise ReliabilityError(f"{scenario_id} expectedFinalDecision is invalid")
        if row["expectedCircuitState"] not in {"closed", "open"}:
            raise ReliabilityError(f"{scenario_id} expectedCircuitState is invalid")
        if not isinstance(row["expectedAppliedSideEffects"], int) or row["expectedAppliedSideEffects"] < 0:
            raise ReliabilityError(f"{scenario_id} expectedAppliedSideEffects is invalid")
    required_faults = {"tool-unavailable", "timeout", "rate-limited", "partial-outage", "corrupt-state", "duplicate-side-effect", "safety-violation"}
    if not required_faults <= covered:
        raise ReliabilityError("scenario registry does not cover every required degraded condition")
    exercise_scenarios(policy, scenarios)
    return policy, scenarios


def _exercise_one(policy: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    retry = policy["retryPolicy"]
    retryable = set(retry["retryable"])
    breaker_limit = policy["circuitBreaker"]["consecutiveRetryableFailures"]
    applied: dict[str, int] = {}
    circuit = "closed"
    decision = "stop"
    consecutive = 0
    for index, attempt in enumerate(scenario["attempts"], start=1):
        if circuit == "open":
            raise ReliabilityError(f"{scenario['id']} contains an attempt after its circuit opened")
        side_effect = attempt["sideEffect"]
        key = attempt["idempotencyKey"]
        if side_effect == "applied":
            applied[key] = applied.get(key, 0) + 1
            if applied[key] > 1:
                circuit, decision = "open", "rollback"
                continue
        outcome = attempt["outcome"]
        if outcome == "safety-violation":
            circuit, decision = "open", "rollback"
        elif outcome == "success":
            consecutive, decision = 0, "complete"
        elif outcome in retryable:
            consecutive += 1
            if consecutive >= breaker_limit:
                circuit = "open"
            decision = "retry" if index < len(scenario["attempts"]) and circuit == "closed" else "stop"
        else:
            consecutive, decision = 0, "stop"
    return {
        "id": scenario["id"],
        "decision": decision,
        "circuitState": circuit,
        "appliedSideEffects": sum(applied.values()),
    }


def exercise_scenarios(policy: dict[str, Any], scenarios: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for scenario in scenarios["scenarios"]:
        result = _exercise_one(policy, scenario)
        expected = {
            "id": scenario["id"],
            "decision": scenario["expectedFinalDecision"],
            "circuitState": scenario["expectedCircuitState"],
            "appliedSideEffects": scenario["expectedAppliedSideEffects"],
        }
        if result != expected:
            raise ReliabilityError(f"{scenario['id']} replay mismatch: expected {expected}, got {result}")
        results.append(result)
    return results


def read_observations(root: pathlib.Path, path: pathlib.Path, expected_cohort: str, policy: dict[str, Any]) -> tuple[str, pathlib.Path, dict[str, Any]]:
    raw, resolved = relative_file(root, path, f"{expected_cohort} evidence")
    payload = load_json(resolved, raw)
    if set(payload) != {"schemaVersion", "cohort", "release", "attempts"} or payload.get("schemaVersion") != 1:
        raise ReliabilityError(f"{expected_cohort} evidence schema is invalid")
    if payload.get("cohort") != expected_cohort:
        raise ReliabilityError(f"expected {expected_cohort} evidence")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", text(payload.get("release"), f"{expected_cohort}.release")):
        raise ReliabilityError(f"{expected_cohort}.release must be stable semver")
    attempts = payload.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ReliabilityError(f"{expected_cohort}.attempts must be nonempty")
    outcomes = set(policy["outcomes"])
    seen_ids: set[str] = set()
    closed_operations: set[str] = set()
    current_operation: str | None = None
    expected_attempt = 0
    previous_outcome: str | None = None
    effect_key: str | None = None
    attempts_by_operation: dict[str, int] = {}
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict) or set(attempt) != ATTEMPT_KEYS:
            raise ReliabilityError(f"{expected_cohort} attempt {index} fields are invalid")
        attempt_id = text(attempt["id"], f"attempt {index}.id")
        operation_id = text(attempt["operationId"], f"attempt {index}.operationId")
        if attempt_id in seen_ids:
            raise ReliabilityError(f"duplicate attempt id: {attempt_id}")
        seen_ids.add(attempt_id)
        if operation_id != current_operation:
            if current_operation is not None:
                closed_operations.add(current_operation)
            if operation_id in closed_operations:
                raise ReliabilityError(f"attempts for {operation_id} must be contiguous")
            current_operation, expected_attempt = operation_id, 1
            previous_outcome, effect_key = None, None
        elif previous_outcome not in set(policy["retryPolicy"]["retryable"]):
            raise ReliabilityError(f"{operation_id} cannot retry after terminal outcome {previous_outcome}")
        if attempt["attempt"] != expected_attempt:
            raise ReliabilityError(f"{operation_id} attempts must start at 1 and be contiguous")
        expected_attempt += 1
        attempts_by_operation[operation_id] = attempts_by_operation.get(operation_id, 0) + 1
        if attempts_by_operation[operation_id] > policy["retryPolicy"]["maxAttempts"]:
            raise ReliabilityError(f"{operation_id} exceeds the retry budget")
        if attempt["outcome"] not in outcomes or attempt["sideEffect"] not in SIDE_EFFECTS:
            raise ReliabilityError(f"attempt {attempt_id} has an unknown outcome or side effect")
        number(attempt["durationSeconds"], f"{attempt_id}.durationSeconds")
        number(attempt["costUsd"], f"{attempt_id}.costUsd")
        if not isinstance(attempt["humanIntervention"], bool):
            raise ReliabilityError(f"{attempt_id}.humanIntervention must be boolean")
        if not isinstance(attempt["safetyViolations"], int) or isinstance(attempt["safetyViolations"], bool) or attempt["safetyViolations"] < 0:
            raise ReliabilityError(f"{attempt_id}.safetyViolations must be a nonnegative integer")
        if attempt["outcome"] == "safety-violation" and attempt["safetyViolations"] < 1:
            raise ReliabilityError(f"{attempt_id} safety violation must be counted")
        key = attempt["idempotencyKey"]
        if attempt["sideEffect"] != "none" and not isinstance(key, str):
            raise ReliabilityError(f"{attempt_id} side effect requires an idempotency key")
        if attempt["sideEffect"] == "none" and key is not None:
            raise ReliabilityError(f"{attempt_id} no-op must not carry an idempotency key")
        if effect_key is not None and key != effect_key:
            raise ReliabilityError(f"{attempt_id} must preserve the side-effect idempotency key")
        if attempt["sideEffect"] != "none":
            effect_key = key
        previous_outcome = attempt["outcome"]
    return raw, resolved, payload


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def summarize(payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    groups: list[list[dict[str, Any]]] = []
    for attempt in payload["attempts"]:
        if not groups or groups[-1][0]["operationId"] != attempt["operationId"]:
            groups.append([])
        groups[-1].append(attempt)
    retryable = set(policy["retryPolicy"]["retryable"])
    durations, costs = [], []
    completed = interventions = safety = recoverable = recovered = 0
    duplicate_operations: set[str] = set()
    applied: dict[str, str] = {}
    for group in groups:
        final = group[-1]
        completed += final["outcome"] == "success"
        interventions += any(item["humanIntervention"] for item in group)
        safety += sum(item["safetyViolations"] for item in group)
        durations.append(sum(float(item["durationSeconds"]) for item in group))
        costs.append(sum(float(item["costUsd"]) for item in group))
        had_retryable = any(item["outcome"] in retryable for item in group)
        if had_retryable:
            recoverable += 1
            recovered += final["outcome"] == "success"
        for item in group:
            if item["sideEffect"] == "applied":
                key = item["idempotencyKey"]
                if key in applied:
                    duplicate_operations.add(item["operationId"])
                else:
                    applied[key] = item["operationId"]

    circuit = "closed"
    opened_at = None
    attempts_after_open = 0
    consecutive = 0
    applied_seen: set[str] = set()
    for attempt in payload["attempts"]:
        if circuit == "open":
            attempts_after_open += 1
            continue
        if attempt["safetyViolations"]:
            circuit, opened_at = "open", attempt["id"]
            continue
        if attempt["sideEffect"] == "applied":
            key = attempt["idempotencyKey"]
            if key in applied_seen:
                circuit, opened_at = "open", attempt["id"]
                continue
            applied_seen.add(key)
        if attempt["outcome"] in retryable:
            consecutive += 1
            if consecutive >= policy["circuitBreaker"]["consecutiveRetryableFailures"]:
                circuit, opened_at = "open", attempt["id"]
        else:
            consecutive = 0
    total = len(groups)
    return {
        "operations": total,
        "attempts": len(payload["attempts"]),
        "completionRate": completed / total,
        "p95DurationSeconds": percentile95(durations),
        "p95CostUsd": percentile95(costs),
        "humanInterventionRate": interventions / total,
        "recoveryRate": recovered / recoverable if recoverable else 1.0,
        "safetyViolationRate": safety / total,
        "duplicateSideEffectRate": len(duplicate_operations) / total,
        "circuit": {"state": circuit, "openedAtAttempt": opened_at, "attemptsAfterOpen": attempts_after_open},
    }


def slo_breaches(summary: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    slo = policy["serviceLevelObjectives"]
    breaches = []
    if summary["operations"] < slo["minimumOperations"]:
        breaches.append({"metric": "operations", "actual": summary["operations"], "minimum": slo["minimumOperations"]})
    for metric in ("completionRate", "recoveryRate"):
        if summary[metric] < slo[metric]["minimum"]:
            breaches.append({"metric": metric, "actual": summary[metric], "minimum": slo[metric]["minimum"]})
    for metric in ("p95DurationSeconds", "p95CostUsd", "humanInterventionRate", "safetyViolationRate", "duplicateSideEffectRate"):
        if summary[metric] > slo[metric]["maximum"]:
            breaches.append({"metric": metric, "actual": summary[metric], "maximum": slo[metric]["maximum"]})
    return breaches


def compare_summaries(baseline: dict[str, Any], canary: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = policy["canaryPolicy"]["regressionThresholds"]
    regressions = []
    for metric in ("completionRate", "recoveryRate"):
        decrease = baseline[metric] - canary[metric]
        if decrease > thresholds[metric]["maximumDecrease"]:
            regressions.append({"metric": metric, "baseline": baseline[metric], "canary": canary[metric], "change": -decrease})
    increase = canary["humanInterventionRate"] - baseline["humanInterventionRate"]
    if increase > thresholds["humanInterventionRate"]["maximumIncrease"]:
        regressions.append({"metric": "humanInterventionRate", "baseline": baseline["humanInterventionRate"], "canary": canary["humanInterventionRate"], "change": increase})
    for metric, delta_key in (("p95DurationSeconds", "minimumIncrease"), ("p95CostUsd", "minimumIncrease")):
        rule = thresholds[metric]
        increase = canary[metric] - baseline[metric]
        ratio = canary[metric] / baseline[metric] if baseline[metric] else (math.inf if canary[metric] else 1)
        if ratio > rule["ratio"] and increase > rule[delta_key]:
            regressions.append({"metric": metric, "baseline": baseline[metric], "canary": canary[metric], "ratio": ratio, "increase": increase})
    return regressions


def decide(baseline: dict[str, Any], canary: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    baseline_breaches = slo_breaches(baseline, policy)
    canary_breaches = slo_breaches(canary, policy)
    regressions = compare_summaries(baseline, canary, policy)
    minimum = policy["serviceLevelObjectives"]["minimumOperations"]
    if canary["circuit"]["state"] == "open":
        decision, reasons = "rollback", ["circuit-open"]
    elif baseline["operations"] < minimum or canary["operations"] < minimum:
        decision, reasons = "hold", ["insufficient-evidence"]
    elif baseline_breaches:
        decision, reasons = "hold", ["baseline-unhealthy"]
    elif canary_breaches:
        decision, reasons = "rollback", ["candidate-slo-breach"]
    elif regressions:
        decision, reasons = "rollback", ["material-regression"]
    else:
        decision, reasons = "promote", ["slo-and-comparison-pass"]
    return {
        "decision": decision,
        "reasons": reasons,
        "baselineBreaches": baseline_breaches,
        "canaryBreaches": canary_breaches,
        "regressions": regressions,
    }


def build_receipt(root: pathlib.Path, baseline_path: pathlib.Path, canary_path: pathlib.Path, *, generated_at: str | None = None) -> dict[str, Any]:
    policy, scenarios = validate(root)
    baseline_raw, baseline_resolved, baseline_payload = read_observations(root, baseline_path, "baseline", policy)
    canary_raw, canary_resolved, canary_payload = read_observations(root, canary_path, "canary", policy)
    baseline_summary = summarize(baseline_payload, policy)
    canary_summary = summarize(canary_payload, policy)
    decision = decide(baseline_summary, canary_summary, policy)
    sources = {}
    for raw in policy["receipt"]["sourceFiles"]:
        sources[raw] = digest_bytes(repo_file(root, raw, raw).read_bytes())
    sources[baseline_raw] = digest_bytes(baseline_resolved.read_bytes())
    sources[canary_raw] = digest_bytes(canary_resolved.read_bytes())
    receipt = {
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": policy["receipt"]["kind"],
        "generatedAt": generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policyId": policy["policyId"],
        "releases": {"baseline": baseline_payload["release"], "canary": canary_payload["release"]},
        "evidence": {
            "baseline": {"path": baseline_raw, "sha256": sources[baseline_raw]},
            "canary": {"path": canary_raw, "sha256": sources[canary_raw]},
        },
        "baseline": baseline_summary,
        "canary": canary_summary,
        "decision": decision,
        "scenarioReplay": {"status": "pass", "cases": len(exercise_scenarios(policy, scenarios))},
        "sources": dict(sorted(sources.items())),
    }
    receipt["receiptHash"] = digest_json(receipt)
    return receipt


def verify_receipt(root: pathlib.Path, receipt: dict[str, Any]) -> None:
    supplied = receipt.get("receiptHash")
    if not isinstance(supplied, str) or supplied != digest_json({key: value for key, value in receipt.items() if key != "receiptHash"}):
        raise ReliabilityError("operational health receipt is tampered")
    if receipt.get("kind") != "agent-operational-health" or receipt.get("schemaVersion") != 1:
        raise ReliabilityError("operational health receipt schema is invalid")
    sources = receipt.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ReliabilityError("operational health receipt has no sources")
    for raw, expected in sources.items():
        actual = digest_bytes(repo_file(root, raw, f"receipt source {raw}").read_bytes())
        if actual != expected:
            raise ReliabilityError(f"operational health receipt is source-drifted: {raw}")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != {"baseline", "canary"}:
        raise ReliabilityError("operational health receipt evidence is invalid")
    for cohort in ("baseline", "canary"):
        item = evidence[cohort]
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ReliabilityError("operational health receipt evidence is invalid")
        if not isinstance(item["path"], str) or not isinstance(item["sha256"], str):
            raise ReliabilityError("operational health receipt evidence is invalid")
        if sources.get(item["path"]) != item["sha256"]:
            raise ReliabilityError("operational health receipt evidence hash is inconsistent")
    rebuilt = build_receipt(
        root,
        root / evidence["baseline"]["path"],
        root / evidence["canary"]["path"],
        generated_at=receipt.get("generatedAt"),
    )
    if rebuilt != receipt:
        raise ReliabilityError("operational health receipt decision is inconsistent")


def write_receipt(path: pathlib.Path, receipt: dict[str, Any], root: pathlib.Path, policy: dict[str, Any]) -> None:
    sealed = {repo_file(root, raw, raw).resolve() for raw in policy["receipt"]["sourceFiles"]}
    if path.resolve(strict=False) in sealed:
        raise ReliabilityError("refusing to replace a sealed source")
    if path.is_symlink():
        raise ReliabilityError("receipt output must be a non-symlink path")
    if path.exists() and (not path.is_file() or path.stat().st_size > 0):
        raise ReliabilityError("receipt output must not replace a nonempty path")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = pathlib.Path(handle.name)
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reliability-harness.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "exercise"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    assess = sub.add_parser("assess")
    assess.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    assess.add_argument("--baseline", type=pathlib.Path, required=True)
    assess.add_argument("--canary", type=pathlib.Path, required=True)
    assess.add_argument("--output", type=pathlib.Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    verify.add_argument("--receipt", type=pathlib.Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        policy, scenarios = validate(root)
        if args.command == "validate":
            print(f"valid: reliability policy with {len(scenarios['scenarios'])} degraded-condition scenarios")
        elif args.command == "exercise":
            results = exercise_scenarios(policy, scenarios)
            print(f"pass: replayed {len(results)} degraded-condition scenarios")
        elif args.command == "assess":
            receipt = build_receipt(root, args.baseline, args.canary)
            write_receipt(args.output, receipt, root, policy)
            print(f"{receipt['decision']['decision']}: {', '.join(receipt['decision']['reasons'])}")
        else:
            receipt = load_json(args.receipt, str(args.receipt))
            verify_receipt(root, receipt)
            print(f"verified: {receipt['decision']['decision']} operational health receipt")
    except ReliabilityError as exc:
        print(f"reliability harness failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
