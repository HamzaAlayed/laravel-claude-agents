import { useEffect, useState } from "react";
import { XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Actor } from "@/components/Actor";
import {
  buildAnswers,
  mergeFreeText,
  splitJsonKey,
  type Question,
} from "@/components/DecisionSheet";
import type { Agent, PendingPrompt } from "@/lib/types";

const captionClass = "text-xs text-[color-mix(in_oklab,var(--ink)_70%,transparent)]";
const fieldClass =
  "border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] text-[var(--ink)]";

export function Spotlight({
  pending,
  disabled,
  queueLength,
  onClose,
  onAnswer,
  agent,
}: {
  pending: PendingPrompt;
  /**
   * True while an answer is in flight or this prompt has only just appeared —
   * one click must resolve exactly one decision. Owned by App. See lib/submitGate.ts.
   */
  disabled: boolean;
  /** How many decisions are waiting, including this one. Hidden at 1. */
  queueLength: number;
  onClose: () => void;
  onAnswer: (payload: Record<string, unknown>) => void;
  agent?: Agent;
}) {
  const [selections, setSelections] = useState<Record<string, string[]>>({});
  const [other, setOther] = useState<Record<string, string>>({});
  const [denyReason, setDenyReason] = useState("");
  const questions = (pending.input.questions as Question[]) ?? [];

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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
    <section className="relative flex min-h-dvh flex-col bg-[var(--paper)] px-8 py-10 text-[var(--ink)]">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="absolute top-3 right-3 text-[var(--ink)]"
        onClick={onClose}
      >
        <XIcon />
        <span className="sr-only">Close</span>
      </Button>

      <header className="mb-8 flex flex-col items-start gap-4">
        <Actor
          pose="needs"
          color={agent?.color ?? "#64748b"}
          slug={pending.agent ?? undefined}
          size="lg"
        />
        <div className="space-y-1">
          <h2 className="font-heading text-2xl font-medium">
            {pending.is_question ? "The Guild has questions" : `Allow ${pending.tool}?`}
          </h2>
          {queueLength > 1 && <p className={captionClass}>{queueLength} remaining</p>}
        </div>
      </header>

      {pending.is_question ? (
        <div className="space-y-5">
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
                className={`mt-2 ${fieldClass}`}
                placeholder="Other — type your own answer"
                value={other[question.question] ?? ""}
                onChange={(e) =>
                  setOther((prev) => ({ ...prev, [question.question]: e.target.value }))
                }
              />
            </fieldset>
          ))}
          <Textarea
            className={fieldClass}
            placeholder="…or write a freeform reply instead of choosing"
            value={denyReason}
            onChange={(e) => setDenyReason(e.target.value)}
          />
          <p className={captionClass}>
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
        </div>
      ) : (
        <div className="space-y-4">
          <pre className={`overflow-x-auto border p-3 text-xs leading-relaxed font-mono font-normal ${fieldClass}`}>
            {JSON.stringify(pending.input, null, 2).split("\n").map((line, index) => {
              const { key, rest } = splitJsonKey(line);
              return (
                <div key={index}>
                  {key && (
                    <span className="text-[color-mix(in_oklab,var(--ink)_70%,transparent)]">
                      {key}
                    </span>
                  )}
                  {rest}
                </div>
              );
            })}
          </pre>
          <Textarea
            className={fieldClass}
            placeholder="Tell the agent why, or what to do instead"
            value={denyReason}
            onChange={(e) => setDenyReason(e.target.value)}
          />
          <p className={captionClass}>
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
        </div>
      )}
    </section>
  );
}
