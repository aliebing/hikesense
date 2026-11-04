"use client";

import Link from "next/link";
import { useT } from "../i18n";
import LegalLinks from "./LegalLinks";

/** The short, readable credit line under a page: OSM and elevation (both must be named),
 * then a link to all sources and licences. `lead` goes first (e.g. a trail's own sources),
 * `children` below (e.g. the background photo's credit). */
export default function CreditsLine({
  lead,
  osm = true,
  children,
}: {
  lead?: React.ReactNode;
  /** false when `lead` already credits OpenStreetMap */
  osm?: boolean;
  children?: React.ReactNode;
}) {
  const t = useT().credits;
  return (
    // as wide as the header row and aligned with it, as high as its navigation; quiet grey 12 px text
    <footer data-credits className="schrift-feld flex min-h-10 w-full flex-col justify-center gap-1 text-xs font-normal text-papier/70">
      <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        {lead && <span>{lead}</span>}
        {osm && (
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" className="whitespace-nowrap underline-offset-4 hover:underline">
            {t.osm}
          </a>
        )}
        <span className="whitespace-nowrap">{t.elevation}</span>
        <Link href="/quellen" className="whitespace-nowrap underline-offset-4 hover:underline">
          {t.link}
        </Link>
        <LegalLinks />
      </p>
      {children}
    </footer>
  );
}
