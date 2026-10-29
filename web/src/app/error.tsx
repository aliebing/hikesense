"use client";

import Notice from "../components/Notice";
import Panorama from "../components/Panorama";
import PhotoSwitcher from "../components/PhotoSwitcher";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <Panorama back>
      <PhotoSwitcher photos={[]} />
      <Notice title="Etwas ist schiefgelaufen.">
        <p>Die Seite konnte nicht angezeigt werden.</p>
        <button type="button" onClick={reset} className="rounded-full bg-wald px-4 py-2 text-papier">
          Erneut versuchen
        </button>
      </Notice>
    </Panorama>
  );
}
