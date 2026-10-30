import type { CalendarLink, RaceField, VerifiedRace } from "../lib/chat";

const FIELDS: [keyof VerifiedRace & string, string][] = [
  ["name", "Name"],
  ["date", "Datum"],
  ["place", "Ort"],
  ["distances", "Distanzen"],
  ["registration_url", "Anmeldung"],
  ["registration_deadline", "Anmeldeschluss"],
  ["fee", "Startgebühr"],
];

const isWeb = (url: string) => /^https?:\/\//i.test(url);

/** ISO dates (the backend's verified dates) as 18.04.2027; anything else as written. */
function shown(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : value;
}

function host(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function Value({ name, field }: { name: string; field: RaceField }) {
  const value = field.value;
  if (name === "registration_url") {
    if (!value || !isWeb(value)) return <span className="italic">nicht angegeben</span>;
    return (
      <a href={value} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
        {field.quote || host(value)}
      </a>
    );
  }
  return value ? <span>{shown(value)}</span> : <span className="italic">nicht angegeben</span>;
}

/**
 * Official races found live on the web (rendered inside the chat). Each verified field links to
 * the page it is quoted from (the quote as title); a field the page does not state reads
 * „nicht angegeben“. Without races: running calendars to search yourself. Nothing is stored.
 */
export default function EventCards({ events, fallback, note }: { events: VerifiedRace[]; fallback: CalendarLink[]; note: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
      {events.map((r) => {
        const title = r.name.value ?? `Lauf auf ${host(r.source_url)}`;
        const linked = isWeb(r.source_url);
        return (
          <article key={`${r.source_url}|${r.day}`} aria-label={title} className="flex flex-col gap-1">
            <h3 className="font-medium">{title}</h3>
            <dl className="flex flex-col gap-0.5 text-xs">
              {FIELDS.map(([key, label]) => {
                const field = r[key] as RaceField;
                const verified = key === "registration_url" ? !!field.value && isWeb(field.value) : !!field.value;
                return (
                  <div key={key} className="flex flex-wrap gap-x-2">
                    <dt className="font-medium">{label}</dt>
                    <dd className="flex flex-wrap gap-x-2">
                      <Value name={key} field={field} />
                      {verified &&
                        (linked ? (
                          <a
                            href={r.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={field.quote ? `„${field.quote}“` : undefined}
                            className="text-wald underline underline-offset-2"
                          >
                            Quelle
                          </a>
                        ) : (
                          <span>Quelle</span>
                        ))}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </article>
        );
      })}
      {fallback.length > 0 && (
        <ul aria-label="Laufkalender" className="flex flex-col gap-0.5">
          {fallback
            .filter((c) => isWeb(c.url))
            .map((c) => (
              <li key={c.url}>
                <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                  {c.name}
                </a>
              </li>
            ))}
        </ul>
      )}
      <p className="text-xs">{note}</p>
    </div>
  );
}
