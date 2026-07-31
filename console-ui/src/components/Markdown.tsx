import ReactMarkdown from "react-markdown";

/**
 * Renders an agent's answer as markdown.
 *
 * **Raw HTML is deliberately not rendered.** This text comes from a model and
 * lands in a page that can launch agents against the developer's checkout, so
 * `rehype-raw` is not installed and must not be added — react-markdown's default
 * is to pass embedded HTML through as visible text, which is what we want.
 *
 * Styling is done with arbitrary descendant variants rather than a `components`
 * map or the typography plugin: it is one place to read, and `[&_pre_code]` can
 * undo the inline-code treatment inside a fenced block, which a per-element map
 * cannot do without inspecting the node.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div
      className="text-sm break-words
        [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold
        [&_h2]:mt-3 [&_h2]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2:first-child]:mt-0
        [&_h3]:mt-3 [&_h3]:mb-1 [&_h3]:font-medium
        [&_p]:mb-2 [&_p:last-child]:mb-0
        [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-5
        [&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5
        [&_li]:mt-0.5
        [&_a]:underline [&_a]:underline-offset-2
        [&_blockquote]:mb-2 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:italic
        [&_hr]:my-3
        [&_strong]:font-semibold
        [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.85em]
        [&_pre]:mb-2 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:border [&_pre]:bg-muted/40 [&_pre]:p-3
        [&_pre_code]:bg-transparent [&_pre_code]:px-0 [&_pre_code]:py-0 [&_pre_code]:text-xs
        [&_table]:mb-2 [&_table]:w-full [&_th]:text-left [&_th]:font-medium
        [&_td]:align-top"
    >
      <ReactMarkdown
        components={{
          // Agent answers cite external docs; opening them must not hand the
          // target a handle on the console's window.
          a: ({ href, children: label }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {label}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
