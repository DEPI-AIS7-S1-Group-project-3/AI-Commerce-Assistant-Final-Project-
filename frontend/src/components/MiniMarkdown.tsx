import type { ReactNode } from "react";

// Tiny Markdown renderer for assistant and policy texts: paragraphs, "- " bullet lists,
// "> " quotes, tables, **bold** and `code`. Anything else shows as plain text (never as HTML),
// so there is no injection risk.

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-sand px-1 text-[0.9em]" dir="ltr">{part.slice(1, -1)}</code>;
    return part;
  });
}

type Block =
  | { kind: "p" | "ul" | "quote"; lines: string[] }
  | { kind: "table"; rows: string[][] };

function isTableSeparator(line: string): boolean {
  return /^\|?[\s-:]+(\|[\s-:]+)+\|?$/.test(line.trim());
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function blocks(md: string): Block[] {
  const out: Block[] = [];
  const rawLines = md.split("\n");

  for (let i = 0; i < rawLines.length; i++) {
    const raw = rawLines[i];
    const line = raw.trim();
    if (!line) {
      out.push({ kind: "p", lines: [] }); // blank line ends the current block
      continue;
    }

    // Check if this line is part of a markdown table (starts or contains |)
    if (line.includes("|") && (line.startsWith("|") || line.endsWith("|") || (i + 1 < rawLines.length && isTableSeparator(rawLines[i + 1])))) {
      if (isTableSeparator(line)) {
        continue;
      }
      const cells = parseTableRow(line);
      const last = out[out.length - 1];
      if (last && last.kind === "table") {
        last.rows.push(cells);
      } else {
        out.push({ kind: "table", rows: [cells] });
      }
      continue;
    }

    const kind: "ul" | "quote" | "p" = line.startsWith("- ") || line.startsWith("* ") ? "ul" : line.startsWith(">") ? "quote" : "p";
    const text = kind === "ul" ? line.slice(2) : kind === "quote" ? line.replace(/^>\s?/, "") : line;
    const last = out[out.length - 1];
    if (last && last.kind === kind && last.lines.length) last.lines.push(text);
    else out.push({ kind, lines: [text] });
  }
  return out.filter((b) => (b.kind === "table" ? b.rows.length : b.lines.length));
}

export default function MiniMarkdown({ md, className = "" }: { md: string; className?: string }) {
  return (
    <div className={`space-y-3 leading-relaxed ${className}`}>
      {blocks(md).map((b, i) => {
        if (b.kind === "ul") {
          return (
            <ul key={i} className="list-disc space-y-1 ps-6">
              {b.lines.map((l, j) => (
                <li key={j}>{inline(l)}</li>
              ))}
            </ul>
          );
        }
        if (b.kind === "quote") {
          return (
            <p key={i} className="border-s-2 border-line ps-3 text-sm text-ink-soft">
              {inline(b.lines.join(" "))}
            </p>
          );
        }
        if (b.kind === "table") {
          const [header, ...bodyRows] = b.rows;
          return (
            <div key={i} className="my-2 overflow-x-auto rounded border border-line">
              <table className="w-full text-start text-xs sm:text-sm">
                {header && (
                  <thead className="bg-sand/60 border-b border-line">
                    <tr>
                      {header.map((col, cIdx) => (
                        <th key={cIdx} className="px-3 py-2 text-start font-semibold">
                          {inline(col)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody className="divide-y divide-line">
                  {bodyRows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-sand/20">
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2">
                          {inline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={i}>{inline(b.lines.join(" "))}</p>;
      })}
    </div>
  );
}
