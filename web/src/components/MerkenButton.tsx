"use client";

import Link from "next/link";
import { useState } from "react";
import { useLocale, useT } from "../i18n";
import { checkBlocked, reportBlocked, useSession } from "../lib/auth";
import { planErrorText, savePlan, type PlanError, type PlanKind } from "../lib/plans";

/** „Merken“: saves the payload unchanged, then shows „Gemerkt“. Without a session a link to the
 * sign-in that comes back here; a refused save of a blocked account signs it out. */
export default function MerkenButton({ kind, title, payload, className = "", label, savedLabel, onPhoto = false, disabled = false }: { kind: PlanKind; title: string; payload: unknown; className?: string; label?: string; savedLabel?: string; onPhoto?: boolean; disabled?: boolean }) {
  const { session } = useSession();
  const { locale } = useLocale();
  const t = useT().results;
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<PlanError | null>(null);
  if (!session) {
    const here = typeof window === "undefined" ? "/" : window.location.pathname + window.location.search;
    return (
      <div className={`flex flex-col items-start gap-1 ${className}`}>
        <Link
          href={`/anmelden?next=${encodeURIComponent(here)}`}
          className={`rounded-full border px-3 py-1 text-xs ${onPhoto ? "border-white/60 bg-papier text-wald-dunkel shadow hover:bg-white" : "border-wald-dunkel/30 hover:bg-wald-dunkel/10"}`}
        >
          {t.signInToSave}
        </Link>
      </div>
    );
  }
  const save = async () => {
    setState("saving");
    setError(null);
    const r = await savePlan(kind, title, payload);
    if (r.error) {
      if (await checkBlocked()) return reportBlocked();
      setError(r.error);
      setState("idle");
    } else setState("saved");
  };
  return (
    <div className={`flex flex-col items-start gap-1 ${className}`}>
      <button
        type="button"
        onClick={() => void save()}
        disabled={disabled || state !== "idle"}
        className={`rounded-full border px-3 py-1 text-xs disabled:opacity-60 ${onPhoto ? "border-white/60 bg-papier text-wald-dunkel shadow hover:bg-white" : "border-wald-dunkel/30 hover:bg-wald-dunkel/10"}`}
      >
        {state === "saved" ? (savedLabel ?? t.saved) : (label ?? t.saveOne)}
      </button>
      {error && (
        <p role="alert" className="text-xs text-red-800">
          {planErrorText(error, locale)}
        </p>
      )}
    </div>
  );
}
