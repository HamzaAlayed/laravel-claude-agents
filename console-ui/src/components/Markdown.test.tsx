import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders headings as headings", () => {
    render(<Markdown>{"## What I did\n\nsome prose"}</Markdown>);
    expect(screen.getByRole("heading", { name: "What I did" })).toBeTruthy();
  });

  it("renders bullets as a real list", () => {
    render(<Markdown>{"- added the Action\n- moved the mail fan-out"}</Markdown>);
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual(["added the Action", "moved the mail fan-out"]);
  });

  it("renders a fenced code block inside a pre", () => {
    render(<Markdown>{"```php\n$post->load('user');\n```"}</Markdown>);
    const code = screen.getByText(/\$post->load/);
    expect(code.closest("pre")).not.toBeNull();
  });

  it("keeps inline code out of a pre", () => {
    render(<Markdown>{"use `withCount` instead"}</Markdown>);
    const code = screen.getByText("withCount");
    expect(code.tagName).toBe("CODE");
    expect(code.closest("pre")).toBeNull();
  });

  it("does NOT render raw HTML from the model as HTML", () => {
    // This text is model output rendered inside a page that can launch agents.
    // react-markdown ignores embedded HTML unless rehype-raw is added, and it is
    // deliberately not added — so this must arrive as visible text, not markup.
    const { container } = render(
      <Markdown>{'before <b>bold</b> <img src=x onerror="alert(1)"> after'}</Markdown>,
    );
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<b>bold</b>");
  });

  it("renders a link without handing it the opener", () => {
    const { container } = render(<Markdown>{"[docs](https://example.test)"}</Markdown>);
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://example.test");
    // ?? "" so a missing rel fails as a readable diff rather than erroring on null
    expect(link?.getAttribute("rel") ?? "").toContain("noreferrer");
  });

  it("passes plain prose through unchanged", () => {
    render(<Markdown>{"just a sentence"}</Markdown>);
    expect(screen.getByText("just a sentence")).toBeTruthy();
  });
});
