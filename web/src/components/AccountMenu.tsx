"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminGet } from "../lib/admin";
import { signOut, useSession } from "../lib/auth";
import { useResetChat } from "./ChatProvider";

const shorten = (email: string) => (email.length > 22 ? `${email.slice(0, 20)}…` : email);

/** Header entry: „Anmelden“ without session, otherwise „Meine Pläne“, the shortened e-mail and „Abmelden“. */
export default function AccountMenu() {
  const { session, loading } = useSession();
  const resetChat = useResetChat();
  const [isAdmin, setIsAdmin] = useState(false);
  const userKey = session?.user.id ?? session?.user.email ?? (session ? "user" : null);
  useEffect(() => {
    setIsAdmin(false);
    if (!userKey) return;
    let stale = false;
    adminGet("/me")
      .then((r) => { if (!stale) setIsAdmin(r.ok); })
      .catch(() => {});
    return () => { stale = true; };
  }, [userKey]);
  if (loading) return null;
  if (!session) {
    return (
      <Link href="/anmelden" className="whitespace-nowrap underline-offset-4 hover:underline">
        Anmelden
      </Link>
    );
  }
  return (
    <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      {isAdmin && (
        <Link href="/admin" className="whitespace-nowrap underline-offset-4 hover:underline">
          Backend
        </Link>
      )}
      <Link href="/meine-plaene" className="whitespace-nowrap underline-offset-4 hover:underline">
        Meine Pläne
      </Link>
      <span title={session.user.email ?? undefined} className="hidden sm:inline">{shorten(session.user.email ?? "Konto")}</span>
      <button type="button" onClick={() => void signOut().finally(() => resetChat?.())} className="whitespace-nowrap underline-offset-4 hover:underline">
        Abmelden
      </button>
    </span>
  );
}
