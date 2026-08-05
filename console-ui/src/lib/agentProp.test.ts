/**
 * A prop ships only when its silhouette reads at nine pixels in the sprite's
 * hand. A craft that needs explaining gets none, and its specialist keeps the
 * plain rig — which is what stops a newly added agent from looking unfinished.
 */
import { describe, expect, it } from "vitest";
import { PROPS, propFor } from "./agentProp";

describe("propFor", () => {
  it("hands the security engineer a padlock", () => {
    expect(propFor("security-engineer")).toBe("padlock");
  });

  it("hands the QA engineer a clipboard", () => {
    expect(propFor("qa-engineer")).toBe("clipboard");
  });

  it("hands the performance engineer a stopwatch", () => {
    expect(propFor("performance-engineer")).toBe("stopwatch");
  });

  // The plain rig is the fallback, never a placeholder prop: a wrong object in
  // the hand is a worse lie than an empty one.
  it("gives an agent with no readable object nothing to hold", () => {
    expect(propFor("solution-architect")).toBeNull();
  });

  it("gives an agent it has never heard of nothing to hold", () => {
    expect(propFor("underwater-basket-weaver")).toBeNull();
  });

  // Two specialists holding the same object would make the prop a decoration
  // rather than an identity.
  it("never issues the same object twice", () => {
    const held = Object.values(PROPS);
    expect(new Set(held).size).toBe(held.length);
  });
});
