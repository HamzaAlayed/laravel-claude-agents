/**
 * Dev-only capture harness. Mounts the real App against a browser-safe copy of
 * the test fake (same catalog + mid-run events as App.test.tsx) so Playwright
 * can photograph the pipeline board. Not imported from main.tsx.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import App from "../App";
import { testCatalog } from "../test/fakeServer";
import "../index.css";

class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  closed = false;
  readyState = 1;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
}

type PoseServer = {
  emit: (event: Record<string, unknown> & { type: string }) => void;
  openStreams: () => number;
};

function installPoseFake(): PoseServer {
  const realFetch = globalThis.fetch;
  const realEventSource = globalThis.EventSource;
  FakeEventSource.instances = [];
  let launched = 0;
  let seq = 0;

  const respond = (body: unknown, ok = true, status = 200) =>
    ({
      ok,
      status,
      statusText: ok ? "OK" : "Internal Server Error",
      json: async () => body,
    }) as Response;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/catalog")) return respond(testCatalog);
    if ((init?.method ?? "GET") === "GET") {
      if (url === "/api/runs") return respond({ runs: [] });
      return respond({ error: "no such route" }, false, 404);
    }
    if (url === "/api/runs") return respond({ run_id: `run-${++launched}` });
    return respond({ ok: true });
  }) as typeof fetch;

  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;

  void realFetch;
  void realEventSource;

  return {
    emit: (event) => {
      const stream = [...FakeEventSource.instances].reverse().find((s) => !s.closed);
      if (!stream) throw new Error("no open event stream — has a run been launched?");
      seq += 1;
      stream.onmessage?.({
        data: JSON.stringify({
          seq,
          run_id: "run-1",
          ts: Date.now(),
          agent: null,
          ...event,
        }),
      });
    },
    openStreams: () => FakeEventSource.instances.filter((stream) => !stream.closed).length,
  };
}

function waitFor(predicate: () => boolean, timeoutMs = 8_000): Promise<void> {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (predicate()) {
        resolve();
        return;
      }
      if (Date.now() - started > timeoutMs) {
        reject(new Error("poseBoard timed out waiting for the console"));
        return;
      }
      requestAnimationFrame(tick);
    };
    tick();
  });
}

function setInputValue(input: HTMLInputElement, value: string) {
  const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
  proto?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function buttonNamed(name: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll("button")].find((button) => {
    const label = button.getAttribute("aria-label") ?? button.textContent ?? "";
    return label.replace(/\s+/g, " ").trim() === name;
  }) as HTMLButtonElement | undefined;
}

async function pose(server: PoseServer) {
  await waitFor(() => Boolean(document.querySelector('[placeholder="describe the task"]')));
  const field = document.querySelector('[placeholder="describe the task"]');
  if (!(field instanceof HTMLInputElement)) throw new Error("task field missing");
  setInputValue(field, "ship the invoice export");
  buttonNamed("Run")?.click();
  await waitFor(() => server.openStreams() === 1);

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
  server.emit({
    type: "prompt",
    prompt_id: "p1",
    agent: "qa-engineer",
    tool: "Bash",
    input: { command: "php artisan migrate --force" },
    is_question: false,
    suggestions: [],
  });

  await waitFor(() => Boolean(buttonNamed("Close")));
  buttonNamed("Close")?.click();
  await waitFor(
    () =>
      Boolean(buttonNamed("Adam: add the export job")) &&
      Boolean(buttonNamed("Dina: cover it with tests")),
  );
  document.documentElement.dataset.poseReady = "1";
}

const server = installPoseFake();
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>,
);
void pose(server);
