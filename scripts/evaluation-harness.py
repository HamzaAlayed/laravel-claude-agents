#!/usr/bin/env python3
"""Validate eval contracts, seal source-bound receipts, and detect regressions."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
from typing import Any


class EvaluationError(ValueError):
    """A closed failure caused by invalid evaluation evidence or configuration."""


CASE_KEYS = {
    "id", "suite", "prompt", "description", "minimumChecks",
    "requiredOutcomes", "forbiddenOutcomes", "comparisonMetrics",
}
MANIFEST_KEYS = {
    "schemaVersion", "receiptSchemaVersion", "caseRegistry", "budgetBaseline",
    "resultsDirectory", "hashAlgorithm", "verdictPolicy", "requiredMetrics",
    "sourceArtifacts", "excludedReceiptData", "comparisonPolicy",
}
OUTCOME_KEYS = {"id", "statement"}
METRICS = {"durationSeconds", "tokens", "billedUsd", "toolCalls"}
ARTIFACT_NAMES = ("checks", "cost", "status", "diff")
CHECK_RE = re.compile(r"^\s+(PASS|FAIL)\s+(.+)$")
RECEIPT_KEYS = {
    "schemaVersion", "kind", "generatedAt", "runId", "case", "contract",
    "execution", "deterministic", "metrics", "budget", "judge", "artifacts",
    "evidenceComplete", "verdict", "receiptHash",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical(value))


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read JSON {path}: {exc}") from exc


def safe_path(root: pathlib.Path, raw: str, *, must_exist: bool = True) -> pathlib.Path:
    if not isinstance(raw, str):
        raise EvaluationError("artifact path must be a string")
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or not raw or ".." in relative.parts:
        raise EvaluationError(f"artifact path must be project-relative: {raw!r}")
    path = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvaluationError(f"artifact path must not contain a symlink: {raw}")
    if must_exist and (not path.is_file() or path.resolve().parent != path.parent.resolve()):
        raise EvaluationError(f"artifact must be a regular non-symlink file: {raw}")
    try:
        path.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise EvaluationError(f"artifact escapes project root: {raw}") from exc
    return path


def relative_path(root: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise EvaluationError(f"path is outside project root: {path}") from exc


def _positive_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value > 0


def read_contract(root: pathlib.Path) -> tuple[dict, dict, dict, dict[str, dict]]:
    manifest_path = root / "config" / "evaluation-harness.json"
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise EvaluationError("evaluation manifest schemaVersion must be 1")
    if set(manifest) != MANIFEST_KEYS:
        raise EvaluationError(f"evaluation manifest must declare exactly {sorted(MANIFEST_KEYS)}")
    if manifest.get("receiptSchemaVersion") != 1 or manifest.get("hashAlgorithm") != "sha256":
        raise EvaluationError("evaluation manifest requires receipt schema 1 and sha256")
    if manifest.get("verdictPolicy") != {
        "deterministicChecks": "authoritative",
        "budgetCeilings": "authoritative",
        "executionStatus": "authoritative",
        "rubricJudge": "advisory-only",
    }:
        raise EvaluationError("verdictPolicy must keep deterministic evidence authoritative and the judge advisory")
    required_metrics = manifest.get("requiredMetrics")
    if not isinstance(required_metrics, list) or set(required_metrics) != METRICS or len(required_metrics) != len(METRICS):
        raise EvaluationError("requiredMetrics must declare duration, tokens, billed USD, and tool calls")
    if manifest.get("sourceArtifacts") != list(ARTIFACT_NAMES):
        raise EvaluationError("sourceArtifacts must declare checks, cost, status, and diff in order")
    excluded_values = manifest.get("excludedReceiptData")
    if not isinstance(excluded_values, list):
        raise EvaluationError("excludedReceiptData must be a list")
    excluded = set(excluded_values)
    if excluded != {"rawTranscript", "assistantText", "toolInputs", "secrets"} or len(excluded_values) != len(excluded):
        raise EvaluationError("excludedReceiptData must prevent raw or secret-bearing evidence in receipts")
    results_value = manifest.get("resultsDirectory")
    if not isinstance(results_value, str):
        raise EvaluationError("resultsDirectory must be a string")
    results_directory = pathlib.PurePosixPath(results_value)
    if results_directory.is_absolute() or not results_directory.parts or ".." in results_directory.parts:
        raise EvaluationError("resultsDirectory must stay inside the project")

    registry_path = safe_path(root, manifest.get("caseRegistry", ""))
    baseline_path = safe_path(root, manifest.get("budgetBaseline", ""))
    registry = load_json(registry_path)
    baseline = load_json(baseline_path)
    if not isinstance(registry, dict) or registry.get("schemaVersion") != 1:
        raise EvaluationError("case registry schemaVersion must be 1")
    raw_cases = registry.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvaluationError("case registry must contain a nonempty cases list")

    cases: dict[str, dict] = {}
    for index, case in enumerate(raw_cases):
        if not isinstance(case, dict) or set(case) != CASE_KEYS:
            raise EvaluationError(f"case {index} must declare exactly {sorted(CASE_KEYS)}")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id):
            raise EvaluationError(f"case {index} has an invalid id")
        if case_id in cases:
            raise EvaluationError(f"duplicate case id: {case_id}")
        if case.get("suite") not in {"default", "opt-in"}:
            raise EvaluationError(f"{case_id}: suite must be default or opt-in")
        for key in ("prompt", "description"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise EvaluationError(f"{case_id}: {key} must be nonempty")
        if not isinstance(case.get("minimumChecks"), int) or case["minimumChecks"] <= 0:
            raise EvaluationError(f"{case_id}: minimumChecks must be a positive integer")
        outcome_ids: set[str] = set()
        for key in ("requiredOutcomes", "forbiddenOutcomes"):
            values = case.get(key)
            if not isinstance(values, list) or not values:
                raise EvaluationError(f"{case_id}: {key} must be nonempty")
            for outcome in values:
                if not isinstance(outcome, dict) or set(outcome) != OUTCOME_KEYS:
                    raise EvaluationError(f"{case_id}: malformed {key} entry")
                if not all(isinstance(outcome.get(field), str) and outcome[field].strip() for field in OUTCOME_KEYS):
                    raise EvaluationError(f"{case_id}: blank {key} entry")
                if outcome["id"] in outcome_ids:
                    raise EvaluationError(f"{case_id}: duplicate outcome id {outcome['id']}")
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", outcome["id"]):
                    raise EvaluationError(f"{case_id}: invalid outcome id {outcome['id']}")
                outcome_ids.add(outcome["id"])
        metrics = case.get("comparisonMetrics")
        if not isinstance(metrics, list) or not metrics or set(metrics) - METRICS or len(metrics) != len(set(metrics)):
            raise EvaluationError(f"{case_id}: comparisonMetrics is invalid")
        cases[case_id] = case

    baseline_cases = baseline.get("cases") if isinstance(baseline, dict) else None
    if not isinstance(baseline_cases, dict) or set(baseline_cases) != set(cases):
        raise EvaluationError("budget baseline cases must exactly match the case registry")
    for case_id, budget in baseline_cases.items():
        if not isinstance(budget, dict) or not all(_positive_number(budget.get(key)) for key in ("max_seconds", "max_tokens", "max_usd")):
            raise EvaluationError(f"{case_id}: budget must include positive max_seconds, max_tokens, and max_usd")

    policy = manifest.get("comparisonPolicy")
    if not isinstance(policy, dict) or any(policy.get(key) is not True for key in (
        "sameCaseDefinitionRequired", "baselineMustPass", "candidateMustPass", "qualityMayNotDecrease"
    )):
        raise EvaluationError("comparisonPolicy must fail closed on identity, verdict, and quality")
    thresholds = policy.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != METRICS:
        raise EvaluationError("comparisonPolicy thresholds must cover every required metric")
    for metric, threshold in thresholds.items():
        if not isinstance(threshold, dict) or set(threshold) != {"ratio", "minimumDelta"}:
            raise EvaluationError(f"comparison threshold is malformed: {metric}")
        if not _positive_number(threshold["ratio"]) or threshold["ratio"] <= 1:
            raise EvaluationError(f"comparison ratio must be greater than one: {metric}")
        if not _positive_number(threshold["minimumDelta"]):
            raise EvaluationError(f"comparison minimumDelta must be positive: {metric}")
    return manifest, registry, baseline, cases


def validate_shell_registry(root: pathlib.Path, cases: dict[str, dict]) -> None:
    shell = (root / "tests" / "eval" / "run-evals.sh").read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    for variable, suite in (("ALL_CASES", "default"), ("OPT_IN_CASES", "opt-in")):
        match = re.search(rf"^{variable}=\(([^)]*)\)$", shell, re.MULTILINE)
        if not match:
            raise EvaluationError(f"run-evals.sh is missing {variable}")
        found[suite] = match.group(1).split()
    for suite in ("default", "opt-in"):
        registered = [case_id for case_id, case in cases.items() if case["suite"] == suite]
        if found[suite] != registered:
            raise EvaluationError(f"run-evals.sh {suite} cases differ from registry: shell={found[suite]} registry={registered}")
    for case_id in cases:
        function = case_id.replace("-", "_")
        if not re.search(rf"^checks_{re.escape(function)}\(\)", shell, re.MULTILINE):
            raise EvaluationError(f"run-evals.sh has no checks function for {case_id}")


def validate(root: pathlib.Path) -> dict:
    manifest, registry, baseline, cases = read_contract(root)
    validate_shell_registry(root, cases)
    return {
        "status": "valid",
        "cases": len(cases),
        "defaultCases": sum(case["suite"] == "default" for case in cases.values()),
        "optInCases": sum(case["suite"] == "opt-in" for case in cases.values()),
        "manifestHash": digest_json(manifest),
        "registryHash": digest_json(registry),
        "baselineHash": digest_json(baseline),
    }


def read_checks(path: pathlib.Path) -> list[dict]:
    checks = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = CHECK_RE.match(line)
        if match:
            checks.append({"index": len(checks) + 1, "status": match.group(1).lower(), "description": match.group(2)})
    return checks


def artifact_record(root: pathlib.Path, name: str, raw: str) -> dict:
    path = safe_path(root, raw, must_exist=False)
    exists = path.is_file() and not path.is_symlink()
    return {
        "name": name,
        "path": relative_path(root, path),
        "exists": exists,
        "sha256": digest_bytes(path.read_bytes()) if exists else None,
    }


def create_receipt(
    root: pathlib.Path,
    *,
    case_id: str,
    run_id: str,
    duration: int,
    exit_code: int,
    timed_out: bool,
    ignore_duration: bool,
    checks_path: str,
    cost_path: str,
    status_path: str,
    diff_path: str,
    judge_path: str | None,
) -> dict:
    manifest, registry, baseline, cases = read_contract(root)
    validate_shell_registry(root, cases)
    if case_id not in cases:
        raise EvaluationError(f"unknown evaluation case: {case_id}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", run_id):
        raise EvaluationError("run id contains unsupported characters")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
        raise EvaluationError("duration must be nonnegative")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise EvaluationError("exit code must be an integer")
    if not isinstance(timed_out, bool) or not isinstance(ignore_duration, bool):
        raise EvaluationError("timeout and duration-policy flags must be boolean")

    raw_artifacts = {
        "checks": checks_path,
        "cost": cost_path,
        "status": status_path,
        "diff": diff_path,
    }
    artifacts = [artifact_record(root, name, raw_artifacts[name]) for name in ARTIFACT_NAMES]
    artifact_map = {item["name"]: item for item in artifacts}
    checks = read_checks(safe_path(root, checks_path)) if artifact_map["checks"]["exists"] else []
    check_passes = sum(item["status"] == "pass" for item in checks)
    check_failures = len(checks) - check_passes
    case = cases[case_id]
    minimum_met = len(checks) >= case["minimumChecks"]

    cost: dict = {}
    if artifact_map["cost"]["exists"]:
        loaded = load_json(safe_path(root, cost_path))
        cost = loaded if isinstance(loaded, dict) else {}
    billed_usd = (cost.get("billed") or {}).get("usd")
    tokens = ((cost.get("attributed") or {}).get("total") or {}).get("tokens")
    tools = cost.get("tools") or {}
    tool_calls = sum(value for value in tools.values() if isinstance(value, int) and not isinstance(value, bool)) if isinstance(tools, dict) else None
    budget = baseline["cases"][case_id]
    breaches = []
    if not ignore_duration and duration > budget["max_seconds"]:
        breaches.append({"metric": "durationSeconds", "actual": duration, "limit": budget["max_seconds"]})
    if not _positive_number(tokens) or tokens > budget["max_tokens"]:
        breaches.append({"metric": "tokens", "actual": tokens, "limit": budget["max_tokens"]})
    if not _positive_number(billed_usd) or billed_usd > budget["max_usd"]:
        breaches.append({"metric": "billedUsd", "actual": billed_usd, "limit": budget["max_usd"]})
    if tool_calls is None:
        breaches.append({"metric": "toolCalls", "actual": None, "limit": None})

    judge = {"present": False, "role": "advisory-only"}
    if judge_path:
        judge_artifact = artifact_record(root, "judge", judge_path)
        if judge_artifact["exists"]:
            payload = load_json(safe_path(root, judge_path))
            judge = {
                "present": True,
                "role": "advisory-only",
                "verdict": payload.get("verdict") if isinstance(payload, dict) else None,
                "score": payload.get("score") if isinstance(payload, dict) else None,
                "artifact": judge_artifact,
            }

    evidence_complete = all(item["exists"] for item in artifacts)
    deterministic_pass = bool(checks and check_failures == 0 and minimum_met)
    execution_pass = exit_code == 0 and not timed_out
    verdict = "pass" if deterministic_pass and not breaches and execution_pass and evidence_complete else "fail"
    receipt = {
        "schemaVersion": manifest["receiptSchemaVersion"],
        "kind": "agent-evaluation-receipt",
        "generatedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "runId": run_id,
        "case": {
            "id": case_id,
            "suite": case["suite"],
            "definitionHash": digest_json(case),
        },
        "contract": {
            "manifestHash": digest_json(manifest),
            "registryHash": digest_json(registry),
            "budgetBaselineHash": digest_json(baseline),
        },
        "execution": {
            "exitCode": exit_code,
            "timedOut": timed_out,
            "verdict": "pass" if execution_pass else "fail",
        },
        "deterministic": {
            "authority": "authoritative",
            "minimumChecks": case["minimumChecks"],
            "minimumMet": minimum_met,
            "passCount": check_passes,
            "failCount": check_failures,
            "checks": checks,
            "verdict": "pass" if deterministic_pass else "fail",
        },
        "metrics": {
            "durationSeconds": duration,
            "tokens": tokens,
            "billedUsd": billed_usd,
            "toolCalls": tool_calls,
        },
        "budget": {
            "authority": "authoritative",
            "durationApplied": not ignore_duration,
            "limits": {
                "durationSeconds": budget["max_seconds"],
                "tokens": budget["max_tokens"],
                "billedUsd": budget["max_usd"],
            },
            "breaches": breaches,
            "verdict": "pass" if not breaches else "fail",
        },
        "judge": judge,
        "artifacts": artifacts,
        "evidenceComplete": evidence_complete,
        "verdict": verdict,
    }
    receipt["receiptHash"] = digest_json(receipt)
    return receipt


def verify_receipt(root: pathlib.Path, receipt: dict, *, check_sources: bool) -> dict:
    if not isinstance(receipt, dict) or receipt.get("schemaVersion") != 1 or receipt.get("kind") != "agent-evaluation-receipt":
        raise EvaluationError("unsupported evaluation receipt")
    if set(receipt) != RECEIPT_KEYS:
        raise EvaluationError("evaluation receipt fields do not match schema 1")
    expected_nested = {
        "case": {"id", "suite", "definitionHash"},
        "contract": {"manifestHash", "registryHash", "budgetBaselineHash"},
        "execution": {"exitCode", "timedOut", "verdict"},
        "deterministic": {"authority", "minimumChecks", "minimumMet", "passCount", "failCount", "checks", "verdict"},
        "metrics": METRICS,
        "budget": {"authority", "durationApplied", "limits", "breaches", "verdict"},
    }
    for field, keys in expected_nested.items():
        value = receipt.get(field)
        if not isinstance(value, dict) or set(value) != keys:
            raise EvaluationError(f"receipt {field} fields do not match schema 1")
    checks = receipt["deterministic"].get("checks")
    if not isinstance(checks, list) or any(
        not isinstance(item, dict) or set(item) != {"index", "status", "description"}
        for item in checks
    ):
        raise EvaluationError("receipt deterministic checks do not match schema 1")
    if set(receipt["budget"].get("limits") or {}) != {"durationSeconds", "tokens", "billedUsd"}:
        raise EvaluationError("receipt budget limits do not match schema 1")
    breaches = receipt["budget"].get("breaches")
    if not isinstance(breaches, list) or any(
        not isinstance(item, dict) or set(item) != {"metric", "actual", "limit"}
        for item in breaches
    ):
        raise EvaluationError("receipt budget breaches do not match schema 1")
    judge = receipt.get("judge")
    judge_keys = {"present", "role"} if isinstance(judge, dict) and judge.get("present") is False else {"present", "role", "verdict", "score", "artifact"}
    if not isinstance(judge, dict) or set(judge) != judge_keys:
        raise EvaluationError("receipt judge fields do not match schema 1")
    if judge.get("present") and (
        not isinstance(judge.get("artifact"), dict)
        or set(judge["artifact"]) != {"name", "path", "exists", "sha256"}
    ):
        raise EvaluationError("receipt judge artifact does not match schema 1")
    supplied_hash = receipt.get("receiptHash")
    unsigned = dict(receipt)
    unsigned.pop("receiptHash", None)
    if not isinstance(supplied_hash, str) or supplied_hash != digest_json(unsigned):
        raise EvaluationError("receiptHash does not match receipt content")
    manifest, registry, baseline, cases = read_contract(root)
    case_id = (receipt.get("case") or {}).get("id")
    if case_id not in cases:
        raise EvaluationError("receipt references an unknown case")
    expected_contract = {
        "manifestHash": digest_json(manifest),
        "registryHash": digest_json(registry),
        "budgetBaselineHash": digest_json(baseline),
    }
    if receipt.get("contract") != expected_contract:
        raise EvaluationError("receipt contract hashes are stale")
    if receipt["case"].get("definitionHash") != digest_json(cases[case_id]):
        raise EvaluationError("receipt case definition is stale")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list) or [item.get("name") for item in artifacts if isinstance(item, dict)] != list(ARTIFACT_NAMES):
        raise EvaluationError("receipt artifacts are incomplete or out of order")
    if any(set(item) != {"name", "path", "exists", "sha256"} for item in artifacts):
        raise EvaluationError("receipt artifact fields do not match schema 1")
    if check_sources:
        for artifact in artifacts:
            path = safe_path(root, artifact.get("path", ""), must_exist=artifact.get("exists") is True)
            if artifact.get("exists") is True and digest_bytes(path.read_bytes()) != artifact.get("sha256"):
                raise EvaluationError(f"source artifact drifted: {artifact.get('name')}")
            if artifact.get("exists") is False and path.exists():
                raise EvaluationError(f"previously missing artifact now exists: {artifact.get('name')}")
        judge = receipt.get("judge") or {}
        if judge.get("present"):
            artifact = judge.get("artifact") or {}
            path = safe_path(root, artifact.get("path", ""))
            if digest_bytes(path.read_bytes()) != artifact.get("sha256"):
                raise EvaluationError("judge source artifact drifted")
        artifact_map = {item["name"]: item["path"] for item in artifacts}
        judge_path = None
        if (receipt.get("judge") or {}).get("present"):
            judge_path = receipt["judge"]["artifact"]["path"]
        rebuilt = create_receipt(
            root,
            case_id=case_id,
            run_id=receipt.get("runId", ""),
            duration=(receipt.get("metrics") or {}).get("durationSeconds"),
            exit_code=(receipt.get("execution") or {}).get("exitCode"),
            timed_out=(receipt.get("execution") or {}).get("timedOut"),
            ignore_duration=not (receipt.get("budget") or {}).get("durationApplied"),
            checks_path=artifact_map["checks"],
            cost_path=artifact_map["cost"],
            status_path=artifact_map["status"],
            diff_path=artifact_map["diff"],
            judge_path=judge_path,
        )
        semantic_fields = {
            "case", "contract", "execution", "deterministic", "metrics", "budget",
            "judge", "artifacts", "evidenceComplete", "verdict",
        }
        for field in semantic_fields:
            if receipt.get(field) != rebuilt.get(field):
                raise EvaluationError(f"receipt semantics do not match source evidence: {field}")
    return {"status": "valid", "verdict": receipt.get("verdict"), "case": case_id, "sourcesChecked": check_sources}


def compare_receipts(root: pathlib.Path, baseline_receipt: dict, candidate_receipt: dict) -> dict:
    verify_receipt(root, baseline_receipt, check_sources=True)
    verify_receipt(root, candidate_receipt, check_sources=True)
    manifest, _, _, cases = read_contract(root)
    baseline_case = baseline_receipt["case"]
    candidate_case = candidate_receipt["case"]
    if baseline_case["id"] != candidate_case["id"] or baseline_case["definitionHash"] != candidate_case["definitionHash"]:
        raise EvaluationError("receipts do not use the same case definition")
    regressions = []
    if baseline_receipt.get("verdict") != "pass":
        raise EvaluationError("baseline receipt must pass")
    if candidate_receipt.get("verdict") != "pass":
        regressions.append({"type": "verdict", "baseline": "pass", "candidate": candidate_receipt.get("verdict")})
    before_quality = (baseline_receipt.get("deterministic") or {}).get("passCount")
    after_quality = (candidate_receipt.get("deterministic") or {}).get("passCount")
    if not isinstance(after_quality, int) or not isinstance(before_quality, int) or after_quality < before_quality:
        regressions.append({"type": "quality", "baseline": before_quality, "candidate": after_quality})
    thresholds = manifest["comparisonPolicy"]["thresholds"]
    for metric in cases[baseline_case["id"]]["comparisonMetrics"]:
        before = (baseline_receipt.get("metrics") or {}).get(metric)
        after = (candidate_receipt.get("metrics") or {}).get(metric)
        if not _positive_number(before) or not _positive_number(after):
            regressions.append({"type": "missing-metric", "metric": metric, "baseline": before, "candidate": after})
            continue
        threshold = thresholds[metric]
        if after > before * threshold["ratio"] and after - before > threshold["minimumDelta"]:
            regressions.append({
                "type": "metric",
                "metric": metric,
                "baseline": before,
                "candidate": after,
                "ratio": round(after / before, 4),
                "allowedRatio": threshold["ratio"],
                "minimumDelta": threshold["minimumDelta"],
            })
    return {
        "status": "regressed" if regressions else "pass",
        "case": baseline_case["id"],
        "baselineRunId": baseline_receipt.get("runId"),
        "candidateRunId": candidate_receipt.get("runId"),
        "regressions": regressions,
    }


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__)
    sub = top.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    case_parser = sub.add_parser("case")
    case_parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    case_parser.add_argument("--id", required=True)
    case_parser.add_argument("--field", choices=("prompt", "description"), required=True)
    receipt = sub.add_parser("receipt")
    receipt.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    receipt.add_argument("--case", required=True)
    receipt.add_argument("--run-id", required=True)
    receipt.add_argument("--duration", required=True, type=int)
    receipt.add_argument("--exit-code", required=True, type=int)
    receipt.add_argument("--timed-out", action="store_true")
    receipt.add_argument("--ignore-duration", action="store_true")
    for name in ARTIFACT_NAMES:
        receipt.add_argument(f"--{name}", required=True)
    receipt.add_argument("--judge")
    receipt.add_argument("--output", required=True, type=pathlib.Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    verify.add_argument("--receipt", required=True, type=pathlib.Path)
    verify.add_argument("--check-sources", action="store_true")
    compare = sub.add_parser("compare")
    compare.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    compare.add_argument("--baseline", required=True, type=pathlib.Path)
    compare.add_argument("--candidate", required=True, type=pathlib.Path)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            print(json.dumps(validate(root), indent=2))
            return 0
        if args.command == "case":
            _, _, _, cases = read_contract(root)
            if args.id not in cases:
                raise EvaluationError(f"unknown evaluation case: {args.id}")
            print(cases[args.id][args.field])
            return 0
        if args.command == "receipt":
            receipt = create_receipt(
                root,
                case_id=args.case,
                run_id=args.run_id,
                duration=args.duration,
                exit_code=args.exit_code,
                timed_out=args.timed_out,
                ignore_duration=args.ignore_duration,
                checks_path=args.checks,
                cost_path=args.cost,
                status_path=args.status,
                diff_path=args.diff,
                judge_path=args.judge,
            )
            output = args.output if args.output.is_absolute() else root / args.output
            safe_path(root, relative_path(root, output), must_exist=False)
            write_json(output, receipt)
            print(receipt["verdict"].upper())
            return 0
        if args.command == "verify":
            print(json.dumps(verify_receipt(root, load_json(args.receipt), check_sources=args.check_sources), indent=2))
            return 0
        if args.command == "compare":
            result = compare_receipts(root, load_json(args.baseline), load_json(args.candidate))
            print(json.dumps(result, indent=2))
            return 1 if result["regressions"] else 0
    except EvaluationError as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
