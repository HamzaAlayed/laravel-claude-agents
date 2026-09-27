#!/usr/bin/env python3
"""Route agent work and compare measured cost per successful outcome."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import statistics
import sys
import tempfile
from typing import Any


DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY_PATH = pathlib.PurePosixPath("config/economics-harness.json")
SCENARIO_PATH = pathlib.PurePosixPath("config/economics-scenarios.json")
AGENT_PATH = pathlib.PurePosixPath("config/agent-harness.json")
WORKLOAD_KEYS = {
    "schemaVersion", "workloadId", "complexity", "risk", "requiredCapabilities",
    "estimatedSeconds", "estimatedInputTokens", "estimatedOutputTokens",
    "estimatedToolCalls", "estimatedRetries", "estimatedUsd", "longContext",
    "stablePrefixHash", "reusableInputTokens", "independentItems", "itemsIndependent",
    "sharedAuthorityScope", "hasSideEffects", "protectedAction", "approvalGranted",
    "requiredCriteria", "budget",
}
RUN_KEYS = {
    "id", "success", "requiredCriteria", "passedCriteria", "safetyViolations",
    "durationSeconds", "billedUsd", "inputTokens", "outputTokens", "cacheReadTokens",
    "cacheWriteTokens", "toolCalls", "retries", "humanInterventions",
}
HEX64 = re.compile(r"[0-9a-f]{64}")


class EconomicsError(ValueError):
    """Economics policy, evidence, or receipt failed closed."""


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
        raise EconomicsError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise EconomicsError(f"{label} must be a JSON object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EconomicsError(f"{label} must be nonempty text")
    return value.strip()


def number(value: Any, label: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise EconomicsError(f"{label} must be a number >= {minimum}")
    return float(value)


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EconomicsError(f"{label} must be an integer >= {minimum}")
    return value


def string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise EconomicsError(f"{label} must be a {'possibly empty ' if allow_empty else 'nonempty '}string list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise EconomicsError(f"{label} must contain nonempty strings")
    if len(value) != len(set(value)):
        raise EconomicsError(f"{label} contains duplicates")
    return value


def repo_file(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise EconomicsError(f"{label} must stay inside the repository")
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise EconomicsError(f"{label} is missing or escapes the repository") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EconomicsError(f"{label} must be a regular non-symlink file")
    if not resolved.is_file():
        raise EconomicsError(f"{label} must be a regular non-symlink file")
    return resolved


def relative_file(root: pathlib.Path, path: pathlib.Path, label: str) -> tuple[str, pathlib.Path]:
    candidate = path if path.is_absolute() else root / path
    try:
        raw = candidate.absolute().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise EconomicsError(f"{label} must stay inside the repository") from exc
    return raw, repo_file(root, raw, label)


def _ratio(value: Any, label: str, *, greater_than: float | None = None) -> float:
    result = number(value, label)
    if greater_than is not None and result <= greater_than:
        raise EconomicsError(f"{label} must exceed {greater_than}")
    return result


def validate(root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    policy = load_json(root / POLICY_PATH, str(POLICY_PATH))
    scenarios = load_json(root / SCENARIO_PATH, str(SCENARIO_PATH))
    agents = load_json(root / AGENT_PATH, str(AGENT_PATH))
    required = {
        "schemaVersion", "receiptSchemaVersion", "policyId", "scope", "tierProfiles",
        "routingPolicy", "cachePolicy", "batchPolicy", "earlyStopPolicy",
        "comparisonPolicy", "budgetSource", "failureManifest", "receipt", "limitations",
    }
    if set(policy) != required or policy.get("schemaVersion") != 1 or policy.get("receiptSchemaVersion") != 1:
        raise EconomicsError("economics policy fields or schema versions are invalid")
    policy_id = text(policy["policyId"], "policyId")
    text(policy["scope"], "scope")
    tiers = policy["tierProfiles"]
    if not isinstance(tiers, dict) or list(tiers) != ["economy", "standard", "premium"]:
        raise EconomicsError("tierProfiles must declare economy, standard, and premium in order")
    expected_selectors = {"economy": ("haiku", 1), "standard": ("sonnet", 2), "premium": ("opus", 3)}
    for name, (selector, rank) in expected_selectors.items():
        profile = tiers[name]
        if not isinstance(profile, dict) or set(profile) != {"selector", "rank", "intendedUse"}:
            raise EconomicsError(f"tierProfiles.{name} fields are invalid")
        if profile["selector"] != selector or profile["rank"] != rank:
            raise EconomicsError(f"tierProfiles.{name} selector or rank is invalid")
        text(profile["intendedUse"], f"tierProfiles.{name}.intendedUse")

    routing = policy["routingPolicy"]
    expected_routing = {
        "decisions", "complexityMinimumTier", "riskMinimumTier", "longContextMinimumTier",
        "protectedActionRequiresApproval", "unknownClassificationDecision",
        "downgradeRequiresAcceptedComparisonReceipt",
    }
    if not isinstance(routing, dict) or set(routing) != expected_routing:
        raise EconomicsError("routingPolicy fields are invalid")
    if routing["decisions"] != ["route", "hold"]:
        raise EconomicsError("routing decisions are invalid")
    if routing["complexityMinimumTier"] != {"routine": "economy", "bounded": "standard", "complex": "premium"}:
        raise EconomicsError("complexity routing floors are invalid")
    if routing["riskMinimumTier"] != {"low": "economy", "medium": "standard", "high": "premium", "protected": "premium"}:
        raise EconomicsError("risk routing floors are invalid")
    if routing["longContextMinimumTier"] != "standard" or routing["protectedActionRequiresApproval"] is not True or routing["unknownClassificationDecision"] != "hold" or routing["downgradeRequiresAcceptedComparisonReceipt"] is not True:
        raise EconomicsError("routing safety contract is invalid")

    cache = policy["cachePolicy"]
    if not isinstance(cache, dict) or set(cache) != {"minimumReusableInputTokens", "requiresStablePrefixHash", "decision", "neverCache"}:
        raise EconomicsError("cachePolicy fields are invalid")
    integer(cache["minimumReusableInputTokens"], "cache minimum", minimum=1)
    if cache["requiresStablePrefixHash"] is not True or cache["decision"] != ["reuse-eligible", "not-eligible"]:
        raise EconomicsError("cache decision contract is invalid")
    if set(string_list(cache["neverCache"], "cachePolicy.neverCache")) != {"secrets", "credentials", "untrusted instructions", "volatile authorization state"}:
        raise EconomicsError("cache exclusions are incomplete")

    batch = policy["batchPolicy"]
    if batch != {
        "minimumItems": 2,
        "maximumItems": 8,
        "requiresIndependence": True,
        "requiresSharedAuthorityScope": True,
        "sideEffectsAllowed": False,
        "decision": ["eligible", "separate"],
    }:
        raise EconomicsError("batch policy must preserve the fail-closed contract")
    early = policy["earlyStopPolicy"]
    if not isinstance(early, dict) or early.get("allowedAfter") != "all-required-criteria-and-verification-pass":
        raise EconomicsError("early stop must remain verification-bound")
    if set(string_list(early.get("stopImmediatelyOn"), "earlyStopPolicy.stopImmediatelyOn")) != {"safety violation", "protected-action approval missing", "hard budget breach", "corrupt evidence"}:
        raise EconomicsError("early stop terminal outcomes are incomplete")
    if set(string_list(early.get("mustNotSkip"), "earlyStopPolicy.mustNotSkip")) != {"required verification", "security boundary", "approval", "receipt sealing"}:
        raise EconomicsError("early stop protected work is incomplete")

    comparison = policy["comparisonPolicy"]
    comparison_fields = {
        "decisions", "minimumRunsPerVariant", "minimumCompletionRate", "minimumQualityPassRate",
        "minimumCostPerSuccessfulOutcomeReduction", "maximumDurationIncreaseRatio",
        "maximumToolCallIncreaseRatio", "maximumRetryIncreasePerRun",
        "maximumHumanInterventionIncrease", "safetyViolationsMustBeZero",
        "metricOfRecord", "diagnosticMetrics",
    }
    if not isinstance(comparison, dict) or set(comparison) != comparison_fields:
        raise EconomicsError("comparisonPolicy fields are invalid")
    if comparison["decisions"] != ["adopt-candidate", "keep-baseline", "hold"]:
        raise EconomicsError("comparison decisions are invalid")
    if integer(comparison["minimumRunsPerVariant"], "minimumRunsPerVariant", minimum=5) < 5:
        raise EconomicsError("minimumRunsPerVariant must be >= 5")
    for key in ("minimumCompletionRate", "minimumQualityPassRate", "minimumCostPerSuccessfulOutcomeReduction"):
        if number(comparison[key], key) > 1:
            raise EconomicsError(f"{key} must be <= 1")
    _ratio(comparison["maximumDurationIncreaseRatio"], "maximumDurationIncreaseRatio", greater_than=1)
    _ratio(comparison["maximumToolCallIncreaseRatio"], "maximumToolCallIncreaseRatio", greater_than=1)
    number(comparison["maximumRetryIncreasePerRun"], "maximumRetryIncreasePerRun")
    number(comparison["maximumHumanInterventionIncrease"], "maximumHumanInterventionIncrease")
    if comparison["safetyViolationsMustBeZero"] is not True or comparison["metricOfRecord"] != "billedUsdPerSuccessfulOutcome":
        raise EconomicsError("comparison safety or metric-of-record contract is invalid")
    expected_diagnostics = {"input tokens", "output tokens", "cache read tokens", "cache write tokens", "tool calls", "retries", "duration"}
    if set(string_list(comparison["diagnosticMetrics"], "diagnosticMetrics")) != expected_diagnostics:
        raise EconomicsError("diagnostic metrics are incomplete")

    budget_source = policy["budgetSource"]
    if budget_source != {
        "manifest": str(AGENT_PATH),
        "jsonPath": "shared.budgets.defaults",
        "dimensions": ["max_seconds", "max_tool_calls", "max_tokens", "max_usd"],
        "retryLimitSource": "shared.retryPolicy.maxRetries",
    }:
        raise EconomicsError("budgetSource contract is invalid")
    defaults = agents.get("shared", {}).get("budgets", {}).get("defaults")
    retry_limit = agents.get("shared", {}).get("retryPolicy", {}).get("maxRetries")
    if not isinstance(defaults, dict) or any(key not in defaults for key in budget_source["dimensions"]) or not isinstance(retry_limit, int):
        raise EconomicsError("shared budget source is incomplete")

    if policy["failureManifest"] != str(SCENARIO_PATH):
        raise EconomicsError("failureManifest must point to the canonical scenario registry")
    receipt = policy["receipt"]
    if not isinstance(receipt, dict) or receipt.get("kinds") != ["economics-route", "economics-comparison"] or receipt.get("algorithm") != "sha256-canonical-json":
        raise EconomicsError("receipt contract is invalid")
    sources = string_list(receipt.get("sourceFiles"), "receipt.sourceFiles")
    for mandatory in (str(POLICY_PATH), str(SCENARIO_PATH), str(AGENT_PATH), "scripts/economics-harness.py"):
        if mandatory not in sources:
            raise EconomicsError(f"receipt sources must include {mandatory}")
    for index, raw in enumerate(sources):
        repo_file(root, raw, f"receipt.sourceFiles[{index}]")
    if set(string_list(receipt.get("excludedRawData"), "receipt.excludedRawData")) != {"prompts", "assistant text", "tool inputs", "tool output", "commands", "responses", "secrets"}:
        raise EconomicsError("receipt privacy exclusions are incomplete")
    if len(string_list(policy["limitations"], "limitations")) < 5:
        raise EconomicsError("limitations must name at least five boundaries")

    if scenarios.get("schemaVersion") != 1 or scenarios.get("policyId") != policy_id:
        raise EconomicsError("scenario registry must use schema 1 and the policy id")
    rows = scenarios.get("scenarios")
    if not isinstance(rows, list) or len(rows) < 10:
        raise EconomicsError("scenario registry must contain at least ten cases")
    ids: set[str] = set()
    for index, row in enumerate(rows):
        fields = {"id", "name", "workload", "expectedDecision", "expectedTier", "expectedCache", "expectedBatch", "expectedReasons"}
        if not isinstance(row, dict) or set(row) != fields:
            raise EconomicsError(f"scenario {index} fields are invalid")
        scenario_id = text(row["id"], f"scenario {index}.id")
        if not re.fullmatch(r"ECON-[0-9]{3}", scenario_id) or scenario_id in ids:
            raise EconomicsError(f"scenario id is invalid or duplicate: {scenario_id}")
        ids.add(scenario_id)
        result = route_workload(policy, agents, row["workload"])
        expected = (row["expectedDecision"], row["expectedTier"], row["expectedCache"], row["expectedBatch"], row["expectedReasons"])
        actual = (result["decision"], result["tier"], result["cache"], result["batch"], result["reasons"])
        if actual != expected:
            raise EconomicsError(f"{scenario_id} expected {expected!r}, got {actual!r}")
    return policy, scenarios, agents


def _validate_budget(value: Any, agents: dict[str, Any]) -> dict[str, float | int]:
    keys = {"maxSeconds", "maxTokens", "maxToolCalls", "maxRetries", "maxUsd"}
    if not isinstance(value, dict) or set(value) != keys:
        raise EconomicsError("budget fields are invalid")
    budget = {
        "maxSeconds": number(value["maxSeconds"], "budget.maxSeconds", minimum=1),
        "maxTokens": integer(value["maxTokens"], "budget.maxTokens", minimum=1),
        "maxToolCalls": integer(value["maxToolCalls"], "budget.maxToolCalls", minimum=1),
        "maxRetries": integer(value["maxRetries"], "budget.maxRetries"),
        "maxUsd": number(value["maxUsd"], "budget.maxUsd", minimum=0.001),
    }
    defaults = agents["shared"]["budgets"]["defaults"]
    ceilings = {
        "maxSeconds": defaults["max_seconds"],
        "maxTokens": defaults["max_tokens"],
        "maxToolCalls": defaults["max_tool_calls"],
        "maxUsd": defaults["max_usd"],
        "maxRetries": agents["shared"]["retryPolicy"]["maxRetries"],
    }
    if any(budget[key] > ceilings[key] for key in budget):
        raise EconomicsError("task budget cannot exceed the shared default budget")
    return budget


def _validate_workload(raw: Any, agents: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != WORKLOAD_KEYS or raw.get("schemaVersion") != 1:
        raise EconomicsError("workload fields or schemaVersion are invalid")
    value = dict(raw)
    value["workloadId"] = text(value["workloadId"], "workloadId")
    value["complexity"] = text(value["complexity"], "complexity")
    value["risk"] = text(value["risk"], "risk")
    value["requiredCapabilities"] = string_list(value["requiredCapabilities"], "requiredCapabilities")
    value["requiredCriteria"] = string_list(value["requiredCriteria"], "requiredCriteria")
    for key in ("estimatedInputTokens", "estimatedOutputTokens", "estimatedToolCalls", "estimatedRetries", "reusableInputTokens", "independentItems"):
        value[key] = integer(value[key], key)
    value["estimatedSeconds"] = number(value["estimatedSeconds"], "estimatedSeconds")
    value["estimatedUsd"] = number(value["estimatedUsd"], "estimatedUsd")
    for key in ("longContext", "itemsIndependent", "sharedAuthorityScope", "hasSideEffects", "protectedAction", "approvalGranted"):
        if not isinstance(value[key], bool):
            raise EconomicsError(f"{key} must be boolean")
    if value["stablePrefixHash"] is not None and (not isinstance(value["stablePrefixHash"], str) or not HEX64.fullmatch(value["stablePrefixHash"])):
        raise EconomicsError("stablePrefixHash must be null or a lowercase SHA-256")
    value["budget"] = _validate_budget(value["budget"], agents)
    return value


def route_workload(policy: dict[str, Any], agents: dict[str, Any], raw: Any) -> dict[str, Any]:
    workload = _validate_workload(raw, agents)
    routing = policy["routingPolicy"]
    tiers = policy["tierProfiles"]
    reasons: list[str] = []
    complexity_tier = routing["complexityMinimumTier"].get(workload["complexity"])
    risk_tier = routing["riskMinimumTier"].get(workload["risk"])
    if complexity_tier is None or risk_tier is None:
        reasons.append("unknown-classification")
    if (workload["protectedAction"] or workload["risk"] == "protected") and not workload["approvalGranted"]:
        reasons.append("protected-action-approval-missing")
    budget_checks = {
        "seconds": workload["estimatedSeconds"] > workload["budget"]["maxSeconds"],
        "tokens": workload["estimatedInputTokens"] + workload["estimatedOutputTokens"] > workload["budget"]["maxTokens"],
        "tool-calls": workload["estimatedToolCalls"] > workload["budget"]["maxToolCalls"],
        "retries": workload["estimatedRetries"] > workload["budget"]["maxRetries"],
        "usd": workload["estimatedUsd"] > workload["budget"]["maxUsd"],
    }
    reasons.extend(f"estimated-{name}-budget-exceeded" for name, exceeded in budget_checks.items() if exceeded)

    cache = "not-eligible"
    if workload["reusableInputTokens"] >= policy["cachePolicy"]["minimumReusableInputTokens"] and workload["stablePrefixHash"] is not None:
        cache = "reuse-eligible"
    batch = "separate"
    batch_policy = policy["batchPolicy"]
    if (
        batch_policy["minimumItems"] <= workload["independentItems"] <= batch_policy["maximumItems"]
        and workload["itemsIndependent"]
        and workload["sharedAuthorityScope"]
        and not workload["hasSideEffects"]
    ):
        batch = "eligible"

    tier = None
    if complexity_tier is not None and risk_tier is not None:
        candidates = [complexity_tier, risk_tier]
        if workload["longContext"]:
            candidates.append(routing["longContextMinimumTier"])
        tier = max(candidates, key=lambda item: tiers[item]["rank"])
    decision = "hold" if reasons else "route"
    if decision == "hold":
        tier = None
    else:
        floor_reasons = []
        if tier == "premium":
            floor_reasons.append("premium-risk-or-complexity-floor")
        elif tier == "standard":
            floor_reasons.append("standard-complexity-or-context-floor")
        else:
            floor_reasons.append("routine-economy-route")
        reasons = floor_reasons
    return {
        "workloadId": workload["workloadId"],
        "decision": decision,
        "tier": tier,
        "selector": tiers[tier]["selector"] if tier else None,
        "cache": cache,
        "batch": batch,
        "earlyStop": policy["earlyStopPolicy"]["allowedAfter"],
        "reasons": sorted(reasons),
        "budget": workload["budget"],
        "requiredCriteriaHash": digest_json(sorted(workload["requiredCriteria"])),
    }


def exercise_scenarios(policy: dict[str, Any], scenarios: dict[str, Any], agents: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"id": row["id"], **route_workload(policy, agents, row["workload"])} for row in scenarios["scenarios"]]


def source_hashes(root: pathlib.Path, policy: dict[str, Any]) -> dict[str, str]:
    return {raw: digest_bytes(repo_file(root, raw, f"receipt source {raw}").read_bytes()) for raw in policy["receipt"]["sourceFiles"]}


def _seal(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["seal"] = digest_json(receipt)
    return receipt


def build_route_receipt(root: pathlib.Path, workload_path: pathlib.Path) -> dict[str, Any]:
    policy, _, agents = validate(root)
    raw, path = relative_file(root, workload_path, "workload")
    workload = load_json(path, "workload")
    return _seal({
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": "economics-route",
        "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policyId": policy["policyId"],
        "sourceHashes": source_hashes(root, policy),
        "workload": {"path": raw, "sha256": digest_bytes(path.read_bytes())},
        "route": route_workload(policy, agents, workload),
    })


def read_observations(root: pathlib.Path, path: pathlib.Path, expected_variant: str, agents: dict[str, Any]) -> tuple[str, pathlib.Path, dict[str, Any]]:
    raw, resolved = relative_file(root, path, f"{expected_variant} evidence")
    payload = load_json(resolved, f"{expected_variant} evidence")
    if set(payload) != {"schemaVersion", "workloadId", "variant", "configuration", "runs"} or payload.get("schemaVersion") != 1 or payload.get("variant") != expected_variant:
        raise EconomicsError(f"{expected_variant} evidence fields, schema, or variant are invalid")
    text(payload["workloadId"], f"{expected_variant}.workloadId")
    configuration = payload["configuration"]
    if not isinstance(configuration, dict) or set(configuration) != {"modelTier", "contextStrategy", "cacheStrategy", "batchSize", "maxAttempts"}:
        raise EconomicsError(f"{expected_variant}.configuration fields are invalid")
    if configuration["modelTier"] not in {"economy", "standard", "premium"}:
        raise EconomicsError(f"{expected_variant}.configuration.modelTier is invalid")
    if configuration["contextStrategy"] not in {"full", "bounded", "retrieval"} or configuration["cacheStrategy"] not in {"none", "read", "write"}:
        raise EconomicsError(f"{expected_variant} context or cache strategy is invalid")
    batch_size = integer(configuration["batchSize"], f"{expected_variant}.batchSize", minimum=1)
    max_attempts = integer(configuration["maxAttempts"], f"{expected_variant}.maxAttempts", minimum=1)
    if batch_size > 8:
        raise EconomicsError(f"{expected_variant}.batchSize exceeds the policy maximum")
    if max_attempts > agents["shared"]["retryPolicy"]["maxRetries"] + 1:
        raise EconomicsError(f"{expected_variant}.maxAttempts exceeds the shared retry limit")
    runs = payload["runs"]
    if not isinstance(runs, list) or not runs:
        raise EconomicsError(f"{expected_variant}.runs must be nonempty")
    ids: set[str] = set()
    criteria: list[str] | None = None
    for index, run in enumerate(runs):
        if not isinstance(run, dict) or set(run) != RUN_KEYS:
            raise EconomicsError(f"{expected_variant} run {index} fields are invalid")
        run_id = text(run["id"], f"{expected_variant} run {index}.id")
        if run_id in ids:
            raise EconomicsError(f"{expected_variant} run ids must be unique")
        ids.add(run_id)
        if not isinstance(run["success"], bool):
            raise EconomicsError(f"{run_id}.success must be boolean")
        required = string_list(run["requiredCriteria"], f"{run_id}.requiredCriteria")
        passed = string_list(run["passedCriteria"], f"{run_id}.passedCriteria", allow_empty=True)
        if criteria is None:
            criteria = sorted(required)
        elif sorted(required) != criteria:
            raise EconomicsError(f"{expected_variant} runs must use one criteria definition")
        if not set(passed) <= set(required):
            raise EconomicsError(f"{run_id}.passedCriteria contains undeclared criteria")
        number(run["durationSeconds"], f"{run_id}.durationSeconds", minimum=0.001)
        number(run["billedUsd"], f"{run_id}.billedUsd")
        for key in ("safetyViolations", "inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens", "toolCalls", "retries", "humanInterventions"):
            integer(run[key], f"{run_id}.{key}")
    return raw, resolved, payload


def aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    runs = payload["runs"]
    required_total = sum(len(run["requiredCriteria"]) for run in runs)
    passed_total = sum(len(run["passedCriteria"]) for run in runs)
    successful = [
        run for run in runs
        if run["success"] and set(run["passedCriteria"]) == set(run["requiredCriteria"]) and run["safetyViolations"] == 0
    ]
    total_cost = sum(run["billedUsd"] for run in runs)
    return {
        "configurationHash": digest_json(payload["configuration"]),
        "criteriaHash": digest_json(sorted(runs[0]["requiredCriteria"])),
        "runs": len(runs),
        "completionRate": round(sum(1 for run in runs if run["success"]) / len(runs), 6),
        "qualityPassRate": round(passed_total / required_total, 6) if required_total else 0,
        "safetyViolations": sum(run["safetyViolations"] for run in runs),
        "successfulOutcomes": len(successful),
        "totalBilledUsd": round(total_cost, 6),
        "billedUsdPerSuccessfulOutcome": round(total_cost / len(successful), 6) if successful else "infinite",
        "medianDurationSeconds": round(statistics.median(run["durationSeconds"] for run in runs), 6),
        "medianBilledUsd": round(statistics.median(run["billedUsd"] for run in runs), 6),
        "medianInputTokens": round(statistics.median(run["inputTokens"] for run in runs), 6),
        "medianOutputTokens": round(statistics.median(run["outputTokens"] for run in runs), 6),
        "medianCacheReadTokens": round(statistics.median(run["cacheReadTokens"] for run in runs), 6),
        "medianCacheWriteTokens": round(statistics.median(run["cacheWriteTokens"] for run in runs), 6),
        "medianToolCalls": round(statistics.median(run["toolCalls"] for run in runs), 6),
        "retriesPerRun": round(sum(run["retries"] for run in runs) / len(runs), 6),
        "humanInterventions": sum(run["humanInterventions"] for run in runs),
    }


def _candidate_budget_breaches(payload: dict[str, Any], agents: dict[str, Any]) -> list[str]:
    defaults = agents["shared"]["budgets"]["defaults"]
    retry_limit = agents["shared"]["retryPolicy"]["maxRetries"]
    breaches: set[str] = set()
    for run in payload["runs"]:
        checks = {
            "duration": run["durationSeconds"] > defaults["max_seconds"],
            "tokens": run["inputTokens"] + run["outputTokens"] > defaults["max_tokens"],
            "tool-calls": run["toolCalls"] > defaults["max_tool_calls"],
            "usd": run["billedUsd"] > defaults["max_usd"],
            "retries": run["retries"] > retry_limit,
        }
        breaches.update(name for name, breached in checks.items() if breached)
    return sorted(breaches)


def comparison_decision(policy: dict[str, Any], agents: dict[str, Any], baseline_payload: dict[str, Any], candidate_payload: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    rules = policy["comparisonPolicy"]
    if baseline["runs"] < rules["minimumRunsPerVariant"] or candidate["runs"] < rules["minimumRunsPerVariant"]:
        return {"decision": "hold", "reasons": ["insufficient-evidence"]}
    if baseline["criteriaHash"] != candidate["criteriaHash"]:
        return {"decision": "hold", "reasons": ["criteria-definition-mismatch"]}
    if baseline["configurationHash"] == candidate["configurationHash"]:
        return {"decision": "hold", "reasons": ["configuration-not-changed"]}
    if baseline["completionRate"] < rules["minimumCompletionRate"] or baseline["qualityPassRate"] < rules["minimumQualityPassRate"] or baseline["safetyViolations"]:
        return {"decision": "hold", "reasons": ["baseline-unhealthy"]}
    reasons = []
    if candidate["safetyViolations"]:
        reasons.append("safety-violation")
    if candidate["completionRate"] < baseline["completionRate"] or candidate["qualityPassRate"] < baseline["qualityPassRate"]:
        reasons.append("quality-or-completion-regression")
    if candidate["successfulOutcomes"] == 0:
        reasons.append("no-successful-outcome")
    breaches = _candidate_budget_breaches(candidate_payload, agents)
    if breaches:
        reasons.extend(f"hard-{name}-budget-breach" for name in breaches)
    duration_ratio = candidate["medianDurationSeconds"] / baseline["medianDurationSeconds"]
    tool_ratio = candidate["medianToolCalls"] / baseline["medianToolCalls"] if baseline["medianToolCalls"] else (1 if candidate["medianToolCalls"] == 0 else float("inf"))
    retry_increase = candidate["retriesPerRun"] - baseline["retriesPerRun"]
    intervention_increase = candidate["humanInterventions"] - baseline["humanInterventions"]
    if duration_ratio > rules["maximumDurationIncreaseRatio"]:
        reasons.append("duration-regression")
    if tool_ratio > rules["maximumToolCallIncreaseRatio"]:
        reasons.append("tool-call-regression")
    if retry_increase > rules["maximumRetryIncreasePerRun"]:
        reasons.append("retry-regression")
    if intervention_increase > rules["maximumHumanInterventionIncrease"]:
        reasons.append("human-intervention-regression")
    baseline_cost = baseline["billedUsdPerSuccessfulOutcome"]
    candidate_cost = candidate["billedUsdPerSuccessfulOutcome"]
    if baseline_cost == "infinite":
        return {"decision": "hold", "reasons": ["baseline-unhealthy"]}
    reduction = 1 - (candidate_cost / baseline_cost) if candidate_cost != "infinite" else float("-inf")
    if reduction < rules["minimumCostPerSuccessfulOutcomeReduction"]:
        reasons.append("insufficient-cost-per-success-reduction")
    return {
        "decision": "keep-baseline" if reasons else "adopt-candidate",
        "reasons": sorted(set(reasons)),
        "costPerSuccessfulOutcomeReduction": round(reduction, 6) if reduction != float("-inf") else "negative-infinite",
        "durationIncreaseRatio": round(duration_ratio, 6),
        "toolCallIncreaseRatio": round(tool_ratio, 6) if tool_ratio != float("inf") else "infinite",
        "retryIncreasePerRun": round(retry_increase, 6),
        "humanInterventionIncrease": intervention_increase,
    }


def build_comparison_receipt(root: pathlib.Path, baseline_path: pathlib.Path, candidate_path: pathlib.Path) -> dict[str, Any]:
    policy, _, agents = validate(root)
    baseline_raw, baseline_file, baseline_payload = read_observations(root, baseline_path, "baseline", agents)
    candidate_raw, candidate_file, candidate_payload = read_observations(root, candidate_path, "candidate", agents)
    if baseline_payload["workloadId"] != candidate_payload["workloadId"]:
        raise EconomicsError("baseline and candidate must describe the same workloadId")
    baseline = aggregate(baseline_payload)
    candidate = aggregate(candidate_payload)
    return _seal({
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": "economics-comparison",
        "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policyId": policy["policyId"],
        "workloadId": baseline_payload["workloadId"],
        "sourceHashes": source_hashes(root, policy),
        "evidence": {
            "baseline": {"path": baseline_raw, "sha256": digest_bytes(baseline_file.read_bytes())},
            "candidate": {"path": candidate_raw, "sha256": digest_bytes(candidate_file.read_bytes())},
        },
        "baseline": baseline,
        "candidate": candidate,
        "decision": comparison_decision(policy, agents, baseline_payload, candidate_payload, baseline, candidate),
    })


def verify_receipt(root: pathlib.Path, receipt: dict[str, Any]) -> None:
    policy, _, agents = validate(root)
    if receipt.get("schemaVersion") != policy["receiptSchemaVersion"] or receipt.get("policyId") != policy["policyId"]:
        raise EconomicsError("receipt schema or policy id is invalid")
    seal = receipt.get("seal")
    unsigned = dict(receipt)
    unsigned.pop("seal", None)
    if not isinstance(seal, str) or seal != digest_json(unsigned):
        raise EconomicsError("receipt is tampered")
    if receipt.get("sourceHashes") != source_hashes(root, policy):
        raise EconomicsError("receipt policy source-drifted")
    if receipt.get("kind") == "economics-route":
        evidence = receipt.get("workload", {})
        raw, path = relative_file(root, pathlib.Path(str(evidence.get("path", ""))), "workload")
        if evidence != {"path": raw, "sha256": digest_bytes(path.read_bytes())}:
            raise EconomicsError("receipt workload source-drifted")
        if receipt.get("route") != route_workload(policy, agents, load_json(path, "workload")):
            raise EconomicsError("receipt route is stale")
    elif receipt.get("kind") == "economics-comparison":
        evidence = receipt.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"baseline", "candidate"}:
            raise EconomicsError("receipt comparison evidence is invalid")
        payloads = {}
        for variant in ("baseline", "candidate"):
            record = evidence[variant]
            raw, path = relative_file(root, pathlib.Path(str(record.get("path", ""))), f"{variant} evidence")
            if record != {"path": raw, "sha256": digest_bytes(path.read_bytes())}:
                raise EconomicsError(f"receipt {variant} source-drifted")
            _, _, payloads[variant] = read_observations(root, path, variant, agents)
        baseline = aggregate(payloads["baseline"])
        candidate = aggregate(payloads["candidate"])
        decision = comparison_decision(policy, agents, payloads["baseline"], payloads["candidate"], baseline, candidate)
        if receipt.get("baseline") != baseline or receipt.get("candidate") != candidate or receipt.get("decision") != decision:
            raise EconomicsError("receipt comparison is stale")
    else:
        raise EconomicsError("receipt kind is invalid")


def write_receipt(path: pathlib.Path, receipt: dict[str, Any], root: pathlib.Path, policy: dict[str, Any]) -> None:
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.absolute().relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise EconomicsError("receipt output must stay inside the repository") from exc
    cursor = root.resolve()
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise EconomicsError("receipt output parent must not be a symlink")
    if candidate.is_symlink():
        raise EconomicsError("receipt output must be a regular non-symlink file")
    sealed = {repo_file(root, raw, f"sealed source {raw}").resolve() for raw in policy["receipt"]["sourceFiles"]}
    if candidate.resolve() in sealed:
        raise EconomicsError("receipt output cannot replace a sealed source")
    if candidate.exists() and candidate.stat().st_size:
        raise EconomicsError("receipt output must not overwrite a nonempty file")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        candidate.parent.resolve(strict=True).relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise EconomicsError("receipt output parent must stay inside the repository") from exc
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=candidate.parent, delete=False) as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = pathlib.Path(handle.name)
    temporary.replace(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    exercise_parser = subparsers.add_parser("exercise")
    exercise_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    route_parser = subparsers.add_parser("route")
    route_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    route_parser.add_argument("--workload", type=pathlib.Path, required=True)
    route_parser.add_argument("--output", type=pathlib.Path, required=True)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    compare_parser.add_argument("--baseline", type=pathlib.Path, required=True)
    compare_parser.add_argument("--candidate", type=pathlib.Path, required=True)
    compare_parser.add_argument("--output", type=pathlib.Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    verify_parser.add_argument("--receipt", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        policy, scenarios, agents = validate(root)
        if args.command == "validate":
            print(f"validated: {policy['policyId']} ({len(scenarios['scenarios'])} scenarios)")
        elif args.command == "exercise":
            print(json.dumps(exercise_scenarios(policy, scenarios, agents), indent=2, sort_keys=True))
        elif args.command == "route":
            receipt = build_route_receipt(root, args.workload)
            write_receipt(args.output, receipt, root, policy)
            print(f"{receipt['route']['decision']}: {receipt['route']['tier'] or ','.join(receipt['route']['reasons'])}")
        elif args.command == "compare":
            receipt = build_comparison_receipt(root, args.baseline, args.candidate)
            write_receipt(args.output, receipt, root, policy)
            print(f"{receipt['decision']['decision']}: {','.join(receipt['decision']['reasons']) or 'measured-savings'}")
        elif args.command == "verify":
            _, receipt_path = relative_file(root, args.receipt, "receipt")
            receipt = load_json(receipt_path, "receipt")
            verify_receipt(root, receipt)
            decision = receipt["route"]["decision"] if receipt["kind"] == "economics-route" else receipt["decision"]["decision"]
            print(f"verified: {decision}")
    except EconomicsError as exc:
        print(f"economics error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
