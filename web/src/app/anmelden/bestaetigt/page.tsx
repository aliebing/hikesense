"use client";

import Link from "next/link";
import PageFrame from "../../../components/PageFrame";
import { useT } from "../../../i18n";

/** Target of the confirmation link in the sign-up mail (supabase-js picks up the session). */
export default function Bestaetigt() {
  const t = useT().account.confirmed;
  return (
    <PageFrame>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">{t.title}</h1>
        <p className="max-w-sm rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{t.text}</p>
        <Link href="/" className="rounded-full bg-wald px-4 py-2 text-sm text-papier">
          {t.home}
        </Link>
      </main>
    </PageFrame>
  );
}
