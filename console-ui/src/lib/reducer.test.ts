import { describe, expect, it } from "vitest";
import { emptyRun, reduce } from "./reducer";
import type { GuildEvent } from "./types";

let seq = 0;
const ev = (partial: Partial<GuildEvent> & { type: string }): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: null, ...partial }) as GuildEvent;

const play = (kind: string, events: GuildEvent[]) => events.reduce(reduce, emptyRun(kind));

describe("reduce", () => {
  it("starts a specialist run in focus mode", () => {
    expect(emptyRun("specialist").mode).toBe("focus");
    expect(emptyRun("command").mode).toBe("board");
  });

  it("opens a lane on agent_start", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "Add Action", tool_use_id: "t1" }),
    ]);
    expect(view.lanes).toHaveLength(1);
    expect(view.lanes[0].slug).toBe("backend-developer");
    expect(view.lanes[0].status).toBe("running");
    expect(view.lanes[0].task).toBe("Add Action");
  });

  it("closes the lane on agent_end", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "agent_end", agent: "qa-engineer", tool_use_id: "t1", is_error: false }),
    ]);
    expect(view.lanes[0].status).toBe("done");
    expect(view.lanes[0].endedAt).toBeGreaterThan(0);
  });

  it("marks an errored lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "agent_end", agent: "qa-engineer", tool_use_id: "t1", is_error: true }),
    ]);
    expect(view.lanes[0].status).toBe("error");
  });

  it("promotes focus to board when a second agent appears", () => {
    const view = play("specialist", [
      ev({ type: "agent_start", agent: "performance-engineer", task: "profile", tool_use_id: "t1" }),
      ev({ type: "agent_start", agent: "backend-developer", task: "fix", tool_use_id: "t2" }),
    ]);
    expect(view.mode).toBe("board");
  });

  it("never demotes board back to focus", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
    ]);
    expect(view.mode).toBe("board");
  });

  it("attributes tool_use to its lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "x", tool_use_id: "t1" }),
      ev({ type: "tool_use", agent: "backend-developer", tool: "Edit", tool_use_id: "t9" }),
    ]);
    expect(view.lanes[0].events.map((e) => e.type)).toContain("tool_use");
  });

  it("keeps main-thread text out of every lane", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "backend-developer", task: "x", tool_use_id: "t1" }),
      ev({ type: "text", agent: null, text: "coordinating" }),
    ]);
    expect(view.lanes[0].events.some((e) => e.type === "text")).toBe(false);
    expect(view.main.some((e) => e.type === "text")).toBe(true);
  });

  it("records a pending prompt and clears it on resolution", () => {
    const withPrompt = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: { command: "ls" }, is_question: false }),
    ]);
    expect(withPrompt.pending?.prompt_id).toBe("p1");
    const resolved = reduce(withPrompt, ev({ type: "prompt_resolved", prompt_id: "p1", behavior: "allow" }));
    expect(resolved.pending).toBeNull();
  });

  it("ignores a resolution for a different prompt", () => {
    const withPrompt = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {}, is_question: false }),
    ]);
    const other = reduce(withPrompt, ev({ type: "prompt_resolved", prompt_id: "p2", behavior: "allow" }));
    expect(other.pending?.prompt_id).toBe("p1");
  });

  it("captures init warnings", () => {
    const view = play("command", [
      ev({ type: "init", plugins: ["laravel-team"], plugin_errors: [{ plugin: "x", message: "bad" }] }),
    ]);
    expect(view.init?.plugin_errors).toHaveLength(1);
  });

  it("captures api_retry and clears it on the next event", () => {
    const retrying = play("command", [
      ev({ type: "api_retry", attempt: 2, max_retries: 5, error: "overloaded" }),
    ]);
    expect(retrying.retry?.attempt).toBe(2);
    expect(reduce(retrying, ev({ type: "text", text: "back" })).retry).toBeNull();
  });

  it("stores the final result", () => {
    const view = play("command", [
      ev({ type: "result", subtype: "success", result: "done", duration_ms: 10, total_cost_usd: 1 }),
    ]);
    expect(view.result?.result).toBe("done");
  });

  it("is idempotent for replayed events", () => {
    const start = ev({ type: "agent_start", agent: "qa-engineer", task: "t", tool_use_id: "t1" });
    const once = reduce(emptyRun("command"), start);
    const twice = reduce(once, start);
    expect(twice.lanes).toHaveLength(1);
  });
});
