#!/usr/bin/env python3
"""Compare verified Laravel task delivery on live Claude Code sessions."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import importlib.util
import itertools
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import types
import uuid

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/guild-kernel"))
import kernel  # noqa: E402

BASELINE = "920df9f1e4a19e7fa54eb07718e0b1e00c2d72e3"
MODEL = "claude-sonnet-5-5"
VARIANTS = ("single", "wave", "rolling")
CHECKPOINT = "approve-contract"
CHECKPOINT_SECONDS = 6
SYSTEM = "Return only the requested JSON. Work only from the supplied synthetic Laravel fixture."
CONTRACT = {
    "method": "POST", "path": "/api/tags", "field": "slug",
    "maximumLength": 32, "successStatus": 201, "invalidStatus": 422,
}
POLICY = (
    "A valid slug is a string of 1 to 32 ASCII characters that starts with a lowercase "
    "ASCII letter and then contains only lowercase ASCII letters, digits, or hyphens. "
    "Reject all whitespace and malformed inputs. Preserve values without normalizing them."
)
VALUES = [
    "a", "abc", "a-b", "a0", "ab--cd", "banana-", "a-", "a" * 31, "a" * 32,
    "a" * 33, "a" + "-" * 31, "b" + "0" * 31, "aa-99", "tag-1", "x9y", "x-0",
    "z", "a--", "", "A", "firstName", "-a", "1a", "a_b", "a b", " abc", "abc ",
    "abc\n", "a\tb", "a/b", "a.b", "é", "aé", "Ａ", "abc🙂", "a–b", 7, False, None, ["a"],
]
VALID = [isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value) is not None
         for value in VALUES]
TASKS = {
    "contract": ("architecture", 5, ("shape", "route", "statuses", "field")),
    "rules": ("backend", 10, ("class-and-status", "laravel-rules", "php-behavior")),
    "matrix": ("testing", 30, ("shape", "valid-cases", "invalid-cases")),
    "review": ("documentation", 8, ("counts", "invalid-ids", "boundary-ids")),
}
WORKLOADS = {
    "narrow-fix": {"rules": []},
    "sequential": {"contract": [], "rules": ["contract"], "matrix": ["rules"], "review": ["matrix"]},
    "independent": {"contract": [], "rules": [], "matrix": []},
    "checkpoint-hybrid": {"contract": [], "matrix": [], "rules": ["contract"], "review": ["matrix"]},
}


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def request(tasks, dependencies, artifacts):
    def source(task, dependency, fallback=None):
        if dependency not in dependencies[task]:
            return encode(fallback)
        if dependency in artifacts:
            return encode(artifacts[dependency])
        return f"the {dependency} object generated earlier for this request"

    prompts = {
        "contract": lambda: (
            "For POST /api/tags with one slug field limited to 32 characters, creation "
            "returns 201 and invalid input 422. Give JSON keys method, path, field, "
            "maximumLength, successStatus, invalidStatus, with numeric length and statuses."
        ),
        "rules": lambda: (
            f"Use {source('rules', 'contract', CONTRACT)} as the Laravel endpoint contract. "
            f"{POLICY} Give exactly keys class (the short name StoreTagRequest), invalidStatus "
            "(numeric), and rules (an object with only slug, an array of exactly required, "
            "string, max:32, and one Laravel regex rule). Use PHP PCRE that rejects a final newline."
        ),
        "matrix": lambda: (
            ("Use the Laravel rule in " + source("matrix", "rules") + ". "
             if "rules" in dependencies["matrix"] else "")
            + f"{POLICY} Classify all values in the original order as a JSON array of objects "
            "each with exactly id (integer, starting at 1), value (original value), and valid "
            f"(boolean). Values: {encode(VALUES)}"
        ),
        "review": lambda: (
            f"Summarize the QA matrix from {source('review', 'matrix')}. "
            "Give exactly total, validCount, invalidCount, invalidIds (ascending), "
            "and validAtMaxLengthIds (ascending IDs of valid strings exactly 32 characters long)."
        ),
    }
    return ("Return a JSON object with exactly these artifact keys. Resolve any prerequisites "
            "before producing the dependent artifact.\n"
            + "\n".join(f"{task}: {prompts[task]()}" for task in tasks))


def expected_matrix():
    return [{"id": index, "value": value, "valid": valid}
            for index, (value, valid) in enumerate(zip(VALUES, VALID), 1)]


def expected_review():
    return {
        "total": len(VALUES), "validCount": sum(VALID), "invalidCount": len(VALID) - sum(VALID),
        "invalidIds": [index for index, valid in enumerate(VALID, 1) if not valid],
        "validAtMaxLengthIds": [index for index, (value, valid) in
                                enumerate(zip(VALUES, VALID), 1) if valid and len(value) == 32],
    }


def grade(task, artifact):
    obj = artifact if isinstance(artifact, dict) else {}
    if task == "contract":
        scores = [set(obj) == set(CONTRACT)] + [
            all(type(obj.get(key)) is type(CONTRACT[key]) and obj[key] == CONTRACT[key]
                for key in keys)
            for keys in (("method", "path"), ("successStatus", "invalidStatus"), ("field", "maximumLength"))
        ]
    elif task == "rules":
        rule = obj.get("rules")
        slug = rule.get("slug") if isinstance(rule, dict) else None
        regexes = [s.removeprefix("regex:") for s in slug if isinstance(s, str) and s.startswith("regex:")] if isinstance(slug, list) else []
        meets_shape = (len(regexes) == 1 and set(rule) == {"slug"} and len(slug) == 4
                       and all(s in slug for s in ("required", "string", "max:32")))
        behavior = False
        if meets_shape and len(regexes[0]) <= 150:
            # Execute the regex as data with bounded PCRE limits.
            php = (
                '$d=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);'
                'echo json_encode(array_map(fn($s)=>is_string($s)&&strlen($s)<=32'
                '&&preg_match($d[0],$s)===1,$d[1]));'
            )
            result = subprocess.run(
                ["php", "-n", "-d", "pcre.backtrack_limit=10000", "-d",
                 "pcre.recursion_limit=1000", "-r", php],
                input=encode([regexes[0], VALUES]), text=True, capture_output=True, timeout=8,
            )
            behavior = result.returncode == 0 and not result.stderr and json.loads(result.stdout) == VALID
        scores = [set(obj) == {"class", "invalidStatus", "rules"}
                  and obj["class"] == "StoreTagRequest" and obj["invalidStatus"] == 422,
                  bool(meets_shape), behavior]
    elif task == "matrix":
        rows = artifact if isinstance(artifact, list) else []
        shape = len(rows) == len(VALUES) and all(
            isinstance(row, dict) and set(row) == {"id", "value", "valid"}
            and type(row["id"]) is int and row["id"] == index
            and type(row["value"]) is type(value) and row["value"] == value
            and type(row["valid"]) is bool
            for index, (row, value) in enumerate(zip(rows, VALUES), 1)
        )
        scores = [shape] + [
            shape and all(row["valid"] is expected for row, expected in zip(rows, VALID)
                          if expected is selected) for selected in (True, False)
        ]
    else:
        expected = expected_review()
        scores = [
            set(obj) == set(expected) and all(obj[key] == expected[key] for key in
                                             ("total", "validCount", "invalidCount")),
            obj.get("invalidIds") == expected["invalidIds"],
            obj.get("validAtMaxLengthIds") == expected["validAtMaxLengthIds"],
        ]
    return dict(zip(TASKS[task][2], scores))


def parse_artifacts(body):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # Grade the artifact even when the model wraps an unambiguous JSON block.
        fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", body, flags=re.DOTALL)
        if len(fenced) != 1:
            raise
        return json.loads(fenced[0])


def subtract_prior_usage(cost, tokens, prior):
    if prior is None:
        return cost, tokens
    delta = {key: value - prior["tokens"][key] for key, value in tokens.items()}
    if cost <= prior["usd"] or any(value < 0 for value in delta.values()):
        raise ValueError("Resumed Claude usage is inconsistent with the previous turn")
    return cost - prior["usd"], delta


def run_worker(root, name, stage, agent, tasks, prompt, dry, prior, session):
    worker = str(uuid.uuid4())
    target = (name, stage)
    kernel.record_worker_event(root, agent, worker, "start", expected_target=target)
    started = time.monotonic()
    metadata = {"usd": None, "tokens": {}, "turns": 0, "error": None, "session": None,
                "promptSha256": sha(prompt.encode())}
    try:
        if dry:
            fixtures = {
                "contract": CONTRACT, "matrix": expected_matrix(), "review": expected_review(),
                "rules": {"class": "StoreTagRequest", "invalidStatus": 422, "rules": {
                    "slug": ["required", "string", "max:32", r"regex:/\A[a-z][a-z0-9-]*\z/"],
                }},
            }
            if name == "checkpoint-hybrid" and "matrix" in tasks:
                time.sleep(0.8)
            return {task: fixtures[task] for task in tasks}, {
                **metadata, "usd": 0.0, "turns": 1, "seconds": time.monotonic() - started,
            }
        session_args = (["--resume" if prior else "--session-id", session]
                        if session else ["--no-session-persistence"])
        raw = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--effort", "low", "--tools", "",
             "--setting-sources", "", "--strict-mcp-config", *session_args,
             "--max-turns", "1", "--max-budget-usd", "0.15", "--output-format", "json",
             "--system-prompt", SYSTEM],
            input=prompt, cwd=root, capture_output=True, text=True, timeout=150,
        )
        reply = json.loads(raw.stdout)
        reported_cost = reply.get("total_cost_usd")
        metadata["reportedCostUsd"] = reported_cost
        metadata["turns"] = reply.get("num_turns", 0)
        metadata["seconds"] = time.monotonic() - started
        metadata["session"] = reply.get("session_id")
        usage = reply.get("modelUsage", {})
        if set(usage) == {MODEL} and isinstance(reported_cost, (int, float)) and reported_cost > 0:
            tokens = {key: usage[MODEL].get(key, 0) for key in
                      ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")}
            metadata["usd"], metadata["tokens"] = subtract_prior_usage(reported_cost, tokens, prior)
        if raw.returncode or reply.get("is_error") or reply.get("subtype") != "success":
            metadata["error"] = f"Claude exit {raw.returncode}; subtype {reply.get('subtype')}; see authentication and usage status"
            return {}, metadata
        if metadata["usd"] is None:
            metadata["error"] = "Missing positive provider cost or requested model evidence"
            return {}, metadata
        if session and metadata["session"] != session:
            metadata["error"] = "Claude session identity changed"
            return {}, metadata
        parsed = parse_artifacts(reply.get("result", "").strip())
        if not isinstance(parsed, dict) or not set(parsed) <= set(tasks):
            metadata["error"] = "Unexpected artifact keys"
            return {}, metadata
        return parsed, metadata
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        metadata["error"] = type(exc).__name__
        metadata.setdefault("seconds", time.monotonic() - started)
        return {}, metadata
    except ValueError as exc:
        metadata["error"] = str(exc)
        metadata.setdefault("seconds", time.monotonic() - started)
        return {}, metadata
    finally:
        kernel.record_worker_event(root, agent, worker, "finish", expected_target=target)


def load_planners():
    path = REPO / "scripts/coordination-harness.py"
    old_source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:scripts/coordination-harness.py"], cwd=REPO,
    )
    old = types.ModuleType("guild_previous_coordination")
    old.__file__ = str(path)
    exec(compile(old_source, f"{BASELINE}:{path.name}", "exec"), old.__dict__)
    spec = importlib.util.spec_from_file_location("guild_rolling_coordination", path)
    rolling = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rolling)
    return old, rolling, sha(old_source)


def plan_dispatch(planner, name, dependencies):
    policy = json.loads((REPO / "config/coordination-harness.json").read_text())
    registry = json.loads((REPO / "config/agent-harness.json").read_text())
    workload = {"schemaVersion": 1, "workloadId": name, "coordinator": "delivery-coordinator", "tasks": [
        {"id": task, "capability": TASKS[task][0], "dependencies": deps,
         "ownedPaths": [f"artifacts/{task}.json"], "estimatedSeconds": TASKS[task][1],
         "estimatedCostUsd": 0.15, "mutates": True, "sideEffectKey": None,
         "requiresSpecialist": True, "approvalsRequired": [], "approvalsGranted": [],
         "contextPacketHash": sha(encode([task, deps]).encode()), "expectedOutput": f"{task} JSON"}
        for task, deps in dependencies.items()
    ]}
    if len(dependencies) == 1:
        return [list(dependencies)], {task: policy["capabilityRouting"][TASKS[task][0]] for task in dependencies}
    plan = planner.plan_workload(policy, registry, workload)
    if plan["decision"] != "delegate":
        raise RuntimeError(f"Unusable evaluation plan: {plan['reasons']}")
    return plan["waves"], {row["taskId"]: row["agent"] for row in plan["assignments"]}


def commit_worker(root, name, stage, agent, tasks, outputs, metadata, grades):
    if metadata["usd"] is not None:
        kernel.record_stage_usage(root, agent, {
            "seconds": metadata["seconds"], "tool_calls": 0, "turns": metadata["turns"],
            "tokens": sum(metadata["tokens"].values()), "cost_usd": metadata["usd"],
        }, expected_target=(name, stage))
    for task in tasks:
        grades[task] = grade(task, outputs.get(task))
        if task in outputs:
            (root / f"artifacts/{task}.json").write_text(encode(outputs[task]) + "\n")
    if metadata["error"] or not all(all(grades[task].values()) for task in tasks):
        return False
    report = root / f"docs/delivery/{name}/stages/{agent}--{stage}.md"
    lines = ["STATUS: done"]
    for task in tasks:
        path = f"artifacts/{task}.json"
        lines.extend([f"DID: {path}", "VERIFIED: " + encode({
            "criterion": f"{task}-checked", "runner": "file-exists", "args": [path],
        })])
    report.write_text("\n".join([*lines, "NOT-CHECKED: none", "FLAGS: none", "NEXT: none"]) + "\n")
    kernel.report(root, name, report, runner=None)
    return True


def trial(name, variant, repetition, old, rolling, dry):
    dependencies = WORKLOADS[name]
    hybrid = name == "checkpoint-hybrid"
    waves, agents = plan_dispatch(old if variant == "wave" else rolling, name, dependencies)
    bundles = {task: [task] for task in agents}
    stage_dependencies = dependencies
    gated = "contract"
    if variant == "single":
        bundles = {"single-prep": ["matrix", "review"], "single-deliver": ["contract", "rules"]} if hybrid else {"single-deliver": list(dependencies)}
        agents = dict.fromkeys(bundles, "backend-developer")
        stage_dependencies = {stage: [] for stage in bundles}
        if hybrid:
            stage_dependencies["single-deliver"] = ["single-prep"]
        gated = "single-deliver"
    stage_order = list(bundles) if variant == "single" else list(itertools.chain.from_iterable(waves))
    artifacts, grades, workers, complete = {}, {}, {}, set()
    with tempfile.TemporaryDirectory(prefix=f"guild-stage-eval-{variant}-") as temporary:
        root = pathlib.Path(temporary)
        (root / "artifacts").mkdir()
        (root / f"docs/delivery/{name}/stages").mkdir(parents=True)
        start = time.monotonic()
        kernel.plan(
            root=root, name=name, done_when="Verify all Laravel fixture artifacts",
            max_parallel=1 if variant == "single" else 4,
            stages=[
                kernel.StageSpec(
                    stage, agents[stage], "writer", [f"Validate the {task} artifact" for task in bundles[stage]],
                    stage_dependencies[stage], owned_paths=[f"artifacts/{task}.json" for task in bundles[stage]],
                    criterion_ids=[f"{task}-checked" for task in bundles[stage]],
                ) for stage in stage_order
            ],
        )
        checkpoint_at = None
        if hybrid:
            kernel.open_checkpoint(
                root, name, gated, CHECKPOINT, "Approve the synthetic Tag API contract?",
                "A contract change can invalidate implementation.",
                [{"id": "approve", "label": "Approve", "action": "continue"},
                 {"id": "stop", "label": "Stop", "action": "stop"}], "approve",
            )
            checkpoint_at = time.monotonic() + (0.5 if dry else CHECKPOINT_SECONDS)
        session = str(uuid.uuid4()) if hybrid and variant == "single" else None
        pending = {}
        with ThreadPoolExecutor(max_workers=1 if variant == "single" else 4) as pool:
            while len(complete) < len(bundles):
                if checkpoint_at is not None and time.monotonic() >= checkpoint_at:
                    kernel.resolve_checkpoint(root, name, CHECKPOINT, "approve", note="Synthetic eval approval")
                    checkpoint_at = None
                ready = [stage.id for stage in kernel.ready_stages(root, name)]
                if variant == "wave":
                    wave = next((wave for wave in waves if not set(wave) <= complete), ())
                    ready = [stage for stage in ready if stage in wave]
                for stage in ready:
                    kernel.claim_stage(root, name, stage)
                    tasks = bundles[stage]
                    future = pool.submit(
                        run_worker, root, name, stage, agents[stage], tasks,
                        request(tasks, dependencies, artifacts), dry,
                        workers.get("single-prep") if session else None, session,
                    )
                    pending[future] = stage
                remaining = None if checkpoint_at is None else max(0, checkpoint_at - time.monotonic())
                if not pending:
                    if remaining is None:
                        break
                    time.sleep(remaining)
                    continue
                finished, _ = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                for future in finished:
                    stage = pending.pop(future)
                    outputs, metadata = future.result()
                    workers[stage] = metadata
                    if commit_worker(root, name, stage, agents[stage], bundles[stage], outputs, metadata, grades):
                        artifacts.update(outputs)
                        complete.add(stage)
        elapsed = time.monotonic() - start
        trace = kernel.observability_status(root, name)
        if trace["status"] != "healthy":
            raise RuntimeError(trace["errors"])
        timings = kernel.timing_rows(root, name)
        finished = kernel.load(root, name).status == "done"
    quality = sum(sum(values.values()) for values in grades.values())
    total = sum(len(TASKS[task][2]) for task in dependencies)
    costs = [worker["usd"] for worker in workers.values()]
    return {"workload": name, "variant": variant, "repetition": repetition, "model": MODEL,
            "dry": dry, "wallSeconds": elapsed, "usd": round(sum(costs), 8) if all(c is not None for c in costs) else None,
            "verified": finished and quality == total, "passed": quality, "total": total,
            "grades": grades, "workers": workers, "timings": timings, "trace": trace,
            "waves": waves if variant == "wave" else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3, choices=range(1, 7))
    parser.add_argument("--workload", choices=WORKLOADS, action="append")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    old, rolling, old_hash = load_planners()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = {"baseCommit": BASELINE, "oldPlannerSha256": old_hash}
    for path in ("scripts/guild-kernel/kernel.py", "scripts/coordination-harness.py", "tests/eval/run-stage-timing.py"):
        sources[path] = sha((REPO / path).read_bytes())
    for repetition in range(1, args.repetitions + 1):
        for index, name in enumerate(args.workload or WORKLOADS):
            rotation = (repetition + index - 1) % len(VARIANTS)
            for variant in VARIANTS[rotation:] + VARIANTS[:rotation]:
                path = args.output / f"{name}-{repetition}-{variant}.json"
                if path.exists():
                    saved = json.loads(path.read_text())
                    if saved["sources"] != sources or saved["dry"] != args.dry_run:
                        raise RuntimeError(f"Existing result has different inputs: {path}")
                    continue
                result = trial(name, variant, repetition, old, rolling, args.dry_run)
                path.write_text(json.dumps({**result, "sources": sources}, indent=2) + "\n")
                cost = f"${result['usd']:.5f}" if result["usd"] is not None else "cost unavailable"
                print(f"{name} {repetition} {variant}: {result['wallSeconds']:.2f}s, {cost}, "
                      f"{result['passed']}/{result['total']}, verified={result['verified']}", flush=True)
                if any(row["error"] and not row["usd"] for row in result["workers"].values()):
                    raise RuntimeError("Model unavailable before a paid response; inspect the result and fix access.")


if __name__ == "__main__":
    main()
