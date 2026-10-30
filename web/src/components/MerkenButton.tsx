"use client";

import { useState } from "react";
import { useSession } from "../lib/auth";
import { savePlan, type PlanKind } from "../lib/plans";

/** „Merken“ for signed-in users only; saves the payload unchanged, then shows „Gemerkt“. */
export default function MerkenButton({ kind, title, payload, className = "" }: { kind: PlanKind; title: string; payload: unknown; className?: string }) {
  const { session } = useSession();
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
        disabled={state !== "idle"}
        className="rounded-full border border-wald-dunkel/30 px-3 py-1 text-xs hover:bg-wald-dunkel/10 disabled:opacity-60"
      >
        {state === "saved" ? "Gemerkt" : "Merken"}
      </button>
      {error && (
        <p role="alert" className="text-xs text-red-800">
          {error}
        </p>
      )}
    </div>
  );
}
