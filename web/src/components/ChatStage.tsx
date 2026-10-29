"use client";

import { useState } from "react";
import ChatShell from "./ChatShell";

/** Chat plus the panorama image of the first suggested tour (gradient when it has no/broken cover). */
export default function ChatStage({ intro }: { intro: string }) {
  const [cover, setCover] = useState<string | null>(null);
  const [broken, setBroken] = useState(false);
  return (
    <>
      {cover && (
        <div data-testid="tour-cover" aria-hidden className="wald-verlauf fixed inset-0 -z-10">
          {!broken && (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={cover} src={cover} alt="" className="h-full w-full object-cover" onError={() => setBroken(true)} />
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/5 to-black/65" />
        </div>
      )}
      <ChatShell
        intro={intro}
        onCover={(u) => {
          setBroken(false);
          setCover(u);
        }}
      />
    </>
  );
}
