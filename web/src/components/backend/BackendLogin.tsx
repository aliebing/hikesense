"use client";

import { useState } from "react";
import { useLocale, useT } from "../../i18n";
import { adminErrorText, backendLogin } from "../../lib/backend";

const field = "rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70";

/** The admin's own sign-in for /backend (name + password); no app account involved. */
export default function BackendLogin({ onSignedIn }: { onSignedIn: () => void }) {
  const t = useT().admin;
  const { locale } = useLocale();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <main className="flex flex-1 flex-col items-center gap-5 pb-4">
      <h1 className="schrift-feld font-serif text-3xl">{t.login.title}</h1>
      <form
        className="flex w-full max-w-sm flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 ring-1 ring-white/10"
        onSubmit={async (ev) => {
          ev.preventDefault();
          setBusy(true);
          setError(null);
          const r = await backendLogin(name, password);
          setBusy(false);
          if (r.ok) return onSignedIn();
          setError(r.status === 401 ? t.login.failed : adminErrorText(r.status, locale));
        }}
      >
        <input type="text" required autoComplete="username" value={name} onChange={(e) => setName(e.target.value)} placeholder={t.login.name} aria-label={t.login.name} className={field} />
        <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t.login.password} aria-label={t.login.password} className={field} />
        {error && <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
        <button type="submit" disabled={busy} className="rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:opacity-60">
          {t.login.submit}
        </button>
      </form>
    </main>
  );
}
