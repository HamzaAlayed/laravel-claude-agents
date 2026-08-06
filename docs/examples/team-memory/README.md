# Team memory, captured live — partial, and labeled as such

A real instance of the teach → override → harvest loop, captured from eval
run 7 (2026-08-06, pack v1.39.0 → released as v1.40.0; record:
[../../evals/2026-08-06-run-7.md](../../evals/2026-08-06-run-7.md)). Nothing
here is hand-written except this page — every other file is copied verbatim
out of the `teach-delivery` case's throwaway workdir.

**This example is honestly partial: 2 of the loop's 3 steps happened, and 1
did not.** Run 7's own findings doc explains why (finding 2) — the coordinator
ended its turn on backgrounded specialist work before reaching its own
end-of-delivery harvest step. A future run that fixes this should replace
this page's harvest section rather than paper over today's gap.

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

   The coordinator's turn ended there — before the delivery-end steps
   (`agents/delivery-coordinator.md:112-113`) that would have appended to the
   ledger and written a delivery log. **This is the loop's third step not
   happening**, and there is nothing to show for it because nothing was
   produced. See run 7's finding 2 for the structural reason (a headless
   one-shot invocation has no later turn to "follow up" in) and the fix this
   milestone parked pending a human-approved re-run.

## What to look at

The migration is the artifact worth reading closely: a database-developer
subagent, briefed with the ledger, produced a schema that visibly diverges
from Laravel's idioms in exactly the two places the ledger dictated, and
said so in its own comments. That is the pack's "team memory changes
behaviour" claim, demonstrated rather than described — for the override
half of the claim. The harvest half remains an open problem, not a
documented feature yet.
