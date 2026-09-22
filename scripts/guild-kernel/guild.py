#!/usr/bin/env python3
"""Guild kernel CLI — plan, next, report, board, status, sprint."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kernel  # noqa: E402


class ProcessRunner:
    def run(self, cwd, cmd):
        completed = subprocess.run(cmd, cwd=cwd, shell=True)
        return completed.returncode


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
        help="id,agent,role[,dep+dep][,criterion|criterion] — repeatable",
    )
    sub.add_parser("next", parents=[common])
    report = sub.add_parser("report", parents=[common])
    report.add_argument("--path", required=True)
    sub.add_parser("board", parents=[common])
    sub.add_parser("status", parents=[common])
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
    return parser


def _stages_from_args(raw_stages):
    stages = []
    help_form = "id,agent,role[,dep+dep][,criterion|criterion]"
    for raw in raw_stages:
        parts = raw.split(",")
        if len(parts) < 2:
            raise SystemExit(
                f"--stage needs at least id and agent ({help_form})"
            )
        sid, agent = parts[0].strip(), parts[1].strip()
        role = parts[2].strip() if len(parts) > 2 and parts[2].strip() else "writer"
        depends = (
            [dep for dep in parts[3].strip().split("+") if dep]
            if len(parts) > 3
            else []
        )
        criteria_raw = ",".join(parts[4:])
        criteria = [item.strip() for item in criteria_raw.split("|") if item.strip()]
        stages.append(kernel.StageSpec(sid, agent, role, criteria, depends))
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
            delivery = kernel.plan(
                root=args.root,
                name=args.name,
                done_when=args.done_when,
                stages=_stages_from_args(args.stage),
                sprint=args.sprint,
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
        if args.cmd == "report":
            kernel.report(args.root, args.name, args.path, runner=ProcessRunner())
            return 0
        if args.cmd == "board":
            print(kernel.board_line(kernel.load(args.root, args.name)))
            return 0
        if args.cmd == "status":
            print(kernel.load(args.root, args.name).status)
            return 0
        if args.cmd == "sprint":
            return _sprint_main(args)
    except kernel.PlanError as exc:
        raise SystemExit(str(exc)) from None
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
