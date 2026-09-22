import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KernelStrip } from "./KernelStrip";

describe("KernelStrip", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ok: true, text: "ok" }),
      }),
    );
  });

  it("reopen-on-check POSTs name, kind, stage, check without root", async () => {
    const user = userEvent.setup();
    render(<KernelStrip />);

    await user.type(screen.getByLabelText(/delivery name/i), "tag");
    await user.type(screen.getByLabelText(/^stage$/i), "a");
    await user.type(screen.getByLabelText(/check name/i), "pint");
    await user.click(screen.getByRole("button", { name: /reopen on check/i }));

    expect(fetch).toHaveBeenCalled();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]: [string]) => String(url).includes("/api/kernel/ingest"),
    ) as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body).toEqual({ name: "tag", kind: "check", stage: "a", check: "pint" });
    expect(body).not.toHaveProperty("root");
  });
});
