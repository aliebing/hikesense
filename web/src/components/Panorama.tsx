import Link from "next/link";

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
      <header className="flex items-baseline justify-between gap-4">
        <Link href="/" className="font-serif text-xl tracking-wide text-papier drop-shadow sm:text-2xl">
          Hike all about
        </Link>
        <nav className="flex items-baseline gap-4 text-sm text-papier/90 drop-shadow">
          {longDistance.length > 0 && (
            <details className="relative">
              <summary className="cursor-pointer list-none underline-offset-4 hover:underline">Fernwege</summary>
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
          {back && (
            <Link href={back.href} className="underline-offset-4 hover:underline">
              {back.label}
            </Link>
          )}
        </nav>
      </header>
      {children}
    </div>
  );
}
