import Link from "next/link";
import AccountMenu from "./AccountMenu";

/** Page frame: header with logo, optional „Fernwege“ menu and back link; content on top of the backdrop. */
export default function Panorama({
  children,
  back,
  longDistance = [],
}: {
  children: React.ReactNode;
  back?: { href: string; label: string };
  longDistance?: { id: string; name: string }[];
}) {
  return (
    <div className="relative isolate flex min-h-dvh flex-col gap-4 overflow-x-clip px-4 pt-4 pb-3 sm:px-6 sm:pt-5">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Link href="/" className="whitespace-nowrap font-serif text-xl tracking-wide text-papier drop-shadow sm:text-2xl">
          Hike all about
        </Link>
        <nav className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-papier/90 drop-shadow">
          {longDistance.length > 0 && (
            <details className="relative">
              <summary className="cursor-pointer list-none whitespace-nowrap underline-offset-4 hover:underline">Fernwege</summary>
              <ul className="absolute right-0 z-20 mt-2 grid min-w-48 gap-1 rounded-xl bg-wald-dunkel/95 p-3 shadow-xl">
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
  );
}
