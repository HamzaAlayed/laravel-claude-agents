from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field

_LABELS = ("STATUS", "DID", "VERIFIED", "NOT-CHECKED", "FLAGS", "NEXT")
_COMMAND_MARKERS = ("/", "\\", "artisan", "vendor/bin", "php", "pint", "phpstan", "pest", "./")
_BOARD_MARK = {
    "done": "✔",
    "running": "▶",
    "queued": "·",
    "failed": "✖",
    "skipped": "·",
}
AGENTS = frozenset(
    {
        "backend-developer",
        "business-analyst",
        "database-developer",
        "delivery-coordinator",
        "devops-engineer",
        "frontend-developer",
        "mobile-developer",
        "package-developer",
        "peer-router",
        "performance-engineer",
        "product-owner",
        "qa-engineer",
        "scrum-master",
        "security-engineer",
        "solution-architect",
        "tech-lead",
        "technical-writer",
        "ui-ux-designer",
    }
)


class ReportError(Exception):
    pass


class PlanError(Exception):
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
    verified: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    pair: str = ""
    awaiting_pair: bool = False
    reopens: int = 0


@dataclass
class Delivery:
    name: str
    done_when: str
    cap: int
    status: str
    stages: list
    spawns: int = 0
    sprint: str = ""
    rules_printed: list = field(default_factory=list)
    issue: dict = field(default_factory=dict)
    pr: dict = field(default_factory=dict)
    repo: str = ""


def _state_path(root, name):
    return pathlib.Path(root) / "docs" / "delivery" / name / "kernel.json"


def save(root, delivery):
    path = _state_path(root, delivery.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(delivery), indent=2) + "\n")


def load(root, name):
    data = json.loads(_state_path(root, name).read_text())
    data.setdefault("sprint", "")
    data.setdefault("rules_printed", [])
    data.setdefault("issue", {})
    data.setdefault("pr", {})
    data.setdefault("repo", "")
    stages = []
    for stage in data.pop("stages"):
        stage.setdefault("flags", [])
        stage.setdefault("pair", "")
        stage.setdefault("awaiting_pair", False)
        stage.setdefault("reopens", 0)
        stages.append(StageSpec(**stage))
    return Delivery(stages=stages, **data)


def _norm_flag(text):
    return " ".join(text.strip().lower().split())


def _lessons_path(root):
    return pathlib.Path(root) / "docs" / "team" / "lessons.json"


def _load_lessons(root):
    path = _lessons_path(root)
    if not path.is_file():
        return {"lessons": []}
    return json.loads(path.read_text())


def _save_lessons(root, data):
    path = _lessons_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def render_lessons(data):
    taught = [lesson for lesson in data.get("lessons", []) if lesson.get("status") == "taught"]
    if not taught:
        return "LESSONS: none\n"
    lines = ["LESSONS:"]
    for lesson in taught:
        scope = ", ".join(lesson.get("scope", []))
        lines.append(f"RULE: {lesson['text']}")
        lines.append(f"SCOPE: {scope}")
        lines.append(f"STATUS: taught")
    return "\n".join(lines) + "\n"


def write_lessons_view(root, data):
    path = pathlib.Path(root) / "docs" / "team" / "lessons.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_lessons(data))


def _record_lesson(root, delivery_name, agent, text):
    norm = _norm_flag(text)
    if not norm or norm == "none":
        return
    data = _load_lessons(root)
    for lesson in data["lessons"]:
        if lesson.get("norm") != norm:
            continue
        if delivery_name in lesson.get("deliveries", []):
            write_lessons_view(root, data)
            return
        lesson["deliveries"].append(delivery_name)
        if agent not in lesson["scope"]:
            lesson["scope"].append(agent)
        if len(lesson["deliveries"]) >= 2:
            lesson["status"] = "taught"
        _save_lessons(root, data)
        write_lessons_view(root, data)
        return
    data["lessons"].append(
        {
            "norm": norm,
            "text": text,
            "status": "seen",
            "scope": [agent],
            "deliveries": [delivery_name],
        }
    )
    _save_lessons(root, data)
    write_lessons_view(root, data)


def _taught_rules(root, stages):
    data = _load_lessons(root)
    agents = {stage.agent for stage in stages}
    rules = []
    for lesson in data.get("lessons", []):
        if lesson.get("status") != "taught":
            continue
        if agents.intersection(lesson.get("scope", [])):
            rules.append(lesson["text"])
    return rules


def board_line(delivery):
    header = (
        f"{len(delivery.stages)} stages · cap: {delivery.cap} spawns · "
        f"done when: {delivery.done_when}"
    )
    lanes = []
    for stage in delivery.stages:
        mark = _BOARD_MARK.get(stage.status, "·")
        label = f"pair:{stage.pair}" if stage.awaiting_pair and stage.pair else stage.agent
        lanes.append(f"{stage.id} {mark} {label}")
    return " · ".join([header, *lanes]) if lanes else header


def render_close(delivery, *, verified="none", not_checked="none"):
    issue_url = delivery.issue.get("url") or "none"
    pr_url = delivery.pr.get("url") or "none"
    return (
        f"VERIFIED: {verified}\n"
        f"NOT-CHECKED: {not_checked}\n"
        f"STATUS: {delivery.status}\n"
        f"BOARD: {board_line(delivery)}\n"
        f"ISSUE: {issue_url}\n"
        f"PR: {pr_url}\n"
    )


def render_graph(delivery):
    nodes = ", ".join(stage.agent for stage in delivery.stages)
    by_id = {stage.id: stage for stage in delivery.stages}
    edges = []
    for stage in delivery.stages:
        for dep in stage.depends_on:
            upstream = by_id.get(dep)
            if upstream:
                edges.append(f"{upstream.agent} -> {stage.agent}")
    return (
        f"NODES: {nodes}\n"
        f"EDGES: {', '.join(edges) if edges else 'none'}\n"
        f"PARALLEL: none\n"
        f"ON-FAIL: stop\n"
    )


def write_views(root, delivery, *, verified="none", not_checked="none"):
    folder = pathlib.Path(root) / "docs" / "delivery" / delivery.name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "close.md").write_text(
        render_close(delivery, verified=verified, not_checked=not_checked)
    )
    (folder / "graph.md").write_text(render_graph(delivery))


def _has_criteria(stage):
    return any(str(item).strip() for item in stage.success_criteria)


def _wip_count(root, sprint):
    count = 0
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            continue
        if load(root, name).status == "running":
            count += 1
    return count


def running_sprints(root):
    base = pathlib.Path(root) / "docs" / "sprints"
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.glob("*/sprint.json")):
        sprint = Sprint(**json.loads(path.read_text()))
        if sprint.status == "running":
            found.append(sprint)
    return found


def _resolve_sprint(root, sprint_id):
    running = running_sprints(root)
    if len(running) > 1:
        raise PlanError("two or more sprints are running")
    if sprint_id:
        path = _sprint_dir(root, sprint_id) / "sprint.json"
        if not path.is_file():
            raise PlanError(f"sprint {sprint_id} is missing")
        chosen = load_sprint(root, sprint_id)
        if chosen.status != "running":
            raise PlanError(f"sprint {sprint_id} is {chosen.status}")
        if any(sprint.id != chosen.id for sprint in running):
            raise PlanError("two or more sprints are running")
        return chosen
    if len(running) == 1:
        return running[0]
    return None


def _attach_sprint(root, name, sprint_id):
    chosen = _resolve_sprint(root, sprint_id)
    if chosen is None:
        return ""
    if _wip_count(root, chosen) >= chosen.wip:
        raise PlanError("sprint WIP is full")
    return chosen.id


def _remember_story(root, sprint_id, name):
    if not sprint_id:
        return
    sprint = load_sprint(root, sprint_id)
    if name not in sprint.stories:
        sprint.stories.append(name)
        save_sprint(root, sprint)
    write_sprint_view(root, sprint)


def plan(*, root, name, done_when, stages, sprint=""):
    if _state_path(root, name).is_file():
        existing = load(root, name)
        existing.rules_printed = _taught_rules(root, existing.stages)
        save(root, existing)
        write_views(root, existing, not_checked=existing.done_when or "none")
        return existing
    if not done_when.strip() or any(not _has_criteria(stage) for stage in stages):
        raise PlanError("plan requires nonempty done_when and success criteria")
    sprint_id = _attach_sprint(root, name, sprint)
    delivery = Delivery(
        name=name,
        done_when=done_when,
        cap=len(stages) + 2,
        status="running",
        stages=list(stages),
        spawns=0,
        sprint=sprint_id,
    )
    delivery.rules_printed = _taught_rules(root, delivery.stages)
    save(root, delivery)
    write_views(root, delivery, not_checked=done_when or "none")
    _remember_story(root, sprint_id, name)
    return delivery


def _did_on_disk(root, stage):
    root = pathlib.Path(root)
    return any((root / path).is_file() for path in stage.did if path)


def _cap_hit(delivery):
    return delivery.spawns >= delivery.cap and delivery.status != "done"


def next_agent(root, name):
    delivery = load(root, name)
    if delivery.status in ("stopped", "done") or _cap_hit(delivery):
        if _cap_hit(delivery) and delivery.status not in ("stopped", "done"):
            delivery.status = "stopped"
            save(root, delivery)
            write_views(root, delivery)
        return "STOP"
    by_id = {stage.id: stage for stage in delivery.stages}
    for stage in delivery.stages:
        deps_met = all(
            by_id[dep].status in ("done", "skipped") for dep in stage.depends_on
        )
        if not deps_met:
            continue
        if stage.awaiting_pair and stage.pair:
            return stage.pair
        if stage.status in ("queued", "running"):
            return stage.agent
        if (
            stage.role == "writer"
            and stage.status == "done"
            and not _did_on_disk(root, stage)
        ):
            return stage.agent
    return "STOP"


def pair(root, name, stage_id, *, reviewer="tech-lead"):
    delivery = load(root, name)
    stage = next((item for item in delivery.stages if item.id == stage_id), None)
    if stage is None:
        raise PlanError(f"stage {stage_id} is missing")
    if stage.status not in ("queued", "running"):
        raise PlanError(f"stage {stage_id} is {stage.status}")
    if reviewer not in AGENTS:
        raise PlanError(f"unknown reviewer {reviewer}")
    if reviewer == stage.agent:
        raise PlanError(f"reviewer cannot be the stage agent {reviewer}")
    if stage.pair and stage.pair != reviewer:
        raise PlanError(f"stage {stage_id} already paired with {stage.pair}")
    if stage.pair == reviewer:
        return delivery
    stage.pair = reviewer
    save(root, delivery)
    return delivery


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
    flag_texts = [
        raw
        for raw in fields["FLAGS"]
        if _norm_flag(raw) and _norm_flag(raw) != "none"
    ]
    matched = False
    for stage in delivery.stages:
        if stage.awaiting_pair and stage.pair == agent:
            matched = True
            for criterion in stage.success_criteria:
                if criterion and criterion in not_checked:
                    raise ReportError(f"NOT-CHECKED names success criterion: {criterion}")
            stage.verified = list(stage.verified) + [
                {"cmd": cmd, "exit": 0} for cmd in commands
            ]
            stage.awaiting_pair = False
            stage.status = "done"
            for flag_text in flag_texts:
                _record_lesson(root, name, agent, flag_text)
            continue
        if stage.agent != agent:
            continue
        if stage.awaiting_pair:
            raise ReportError(f"stage {stage.id} is awaiting pair {stage.pair}")
        matched = True
        for criterion in stage.success_criteria:
            if criterion and criterion in not_checked:
                raise ReportError(f"NOT-CHECKED names success criterion: {criterion}")
        stage.did = did_paths
        stage.verified = [{"cmd": cmd, "exit": 0} for cmd in commands]
        stage.flags = list(flag_texts)
        if stage.pair:
            stage.awaiting_pair = True
            stage.status = "running"
        else:
            stage.status = "done"
        for flag_text in flag_texts:
            _record_lesson(root, name, agent, flag_text)
    if not matched:
        raise ReportError(f"no stage matched report agent {agent}")
    delivery.spawns += 1
    if all(stage.status in ("done", "skipped") for stage in delivery.stages):
        if any(
            stage.status != "skipped"
            and not any(entry.get("exit") == 0 for entry in stage.verified)
            for stage in delivery.stages
        ):
            raise ReportError("DoD requires verified exit 0 on every done stage")
        delivery.status = "done"
    elif _cap_hit(delivery):
        delivery.status = "stopped"
    save(root, delivery)
    write_views(
        root,
        delivery,
        verified=" ".join(commands) if commands else "none",
        not_checked=not_checked or "none",
    )
    if delivery.sprint and (_sprint_dir(root, delivery.sprint) / "sprint.json").is_file():
        write_sprint_view(root, load_sprint(root, delivery.sprint))
    return delivery


@dataclass
class Sprint:
    id: str
    goal: str
    wip: int
    stories: list
    status: str


def _sprint_dir(root, sprint_id):
    return pathlib.Path(root) / "docs" / "sprints" / sprint_id


def save_sprint(root, sprint):
    folder = _sprint_dir(root, sprint.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sprint.json").write_text(json.dumps(asdict(sprint), indent=2) + "\n")


def load_sprint(root, sprint_id):
    data = json.loads((_sprint_dir(root, sprint_id) / "sprint.json").read_text())
    return Sprint(**data)


def _running_sprint(root):
    found = running_sprints(root)
    return found[0] if found else None


def render_sprint(root, sprint):
    lanes = []
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            lanes.append(f"· {name}")
            continue
        mark = _BOARD_MARK.get(load(root, name).status, "·")
        lanes.append(f"{mark} {name}")
    board = " ".join(lanes) if lanes else "none"
    return (
        f"GOAL: {sprint.goal}\n"
        f"WIP: {_wip_count(root, sprint)}/{sprint.wip}\n"
        f"BOARD: {board}\n"
        f"STATUS: {sprint.status}\n"
    )


def write_sprint_view(root, sprint):
    folder = _sprint_dir(root, sprint.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sprint.md").write_text(render_sprint(root, sprint))


def sprint_start(root, *, id, goal, wip):
    existing = _running_sprint(root)
    if existing is not None:
        write_sprint_view(root, existing)
        return existing
    sprint = Sprint(id=id, goal=goal, wip=wip, stories=[], status="running")
    save_sprint(root, sprint)
    write_sprint_view(root, sprint)
    return sprint


def _sprint_blocked(root, sprint):
    for name in sprint.stories:
        if not _state_path(root, name).is_file():
            return True
        if load(root, name).status == "running":
            return True
    return False


def sprint_close(root, sprint_id, *, force=False):
    sprint = load_sprint(root, sprint_id)
    blocked = _sprint_blocked(root, sprint)
    if blocked and not force:
        raise PlanError("sprint close rejected: a story is still running")
    sprint.status = "stopped" if blocked else "done"
    save_sprint(root, sprint)
    write_sprint_view(root, sprint)
    return sprint


def sprint_text(root, sprint_id):
    sprint = load_sprint(root, sprint_id)
    write_sprint_view(root, sprint)
    return (_sprint_dir(root, sprint_id) / "sprint.md").read_text()
