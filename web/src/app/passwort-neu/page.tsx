"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import PageFrame from "../../components/PageFrame";
import { useLocale, useT } from "../../i18n";
import { setNewPassword, useSession } from "../../lib/auth";

const field = "rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70";

/** Target of the reset link: the link opens a recovery session, here the new password is set. */
export default function PasswortNeu() {
  const t = useT().account.newPassword;
  const { locale } = useLocale();
  const router = useRouter();
  const { session, loading } = useSession();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <PageFrame>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">{t.title}</h1>
        {loading ? null : !session ? (
          <p className="max-w-sm rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
            {t.expired}
            <Link href="/passwort-vergessen" className="underline">
              {t.requestNew}
            </Link>
          </p>
        ) : (
          <form
            className="flex w-full max-w-sm flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 ring-1 ring-white/10"
            onSubmit={async (ev) => {
              ev.preventDefault();
              if (password !== repeat) return setError(t.mismatch);
              setBusy(true);
              setError(null);
              const r = await setNewPassword(password, locale);
              setBusy(false);
              if (r.error) return setError(r.error);
              router.push("/");
            }}
          >
            <input type="password" required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t.password} aria-label={t.password} className={field} />
            <input type="password" required autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} placeholder={t.repeat} aria-label={t.repeat} className={field} />
            {error && <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
            <button type="submit" disabled={busy} className="rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:opacity-60">
              {t.submit}
            </button>
          </form>
        )}
      </main>
    </PageFrame>
  );
}
