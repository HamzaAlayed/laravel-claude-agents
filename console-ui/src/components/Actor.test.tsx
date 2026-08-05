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

  /**
   * The instrument is gated on size, and the gate is the whole finding.
   *
   * Drawn on the card it occupies about nine pixels, and at nine pixels a padlock,
   * a clipboard and a stopwatch are the same grey lump — verified in a browser
   * against the built bundle, at which size the author could not tell his own
   * three drawings apart. It reads from about 2× up, so it appears where there is
   * room for it: the lane panel, which is where you go to find out what an agent
   * is actually doing. The board stays dense and clean.
   */
  it("draws no instrument at card size, however famous the craft", () => {
    const { container } = render(
      <Actor pose="working" color="#b91c1c" slug="security-engineer" />,
    );
    expect(container.querySelector(".sp-prop")).toBeNull();
  });

  it("draws the instrument at panel size", () => {
    const { container } = render(
      <Actor pose="working" color="#b91c1c" slug="security-engineer" size="lg" />,
    );
    expect(container.querySelector(".sp-prop")?.getAttribute("data-prop")).toBe("padlock");
  });

  // Drawn before the body, so the working hand passes over the tool it is using.
  it("draws the instrument behind the sprite's limbs", () => {
    const { container } = render(
      <Actor pose="working" color="#b91c1c" slug="qa-engineer" size="lg" />,
    );
    const nodes = [...container.querySelectorAll(".sp-prop, .sp-body")];
    expect(nodes[0]?.classList.contains("sp-prop")).toBe(true);
  });

  it("gives a craft with no readable object nothing, even where there is room", () => {
    const { container } = render(
      <Actor pose="working" color="#3b82f6" slug="solution-architect" size="lg" />,
    );
    expect(container.querySelector(".sp-prop")).toBeNull();
  });

  it("draws no instrument when no agent is named at all", () => {
    const { container } = render(<Actor pose="working" color="#3b82f6" size="lg" />);
    expect(container.querySelector(".sp-prop")).toBeNull();
  });

  it("draws each specialist their own object", () => {
    const held = (slug: string) => {
      const { container } = render(
        <Actor pose="thinking" color="#000" slug={slug} size="lg" />,
      );
      return container.querySelector(".sp-prop")?.getAttribute("data-prop");
    };
    expect(held("security-engineer")).toBe("padlock");
    expect(held("qa-engineer")).toBe("clipboard");
    expect(held("performance-engineer")).toBe("stopwatch");
  });
});
