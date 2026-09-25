#!/usr/bin/env python3
"""Validate and publish one immutable Laravel Guild GitHub release.

The release harness deliberately has no force, delete, or overwrite path. A
partial publication is recoverable by rerunning the same version: an existing
tag must resolve to the requested commit, and an existing release is a no-op.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "release-harness.json"
VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
SHA_RE = re.compile(r"[0-9a-f]{40}")


class ReleaseError(RuntimeError):
    """A release invariant failed and publication must stop."""


class Runner:
    def run(self, argv, *, cwd=ROOT, check=True):
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            text=True,
            capture_output=True,
            shell=False,
        )
        if check and completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ReleaseError(f"command failed ({' '.join(argv)}): {detail}")
        return completed


def _load_config(path=CONFIG_PATH):
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"release harness is invalid: {path}") from exc
    required = {
        "schemaVersion",
        "branch",
        "ciWorkflow",
        "tagPrefix",
        "releaseNotesDirectory",
        "versionFiles",
        "requiredCiJobs",
        "requiredReleaseNoteHeadings",
        "publication",
    }
    if not isinstance(config, dict) or set(config) != required:
        raise ReleaseError("release harness fields do not match the schema")
    if config["schemaVersion"] != 1:
        raise ReleaseError("unsupported release harness schema")
    if config["branch"] != "main" or config["tagPrefix"] != "v":
        raise ReleaseError("release branch and tag prefix must remain main and v")
    _single_line(config["ciWorkflow"], "CI workflow")
    notes_dir = config["releaseNotesDirectory"]
    if (
        not isinstance(notes_dir, str)
        or pathlib.PurePosixPath(notes_dir).is_absolute()
        or ".." in pathlib.PurePosixPath(notes_dir).parts
    ):
        raise ReleaseError("release notes directory must be a safe relative path")
    if config["publication"] != {
        "tagType": "annotated",
        "draft": False,
        "prerelease": False,
        "force": False,
    }:
        raise ReleaseError("release publication must remain annotated and non-force")
    jobs = config["requiredCiJobs"]
    if (
        not isinstance(jobs, list)
        or not jobs
        or len(jobs) != len(set(jobs))
        or not all(
            isinstance(job, str)
            and bool(job)
            and job == job.strip()
            and "\n" not in job
            and "\r" not in job
            for job in jobs
        )
    ):
        raise ReleaseError("required CI jobs must be unique nonempty strings")
    headings = config["requiredReleaseNoteHeadings"]
    if (
        not isinstance(headings, list)
        or not headings
        or len(headings) != len(set(headings))
        or not all(
            isinstance(heading, str)
            and heading.startswith("## ")
            and heading == heading.strip()
            and "\n" not in heading
            and "\r" not in heading
            for heading in headings
        )
    ):
        raise ReleaseError("release note headings must be unique level-two headings")
    files = config["versionFiles"]
    if not isinstance(files, list) or not files:
        raise ReleaseError("versionFiles must be a nonempty list")
    paths = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "field"}:
            raise ReleaseError("versionFiles entries require path and field")
        if (
            not isinstance(item["path"], str)
            or not item["path"]
        ):
            raise ReleaseError("versionFiles paths must stay inside the repository")
        candidate = pathlib.PurePosixPath(item["path"])
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ReleaseError("versionFiles paths must stay inside the repository")
        _single_line(item["field"], "version manifest field")
        paths.append(item["path"])
    if len(paths) != len(set(paths)):
        raise ReleaseError("versionFiles paths must be unique")
    return config


def _nested_value(payload, field):
    value = payload
    for part in field.split("."):
        if isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError) as exc:
                raise ReleaseError(f"manifest field is missing: {field}") from exc
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ReleaseError(f"manifest field is missing: {field}")
    return value


def _version(value):
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise ReleaseError("version must be a stable X.Y.Z value without a v prefix")
    return value


def _single_line(value, label, *, max_length=160):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_length
        or any(char in value for char in "\r\n")
    ):
        raise ReleaseError(f"{label} must be a nonempty single line")
    return value.strip()


def validate_local(root, version, config):
    root = pathlib.Path(root)
    version = _version(version)
    actual = (root / "VERSION").read_text(encoding="utf-8").strip()
    if actual != version:
        raise ReleaseError(f"VERSION says {actual}, requested {version}")

    checked = ["VERSION"]
    for item in config["versionFiles"]:
        if not isinstance(item, dict) or set(item) != {"path", "field"}:
            raise ReleaseError("versionFiles entries require path and field")
        path = root / item["path"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReleaseError(f"version manifest is invalid: {item['path']}") from exc
        found = _nested_value(payload, item["field"])
        if found != version:
            raise ReleaseError(
                f"{item['path']} declares {found}, requested {version}"
            )
        checked.append(item["path"])

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    release_header = re.compile(
        rf"^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})$", re.MULTILINE
    )
    matches = list(release_header.finditer(changelog))
    unreleased = changelog.find("## [Unreleased]")
    if len(matches) != 1 or unreleased < 0 or unreleased > matches[0].start():
        raise ReleaseError("CHANGELOG must contain Unreleased before the dated release")
    try:
        dt.date.fromisoformat(matches[0].group(1))
    except ValueError as exc:
        raise ReleaseError("CHANGELOG release date is not a calendar date") from exc
    checked.append("CHANGELOG.md")

    notes = root / config["releaseNotesDirectory"] / f"{version}.md"
    if not notes.is_file():
        raise ReleaseError(f"release notes are missing: {notes.relative_to(root)}")
    note_text = notes.read_text(encoding="utf-8")
    if not note_text.startswith(f"# Laravel Guild {version}\n"):
        raise ReleaseError("release notes must start with the versioned Guild heading")
    for heading in config["requiredReleaseNoteHeadings"]:
        if f"\n{heading}\n" not in note_text:
            raise ReleaseError(f"release notes are missing heading: {heading}")
    checked.append(notes.relative_to(root).as_posix())
    return {
        "version": version,
        "artifacts": checked,
        "notes": notes.relative_to(root).as_posix(),
    }


def _json_output(completed, label):
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"{label} returned malformed JSON") from exc


def _repository(runner, root, supplied):
    if supplied:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", supplied):
            raise ReleaseError("repository must be owner/name")
        return supplied
    result = runner.run(
        ["gh", "repo", "view", "--json", "nameWithOwner"], cwd=root
    )
    payload = _json_output(result, "gh repo view")
    repo = payload.get("nameWithOwner") if isinstance(payload, dict) else None
    if not isinstance(repo, str) or "/" not in repo:
        raise ReleaseError("gh repo view did not identify owner/name")
    return repo


def _head_and_main(runner, root, config, requested_commit=""):
    dirty = runner.run(["git", "status", "--porcelain"], cwd=root).stdout.strip()
    if dirty:
        raise ReleaseError("release checkout is dirty")
    head = runner.run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    if not SHA_RE.fullmatch(head):
        raise ReleaseError("HEAD is not a full commit SHA")
    if requested_commit and head != requested_commit:
        raise ReleaseError(f"HEAD {head} does not match requested commit {requested_commit}")
    ref = f"refs/heads/{config['branch']}"
    remote = runner.run(["git", "ls-remote", "--heads", "origin", ref], cwd=root)
    rows = [line.split() for line in remote.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != ref:
        raise ReleaseError(f"origin/{config['branch']} could not be resolved exactly")
    if rows[0][0] != head:
        raise ReleaseError(
            f"HEAD {head} is not the immutable origin/{config['branch']} commit"
        )
    return head


def _tag_state(runner, root, tag, commit):
    local_ref = f"refs/tags/{tag}"
    presence = runner.run(
        ["git", "show-ref", "--verify", "--quiet", local_ref],
        cwd=root,
        check=False,
    )
    if presence.returncode not in (0, 1):
        raise ReleaseError(f"could not inspect local tag {tag}")
    local_commit = ""
    if presence.returncode == 0:
        local_commit = runner.run(
            ["git", "rev-list", "-n", "1", tag], cwd=root
        ).stdout.strip()
    if local_commit and local_commit != commit:
        raise ReleaseError(f"local tag {tag} points to {local_commit}, not {commit}")
    if local_commit:
        tag_type = runner.run(["git", "cat-file", "-t", tag], cwd=root).stdout.strip()
        if tag_type != "tag":
            raise ReleaseError(f"local tag {tag} is not annotated")

    remote = runner.run(
        [
            "git",
            "ls-remote",
            "--tags",
            "origin",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        cwd=root,
    )
    direct = ""
    peeled = ""
    for line in remote.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2 or not SHA_RE.fullmatch(parts[0]):
            raise ReleaseError(f"remote tag lookup for {tag} returned malformed data")
        if parts[1] == f"refs/tags/{tag}":
            direct = parts[0]
        elif parts[1] == f"refs/tags/{tag}^{{}}":
            peeled = parts[0]
        else:
            raise ReleaseError(f"remote tag lookup for {tag} returned an unexpected ref")
    if direct and not peeled:
        raise ReleaseError(f"remote tag {tag} is not annotated")
    remote_commit = peeled
    if remote_commit and remote_commit != commit:
        raise ReleaseError(f"remote tag {tag} points to {remote_commit}, not {commit}")
    return {
        "local": bool(local_commit),
        "remote": bool(remote_commit),
        "commit": remote_commit or local_commit or "",
    }


def _release_state(runner, root, repo, tag):
    result = runner.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "name,tagName,url,isDraft,isPrerelease",
        ],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        detail = f"{result.stderr}\n{result.stdout}".lower()
        if "release not found" in detail or "release does not exist" in detail:
            return None
        raise ReleaseError(f"could not inspect existing release {tag}")
    payload = _json_output(result, "gh release view")
    if (
        not isinstance(payload, dict)
        or payload.get("tagName") != tag
        or payload.get("isDraft") is not False
        or payload.get("isPrerelease") is not False
        or not str(payload.get("url", "")).startswith("https://")
    ):
        raise ReleaseError(f"existing release {tag} does not match publication policy")
    return payload


def verify_ci(runner, root, repo, commit, config):
    listed = runner.run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            config["ciWorkflow"],
            "--branch",
            config["branch"],
            "--commit",
            commit,
            "--limit",
            "20",
            "--json",
            "databaseId,headSha,status,conclusion,url,createdAt",
        ],
        cwd=root,
    )
    rows = _json_output(listed, "gh run list")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ReleaseError("gh run list did not return a list")
    matching = [row for row in rows if row.get("headSha") == commit]
    if not matching:
        raise ReleaseError(f"no {config['ciWorkflow']} run exists for {commit}")
    run = max(matching, key=lambda row: row.get("createdAt") or "")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ReleaseError(
            f"CI run {run.get('databaseId')} is {run.get('status')}/{run.get('conclusion')}"
        )
    run_id = run.get("databaseId")
    if not isinstance(run_id, int) or run_id <= 0:
        raise ReleaseError("CI run does not have a valid database ID")
    run_id = str(run_id)
    viewed = runner.run(
        [
            "gh",
            "run",
            "view",
            run_id,
            "--repo",
            repo,
            "--json",
            "status,conclusion,url,jobs",
        ],
        cwd=root,
    )
    details = _json_output(viewed, "gh run view")
    if not isinstance(details, dict):
        raise ReleaseError("gh run view did not return an object")
    if details.get("status") != "completed" or details.get("conclusion") != "success":
        raise ReleaseError(f"CI run {run_id} is not successful")
    jobs = details.get("jobs")
    if not isinstance(jobs, list):
        raise ReleaseError("CI run jobs are missing")
    by_name = {}
    for job in jobs:
        name = job.get("name") if isinstance(job, dict) else None
        if not isinstance(name, str) or not name.strip() or name in by_name:
            raise ReleaseError("CI job names must be present and unique")
        by_name[name] = job
    missing = [name for name in config["requiredCiJobs"] if name not in by_name]
    if missing:
        raise ReleaseError("required CI jobs are missing: " + ", ".join(missing))
    failed = [
        name for name, job in by_name.items()
        if job.get("status") != "completed" or job.get("conclusion") != "success"
    ]
    if failed:
        raise ReleaseError("CI jobs are not successful: " + ", ".join(failed))
    url = details.get("url") or run.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ReleaseError("CI run does not have a valid URL")
    return {
        "id": int(run_id),
        "url": url,
        "jobs": sorted(by_name),
    }


def preflight(root, version, *, repo="", commit="", runner=None, config=None):
    root = pathlib.Path(root)
    runner = runner or Runner()
    config = config or _load_config(root / "config" / "release-harness.json")
    local = validate_local(root, version, config)
    resolved_repo = _repository(runner, root, repo)
    resolved_commit = _head_and_main(runner, root, config, commit)
    tag = f"{config['tagPrefix']}{version}"
    tag_state = _tag_state(runner, root, tag, resolved_commit)
    release = _release_state(runner, root, resolved_repo, tag)
    if release is not None and not tag_state["remote"]:
        raise ReleaseError(f"release {tag} exists without its remote tag")
    ci = verify_ci(runner, root, resolved_repo, resolved_commit, config)
    return {
        "schemaVersion": 1,
        "version": version,
        "tag": tag,
        "commit": resolved_commit,
        "branch": config["branch"],
        "repository": resolved_repo,
        "artifacts": local["artifacts"],
        "notes": local["notes"],
        "ci": ci,
        "tagState": tag_state,
        "release": release,
    }


def _validate_title(title, version):
    title = _single_line(title, "release title")
    prefix = f"Laravel Guild {version} — "
    if not title.startswith(prefix) or len(title) == len(prefix):
        raise ReleaseError(f"release title must start with {prefix}")
    return title


def publish(root, version, title, *, repo="", commit="", receipt="", runner=None):
    root = pathlib.Path(root)
    runner = runner or Runner()
    title = _validate_title(title, version)
    state = preflight(
        root, version, repo=repo, commit=commit, runner=runner
    )
    if state["release"] is not None:
        if state["release"].get("name") != title:
            raise ReleaseError(
                f"existing release {state['tag']} title does not match {title}"
            )
        action = "already-published"
        release_url = state["release"]["url"]
    else:
        if not state["tagState"]["local"]:
            runner.run(
                [
                    "git", "tag", "-a", state["tag"],
                    "-m", title, state["commit"],
                ],
                cwd=root,
            )
        if not state["tagState"]["remote"]:
            runner.run(["git", "push", "origin", state["tag"]], cwd=root)
        created = runner.run(
            [
                "gh", "release", "create", state["tag"],
                "--repo", state["repository"],
                "--title", title,
                "--notes-file", state["notes"],
                "--verify-tag",
            ],
            cwd=root,
        )
        release_url = created.stdout.strip()
        if not release_url.startswith("https://"):
            raise ReleaseError("gh release create did not return a release URL")
        action = "published"
    result = {
        **state,
        "action": action,
        "releaseUrl": release_url,
        "publishedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    if receipt:
        path = pathlib.Path(receipt)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser():
    parser = argparse.ArgumentParser(prog="release.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "check", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--version", required=True)
        if name in ("check", "publish"):
            command.add_argument("--repo", default="")
            command.add_argument("--commit", default="")
        if name == "publish":
            command.add_argument("--title", required=True)
            command.add_argument("--receipt", default="")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        config = _load_config()
        if args.command == "validate":
            result = validate_local(ROOT, args.version, config)
            result["action"] = "validated"
        elif args.command == "check":
            result = preflight(
                ROOT, args.version, repo=args.repo, commit=args.commit,
                config=config,
            )
            result["action"] = "checked"
        else:
            result = publish(
                ROOT,
                args.version,
                args.title,
                repo=args.repo,
                commit=args.commit,
                receipt=args.receipt,
            )
        print(json.dumps(result, indent=2))
        return 0
    except (ReleaseError, OSError) as exc:
        print(f"release blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
