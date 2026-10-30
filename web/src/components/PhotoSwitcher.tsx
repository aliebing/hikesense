"use client";

import { useCallback, useEffect, useState } from "react";
import { getBrowserSupabase, useSession } from "../lib/auth";
import type { Photo } from "../lib/data";
import { deleteOwnPhoto, listOwnPhotos } from "../lib/photo";
import Attribution from "./Attribution";
import PhotoUpload from "./PhotoUpload";

/**
 * Full-bleed background photo with prev/next controls and the attribution of
 * the current photo. The background layer is fixed behind the page; the
 * controls render where the component is placed. Without photos (or when an
 * image fails to load) a forest-green gradient is shown instead.
 * With `trailId`, a signed-in user additionally gets their own private photos of
 * this trail (loaded in the browser, never part of the server-rendered data),
 * can add one and delete them.
 */
export default function PhotoSwitcher({ photos: publicPhotos, trailId }: { photos: Photo[]; trailId?: string }) {
  const { session } = useSession();
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

  if (photos.length === 0 && !(trailId && userId)) {
    return <div data-testid="panorama-fallback" aria-hidden className="wald-verlauf fixed inset-0 -z-10" />;
  }

  const current = photos.length ? photos[index % photos.length] : null;
  const go = (step: number) => setIndex((i) => (i + step + photos.length) % photos.length);

  async function remove(ownPhoto: { id: number; path: string }) {
    setDeleteError(null);
    try {
      await deleteOwnPhoto(getBrowserSupabase(), ownPhoto);
      setIndex(0);
      await loadOwn();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Löschen hat nicht geklappt");
    }
  }

  async function uploaded() {
    const list = await loadOwn();
    // show the new photo: it is the last own one
    if (list.length) setIndex(publicPhotos.length + list.length - 1);
  }

  return (
    <>
      <div aria-hidden className="wald-verlauf fixed inset-0 -z-10">
        {current && !broken.has(current.url) && (
          // Plain <img>: the stored Commons URL (or the signed URL of an own photo) is loaded by the browser, never proxied by the server.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={current.url}
            src={current.url}
            alt=""
            className="h-full w-full object-cover"
            onError={() => setBroken((b) => new Set(b).add(current.url))}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/5 to-black/65" />
      </div>
      <div className="flex max-w-full flex-wrap items-center gap-2 rounded-3xl bg-black/35 py-1 pr-3 pl-1 text-papier backdrop-blur-md">
        {photos.length > 1 && (
          <>
            <button
              type="button"
              aria-label="Vorheriges Bild"
              onClick={() => go(-1)}
              className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier"
            >
              ‹
            </button>
            <span className="shrink-0 text-xs tabular-nums opacity-80">
              {(index % photos.length) + 1} / {photos.length}
            </span>
            <button
              type="button"
              aria-label="Nächstes Bild"
              onClick={() => go(1)}
              className="grid size-8 shrink-0 place-items-center rounded-full hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier"
            >
              ›
            </button>
          </>
        )}
        {current && <Attribution photo={current} className="min-w-0 pl-2" />}
        {current?.own && (
          <button
            type="button"
            onClick={() => void remove(current.own!)}
            className="rounded-full px-3 py-1 text-xs hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-papier"
          >
            Foto löschen
          </button>
        )}
        {trailId && <PhotoUpload trailId={trailId} onUploaded={() => void uploaded()} />}
        {deleteError && (
          <span role="alert" className="text-xs text-red-200">
            {deleteError}
          </span>
        )}
      </div>
    </>
  );
}
