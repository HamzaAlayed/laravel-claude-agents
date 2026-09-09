#!/usr/bin/env python3
"""Guild kernel CLI — plan, next, report, board, status."""

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
    return parser


def _stages_from_args(raw_stages):
    stages = []
    for raw in raw_stages:
        parts = [part.strip() for part in raw.split(",")]
        sid, agent = parts[0], parts[1]
        role = parts[2] if len(parts) > 2 and parts[2] else "writer"
        depends = (
            [dep for dep in parts[3].split("+") if dep]
            if len(parts) > 3
            else []
        )
        criteria = (
            [item for item in parts[4].split("|") if item]
            if len(parts) > 4
            else []
        )
        stages.append(kernel.StageSpec(sid, agent, role, criteria, depends))
    return stages


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "plan":
        kernel.plan(
            root=args.root,
            name=args.name,
            done_when=args.done_when,
            stages=_stages_from_args(args.stage),
        )
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
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
