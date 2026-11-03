"use client";

import Link from "next/link";
import { useT } from "../i18n";
import LanguageFlags from "./LanguageFlags";
import AccountMenu from "./AccountMenu";
import { LogoMark, Wordmark } from "./Logo";

/** Page frame: dark green ground running towards black (dark blue to matt black over winter photos), header with logo, optional „Fernwege“ menu and back link. No photo backdrop. */
export default function PageFrame({
  children,
  back,
  longDistance = [],
  wide = false,
}: {
  children: React.ReactNode;
  back?: { href: string; label: string };
  longDistance?: { id: string; name: string }[];
  wide?: boolean;
}) {
  const t = useT().frame;
  return (
    <div className="relative isolate flex min-h-dvh flex-col bg-[linear-gradient(to_bottom,var(--page-top),var(--page-bottom))] text-papier">
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
      </div>
    </div>
  );
}
