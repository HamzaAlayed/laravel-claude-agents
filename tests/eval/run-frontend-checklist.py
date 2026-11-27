#!/usr/bin/env python3
"""Run a read-only, paired Claude Code audit against a disposable Laravel fixture."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "tests/eval/fixtures/frontend-checklist"
MODELS = {
    "frontend-developer": "claude-sonnet-5-5",
    "performance-engineer": "claude-opus-5-5",
}
PROMPT = """Audit frontend performance for the Laravel app's /catalog page. Use the fixture's
source, configuration, and any recorded runtime evidence. Stay within the catalog
workload and work read-only. Report each distinct issue you can substantiate with its
file and line, the mechanism, and a targeted fix. Label checks requiring further
measurement separately. Distinguish source findings from measured effects.
"""


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def prepare(app, vendor):
    archive = subprocess.check_output(["git", "archive", "HEAD:tests/fixture-app"], cwd=ROOT)
    archive_path = app.parent / "source.tar"
    archive_path.write_bytes(archive)
    with tarfile.open(archive_path) as source:
        source.extractall(app, filter="data")

    (app / "vendor").symlink_to(vendor.resolve(), target_is_directory=True)
    (app / "bootstrap/cache").mkdir(exist_ok=True)
    (app / ".env").write_text(
        "APP_ENV=local\nAPP_KEY=base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n"
        "APP_DEBUG=false\nSESSION_DRIVER=array\nCACHE_STORE=array\n"
    )
    with (app / "routes/web.php").open("a") as routes:
        routes.write("\nrequire __DIR__.'/catalog.php';\n")
    (app / "resources/catalog").mkdir()
    assets = app / "public/catalog-assets"
    assets.mkdir(parents=True)
    (app / "public/index.php").write_text("""<?php

if (PHP_SAPI === 'cli-server' && is_file(__DIR__.parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH))) {
    return false;
}

require __DIR__.'/../vendor/autoload.php';
$app = require __DIR__.'/../bootstrap/app.php';
$app->handleRequest(Illuminate\\Http\\Request::capture());
""")
    for source, target in {
        "routes.php": app / "routes/catalog.php",
        "catalog.blade.php": app / "resources/views/catalog.blade.php",
        "catalog.js": app / "resources/catalog/catalog.js",
        "catalog.css": assets / "catalog.css",
        "surface.css": assets / "surface.css",
        "lighthouserc.json": app / "lighthouserc.json",
    }.items():
        shutil.copyfile(SEED / source, target)
    font, = (ROOT / "scripts/console/dist/assets").glob("source-sans-3-latin-wght-normal-*.woff2")
    shutil.copyfile(font, assets / "catalog.woff2")

    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080",
        "-vf", "noise=alls=35:allf=u", "-frames:v", "1", "-q:v", "1", str(assets / "trail.jpg"))
    for size in (160, 320):
        run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s={size}x{size * 9 // 16}",
            "-frames:v", "1", str(assets / f"material-{size}.jpg"))
    run("ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360",
        "-t", "4", "-c:v", "mpeg4", "-movflags", "+faststart", str(assets / "fitting.mp4"))


def capture_http(app):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (app.parent / "laravel-server.log").open("w") as server_log:
        server = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", "public", "public/index.php"],
            cwd=app, stdout=server_log, stderr=server_log,
        )
        try:
            for attempt in range(30):
                try:
                    with urlopen(base + "/up", timeout=2):
                        break
                except URLError:
                    if attempt == 29 or server.poll() is not None:
                        raise
                    time.sleep(0.1)

            evidence = app / "evidence"
            evidence.mkdir()
            entries = []
            for path, extra_headers in [
                ("/catalog", {}),
                ("/catalog/viewer", {"X-Catalog-Viewer": "new"}),
                ("/catalog/viewer", {"X-Catalog-Viewer": "returning"}),
                ("/catalog/items", {}),
                ("/catalog-assets/catalog.8c4e21af.js", {}),
                ("/catalog-assets/catalog.css", {}),
                ("/catalog-assets/surface.css", {}),
                ("/catalog-assets/catalog.woff2", {}),
                ("/catalog-assets/trail.jpg", {}),
                ("/catalog-assets/fitting.mp4", {}),
            ]:
                headers = {"Accept-Encoding": "br, gzip", **extra_headers}
                with urlopen(Request(base + path, headers=headers), timeout=5) as response:
                    body = response.read()
                    entry = {
                        "request_path": path, "request_headers": headers, "status": response.status,
                        "body_bytes": len(body), "response_headers": {
                            key: value for key, value in response.headers.items()
                            if key.lower() in {"cache-control", "content-encoding", "content-length",
                                               "content-type", "etag", "last-modified", "vary"}
                        },
                    }
                    if path == "/catalog":
                        assert '<h1 id="catalog-heading"></h1>' in body.decode()
                    if path == "/catalog/items":
                        items = json.loads(body)
                        assert len(items) == 180 and len(items[0]["listing_history"]) == 12
                        entry["first_item"] = items[0]
                    if path == "/catalog/viewer":
                        entry["body"] = json.loads(body)
                    entries.append(entry)
            assert entries[1]["body"] != entries[2]["body"]
            (evidence / "local-http.json").write_text(json.dumps(entries, indent=2) + "\n")
        finally:
            server.terminate()
            server.wait(timeout=5)


def profiles(baseline, baseline_profiles, output):
    definitions = {}
    hashes = {}
    for role, model in MODELS.items():
        path = Path("agents") / f"{role}.md"
        if baseline_profiles is None:
            previous = run("git", "show", f"{baseline}:{path.as_posix()}", cwd=ROOT, capture_output=True).stdout
        else:
            previous = (baseline_profiles / path.name).read_text()
        for revision, source in (
            ("before", previous),
            ("after", (ROOT / path).read_text()),
        ):
            _, frontmatter, body = source.split("---", 2)
            description = next(line.removeprefix("description: ") for line in frontmatter.splitlines()
                               if line.startswith("description: "))
            definitions[(role, revision)] = {
                role: {"description": description, "prompt": body.strip(), "model": model,
                       "tools": ["Read", "Glob", "Grep"]},
            }
            hashes[f"{role}-{revision}"] = hashlib.sha256(source.encode()).hexdigest()
    (output / "profiles.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return definitions


def evaluate(app, output, role, revision, round_number, definition, *, prompt=PROMPT, effort="low"):
    name = f"{role}-{revision}-{round_number}"
    env = os.environ.copy()
    # Use the signed-in Claude Code account without inheriting an API override.
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDECODE"):
        env.pop(key, None)
    command = [
        "claude", "-p", "--agent", role, "--agents", json.dumps(definition),
        "--model", definition[role]["model"], "--effort", effort, "--tools", "Read,Glob,Grep",
        "--allowedTools", "Read,Glob,Grep", "--permission-mode", "dontAsk",
        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
        "--no-session-persistence", "--max-turns", "16", "--max-budget-usd", "0.85",
        "--output-format", "json",
    ]
    print(f"Starting {name}", flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=app, env=env, input=prompt,
                            capture_output=True, text=True, timeout=180)
    elapsed = time.monotonic() - started
    (output / f"{name}.json").write_text(result.stdout)
    if result.stderr:
        (output / f"{name}.stderr").write_text(result.stderr)

    data = json.loads(result.stdout)
    assert result.returncode == 0 and data.get("subtype") == "success" and not data.get("is_error"), data
    assert data.get("result", "").strip() and data.get("total_cost_usd") is not None, data
    record = {"run": name, "wall_seconds": round(elapsed, 3), "claude_seconds": data["duration_ms"] / 1000,
              "cost_usd": data["total_cost_usd"], "turns": data["num_turns"],
              "model_usage": data["modelUsage"]}
    with (output / "runs.jsonl").open("a") as log:
        log.write(json.dumps(record) + "\n")
    print(f"Finished {name} in {elapsed:.1f}s, Claude Code estimate ${record['cost_usd']:.4f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    baseline = parser.add_mutually_exclusive_group(required=True)
    baseline.add_argument("--baseline", help="Git revision of previous profiles")
    baseline.add_argument(
        "--baseline-profiles", type=Path, help="Directory containing the previous profile files"
    )
    parser.add_argument("--vendor", required=True, type=Path, help="Installed tests/fixture-app/vendor")
    parser.add_argument("--output", required=True, type=Path, help="New results directory")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.rounds < 1 or not (args.vendor / "autoload.php").is_file():
        parser.error("provide at least one round and an installed fixture vendor directory")
    output = args.output.resolve()
    output.mkdir(parents=True)
    definitions = profiles(args.baseline, args.baseline_profiles, output)
    (output / "prompt.txt").write_text(PROMPT)
    with tempfile.TemporaryDirectory(prefix="guild-frontend-checklist-") as temp:
        app = Path(temp) / "fixture"
        prepare(app, args.vendor)
        capture_http(app)
        shutil.copyfile(app / "evidence/local-http.json", output / "local-http.json")
        for round_number in range(1, args.rounds + 1):
            for role in MODELS:
                revisions = ("before", "after") if round_number % 2 else ("after", "before")
                for revision in revisions:
                    evaluate(app, output, role, revision, round_number, definitions[(role, revision)])


if __name__ == "__main__":
    main()
