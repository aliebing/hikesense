import type { SearchPage, SearchSummary } from "../../lib/admin";
import { ms, usd, when } from "../../lib/admin";

const de0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

const hits = (s: SearchSummary) => (s.hits === null ? "–" : s.fallback ? `${s.hits} (Ausweich)` : String(s.hits));

export default function SearchTable({
  page,
  selected,
  onSelect,
  onMore,
}: {
  page: SearchPage;
  selected: string | null;
  onSelect: (id: string) => void;
  onMore: () => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl bg-papier/95 p-4 text-wald-dunkel">
      <h2 className="schrift-feld mb-2 font-serif text-lg">Alle Suchen</h2>
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-wald-dunkel/20">
            {["Zeit", "Benutzer", "Suche", "Intent", "Treffer", "Tools", "Tokens", "Kosten", "Dauer", "Fehler"].map((h) => (
              <th key={h} className="py-1 pr-2">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {page.items.map((s) => (
            <tr
              key={s.request_id}
              onClick={() => onSelect(s.request_id)}
              className={`cursor-pointer border-b border-wald-dunkel/10 hover:bg-wald-dunkel/5 ${selected === s.request_id ? "bg-wald-dunkel/10" : ""}`}
            >
              <td className="py-1 pr-2 whitespace-nowrap">{when(s.ts)}</td>
              <td className="pr-2">{s.email ?? (s.owner === "unknown" ? "Unbekannt" : s.owner)}</td>
              <td className="max-w-64 truncate pr-2">{s.message ?? "(ältere Suche)"}</td>
              <td className="pr-2">{s.intent ?? "–"}</td>
              <td className="pr-2">{hits(s)}</td>
              <td className="pr-2">{s.tool_calls ?? "–"}</td>
              <td className="pr-2">{de0.format(s.tokens)}</td>
              <td className="pr-2 whitespace-nowrap">{usd(s.cost_usd)}</td>
              <td className="pr-2">{ms(s.duration_ms)}</td>
              <td>{s.error ?? "–"}</td>
            </tr>
          ))}
          <tr>
            <td colSpan={10} className="py-2 text-right font-bold">{`Summe: ${de0.format(page.sums.count)} Suchen · ${usd(page.sums.cost_usd)} · Ø ${ms(page.sums.avg_duration_ms)}`}</td>
          </tr>
        </tbody>
      </table>
      {page.items.length < page.total && (
        <button type="button" onClick={onMore} className="mt-2 rounded-lg bg-wald px-3 py-1 text-sm text-papier">
          Mehr laden
        </button>
      )}
    </div>
  );
}
