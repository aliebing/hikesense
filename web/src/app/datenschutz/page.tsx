"use client";

import PageFrame from "../../components/PageFrame";
import { useLocale, useT } from "../../i18n";
import LegalPage from "../../legal/LegalPage";
import { datenschutz } from "../../legal/datenschutz";

export default function DatenschutzPage() {
  const { locale } = useLocale();
  const t = useT().frame;
  return (
    <PageFrame back={{ href: "/", label: t.toHome }}>
      <LegalPage doc={datenschutz(locale)} updatedLabel={t.legalUpdated} className="rounded-2xl bg-wald-flaeche/80 p-5 text-papier ring-1 ring-white/10 sm:p-7" />
    </PageFrame>
  );
}
