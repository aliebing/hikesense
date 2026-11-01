"use client";

import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <PageFrame back={{ href: "/", label: "← Zur Startseite" }}>
      <Notice title="Etwas ist schiefgelaufen.">
        <p>Die Seite konnte nicht angezeigt werden.</p>
        <button type="button" onClick={reset} className="rounded-full bg-wald px-4 py-2 text-papier">
          Erneut versuchen
        </button>
      </Notice>
    </PageFrame>
  );
}
