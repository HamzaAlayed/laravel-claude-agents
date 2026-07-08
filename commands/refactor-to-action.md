---
description: Refactor a fat controller method (or Livewire action) into a single-responsibility Action class, with tests.
argument-hint: <Controller@method>  or  <LivewireComponent::action>
allowed-tools: Agent, Read, Bash, Grep, Glob, AskUserQuestion
---

# Refactor to Action — `{{args}}`

> **Delegation:** Spawn each specialist by its registered agent type as it appears in your available-agents list — prefixed when installed as a plugin (e.g. `laravel-team:backend-developer`), unprefixed when installed via `install.sh`. The specialist names in this command are labels, not literal `subagent_type` strings.

> **Interface:** Print a progress board after the plan and after every stage — `✔ done / ▶ running / · queued / ✖ failed` + owner + one-line result, so the user never wonders what's running or what's left. Demand each specialist return `STATUS / DID / VERIFIED / FLAGS / NEXT` (≤10 lines; an empty VERIFIED is a claim, not a return). Human decision needed → numbered options with a recommended default (AskUserQuestion when available), never a paragraph.

Extract the logic in `{{args}}` into a dedicated Action class, leaving the caller as thin glue.

## What you do

1. **Locate the source.**
   - For `Controller@method`: find `app/Http/Controllers/<Controller>.php` and the `<method>` body
   - For `LivewireComponent::action`: find the matching public method on the component
   - Read the method end to end before proposing anything

2. **Decide the Action's name and signature.** The verb-noun pattern is canonical:
   - `CreateOrderAction`, `PublishPostAction`, `RefundChargeAction`
   - Place under `app/Actions/<Domain>/<Name>Action.php` — match the project's directory convention if different
   - The Action exposes a single entry point — `execute(...)` or `__invoke(...)`. Pick whichever the project uses; default to `execute`.
   - Parameters are typed primitives or DTOs/Eloquent models — never the `Request`. Validation stays in the Form Request.

3. **Delegate to `backend-developer`** to:
   - Generate the Action class with `declare(strict_types=1);` and explicit return type
   - Move the logic, preserving behaviour
   - Wrap multi-write paths in `DB::transaction(...)` if not already
   - Move side-effects (mail, events, jobs) into the Action; the controller no longer dispatches them
   - Update the original method to:
     ```php
     public function store(StoreXRequest $request, CreateXAction $action): RedirectResponse
     {
         $x = $action->execute($request->validated(), $request->user());
         return redirect()->route('x.show', $x);
     }
     ```
   - Update any other caller currently inlining the same logic

4. **Delegate to `qa-engineer`** to:
   - Add a unit test for the Action (no HTTP, real DB or transactional)
   - Keep the existing feature test green
   - Add an edge-case test for at least one failure path the original method handled (or didn't handle correctly)

5. **Delegate to `tech-lead`** for review focused on:
   - The Action is genuinely single-responsibility (if `execute()` has internal branches that change semantics, it's actually two Actions)
   - No leaked controller concerns (request parsing, redirects) inside the Action
   - Transactional integrity preserved
   - Tests cover what the refactor changed

## Guardrails

- Don't refactor if the original method is already thin (< ~15 lines of meaningful logic). Say so and stop.
- Don't introduce Actions in a project that doesn't already use them without a heads-up — propose the pattern and wait for confirmation.

## Output

- New Action class path
- All call sites updated (with file:line)
- Test results before and after
- Diff summary
