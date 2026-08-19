import { describe, expect, it } from "vitest";
import { buildAnswers, mergeFreeText, splitJsonKey } from "./DecisionSheet";

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

  it("omits unanswered questions", () => {
    expect(buildAnswers(questions, {})).toEqual({});
  });
});

// The previous test named "uses free text verbatim rather than the word Other"
// called buildAnswers, which has no notion of Other — the merge could be deleted
// with every test still green while the field discarded the user's input. These
// exercise the merge itself, and the composed path the Send button takes.
describe("mergeFreeText", () => {
  it("overrides the chosen option with the free text for that question", () => {
    const merged = mergeFreeText(
      { "How should I partition?": ["Hash"] },
      { "How should I partition?": "by tenant id, hashed" },
    );
    expect(merged["How should I partition?"]).toEqual(["by tenant id, hashed"]);
  });

  it("answers a question that had no selection at all", () => {
    expect(mergeFreeText({}, { "Which suites?": "smoke only" })).toEqual({
      "Which suites?": ["smoke only"],
    });
  });

  it("trims the free text", () => {
    expect(mergeFreeText({}, { "Which suites?": "  smoke only  " })).toEqual({
      "Which suites?": ["smoke only"],
    });
  });

  it("keeps the selection when the free text is blank or whitespace", () => {
    expect(
      mergeFreeText({ "Which suites?": ["Unit"] }, { "Which suites?": "   " }),
    ).toEqual({ "Which suites?": ["Unit"] });
  });

  it("leaves other questions untouched", () => {
    const merged = mergeFreeText(
      { "How should I partition?": ["Hash"], "Which suites?": ["Unit", "Feature"] },
      { "How should I partition?": "by tenant id" },
    );
    expect(merged["Which suites?"]).toEqual(["Unit", "Feature"]);
  });

  it("reaches the wire answers verbatim, not the word Other", () => {
    const answers = buildAnswers(
      questions,
      mergeFreeText(
        { "How should I partition?": ["Hash"] },
        { "How should I partition?": "by tenant id, hashed" },
      ),
    );
    expect(answers["How should I partition?"]).toBe("by tenant id, hashed");
  });
});

describe("splitJsonKey", () => {
  it("splits a key line into its key prefix and the rest", () => {
    expect(splitJsonKey('  "command": "ls -la"')).toEqual({
      key: '  "command":',
      rest: ' "ls -la"',
    });
  });

  it("leaves braces and bare lines untouched", () => {
    expect(splitJsonKey("{")).toEqual({ key: null, rest: "{" });
    expect(splitJsonKey("}")).toEqual({ key: null, rest: "}" });
  });

  it("keeps a key that contains an escaped quote as one key", () => {
    const line = JSON.stringify({ 'my"key': 1 }, null, 2).split("\n")[1] ?? "";
    expect(splitJsonKey(line)).toEqual({
      key: '  "my\\"key":',
      rest: " 1",
    });
  });
});
