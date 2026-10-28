import Notice from "../components/Notice";
import Panorama from "../components/Panorama";
import PhotoSwitcher from "../components/PhotoSwitcher";

export default function NotFound() {
  return (
    <Panorama back>
      <PhotoSwitcher photos={[]} />
      <Notice title="Diesen Weg gibt es hier nicht.">
        <p>Vielleicht wurde er (noch) nicht importiert. Zurück zur Übersicht über „Alle Wege“.</p>
      </Notice>
    </Panorama>
  );
}
