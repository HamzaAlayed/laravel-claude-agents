import { describe, expect, it } from "vitest";
import { emptyRun, isRunOver, reduce } from "./reducer";
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

  // The PreToolUse gate publishes one tool_gate per call. Calls it did not force
  // through the browser ran unasked, and the transcript has to say so rather
  // than implying every call was approved.
  it("counts a lane's unasked calls", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "tool_gate", agent: "qa-engineer", tool: "Read", tool_use_id: "r1", asked: false }),
      ev({ type: "tool_gate", agent: "qa-engineer", tool: "Grep", tool_use_id: "r2", asked: false }),
    ]);
    expect(view.lanes[0].unasked).toBe(2);
  });

  it("does not count a call the browser was asked about", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "tool_gate", agent: "qa-engineer", tool: "Bash", tool_use_id: "b1", asked: true }),
    ]);
    expect(view.lanes[0].unasked).toBe(0);
  });

  it("counts main-thread unasked calls on the run, not on someone's lane", () => {
    const view = play("prompt", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "tool_gate", agent: null, tool: "Read", tool_use_id: "r1", asked: false }),
    ]);
    expect(view.unasked).toBe(1);
    expect(view.lanes[0].unasked).toBe(0);
  });

  it("attributes each lane's unasked calls separately", () => {
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "agent_start", agent: "backend-developer", task: "build", tool_use_id: "t2" }),
      ev({ type: "tool_gate", agent: "backend-developer", tool: "Read", tool_use_id: "r1", asked: false }),
    ]);
    expect(view.lanes.map((lane) => lane.unasked)).toEqual([0, 1]);
  });

  it("keeps a tool_gate out of the lane transcript", () => {
    // It is bookkeeping, not something the agent did — the tool_use event that
    // follows is what belongs in the timeline.
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "tests", tool_use_id: "t1" }),
      ev({ type: "tool_gate", agent: "qa-engineer", tool: "Read", tool_use_id: "r1", asked: false }),
    ]);
    expect(view.lanes[0].events).toHaveLength(0);
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
    expect(withPrompt.pending.map((p) => p.prompt_id)).toEqual(["p1"]);
    const resolved = reduce(withPrompt, ev({ type: "prompt_resolved", prompt_id: "p1", behavior: "allow" }));
    expect(resolved.pending).toEqual([]);
  });

  it("keeps the agent the engine attributed the prompt to", () => {
    const view = play("command", [
      ev({ type: "prompt", agent: "backend-developer", prompt_id: "p1", tool: "Bash", input: {} }),
      ev({ type: "prompt", agent: null, prompt_id: "p2", tool: "Write", input: {} }),
    ]);
    expect(view.pending.map((p) => p.agent)).toEqual(["backend-developer", null]);
  });

  // Two parallel subagents each parking on their own approval is this pack's
  // normal orchestration shape. A single slot silently dropped the first one and
  // left that subagent awaiting a future nothing in the UI could name.
  it("queues two concurrent prompts in arrival order", () => {
    const view = play("command", [
      ev({ type: "prompt", agent: "security-engineer", prompt_id: "p1", tool: "Bash", input: {} }),
      ev({ type: "prompt", agent: "performance-engineer", prompt_id: "p2", tool: "Read", input: {} }),
    ]);
    expect(view.pending.map((p) => p.prompt_id)).toEqual(["p1", "p2"]);
    expect(view.pending[1].tool).toBe("Read");
  });

  it("resolving the first prompt leaves the second waiting", () => {
    const queued = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {} }),
      ev({ type: "prompt", prompt_id: "p2", tool: "Read", input: {} }),
    ]);
    const after = reduce(queued, ev({ type: "prompt_resolved", prompt_id: "p1", behavior: "allow" }));
    expect(after.pending.map((p) => p.prompt_id)).toEqual(["p2"]);
  });

  it("resolving the second prompt leaves the first waiting", () => {
    const queued = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {} }),
      ev({ type: "prompt", prompt_id: "p2", tool: "Read", input: {} }),
    ]);
    const after = reduce(queued, ev({ type: "prompt_resolved", prompt_id: "p2", behavior: "deny" }));
    expect(after.pending.map((p) => p.prompt_id)).toEqual(["p1"]);
  });

  it("ignores a resolution for an unknown prompt", () => {
    const queued = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {} }),
      ev({ type: "prompt", prompt_id: "p2", tool: "Read", input: {} }),
    ]);
    const after = reduce(queued, ev({ type: "prompt_resolved", prompt_id: "nope", behavior: "allow" }));
    expect(after.pending.map((p) => p.prompt_id)).toEqual(["p1", "p2"]);
  });

  // The SSE backlog is replayed on every reconnect, so the same prompt event
  // arrives again — it must not queue twice and demand two answers.
  it("does not double-queue a replayed prompt", () => {
    const prompt = ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: { command: "ls" } });
    const once = reduce(emptyRun("command"), prompt);
    const twice = reduce(once, prompt);
    expect(twice.pending.map((p) => p.prompt_id)).toEqual(["p1"]);
  });

  it("a replayed resolution after the queue drained changes nothing", () => {
    const resolution = ev({ type: "prompt_resolved", prompt_id: "p1", behavior: "allow" });
    const drained = play("command", [
      ev({ type: "prompt", prompt_id: "p1", tool: "Bash", input: {} }),
      resolution,
    ]);
    expect(reduce(drained, resolution).pending).toEqual([]);
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

  // The engine's _pump publishes `error` INSTEAD of a result when the CLI or the
  // transport dies. With no terminal case for it the run read as live forever:
  // the Launcher stayed disabled, and the advice "interrupt it first" 500s on a
  // dead client, so a page reload was the only way out.
  it("ends the run on an error event and keeps the message", () => {
    expect(isRunOver(emptyRun("command"))).toBe(false);
    const view = play("command", [
      ev({ type: "agent_start", agent: "qa-engineer", task: "t", tool_use_id: "t1" }),
      ev({ type: "error", message: "CLI transport closed" }),
    ]);
    expect(view.failure?.message).toBe("CLI transport closed");
    expect(isRunOver(view)).toBe(true);
    // Not swallowed: the timeline still shows it happened.
    expect(view.main.some((e) => e.type === "error")).toBe(true);
  });

  it("an error after a result does not resurrect the run", () => {
    const finished = play("command", [
      ev({ type: "result", subtype: "success", result: "done", duration_ms: 10, total_cost_usd: 1 }),
    ]);
    const after = reduce(finished, ev({ type: "error", message: "late transport error" }));
    expect(after.result?.result).toBe("done");
    expect(isRunOver(after)).toBe(true);
  });

  it("is idempotent for replayed events", () => {
    const start = ev({ type: "agent_start", agent: "qa-engineer", task: "t", tool_use_id: "t1" });
    const once = reduce(emptyRun("command"), start);
    const twice = reduce(once, start);
    expect(twice.lanes).toHaveLength(1);
  });
});
