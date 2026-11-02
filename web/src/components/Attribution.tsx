"use client";

import { useT } from "../i18n";
import type { Photo } from "../lib/data";

/** Values photo.ts stores for a user's own upload; shown through the catalog. */
const OWN_AUTHOR = "Eigenes Foto";
const OWN_LICENSE = "privat";

/** Author, licence (linked) and source page of a photo — shown wherever the photo appears. */
export default function Attribution({ photo, className = "" }: { photo: Photo; className?: string }) {
  const t = useT().tour;
  return (
    <p className={`text-[11px] leading-snug ${className}`}>
      {t.photoBy} {photo.author === OWN_AUTHOR ? t.ownPhoto : photo.author} ·{" "}
      {photo.license_url ? (
        <a href={photo.license_url} target="_blank" rel="noopener noreferrer license" className="underline underline-offset-2">
          {photo.license}
        </a>
      ) : photo.license === OWN_LICENSE ? (
        t.ownLicence
      ) : (
        photo.license
      )}
      {photo.page_url && (
        <>
          {" "}·{" "}
          <a href={photo.page_url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
            Wikimedia Commons
          </a>
        </>
      )}
    </p>
  );
}
