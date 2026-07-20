# Fixture app

A small Laravel blog used by the pack's eval harness (`tests/eval/run-evals.sh`).
It is analyzed by agents under evaluation — keep it free of hints about what the
evals check for.

Not a real application: `vendor/` is never committed, and the app only needs to
be *readable*, not runnable, for the default eval run.
