# Publish an immutable release

Laravel Guild publishes from one exact, already-green `main` commit. The
release harness validates the repository state, creates an annotated tag, and
creates the GitHub release. It has no force, overwrite, tag-replacement, or
delete operation.

## Prepare the release artifacts

Choose a stable `X.Y.Z` version and update all release-owned files:

- `VERSION` and the five manifests listed in `config/release-harness.json`;
- a dated Keep a Changelog entry after `Unreleased`;
- `docs/releases/X.Y.Z.md` with every required section.

Validate locally without contacting GitHub:

```sh
python3 scripts/release.py validate --version X.Y.Z
python3 -m unittest discover -s tests/release -t tests/release -v
```

Commit the complete release, push it to `main`, and wait for the `CI` workflow
on that exact commit to finish successfully. Do not create a tag by hand.

## Publish

In GitHub Actions, open **Release**, choose **Run workflow**, select `main`, and
enter:

- `version`: the stable version without `v`;
- `title`: `Laravel Guild X.Y.Z — Short release name`.

The workflow checks out its immutable `github.sha` and gives the publisher only
`actions: read` and `contents: write`. Before mutation it proves:

1. the checkout is clean and equals `origin/main`;
2. all versions, changelog entry, and release-note sections agree;
3. the newest `CI` run for the exact commit completed successfully;
4. every job named in `requiredCiJobs` exists and passed;
5. any existing local or remote tag is annotated and resolves to that commit;
6. any existing GitHub release is final, not a draft or prerelease.

Only then does it create and push `vX.Y.Z` and publish the prepared notes. The
workflow retains `release-vX.Y.Z-receipt` for 90 days. That JSON receipt records
the commit, CI run, checked artifacts, tag state, action, URL, and UTC time.

## Symptoms

The workflow stops with `release blocked: ...`, a tag exists without a release,
or a rerun reports a conflicting tag, title, version, branch, or CI state.

## Triage

Read the first `release blocked` message and classify it before changing
anything:

- **artifact mismatch:** run `validate` locally and correct the named file;
- **dirty or stale commit:** commit the intended files, push `main`, and wait
  for CI on the new exact SHA;
- **CI missing, incomplete, or failed:** open the recorded run and repair CI;
- **inspection failure:** restore GitHub authentication or connectivity;
- **tag without release:** verify the tag is annotated and points to the
  workflow commit;
- **conflicting tag or release:** stop. Do not move, force-push, delete, or
  recreate published state.

For a read-only preflight from a clean checkout after CI passes, run:

```sh
python3 scripts/release.py check --version X.Y.Z \
  --repo OWNER/REPOSITORY --commit FULL_COMMIT_SHA
```

## Resolve

Correct unpublished repository artifacts with a new commit, let its complete CI
run pass, and dispatch Release for that new SHA. If the first publication
created the remote tag but failed before creating the release, rerun the same
version, title, and commit. The publisher recognizes the matching annotated tag
and continues without replacing it. If the GitHub release already matches, the
rerun is an `already-published` no-op and still writes a receipt.

A conflict is intentionally not self-healing. Preserve the evidence and choose
a new version after human review. Never recover by deleting or moving a public
tag.

## Verification

The release is complete only when the Release workflow is green, its receipt is
available, the annotated remote tag peels to the intended commit, and the final
GitHub release URL opens with the expected title and notes. Local validation or
a successful tag push alone is not completion.
