import Link from "next/link";

/** Page frame of layout A: full-bleed photo stage (rendered by PhotoSwitcher) with content on top. */
export default function Panorama({ children, back = false }: { children: React.ReactNode; back?: boolean }) {
  return (
    <div className="relative isolate flex min-h-dvh flex-col gap-4 overflow-x-clip px-4 pt-4 pb-3 sm:px-6 sm:pt-5">
      <header className="flex items-baseline justify-between gap-4">
        <Link href="/" className="font-serif text-xl tracking-wide text-papier drop-shadow sm:text-2xl">
          Hike all about
        </Link>
        {back && (
          <Link href="/" className="text-sm text-papier/85 underline-offset-4 drop-shadow hover:underline">
            ← Alle Wege
          </Link>
        )}
      </header>
      {children}
    </div>
  );
}
