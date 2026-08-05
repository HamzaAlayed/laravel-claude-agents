/**
 * The card's animated element is the actor, and the actor is the running
 * indicator: a live lane therefore carries no outcome icon, because a second
 * moving glyph in a 24px row was two things saying "busy" and neither saying
 * what. The icon returns for the states that have an outcome to mark.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { AgentCard } from "./AgentCard";
import type { Agent, GuildEvent, Lane, LaneStatus } from "@/lib/types";

let seq = 0;
const ev = (partial: Partial<GuildEvent> & { type: string }): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: "qa-engineer", ...partial }) as GuildEvent;

const lane = (status: LaneStatus, events: GuildEvent[] = []): Lane => ({
  slug: "qa-engineer",
  task: "Writing the regression test",
  toolUseId: "t1",
  parent: null,
  status,
  startedAt: 1000,
  endedAt: status === "running" ? 0 : 9000,
  events,
  unasked: 0,
});

const agent: Agent = {
  slug: "qa-engineer",
  name: "Dina",
  description: "",
  model: "sonnet",
  tools: [],
  color: "#c2410c",
  stage: "Test",
};

const show = (l: Lane, parked = false) =>
  render(<AgentCard lane={l} agent={agent} parked={parked} onSelect={() => {}} />).container;

describe("AgentCard", () => {
  it("poses the actor from the lane's newest event", () => {
    const container = show(lane("running", [ev({ type: "tool_use", tool: "Bash" })]));
    expect(container.querySelector("[data-pose]")?.getAttribute("data-pose")).toBe("working");
  });

  it("poses the actor as needs-you on a parked lane", () => {
    const container = show(lane("running"), true);
    expect(container.querySelector("[data-pose]")?.getAttribute("data-pose")).toBe("needs");
  });

  it("gives the actor the agent's colour", () => {
    const container = show(lane("running"));
    const actor = container.querySelector("[data-pose]") as HTMLElement;
    expect(actor.style.getPropertyValue("--lane")).toBe("#c2410c");
  });

  // Deliberately no instrument here. At the card's size Dina's clipboard, Felix's
  // padlock and Omar's stopwatch are one indistinguishable grey lump; the panel
  // draws them at twice the size, where they read.
  it("draws no instrument at card size", () => {
    expect(show(lane("running")).querySelector("[data-prop]")).toBeNull();
  });

  it("marks no outcome while the lane is running", () => {
    expect(show(lane("running")).querySelector("[data-outcome]")).toBeNull();
  });

  it("marks the outcome once the lane is done", () => {
    expect(show(lane("done")).querySelector("[data-outcome]")?.getAttribute("data-outcome")).toBe(
      "done",
    );
  });

  it("marks an errored lane's outcome", () => {
    expect(show(lane("error")).querySelector("[data-outcome]")?.getAttribute("data-outcome")).toBe(
      "error",
    );
  });

  it("marks a parked lane as waiting on the human", () => {
    expect(
      show(lane("running"), true).querySelector("[data-outcome]")?.getAttribute("data-outcome"),
    ).toBe("parked");
  });
});
