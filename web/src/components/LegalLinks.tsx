"use client";

import Link from "next/link";
import { useT } from "../i18n";

/** Impressum and privacy links; on every page (in the credit line or the frame's footer). */
export default function LegalLinks() {
  const t = useT().frame;
  return (
    <>
      <Link href="/impressum" className="whitespace-nowrap underline-offset-4 hover:underline">
        {t.imprint}
      </Link>
      <Link href="/datenschutz" className="whitespace-nowrap underline-offset-4 hover:underline">
        {t.privacy}
      </Link>
    </>
  );
}
