"use client";

import Link from "next/link";
import { useT } from "../i18n";
import LanguageFlags from "./LanguageFlags";
import LegalLinks from "./LegalLinks";
import AccountMenu from "./AccountMenu";
import { LogoMark, Wordmark } from "./Logo";

/** Page frame: near-black ground (#070808), header with logo, optional „Fernwege“ menu and back link. No photo backdrop.
 * A small footer links Impressum and privacy notice; pages with their own CreditsLine (which
 * carries those links) pass `legalFooter={false}`. */
export default function PageFrame({
  children,
  back,
  longDistance = [],
  wide = false,
  legalFooter = true,
}: {
  children: React.ReactNode;
  back?: { href: string; label: string };
  longDistance?: { id: string; name: string }[];
  wide?: boolean;
  legalFooter?: boolean;
}) {
  const t = useT().frame;
  return (
    <div className="relative isolate flex min-h-dvh flex-col bg-[var(--page-ground)] text-papier">
      <div className={`mx-auto flex w-full flex-1 flex-col gap-5 px-4 pt-4 pb-4 sm:px-6 sm:pt-5 ${wide ? "max-w-7xl" : "max-w-6xl"}`}>
        <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          {/* data-frame-logo: hidden on the start view, where the big logo stands in the middle */}
          <Link href="/" data-frame-logo className="schrift-feld flex items-center gap-2 whitespace-nowrap py-1.5 text-xl text-papier sm:text-2xl">
            <LogoMark trail={false} className="h-7 w-auto sm:h-8" />
            <Wordmark />
          </Link>
          <nav className="schrift-feld flex empty:hidden flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-papier">
            {longDistance.length > 0 && (
              <details className="relative">
                <summary className="cursor-pointer list-none whitespace-nowrap underline-offset-4 hover:underline">{t.longDistance}</summary>
                <ul className="absolute right-0 z-20 mt-2 grid min-w-48 gap-1 rounded-xl bg-panel p-3 shadow-xl ring-1 ring-white/10">
                  {longDistance.map((t) => (
                    <li key={t.id}>
                      <Link href={`/t/${t.id}`} className="underline-offset-4 hover:underline">
                        {t.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <LanguageFlags />
            <AccountMenu />
            {back && (
              <Link href={back.href} className="whitespace-nowrap underline-offset-4 hover:underline">
                {back.label}
              </Link>
            )}
          </nav>
        </header>
        {children}
        {legalFooter && (
          <footer data-legal className="schrift-feld mt-auto flex min-h-10 flex-wrap items-center gap-x-4 text-xs text-papier/70">
            <LegalLinks />
          </footer>
        )}
      </div>
    </div>
  );
}
