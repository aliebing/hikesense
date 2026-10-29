"use client";

import { createContext, useContext, useMemo, useState } from "react";
import type { Photo } from "../lib/data";

type CoverState = { cover: Photo | null; setCover: (p: Photo | null) => void };

const Ctx = createContext<CoverState>({ cover: null, setCover: () => {} });

/** Shares the cover of the first suggested tour between the chat and the panorama background. */
export function CoverProvider({ children }: { children: React.ReactNode }) {
  const [cover, setCover] = useState<Photo | null>(null);
  const value = useMemo(() => ({ cover, setCover }), [cover]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useCover = () => useContext(Ctx);
