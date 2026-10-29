/** Readable message panel for missing data / configuration problems. */
export default function Notice({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <section role="status" className="max-w-xl rounded-2xl bg-papier/95 p-5 text-wald-dunkel shadow-xl">
      <h2 className="font-serif text-xl">{title}</h2>
      {children && <div className="mt-2 space-y-2 text-sm leading-relaxed">{children}</div>}
    </section>
  );
}
