import { describe, expect, it } from "vitest";
import { sceneOf } from "./scene";

const idle = {
  runActive: false,
  recorded: false,
  pending: 0,
  spotlightOpen: false,
};

describe("sceneOf", () => {
  it("is call when nothing is running", () => {
    expect(sceneOf(idle)).toBe("call");
  });

  it("is floor for a live run with no spotlight", () => {
    expect(sceneOf({ ...idle, runActive: true })).toBe("floor");
  });

  it("is spotlight only when live, open, and a prompt waits", () => {
    expect(
      sceneOf({ runActive: true, recorded: false, pending: 1, spotlightOpen: true }),
    ).toBe("spotlight");
  });

  it("stays floor when the human dismissed but a prompt still waits", () => {
    expect(
      sceneOf({ runActive: true, recorded: false, pending: 1, spotlightOpen: false }),
    ).toBe("floor");
  });

  it("never spotlights a recording", () => {
    expect(
      sceneOf({ runActive: false, recorded: true, pending: 1, spotlightOpen: true }),
    ).toBe("floor");
  });
});
