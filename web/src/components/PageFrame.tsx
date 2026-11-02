import Link from "next/link";
import AccountMenu from "./AccountMenu";

/** Page frame: dark green ground very dark green running towards black, header with logo, optional „Fernwege“ menu and back link. No photo backdrop. */
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
  return (
    <div className="relative isolate flex min-h-dvh flex-col bg-gradient-to-b from-[#0e2214] to-[#040a05] text-papier">
      <div className={`mx-auto flex w-full flex-1 flex-col gap-5 px-4 pt-4 pb-4 sm:px-6 sm:pt-5 ${wide ? "max-w-7xl" : "max-w-6xl"}`}>
        <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <Link href="/" className="schrift-feld whitespace-nowrap font-serif text-xl tracking-wide text-papier sm:text-2xl">
            Hike all about
          </Link>
          <nav className="schrift-feld flex empty:hidden flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-papier">
            {longDistance.length > 0 && (
              <details className="relative">
                <summary className="cursor-pointer list-none whitespace-nowrap underline-offset-4 hover:underline">Fernwege</summary>
                <ul className="absolute right-0 z-20 mt-2 grid min-w-48 gap-1 rounded-xl bg-wald-flaeche p-3 shadow-xl ring-1 ring-white/10">
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
