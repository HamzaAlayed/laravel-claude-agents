# Team conventions — taught rules

Rules the user taught the agent team. Every agent reads this file before
starting work; entries here override agent defaults. Maintain via /teach
(or edit by hand — the shape below is the contract).

## Money is integer cents
- **Rule:** Store and compute money as integer cents (`*_cents` integer columns) — never float or decimal columns.
- **Why:** Float drift is unacceptable in billing; integer math is exact.
- **Scope:** database-developer + backend-developer (migrations, models, calculations)
- **Source:** user, 2026-08-06

## New tables use ULID primary keys
- **Rule:** New tables use ULID primary keys (`$table->ulid('id')->primary()` + `HasUlids` on the model), never auto-increment integers.
- **Why:** Sortable, non-enumerable identifiers.
- **Scope:** database-developer + backend-developer
- **Source:** user, 2026-08-06
