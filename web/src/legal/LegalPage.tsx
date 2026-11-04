import type { Block, LegalDoc } from "./site";

// a full stop at the end of a sentence is not part of the address or link
const LINKABLE = /([\w.+-]+@[\w-]+(?:\.[\w-]+)+|https:\/\/[^\s,)]*[^\s,).])/g;

/** Text with email addresses and https links turned into links. */
function Linked({ text }: { text: string }) {
  return (
    <>
      {text.split(LINKABLE).map((part, i) => {
        if (i % 2 === 0) return part;
        const href = part.includes("@") && !part.startsWith("https://") ? `mailto:${part}` : part;
        return (
          <a key={i} href={href} className="underline underline-offset-2" {...(href.startsWith("https://") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
            {part}
          </a>
        );
      })}
    </>
  );
}

function BlockView({ b }: { b: Block }) {
  if (typeof b === "string") return <p><Linked text={b} /></p>;
  return (
    <ul className="list-disc space-y-1 pl-5">
      {b.list.map((item) => (
        <li key={item}><Linked text={item} /></li>
      ))}
    </ul>
  );
}

/** One legal page (Impressum or privacy notice) as a readable text panel. Framework-free apart
 * from React and Tailwind, so it can be copied into another app together with the texts. */
export default function LegalPage({ doc, updatedLabel, className = "" }: { doc: LegalDoc; updatedLabel: string; className?: string }) {
  return (
    <main className={`mx-auto flex w-full max-w-3xl flex-col gap-5 text-sm leading-relaxed sm:text-base ${className}`}>
      <h1 className="font-serif text-2xl sm:text-3xl">{doc.title}</h1>
      {doc.bindingNote && <p className="text-xs opacity-75">{doc.bindingNote}</p>}
      {doc.sections.map((s) => (
        <section key={s.h} className="flex flex-col gap-2 border-t border-white/10 pt-4">
          <h2 className="font-semibold">{s.h}</h2>
          {s.body.map((b, i) => (
            <BlockView key={i} b={b} />
          ))}
        </section>
      ))}
      <p className="text-xs opacity-75">{`${updatedLabel}: ${doc.updated}`}</p>
    </main>
  );
}
