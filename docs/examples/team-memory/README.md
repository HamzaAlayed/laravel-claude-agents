# Team memory, captured live — partial as captured, fixed since

A real instance of the teach → override → harvest loop, captured from eval
run 7 (2026-08-06, pack v1.39.0 → released as v1.40.0; record:
[../../evals/2026-08-06-run-7.md](../../evals/2026-08-06-run-7.md)). Nothing
here is hand-written except this page — every other file is copied verbatim
out of the `teach-delivery` case's throwaway workdir.

**As captured, this example is honestly partial: 2 of the loop's 3 steps
happened, and 1 did not.** Run 7's own findings doc explains why (finding 2)
— `/make-feature` runs on the main thread and never loads
`agents/delivery-coordinator.md`, the only file that promised harvest, so
the step was never in a position to run at all on this command.

**Fixed in v1.41.0, same day as this page's original capture** — the
harvest requirement moved into the shared `Interface` block `/make-feature`
actually reads. A billed re-run confirmed harvest now genuinely fires
(`docs/team/stack.md` + a delivery log both written with real content,
verified directly against the filesystem): see the "Second addendum"
section of [run 7's findings](../../evals/2026-08-06-run-7.md).
The artifacts on this page are still from the original, partial run — left
as-is because they're an honest record of what that run produced, not
because the gap they show is still open.

## What happened

1. **Teach.** `/teach New tables use ULID primary keys, never auto-increment
   integers — sortable and non-enumerable` (plus a second taught rule: money
   as integer cents, not decimal) landed in [`conventions.md`](conventions.md)
   — the ledger as seeded for this case, in `/teach`'s exact Rule / Why /
   Scope / Source contract. **This is the INPUT.**

2. **Override.** `/make-feature Donation --api` was run against that ledger.
   Laravel's own defaults point the other way on both taught rules —
   auto-increment ids, decimal money — so an override is observable, not
   coincidental. [`donations-migration.php`](donations-migration.php) is the
   migration the run produced. Its own docblock names the ledger explicitly:

   > Taught conventions applied (docs/team/conventions.md):
   > - Primary key is a ULID, not auto-increment — "New tables use ULID
   >   primary keys".
   > - Monetary amount stored as `amount_cents` (unsigned integer, no
   >   decimals) — "Money is integer cents". Deviates from the requested
   >   `amount` column name to satisfy this rule.

   `$table->ulid('id')->primary()` and `$table->unsignedBigInteger
   ('amount_cents')` — the ledger was consulted, not coincidentally matched.
   **This is the loop's second step working.**

3. **Harvest — did not happen this run.** Neither `docs/team/stack.md` nor
   any `docs/delivery/**/log.md` exists in the source workdir. The run's own
   final message, captured verbatim as [`final-answer.md`](final-answer.md),
   is:

   > Waiting on the QA feature-test agent and the tech-lead review agent to
   > finish (both running in the background). I'll follow up once they
   > complete.

   That final message is the main thread narrating an intention to follow
   up on backgrounded specialists — but that framing turned out to be a
   symptom, not the cause: the delivery-end steps that would have appended
   to the ledger and written a delivery log
   (`agents/delivery-coordinator.md:104,113`) live in a file `/make-feature`
   never loads in the first place. **This is the loop's third step not
   happening**, and there is nothing to show for it because nothing was
   produced.

   **Update, same day:** a fix was attempted on the original (wrong)
   diagnosis — the `delivery-coordinator` agent body was patched so
   parallel lanes are always awaited, never backgrounded — and a
   human-approved re-run was spent validating it. The patch is real and
   ships as good guidance for interactive `delivery-coordinator` sessions,
   but since `/make-feature` never loads that file, the re-run could not
   have tested it either way; its different outcome (a timeout, this time)
   is best read as ordinary run-to-run variance on the main thread, not
   evidence about the patch. At this point, harvest was still unproven.

   **Update, v1.41.0 (also same day):** the actual fix landed — the harvest
   requirement moved into the shared `Interface` block `/make-feature`
   reads directly. A billed re-run confirmed harvest genuinely fires:
   `docs/team/stack.md` and a phase-by-phase delivery log were both
   written with real, run-specific content, verified against the
   filesystem. See run 7's finding 2 and its two addenda for the full,
   corrected account — this page's captured artifacts above are still from
   the original run (that's what "as captured" in the title means), not
   because harvest is still broken.

## What to look at

The migration is the artifact worth reading closely: a database-developer
subagent, briefed with the ledger, produced a schema that visibly diverges
from Laravel's idioms in exactly the two places the ledger dictated, and
said so in its own comments. That is the pack's "team memory changes
behaviour" claim, demonstrated rather than described — for the override
half of the claim. The harvest half is now a documented, working feature
as of v1.41.0 (see the update above) — this page just doesn't carry its
own artifacts yet, since the run that proved it wasn't the run captured
here.
