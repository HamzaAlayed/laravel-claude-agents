/**
 * The flows that can strand a user, exercised against a mounted App.
 *
 * Every other suite in this package tests pure functions, which is why ~480 lines
 * of React shipped without ever being rendered. These four are the ones where a
 * regression is silent and unrecoverable from the browser: a parked approval, a
 * queue of them, a run that dies without a result, and an interrupt that fails.
 */
import { afterEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UserEvent } from "@testing-library/user-event";
import App from "./App";
import { installFakeServer, testCatalog, type FakeServer } from "./test/fakeServer";
import type { Catalog } from "./lib/types";

let server: FakeServer | null = null;

afterEach(() => {
  server?.restore();
  server = null;
});

const runButton = () => screen.getByRole("button", { name: "Run" }) as HTMLButtonElement;

const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement;

/** Render the console and wait for the catalog to land. */
async function open(catalog: Catalog | null = testCatalog) {
  server = installFakeServer(catalog);
  const user = userEvent.setup();
  render(<App />);
  return { server, user };
}

/** Render, then launch a freeform run and wait for its event stream. */
async function launch(): Promise<{ server: FakeServer; user: UserEvent }> {
  const opened = await open();
  await screen.findByLabelText("Run kind");
  await opened.user.type(
    screen.getByPlaceholderText("describe the task"),
    "ship the invoice export",
  );
  await opened.user.click(runButton());
  await waitFor(() => expect(opened.server.openStreams()).toBe(1));
  return { server: opened.server, user: opened.user };
}

const approval = (promptId: string, agent: string | null, tool = "Bash") => ({
  type: "prompt",
  prompt_id: promptId,
  agent,
  tool,
  input: { command: "php artisan migrate --force" },
  is_question: false,
  suggestions: [] as unknown[],
});

const question = (promptId: string) => ({
  type: "prompt",
  prompt_id: promptId,
  agent: "qa-engineer",
  tool: "AskUserQuestion",
  is_question: true,
  suggestions: [] as unknown[],
  input: {
    questions: [
      {
        question: "Which suites should I run?",
        header: "Suites",
        multiSelect: false,
        options: [
          { label: "Unit", description: "fast" },
          { label: "Feature", description: "slower" },
        ],
      },
    ],
  },
});

describe("the run is launched", () => {
  it("degrades to a readable message when the API cannot be reached", async () => {
    await open(null);
    expect(
      await screen.findByText(/Could not reach the console API/),
    ).toBeTruthy();
  });

  it("opens one event stream, resuming from seq 0", async () => {
    const { server } = await launch();
    expect(server.streams()).toHaveLength(1);
    expect(server.streams()[0]).toContain("since=0");
    expect(server.postsTo("/api/runs")[0].body).toMatchObject({
      kind: "prompt",
      text: "ship the invoice export",
    });
  });

  it("refuses a second launch while a run is live, and says why", async () => {
    const { server, user } = await launch();
    expect(runButton().disabled).toBe(true);
    expect(screen.getByText(/interrupt it before starting another/)).toBeTruthy();

    // Implicit submission must not sneak past the disabled button either.
    await user.type(screen.getByPlaceholderText("describe the task"), "{Enter}");
    expect(server.postsTo("/api/runs")).toHaveLength(1);
  });
});

describe("a parked approval", () => {
  it("is announced by name and opens the sheet unprompted", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));

    expect(screen.getByText("Adam needs approval — Bash")).toBeTruthy();
    // The sheet opens itself: a parked run must never wait to be noticed.
    expect(await screen.findByText("Allow Bash?")).toBeTruthy();
  });

  it("answers exactly the prompt on screen", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));

    await user.click(await screen.findByRole("button", { name: "Allow once" }));

    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(1));
    expect(server.postsTo("/answer")[0].body).toEqual({
      prompt_id: "p1",
      behavior: "allow",
    });
  });

  it("sends the typed reason with a denial", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));

    await user.type(
      await screen.findByPlaceholderText(/Tell the agent why/),
      "not against production",
    );
    await user.click(button("Deny"));

    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(1));
    expect(server.postsTo("/answer")[0].body).toEqual({
      prompt_id: "p1",
      behavior: "deny",
      message: "not against production",
    });
  });

  it("marks the blocked agent's own card on the board, and no other", async () => {
    const { server, user } = await launch();
    server.emit({
      type: "agent_start",
      agent: "backend-developer",
      tool_use_id: "t1",
      task: "add the export job",
    });
    server.emit({
      type: "agent_start",
      agent: "qa-engineer",
      tool_use_id: "t2",
      task: "cover it with tests",
    });
    server.emit(approval("p1", "qa-engineer"));

    // The sheet is modal: while it is open the board is hidden from the
    // accessibility tree, so shut it the way a user would before reading cards.
    await user.click(await screen.findByRole("button", { name: "Close" }));

    const parked = button("Dina: cover it with tests");
    expect(within(parked).getByText("needs you")).toBeTruthy();
    expect(
      within(button("Adam: add the export job")).queryByText("needs you"),
    ).toBeNull();

    // Selecting a card reveals that lane's transcript under its agent's name.
    await user.click(parked);
    expect(screen.getByRole("heading", { name: "Dina" })).toBeTruthy();
  });

  it("keeps the run live and the sheet shut once the engine resolves the prompt", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));
    await user.click(await screen.findByRole("button", { name: "Allow once" }));
    server.emit({ type: "prompt_resolved", prompt_id: "p1", agent: "backend-developer" });

    await waitFor(() => expect(screen.queryByText("Allow Bash?")).toBeNull());
    // The bar animates out, so it outlives the state change by a few frames.
    await waitFor(() => expect(screen.queryByText(/needs approval/)).toBeNull(), {
      timeout: 3000,
    });
    expect(runButton().disabled).toBe(true);
  });
});

describe("a queue of approvals", () => {
  it("counts everything waiting and offers the oldest first", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.emit(approval("p2", "qa-engineer", "Write"));

    expect(screen.getByText("2 waiting on you")).toBeTruthy();
    expect(screen.getByText("Adam needs approval — Bash")).toBeTruthy();
    expect(await screen.findByText("Allow Bash?")).toBeTruthy();
  });

  it("cannot be resolved two-at-a-time by one double-click", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.emit(approval("p2", "qa-engineer", "Write"));

    const release = server.hold("/answer");
    await user.click(await screen.findByRole("button", { name: "Allow once" }));

    // The queue has already advanced: the SECOND decision is under the cursor.
    expect(await screen.findByText("Allow Write?")).toBeTruthy();
    const next = button("Allow once");
    expect(next.disabled).toBe(true);

    await user.click(next); // the stray second click of a double-click
    expect(server.postsTo("/answer")).toHaveLength(1);
    expect(server.postsTo("/answer")[0].body).toMatchObject({ prompt_id: "p1" });

    release();
  });

  it("re-arms for the next decision once the answer has landed", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.emit(approval("p2", "qa-engineer", "Write"));

    await user.click(await screen.findByRole("button", { name: "Allow once" }));
    await screen.findByText("Allow Write?");
    await waitFor(() => expect(button("Allow once").disabled).toBe(false));

    await user.click(button("Allow once"));
    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(2));
    expect(server.postsTo("/answer")[1].body).toMatchObject({ prompt_id: "p2" });
  });

  it("puts a failed answer back in the queue instead of losing the agent", async () => {
    const { server, user } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.failNext("/answer", "the run is no longer accepting answers");

    await user.click(await screen.findByRole("button", { name: "Allow once" }));

    expect(
      await screen.findByText(/the run is no longer accepting answers/),
    ).toBeTruthy();
    // The sheet closes on the way out, so the bar is the surface that has to
    // still name the parked agent — and Review must lead back to the SAME
    // decision, armed again rather than stuck disabled from the failed attempt.
    expect(screen.getByText("Adam needs approval — Bash")).toBeTruthy();
    await user.click(button("Review"));
    expect(await screen.findByText("Allow Bash?")).toBeTruthy();
    await waitFor(() => expect(button("Allow once").disabled).toBe(false));

    await user.click(button("Allow once"));
    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(2));
    expect(server.postsTo("/answer")[1].body).toMatchObject({ prompt_id: "p1" });
  });
});

describe("a question prompt", () => {
  it("sends the option the user chose", async () => {
    const { server, user } = await launch();
    server.emit(question("q1"));

    await user.click(await screen.findByRole("button", { name: "Unit" }));
    await user.click(button("Send answers"));

    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(1));
    expect(server.postsTo("/answer")[0].body).toEqual({
      prompt_id: "q1",
      behavior: "allow",
      answers: { "Which suites should I run?": "Unit" },
    });
  });

  it("sends what the user typed instead of the option they had clicked", async () => {
    const { server, user } = await launch();
    server.emit(question("q1"));

    await user.click(await screen.findByRole("button", { name: "Unit" }));
    await user.type(
      screen.getByPlaceholderText("Other — type your own answer"),
      "the migration suite only",
    );
    await user.click(button("Send answers"));

    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(1));
    expect(server.postsTo("/answer")[0].body).toMatchObject({
      answers: { "Which suites should I run?": "the migration suite only" },
    });
  });

  it("does not carry one prompt's typing into the next one", async () => {
    const { server, user } = await launch();
    server.emit(question("q1"));
    server.emit(question("q2"));

    await user.type(
      await screen.findByPlaceholderText("Other — type your own answer"),
      "the migration suite only",
    );
    await user.click(button("Send answers"));

    await waitFor(() => expect(server.postsTo("/answer")).toHaveLength(1));
    expect(
      (screen.getByPlaceholderText("Other — type your own answer") as HTMLInputElement).value,
    ).toBe("");
  });
});

describe("a run that ends badly", () => {
  it("reports an errored run as ended and lets another one start", async () => {
    const { server } = await launch();
    expect(runButton().disabled).toBe(true);

    server.emit({ type: "error", message: "CLINotConnectedError: transport closed" });

    expect(screen.getByText(/The run ended with an error/)).toBeTruthy();
    expect(screen.getByText(/transport closed/)).toBeTruthy();
    expect(runButton().disabled).toBe(false);
    // No result, so nothing may claim there is a final answer.
    expect(screen.queryByText("Final answer")).toBeNull();
  });

  it("treats a failed interrupt as an ended run rather than wedging the console", async () => {
    const { server, user } = await launch();
    server.failNext("/interrupt", "CLINotConnectedError");

    await user.click(button("Interrupt the running agent"));

    expect(await screen.findByText(/treating this run as ended/)).toBeTruthy();
    await waitFor(() => expect(runButton().disabled).toBe(false));
  });

  it("ends the run on a successful interrupt", async () => {
    const { server, user } = await launch();
    await user.click(button("Interrupt the running agent"));

    await waitFor(() => expect(server.postsTo("/interrupt")).toHaveLength(1));
    await waitFor(() => expect(runButton().disabled).toBe(false));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warns when the pack did not load cleanly", async () => {
    const { server } = await launch();
    server.emit({ type: "init", plugins: ["laravel-team"], plugin_errors: ["boom"] });

    expect(screen.getByText(/did not load cleanly/)).toBeTruthy();
  });
});

describe("calls that ran without an ask", () => {
  const gate = (agent: string | null, toolUseId: string, asked = false) => ({
    type: "tool_gate",
    agent,
    tool: "Read",
    tool_use_id: toolUseId,
    asked,
  });

  it("says so on the card of the agent that made them", async () => {
    const { server, user } = await launch();
    server.emit({
      type: "agent_start",
      agent: "backend-developer",
      tool_use_id: "t1",
      task: "add the export job",
    });
    server.emit({
      type: "agent_start",
      agent: "qa-engineer",
      tool_use_id: "t2",
      task: "cover it with tests",
    });
    server.emit(gate("qa-engineer", "r1"));
    server.emit(gate("qa-engineer", "r2"));

    const card = button("Dina: cover it with tests");
    expect(within(card).getByText("2 ran unasked")).toBeTruthy();
    expect(
      within(button("Adam: add the export job")).queryByText(/ran unasked/),
    ).toBeNull();
    // Nothing to answer — this is a record, not a decision.
    expect(screen.queryByText(/needs approval/)).toBeNull();
    expect(user).toBeTruthy();
  });

  it("says so for the main thread, which has no card", async () => {
    const { server } = await launch();
    server.emit(gate(null, "r1"));

    expect(screen.getByText("1 ran unasked on the main thread")).toBeTruthy();
  });

  it("stays quiet about calls the browser was asked about", async () => {
    const { server } = await launch();
    server.emit(gate(null, "r1", true));

    expect(screen.queryByText(/ran unasked/)).toBeNull();
  });
});

describe("the follow-up composer", () => {
  it("sends a reply and clears the box", async () => {
    const { server, user } = await launch();
    const box = screen.getByLabelText("Follow-up message") as HTMLInputElement;

    await user.type(box, "use the queue, not a sync job");
    await user.click(button("Send"));

    await waitFor(() => expect(server.postsTo("/message")).toHaveLength(1));
    expect(server.postsTo("/message")[0].body).toEqual({
      text: "use the queue, not a sync job",
    });
    expect(box.value).toBe("");
  });

  it("gives the text back when the send fails", async () => {
    const { server, user } = await launch();
    server.failNext("/message", "the run has already finished");
    const box = screen.getByLabelText("Follow-up message") as HTMLInputElement;

    await user.type(box, "use the queue");
    await user.click(button("Send"));

    expect(await screen.findByText(/the run has already finished/)).toBeTruthy();
    expect(box.value).toBe("use the queue");
  });

  it("is gone once the run is over", async () => {
    const { server } = await launch();
    server.emit({ type: "result", subtype: "success", result: "shipped", duration_ms: 10, total_cost_usd: 0.1 });

    expect(screen.queryByLabelText("Follow-up message")).toBeNull();
    expect(screen.getByText("shipped")).toBeTruthy();
  });
});
