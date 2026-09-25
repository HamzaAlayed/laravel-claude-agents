# Route PR and CI feedback

## Purpose

Laravel Guild routes pull-request feedback from durable ownership data rather
than from whichever specialist ran most recently. CI checks belong to the
stage that declares their exact names. Review comments belong to the stage
whose `owned_paths` contains the commented file, using the longest match when
paths are nested.

## Declare routes during planning

Every typed stage includes `feedback_checks`. Check names must be nonempty,
single-line strings and globally unique inside one delivery. Use an empty list
only when the stage owns no CI job.

```json
{
  "id": "backend",
  "agent": "backend-developer",
  "success_criteria": ["the endpoint passes its feature tests"],
  "criterion_ids": ["endpoint-tests-pass"],
  "depends_on": [],
  "owned_paths": ["app/Http", "tests/Feature"],
  "approval_categories": [],
  "feedback_checks": ["phpunit", "pint"]
}
```

## Ingest confirmed feedback

Record the pull request first, then ingest only feedback that GitHub confirms:

```sh
python3 scripts/guild-kernel/guild.py pr \
  --root . --name tags --number 17
python3 scripts/guild-kernel/guild.py ingest \
  --root . --name tags --kind check --check phpunit
python3 scripts/guild-kernel/guild.py ingest \
  --root . --name tags --kind review --comment 991204
```

Do not pass `--stage` to choose an owner. It is optional and acts only as an
assertion: the command fails if the kernel derives a different stage.

The first distinct feedback event for a completed stage consumes its single
allowed reopen and moves that stage to `queued`. Additional open items for the
same queued or running repair attach to that attempt without consuming another
retry. The next successful `report` resolves every open item for the stage.

## Resolve an unknown route

Inspect routing state whenever a delivery starts or resumes and after polling
an open pull request:

```sh
python3 scripts/guild-kernel/guild.py feedback list \
  --root . --name tags
```

An unknown CI name or unowned review path persists as `route_required` and
blocks `ready` and `next`. Review the event and ownership before assigning it.
Only the main thread may run:

```sh
python3 scripts/guild-kernel/guild.py feedback assign \
  --root . --name tags \
  --event-id ci:2ff3478f1c19 \
  --stage backend
```

Assigning an unknown CI check also records that exact check name on the stage
for later events. Review comments remain stricter: the selected stage must own
the commented path.

## Lifecycle and stopping rules

The generated `docs/delivery/<name>/feedback.md` view records each event,
route, owner, source location, status, and resolution attempt. `kernel.json`
remains authoritative.

- `route_required`: no safe owner was derived; dispatch is blocked.
- `open`: assigned to an active repair attempt.
- `resolved`: a passing report completed the owning stage.
- `stopped`: the stage was not repairable or its one reopen was exhausted.

Repeated delivery of the same external event is a no-op in every status. A new
event after the allowed reopen is exhausted fails the stage and stops the
delivery for a human decision. Never rewrite kernel state, route by last
writer, or create another repair loop outside this lifecycle.

## Compatibility

Existing delivery files load with empty feedback routes and events. They gain
new routing state only when planned again or when confirmed feedback is
assigned. Direct single-specialist work without a recorded pull request is
unchanged.
