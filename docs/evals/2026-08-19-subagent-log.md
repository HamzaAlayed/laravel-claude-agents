# Subagent-log extraction — the run-8 observability gap, instrumented — 2026-08-19

**Trigger:** [run 8](2026-08-12-run-8.md) filed that per-stage specialist returns (`STATUS`/`DID`/`VERIFIED`/`NOT-CHECKED`/`FLAGS`/`NEXT`) live on subagent turns and are structurally invisible to `scripts/eval-cost.py` `full_text()`, which keeps `parent_tool_use_id is None`. [Run 9](2026-08-19-run-9-cost.md) finding 5 then showed the complementary failure: a timeout-path `$LOG` (`final_text()` fallback) can pass a closing-contract grep on a specialist quoted into the reconstructed log, while `$FULL_LOG` never saw an orchestrator close. `tests/guardrails.test.sh` forbids any `checks_*` function from grepping `stream.jsonl` directly, so there was no legal way to observe the per-stage half of the Interface contract.

**What shipped (this change):** a third derived extraction, complementary to `full_text()` and `final_text()`, whose meaning those two modes do not change.

| Surface | Name |
| ------- | ---- |
| Extractor | `subagent_text()` — concatenates assistant text from turns whose `parent_tool_use_id` is not None |
| CLI | `scripts/eval-cost.py --subagent-text` (mutually exclusive with `--text-only` / `--full-text`) |
| Artifact | `<case>.subagent.log` (`$SUBAGENT_LOG`), persisted next to `$FULL_LOG` |
| Helper | `check_subagent_log <regex> <description>` — greps `$SUBAGENT_LOG`, never `stream.jsonl` |

Unit tests plant a six-field specialist return on a subagent turn via `assistant_line(..., parent=...)` and prove: `full_text()` does not see `STATUS`/`DID`/`FLAGS`/`NEXT`; `subagent_text()` does; a specialist `VERIFIED` in `subagent_text()` cannot satisfy a main-thread grep of `$FULL_LOG`. The guardrails ratchet now also pins that `check_subagent_log` itself does not collapse to grepping `stream.jsonl`.

**What did not ship:** a live billed assertion. `checks_feature()` still only greps the coordinator's own closing `VERIFIED`/`NOT-CHECKED` on `$LOG`. A commented `check_subagent_log` shape sits next to those lines for a future inspected `feature` run. `check_stage_return_shape` was not re-added. `max_usd` was not raised. No billed `claude -p` ran in this task. `full_text()`'s main-thread filter is unchanged (run 7 finding 3).

**Inspected 2026-08-19 on [run 10](2026-08-19-run-10.md):** `KEEP_TRANSCRIPT=1` `feature` stream, Claude Code 2.1.235. 125 nested assistant turns have top-level `parent_tool_use_id` (extractor key is right). Every nested `message.content` is `tool_use` only — 0 text blocks — so `$SUBAGENT_LOG` is empty. The orchestrator closed on `$FULL_LOG` with its own `VERIFIED` / `NOT-CHECKED`. `check_subagent_log` stays commented; uncommenting it would fail that 10/10 PASS. Per-stage six-field prose is still unmeasured.
