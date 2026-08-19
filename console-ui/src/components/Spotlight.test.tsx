import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Spotlight } from "./Spotlight";
import type { PendingPrompt } from "@/lib/types";

const pending: PendingPrompt = {
  prompt_id: "p1",
  agent: "backend-developer",
  agentConfidence: "exact",
  tool: "Bash",
  input: { command: "php artisan migrate --force" },
  is_question: false,
  suggestions: [] as unknown[],
};

const mount = (
  over: Partial<Parameters<typeof Spotlight>[0]> = {},
) => {
  const onAnswer = vi.fn();
  const onClose = vi.fn();
  const view = render(
    <Spotlight
      pending={pending}
      disabled={false}
      queueLength={1}
      onClose={onClose}
      onAnswer={onAnswer}
      {...over}
    />,
  );
  return { onAnswer, onClose, user: userEvent.setup(), ...view };
};

describe("the queue counter", () => {
  it("tells the user where they are in the queue", () => {
    mount({ queueLength: 2 });
    expect(screen.getByText("2 remaining")).toBeTruthy();
  });

  it("drops the counter when only one decision remains", () => {
    mount({ queueLength: 1 });
    expect(screen.queryByText(/remaining/)).toBeNull();
  });
});

describe("the parked actor", () => {
  it("takes the stage at lg with a needs pose and no hover", () => {
    const { container } = mount();
    const actor = container.querySelector("[data-pose]") as HTMLElement;
    expect(actor.dataset.pose).toBe("needs");
    expect(actor.hasAttribute("data-hover")).toBe(false);
  });
});

describe("the canvas is not a sheet", () => {
  it("does not mount a dialog", () => {
    mount();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("focuses Close when it opens", () => {
    mount();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
  });
});

describe("the decision", () => {
  it("keeps the Allow title App already looks for", () => {
    mount();
    expect(screen.getByText("Allow Bash?")).toBeTruthy();
  });

  it("sends Allow once with the same payload DecisionSheet used", async () => {
    const { onAnswer, user } = mount();
    await user.click(screen.getByRole("button", { name: "Allow once" }));
    expect(onAnswer).toHaveBeenCalledWith({ prompt_id: "p1", behavior: "allow" });
  });

  it("sends Deny with the same payload DecisionSheet used", async () => {
    const { onAnswer, user } = mount();
    await user.click(screen.getByRole("button", { name: "Deny" }));
    expect(onAnswer).toHaveBeenCalledWith({
      prompt_id: "p1",
      behavior: "deny",
      message: "The user denied this action.",
    });
  });

  it("sends Allow always when a suggestion is on offer", async () => {
    const { onAnswer, user } = mount({
      pending: { ...pending, suggestions: [{}] },
    });
    await user.click(screen.getByRole("button", { name: "Allow always" }));
    expect(onAnswer).toHaveBeenCalledWith({
      prompt_id: "p1",
      behavior: "allow",
      remember: true,
    });
  });

  it("closes when the user dismisses", async () => {
    const { onClose, user } = mount();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables Allow once while the submit gate is closed", () => {
    mount({ disabled: true });
    expect(
      (screen.getByRole("button", { name: "Allow once" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
