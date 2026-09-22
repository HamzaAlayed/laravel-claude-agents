# How can I explain less and supervise fewer steps?

Choose **Work independently** in the console launcher. This is the default for
new UI runs; API clients that omit a mode retain the existing `default` behavior.
Existing running sessions need a new run to receive the new system instructions.

## What continues automatically?

The console uses the SDK's `acceptEdits` mode and permits an exact, narrow set of
commands, including `npm test`, `npm run build`, `npm run lint`, `php artisan test`,
and `vendor/bin/pest`. Unknown arguments, compound shell commands and commands
such as `git push`, `npm publish` and deletion commands still require review.
External MCP tool calls and edits outside the project also require review.
The complete allowlist is `routine_command` in `scripts/console/independence.py`.

Independence is still bounded. Every run receives hard wall-clock, tool-call,
token, and dollar ceilings; reaching one interrupts the SDK run and leaves a
`budget_exceeded` event. The run's launch spec and budget are checkpointed in a
redacted JSONL metadata record before the first query, so the resume endpoint can
start a new run that inspects the current workspace and kernel state rather than
replaying completed work. Raw SDK messages are not persisted by default.

This is **not a sandbox**. Test and build commands execute project code, including
package lifecycle scripts. Only use this mode in a trusted checkout. A malicious
test can still cause external effects. Select **Ask me** when you want to inspect
every shell command. Existing explicit “Allow always” choices still apply.

## What does the agent remember?

Each new run loads project-level SDK settings/instructions and a fresh bounded
snapshot of root `composer.json` and `package.json` metadata. It does not scan
`.env` files for context. Relevant existing code and project decisions should be
inspected before asking you to explain them.

Keep explicit, non-secret preferences in `.claude/guild-preferences.md` (up to
8,000 bytes). Edit or delete it yourself, or explicitly ask the agent to remember
a preference there. For example: “Remember that UI changes should reuse our
existing components.” This is a plain project file, not a hidden memory service;
it may be committed unless you add it to your project's ignore rules.

The execution instructions distinguish user preferences from inferred lessons.
Neither grants permission to publish, deploy, spend money or delete user data.
The implementation is in `instructions` and `working_context` in
`scripts/console/independence.py`; SDK wiring is in `scripts/console/serve.py`.

## When should it ask me?

For missing information that materially changes the outcome, consequential
actions, or a blocker it cannot resolve. Implementation runs are instructed to
choose reversible defaults, verify their work, and make at most three
evidence-driven repair attempts on the same failure before reporting a blocker.
That repair limit is prompt guidance, not a hard runtime counter. No background
retry worker or automatic resumption after process restarts is added here.

Mode changes take effect through the existing live-run selector. Plan-only stays
available. New context is gathered at launch; ongoing runs must reread files when
facts change. Deterministic approval tests do not prove model compliance with
the working agreement; representative live-run evaluation remains necessary.
