"use client";

import { useT } from "../i18n";
import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  const t = useT().frame;
  return (
    <PageFrame back={{ href: "/", label: t.toHome }}>
      <Notice title={t.errorTitle}>
        <p>{t.errorBody}</p>
        <button type="button" onClick={reset} className="rounded-full bg-wald px-4 py-2 text-papier">
          {t.retry}
        </button>
      </Notice>
    </PageFrame>
  );
}
