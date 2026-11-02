"use client";

import { useState } from "react";
import { useT } from "../i18n";
import { useSession } from "../lib/auth";
import { savePlan, type PlanKind } from "../lib/plans";

/** „Merken“ for signed-in users only; saves the payload unchanged, then shows „Gemerkt“. */
export default function MerkenButton({ kind, title, payload, className = "", label, savedLabel, onPhoto = false, disabled = false }: { kind: PlanKind; title: string; payload: unknown; className?: string; label?: string; savedLabel?: string; onPhoto?: boolean; disabled?: boolean }) {
  const { session } = useSession();
  const t = useT().results;
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);
  if (!session) return null;
  const save = async () => {
    setState("saving");
    setError(null);
    const r = await savePlan(kind, title, payload);
    if (r.error) {
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
          {error}
        </p>
      )}
    </div>
  );
}
