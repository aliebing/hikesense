"use client";

import { useRef, useState } from "react";
import { useT } from "../i18n";
import type { PhotoErrorCode } from "../lib/photo";
import { getBrowserSupabase, useSession } from "../lib/auth";
import { prepareUpload, uploadOwnPhoto } from "../lib/photo";

/** „Eigenes Foto“ button for signed-in users: strips location data in the browser, then uploads privately. */
export default function PhotoUpload({ trailId, onUploaded }: { trailId: string; onUploaded: () => void }) {
  const { session } = useSession();
  const t = useT().tour;
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
      // PhotoError carries a code; anything else gets the generic text
      const code = (e as { code?: PhotoErrorCode } | null)?.code;
      setError(code && code in t.photoErrors ? t.photoErrors[code] : t.photoUploadFailed);
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
        aria-label={t.photoChoose}
        onChange={(e) => void choose(e.target.files?.[0])}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        className="rounded-full px-3 py-1 text-xs hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-current disabled:opacity-60"
      >
        {busy ? t.photoPreparing : t.photoAdd}
      </button>
      {error && (
        <span role="alert" className="rounded bg-red-100 px-2 text-xs text-red-900">
          {error}
        </span>
      )}
    </span>
  );
}
