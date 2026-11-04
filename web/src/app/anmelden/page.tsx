"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale, useT } from "../../i18n";
import PageFrame from "../../components/PageFrame";
import { loginEmail, safeNext, signIn, signUp } from "../../lib/auth";

const field = "rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70";

/** Sign-in and sign-up with e-mail and password; afterwards back to the chat. */
export default function Anmelden() {
  const router = useRouter();
  const t = useT().account.login;
  const { locale } = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // read after mounting (no useSearchParams: the page stays static); `next` is only a local path
  const [query, setQuery] = useState<{ next: string; blocked: boolean; save: boolean }>({ next: "/", blocked: false, save: false });
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setQuery({ next: safeNext(p.get("next")), blocked: p.get("gesperrt") === "1", save: p.has("next") });
  }, []);

  const go = async (action: typeof signIn) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    const r = await action(loginEmail(email), password, locale);
    setBusy(false);
    if (r.error) setError(r.error);
    else if (r.notice) setNotice(r.notice);
    else router.push(query.next);
  };

  return (
    <PageFrame back={{ href: "/", label: t.back }}>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">{t.title}</h1>
        {query.blocked && <p role="status" className="max-w-sm rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{t.blocked}</p>}
        {!query.blocked && query.save && <p className="max-w-sm rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{t.saveHint}</p>}
        <form
          className="flex w-full max-w-sm flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 ring-1 ring-white/10"
          onSubmit={(ev) => {
            ev.preventDefault();
            void go(signIn);
          }}
        >
          <input type="text" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t.identifier} aria-label={t.email} className={field} />
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t.password} aria-label={t.password} className={field} />
          {error && <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
          {notice && <p role="status" className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{notice}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="flex-1 rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:opacity-60">
              {t.submit}
            </button>
            <button
              type="button"
              disabled={busy || !email.trim() || !password}
              onClick={() => void go(signUp)}
              className="flex-1 rounded-full border border-white/40 px-4 py-2 text-sm hover:bg-white/15 disabled:opacity-60"
            >
              {t.create}
            </button>
          </div>
        </form>
      </main>
    </PageFrame>
  );
}
