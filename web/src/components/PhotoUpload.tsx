"use client";

import { useRef, useState } from "react";
import { getBrowserSupabase, useSession } from "../lib/auth";
import { prepareUpload, uploadOwnPhoto } from "../lib/photo";

/** „Eigenes Foto“ button for signed-in users: strips location data in the browser, then uploads privately. */
export default function PhotoUpload({ trailId, onUploaded }: { trailId: string; onUploaded: () => void }) {
  const { session } = useSession();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!session) return null;
  const userId = session.user.id;

  async function choose(file: File | undefined) {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const blob = await prepareUpload(file);
      await uploadOwnPhoto(getBrowserSupabase(), userId, trailId, blob);
      onUploaded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Hochladen hat nicht geklappt");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        aria-label="Foto auswählen"
        onChange={(e) => void choose(e.target.files?.[0])}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        className="rounded-full px-3 py-1 text-xs hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier disabled:opacity-60"
      >
        {busy ? "Foto wird vorbereitet …" : "Eigenes Foto hinzufügen"}
      </button>
      {error && (
        <span role="alert" className="text-xs text-red-200">
          {error}
        </span>
      )}
    </span>
  );
}
