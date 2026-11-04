"use client";

import PageFrame from "../../components/PageFrame";
import { useLocale, useT } from "../../i18n";
import LegalPage from "../../legal/LegalPage";
import { impressum } from "../../legal/impressum";

export default function ImpressumPage() {
  const { locale } = useLocale();
  const t = useT().frame;
  return (
    <PageFrame back={{ href: "/", label: t.toHome }}>
      <LegalPage doc={impressum(locale, "HikeSense")} updatedLabel={t.legalUpdated} className="rounded-2xl bg-wald-flaeche/80 p-5 text-papier ring-1 ring-white/10 sm:p-7" />
    </PageFrame>
  );
}
