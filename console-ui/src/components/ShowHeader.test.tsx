import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ShowHeader } from "./ShowHeader";

const mount = (over: Partial<Parameters<typeof ShowHeader>[0]> = {}) => {
  const onStop = vi.fn();
  const view = render(
    <ShowHeader
      title="ship the invoice export"
      live
      startedAt={Date.now()}
      outcome={null}
      onStop={onStop}
      {...over}
    />,
  );
  return { onStop, user: userEvent.setup(), ...view };
};

describe("ShowHeader", () => {
  it("Stop calls onStop", async () => {
    const { onStop, user } = mount();
    expect(screen.getByText("Stop")).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Stop — interrupt the running agent" }),
    );
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("does not include #guild-launcher", () => {
    mount();
    expect(document.getElementById("guild-launcher")).toBeNull();
    expect(document.getElementById("guild-call-sheet")).toBeNull(); // header is not the call sheet
  });
});
