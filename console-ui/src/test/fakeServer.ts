/**
 * The console API, faked at the boundary the browser actually talks to: `fetch`
 * and `EventSource`.
 *
 * Deliberately NOT a mock of `lib/api` — the two worst defects in this console
 * were a wire-format mismatch and a queue the UI modelled as a single slot, and
 * both hid behind fixtures written from the spec rather than the dependency.
 * Faking the transport keeps `lib/api`, `lib/reducer`, `lib/submitGate` and every
 * component on the real path, so a test can only pass if the whole chain agrees.
 */
import { act } from "@testing-library/react";
import type { Catalog } from "@/lib/types";

export const testCatalog: Catalog = {
  agents: [
    {
      slug: "backend-developer",
      name: "Adam",
      description: "backend",
      model: "sonnet",
      tools: ["Read", "Edit"],
      color: "#2563eb",
      stage: "build",
    },
    {
      slug: "qa-engineer",
      name: "Dina",
      description: "qa",
      model: "sonnet",
      tools: ["Read", "Bash"],
      color: "#16a34a",
      stage: "verify",
    },
  ],
  commands: [{ slug: "review-pr", description: "review the diff", argument_hint: "" }],
  skills: [{ slug: "laravel-testing", description: "test cookbook" }],
  stages: ["build", "verify"],
};

type PostRecord = { path: string; body: Record<string, unknown> };

class FakeEventSource {
  // Copied from the real EventSource: api.streamRun compares against these, so a
  // fake without them would make the comparison silently never match.
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  closed = false;
  /** Mirrors the real readyState: 0 CONNECTING, 1 OPEN, 2 CLOSED. */
  readyState = 1;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
}

export type FakeServer = {
  /** Every POST the app has made, in order. */
  posts: PostRecord[];
  /** The POSTs whose URL ends with `suffix` (e.g. "/answer"). */
  postsTo: (suffix: string) => PostRecord[];
  /** Make the next POST to `suffix` fail the way the real API reports errors. */
  failNext: (suffix: string, message: string, status?: number) => void;
  /** Keep POSTs to `suffix` in flight until the returned release is called. */
  hold: (suffix: string) => () => void;
  /** Push one event down the newest open SSE stream, as the engine would. */
  emit: (event: Record<string, unknown> & { type: string }) => void;
  /**
   * Fail the stream for good — what a 404 does when the run is no longer live in
   * this console process (the classic case: the console was restarted).
   */
  killStream: () => void;
  /** A transient drop the browser will retry on its own. Not terminal. */
  blipStream: () => void;
  /** URLs of the SSE streams opened so far, closed ones included. */
  streams: () => string[];
  /** How many SSE streams are open right now. */
  openStreams: () => number;
  restore: () => void;
};

/**
 * @param catalog pass null to make /api/catalog fail — the no-token / dead-server
 *   path the console must degrade cleanly on.
 */
export function installFakeServer(catalog: Catalog | null = testCatalog): FakeServer {
  const realFetch = globalThis.fetch;
  const realEventSource = globalThis.EventSource;
  FakeEventSource.instances = [];

  const posts: PostRecord[] = [];
  const failures = new Map<string, { message: string; status: number }>();
  const holds = new Map<string, Promise<void>>();
  let seq = 0;
  let runs = 0;

  const respond = (body: unknown, ok = true, status = 200) =>
    ({
      ok,
      status,
      statusText: ok ? "OK" : "Internal Server Error",
      json: async () => body,
    }) as Response;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("/api/catalog")) {
      return catalog === null
        ? respond({ error: "no catalog" }, false, 500)
        : respond(catalog);
    }

    // Recorded before any hold, so a test can assert the request went out while
    // it is still in flight.
    posts.push({ path: url, body: init?.body ? JSON.parse(String(init.body)) : {} });

    for (const [suffix, pending] of holds) if (url.endsWith(suffix)) await pending;

    for (const [suffix, failure] of failures) {
      if (!url.endsWith(suffix)) continue;
      failures.delete(suffix);
      return respond({ error: failure.message }, false, failure.status);
    }

    if (url === "/api/runs") return respond({ run_id: `run-${++runs}` });
    return respond({ ok: true });
  }) as typeof fetch;

  globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;

  return {
    posts,
    postsTo: (suffix) => posts.filter((post) => post.path.endsWith(suffix)),
    failNext: (suffix, message, status = 500) => failures.set(suffix, { message, status }),
    hold: (suffix) => {
      let release = () => {};
      holds.set(
        suffix,
        new Promise<void>((resolve) => {
          release = resolve;
        }),
      );
      return () => {
        holds.delete(suffix);
        release();
      };
    },
    emit: (event) => {
      const stream = [...FakeEventSource.instances].reverse().find((s) => !s.closed);
      if (!stream) throw new Error("no open event stream — has a run been launched?");
      seq += 1;
      const payload = {
        seq,
        run_id: "run-1",
        ts: 1_700_000_000_000 + seq * 1000,
        agent: null,
        ...event,
      };
      act(() => {
        stream.onmessage?.({ data: JSON.stringify(payload) });
      });
    },
    killStream: () => {
      const stream = [...FakeEventSource.instances].reverse().find((s) => !s.closed);
      if (!stream) throw new Error("no open event stream to kill");
      stream.readyState = 2;
      act(() => {
        stream.onerror?.({});
      });
    },
    blipStream: () => {
      const stream = [...FakeEventSource.instances].reverse().find((s) => !s.closed);
      if (!stream) throw new Error("no open event stream to blip");
      stream.readyState = 0; // CONNECTING — the browser is already retrying
      act(() => {
        stream.onerror?.({});
      });
    },
    streams: () => FakeEventSource.instances.map((stream) => stream.url),
    openStreams: () => FakeEventSource.instances.filter((stream) => !stream.closed).length,
    restore: () => {
      globalThis.fetch = realFetch;
      globalThis.EventSource = realEventSource;
    },
  };
}
