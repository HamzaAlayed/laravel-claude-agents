import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Launcher, roleOf } from "./Launcher";
import { testCatalog } from "@/test/fakeServer";

const mount = (over: Partial<Parameters<typeof Launcher>[0]> = {}) => {
  const onLaunch = vi.fn();
  render(
    <Launcher catalog={testCatalog} busy={false} busyReason={null} onLaunch={onLaunch} {...over} />,
  );
  return { onLaunch, user: userEvent.setup() };
};

describe("roleOf", () => {
  it("turns a slug into a human role", () => {
    expect(roleOf("backend-developer")).toBe("backend developer");
  });
});

describe("the launcher explains itself", () => {
  it("captions the selected kind, and follows a switch", async () => {
    const { user } = mount();
    expect(screen.getByText(/task in your own words/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Command" }));
    expect(screen.getByText(/pack's slash commands/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Command" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Freeform" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("lists specialists by name and role, coordinator excluded", async () => {
    const { user } = mount();
    await user.click(screen.getByRole("button", { name: "Specialist" }));

    expect(
      screen.getByRole("option", { name: "Adam — backend developer" }),
    ).toBeTruthy();
    expect(screen.queryByRole("option", { name: /Emre/ })).toBeNull();
  });

  it("captions the selected permission mode", async () => {
    const { user } = mount();
    expect(screen.getByText(/Asks before edits and commands/)).toBeTruthy();

    await user.selectOptions(screen.getByLabelText("Permission mode"), "plan");
    expect(screen.getByText(/changes nothing/)).toBeTruthy();
  });
});

describe("Cmd/Ctrl+Enter", () => {
  it("launches from the text field", async () => {
    const { onLaunch, user } = mount();
    await user.type(screen.getByPlaceholderText("describe the task"), "ship it");
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(onLaunch).toHaveBeenCalledWith({
      kind: "prompt", target: "", text: "ship it", mode: "default",
    });
  });

  it("does nothing while a run is live", async () => {
    const { onLaunch, user } = mount({ busy: true, busyReason: "A run is in flight" });
    await user.type(screen.getByPlaceholderText("describe the task"), "ship it");
    await user.keyboard("{Control>}{Enter}{/Control}");

    expect(onLaunch).not.toHaveBeenCalled();
  });
});
