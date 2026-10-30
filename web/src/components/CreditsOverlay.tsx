"use client";

import { useEffect, useRef } from "react";
import type { Photo } from "../lib/data";

/** Dialog listing author, licence (linked) and Commons page of every tile photo; closes with the button, Escape or a click on the backdrop; focus moves in and returns to the opener. */
export default function CreditsOverlay({ photos, onClose }: { photos: Photo[]; onClose(): void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Focus the close button on open and hand focus back to the opener on close; Escape listener registered once.
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-30 grid place-items-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Bildnachweise"
        className="flex max-h-[85dvh] w-full max-w-lg flex-col gap-3 rounded-2xl bg-wald-dunkel p-5 text-papier shadow-2xl"
      >
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-serif text-xl">Bildnachweise</h2>
          <button ref={closeRef} type="button" onClick={onClose} className="rounded-full border border-papier/40 px-3 py-1 text-sm hover:bg-papier/10">
            Schließen
          </button>
        </div>
        <ul className="grid gap-2 overflow-y-auto text-xs leading-snug">
          {photos.map((p) => (
            <li key={p.url}>
              {p.author} ·{" "}
              {p.license_url ? (
                <a href={p.license_url} target="_blank" rel="noopener noreferrer license" className="underline underline-offset-2">
                  {p.license}
                </a>
              ) : (
                p.license
              )}
              {p.page_url && (
                <>
                  {" "}·{" "}
                  <a href={p.page_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                    Wikimedia Commons
                  </a>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
