import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import type { PendingPrompt } from "@/lib/types";

export type Question = {
  question: string;
  header: string;
  multiSelect: boolean;
  options: { label: string; description: string }[];
};

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
  onClose,
  onAnswer,
}: {
  pending: PendingPrompt;
  open: boolean;
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

  const submitQuestions = () => {
    const merged = { ...selections };
    for (const [question, text] of Object.entries(other)) {
      if (text.trim()) merged[question] = [text.trim()];
    }
    onAnswer({
      prompt_id: pending.prompt_id,
      behavior: "allow",
      answers: buildAnswers(questions, merged),
    });
  };

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="bottom" className="max-h-[80vh] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            {pending.is_question ? "The Guild has questions" : `Allow ${pending.tool}?`}
          </SheetTitle>
        </SheetHeader>

        {pending.is_question ? (
          <div className="space-y-5 py-4">
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
            <div className="flex gap-2">
              <Button onClick={submitQuestions}>Send answers</Button>
              <Button
                variant="outline"
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
            <Textarea
              placeholder="…or write a freeform reply instead of choosing"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            <pre className="overflow-x-auto rounded-md border bg-muted/40 p-3 text-xs">
              {JSON.stringify(pending.input, null, 2)}
            </pre>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => onAnswer({ prompt_id: pending.prompt_id, behavior: "allow" })}
              >
                Allow once
              </Button>
              {pending.suggestions.length > 0 && (
                <Button
                  variant="secondary"
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
            <Textarea
              placeholder="Tell the agent why, or what to do instead"
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
