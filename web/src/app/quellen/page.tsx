"use client";

import PageFrame from "../../components/PageFrame";
import { useT } from "../../i18n";

const ODBL = "https://opendatacommons.org/licenses/odbl/";
const CC_BY = "https://creativecommons.org/licenses/by/4.0/";
const CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/";

type Row = { what: string; source: React.ReactNode; licence: React.ReactNode };

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
      {children}
    </a>
  );
}

/** All data sources and their licences; the pages link here from their short credit line. */
export default function Sources() {
  const all = useT();
  const t = all.credits;
  const rows: Row[] = [
    { what: t.rows.osm, source: <Ext href="https://www.openstreetmap.org/copyright">{t.osm}</Ext>, licence: <Ext href={ODBL}>ODbL</Ext> },
    { what: t.rows.elevation, source: t.elevationSource, licence: "Copernicus" },
    { what: t.rows.photos, source: <Ext href="https://commons.wikimedia.org/">{t.photosSource}</Ext>, licence: t.photosLicence },
    { what: t.rows.map, source: <Ext href="https://basemap.de/">basemap.de © BKG</Ext>, licence: <Ext href={CC_BY}>CC BY 4.0</Ext> },
    { what: t.rows.weather, source: <Ext href="https://open-meteo.com/">Open-Meteo.com</Ext>, licence: <Ext href={CC_BY}>CC BY 4.0</Ext> },
    { what: t.rows.knowledge, source: "Wikipedia, Wikivoyage", licence: <Ext href={CC_BY_SA}>CC BY-SA 4.0</Ext> },
    { what: t.rows.stages, source: t.stagesSource, licence: t.stagesLicence },
    { what: t.rows.time, source: t.timeSource, licence: "–" },
    { what: t.rows.groups, source: t.groupsSource, licence: t.groupsLicence },
  ];
  return (
    <PageFrame back={{ href: "/", label: all.frame.toHome }}>
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 rounded-2xl bg-wald-flaeche/80 p-5 text-papier ring-1 ring-white/10 sm:p-7">
        <h1 className="font-serif text-2xl sm:text-3xl">{t.title}</h1>
        <p className="text-sm leading-relaxed text-papier/90 sm:text-base">{t.intro}</p>
        <dl className="grid gap-3 text-sm sm:text-base">
          {rows.map((r) => (
            <div key={r.what} className="grid gap-0.5 border-t border-white/10 pt-3 sm:grid-cols-[14rem_1fr] sm:gap-4">
              <dt className="font-medium text-sense">{r.what}</dt>
              <dd>
                {r.source}
                <span className="text-papier/75"> · {t.licence}: {r.licence}</span>
              </dd>
            </div>
          ))}
        </dl>
      </main>
    </PageFrame>
  );
}
