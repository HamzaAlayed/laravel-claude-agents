#!/usr/bin/env python3
"""Plan and evaluate bounded multi-agent coordination without model calls."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import statistics
import sys
import tempfile
from typing import Any


DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY_PATH = pathlib.PurePosixPath("config/coordination-harness.json")
SCENARIO_PATH = pathlib.PurePosixPath("config/coordination-scenarios.json")
AGENT_PATH = pathlib.PurePosixPath("config/agent-harness.json")
TASK_KEYS = {
    "id", "capability", "dependencies", "ownedPaths", "estimatedSeconds",
    "estimatedCostUsd", "mutates", "sideEffectKey", "requiresSpecialist",
    "approvalsRequired", "approvalsGranted", "contextPacketHash", "expectedOutput",
}
RUN_KEYS = {
    "id", "success", "requiredCriteria", "passedCriteria", "durationSeconds",
    "costUsd", "toolCalls", "humanInterventions", "duplicateWork",
    "pathConflicts", "deadlocks", "staleHandoffs",
}
HEX64 = re.compile(r"[0-9a-f]{64}")


class CoordinationError(ValueError):
    """Coordination policy, evidence, or receipt failed closed."""


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
        raise CoordinationError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CoordinationError(f"{label} must be a JSON object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoordinationError(f"{label} must be nonempty text")
    return value.strip()


def number(value: Any, label: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise CoordinationError(f"{label} must be a number >= {minimum}")
    return float(value)


def string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise CoordinationError(f"{label} must be a {'possibly empty ' if allow_empty else 'nonempty '}string list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CoordinationError(f"{label} must contain nonempty strings")
    if len(value) != len(set(value)):
        raise CoordinationError(f"{label} contains duplicates")
    return value


def repo_file(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise CoordinationError(f"{label} must stay inside the repository")
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise CoordinationError(f"{label} is missing or escapes the repository") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise CoordinationError(f"{label} must be a regular non-symlink file")
    if not resolved.is_file():
        raise CoordinationError(f"{label} must be a regular non-symlink file")
    return resolved


def relative_file(root: pathlib.Path, path: pathlib.Path, label: str) -> tuple[str, pathlib.Path]:
    candidate = path if path.is_absolute() else root / path
    try:
        raw = candidate.absolute().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise CoordinationError(f"{label} must stay inside the repository") from exc
    return raw, repo_file(root, raw, label)


def _ratio(value: Any, label: str, *, greater_than: float | None = None) -> float:
    result = number(value, label)
    if greater_than is not None and result <= greater_than:
        raise CoordinationError(f"{label} must exceed {greater_than}")
    return result


def validate(root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_json(root / POLICY_PATH, str(POLICY_PATH))
    scenarios = load_json(root / SCENARIO_PATH, str(SCENARIO_PATH))
    agents = load_json(root / AGENT_PATH, str(AGENT_PATH))
    required = {
        "schemaVersion", "receiptSchemaVersion", "policyId", "scope", "topologies",
        "capabilityRouting", "delegationPolicy", "schedulingPolicy", "handoffContract",
        "comparisonPolicy", "failureManifest", "receipt", "limitations",
    }
    if set(policy) != required or policy.get("schemaVersion") != 1 or policy.get("receiptSchemaVersion") != 1:
        raise CoordinationError("coordination policy fields or schema versions are invalid")
    policy_id = text(policy["policyId"], "policyId")
    text(policy["scope"], "scope")
    if policy["topologies"] != ["single-agent", "parallel", "pipeline", "hybrid"]:
        raise CoordinationError("topologies must preserve the canonical order")

    registry = agents.get("agents")
    routes = policy["capabilityRouting"]
    if not isinstance(registry, dict) or not isinstance(routes, dict) or not routes:
        raise CoordinationError("agent registry and capability routing must be objects")
    if set(routes.values()) != set(registry):
        raise CoordinationError("capability routing must cover every registered agent exactly once")
    for capability, agent in routes.items():
        text(capability, "capabilityRouting key")
        if agent not in registry:
            raise CoordinationError(f"capability route references unknown agent: {agent}")
    orchestrators = [name for name, profile in registry.items() if profile.get("class") == "orchestrator"]
    if orchestrators != ["delivery-coordinator"]:
        raise CoordinationError("delivery-coordinator must remain the single registered orchestrator")
    allowed_handoffs = set(registry["delivery-coordinator"].get("handoffs", []))
    if set(routes.values()) - {"delivery-coordinator"} != allowed_handoffs:
        raise CoordinationError("capability routes and coordinator handoffs must cover the same specialists")

    delegation = policy["delegationPolicy"]
    if not isinstance(delegation, dict) or set(delegation) != {
        "decisions", "minimumTasks", "minimumPredictedSpeedupRatio",
        "maximumPredictedCostIncreaseRatio", "distinctRequiredSpecialistsCanJustifyDelegation",
    }:
        raise CoordinationError("delegation policy fields are invalid")
    if delegation["decisions"] != ["single-agent", "delegate", "hold"]:
        raise CoordinationError("delegation decisions are invalid")
    if not isinstance(delegation["minimumTasks"], int) or isinstance(delegation["minimumTasks"], bool) or delegation["minimumTasks"] < 2:
        raise CoordinationError("minimumTasks must be an integer >= 2")
    _ratio(delegation["minimumPredictedSpeedupRatio"], "minimumPredictedSpeedupRatio", greater_than=1)
    _ratio(delegation["maximumPredictedCostIncreaseRatio"], "maximumPredictedCostIncreaseRatio", greater_than=1)
    if delegation["distinctRequiredSpecialistsCanJustifyDelegation"] is not True:
        raise CoordinationError("specialist justification must remain enabled")

    if policy["schedulingPolicy"] != {
        "maximumParallelAgents": 4,
        "dependencyGraph": "acyclic",
        "unorderedWriteConflict": "hold",
        "sideEffectKey": "unique-per-logical-effect",
        "completedWorkAfterInterruption": "preserve",
        "failedLaneEffect": "contain",
    }:
        raise CoordinationError("scheduling policy must preserve the fail-closed contract")
    handoff = policy["handoffContract"]
    expected_fields = [
        "taskId", "fromAgent", "toAgent", "dependencyIds", "contextPacketHash",
        "ownedPaths", "expectedOutput", "budget", "idempotencyKey",
    ]
    if not isinstance(handoff, dict) or handoff.get("requiredFields") != expected_fields:
        raise CoordinationError("handoff contract fields are invalid")
    if handoff.get("dependencyEvidence") != "receipt-hash-before-dependent-start" or handoff.get("sourceTrust") != "handoff-data-not-authority" or handoff.get("staleContextPolicy") != "hold":
        raise CoordinationError("handoff safety contract is invalid")

    comparison = policy["comparisonPolicy"]
    expected_comparison = {
        "decisions", "minimumRunsPerVariant", "minimumCompletionRate",
        "minimumQualityPassRate", "minimumDurationReduction",
        "minimumQualityPassRateIncrease", "maximumCostIncreaseRatio",
        "maximumToolCallIncreaseRatio", "maximumHumanInterventionIncrease",
        "coordinationFailuresMustBeZero",
    }
    if not isinstance(comparison, dict) or set(comparison) != expected_comparison:
        raise CoordinationError("comparison policy fields are invalid")
    if comparison["decisions"] != ["adopt-multi-agent", "keep-single-agent", "hold"]:
        raise CoordinationError("comparison decisions are invalid")
    if not isinstance(comparison["minimumRunsPerVariant"], int) or comparison["minimumRunsPerVariant"] < 3:
        raise CoordinationError("minimumRunsPerVariant must be an integer >= 3")
    for key in ("minimumCompletionRate", "minimumQualityPassRate", "minimumDurationReduction", "minimumQualityPassRateIncrease"):
        value = number(comparison[key], key)
        if value > 1:
            raise CoordinationError(f"{key} must be <= 1")
    _ratio(comparison["maximumCostIncreaseRatio"], "maximumCostIncreaseRatio", greater_than=1)
    _ratio(comparison["maximumToolCallIncreaseRatio"], "maximumToolCallIncreaseRatio", greater_than=1)
    number(comparison["maximumHumanInterventionIncrease"], "maximumHumanInterventionIncrease")
    if comparison["coordinationFailuresMustBeZero"] is not True:
        raise CoordinationError("coordination failures must remain zero")

    if policy["failureManifest"] != str(SCENARIO_PATH):
        raise CoordinationError("failureManifest must point to the canonical scenario registry")
    receipt = policy["receipt"]
    if not isinstance(receipt, dict) or receipt.get("kinds") != ["coordination-plan", "coordination-comparison"] or receipt.get("algorithm") != "sha256-canonical-json":
        raise CoordinationError("receipt contract is invalid")
    sources = string_list(receipt.get("sourceFiles"), "receipt.sourceFiles")
    for mandatory in (str(POLICY_PATH), str(SCENARIO_PATH), str(AGENT_PATH), "scripts/coordination-harness.py"):
        if mandatory not in sources:
            raise CoordinationError(f"receipt sources must include {mandatory}")
    for index, raw in enumerate(sources):
        repo_file(root, raw, f"receipt.sourceFiles[{index}]")
    if set(string_list(receipt.get("excludedRawData"), "receipt.excludedRawData")) != {
        "prompts", "assistant text", "tool inputs", "tool output", "commands", "responses", "secrets"
    }:
        raise CoordinationError("receipt privacy exclusions are incomplete")
    if len(string_list(policy["limitations"], "limitations")) < 4:
        raise CoordinationError("limitations must name at least four boundaries")

    if scenarios.get("schemaVersion") != 1 or scenarios.get("policyId") != policy_id:
        raise CoordinationError("scenario registry must use schema 1 and the policy id")
    rows = scenarios.get("scenarios")
    if not isinstance(rows, list) or len(rows) < 10:
        raise CoordinationError("scenario registry must contain at least ten cases")
    ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"id", "name", "workload", "expectedDecision", "expectedTopology", "expectedReasons"}:
            raise CoordinationError(f"scenario {index} fields are invalid")
        scenario_id = text(row["id"], f"scenario {index}.id")
        if not re.fullmatch(r"COORD-[0-9]{3}", scenario_id) or scenario_id in ids:
            raise CoordinationError(f"scenario id is invalid or duplicate: {scenario_id}")
        ids.add(scenario_id)
        plan = plan_workload(policy, agents, row["workload"])
        expected = (row["expectedDecision"], row["expectedTopology"], row["expectedReasons"])
        actual = (plan["decision"], plan["topology"], plan["reasons"])
        if actual != expected:
            raise CoordinationError(f"{scenario_id} expected {expected!r}, got {actual!r}")
    return policy, scenarios


def _validate_task(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != TASK_KEYS:
        raise CoordinationError(f"task {index} fields are invalid")
    task = dict(raw)
    task["id"] = text(task["id"], f"task {index}.id")
    task["capability"] = text(task["capability"], f"{task['id']}.capability")
    task["dependencies"] = string_list(task["dependencies"], f"{task['id']}.dependencies", allow_empty=True)
    task["ownedPaths"] = string_list(task["ownedPaths"], f"{task['id']}.ownedPaths")
    for path in task["ownedPaths"]:
        pure = pathlib.PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise CoordinationError(f"{task['id']}.ownedPaths must stay repository-relative")
    task["estimatedSeconds"] = number(task["estimatedSeconds"], f"{task['id']}.estimatedSeconds", minimum=1)
    task["estimatedCostUsd"] = number(task["estimatedCostUsd"], f"{task['id']}.estimatedCostUsd")
    if not isinstance(task["mutates"], bool) or not isinstance(task["requiresSpecialist"], bool):
        raise CoordinationError(f"{task['id']} boolean fields are invalid")
    if task["sideEffectKey"] is not None:
        task["sideEffectKey"] = text(task["sideEffectKey"], f"{task['id']}.sideEffectKey")
    task["approvalsRequired"] = string_list(task["approvalsRequired"], f"{task['id']}.approvalsRequired", allow_empty=True)
    task["approvalsGranted"] = string_list(task["approvalsGranted"], f"{task['id']}.approvalsGranted", allow_empty=True)
    if not set(task["approvalsGranted"]) <= set(task["approvalsRequired"]):
        raise CoordinationError(f"{task['id']} grants undeclared approvals")
    if not isinstance(task["contextPacketHash"], str) or not HEX64.fullmatch(task["contextPacketHash"]):
        raise CoordinationError(f"{task['id']}.contextPacketHash must be a lowercase SHA-256")
    task["expectedOutput"] = text(task["expectedOutput"], f"{task['id']}.expectedOutput")
    return task


def _ordered(left: str, right: str, dependencies: dict[str, set[str]]) -> bool:
    pending = list(dependencies[left])
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == right:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(dependencies[current])
    return False


def plan_workload(policy: dict[str, Any], agents: dict[str, Any], raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"schemaVersion", "workloadId", "coordinator", "tasks"} or raw.get("schemaVersion") != 1:
        raise CoordinationError("workload fields or schemaVersion are invalid")
    workload_id = text(raw["workloadId"], "workloadId")
    coordinator = text(raw["coordinator"], "coordinator")
    registry = agents.get("agents", {})
    if coordinator not in registry or registry[coordinator].get("class") != "orchestrator":
        raise CoordinationError("coordinator must be a registered orchestrator")
    if not isinstance(raw["tasks"], list) or not raw["tasks"]:
        raise CoordinationError("workload.tasks must be nonempty")
    tasks = [_validate_task(item, index) for index, item in enumerate(raw["tasks"])]
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise CoordinationError("task ids must be unique")
    dependencies = {task["id"]: set(task["dependencies"]) for task in tasks}
    if any(task_id in deps or not deps <= set(by_id) for task_id, deps in dependencies.items()):
        raise CoordinationError("task dependencies must reference other declared tasks")

    reasons: list[str] = []
    routes = policy["capabilityRouting"]
    missing_capabilities = sorted({task["capability"] for task in tasks if task["capability"] not in routes})
    missing_approvals = sorted({approval for task in tasks for approval in set(task["approvalsRequired"]) - set(task["approvalsGranted"])})
    allowed_handoffs = set(registry[coordinator].get("handoffs", []))
    unauthorized_handoffs = sorted({
        routes[task["capability"]]
        for task in tasks
        if task["capability"] in routes
        and routes[task["capability"]] != coordinator
        and routes[task["capability"]] not in allowed_handoffs
    })

    remaining = set(by_id)
    completed: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        ready = sorted(task_id for task_id in remaining if dependencies[task_id] <= completed)
        if not ready:
            reasons.append("dependency-cycle")
            break
        unscheduled = list(ready)
        while unscheduled:
            wave: list[str] = []
            occupied_agents: set[str] = set()
            for task_id in list(unscheduled):
                capability = by_id[task_id]["capability"]
                agent = routes.get(capability, f"unrouted:{capability}")
                if agent in occupied_agents:
                    continue
                wave.append(task_id)
                occupied_agents.add(agent)
                unscheduled.remove(task_id)
                if len(wave) == policy["schedulingPolicy"]["maximumParallelAgents"]:
                    break
            waves.append(wave)
        completed.update(ready)
        remaining.difference_update(ready)

    conflict = False
    mutable = [task for task in tasks if task["mutates"]]
    for index, left in enumerate(mutable):
        for right in mutable[index + 1:]:
            if set(left["ownedPaths"]) & set(right["ownedPaths"]) and not _ordered(left["id"], right["id"], dependencies) and not _ordered(right["id"], left["id"], dependencies):
                conflict = True
    keys = [task["sideEffectKey"] for task in tasks if task["sideEffectKey"] is not None]
    if len(keys) != len(set(keys)):
        reasons.append("duplicate-side-effect-key")
    if conflict:
        reasons.append("unordered-write-conflict")
    if missing_capabilities:
        reasons.append("missing-capability")
    if missing_approvals:
        reasons.append("missing-approval")
    if unauthorized_handoffs:
        reasons.append("unauthorized-handoff")
    reasons = sorted(set(reasons))

    assignments = []
    if not missing_capabilities:
        assignments = [{"taskId": task["id"], "agent": routes[task["capability"]]} for task in tasks]
    single_duration = sum(task["estimatedSeconds"] for task in tasks)
    single_cost = sum(task["estimatedCostUsd"] for task in tasks)
    overhead_seconds = max(0, len(tasks) - 1) * 10
    overhead_cost = max(0, len(tasks) - 1) * 0.02
    multi_duration = sum(max(by_id[item]["estimatedSeconds"] for item in wave) for wave in waves) + overhead_seconds if waves else single_duration
    multi_cost = single_cost + overhead_cost
    speedup = single_duration / multi_duration if multi_duration else 0
    cost_ratio = multi_cost / single_cost if single_cost else (1 if multi_cost == 0 else float("inf"))

    if reasons:
        decision = "hold"
        topology = "single-agent"
    else:
        distinct_specialists = len({row["agent"] for row in assignments}) > 1 and any(task["requiresSpecialist"] for task in tasks)
        beneficial = speedup >= policy["delegationPolicy"]["minimumPredictedSpeedupRatio"] or distinct_specialists
        affordable = cost_ratio <= policy["delegationPolicy"]["maximumPredictedCostIncreaseRatio"]
        if len(tasks) < policy["delegationPolicy"]["minimumTasks"] or not beneficial or not affordable:
            decision = "single-agent"
            topology = "single-agent"
            reasons = ["coordination-not-justified"]
        else:
            decision = "delegate"
            if len(waves) == 1:
                topology = "parallel"
            elif all(len(wave) == 1 for wave in waves):
                topology = "pipeline"
            else:
                topology = "hybrid"
            reasons = ["predicted-speedup" if speedup >= policy["delegationPolicy"]["minimumPredictedSpeedupRatio"] else "required-specialists"]

    handoffs = []
    if decision == "delegate":
        assigned = {row["taskId"]: row["agent"] for row in assignments}
        for task in tasks:
            handoffs.append({
                "taskId": task["id"],
                "fromAgent": coordinator,
                "toAgent": assigned[task["id"]],
                "dependencyIds": task["dependencies"],
                "contextPacketHash": task["contextPacketHash"],
                "ownedPaths": task["ownedPaths"],
                "expectedOutput": task["expectedOutput"],
                "budget": {"seconds": task["estimatedSeconds"], "costUsd": task["estimatedCostUsd"]},
                "idempotencyKey": task["sideEffectKey"],
            })
    return {
        "workloadId": workload_id,
        "decision": decision,
        "topology": topology,
        "reasons": reasons,
        "waves": waves if decision == "delegate" else [],
        "assignments": assignments if decision == "delegate" else [],
        "handoffs": handoffs,
        "prediction": {
            "singleAgentDurationSeconds": round(single_duration, 6),
            "multiAgentDurationSeconds": round(multi_duration, 6),
            "speedupRatio": round(speedup, 6),
            "singleAgentCostUsd": round(single_cost, 6),
            "multiAgentCostUsd": round(multi_cost, 6),
            "costIncreaseRatio": round(cost_ratio, 6) if cost_ratio != float("inf") else "infinite",
        },
        "preserveCompletedWork": policy["schedulingPolicy"]["completedWorkAfterInterruption"] == "preserve",
        "containFailedLane": policy["schedulingPolicy"]["failedLaneEffect"] == "contain",
    }


def exercise_scenarios(policy: dict[str, Any], scenarios: dict[str, Any], root: pathlib.Path = DEFAULT_ROOT) -> list[dict[str, Any]]:
    agents = load_json(root / AGENT_PATH, str(AGENT_PATH))
    return [{"id": row["id"], **plan_workload(policy, agents, row["workload"])} for row in scenarios["scenarios"]]


def source_hashes(root: pathlib.Path, policy: dict[str, Any]) -> dict[str, str]:
    return {raw: digest_bytes(repo_file(root, raw, f"receipt source {raw}").read_bytes()) for raw in policy["receipt"]["sourceFiles"]}


def _seal(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt["seal"] = digest_json(receipt)
    return receipt


def build_plan_receipt(root: pathlib.Path, workload_path: pathlib.Path) -> dict[str, Any]:
    policy, _ = validate(root)
    agents = load_json(root / AGENT_PATH, str(AGENT_PATH))
    raw, path = relative_file(root, workload_path, "workload")
    workload = load_json(path, "workload")
    return _seal({
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": "coordination-plan",
        "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policyId": policy["policyId"],
        "sourceHashes": source_hashes(root, policy),
        "workload": {"path": raw, "sha256": digest_bytes(path.read_bytes())},
        "plan": plan_workload(policy, agents, workload),
    })


def read_observations(root: pathlib.Path, path: pathlib.Path, expected_variant: str, policy: dict[str, Any]) -> tuple[str, pathlib.Path, dict[str, Any]]:
    raw, resolved = relative_file(root, path, f"{expected_variant} evidence")
    payload = load_json(resolved, f"{expected_variant} evidence")
    if set(payload) != {"schemaVersion", "workloadId", "variant", "runs"} or payload.get("schemaVersion") != 1 or payload.get("variant") != expected_variant:
        raise CoordinationError(f"{expected_variant} evidence fields, schema, or variant are invalid")
    text(payload["workloadId"], f"{expected_variant}.workloadId")
    runs = payload["runs"]
    if not isinstance(runs, list) or not runs:
        raise CoordinationError(f"{expected_variant}.runs must be nonempty")
    ids: set[str] = set()
    criteria: list[str] | None = None
    for index, run in enumerate(runs):
        if not isinstance(run, dict) or set(run) != RUN_KEYS:
            raise CoordinationError(f"{expected_variant} run {index} fields are invalid")
        run_id = text(run["id"], f"{expected_variant} run {index}.id")
        if run_id in ids:
            raise CoordinationError(f"{expected_variant} run ids must be unique")
        ids.add(run_id)
        if not isinstance(run["success"], bool):
            raise CoordinationError(f"{run_id}.success must be boolean")
        required = string_list(run["requiredCriteria"], f"{run_id}.requiredCriteria")
        passed = string_list(run["passedCriteria"], f"{run_id}.passedCriteria", allow_empty=True)
        if criteria is None:
            criteria = sorted(required)
        elif sorted(required) != criteria:
            raise CoordinationError(f"{expected_variant} runs must use one criteria definition")
        if not set(passed) <= set(required):
            raise CoordinationError(f"{run_id}.passedCriteria contains undeclared criteria")
        number(run["durationSeconds"], f"{run_id}.durationSeconds", minimum=0.001)
        number(run["costUsd"], f"{run_id}.costUsd")
        for key in ("toolCalls", "humanInterventions", "duplicateWork", "pathConflicts", "deadlocks", "staleHandoffs"):
            if not isinstance(run[key], int) or isinstance(run[key], bool) or run[key] < 0:
                raise CoordinationError(f"{run_id}.{key} must be a nonnegative integer")
    return raw, resolved, payload


def aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    runs = payload["runs"]
    required = sum(len(run["requiredCriteria"]) for run in runs)
    passed = sum(len(run["passedCriteria"]) for run in runs)
    return {
        "runs": len(runs),
        "criteriaHash": digest_json(sorted(runs[0]["requiredCriteria"])),
        "completionRate": round(sum(1 for run in runs if run["success"]) / len(runs), 6),
        "qualityPassRate": round(passed / required, 6) if required else 0,
        "medianDurationSeconds": round(statistics.median(run["durationSeconds"] for run in runs), 6),
        "medianCostUsd": round(statistics.median(run["costUsd"] for run in runs), 6),
        "medianToolCalls": round(statistics.median(run["toolCalls"] for run in runs), 6),
        "humanInterventions": sum(run["humanInterventions"] for run in runs),
        "coordinationFailures": {
            key: sum(run[key] for run in runs)
            for key in ("duplicateWork", "pathConflicts", "deadlocks", "staleHandoffs")
        },
    }


def comparison_decision(policy: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    rules = policy["comparisonPolicy"]
    if baseline["runs"] < rules["minimumRunsPerVariant"] or candidate["runs"] < rules["minimumRunsPerVariant"]:
        return {"decision": "hold", "reasons": ["insufficient-evidence"]}
    if baseline["criteriaHash"] != candidate["criteriaHash"]:
        return {"decision": "hold", "reasons": ["criteria-definition-mismatch"]}
    if baseline["completionRate"] < rules["minimumCompletionRate"] or baseline["qualityPassRate"] < rules["minimumQualityPassRate"]:
        return {"decision": "hold", "reasons": ["baseline-unhealthy"]}
    reasons = []
    if (
        candidate["completionRate"] < rules["minimumCompletionRate"]
        or candidate["qualityPassRate"] < rules["minimumQualityPassRate"]
        or candidate["qualityPassRate"] < baseline["qualityPassRate"]
    ):
        reasons.append("quality-or-completion-regression")
    if any(candidate["coordinationFailures"].values()):
        reasons.append("coordination-failure")
    cost_ratio = candidate["medianCostUsd"] / baseline["medianCostUsd"] if baseline["medianCostUsd"] else (1 if candidate["medianCostUsd"] == 0 else float("inf"))
    tool_ratio = candidate["medianToolCalls"] / baseline["medianToolCalls"] if baseline["medianToolCalls"] else (1 if candidate["medianToolCalls"] == 0 else float("inf"))
    if cost_ratio > rules["maximumCostIncreaseRatio"]:
        reasons.append("cost-regression")
    if tool_ratio > rules["maximumToolCallIncreaseRatio"]:
        reasons.append("tool-call-regression")
    if candidate["humanInterventions"] - baseline["humanInterventions"] > rules["maximumHumanInterventionIncrease"]:
        reasons.append("human-intervention-regression")
    duration_reduction = 1 - (candidate["medianDurationSeconds"] / baseline["medianDurationSeconds"])
    quality_increase = candidate["qualityPassRate"] - baseline["qualityPassRate"]
    if duration_reduction < rules["minimumDurationReduction"] and quality_increase < rules["minimumQualityPassRateIncrease"]:
        reasons.append("no-material-benefit")
    return {
        "decision": "keep-single-agent" if reasons else "adopt-multi-agent",
        "reasons": sorted(reasons),
        "durationReduction": round(duration_reduction, 6),
        "qualityPassRateIncrease": round(quality_increase, 6),
        "costIncreaseRatio": round(cost_ratio, 6) if cost_ratio != float("inf") else "infinite",
        "toolCallIncreaseRatio": round(tool_ratio, 6) if tool_ratio != float("inf") else "infinite",
    }


def build_comparison_receipt(root: pathlib.Path, baseline_path: pathlib.Path, candidate_path: pathlib.Path) -> dict[str, Any]:
    policy, _ = validate(root)
    baseline_raw, baseline_file, baseline_payload = read_observations(root, baseline_path, "single-agent", policy)
    candidate_raw, candidate_file, candidate_payload = read_observations(root, candidate_path, "multi-agent", policy)
    if baseline_payload["workloadId"] != candidate_payload["workloadId"]:
        raise CoordinationError("baseline and candidate must describe the same workloadId")
    baseline = aggregate(baseline_payload)
    candidate = aggregate(candidate_payload)
    return _seal({
        "schemaVersion": policy["receiptSchemaVersion"],
        "kind": "coordination-comparison",
        "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "policyId": policy["policyId"],
        "workloadId": baseline_payload["workloadId"],
        "sourceHashes": source_hashes(root, policy),
        "evidence": {
            "single-agent": {"path": baseline_raw, "sha256": digest_bytes(baseline_file.read_bytes())},
            "multi-agent": {"path": candidate_raw, "sha256": digest_bytes(candidate_file.read_bytes())},
        },
        "singleAgent": baseline,
        "multiAgent": candidate,
        "decision": comparison_decision(policy, baseline, candidate),
    })


def verify_receipt(root: pathlib.Path, receipt: dict[str, Any]) -> None:
    policy, _ = validate(root)
    if receipt.get("schemaVersion") != policy["receiptSchemaVersion"] or receipt.get("policyId") != policy["policyId"]:
        raise CoordinationError("receipt schema or policy id is invalid")
    seal = receipt.get("seal")
    unsigned = dict(receipt)
    unsigned.pop("seal", None)
    if not isinstance(seal, str) or seal != digest_json(unsigned):
        raise CoordinationError("receipt is tampered")
    if receipt.get("sourceHashes") != source_hashes(root, policy):
        raise CoordinationError("receipt policy source-drifted")
    kind = receipt.get("kind")
    if kind == "coordination-plan":
        evidence = receipt.get("workload", {})
        raw, path = relative_file(root, pathlib.Path(str(evidence.get("path", ""))), "workload")
        if evidence != {"path": raw, "sha256": digest_bytes(path.read_bytes())}:
            raise CoordinationError("receipt workload source-drifted")
        agents = load_json(root / AGENT_PATH, str(AGENT_PATH))
        if receipt.get("plan") != plan_workload(policy, agents, load_json(path, "workload")):
            raise CoordinationError("receipt plan is stale")
    elif kind == "coordination-comparison":
        evidence = receipt.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != {"single-agent", "multi-agent"}:
            raise CoordinationError("receipt comparison evidence is invalid")
        payloads = {}
        for variant in ("single-agent", "multi-agent"):
            record = evidence[variant]
            raw, path = relative_file(root, pathlib.Path(str(record.get("path", ""))), f"{variant} evidence")
            if record != {"path": raw, "sha256": digest_bytes(path.read_bytes())}:
                raise CoordinationError(f"receipt {variant} source-drifted")
            _, _, payloads[variant] = read_observations(root, path, variant, policy)
        single = aggregate(payloads["single-agent"])
        multi = aggregate(payloads["multi-agent"])
        if receipt.get("singleAgent") != single or receipt.get("multiAgent") != multi or receipt.get("decision") != comparison_decision(policy, single, multi):
            raise CoordinationError("receipt comparison is stale")
    else:
        raise CoordinationError("receipt kind is invalid")


def write_receipt(path: pathlib.Path, receipt: dict[str, Any], root: pathlib.Path, policy: dict[str, Any]) -> None:
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.absolute().relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise CoordinationError("receipt output must stay inside the repository") from exc
    cursor = root.resolve()
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise CoordinationError("receipt output parent must not be a symlink")
    if candidate.is_symlink():
        raise CoordinationError("receipt output must be a regular non-symlink file")
    sealed = {repo_file(root, raw, f"sealed source {raw}").resolve() for raw in policy["receipt"]["sourceFiles"]}
    if candidate.resolve() in sealed:
        raise CoordinationError("receipt output cannot replace a sealed source")
    if candidate.exists() and candidate.stat().st_size:
        raise CoordinationError("receipt output must not overwrite a nonempty file")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        candidate.parent.resolve(strict=True).relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise CoordinationError("receipt output parent must stay inside the repository") from exc
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
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    plan_parser.add_argument("--workload", type=pathlib.Path, required=True)
    plan_parser.add_argument("--output", type=pathlib.Path, required=True)
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
        policy, scenarios = validate(root)
        if args.command == "validate":
            print(f"validated: {policy['policyId']} ({len(scenarios['scenarios'])} scenarios)")
        elif args.command == "exercise":
            results = exercise_scenarios(policy, scenarios, root)
            print(json.dumps(results, indent=2, sort_keys=True))
        elif args.command == "plan":
            receipt = build_plan_receipt(root, args.workload)
            write_receipt(args.output, receipt, root, policy)
            print(f"{receipt['plan']['decision']}: {receipt['plan']['topology']}")
        elif args.command == "compare":
            receipt = build_comparison_receipt(root, args.baseline, args.candidate)
            write_receipt(args.output, receipt, root, policy)
            print(f"{receipt['decision']['decision']}: {','.join(receipt['decision']['reasons']) or 'measured-benefit'}")
        elif args.command == "verify":
            _, receipt_path = relative_file(root, args.receipt, "receipt")
            receipt = load_json(receipt_path, "receipt")
            verify_receipt(root, receipt)
            decision = receipt["plan"]["decision"] if receipt["kind"] == "coordination-plan" else receipt["decision"]["decision"]
            print(f"verified: {decision}")
    except CoordinationError as exc:
        print(f"coordination error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
