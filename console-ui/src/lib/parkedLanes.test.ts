/**
 * The promise this rule keeps: a marked card is really the blocked one. It was
 * written inside Board and untested; the actor needs the same answer in the lane
 * panel, and two copies of a subtle rule is how the two surfaces drift apart.
 */
import { describe, expect, it } from "vitest";
import { parkedLaneIds } from "./parkedLanes";
import { emptyRun } from "./reducer";
import type { Lane, PendingPrompt, RunView } from "./types";

const lane = (slug: string, toolUseId: string, status: Lane["status"] = "running"): Lane => ({
  slug,
  task: "work",
  toolUseId,
  parent: null,
  status,
  startedAt: 1000,
  endedAt: status === "running" ? 0 : 9000,
  events: [],
  unasked: 0,
});

const prompt = (over: Partial<PendingPrompt> = {}): PendingPrompt => ({
  prompt_id: "p1",
  agent: "qa-engineer",
  agentConfidence: "exact",
  tool: "Bash",
  input: {},
  is_question: false,
  suggestions: [],
  ...over,
});

const view = (lanes: Lane[], pending: PendingPrompt[]): RunView => ({
  ...emptyRun("command"),
  lanes,
  pending,
});

describe("parkedLaneIds", () => {
  it("marks the lane a prompt names", () => {
    const ids = parkedLaneIds(view([lane("qa-engineer", "t1")], [prompt()]));
    expect([...ids]).toEqual(["t1"]);
  });

  // The bar hedges in words instead; a guess must never put a border on a card.
  it("marks nothing when the attribution is a guess", () => {
    const ids = parkedLaneIds(
      view([lane("qa-engineer", "t1")], [prompt({ agentConfidence: "guess" })]),
    );
    expect(ids.size).toBe(0);
  });

  // A prompt with no agent came from the main thread, which is the board's
  // header and not a card — so nothing is blamed.
  it("marks nothing for a main-thread prompt", () => {
    const ids = parkedLaneIds(view([lane("qa-engineer", "t1")], [prompt({ agent: null })]));
    expect(ids.size).toBe(0);
  });

  it("ignores a lane that has already finished", () => {
    const ids = parkedLaneIds(view([lane("qa-engineer", "t1", "done")], [prompt()]));
    expect(ids.size).toBe(0);
  });

  it("marks one lane per prompt when several are waiting", () => {
    const ids = parkedLaneIds(
      view(
        [lane("qa-engineer", "t1"), lane("backend-developer", "t2")],
        [prompt(), prompt({ prompt_id: "p2", agent: "backend-developer" })],
      ),
    );
    expect([...ids].sort()).toEqual(["t1", "t2"]);
  });

  it("marks nothing when no prompt is waiting", () => {
    expect(parkedLaneIds(view([lane("qa-engineer", "t1")], [])).size).toBe(0);
  });
});
