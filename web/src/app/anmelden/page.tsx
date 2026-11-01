"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import PageFrame from "../../components/PageFrame";
import { loginEmail, signIn, signUp } from "../../lib/auth";

const field = "rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70";

/** Sign-in and sign-up with e-mail and password; afterwards back to the chat. */
export default function Anmelden() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const go = async (action: typeof signIn) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    const r = await action(loginEmail(email), password);
    setBusy(false);
    if (r.error) setError(r.error);
    else if (r.notice) setNotice(r.notice);
    else router.push("/");
  };

  return (
    <PageFrame back={{ href: "/", label: "← Zum Chat" }}>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">Anmelden</h1>
        <form
          className="flex w-full max-w-sm flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 ring-1 ring-white/10"
          onSubmit={(ev) => {
            ev.preventDefault();
            void go(signIn);
          }}
        >
          <input type="text" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-Mail oder Benutzername" aria-label="E-Mail" className={field} />
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Passwort" aria-label="Passwort" className={field} />
          {error && <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
          {notice && <p role="status" className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{notice}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="flex-1 rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:opacity-60">
              Anmelden
            </button>
            <button
              type="button"
              disabled={busy || !email.trim() || !password}
              onClick={() => void go(signUp)}
              className="flex-1 rounded-full border border-white/40 px-4 py-2 text-sm hover:bg-white/15 disabled:opacity-60"
            >
              Konto anlegen
            </button>
          </div>
        </form>
      </main>
    </PageFrame>
  );
}
