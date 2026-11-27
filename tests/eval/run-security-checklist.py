#!/usr/bin/env python3
"""Run matched read-only Claude Code security audits of a disposable Laravel release fixture."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
from http.client import HTTPConnection
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "tests/eval/fixtures/security-checklist"
ROLE = "security-engineer"
MODEL = "claude-opus-5-5"
PROFILE = f"agents/{ROLE}.md"
SKILL = "skills/laravel-security/SKILL.md"
REFERENCE = "skills/laravel-security/references/production-security-checklist.md"
PROMPT = """Give a production security and go-live review for the Laravel release described
in release-scope.md. Review the app source and the records in evidence/. Use the
Guild security skill supplied at audit-guide/SKILL.md and any reference it links.
Work read-only, within this fixture. Report distinct findings with the file and
field or code location, what the evidence establishes, and a defensive fix or
additional check. Give a release decision and list each reason to hold release
with the evidence required and responsible role. Map findings to Guild checklist
IDs when the guide provides them. Distinguish confirmed issues, missing evidence,
and controls that are verified or out of scope. Do not probe services, produce
attack steps or payloads, or recount any secret values.
"""
RUNTIME = r"""
require 'vendor/autoload.php';
$app = require 'bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
echo json_encode([
    'capture' => 'local Laravel fixture after config:cache',
    'laravel_version' => $app->version(),
    'app_env' => $app['config']->get('app.env'),
    'app_debug' => $app['config']->get('app.debug'),
]), PHP_EOL;
"""


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def capture_asset(static_root):
    build = static_root / "build"
    build.mkdir(parents=True)
    shutil.copyfile(SEED / "editor.js", build / "editor.js")
    handler = partial(SimpleHTTPRequestHandler, directory=static_root)
    with HTTPServer(("127.0.0.1", 0), handler) as server:
        server.timeout = 8
        with ThreadPoolExecutor(max_workers=1) as executor:
            request_thread = executor.submit(server.handle_request)
            client = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                client.request("GET", "/build/editor.js")
                response = client.getresponse()
                headers = response.getheaders()
                body = response.read()
                assert response.status == 200 and body == (build / "editor.js").read_bytes()
                assert all(name.lower() != "x-content-type-options" for name, _ in headers)
                receipt = {
                    "source": "observed loopback static server response for the fixture asset",
                    "request": {"method": "GET", "path": "/build/editor.js"},
                    "status": response.status,
                    "response_headers_complete": True,
                    "response_headers": [{"name": name, "value": value} for name, value in headers],
                }
            finally:
                client.close()
            request_thread.result()
    return receipt


def prepare(app, vendor, output, fixture_revision):
    archive = git("archive", f"{fixture_revision}:tests/fixture-app")
    with tarfile.open(fileobj=BytesIO(archive)) as source:
        source.extractall(app, filter="data")
    evidence = app / "evidence"
    evidence.mkdir()
    shutil.copyfile(SEED / "release-scope.md", app / "release-scope.md")
    for name in ("edge.json", "platform.json", "ci.json"):
        shutil.copyfile(SEED / name, evidence / name)
    asset = capture_asset(app.parent / "static")
    (evidence / "asset-response.json").write_text(json.dumps(asset, indent=2) + "\n")

    # Capture the isolated fixture's effective config and route inventory, then
    # discard the runtime dependencies and cache before launching the reviewer.
    (app / "bootstrap/cache").mkdir(exist_ok=True)
    (app / "vendor").symlink_to(vendor.resolve(), target_is_directory=True)
    env = {
        **os.environ, "APP_ENV": "production", "APP_DEBUG": "true",
        "APP_CONFIG_CACHE": str(app / "bootstrap/cache/config.php"),
        "APP_KEY": "", "APP_PREVIOUS_KEYS": "",
    }
    subprocess.run(["php", "artisan", "config:cache", "--no-ansi"], cwd=app, env=env,
                   check=True, capture_output=True)
    runtime = json.loads(subprocess.check_output(["php", "-r", RUNTIME], cwd=app, env=env))
    assert runtime["app_env"] == "production" and runtime["app_debug"] is True
    routes = json.loads(subprocess.check_output(
        ["php", "artisan", "route:list", "-vv", "--json"], cwd=app, env=env
    ))
    assert any(route["name"] == "posts.update" for route in routes)
    for filename, data in (("runtime.json", runtime), ("route-inventory.json", routes)):
        (evidence / filename).write_text(json.dumps(data, indent=2) + "\n")
    (app / "vendor").unlink()
    shutil.rmtree(app / "bootstrap/cache")
    shutil.copytree(evidence, output / "evidence")
    shutil.copyfile(app / "release-scope.md", output / "release-scope.md")


def definitions(baseline, baseline_files, output):
    profiles = {}
    hashes = {}
    if baseline_files is None:
        previous = {path: git("show", f"{baseline}:{path}") for path in (PROFILE, SKILL)}
    else:
        previous = {path: (baseline_files / path).read_bytes() for path in (PROFILE, SKILL, REFERENCE)}
    for revision, files in (
        ("before", previous),
        ("after", {path: (ROOT / path).read_bytes() for path in (PROFILE, SKILL, REFERENCE)}),
    ):
        _, frontmatter, body = files[PROFILE].decode().split("---", 2)
        description = next(line.removeprefix("description: ") for line in frontmatter.splitlines()
                           if line.startswith("description: "))
        definition = {ROLE: {"description": description, "prompt": body.strip(), "model": MODEL,
                             "tools": ["Read", "Glob", "Grep"]}}
        guides = {path.removeprefix("skills/laravel-security/"): source
                  for path, source in files.items() if path != PROFILE}
        profiles[revision] = (definition, guides)
        hashes[revision] = {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}
    (output / "profiles.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return profiles


def evaluate_round(fixture, output, number, profiles, evaluate):
    app = fixture.parent / f"round-{number}"
    shutil.copytree(fixture, app)
    guide = app / "audit-guide"
    order = ("before", "after") if number % 2 else ("after", "before")
    for revision in order:
        definition, files = profiles[revision]
        for path, source in files.items():
            target = guide / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)
        evaluate(app, output, ROLE, revision, number, definition, prompt=PROMPT, effort="medium")
        shutil.rmtree(guide)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="Git revision of the fixture and default baseline")
    parser.add_argument("--baseline-files", type=Path, help="Snapshot of the previous profile, skill, and checklist")
    parser.add_argument("--vendor", required=True, type=Path, help="Installed tests/fixture-app/vendor")
    parser.add_argument("--output", required=True, type=Path, help="New results directory")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--parallel-rounds", type=int, default=1)
    args = parser.parse_args()
    if args.rounds < 1 or args.parallel_rounds < 1 or not (args.vendor / "autoload.php").is_file():
        parser.error("provide positive round counts and an installed fixture vendor directory")

    output = args.output.resolve()
    output.mkdir(parents=True)
    (output / "prompt.txt").write_text(PROMPT)
    fixture_revision = git("rev-parse", args.baseline).decode().strip()
    profiles = definitions(fixture_revision, args.baseline_files, output)
    evaluate = runpy.run_path(str(ROOT / "tests/eval/run-frontend-checklist.py"))["evaluate"]
    with tempfile.TemporaryDirectory(prefix="guild-security-checklist-") as temp:
        app = Path(temp) / "fixture"
        prepare(app, args.vendor, output, fixture_revision)
        with ThreadPoolExecutor(max_workers=min(args.parallel_rounds, args.rounds)) as executor:
            rounds = [executor.submit(evaluate_round, app, output, number, profiles, evaluate)
                      for number in range(1, args.rounds + 1)]
            for trial in rounds:
                trial.result()


if __name__ == "__main__":
    main()
