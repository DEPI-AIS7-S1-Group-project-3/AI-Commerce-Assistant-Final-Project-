import type { ReactNode } from "react";

// Tiny Markdown renderer for our own policy texts: paragraphs, "- " bullet lists,
// "> " quotes, **bold** and `code`. Anything else shows as plain text (never as HTML),
// so there is no injection risk. Extend here if policies start using more Markdown.

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-sand px-1 text-[0.9em]" dir="ltr">{part.slice(1, -1)}</code>;
    return part;
  });
}

type Block = { kind: "p" | "ul" | "quote"; lines: string[] };

function blocks(md: string): Block[] {
  const out: Block[] = [];
  for (const raw of md.split("\n")) {
    const line = raw.trim();
    if (!line) {
      out.push({ kind: "p", lines: [] }); // blank line ends the current block
      continue;
    }
    const kind: Block["kind"] = line.startsWith("- ") ? "ul" : line.startsWith(">") ? "quote" : "p";
    const text = kind === "ul" ? line.slice(2) : kind === "quote" ? line.replace(/^>\s?/, "") : line;
    const last = out[out.length - 1];
    if (last && last.kind === kind && last.lines.length) last.lines.push(text);
    else out.push({ kind, lines: [text] });
  }
  return out.filter((b) => b.lines.length);
}

export default function MiniMarkdown({ md }: { md: string }) {
  return (
    <div className="space-y-3 leading-relaxed">
      {blocks(md).map((b, i) =>
        b.kind === "ul" ? (
          <ul key={i} className="list-disc space-y-1 ps-6">
            {b.lines.map((l, j) => (
              <li key={j}>{inline(l)}</li>
            ))}
          </ul>
        ) : b.kind === "quote" ? (
          <p key={i} className="border-s-2 border-line ps-3 text-sm text-ink-soft">
            {inline(b.lines.join(" "))}
          </p>
        ) : (
          <p key={i}>{inline(b.lines.join(" "))}</p>
        ),
      )}
    </div>
  );
}
