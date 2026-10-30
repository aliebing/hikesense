"use client";

import { useEffect } from "react";
import type { Photo } from "../lib/data";

/** Dialog listing author, licence (linked) and Commons page of every tile photo; closes with the button or Escape. */
export default function CreditsOverlay({ photos, onClose }: { photos: Photo[]; onClose(): void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-30 grid place-items-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Bildnachweise"
        className="flex max-h-[85dvh] w-full max-w-lg flex-col gap-3 rounded-2xl bg-wald-dunkel p-5 text-papier shadow-2xl"
      >
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-serif text-xl">Bildnachweise</h2>
          <button type="button" onClick={onClose} className="rounded-full border border-papier/40 px-3 py-1 text-sm hover:bg-papier/10">
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
