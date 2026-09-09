from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field

_LABELS = ("STATUS", "DID", "VERIFIED", "NOT-CHECKED", "FLAGS", "NEXT")
_COMMAND_MARKERS = ("/", "\\", "artisan", "vendor/bin", "php", "pint", "phpstan", "pest", "./")


class ReportError(Exception):
    pass


@dataclass
class StageSpec:
    id: str
    agent: str
    role: str
    success_criteria: list
    depends_on: list
    status: str = "queued"
    did: list = field(default_factory=list)


@dataclass
class Delivery:
    name: str
    done_when: str
    cap: int
    status: str
    stages: list
    spawns: int = 0


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
    if _state_path(root, name).is_file():
        existing = load(root, name)
        if existing.status == "running":
            return existing
    delivery = Delivery(
        name=name,
        done_when=done_when,
        cap=len(stages) + 2,
        status="running",
        stages=list(stages),
        spawns=0,
    )
    save(root, delivery)
    return delivery


def _did_on_disk(root, stage):
    root = pathlib.Path(root)
    return any((root / path).is_file() for path in stage.did if path)


def _cap_hit(delivery):
    return delivery.spawns >= delivery.cap and delivery.status != "done"


def next_agent(root, name):
    delivery = load(root, name)
    if delivery.status == "stopped" or _cap_hit(delivery):
        if _cap_hit(delivery) and delivery.status != "stopped":
            delivery.status = "stopped"
            save(root, delivery)
        return "STOP"
    by_id = {stage.id: stage for stage in delivery.stages}
    for stage in delivery.stages:
        deps_met = all(
            by_id[dep].status in ("done", "skipped") for dep in stage.depends_on
        )
        if not deps_met:
            continue
        if stage.status in ("queued", "running"):
            return stage.agent
        if (
            stage.role == "writer"
            and stage.status == "done"
            and not _did_on_disk(root, stage)
        ):
            return stage.agent
    return "STOP"


def _parse_labels(text):
    fields = {label: [] for label in _LABELS}
    for line in text.splitlines():
        for label in _LABELS:
            prefix = f"{label}:"
            if line.startswith(prefix):
                fields[label].append(line[len(prefix):].strip())
                break
    return fields


def _is_command(text):
    return bool(text) and any(marker in text for marker in _COMMAND_MARKERS)


def report(root, name, path, runner):
    fields = _parse_labels(pathlib.Path(path).read_text())
    commands = []
    for raw in fields["VERIFIED"]:
        cmd = raw.split(" →", 1)[0].strip()
        if not _is_command(cmd):
            raise ReportError("VERIFIED must be a command")
        commands.append(cmd)
    if not commands:
        raise ReportError("VERIFIED must be a command")

    for cmd in commands:
        if runner.run(root, cmd) != 0:
            raise ReportError(f"command failed: {cmd}")

    delivery = load(root, name)
    agent = pathlib.Path(path).stem
    not_checked = " ".join(fields["NOT-CHECKED"])
    did_paths = [item for item in fields["DID"] if item and item != "none"]
    for stage in delivery.stages:
        if stage.agent != agent:
            continue
        for criterion in stage.success_criteria:
            if criterion and criterion in not_checked:
                raise ReportError(f"NOT-CHECKED names success criterion: {criterion}")
        stage.did = did_paths
        stage.status = "done"
    delivery.spawns += 1
    if _cap_hit(delivery):
        delivery.status = "stopped"
    save(root, delivery)
    return delivery
