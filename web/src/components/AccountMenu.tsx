"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useLocale, useT } from "../i18n";
import { checkBlocked, onBlocked, signOut, useSession } from "../lib/auth";
import { useResetChat } from "./ChatProvider";

const shorten = (email: string) => (email.length > 22 ? `${email.slice(0, 20)}…` : email);

/** Header entry: „Anmelden“ without session, otherwise „Meine Pläne“, the shortened e-mail and „Abmelden“. */
export default function AccountMenu() {
  const { session, loading } = useSession();
  const resetChat = useResetChat();
  const { locale } = useLocale();
  const t = useT().account;
  const router = useRouter();
  const userId = session?.user?.id ?? session?.user?.email ?? null;
  // a blocked account (checked when the session appears, or reported by the chat / a failed
  // save) is signed out at once; the chat starts over like after Abmelden
  useEffect(() => {
    if (!userId) return;
    let done = false;
    const out = () => {
      if (done) return;
      done = true;
      void signOut(locale).finally(() => {
        resetChat?.();
        router.push("/anmelden?gesperrt=1");
      });
    };
    const off = onBlocked(out);
    void checkBlocked().then((b) => b && out());
    return off;
  }, [userId, locale, resetChat, router]);
  if (loading) return null;
  if (!session) {
    return (
      <Link href="/anmelden" className="whitespace-nowrap underline-offset-4 hover:underline">
        {t.signIn}
      </Link>
    );
  }
  return (
    <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <Link href="/meine-plaene" className="whitespace-nowrap underline-offset-4 hover:underline">
        {t.myPlans}
      </Link>
      <span title={session.user.email ?? undefined} className="hidden sm:inline">{shorten(session.user.email ?? t.account)}</span>
      <button type="button" onClick={() => void signOut(locale).finally(() => resetChat?.())} className="whitespace-nowrap underline-offset-4 hover:underline">
        {t.signOut}
      </button>
    </span>
  );
}
