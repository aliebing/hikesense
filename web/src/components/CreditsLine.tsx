"use client";

import Link from "next/link";
import { useT } from "../i18n";

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
    <footer className="schrift-feld text-xs text-papier sm:text-sm">
      <p>
        {lead}
        {lead && " · "}
        {osm && (
          <>
            <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
              {t.osm}
            </a>
            {" · "}
          </>
        )}
        {t.elevation}
        {" · "}
        <Link href="/quellen" className="underline underline-offset-2">
          {t.link}
        </Link>
      </p>
      {children}
    </footer>
  );
}
