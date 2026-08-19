import { describe, expect, it } from "vitest";
import { currentTool } from "./currentTool";
import type { GuildEvent, Lane } from "./types";

let seq = 0;
const ev = (partial: Partial<GuildEvent> & { type: string }): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: "qa-engineer", ...partial }) as GuildEvent;

const lane = (events: GuildEvent[]): Lane => ({
  slug: "qa-engineer",
  task: "cover it",
  toolUseId: "t1",
  parent: null,
  status: "running",
  startedAt: 1000,
  endedAt: 0,
  events,
  unasked: 0,
});

describe("currentTool", () => {
  it("is null when no tool has been called yet", () => {
    expect(currentTool(lane([]))).toBeNull();
    expect(currentTool(lane([ev({ type: "text", text: "thinking" })]))).toBeNull();
  });

  it("returns the most recent tool_use, not an older one", () => {
    expect(
      currentTool(
        lane([
          ev({ type: "tool_use", tool: "Read" }),
          ev({ type: "tool_result" }),
          ev({ type: "tool_use", tool: "Bash" }),
        ]),
      ),
    ).toBe("Bash");
  });

  it("skips later non-tool events when finding the latest call", () => {
    expect(
      currentTool(
        lane([
          ev({ type: "tool_use", tool: "Read" }),
          ev({ type: "text", text: "looking" }),
        ]),
      ),
    ).toBe("Read");
  });

  it("stays on the last tool_use when the newest event is its tool_result", () => {
    expect(
      currentTool(
        lane([
          ev({ type: "tool_use", tool: "Read" }),
          ev({ type: "tool_result" }),
        ]),
      ),
    ).toBe("Read");
  });
});
