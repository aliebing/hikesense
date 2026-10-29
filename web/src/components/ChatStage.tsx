"use client";

import ChatShell from "./ChatShell";
import { useCover } from "./CoverContext";

/** Chat that sets the panorama image (PhotoSwitcher shows it) to the first suggested tour's cover. */
export default function ChatStage({ intro }: { intro: string }) {
  const { setCover } = useCover();
  return <ChatShell intro={intro} onCover={setCover} />;
}
