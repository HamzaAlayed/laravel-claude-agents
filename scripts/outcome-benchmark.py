#!/usr/bin/env python3
"""Compare read-only Laravel benchmark captures and verify durable receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import sys
import tempfile
from datetime import datetime, timezone
from statistics import median
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = pathlib.PurePosixPath("config/benchmark-harness.json")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
CAPTURE_FIELDS = {"schemaVersion", "scenario", "runs"}
SCENARIO_FIELDS = {
    "id",
    "version",
    "kind",
    "target",
    "objective",
    "datasetHash",
    "datasetRows",
    "runtimeHash",
    "databaseMode",
    "warmupRuns",
}
RECEIPT_FIELDS = {
    "schemaVersion",
    "createdAt",
    "verdict",
    "scenario",
    "thresholds",
    "baseline",
    "candidate",
    "comparison",
    "failures",
    "sources",
    "receiptHash",
}


class BenchmarkError(ValueError):
    """A capture or receipt is unsafe, incomplete, or internally inconsistent."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkError(f"{label} must contain a JSON object")
    return payload


def _text(value: Any, label: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(char in value for char in ("\x00", "\n", "\r"))
    ):
        raise BenchmarkError(f"{label} must be a nonempty single-line string")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BenchmarkError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value <= minimum:
        raise BenchmarkError(f"{label} must be finite and > {minimum}")
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise BenchmarkError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _safe_input(root: pathlib.Path, raw: str, label: str) -> pathlib.Path:
    root = root.resolve()
    pure = pathlib.PurePosixPath(_text(raw, label))
    if pure.is_absolute() or ".." in pure.parts:
        raise BenchmarkError(f"{label} must stay inside the project")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise BenchmarkError(f"{label} is missing or escapes the project") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise BenchmarkError(f"{label} must be a regular non-symlink file")
    return resolved


def _safe_artifact_input(
    root: pathlib.Path, raw: str, label: str, artifact_dir: str
) -> pathlib.Path:
    pure = pathlib.PurePosixPath(_text(raw, label))
    base = pathlib.PurePosixPath(artifact_dir)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".json"
        or pure.parts[: len(base.parts)] != base.parts
    ):
        raise BenchmarkError(
            f"{label} must be a project-relative JSON file under {artifact_dir}"
        )
    return _safe_input(root, raw, label)


def _safe_output(root: pathlib.Path, raw: str, artifact_dir: str) -> pathlib.Path:
    root = root.resolve()
    pure = pathlib.PurePosixPath(_text(raw, "output path"))
    base = pathlib.PurePosixPath(artifact_dir)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or pure.suffix != ".json"
        or pure.parts[: len(base.parts)] != base.parts
    ):
        raise BenchmarkError(
            f"output path must be a project-relative JSON file under {artifact_dir}"
        )
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise BenchmarkError("output path cannot traverse a symlink")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise BenchmarkError("output path escapes the project") from exc
    if candidate.is_symlink():
        raise BenchmarkError("output path cannot be a symlink")
    return candidate


def load_config(root: pathlib.Path = ROOT) -> dict[str, Any]:
    config = _load_json(root / CONFIG_PATH, "benchmark harness")
    required = {
        "schemaVersion",
        "receiptSchemaVersion",
        "minimumRuns",
        "maximumRuns",
        "minimumWarmupRuns",
        "objectives",
        "scenarioKinds",
        "databaseMode",
        "requiredRunFields",
        "thresholds",
        "percentiles",
        "artifactDirectory",
        "registeredRunner",
        "forbiddenPayloads",
    }
    if set(config) != required or config.get("schemaVersion") != 1:
        raise BenchmarkError("benchmark harness schema is invalid")
    if config.get("receiptSchemaVersion") != 1:
        raise BenchmarkError("unsupported benchmark receipt schema")
    minimum = _integer(config.get("minimumRuns"), "minimumRuns", minimum=3)
    maximum = _integer(config.get("maximumRuns"), "maximumRuns", minimum=minimum)
    if maximum < minimum:
        raise BenchmarkError("maximumRuns must be >= minimumRuns")
    _integer(config.get("minimumWarmupRuns"), "minimumWarmupRuns", minimum=1)
    for field in ("objectives", "scenarioKinds", "requiredRunFields", "forbiddenPayloads"):
        value = config.get(field)
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item for item in value)
            or len(value) != len(set(value))
        ):
            raise BenchmarkError(f"{field} must be a unique nonempty string list")
    expected_run_fields = {
        "queryCount",
        "writeQueryCount",
        "latencyMs",
        "status",
        "responseHash",
        "databaseHash",
        "eventsHash",
        "jobsHash",
    }
    if set(config["requiredRunFields"]) != expected_run_fields:
        raise BenchmarkError("requiredRunFields does not match the supported schema")
    if config.get("databaseMode") != "read-only":
        raise BenchmarkError("benchmark databaseMode must remain read-only")
    if config.get("registeredRunner") != "outcome-benchmark":
        raise BenchmarkError("registeredRunner must remain outcome-benchmark")
    thresholds = config.get("thresholds")
    expected_thresholds = {
        "minimumMedianQueryReductionCount",
        "minimumMedianQueryReductionPercent",
        "maximumQueryP95RegressionPercent",
        "minimumLatencyP95ImprovementPercent",
        "maximumLatencyP95RegressionForQueryObjectivePercent",
    }
    if not isinstance(thresholds, dict) or set(thresholds) != expected_thresholds:
        raise BenchmarkError("benchmark thresholds are invalid")
    for name, value in thresholds.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise BenchmarkError(f"threshold {name} must be nonnegative")
    if config.get("percentiles") != {
        "method": "nearest-rank",
        "reported": [50, 95, 99],
    }:
        raise BenchmarkError("percentile policy is invalid")
    _text(config.get("artifactDirectory"), "artifactDirectory")
    return config


def validate_capture(
    payload: dict[str, Any], config: dict[str, Any], label: str
) -> dict[str, Any]:
    if set(payload) != CAPTURE_FIELDS or payload.get("schemaVersion") != 1:
        raise BenchmarkError(f"{label} capture schema is invalid")
    scenario = payload.get("scenario")
    if not isinstance(scenario, dict) or set(scenario) != SCENARIO_FIELDS:
        raise BenchmarkError(f"{label} scenario schema is invalid")
    scenario_id = _text(scenario.get("id"), f"{label} scenario id", maximum=64)
    if not ID_RE.fullmatch(scenario_id):
        raise BenchmarkError(f"{label} scenario id must be lower-kebab-case")
    _integer(scenario.get("version"), f"{label} scenario version", minimum=1)
    if scenario.get("kind") not in config["scenarioKinds"]:
        raise BenchmarkError(f"{label} scenario kind is unsupported")
    _text(scenario.get("target"), f"{label} scenario target")
    if scenario.get("objective") not in config["objectives"]:
        raise BenchmarkError(f"{label} scenario objective is unsupported")
    _hash(scenario.get("datasetHash"), f"{label} datasetHash")
    _integer(scenario.get("datasetRows"), f"{label} datasetRows", minimum=1)
    _hash(scenario.get("runtimeHash"), f"{label} runtimeHash")
    if scenario.get("databaseMode") != config["databaseMode"]:
        raise BenchmarkError(f"{label} must declare read-only databaseMode")
    warmups = _integer(scenario.get("warmupRuns"), f"{label} warmupRuns")
    if warmups < config["minimumWarmupRuns"]:
        raise BenchmarkError(
            f"{label} requires at least {config['minimumWarmupRuns']} warmup runs"
        )

    runs = payload.get("runs")
    if not isinstance(runs, list) or not config["minimumRuns"] <= len(runs) <= config["maximumRuns"]:
        raise BenchmarkError(
            f"{label} requires {config['minimumRuns']}..{config['maximumRuns']} measured runs"
        )
    expected_fields = set(config["requiredRunFields"])
    behavior = None
    for index, run in enumerate(runs, start=1):
        run_label = f"{label} run {index}"
        if not isinstance(run, dict) or set(run) != expected_fields:
            raise BenchmarkError(f"{run_label} schema is invalid")
        _integer(run.get("queryCount"), f"{run_label} queryCount")
        writes = _integer(run.get("writeQueryCount"), f"{run_label} writeQueryCount")
        if writes != 0:
            raise BenchmarkError(f"{run_label} performed a database write")
        _number(run.get("latencyMs"), f"{run_label} latencyMs")
        _text(run.get("status"), f"{run_label} status", maximum=128)
        for field in ("responseHash", "databaseHash", "eventsHash", "jobsHash"):
            _hash(run.get(field), f"{run_label} {field}")
        current = tuple(
            run[field]
            for field in ("status", "responseHash", "databaseHash", "eventsHash", "jobsHash")
        )
        if behavior is None:
            behavior = current
        elif current != behavior:
            raise BenchmarkError(f"{label} behavior is unstable across measured runs")
    return payload


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return float(ordered[rank - 1])


def _rounded(value: float) -> float:
    return round(float(value), 6)


def _summary(capture: dict[str, Any]) -> dict[str, Any]:
    queries = [float(run["queryCount"]) for run in capture["runs"]]
    latencies = [float(run["latencyMs"]) for run in capture["runs"]]
    first = capture["runs"][0]
    return {
        "runs": len(capture["runs"]),
        "queryMedian": _rounded(median(queries)),
        "queryP95": _rounded(_percentile(queries, 95)),
        "latencyP50Ms": _rounded(_percentile(latencies, 50)),
        "latencyP95Ms": _rounded(_percentile(latencies, 95)),
        "latencyP99Ms": _rounded(_percentile(latencies, 99)),
        "behaviorHash": _digest(
            {
                field: first[field]
                for field in ("status", "responseHash", "databaseHash", "eventsHash", "jobsHash")
            }
        ),
    }


def _improvement(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return _rounded((before - after) / before * 100)


def compare(
    root: pathlib.Path,
    baseline_raw: str,
    candidate_raw: str,
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    artifact_dir = config["artifactDirectory"]
    baseline_path = _safe_artifact_input(
        root, baseline_raw, "baseline capture", artifact_dir
    )
    candidate_path = _safe_artifact_input(
        root, candidate_raw, "candidate capture", artifact_dir
    )
    if baseline_path == candidate_path:
        raise BenchmarkError("baseline and candidate captures must be different files")
    baseline_capture = validate_capture(
        _load_json(baseline_path, "baseline capture"), config, "baseline"
    )
    candidate_capture = validate_capture(
        _load_json(candidate_path, "candidate capture"), config, "candidate"
    )
    if baseline_capture["scenario"] != candidate_capture["scenario"]:
        raise BenchmarkError(
            "baseline and candidate must use the identical scenario, dataset, and runtime"
        )

    baseline = _summary(baseline_capture)
    candidate = _summary(candidate_capture)
    thresholds = dict(config["thresholds"])
    query_reduction_count = _rounded(
        baseline["queryMedian"] - candidate["queryMedian"]
    )
    query_reduction_percent = _improvement(
        baseline["queryMedian"], candidate["queryMedian"]
    )
    query_p95_improvement_percent = _improvement(
        baseline["queryP95"], candidate["queryP95"]
    )
    latency_p95_improvement_percent = _improvement(
        baseline["latencyP95Ms"], candidate["latencyP95Ms"]
    )
    behavior_equivalent = baseline["behaviorHash"] == candidate["behaviorHash"]
    query_pass = (
        query_reduction_count >= thresholds["minimumMedianQueryReductionCount"]
        and query_reduction_percent >= thresholds["minimumMedianQueryReductionPercent"]
        and query_p95_improvement_percent
        >= -thresholds["maximumQueryP95RegressionPercent"]
    )
    latency_pass = (
        latency_p95_improvement_percent
        >= thresholds["minimumLatencyP95ImprovementPercent"]
    )
    latency_safe_for_query = (
        latency_p95_improvement_percent
        >= -thresholds["maximumLatencyP95RegressionForQueryObjectivePercent"]
    )
    objective = baseline_capture["scenario"]["objective"]
    objective_pass = {
        "query-count": query_pass and latency_safe_for_query,
        "latency": latency_pass and query_p95_improvement_percent >= 0,
        "query-and-latency": query_pass and latency_pass,
    }[objective]

    failures = []
    if not behavior_equivalent:
        failures.append("observable behavior changed")
    if not query_pass and objective in ("query-count", "query-and-latency"):
        failures.append("query reduction threshold was not met")
    if not latency_safe_for_query and objective == "query-count":
        failures.append("p95 latency regressed beyond the query-objective tolerance")
    if not latency_pass and objective in ("latency", "query-and-latency"):
        failures.append("p95 latency improvement threshold was not met")
    if objective == "latency" and query_p95_improvement_percent < 0:
        failures.append("query p95 increased for a latency objective")
    passed = behavior_equivalent and objective_pass

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    else:
        try:
            parsed = datetime.fromisoformat(created_at)
        except ValueError as exc:
            raise BenchmarkError("receipt createdAt is invalid") from exc
        if parsed.tzinfo is None:
            raise BenchmarkError("receipt createdAt must include a timezone")

    sources = {
        "baseline": {
            "path": baseline_path.relative_to(root).as_posix(),
            "sha256": _file_digest(baseline_path),
        },
        "candidate": {
            "path": candidate_path.relative_to(root).as_posix(),
            "sha256": _file_digest(candidate_path),
        },
    }
    receipt = {
        "schemaVersion": config["receiptSchemaVersion"],
        "createdAt": created_at,
        "verdict": "pass" if passed else "fail",
        "scenario": baseline_capture["scenario"],
        "thresholds": thresholds,
        "baseline": baseline,
        "candidate": candidate,
        "comparison": {
            "behaviorEquivalent": behavior_equivalent,
            "queryReductionCount": query_reduction_count,
            "queryReductionPercent": query_reduction_percent,
            "queryP95ImprovementPercent": query_p95_improvement_percent,
            "latencyP95ImprovementPercent": latency_p95_improvement_percent,
            "queryThresholdPassed": query_pass,
            "latencyThresholdPassed": latency_pass,
            "objectivePassed": objective_pass,
        },
        "failures": failures,
        "sources": sources,
    }
    receipt["receiptHash"] = _digest(receipt)
    return receipt


def verify(root: pathlib.Path, receipt_raw: str) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    receipt_path = _safe_artifact_input(
        root, receipt_raw, "benchmark receipt", config["artifactDirectory"]
    )
    receipt = _load_json(receipt_path, "benchmark receipt")
    if set(receipt) != RECEIPT_FIELDS:
        raise BenchmarkError("benchmark receipt schema is invalid")
    supplied_hash = receipt.get("receiptHash")
    _hash(supplied_hash, "receiptHash")
    unsigned = dict(receipt)
    unsigned.pop("receiptHash")
    if _digest(unsigned) != supplied_hash:
        raise BenchmarkError("benchmark receipt hash does not match its contents")
    sources = receipt.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"baseline", "candidate"}:
        raise BenchmarkError("benchmark receipt sources are invalid")
    for label in ("baseline", "candidate"):
        source = sources[label]
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            raise BenchmarkError(f"benchmark {label} source is invalid")
        path = _safe_input(root, source["path"], f"{label} source")
        _hash(source["sha256"], f"{label} source hash")
        if _file_digest(path) != source["sha256"]:
            raise BenchmarkError(f"benchmark {label} source hash changed")
    expected = compare(
        root,
        sources["baseline"]["path"],
        sources["candidate"]["path"],
        created_at=receipt.get("createdAt"),
    )
    if receipt != expected:
        raise BenchmarkError("benchmark receipt does not match its source captures")
    if receipt.get("verdict") != "pass":
        reasons = "; ".join(receipt.get("failures") or ["objective failed"])
        raise BenchmarkError(f"benchmark verdict is fail: {reasons}")
    return receipt


def _write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = pathlib.Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise BenchmarkError(f"cannot write benchmark receipt: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="outcome-benchmark", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--root", default=".")
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--candidate", required=True)
    compare_parser.add_argument("--output", required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--root", default=".")
    verify_parser.add_argument("receipt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    try:
        if args.command == "compare":
            config = load_config(root)
            output = _safe_output(root, args.output, config["artifactDirectory"])
            source_paths = {
                _safe_artifact_input(
                    root, args.baseline, "baseline capture", config["artifactDirectory"]
                ),
                _safe_artifact_input(
                    root, args.candidate, "candidate capture", config["artifactDirectory"]
                ),
            }
            if output.resolve(strict=False) in source_paths:
                raise BenchmarkError("output path cannot overwrite a source capture")
            receipt = compare(root, args.baseline, args.candidate)
            _write_json_atomic(output, receipt)
            print(json.dumps(receipt, separators=(",", ":"), sort_keys=True))
            return 0 if receipt["verdict"] == "pass" else 1
        receipt = verify(root, args.receipt)
        print(
            json.dumps(
                {
                    "status": "verified",
                    "verdict": receipt["verdict"],
                    "scenario": receipt["scenario"]["id"],
                    "receiptHash": receipt["receiptHash"],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 0
    except BenchmarkError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
