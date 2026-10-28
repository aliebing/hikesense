/** Chat window of layout A. Input is disabled until the planning agent exists. */
export default function ChatShell({ intro }: { intro: string }) {
  return (
    <aside
      aria-label="Planungs-Chat"
      className="flex w-full flex-col gap-3 rounded-2xl border border-white/15 bg-papier/15 p-4 text-papier shadow-xl backdrop-blur-xl sm:max-w-sm"
    >
      <h2 className="font-serif text-lg">Planungs-Chat</h2>
      <p className="rounded-xl rounded-tl-sm bg-papier/90 px-3 py-2 text-sm leading-relaxed text-wald-dunkel">{intro}</p>
      <form className="flex gap-2">
        <input
          type="text"
          disabled
          placeholder="Der Planungs-Chat kommt bald"
          aria-label="Nachricht"
          className="min-w-0 flex-1 rounded-full border border-white/25 bg-black/20 px-4 py-2 text-sm text-papier placeholder:text-papier/70 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled
          className="rounded-full bg-wald px-4 py-2 text-sm text-papier opacity-60 disabled:cursor-not-allowed"
        >
          Senden
        </button>
      </form>
    </aside>
  );
}
