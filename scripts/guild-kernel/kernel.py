from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass


@dataclass
class StageSpec:
    id: str
    agent: str
    role: str
    success_criteria: list
    depends_on: list
    status: str = "queued"


@dataclass
class Delivery:
    name: str
    done_when: str
    cap: int
    status: str
    stages: list


def _state_path(root, name):
    return pathlib.Path(root) / "docs" / "delivery" / name / "kernel.json"


def save(root, delivery):
    path = _state_path(root, delivery.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(delivery), indent=2) + "\n")


def load(root, name):
    data = json.loads(_state_path(root, name).read_text())
    stages = [StageSpec(**stage) for stage in data.pop("stages")]
    return Delivery(stages=stages, **data)


def plan(*, root, name, done_when, stages):
    delivery = Delivery(
        name=name,
        done_when=done_when,
        cap=len(stages) + 2,
        status="running",
        stages=list(stages),
    )
    save(root, delivery)
    return delivery


def next_agent(root, name):
    delivery = load(root, name)
    by_id = {stage.id: stage for stage in delivery.stages}
    for stage in delivery.stages:
        if stage.status not in ("queued", "running"):
            continue
        deps_met = all(
            by_id[dep].status in ("done", "skipped") for dep in stage.depends_on
        )
        if deps_met:
            return stage.agent
    return "STOP"
