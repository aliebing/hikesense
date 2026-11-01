import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";

export default function NotFound() {
  return (
    <PageFrame back={{ href: "/", label: "← Zur Startseite" }}>
      <Notice title="Diesen Weg gibt es hier nicht.">
        <p>Vielleicht wurde er (noch) nicht importiert. Zurück zur Startseite.</p>
      </Notice>
    </PageFrame>
  );
}
