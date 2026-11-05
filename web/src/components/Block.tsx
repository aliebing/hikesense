/** A light, slightly see-through content block on the page (70 %, no blur: the
 * backdrop photo shows through as it is, and the text stays readable), labelled by its heading. */
export default function Block({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  const id = `block-${title.replace(/[^a-zA-Z0-9]+/g, "-").toLowerCase()}`;
  return (
    <section aria-labelledby={id} className={`flex min-w-0 flex-col gap-2 rounded-2xl bg-papier/70 p-4 text-wald-dunkel ${className}`}>
      <h2 id={id} className="font-serif text-xl">
        {title}
      </h2>
      {children}
    </section>
  );
}
