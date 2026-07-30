import { describe, expect, it } from "vitest";
import { armGate, canSubmit, settleSubmit, startSubmit } from "./submitGate";

// These are the exact double-click sequence from the field report, replayed as
// gate transitions: two prompts queued, "Allow once" clicked twice while the
// first answer is still on the wire. App drives this gate from its own state,
// which is why the sheet's remount between p1 and p2 cannot reset it.
describe("submit gate", () => {
  it("allows only the prompt it is armed for", () => {
    const armed = armGate("p1");
    expect(canSubmit(armed, "p1")).toBe(true);
    expect(canSubmit(armed, "p2")).toBe(false);
    expect(canSubmit(armGate(null), "p1")).toBe(false);
  });

  it("refuses a second submit for the same prompt while the first is in flight", () => {
    const inFlight = startSubmit(armGate("p1"), "p1");
    expect(inFlight.inFlight).toBe("p1");
    expect(canSubmit(inFlight, "p1")).toBe(false);
    // The second click is a no-op, not a second POST.
    expect(startSubmit(inFlight, "p1")).toBe(inFlight);
  });

  // The mis-approval: answering p1 advances the queue, so p2's identical button
  // is under the cursor before the POST has even settled.
  it("refuses the next queued prompt revealed while an answer is in flight", () => {
    const inFlight = startSubmit(armGate("p1"), "p1");
    expect(canSubmit(inFlight, "p2")).toBe(false);
    expect(startSubmit(inFlight, "p2")).toBe(inFlight);
  });

  it("stays closed after the POST settles until the sheet is re-armed", () => {
    const settled = settleSubmit(startSubmit(armGate("p1"), "p1"), "p1");
    expect(settled.inFlight).toBeNull();
    expect(canSubmit(settled, "p1")).toBe(false);
    expect(canSubmit(settled, "p2")).toBe(false);
    // Arming is App's effect, one render after the sheet re-keyed for p2.
    expect(canSubmit(armGate("p2"), "p2")).toBe(true);
  });

  it("ignores a settle for a prompt that is not the one in flight", () => {
    const inFlight = startSubmit(armGate("p1"), "p1");
    expect(settleSubmit(inFlight, "p2")).toBe(inFlight);
    expect(canSubmit(settleSubmit(inFlight, "p2"), "p2")).toBe(false);
  });

  // A failed POST puts the prompt back at the head of the queue; the user must
  // be able to answer it again.
  it("re-arms a prompt whose answer failed and came back", () => {
    const settled = settleSubmit(startSubmit(armGate("p1"), "p1"), "p1");
    expect(canSubmit(armGate("p1"), "p1")).toBe(true);
    expect(settled.armedFor).toBeNull();
  });
});
