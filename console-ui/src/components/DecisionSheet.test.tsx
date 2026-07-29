import { describe, expect, it } from "vitest";
import { buildAnswers } from "./DecisionSheet";

const questions = [
  {
    question: "How should I partition?",
    header: "Partition",
    multiSelect: false,
    options: [{ label: "Hash", description: "" }, { label: "Range", description: "" }],
  },
  {
    question: "Which suites?",
    header: "Suites",
    multiSelect: true,
    options: [{ label: "Unit", description: "" }, { label: "Feature", description: "" }],
  },
];

describe("buildAnswers", () => {
  it("maps a single select to its label", () => {
    expect(buildAnswers(questions, { "How should I partition?": ["Hash"] })).toEqual({
      "How should I partition?": "Hash",
    });
  });

  it("keeps a multi-select as an array", () => {
    const out = buildAnswers(questions, { "Which suites?": ["Unit", "Feature"] });
    expect(out["Which suites?"]).toEqual(["Unit", "Feature"]);
  });

  it("uses free text verbatim rather than the word Other", () => {
    const out = buildAnswers(questions, { "How should I partition?": ["by tenant id, hashed"] });
    expect(out["How should I partition?"]).toBe("by tenant id, hashed");
  });

  it("omits unanswered questions", () => {
    expect(buildAnswers(questions, {})).toEqual({});
  });
});
