#!/usr/bin/env python3
"""Guild kernel CLI — delivery state, explicit lesson approval, and sprints."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402
import context_packets  # noqa: E402


class ProcessRunner:
    def run(self, cwd, argv):
        if not isinstance(argv, (list, tuple)) or not argv:
            raise TypeError("verification runner requires a nonempty argument array")
        completed = subprocess.run(list(argv), cwd=cwd, shell=False)
        return completed.returncode

    def capture(self, cwd, argv):
        if not isinstance(argv, (list, tuple)) or not argv:
            raise TypeError("capture runner requires a nonempty argument array")
        completed = subprocess.run(
            list(argv), cwd=cwd, shell=False, capture_output=True, text=True
        )
        return completed.returncode, completed.stdout


def _common():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", required=True)
    parser.add_argument("--name", required=True)
    return parser


def build_parser():
    common = _common()
    parser = argparse.ArgumentParser(prog="guild")
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", parents=[common])
    plan.add_argument("--done-when", default="")
    plan.add_argument("--sprint", default="")
    plan.add_argument(
        "--stage",
        action="append",
        default=[],
        help="removed in v6; use --stage-json with explicit owned_paths",
    )
    plan.add_argument(
        "--stage-json",
        action="append",
        default=[],
        help="typed stage object with id, agent, role, success_criteria, criterion_ids, benchmark_criteria, depends_on, owned_paths, approval_categories, feedback_checks, budget",
    )
    plan.add_argument("--max-parallel", type=int, default=3)
    plan.add_argument("--issue", type=int, default=0)
    sub.add_parser("next", parents=[common])
    sub.add_parser("ready", parents=[common])
    claim = sub.add_parser("claim", parents=[common])
    claim.add_argument("--stage", required=True)
    report = sub.add_parser("report", parents=[common])
    report.add_argument("--path", required=True)
    sub.add_parser("board", parents=[common])
    sub.add_parser("status", parents=[common])
    pair = sub.add_parser("pair", parents=[common])
    pair.add_argument("--stage", required=True)
    pair.add_argument("--reviewer", default="tech-lead")
    pr = sub.add_parser("pr", parents=[common])
    pr.add_argument("--number", type=int, required=True)
    ingest = sub.add_parser("ingest", parents=[common])
    ingest.add_argument("--kind", required=True)
    ingest.add_argument("--stage", default="")
    ingest.add_argument("--check", default="")
    ingest.add_argument("--comment", default="")
    feedback = sub.add_parser("feedback")
    feedback_cmds = feedback.add_subparsers(dest="feedback_cmd", required=True)
    feedback_cmds.add_parser("list", parents=[common])
    feedback_assign = feedback_cmds.add_parser("assign", parents=[common])
    feedback_assign.add_argument("--event-id", required=True)
    feedback_assign.add_argument("--stage", required=True)
    approval = sub.add_parser("approval")
    approval_cmds = approval.add_subparsers(dest="approval_cmd", required=True)
    approval_cmds.add_parser("list", parents=[common])
    approval_grant = approval_cmds.add_parser("grant", parents=[common])
    approval_grant.add_argument("--stage", required=True)
    approval_grant.add_argument("--category", required=True)
    criterion = sub.add_parser("criterion")
    criterion_cmds = criterion.add_subparsers(dest="criterion_cmd", required=True)
    criterion_cmds.add_parser("list", parents=[common])
    criterion_waive = criterion_cmds.add_parser("waive", parents=[common])
    criterion_waive.add_argument("--stage", required=True)
    criterion_waive.add_argument("--criterion", required=True)
    criterion_waive.add_argument("--reason", required=True)
    checkpoint = sub.add_parser("checkpoint")
    checkpoint_cmds = checkpoint.add_subparsers(dest="checkpoint_cmd", required=True)
    checkpoint_cmds.add_parser("list", parents=[common])
    checkpoint_open = checkpoint_cmds.add_parser("open", parents=[common])
    checkpoint_open.add_argument("--stage", required=True)
    checkpoint_open.add_argument("--id", required=True)
    checkpoint_open.add_argument("--question", required=True)
    checkpoint_open.add_argument("--risk", required=True)
    checkpoint_open.add_argument("--option-json", action="append", default=[])
    checkpoint_open.add_argument("--recommended", required=True)
    checkpoint_resolve = checkpoint_cmds.add_parser("resolve", parents=[common])
    checkpoint_resolve.add_argument("--id", required=True)
    checkpoint_resolve.add_argument("--option", required=True)
    checkpoint_resolve.add_argument("--note", default="")
    loop = sub.add_parser("loop")
    loop_cmds = loop.add_subparsers(dest="loop_cmd", required=True)
    loop_cmds.add_parser("list", parents=[common])
    retry = sub.add_parser("retry")
    retry_cmds = retry.add_subparsers(dest="retry_cmd", required=True)
    retry_cmds.add_parser("list", parents=[common])
    retry_request = retry_cmds.add_parser("request", parents=[common])
    retry_request.add_argument("--stage", required=True)
    retry_request.add_argument(
        "--source",
        required=True,
        choices=("stage-return", "verification", "ci", "review"),
    )
    retry_request.add_argument("--reason", required=True)
    retry_request.add_argument("--event-id", required=True)
    recovery = sub.add_parser("recovery")
    recovery_cmds = recovery.add_subparsers(dest="recovery_cmd", required=True)
    recovery_cmds.add_parser("list", parents=[common])
    recovery_interrupt = recovery_cmds.add_parser("interrupt", parents=[common])
    recovery_interrupt.add_argument("--stage", required=True)
    recovery_interrupt.add_argument(
        "--source",
        required=True,
        choices=("user", "process-exit", "runtime-error", "host-restart"),
    )
    recovery_interrupt.add_argument("--reason", required=True)
    recovery_interrupt.add_argument("--event-id", required=True)
    recovery_resolve = recovery_cmds.add_parser("resolve", parents=[common])
    recovery_resolve.add_argument("--event-id", required=True)
    recovery_resolve.add_argument(
        "--action", required=True, choices=("continue", "stop")
    )
    recovery_resolve.add_argument("--note", default="")
    transition = sub.add_parser("transition")
    transition_cmds = transition.add_subparsers(
        dest="transition_cmd", required=True
    )
    transition_cmds.add_parser("list", parents=[common])
    observe = sub.add_parser("observe")
    observe_cmds = observe.add_subparsers(dest="observe_cmd", required=True)
    observe_cmds.add_parser("list", parents=[common])
    observe_cmds.add_parser("verify", parents=[common])
    observe_cmds.add_parser("repair", parents=[common])
    context = sub.add_parser("context")
    context_cmds = context.add_subparsers(dest="context_cmd", required=True)
    context_build = context_cmds.add_parser("build", parents=[common])
    context_build.add_argument("--stage", required=True)
    context_build.add_argument("--spec", default="")
    context_build.add_argument("--max-tokens", type=int)
    context_show = context_cmds.add_parser("show", parents=[common])
    context_show.add_argument("--stage", required=True)
    context_verify = context_cmds.add_parser("verify", parents=[common])
    context_verify.add_argument("--stage", required=True)
    budget = sub.add_parser("budget")
    budget_cmds = budget.add_subparsers(dest="budget_cmd", required=True)
    budget_cmds.add_parser("list", parents=[common])
    budget_record = budget_cmds.add_parser("record", parents=[common])
    budget_record.add_argument("--stage", required=True)
    budget_record.add_argument("--seconds", type=float, required=True)
    budget_record.add_argument("--tool-calls", type=int, required=True)
    budget_record.add_argument("--turns", type=int, required=True)
    budget_record.add_argument("--tokens", type=int, required=True)
    budget_record.add_argument("--usd", type=float, required=True)
    budget_record.add_argument("--event-id", default="")
    sprint_common = argparse.ArgumentParser(add_help=False)
    sprint_common.add_argument("--root", required=True)
    sprint_common.add_argument("--id", required=True)
    sprint = sub.add_parser("sprint")
    sprint_cmds = sprint.add_subparsers(dest="sprint_cmd", required=True)
    start = sprint_cmds.add_parser("start", parents=[sprint_common])
    start.add_argument("--goal", required=True)
    start.add_argument("--wip", type=int, required=True)
    sprint_cmds.add_parser("board", parents=[sprint_common])
    sprint_cmds.add_parser("status", parents=[sprint_common])
    close = sprint_cmds.add_parser("close", parents=[sprint_common])
    close.add_argument("--force", action="store_true")
    lesson = sub.add_parser("lesson")
    lesson_cmds = lesson.add_subparsers(dest="lesson_cmd", required=True)
    lesson_list = lesson_cmds.add_parser("list")
    lesson_list.add_argument("--root", required=True)
    lesson_approve = lesson_cmds.add_parser("approve")
    lesson_approve.add_argument("--root", required=True)
    lesson_approve.add_argument("--id", required=True)
    return parser


def _stages_from_args(raw_stages, raw_json_stages=()):
    stages = []
    if raw_stages:
        raise SystemExit(
            "--stage was removed in v6; use --stage-json with explicit owned_paths"
        )
    allowed = {
        "id", "agent", "role", "success_criteria", "depends_on", "owned_paths",
        "approval_categories", "criterion_ids", "benchmark_criteria", "feedback_checks",
        "budget",
    }
    for raw in raw_json_stages:
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--stage-json is invalid JSON: {exc.msg}") from None
        if not isinstance(spec, dict) or set(spec) - allowed:
            raise SystemExit("--stage-json contains unknown fields")
        missing = {"id", "agent", "success_criteria", "owned_paths"} - set(spec)
        if missing:
            raise SystemExit(
                f"--stage-json missing required fields: {', '.join(sorted(missing))}"
            )
        stages.append(
            kernel.StageSpec(
                id=spec["id"],
                agent=spec["agent"],
                role=spec.get("role", "writer"),
                success_criteria=spec["success_criteria"],
                depends_on=spec.get("depends_on", []),
                owned_paths=spec["owned_paths"],
                approval_categories=spec.get("approval_categories", []),
                budget=spec.get("budget", {}),
                criterion_ids=spec.get("criterion_ids", []),
                benchmark_criteria=spec.get("benchmark_criteria", []),
                feedback_checks=spec.get("feedback_checks", []),
            )
        )
    return stages


def _checkpoint_options(raw_options):
    options = []
    for raw in raw_options:
        try:
            option = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--option-json is invalid JSON: {exc.msg}") from None
        if not isinstance(option, dict):
            raise SystemExit("--option-json must be an object")
        options.append(option)
    return options


def _sprint_main(args):
    if args.sprint_cmd == "start":
        kernel.sprint_start(args.root, id=args.id, goal=args.goal, wip=args.wip)
        return 0
    if args.sprint_cmd == "board":
        print(kernel.sprint_text(args.root, args.id), end="")
        return 0
    if args.sprint_cmd == "status":
        print(kernel.load_sprint(args.root, args.id).status)
        return 0
    if args.sprint_cmd == "close":
        kernel.sprint_close(args.root, args.id, force=args.force)
        return 0
    raise SystemExit(2)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "plan":
            runner = ProcessRunner() if args.issue else None
            delivery = kernel.plan(
                root=args.root,
                name=args.name,
                done_when=args.done_when,
                stages=_stages_from_args(args.stage, args.stage_json),
                sprint=args.sprint,
                issue=args.issue,
                runner=runner,
                max_parallel=args.max_parallel,
            )
            if delivery.rules_printed:
                for rule in delivery.rules_printed:
                    print(f"RULES: {rule}")
            else:
                print("RULES: none")
            return 0
        if args.cmd == "next":
            print(kernel.next_agent(args.root, args.name))
            return 0
        if args.cmd == "ready":
            feedback_events = kernel.feedback_rows(args.root, args.name)["events"]
            ready = [
                {
                    "id": stage.id,
                    "agent": stage.agent,
                    "role": stage.role,
                    "owned_paths": stage.owned_paths,
                    "feedback_checks": stage.feedback_checks,
                    "budget": stage.budget,
                    "criteria": kernel.criterion_rows_for_stage(stage),
                    "attempt": stage.attempts + 1,
                    "retry": (
                        {
                            "source": stage.retry_source,
                            "reason": stage.retry_reason,
                        }
                        if stage.retry_reason
                        else None
                    ),
                    "recovery": (
                        {
                            "event_id": stage.recovery_event_id,
                            "source": stage.recovery_source,
                            "reason": stage.recovery_reason,
                        }
                        if stage.recovery_reason
                        else None
                    ),
                    "feedback": [
                        event
                        for event in feedback_events
                        if event.get("stage") == stage.id
                        and event.get("status") == "open"
                    ],
                }
                for stage in kernel.ready_stages(args.root, args.name)
            ]
            print(json.dumps(ready, separators=(",", ":")))
            return 0
        if args.cmd == "claim":
            stage = kernel.claim_stage(args.root, args.name, args.stage)
            print(f"AGENT: {stage.agent}")
            return 0
        if args.cmd == "report":
            kernel.report(args.root, args.name, args.path, runner=ProcessRunner())
            return 0
        if args.cmd == "board":
            print(kernel.board_line(kernel.load(args.root, args.name)))
            return 0
        if args.cmd == "status":
            print(kernel.load(args.root, args.name).status)
            return 0
        if args.cmd == "pair":
            kernel.pair(args.root, args.name, args.stage, reviewer=args.reviewer)
            return 0
        if args.cmd == "pr":
            kernel.record_pr(args.root, args.name, args.number, ProcessRunner())
            return 0
        if args.cmd == "ingest":
            result = kernel.ingest(
                args.root,
                args.name,
                kind=args.kind,
                stage_id=args.stage,
                check=args.check,
                comment=args.comment,
                runner=ProcessRunner(),
            )
            print(json.dumps(result, separators=(",", ":")))
            return 0
        if args.cmd == "feedback":
            if args.feedback_cmd == "list":
                print(json.dumps(kernel.feedback_rows(args.root, args.name)))
                return 0
            if args.feedback_cmd == "assign":
                result = kernel.assign_feedback(
                    args.root,
                    args.name,
                    args.event_id,
                    args.stage,
                )
                print(json.dumps(result, separators=(",", ":")))
                return 0
            return 0
        if args.cmd == "approval":
            if args.approval_cmd == "list":
                print(json.dumps(kernel.approval_rows(args.root, args.name)))
                return 0
            if args.approval_cmd == "grant":
                approval = kernel.approve_stage_action(
                    args.root,
                    args.name,
                    args.stage,
                    args.category,
                )
                print(
                    f"APPROVED: {args.stage} {approval['category']} "
                    f"by {approval['by']} at {approval['at']}"
                )
                return 0
        if args.cmd == "criterion":
            if args.criterion_cmd == "list":
                print(json.dumps(kernel.criterion_rows(args.root, args.name)))
                return 0
            if args.criterion_cmd == "waive":
                waiver = kernel.waive_stage_criterion(
                    args.root,
                    args.name,
                    args.stage,
                    args.criterion,
                    args.reason,
                )
                print(
                    f"WAIVED: {args.stage} {waiver['criterion']} "
                    f"by {waiver['by']} at {waiver['at']}"
                )
                return 0
        if args.cmd == "checkpoint":
            if args.checkpoint_cmd == "list":
                print(json.dumps(kernel.checkpoint_rows(args.root, args.name)))
                return 0
            if args.checkpoint_cmd == "open":
                checkpoint = kernel.open_checkpoint(
                    args.root,
                    args.name,
                    args.stage,
                    args.id,
                    args.question,
                    args.risk,
                    _checkpoint_options(args.option_json),
                    args.recommended,
                )
                print(
                    f"CHECKPOINT: {checkpoint['id']} pending for "
                    f"{checkpoint['stage']}"
                )
                return 0
            if args.checkpoint_cmd == "resolve":
                checkpoint = kernel.resolve_checkpoint(
                    args.root,
                    args.name,
                    args.id,
                    args.option,
                    note=args.note,
                )
                answer = checkpoint["answer"]
                print(
                    f"RESOLVED: {checkpoint['id']} {answer['option']} "
                    f"by {answer['by']} at {answer['at']}"
                )
                return 0
        if args.cmd == "loop":
            if args.loop_cmd == "list":
                print(json.dumps(kernel.loop_rows(args.root, args.name)))
                return 0
        if args.cmd == "retry":
            if args.retry_cmd == "list":
                print(json.dumps(kernel.retry_rows(args.root, args.name)))
                return 0
            if args.retry_cmd == "request":
                event = kernel.request_retry(
                    args.root,
                    args.name,
                    args.stage,
                    source=args.source,
                    reason=args.reason,
                    event_id=args.event_id,
                )
                print(
                    f"RETRY: {event['stage']} {event['action']} "
                    f"event={event['event_id']}"
                )
                return 0
        if args.cmd == "recovery":
            if args.recovery_cmd == "list":
                print(json.dumps(kernel.recovery_rows(args.root, args.name)))
                return 0
            if args.recovery_cmd == "interrupt":
                event = kernel.interrupt_stage(
                    args.root,
                    args.name,
                    args.stage,
                    source=args.source,
                    reason=args.reason,
                    event_id=args.event_id,
                )
                print(
                    f"RECOVERY: {event['stage']} {event['status']} "
                    f"event={event['event_id']}"
                )
                return 0
            if args.recovery_cmd == "resolve":
                event = kernel.resolve_recovery(
                    args.root,
                    args.name,
                    args.event_id,
                    action=args.action,
                    note=args.note,
                )
                print(
                    f"RECOVERY: {event['stage']} {event['status']} "
                    f"event={event['event_id']}"
                )
                return 0
        if args.cmd == "transition":
            if args.transition_cmd == "list":
                print(json.dumps(kernel.transition_rows(args.root, args.name)))
                return 0
        if args.cmd == "observe":
            if args.observe_cmd == "list":
                print(json.dumps(kernel.observability_rows(args.root, args.name)))
                return 0
            if args.observe_cmd == "verify":
                result = kernel.observability_status(args.root, args.name)
                print(json.dumps(result, separators=(",", ":")))
                if result["status"] == "unhealthy":
                    return 1
                return 0
            if args.observe_cmd == "repair":
                result = kernel.repair_observability_views(args.root, args.name)
                print(json.dumps(result, separators=(",", ":")))
                return 0
        if args.cmd == "context":
            if args.context_cmd == "build":
                result = context_packets.build(
                    args.root,
                    args.name,
                    args.stage,
                    spec_path=args.spec,
                    max_tokens=args.max_tokens,
                )
                print(json.dumps(result, separators=(",", ":")))
                return 0
            if args.context_cmd == "show":
                print(context_packets.show(args.root, args.name, args.stage), end="")
                return 0
            if args.context_cmd == "verify":
                result = context_packets.verify(args.root, args.name, args.stage)
                print(json.dumps(result, separators=(",", ":")))
                return 0
        if args.cmd == "budget":
            if args.budget_cmd == "list":
                print(json.dumps(kernel.budget_rows(args.root, args.name)))
                return 0
            if args.budget_cmd == "record":
                delivery = kernel.load(args.root, args.name)
                stage = next(
                    (item for item in delivery.stages if item.id == args.stage),
                    None,
                )
                if stage is None:
                    raise kernel.PlanError(f"stage {args.stage} is missing")
                recorded = kernel.record_stage_usage(
                    args.root,
                    stage.agent,
                    {
                        "seconds": args.seconds,
                        "tool_calls": args.tool_calls,
                        "turns": args.turns,
                        "tokens": args.tokens,
                        "cost_usd": args.usd,
                    },
                    event_id=args.event_id,
                    expected_target=(args.name, args.stage),
                )
                if recorded is None or recorded.id != args.stage:
                    raise kernel.PlanError(f"stage {args.stage} is not running")
                print(f"BUDGET: {args.stage} recorded")
                return 0
        if args.cmd == "sprint":
            return _sprint_main(args)
        if args.cmd == "lesson":
            if args.lesson_cmd == "list":
                print(kernel.render_lessons(kernel._load_lessons(args.root)), end="")
                return 0
            if args.lesson_cmd == "approve":
                lesson = kernel.approve_lesson(args.root, args.id)
                print(f"APPROVED: {lesson['id']} {lesson['text']}")
                return 0
    except (kernel.PlanError, context_packets.ContextPacketError) as exc:
        raise SystemExit(str(exc)) from None
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
