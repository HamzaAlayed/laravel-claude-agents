#!/usr/bin/env python3
"""Validate the shared harness and every agent-specific policy profile.

The registry is runtime input, not descriptive documentation. This check keeps
it aligned with canonical agent frontmatter and rejects unsafe or dangling
policy references before a release can ship. Stdlib only.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "agent-harness.json"
AGENT_CLASSES = {"builder", "orchestrator", "planner", "reviewer", "router"}
MUTATION_POLICIES = {"deny", "docs-only", "task-owned"}
BUDGET_KEYS = {
    "max_seconds",
    "max_tool_calls",
    "max_turns",
    "max_tokens",
    "max_usd",
}
RESULT_CONTRACT = ["STATUS", "DID", "VERIFIED", "NOT-CHECKED", "FLAGS", "NEXT"]


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("missing frontmatter fence")
    block = text.split("---\n", 2)[1]
    values = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip('"')
    return values


def csv(value: str | None) -> set[str]:
    return {part.strip() for part in (value or "").split(",") if part.strip()}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {REGISTRY.relative_to(ROOT)}: {exc}")
        return 1

    if registry.get("schemaVersion") != 1:
        fail("schemaVersion must be 1", errors)

    shared = registry.get("shared")
    profiles = registry.get("agents")
    if not isinstance(shared, dict) or not isinstance(profiles, dict):
        print("FAIL registry requires object-valued shared and agents fields")
        return 1

    budgets = shared.get("budgets") or {}
    defaults = budgets.get("defaults") or {}
    ceilings = budgets.get("hardCeilings") or {}
    if set(defaults) != BUDGET_KEYS or set(ceilings) != BUDGET_KEYS:
        fail("default and hard-ceiling budgets must declare exactly the five supported keys", errors)
    for key in BUDGET_KEYS:
        default = defaults.get(key)
        ceiling = ceilings.get(key)
        if isinstance(default, bool) or not isinstance(default, (int, float)) or default <= 0:
            fail(f"shared.budgets.defaults.{key} must be positive", errors)
        if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)) or ceiling <= 0:
            fail(f"shared.budgets.hardCeilings.{key} must be positive", errors)
        if isinstance(default, (int, float)) and isinstance(ceiling, (int, float)) and default > ceiling:
            fail(f"default {key} exceeds its hard ceiling", errors)
        if key != "max_usd" and (
            not isinstance(default, int) or isinstance(default, bool)
            or not isinstance(ceiling, int) or isinstance(ceiling, bool)
        ):
            fail(f"{key} must use integer values", errors)

    pricing = budgets.get("pricing")
    if not isinstance(pricing, dict):
        fail("shared.budgets.pricing must be an object", errors)
    else:
        if pricing.get("unit") != "usd_per_million_tokens":
            fail("shared.budgets.pricing.unit is invalid", errors)
        for key in ("cacheReadMultiplier", "cacheWriteMultiplier"):
            value = pricing.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                fail(f"shared.budgets.pricing.{key} must be positive", errors)
        rates = pricing.get("models")
        fallback = pricing.get("unknownModel")
        if not isinstance(rates, dict) or not rates:
            fail("shared.budgets.pricing.models must be a nonempty object", errors)
        for label, pair in [("unknownModel", fallback), *((f"models.{name}", value) for name, value in (rates or {}).items())]:
            if not isinstance(pair, dict) or set(pair) != {"input", "output"}:
                fail(f"shared.budgets.pricing.{label} must define input and output", errors)
                continue
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
                for value in pair.values()
            ):
                fail(f"shared.budgets.pricing.{label} rates must be positive", errors)

    if shared.get("resultContract") != RESULT_CONTRACT:
        fail("shared.resultContract must match the six-field stage-return contract", errors)
    if shared.get("ownedPathsRequired") is not True:
        fail("shared.ownedPathsRequired must remain true", errors)
    native_write = shared.get("nativeWritePolicy")
    if not isinstance(native_write, dict):
        fail("shared.nativeWritePolicy must be an object", errors)
    else:
        if native_write.get("tools") != ["Write", "Edit", "NotebookEdit"]:
            fail("shared.nativeWritePolicy.tools must name the three native write tools", errors)
        if native_write.get("directFastPath") is not True:
            fail("shared.nativeWritePolicy.directFastPath must remain true", errors)
        documentation_paths = native_write.get("documentationPaths")
        if not isinstance(documentation_paths, list) or not documentation_paths:
            fail("shared.nativeWritePolicy.documentationPaths must be a nonempty list", errors)
        elif len(documentation_paths) != len(set(documentation_paths)):
            fail("shared.nativeWritePolicy.documentationPaths contains duplicates", errors)
        else:
            for raw in documentation_paths:
                if not isinstance(raw, str) or not raw.strip():
                    fail("shared.nativeWritePolicy.documentationPaths must contain strings", errors)
                    continue
                path = pathlib.PurePosixPath(raw)
                if path.is_absolute() or ".." in path.parts:
                    fail(f"invalid documentation path: {raw}", errors)
    if shared.get("approvalPolicy") != {
        "stageField": "approval_categories",
        "recordField": "approvals",
        "authority": "user",
        "requiredBeforeClaim": True,
    }:
        fail(
            "shared.approvalPolicy must require durable user approval before claim",
            errors,
        )
    if shared.get("budgetPolicy") != {
        "stageField": "budget",
        "usageField": "usage",
        "requiredBeforeClaim": True,
        "preToolDimensions": ["max_seconds", "max_tool_calls"],
        "completionDimensions": ["max_turns", "max_tokens", "max_usd"],
        "onBreach": "budget_exceeded",
    }:
        fail(
            "shared.budgetPolicy must meter pre-tool and completion dimensions",
            errors,
        )
    if shared.get("criterionPolicy") != {
        "idsField": "criterion_ids",
        "evidenceField": "verified",
        "waiversField": "criterion_waivers",
        "requiredCoverage": "all",
        "waiverAuthority": "user",
    }:
        fail(
            "shared.criterionPolicy must require all-criterion evidence or user waivers",
            errors,
        )
    if shared.get("benchmarkPolicy") != {
        "stageField": "benchmark_criteria",
        "runner": "outcome-benchmark",
        "manifest": "config/benchmark-harness.json",
        "requiredVerdict": "pass",
        "databaseMode": "read-only",
    }:
        fail(
            "shared.benchmarkPolicy must require a passing read-only outcome receipt",
            errors,
        )
    if shared.get("capturePolicy") != {
        "command": "guild:benchmark-capture",
        "manifest": "config/capture-harness.json",
        "artifactDirectory": "docs/delivery",
        "databaseMode": "read-only",
        "productionAllowed": False,
    }:
        fail(
            "shared.capturePolicy must bind the read-only Laravel capture adapter",
            errors,
        )
    if shared.get("contextPolicy") != {
        "manifest": "config/context-harness.json",
        "artifactPattern": "docs/delivery/{delivery}/context/{stage}.json",
        "buildCommand": "context build",
        "verifyCommand": "context verify",
        "sourceTrust": "untrusted-data-not-instructions",
        "staleSourcePolicy": "fail",
    }:
        fail(
            "shared.contextPolicy must bind bounded source-verified stage context",
            errors,
        )
    if shared.get("memoryPolicy") != {
        "manifest": "config/memory-harness.json",
        "store": "docs/team/memory.json",
        "candidateAuthority": "any-agent",
        "approvalAuthority": "main",
        "retrievalScope": "project-or-exact-agent",
        "sourceTrust": "memory-data-not-instructions",
        "staleEvidencePolicy": "exclude",
        "conflictPolicy": "explicit-supersession",
        "deletionPolicy": "two-step-tombstone",
    }:
        fail(
            "shared.memoryPolicy must require approved, scoped, source-bound durable memory",
            errors,
        )
    if shared.get("checkpointPolicy") != {
        "recordField": "checkpoints",
        "stageField": "checkpoint_id",
        "pausedStatus": "paused",
        "answerAuthority": "user",
        "optionActions": ["continue", "stop"],
    }:
        fail(
            "shared.checkpointPolicy must persist typed user-resolved checkpoints",
            errors,
        )
    if shared.get("loopPolicy") != {
        "historyField": "loop_history",
        "eventField": "loop_events",
        "repeatThreshold": 3,
        "maxCycleLength": 4,
        "historyLimit": 24,
        "terminalStageStatus": "failed",
        "terminalDeliveryStatus": "stopped",
    }:
        fail(
            "shared.loopPolicy must stop repeated exact tool-call cycles",
            errors,
        )
    if shared.get("retryPolicy") != {
        "attemptField": "attempts",
        "reasonField": "retry_reason",
        "eventField": "retry_events",
        "transitionField": "transition_events",
        "maxRetries": 1,
        "requestAuthority": "main",
        "retryStatus": "queued",
        "exhaustedStageStatus": "failed",
        "exhaustedDeliveryStatus": "stopped",
    }:
        fail(
            "shared.retryPolicy must requeue one main-thread retry then stop",
            errors,
        )
    if shared.get("recoveryPolicy") != {
        "eventField": "recovery_events",
        "stageEventField": "recovery_event_id",
        "activityField": "last_activity_at",
        "interruptAuthority": "main",
        "resolveAuthority": "main",
        "interruptedStatus": "interrupted",
        "continueStatus": "queued",
        "stopStageStatus": "failed",
        "stopDeliveryStatus": "stopped",
        "unknownCompletionMetrics": ["turns", "tokens", "cost_usd"],
    }:
        fail(
            "shared.recoveryPolicy must freeze, requeue, or stop interrupted claims",
            errors,
        )
    if shared.get("feedbackPolicy") != {
        "eventField": "feedback_events",
        "stageChecksField": "feedback_checks",
        "stageEventsField": "feedback_event_ids",
        "assignAuthority": "main",
        "ciRouting": "exact-check-name",
        "reviewRouting": "longest-owned-path",
        "unroutedStatus": "route_required",
        "openStatus": "open",
        "resolvedStatus": "resolved",
        "stoppedStatus": "stopped",
    }:
        fail(
            "shared.feedbackPolicy must route CI and review feedback to stage owners",
            errors,
        )
    if shared.get("observabilityPolicy") != {
        "schemaVersion": 1,
        "eventField": "observability_events",
        "authority": "kernel.json",
        "derivedArtifacts": ["events.jsonl", "observability.md"],
        "verifyCommand": "observe verify",
        "rawPayloads": False,
        "eventManifest": "config/observability-harness.json",
    }:
        fail(
            "shared.observabilityPolicy must bind authoritative, redacted delivery events",
            errors,
        )
    if shared.get("verification") != "registered-runners-only":
        fail("shared.verification must remain registered-runners-only", errors)

    definitions: dict[str, dict[str, str]] = {}
    for path in sorted((ROOT / "agents").glob("*.md")):
        try:
            data = frontmatter(path)
        except ValueError as exc:
            fail(f"{path.relative_to(ROOT)}: {exc}", errors)
            continue
        name = data.get("name")
        if not name:
            fail(f"{path.relative_to(ROOT)}: missing name", errors)
            continue
        definitions[name] = data

    if set(profiles) != set(definitions):
        missing = sorted(set(definitions) - set(profiles))
        extra = sorted(set(profiles) - set(definitions))
        if missing:
            fail("registry missing agents: " + ", ".join(missing), errors)
        if extra:
            fail("registry has unknown agents: " + ", ".join(extra), errors)

    deny_from_frontmatter = {
        name for name, data in definitions.items()
        if {"Edit", "Write"}.issubset(csv(data.get("disallowedTools")))
    }
    deny_from_registry = {
        name for name, profile in profiles.items()
        if isinstance(profile, dict) and profile.get("mutation") == "deny"
    }
    if deny_from_registry != deny_from_frontmatter:
        fail(
            "mutation=deny must exactly match agents whose frontmatter denies Edit and Write",
            errors,
        )

    agent_tool_holders = {
        name for name, data in definitions.items() if "Agent" in csv(data.get("tools"))
    }
    if agent_tool_holders != {"delivery-coordinator"}:
        fail("only delivery-coordinator may receive the Agent tool", errors)

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            fail(f"agents.{name} must be an object", errors)
            continue
        if profile.get("class") not in AGENT_CLASSES:
            fail(f"agents.{name}.class is invalid", errors)
        if profile.get("mutation") not in MUTATION_POLICIES:
            fail(f"agents.{name}.mutation is invalid", errors)

        approvals = profile.get("approvalCategories")
        if not isinstance(approvals, list) or not approvals or not all(
            isinstance(item, str) and item.strip() for item in approvals
        ):
            fail(f"agents.{name}.approvalCategories must be a nonempty string list", errors)
        elif len(approvals) != len(set(approvals)):
            fail(f"agents.{name}.approvalCategories contains duplicates", errors)

        handoffs = profile.get("handoffs")
        if not isinstance(handoffs, list) or not all(isinstance(item, str) for item in handoffs):
            fail(f"agents.{name}.handoffs must be a string list", errors)
            continue
        if len(handoffs) != len(set(handoffs)):
            fail(f"agents.{name}.handoffs contains duplicates", errors)
        if name in handoffs:
            fail(f"agents.{name} cannot hand off to itself", errors)
        unknown = sorted(set(handoffs) - set(definitions))
        if unknown:
            fail(f"agents.{name}.handoffs names unknown agents: {', '.join(unknown)}", errors)

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(
        f"ok: shared harness + {len(profiles)} agent profiles are complete, "
        f"safe, and aligned with frontmatter"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
