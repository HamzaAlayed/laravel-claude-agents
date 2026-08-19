import { describe, expect, it } from "vitest";
import { formatRunLabel } from "./runLabel";
import type { RunRow } from "./api";

const NOW = 1_800_000_000_000;
const row = (over: Partial<RunRow> = {}): RunRow => ({
  run_id: "r1",
  status: "done",
  spec: { kind: "make-feature" },
  started_at: 0,
  ...over,
});

describe("formatRunLabel", () => {
  it("reads kind · status · relative time", () => {
    expect(formatRunLabel(row({ started_at: NOW - 12 * 60_000 }), NOW)).toBe(
      "make-feature · done · 12m ago",
    );
  });

  it("calls the last minute 'just now'", () => {
    expect(formatRunLabel(row({ started_at: NOW - 5_000 }), NOW)).toBe(
      "make-feature · done · just now",
    );
  });

  it("scales to hours and days", () => {
    expect(formatRunLabel(row({ started_at: NOW - 3 * 3_600_000 }), NOW)).toBe(
      "make-feature · done · 3h ago",
    );
    expect(formatRunLabel(row({ started_at: NOW - 2 * 86_400_000 }), NOW)).toBe(
      "make-feature · done · 2d ago",
    );
  });

  it("falls back to 'run' for disk-derived rows whose spec is gone", () => {
    expect(formatRunLabel(row({ spec: null, started_at: NOW - 5_000 }), NOW)).toBe(
      "run · done · just now",
    );
  });

  it("omits the time segment when started_at is missing", () => {
    expect(formatRunLabel(row(), NOW)).toBe("make-feature · done");
  });

  it("treats a future started_at as clock skew, not a negative age", () => {
    expect(formatRunLabel(row({ started_at: NOW + 30_000 }), NOW)).toBe(
      "make-feature · done · just now",
    );
  });
});
