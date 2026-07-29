/**
 * One click, one decision.
 *
 * Answering a queued prompt advances the queue, which remounts DecisionSheet
 * (`key={prompt_id}`) with the NEXT prompt's buttons in the SAME screen
 * position. Unguarded, the second click of a double-click landed on an unread
 * decision's "Allow once" — a silent approval of something no human saw, and
 * `answers: {}` for a question prompt. For a console whose whole purpose is
 * that a human sees every decision, that is a safety failure, not a UX nit.
 *
 * The gate therefore lives in App state, not inside the sheet: the sheet is
 * remounted between the two prompts and loses any local flag. It is armed for
 * exactly one prompt_id at a time, and re-arming is a render cycle — never a
 * timer — that can only happen once the answer POST has settled AND the sheet
 * has re-keyed for whatever prompt is now on screen.
 */
export type SubmitGate = {
  /** The one prompt whose actions may be submitted. Null = nothing may be. */
  armedFor: string | null;
  /** The prompt whose answer POST is in flight. */
  inFlight: string | null;
};

/** Arm the gate for the prompt now on screen (null while there is none). */
export const armGate = (promptId: string | null): SubmitGate => ({
  armedFor: promptId,
  inFlight: null,
});

/** Is this exact prompt the armed one, with nothing else in flight? */
export const canSubmit = (gate: SubmitGate, promptId: string): boolean =>
  gate.inFlight === null && gate.armedFor === promptId;

/**
 * Take the gate for one submission. Disarms immediately, so nothing — not the
 * same prompt twice, not the next prompt the queue reveals — can submit until
 * the caller settles and re-arms.
 */
export const startSubmit = (gate: SubmitGate, promptId: string): SubmitGate =>
  canSubmit(gate, promptId) ? { armedFor: null, inFlight: promptId } : gate;

/** The POST finished (either way). Still disarmed: arming is the caller's job. */
export const settleSubmit = (gate: SubmitGate, promptId: string): SubmitGate =>
  gate.inFlight === promptId ? { armedFor: null, inFlight: null } : gate;
