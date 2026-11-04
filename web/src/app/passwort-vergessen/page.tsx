"use client";

import { useState } from "react";
import PageFrame from "../../components/PageFrame";
import { useLocale, useT } from "../../i18n";
import { requestPasswordReset } from "../../lib/auth";

const field = "rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70";

/** Asks for the reset link; the answer never tells whether the address has an account. */
export default function PasswortVergessen() {
  const t = useT().account.forgot;
  const { locale } = useLocale();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  return (
    <PageFrame back={{ href: "/anmelden", label: t.back }}>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">{t.title}</h1>
        <form
          className="flex w-full max-w-sm flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 ring-1 ring-white/10"
          onSubmit={async (ev) => {
            ev.preventDefault();
            setBusy(true);
            setError(null);
            setNotice(null);
            const r = await requestPasswordReset(email.trim(), locale);
            setBusy(false);
            setError(r.error);
            setNotice(r.notice ?? null);
          }}
        >
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t.email} aria-label={t.email} className={field} />
          {error && <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
          {notice && <p role="status" className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{notice}</p>}
          <button type="submit" disabled={busy} className="rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:opacity-60">
            {t.submit}
          </button>
        </form>
      </main>
    </PageFrame>
  );
}
