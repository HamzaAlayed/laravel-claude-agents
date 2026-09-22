import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Desk } from "./Desk";
import type { DeliveryRow } from "@/lib/api";

const tagRow = (over: Partial<DeliveryRow> = {}): DeliveryRow => ({
  name: "tag",
  status: "running",
  done_when: "POST /api/tags creates a Tag",
  issue_url: "https://github.com/acme/repo/issues/42",
  issue_number: 42,
  pr_url: "https://github.com/acme/repo/pull/17",
  pr_state: "open",
  board: "1 stages · cap: 3 spawns · done when: POST /api/tags creates a Tag · a · database-developer",
  steps: [{ who: "Database Developer", state: "Waiting" }],
  watching: false,
  ...over,
});

function mockDeliveries(rows: DeliveryRow[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method === "GET" && url.includes("/api/kernel/deliveries")) {
        return {
          ok: true,
          json: async () => ({ deliveries: rows }),
        };
      }
      if (method === "POST" && url.includes("/api/kernel/watch")) {
        return {
          ok: true,
          json: async () => ({ ok: true, watching: true }),
        };
      }
      if (method === "POST" && url.includes("/api/kernel/ingest")) {
        return {
          ok: true,
          json: async () => ({ ok: true, text: "ok" }),
        };
      }
      return { ok: false, statusText: "not found", json: async () => ({ error: "not found" }) };
    }),
  );
}

describe("Desk", () => {
  beforeEach(() => {
    mockDeliveries([tagRow()]);
  });

  it("renders a row from the mocked list", async () => {
    render(<Desk onNewRun={() => {}} onLaunch={() => {}} />);

    expect(await screen.findByRole("heading", { name: "tag" })).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    expect(screen.getByText("Done when POST /api/tags creates a Tag")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Issue #42" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "PR · open" })).toBeTruthy();
    expect(screen.getByText("Database Developer")).toBeTruthy();
    expect(screen.getByText("Waiting")).toBeTruthy();
    expect(screen.getByRole("button", { name: "New run" })).toBeTruthy();
  });

  it("Run launches make-feature with issue and no root", async () => {
    const onLaunch = vi.fn();
    const user = userEvent.setup();
    render(<Desk onNewRun={() => {}} onLaunch={onLaunch} />);

    await screen.findByText("tag");
    await user.click(screen.getByRole("button", { name: "Continue delivery" }));

    expect(onLaunch).toHaveBeenCalledTimes(1);
    const payload = onLaunch.mock.calls[0][0];
    expect(payload).toEqual({
      kind: "command",
      target: "make-feature",
      text: "tag --issue 42",
      mode: "default",
    });
    expect(payload).not.toHaveProperty("root");
  });

  it("Watch is disabled when pr_url is empty", async () => {
    mockDeliveries([tagRow({ pr_url: "" })]);
    render(<Desk onNewRun={() => {}} onLaunch={() => {}} />);

    await screen.findByText("tag");
    expect(
      (screen.getByRole("button", { name: "Monitor PR" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("Watch click POSTs {name, enabled: true} with no root", async () => {
    const user = userEvent.setup();
    render(<Desk onNewRun={() => {}} onLaunch={() => {}} />);

    await screen.findByText("tag");
    await user.click(screen.getByRole("button", { name: "Monitor PR" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call: unknown[]) =>
        String(call[0]).includes("/api/kernel/watch") &&
        (call[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body).toEqual({ name: "tag", enabled: true });
    expect(body).not.toHaveProperty("root");
  });
});
