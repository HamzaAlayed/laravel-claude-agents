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

const runButton = () => screen.getByRole("button", { name: "Start" }) as HTMLButtonElement;

const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement;

/**
 * Render the console and wait for the catalog to land. `seed` runs before the
 * first render, so anything it sets up is already on disk when the console opens
 * — which is the only honest way to test the recorded-run list, since the list is
 * fetched once on mount.
 */
async function open(
  catalog: Catalog | null = testCatalog,
  seed?: (server: FakeServer) => void,
) {
  server = installFakeServer(catalog);
  seed?.(server);
  const user = userEvent.setup();
  render(<App />);
  return { server, user };
}

/** Render, then launch a freeform run and wait for its event stream. */
async function launch(
  seed?: (server: FakeServer) => void,
): Promise<{ server: FakeServer; user: UserEvent }> {
  const opened = await open(testCatalog, seed);
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
    // The panel now mounts in a portal, a tick after the click.
    await user.click(parked);
    expect(await screen.findByRole("heading", { name: "Dina" })).toBeTruthy();
  });

  it("pulses the parked card so it can be found without reading", async () => {
    const { server, user } = await launch();
    // Two lanes, not one: a single lane keeps the run in "focus" mode (see
    // reducer.ts), which renders FocusRun instead of Board — there would be no
    // card at all to assert on. The sibling test above needs the same thing.
    server.emit({
      type: "agent_start", agent: "backend-developer",
      tool_use_id: "t1", task: "add the export job",
    });
    server.emit({
      type: "agent_start", agent: "qa-engineer",
      tool_use_id: "t2", task: "cover it with tests",
    });
    server.emit(approval("p1", "qa-engineer"));
    await user.click(await screen.findByRole("button", { name: "Close" }));

    // The class is the contract here: the animation itself is CSS.
    expect(button("Dina: cover it with tests").className).toContain("animate-attention");
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

describe("the transcript panel", () => {
  const start = (agent: string, toolUseId: string, task: string) => ({
    type: "agent_start", agent, tool_use_id: toolUseId, lane_id: toolUseId, task,
  });

  it("slides over the board and closes on Escape", async () => {
    const { server, user } = await launch();
    // Two lanes, not one: a single lane keeps the run in "focus" mode (see
    // reducer.ts), which renders FocusRun instead of Board — there would be no
    // card at all to click.
    server.emit(start("backend-developer", "t1", "add the export job"));
    server.emit(start("qa-engineer", "t2", "cover it with tests"));

    await user.click(button("Adam: add the export job"));
    expect(await screen.findByRole("heading", { name: "Adam" })).toBeTruthy();

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull(),
    );
  });

  it("keeps the board clickable: another card swaps the panel in place", async () => {
    const { server, user } = await launch();
    server.emit(start("backend-developer", "t1", "add the export job"));
    server.emit(start("qa-engineer", "t2", "cover it with tests"));

    await user.click(button("Adam: add the export job"));
    await screen.findByRole("heading", { name: "Adam" });

    // Non-modal by design — the board must stay reachable behind the panel.
    await user.click(button("Dina: cover it with tests"));
    expect(await screen.findByRole("heading", { name: "Dina" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull();
  });

  /**
   * The panel is pinned right at 28rem, full height, z-50; the approval bar is
   * sticky z-30 with Review right-aligned — so an open panel covered exactly that
   * button. Reproduced in a browser in this order: park a decision, dismiss the
   * sheet, open a card, then try to click Review.
   *
   * The bar now reserves the panel's width on its own trailing edge, which keeps
   * Review clear without moving the board (still clickable behind the panel) or
   * narrowing the panel itself. jsdom performs no layout, so this asserts the
   * reservation; that it un-occludes the button was verified in a real browser.
   */
  it("keeps Review reachable while a transcript panel covers the bar's edge", async () => {
    const { server, user } = await launch();
    server.emit(start("backend-developer", "t1", "add the export job"));
    server.emit(start("qa-engineer", "t2", "cover it with tests"));
    server.emit(approval("p1", "backend-developer"));

    // The sheet opens itself on arrival; dismissing it is what leaves the bar as
    // the only way back to the decision.
    await user.keyboard("{Escape}");
    const bar = await screen.findByRole("alert");
    expect(bar.dataset.insetEnd).toBe("false");

    await user.click(button("Dina: cover it with tests"));
    await screen.findByRole("heading", { name: "Dina" });
    expect(bar.dataset.insetEnd).toBe("true");

    // And it is still a working button, not just an unobscured one.
    await user.click(button("Review"));
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("yields to an arriving decision", async () => {
    const { server, user } = await launch();
    // Same two-lane requirement as above, to force board mode.
    server.emit(start("backend-developer", "t1", "add the export job"));
    server.emit(start("qa-engineer", "t2", "cover it with tests"));
    await user.click(button("Adam: add the export job"));
    await screen.findByRole("heading", { name: "Adam" });

    server.emit(approval("p1", "backend-developer"));

    // The decision sheet opens; the panel steps aside so exactly one overlay
    // ever owns the screen.
    expect(await screen.findByText("Allow Bash?")).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Adam" })).toBeNull(),
    );
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

  it("tells the user where they are in the queue", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));
    server.emit(approval("p2", "qa-engineer", "Write"));

    expect(await screen.findByText("2 remaining")).toBeTruthy();
  });

  it("drops the counter when only one decision remains", async () => {
    const { server } = await launch();
    server.emit(approval("p1", "backend-developer"));

    await screen.findByText("Allow Bash?");
    expect(screen.queryByText(/remaining/)).toBeNull();
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

describe("the coordinator on the board", () => {
  const start = (agent: string, toolUseId: string, task: string) => ({
    type: "agent_start", agent, tool_use_id: toolUseId, lane_id: toolUseId, task,
  });

  it("is the board's header, not a card in a column", async () => {
    // catalog.py gives it stage: null for exactly this reason. Board.tsx then
    // read `stage ?? "Working"`, which turned that null back into a card.
    const { server } = await launch();
    server.emit(start("delivery-coordinator", "t1", "drive the feature"));
    server.emit(start("backend-developer", "t2", "add the export job"));

    // It earns no column at all, so Working — which only appears when something
    // lands in it — should not exist.
    expect(screen.queryByRole("heading", { name: /Working/ })).toBeNull();
    expect(screen.getByText(/drive the feature/)).toBeTruthy();
    // The specialists still get their cards.
    expect(button("Adam: add the export job")).toBeTruthy();
  });

  it("still opens its transcript, so nothing is hidden", async () => {
    const { server, user } = await launch();
    server.emit(start("delivery-coordinator", "t1", "drive the feature"));
    server.emit(start("backend-developer", "t2", "add the export job"));

    // The panel now mounts in a portal, a tick after the click.
    await user.click(screen.getByRole("button", { name: /Emre/ }));
    expect(await screen.findByRole("heading", { name: "Emre" })).toBeTruthy();
  });

  it("stays out of the Working column even when that column exists", async () => {
    // With only a coordinator lane, Working is filtered out for being empty, so
    // "no card" is true for the wrong reason. An unknown agent forces the column
    // to exist, which is the only way to see whether the coordinator lands in it.
    const { server } = await launch();
    server.emit(start("delivery-coordinator", "t1", "drive the feature"));
    server.emit(start("some-new-agent", "t2", "doing something"));

    const working = screen.getByRole("heading", { name: /Working/ }).closest("section");
    expect(working).not.toBeNull();
    expect(within(working as HTMLElement).getByRole("button", { name: /some-new-agent/ })).toBeTruthy();
    expect(within(working as HTMLElement).queryByRole("button", { name: /Emre/ })).toBeNull();
  });

  it("does not swallow an agent the catalog has never heard of", async () => {
    // The `?? "Working"` fallback exists for unknown agents, and must survive:
    // an agent missing from the catalog has no stage for a DIFFERENT reason.
    const { server } = await launch();
    server.emit(start("some-new-agent", "t1", "doing something"));
    server.emit(start("backend-developer", "t2", "add the export job"));

    expect(screen.getByRole("heading", { name: /Working/ })).toBeTruthy();
    expect(button("some-new-agent: doing something")).toBeTruthy();
  });
});

describe("an attribution the engine had to guess", () => {
  const guessed = (promptId: string, agent: string) => ({
    ...approval(promptId, agent),
    agent_confidence: "guess",
  });

  it("hedges in the bar instead of naming the agent outright", async () => {
    const { server } = await launch();
    server.emit(guessed("p1", "backend-developer"));

    expect(screen.getByText("Possibly Adam needs approval — Bash")).toBeTruthy();
  });

  it("does not mark any card, because the wrong one might be marked", async () => {
    const { server, user } = await launch();
    server.emit({
      type: "agent_start", agent: "backend-developer",
      tool_use_id: "t1", task: "add the export job",
    });
    server.emit({
      type: "agent_start", agent: "qa-engineer",
      tool_use_id: "t2", task: "cover it with tests",
    });
    server.emit(guessed("p1", "qa-engineer"));
    await user.click(await screen.findByRole("button", { name: "Close" }));

    expect(
      within(button("Dina: cover it with tests")).queryByText("needs you"),
    ).toBeNull();
    // Still unmistakably parked — the bar is the honest surface for a guess.
    expect(screen.getByText(/Possibly Dina needs approval/)).toBeTruthy();
  });

  it("still names the agent outright when the engine was sure", async () => {
    const { server } = await launch();
    server.emit({ ...approval("p1", "backend-developer"), agent_confidence: "exact" });

    expect(screen.getByText("Adam needs approval — Bash")).toBeTruthy();
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

describe("recorded runs", () => {
  const picker = () =>
    screen.getByLabelText("Open a recorded run") as HTMLSelectElement;

  it("opens one from disk and shows what it did", async () => {
    // snapshot() already served these from the run jsonl; nothing in the UI
    // called it, so every finished run was unreachable from the browser.
    const opened = await open(testCatalog, (s) =>
      s.addRecordedRun({ run_id: "run_old", spec: { kind: "prompt" } }, [
        { type: "agent_start", agent: "qa-engineer", tool_use_id: "t1", lane_id: "t1", task: "cover the export" },
        { type: "result", subtype: "success", result: "shipped it", duration_ms: 10, total_cost_usd: 0.2 },
      ]),
    );
    await screen.findByLabelText("Run kind");
    await waitFor(() => expect(picker()).toBeTruthy());

    await opened.user.selectOptions(picker(), "run_old");

    expect(await screen.findByText("shipped it")).toBeTruthy();
    expect(screen.getByText(/Viewing a recorded run/)).toBeTruthy();
  });

  it("offers nothing to answer on a run that was parked when it died", async () => {
    const opened = await open(testCatalog, (s) =>
      s.addRecordedRun({ run_id: "run_parked", spec: { kind: "prompt" } }, [
        // A prompt with no prompt_resolved: the process died holding it. Its
        // future is long gone, so an approval bar here would be a lie.
        { type: "prompt", prompt_id: "p1", agent: "backend-developer", tool: "Bash",
          input: { command: "ls" }, is_question: false, suggestions: [] },
      ]),
    );
    await screen.findByLabelText("Run kind");
    await waitFor(() => expect(picker()).toBeTruthy());

    await opened.user.selectOptions(picker(), "run_parked");

    await screen.findByText(/Viewing a recorded run/);
    expect(screen.queryByText(/needs approval/)).toBeNull();
    expect(screen.queryByText("Allow Bash?")).toBeNull();
  });

  it("cannot be opened while a run is live", async () => {
    await launch((s) => s.addRecordedRun({ run_id: "run_old" }, []));

    await waitFor(() => expect(picker()).toBeTruthy());
    expect(picker().disabled).toBe(true);
  });

  it("is replaced by a new launch", async () => {
    const opened = await open(testCatalog, (s) =>
      s.addRecordedRun({ run_id: "run_old", spec: { kind: "prompt" } }, [
        { type: "result", subtype: "success", result: "old news", duration_ms: 1, total_cost_usd: 0 },
      ]),
    );
    await screen.findByLabelText("Run kind");
    await waitFor(() => expect(picker()).toBeTruthy());
    await opened.user.selectOptions(picker(), "run_old");
    await screen.findByText("old news");

    await opened.user.type(screen.getByPlaceholderText("describe the task"), "something new");
    await opened.user.click(runButton());

    await waitFor(() => expect(screen.queryByText("old news")).toBeNull());
    expect(screen.queryByText(/Viewing a recorded run/)).toBeNull();
  });
});

describe("the event stream giving out", () => {
  it("says so when it dies for good, and frees the console", async () => {
    // What a 404 does: the run is no longer live in this console process, which
    // is what a console restart looks like from the browser. It used to be
    // completely silent — the page just stopped updating.
    const { server } = await launch();
    server.killStream();

    expect(await screen.findByText(/event stream/i)).toBeTruthy();
    await waitFor(() => expect(runButton().disabled).toBe(false));
  });

  it("stays quiet while the browser is only retrying", async () => {
    const { server } = await launch();
    server.blipStream();

    expect(screen.queryByText(/event stream/i)).toBeNull();
    expect(runButton().disabled).toBe(true);
  });
});

describe("steering a live run", () => {
  const modeSelect = () =>
    screen.getByLabelText("Change this run's permission mode") as HTMLSelectElement;

  it("switches the permission mode without restarting", async () => {
    const { server, user } = await launch();
    await user.selectOptions(modeSelect(), "plan");

    await waitFor(() => expect(server.postsTo("/mode")).toHaveLength(1));
    expect(server.postsTo("/mode")[0].body).toEqual({ mode: "plan" });
    expect(modeSelect().value).toBe("plan");
  });

  it("puts the old mode back when the switch is refused", async () => {
    const { server, user } = await launch();
    server.failNext("/mode", "the run has already finished");
    await user.selectOptions(modeSelect(), "acceptEdits");

    expect(await screen.findByText(/the run has already finished/)).toBeTruthy();
    expect(modeSelect().value).toBe("default");
  });

  it("is not offered once the run is over", async () => {
    const { server } = await launch();
    server.emit({ type: "result", subtype: "success", result: "done", duration_ms: 1, total_cost_usd: 0 });

    expect(screen.queryByLabelText("Change this run's permission mode")).toBeNull();
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

  it("renders the final answer as markdown, not as a wall of asterisks", async () => {
    const { server } = await launch();
    server.emit({
      type: "result",
      subtype: "success",
      result: "## Done\n\n- added the Action\n- moved the mail fan-out",
      duration_ms: 10,
      total_cost_usd: 0.1,
    });

    expect(screen.getByRole("heading", { name: "Done" })).toBeTruthy();
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "added the Action",
      "moved the mail fan-out",
    ]);
  });
});

describe("the header status chip", () => {
  it("ticks while the run is live", async () => {
    await launch();
    expect(screen.getByText(/running ·/)).toBeTruthy();
  });

  it("turns into done when the result lands", async () => {
    const { server } = await launch();
    server.emit({ type: "result", subtype: "success", result: "shipped", duration_ms: 10, total_cost_usd: 0 });

    expect(screen.getByText("done")).toBeTruthy();
    expect(screen.queryByText(/running ·/)).toBeNull();
  });

  it("says error when the run dies", async () => {
    const { server } = await launch();
    server.emit({ type: "error", message: "CLINotConnectedError: transport closed" });

    // Scoped to the header: the main-thread transcript also renders a bare
    // "error" row for the same event, and that row is not the chip.
    const header = screen.getByText("Laravel Guild Console").closest("header") as HTMLElement;
    expect(within(header).getByText("error")).toBeTruthy();
  });

  it("says stopped after an interrupt", async () => {
    const { user } = await launch();
    await user.click(button("Interrupt the running agent"));

    expect(await screen.findByText("stopped")).toBeTruthy();
  });

  it("shows nothing for a recorded replay", async () => {
    const opened = await open(testCatalog, (s) =>
      s.addRecordedRun({ run_id: "run_old", spec: { kind: "prompt" } }, [
        { type: "result", subtype: "success", result: "old news", duration_ms: 1, total_cost_usd: 0 },
      ]),
    );
    await screen.findByLabelText("Run kind");
    // The runs list lands async — every recorded-run test waits for the picker.
    await waitFor(() =>
      expect(screen.getByLabelText("Open a recorded run")).toBeTruthy(),
    );
    await opened.user.selectOptions(
      screen.getByLabelText("Open a recorded run"), "run_old",
    );
    await screen.findByText(/Viewing a recorded run/);

    expect(screen.queryByText(/running ·/)).toBeNull();
    expect(screen.queryByText("done")).toBeNull();
  });
});
