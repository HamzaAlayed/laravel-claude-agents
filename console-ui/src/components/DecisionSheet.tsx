import { Spotlight } from "@/components/Spotlight";
import type { PendingPrompt } from "@/lib/types";

export type Question = {
  question: string;
  header: string;
  multiSelect: boolean;
  options: { label: string; description: string }[];
};

/**
 * Fold the per-question "Other — type your own answer" fields over the chosen
 * option labels: non-blank free text REPLACES the selection for that question.
 *
 * Exported and named because it used to be an anonymous loop inside
 * submitQuestions, testable by nothing — deleting it left every test green
 * while the Other field silently discarded whatever the user typed.
 */
export function mergeFreeText(
  selections: Record<string, string[]>,
  other: Record<string, string>,
): Record<string, string[]> {
  const merged = { ...selections };
  for (const [question, text] of Object.entries(other)) {
    if (text.trim()) merged[question] = [text.trim()];
  }
  return merged;
}

/**
 * `"key": value` → the key prefix and the rest, so the pre block can mute the
 * keys without a highlighting library. Pure and exported for the same reason
 * mergeFreeText is.
 */
export function splitJsonKey(line: string): { key: string | null; rest: string } {
  // `(?:\\.|[^"\\])*` keeps going through `\"` so `"my\"key":` is one key.
  // JSON.stringify emits exactly that form; this is a cosmetic tint and must
  // not false-positive on its output.
  const match = /^(\s*"(?:\\.|[^"\\])*":)(.*)$/.exec(line);
  return match ? { key: match[1], rest: match[2] } : { key: null, rest: line };
}

/** Answers map question text -> chosen label(s), or the user's own words. */
export function buildAnswers(
  questions: Question[],
  selections: Record<string, string[]>,
): Record<string, string | string[]> {
  const answers: Record<string, string | string[]> = {};
  for (const question of questions) {
    const chosen = selections[question.question];
    if (!chosen || chosen.length === 0) continue;
    answers[question.question] = question.multiSelect ? chosen : chosen[0];
  }
  return answers;
}

/**
 * Helpers (`buildAnswers`, `mergeFreeText`, `splitJsonKey`) stay here for
 * Spotlight. This wrapper is unused by App — scenes mount Spotlight directly.
 */
export function DecisionSheet({
  pending,
  open,
  disabled,
  queueLength,
  onClose,
  onAnswer,
}: {
  pending: PendingPrompt;
  open: boolean;
  disabled: boolean;
  queueLength: number;
  onClose: () => void;
  onAnswer: (payload: Record<string, unknown>) => void;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={pending.is_question ? "The Guild has questions" : `Allow ${pending.tool}?`}
    >
      <Spotlight
        pending={pending}
        disabled={disabled}
        queueLength={queueLength}
        onClose={onClose}
        onAnswer={onAnswer}
      />
    </div>
  );
}
