import { useState } from "react";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { fadeRise } from "@/lib/motion";
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
  const match = /^(\s*"[^"]+":)(.*)$/.exec(line);
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
  /**
   * True while an answer is in flight or this prompt has only just appeared —
   * one click must resolve exactly one decision. Owned by App: this component is
   * remounted per prompt_id, so a local flag would reset at the very moment the
   * queue advances. See lib/submitGate.ts.
   */
  disabled: boolean;
  /** How many decisions are waiting, including this one. Drives the "Decision
   * 1 of N" counter — hidden when there is nothing else queued behind it. */
  queueLength: number;
  onClose: () => void;
  onAnswer: (payload: Record<string, unknown>) => void;
}) {
  const [selections, setSelections] = useState<Record<string, string[]>>({});
  const [other, setOther] = useState<Record<string, string>>({});
  const [denyReason, setDenyReason] = useState("");
  const questions = (pending.input.questions as Question[]) ?? [];

  const toggle = (question: Question, label: string) =>
    setSelections((prev) => {
      const current = prev[question.question] ?? [];
      if (!question.multiSelect) return { ...prev, [question.question]: [label] };
      return {
        ...prev,
        [question.question]: current.includes(label)
          ? current.filter((entry) => entry !== label)
          : [...current, label],
      };
    });

  const submitQuestions = () =>
    onAnswer({
      prompt_id: pending.prompt_id,
      behavior: "allow",
      answers: buildAnswers(questions, mergeFreeText(selections, other)),
    });

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="bottom" className="max-h-[80vh] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            {pending.is_question ? "The Guild has questions" : `Allow ${pending.tool}?`}
          </SheetTitle>
          {queueLength > 1 && (
            <SheetDescription>Decision 1 of {queueLength}</SheetDescription>
          )}
        </SheetHeader>

        {pending.is_question ? (
          <motion.div {...fadeRise} className="space-y-5 py-4">
            {questions.map((question) => (
              <fieldset key={question.question}>
                <legend className="mb-2 text-sm font-medium">{question.question}</legend>
                <div className="flex flex-wrap gap-2">
                  {question.options.map((option) => (
                    <Button
                      key={option.label}
                      type="button"
                      variant={
                        (selections[question.question] ?? []).includes(option.label)
                          ? "default"
                          : "outline"
                      }
                      size="sm"
                      onClick={() => toggle(question, option.label)}
                      title={option.description}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
                <Input
                  className="mt-2"
                  placeholder="Other — type your own answer"
                  value={other[question.question] ?? ""}
                  onChange={(e) =>
                    setOther((prev) => ({ ...prev, [question.question]: e.target.value }))
                  }
                />
              </fieldset>
            ))}
            <Textarea
              placeholder="…or write a freeform reply instead of choosing"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              A freeform reply here is sent by "Reply in my own words" instead of the options.
            </p>
            <div className="flex gap-2">
              <Button disabled={disabled} onClick={submitQuestions}>
                Send answers
              </Button>
              <Button
                variant="outline"
                disabled={disabled}
                onClick={() =>
                  onAnswer({
                    prompt_id: pending.prompt_id,
                    behavior: "allow",
                    answers: {},
                    response: denyReason || "Do what you judge best.",
                  })
                }
              >
                Reply in my own words
              </Button>
            </div>
          </motion.div>
        ) : (
          <motion.div {...fadeRise} className="space-y-4 py-4">
            <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs leading-relaxed">
              {JSON.stringify(pending.input, null, 2).split("\n").map((line, index) => {
                const { key, rest } = splitJsonKey(line);
                return (
                  <div key={index}>
                    {key && <span className="text-muted-foreground">{key}</span>}
                    {rest}
                  </div>
                );
              })}
            </pre>
            <Textarea
              placeholder="Tell the agent why, or what to do instead"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Sent to the agent with a denial — or use it to say what to do instead.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={disabled}
                onClick={() => onAnswer({ prompt_id: pending.prompt_id, behavior: "allow" })}
              >
                Allow once
              </Button>
              {pending.suggestions.length > 0 && (
                <Button
                  variant="secondary"
                  disabled={disabled}
                  onClick={() =>
                    onAnswer({
                      prompt_id: pending.prompt_id,
                      behavior: "allow",
                      remember: true,
                    })
                  }
                >
                  Allow always
                </Button>
              )}
              <Button
                variant="destructive"
                disabled={disabled}
                onClick={() =>
                  onAnswer({
                    prompt_id: pending.prompt_id,
                    behavior: "deny",
                    message: denyReason || "The user denied this action.",
                  })
                }
              >
                Deny
              </Button>
            </div>
          </motion.div>
        )}
      </SheetContent>
    </Sheet>
  );
}
