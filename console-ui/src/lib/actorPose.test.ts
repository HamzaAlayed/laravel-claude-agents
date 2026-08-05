import { describe, expect, it } from "vitest";
import { actorPose } from "./actorPose";
import type { GuildEvent, Lane, LaneStatus } from "./types";

let seq = 0;
const ev = (partial: Partial<GuildEvent> & { type: string }): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: "qa-engineer", ...partial }) as GuildEvent;

const lane = (status: LaneStatus, events: GuildEvent[] = []): Lane => ({
  slug: "qa-engineer",
  task: "tests",
  toolUseId: "t1",
  parent: null,
  status,
  startedAt: 1000,
  endedAt: status === "running" ? 0 : 9000,
  events,
  unasked: 0,
});

describe("actorPose", () => {
  it("raises a hand for a parked lane", () => {
    expect(actorPose(lane("running"), true)).toBe("needs");
  });

  // Being blocked on the human outranks whatever the agent was mid-way through:
  // the card's job at that moment is to get answered, not to narrate.
  it("raises a hand even while a tool call is open", () => {
    expect(actorPose(lane("running", [ev({ type: "tool_use", tool: "Bash" })]), true)).toBe("needs");
  });

  it("works while a tool call is the newest event", () => {
    expect(actorPose(lane("running", [ev({ type: "tool_use", tool: "Bash" })]), false)).toBe(
      "working",
    );
  });

  it("stumbles when the newest tool result is an error", () => {
    const events = [ev({ type: "tool_use", tool: "Bash" }), ev({ type: "tool_result", is_error: true })];
    expect(actorPose(lane("running", events), false)).toBe("stumble");
  });

  // A result that came back fine puts the agent back to reading it, not to
  // hammering — the next tool_use is what says work resumed.
  it("thinks again after a tool result that succeeded", () => {
    const events = [ev({ type: "tool_use", tool: "Bash" }), ev({ type: "tool_result", is_error: false })];
    expect(actorPose(lane("running", events), false)).toBe("thinking");
  });

  it("speaks when the newest event is assistant text", () => {
    expect(actorPose(lane("running", [ev({ type: "text", text: "here" })]), false)).toBe("speaking");
  });

  it("thinks while reasoning", () => {
    expect(actorPose(lane("running", [ev({ type: "thinking", text: "hmm" })]), false)).toBe(
      "thinking",
    );
  });

  it("thinks in a lane that has produced no events yet", () => {
    expect(actorPose(lane("running"), false)).toBe("thinking");
  });

  // Terminal status outranks the transcript: a lane whose last event was a tool
  // call but which has since ended is finished, not still working.
  it("finishes a done lane whose newest event was a tool call", () => {
    expect(actorPose(lane("done", [ev({ type: "tool_use", tool: "Bash" })]), false)).toBe("done");
  });

  it("fails an errored lane", () => {
    expect(actorPose(lane("error"), false)).toBe("failed");
  });

  // Events the actor has no pose for must not blank it out.
  it("falls back to thinking for an event it has no pose for", () => {
    expect(actorPose(lane("running", [ev({ type: "tool_gate", asked: false })]), false)).toBe(
      "thinking",
    );
  });
});
