"use client";

import { useLocale, useT, type Locale } from "../i18n";
import { dateIn } from "../lib/format";
import type { CalendarLink, RaceField, VerifiedRace } from "../lib/chat";

const FIELDS: (keyof VerifiedRace & string)[] = ["name", "date", "place", "distances", "registration_url", "registration_deadline", "fee"];

const isWeb = (url: string) => /^https?:\/\//i.test(url);

/** ISO dates (the backend's verified dates) as 18.04.2027 / 18/04/2027; anything else as written. */
function shown(value: string, locale: Locale): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return m ? dateIn(new Date(`${value}T00:00:00Z`), locale, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }) : value;
}

function host(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function Value({ name, field }: { name: string; field: RaceField }) {
  const { locale } = useLocale();
  const t = useT().events;
  const value = field.value;
  if (name === "registration_url") {
    if (!value || !isWeb(value)) return <span className="italic">{t.notStated}</span>;
    return (
      <a href={value} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
        {field.quote || host(value)}
      </a>
    );
  }
  return value ? <span>{shown(value, locale)}</span> : <span className="italic">{t.notStated}</span>;
}

/**
 * Official races found live on the web (rendered inside the chat). Each verified field links to
 * the page it is quoted from (the quote as title); a field the page does not state reads
 * „nicht angegeben“. Without races: running calendars to search yourself. Nothing is stored.
 */
export default function EventCards({ events, fallback, note }: { events: VerifiedRace[]; fallback: CalendarLink[]; note: string }) {
  const t = useT().events;
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
      {events.map((r) => {
        const title = r.name.value ?? t.raceOn(host(r.source_url));
        const linked = isWeb(r.source_url);
        return (
          <article key={`${r.source_url}|${r.day}`} aria-label={title} className="flex flex-col gap-1">
            <h3 className="font-medium">{title}</h3>
            <dl className="flex flex-col gap-0.5 text-xs">
              {FIELDS.map((key) => {
                const label = t.fields[key as keyof typeof t.fields];
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
                            {t.source}
                          </a>
                        ) : (
                          <span>{t.source}</span>
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
        <ul aria-label={t.calendars} className="flex flex-col gap-0.5">
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
