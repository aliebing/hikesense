"use client";

import { useEffect, useState } from "react";
import type { Photo } from "../lib/data";
import Attribution from "./Attribution";

/**
 * Fixed landscape backdrop behind the page: photos cross-fade slowly while zooming (Ken Burns),
 * with drifting fog on top. Photos that fail to load are skipped; without photos (or with
 * prefers-reduced-motion) it shows the forest gradient or one still photo.
 */
export default function HeroBackdrop({
  photos,
  intervalMs = 9000,
}: {
  photos: Photo[];
  intervalMs?: number;
}) {
  const [index, setIndex] = useState(0);
  const [prev, setPrev] = useState<string | null>(null);
  const [broken, setBroken] = useState<string[]>([]);
  const [reduced, setReduced] = useState(false);
  const [narrow, setNarrow] = useState(false);

  const usable = photos.filter((p) => !broken.includes(p.url));
  const current = usable.length ? usable[index % usable.length] : null;

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // slower change on phones (spec §5)
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(max-width: 639px)");
    setNarrow(mq.matches);
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const interval = narrow ? intervalMs * 2 : intervalMs;

  const count = usable.length;
  useEffect(() => {
    if (reduced || count < 2) return;
    const timer = setInterval(() => {
      setIndex((i) => {
        setPrev(usable[i % count]?.url ?? null);
        return (i + 1) % count;
      });
    }, interval);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduced, count, interval]);

  const layers = [
    prev && !reduced ? usable.find((p) => p.url === prev) : null,
    current,
  ].filter(
    (p, i, a): p is Photo => !!p && a.findIndex((q) => q?.url === p.url) === i,
  );

  return (
    <>
      <div
        className="fixed inset-0 -z-10 overflow-hidden wald-verlauf"
        data-motion={reduced ? "still" : "slow"}
        aria-hidden={!current}
      >
        {layers.map((p) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={p.url}
            src={p.url}
            alt=""
            onError={() => setBroken((b) => [...b, p.url])}
            className={`absolute inset-0 h-full w-full object-cover ${reduced ? "" : "hike-kenburns"} ${
              p === current && layers.length > 1 ? "hike-fade-in" : ""
            }`}
            style={
              reduced
                ? undefined
                : { animationDuration: `${interval + 3000}ms, 1500ms` }
            }
          />
        ))}
        <div className="absolute inset-0 bg-black/25" />
        <div className="hike-fog pointer-events-none absolute inset-0 hidden sm:block" />
      </div>
      {/* outside the -z-10 layer, or the licence links lie behind the page and cannot be clicked */}
      {current && (
        <Attribution
          photo={current}
          className="fixed bottom-2 right-3 z-20 max-w-[60vw] text-right text-papier/80"
        />
      )}
    </>
  );
}
