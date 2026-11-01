import { Fragment, type ReactNode } from "react";

/**
 * The small Markdown subset the model writes in answers: **fett**, *kursiv*, [Text](URL),
 * "# Überschrift" and "- Liste". Builds React elements (never HTML strings), so nothing in the
 * text is interpreted as markup; links only for http(s). Line breaks stay (whitespace-pre-wrap
 * on the bubble). Unclosed markers (while streaming) stay literal.
 */
const INLINE =
  /\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*(?=\S)([^\n]*?\S)\*\*|__(?=\S)([^\n]*?\S)__|(?<![\w*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![\w*])|(?<![\w_])_(?=[^\s_])([^_\n]*?[^\s_])_(?![\w_])/g;

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const k = `${key}.${n++}`;
    const [, linkText, url, bold1, bold2, em1, em2] = m;
    if (linkText !== undefined) {
      out.push(
        /^https?:\/\//i.test(url) ? (
          <a key={k} href={url} target="_blank" rel="noreferrer" className="underline">
            {inline(linkText, k)}
          </a>
        ) : (
          <Fragment key={k}>{inline(linkText, k)}</Fragment>
        ),
      );
    } else if (bold1 !== undefined || bold2 !== undefined) {
      out.push(<strong key={k}>{inline(bold1 ?? bold2, k)}</strong>);
    } else {
      out.push(<em key={k}>{inline(em1 ?? em2, k)}</em>);
    }
    last = at + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function line(raw: string, i: number): ReactNode {
  const heading = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/.exec(raw);
  if (heading) return <strong key={i}>{inline(heading[1], `${i}`)}</strong>;
  const bullet = /^(\s*)[-*+]\s+(.*)$/.exec(raw);
  if (bullet) return <Fragment key={i}>{`${bullet[1]}• `}{inline(bullet[2], `${i}`)}</Fragment>;
  return <Fragment key={i}>{inline(raw, `${i}`)}</Fragment>;
}

export default function ChatText({ text }: { text: string }) {
  const lines = text.split("\n");
  return <>{lines.flatMap((l, i) => (i === 0 ? [line(l, i)] : ["\n", line(l, i)]))}</>;
}
