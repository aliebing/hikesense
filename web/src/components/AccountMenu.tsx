"use client";

import Link from "next/link";
import { signOut, useSession } from "../lib/auth";

const shorten = (email: string) => (email.length > 22 ? `${email.slice(0, 20)}…` : email);

/** Header entry: „Anmelden“ without session, otherwise „Meine Pläne“, the shortened e-mail and „Abmelden“. */
export default function AccountMenu() {
  const { session, loading } = useSession();
  if (loading) return null;
  if (!session) {
    return (
      <Link href="/anmelden" className="underline-offset-4 hover:underline">
        Anmelden
      </Link>
    );
  }
  return (
    <span className="flex items-baseline gap-3">
      <Link href="/meine-plaene" className="underline-offset-4 hover:underline">
        Meine Pläne
      </Link>
      <span title={session.user.email ?? undefined}>{shorten(session.user.email ?? "Konto")}</span>
      <button type="button" onClick={() => void signOut()} className="underline-offset-4 hover:underline">
        Abmelden
      </button>
    </span>
  );
}
