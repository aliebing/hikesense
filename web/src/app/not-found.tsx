"use client";

import { useT } from "../i18n";
import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";

export default function NotFound() {
  const t = useT().frame;
  return (
    <PageFrame back={{ href: "/", label: t.toHome }}>
      <Notice title={t.notFoundTitle}>
        <p>{t.notFoundBody}</p>
      </Notice>
    </PageFrame>
  );
}
