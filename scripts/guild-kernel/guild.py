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
        help="typed stage object with id, agent, role, success_criteria, depends_on, owned_paths",
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
    ingest.add_argument("--stage", required=True)
    ingest.add_argument("--check", default="")
    ingest.add_argument("--comment", default="")
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
        "id", "agent", "role", "success_criteria", "depends_on", "owned_paths"
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
            )
        )
    return stages


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
            ready = [
                {
                    "id": stage.id,
                    "agent": stage.agent,
                    "role": stage.role,
                    "owned_paths": stage.owned_paths,
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
            kernel.ingest(
                args.root,
                args.name,
                kind=args.kind,
                stage_id=args.stage,
                check=args.check,
                comment=args.comment,
                runner=ProcessRunner(),
            )
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
    except kernel.PlanError as exc:
        raise SystemExit(str(exc)) from None
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
