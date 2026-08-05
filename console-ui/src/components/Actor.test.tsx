/**
 * The actor is the card's one animated element. Its poses live in CSS, keyed off
 * `data-pose`, so what this component owes the stylesheet is exactly that
 * attribute plus the lane's colour — and it owes assistive tech silence, because
 * every word it could say is already in the card's own label and status line.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Actor } from "./Actor";

const actor = (container: HTMLElement) => container.querySelector("[data-pose]") as HTMLElement;

describe("Actor", () => {
  it("publishes its pose for the stylesheet to animate", () => {
    const { container } = render(<Actor pose="working" color="#22c55e" />);
    expect(actor(container).dataset.pose).toBe("working");
  });

  it("carries the agent's colour as the --lane custom property", () => {
    const { container } = render(<Actor pose="thinking" color="#b91c1c" />);
    expect(actor(container).style.getPropertyValue("--lane")).toBe("#b91c1c");
  });

  it("is hidden from assistive tech, which reads the card's label instead", () => {
    const { container } = render(<Actor pose="needs" color="#22c55e" />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  // The raised hand is a separate limb from the working arm: rotating the arm to
  // vertical put the hand beside the head in the head's own colour, which read
  // as a lump rather than a wave. Both limbs ship; CSS shows one at a time.
  it("draws a dedicated raised limb so needs-you can clear the head", () => {
    const { container } = render(<Actor pose="needs" color="#22c55e" />);
    expect(container.querySelector(".sp-raise")).not.toBeNull();
  });
});
