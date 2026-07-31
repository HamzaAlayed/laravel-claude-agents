/**
 * The transcript is a log tail: it must follow new events, but never yank the
 * reader back down while they are scrolled up reading what an agent already did.
 *
 * jsdom performs no layout, so scrollHeight/clientHeight are always 0 and nothing
 * is ever scrollable by default. Each test declares those two numbers on the real
 * element, which is what a browser would have computed — the assertions are then
 * about this component's real scrolling behaviour, not about a mock.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Transcript } from "./Transcript";
import type { GuildEvent } from "@/lib/types";

let seq = 0;
const ev = (text: string): GuildEvent =>
  ({ seq: ++seq, run_id: "r1", ts: 1000 + seq, agent: null, lane_id: null,
     type: "text", text }) as GuildEvent;

/** Give the element the layout a browser would have, in pixels. */
function withLayout(el: HTMLElement, { scrollHeight = 500, clientHeight = 100 } = {}) {
  Object.defineProperty(el, "scrollHeight", { value: scrollHeight, configurable: true });
  Object.defineProperty(el, "clientHeight", { value: clientHeight, configurable: true });
}

const list = () => screen.getByRole("list") as HTMLElement;

describe("Transcript", () => {
  it("is bounded and scrollable rather than growing forever", () => {
    render(<Transcript events={[ev("one")]} />);
    const el = list();
    expect(el.className).toMatch(/overflow-y-auto/);
    // Some max height must be set, or overflow-y-auto never engages.
    expect(el.className).toMatch(/max-h-/);
  });

  it("follows new events to the bottom", () => {
    const { rerender } = render(<Transcript events={[ev("one")]} />);
    const el = list();
    withLayout(el);
    el.scrollTop = 400; // at the bottom: 500 - 400 - 100 === 0

    rerender(<Transcript events={[ev("one"), ev("two")]} />);

    expect(el.scrollTop).toBe(500);
  });

  it("leaves the reader alone when they have scrolled up", () => {
    const { rerender } = render(<Transcript events={[ev("one")]} />);
    const el = list();
    withLayout(el);
    el.scrollTop = 0; // scrolled right back to the first command
    el.dispatchEvent(new Event("scroll"));

    rerender(<Transcript events={[ev("one"), ev("two")]} />);

    expect(el.scrollTop).toBe(0);
  });

  it("resumes following once they scroll back down", () => {
    const { rerender } = render(<Transcript events={[ev("one")]} />);
    const el = list();
    withLayout(el);

    el.scrollTop = 0;
    el.dispatchEvent(new Event("scroll"));
    rerender(<Transcript events={[ev("one"), ev("two")]} />);
    expect(el.scrollTop).toBe(0);

    el.scrollTop = 400; // back at the bottom
    el.dispatchEvent(new Event("scroll"));
    rerender(<Transcript events={[ev("one"), ev("two"), ev("three")]} />);
    expect(el.scrollTop).toBe(500);
  });

  it("still says so when there is nothing yet", () => {
    render(<Transcript events={[]} />);
    expect(screen.getByText("Nothing yet.")).toBeTruthy();
  });
});
