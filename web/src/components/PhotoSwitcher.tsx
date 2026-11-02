"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "../i18n";
import type { PhotoErrorCode } from "../lib/photo";
import { getBrowserSupabase, useSession } from "../lib/auth";
import type { Photo } from "../lib/data";
import { deleteOwnPhoto, listOwnPhotos } from "../lib/photo";
import Attribution from "./Attribution";
import PhotoUpload from "./PhotoUpload";

const MAX_THUMBS = 8;

/**
 * A bounded picture (never a page backdrop, never text on top) with thumbnails, prev/next
 * controls and the attribution of the current photo below it. Without photos (or when an
 * image fails to load) a forest-green gradient area of the same size is shown instead.
 * With `trailId`, a signed-in user additionally gets their own private photos of
 * this trail (loaded in the browser, never part of the server-rendered data),
 * can add one and delete them.
 */
export default function PhotoSwitcher({
  photos: publicPhotos,
  trailId,
  className = "",
  variant = "framed",
}: {
  photos: Photo[];
  trailId?: string;
  className?: string;
  /** framed: a bounded picture with thumbnails; backdrop: full-screen photo behind the page (home start), controls where placed */
  variant?: "framed" | "backdrop";
}) {
  const { session } = useSession();
  const t = useT().tour;
  const userId = session?.user.id;
  const [own, setOwn] = useState<Photo[]>([]);
  const [index, setIndex] = useState(0);
  const [broken, setBroken] = useState<Set<string>>(() => new Set());
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadOwn = useCallback(async (): Promise<Photo[]> => {
    if (!trailId || !userId) return [];
    const list = await listOwnPhotos(getBrowserSupabase(), trailId);
    setOwn(list);
    return list;
  }, [trailId, userId]);

  useEffect(() => {
    if (!userId) setOwn([]); // signed out: own photos leave the page
    void loadOwn();
  }, [userId, loadOwn]);

  const photos = userId ? [...publicPhotos, ...own] : publicPhotos;

  const current = photos.length ? photos[index % photos.length] : null;
  const go = (step: number) => setIndex((i) => (i + step + photos.length) % photos.length);

  async function remove(ownPhoto: { id: number; path: string }) {
    setDeleteError(null);
    try {
      await deleteOwnPhoto(getBrowserSupabase(), ownPhoto);
      setIndex(0);
      await loadOwn();
    } catch (e) {
      const code = (e as { code?: PhotoErrorCode } | null)?.code;
      setDeleteError(code && code in t.photoErrors ? t.photoErrors[code] : t.photoDeleteFailed);
    }
  }

  async function uploaded() {
    const list = await loadOwn();
    // show the new photo: it is the last own one
    if (list.length) setIndex(publicPhotos.length + list.length - 1);
  }

  const shown = current && !broken.has(current.url) ? current : null;
  const at = photos.length ? index % photos.length : 0;

  if (variant === "backdrop") {
    return (
      <>
        <div aria-hidden className="wald-verlauf fixed inset-0 -z-10">
          {shown && (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={shown.url} src={shown.url} alt="" className="h-full w-full object-cover" onError={() => setBroken((b) => new Set(b).add(shown.url))} />
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/5 to-black/65" />
        </div>
        <div className={`flex max-w-full flex-wrap items-center gap-2 rounded-3xl bg-wald-dunkel/88 py-1 pr-3 pl-1 text-papier backdrop-blur-md ${className}`}>
          {photos.length > 1 && (
            <>
              <button type="button" aria-label={t.photoPrev} onClick={() => go(-1)} className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier">
                ‹
              </button>
              <span className="shrink-0 text-xs tabular-nums opacity-80">
                {at + 1} / {photos.length}
              </span>
              <button type="button" aria-label={t.photoNext} onClick={() => go(1)} className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier">
                ›
              </button>
            </>
          )}
          {current && <Attribution photo={current} className="min-w-0 pl-2" />}
        </div>
      </>
    );
  }

  return (
    <figure className={`flex min-w-0 flex-col gap-2 ${className}`}>
      <div className="wald-verlauf aspect-[4/3] w-full overflow-hidden rounded-2xl" data-testid={shown ? undefined : "photo-fallback"}>
        {shown && (
          // Plain <img>: the stored Commons URL (or the signed URL of an own photo) is loaded by the browser, never proxied by the server.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={shown.url}
            data-main
            src={shown.url}
            alt=""
            className="h-full w-full object-cover"
            onError={() => setBroken((b) => new Set(b).add(shown.url))}
          />
        )}
      </div>
      {photos.length > 1 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={t.pictures}>
          {photos.slice(0, MAX_THUMBS).map((ph, i) => (
            <li key={ph.url}>
              <button
                type="button"
                aria-label={t.picture(i + 1)}
                aria-current={i === at ? "true" : undefined}
                onClick={() => setIndex(i)}
                className={`block size-12 overflow-hidden rounded-md ring-2 focus-visible:outline-2 focus-visible:outline-papier ${i === at ? "ring-amber-400" : "ring-transparent opacity-80 hover:opacity-100"}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={ph.thumb_url} alt="" loading="lazy" className="h-full w-full object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <figcaption className="flex max-w-full flex-wrap items-center gap-2 text-xs">
        {photos.length > 1 && (
          <>
            <button
              type="button"
              aria-label={t.photoPrev}
              onClick={() => go(-1)}
              className="grid size-7 shrink-0 place-items-center rounded-full hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-current"
            >
              ‹
            </button>
            <span className="shrink-0 tabular-nums opacity-80">
              {at + 1} / {photos.length}
            </span>
            <button
              type="button"
              aria-label={t.photoNext}
              onClick={() => go(1)}
              className="grid size-7 shrink-0 place-items-center rounded-full hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-current"
            >
              ›
            </button>
          </>
        )}
        {current && <Attribution photo={current} className="min-w-0" />}
        {current?.own && (
          <button
            type="button"
            onClick={() => void remove(current.own!)}
            className="rounded-full px-3 py-1 hover:bg-current/10 focus-visible:outline-2 focus-visible:outline-current"
          >
            {t.photoDelete}
          </button>
        )}
        {trailId && <PhotoUpload trailId={trailId} onUploaded={() => void uploaded()} />}
        {deleteError && (
          <span role="alert" className="rounded bg-red-100 px-2 text-red-900">
            {deleteError}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
