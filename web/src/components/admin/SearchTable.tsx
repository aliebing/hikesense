"use client";

import { useLocale, useT } from "../../i18n";
import type { SearchPage, SearchSummary } from "../../lib/admin";
import { ms, usd, when } from "../../lib/admin";
import { MISSING, num } from "../../lib/format";

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
  const { locale } = useLocale();
  const t = useT().admin;
  const hits = (s: SearchSummary) => (s.hits === null ? MISSING : s.fallback ? t.fallbackHits(String(s.hits)) : String(s.hits));
  const cols = [t.cols.time, t.cols.user, t.cols.search, t.cols.intent, t.cols.hits, t.cols.tools, t.cols.tokens, t.cols.cost, t.cols.duration, t.cols.error];
  return (
    <div className="overflow-x-auto rounded-xl bg-papier/95 p-4 text-wald-dunkel">
      <h2 className="schrift-feld mb-2 font-serif text-lg">{t.allSearches}</h2>
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-wald-dunkel/20">
            {cols.map((h) => (
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
              <td className="py-1 pr-2 whitespace-nowrap">{when(s.ts, locale)}</td>
              <td className="pr-2">{s.email ?? (s.owner === "unknown" ? t.unknown : s.owner)}</td>
              <td className="max-w-64 truncate pr-2">{s.message ?? t.olderSearch}</td>
              <td className="pr-2">{s.intent ?? "–"}</td>
              <td className="pr-2">{hits(s)}</td>
              <td className="pr-2">{s.tool_calls ?? "–"}</td>
              <td className="pr-2">{num(s.tokens, locale)}</td>
              <td className="pr-2 whitespace-nowrap">{usd(s.cost_usd, locale)}</td>
              <td className="pr-2">{ms(s.duration_ms, locale)}</td>
              <td>{s.error ?? "–"}</td>
            </tr>
          ))}
          <tr>
            <td colSpan={10} className="py-2 text-right font-bold">{t.sum(num(page.sums.count, locale), usd(page.sums.cost_usd, locale), ms(page.sums.avg_duration_ms, locale))}</td>
          </tr>
        </tbody>
      </table>
      {page.items.length < page.total && (
        <button type="button" onClick={onMore} className="mt-2 rounded-lg bg-wald px-3 py-1 text-sm text-papier">
          {t.loadMore}
        </button>
      )}
    </div>
  );
}
