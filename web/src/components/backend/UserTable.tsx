"use client";

import { useEffect, useState } from "react";
import { useLocale, useT } from "../../i18n";
import { MISSING } from "../../lib/format";
import { adminErrorText, backendPost, when, type BackendUser } from "../../lib/backend";

const btn = "rounded-full border border-wald-dunkel/40 px-3 py-0.5 text-xs hover:bg-wald-dunkel/10 disabled:opacity-60";

/** Account list with block/unblock; each action asks inside its row first (no browser dialog). */
export default function UserTable({ users }: { users: BackendUser[] }) {
  const t = useT().admin;
  const { locale } = useLocale();
  const [rows, setRows] = useState(users);
  const [asking, setAsking] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setRows(users), [users]);

  const act = async (u: BackendUser) => {
    const block = u.status !== "gesperrt";
    setBusy(u.user_id);
    setError(null);
    const r = await backendPost<{ status: BackendUser["status"] }>(`/users/${encodeURIComponent(u.user_id)}/${block ? "block" : "unblock"}`);
    setBusy(null);
    setAsking(null);
    if (!r.ok) return setError(adminErrorText(r.status, locale));
    setRows((all) => all.map((x) => (x.user_id === u.user_id ? { ...x, status: r.data.status } : x)));
  };

  const accounts = rows.filter((u) => u.user_id !== "unknown");
  return (
    <div className="overflow-x-auto">
      {error && <p role="alert" className="mb-2 rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{error}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-wald-dunkel/20">
            {[t.userCols.email, t.userCols.status, t.userCols.created, t.userCols.lastSignIn, t.userCols.searches, t.userCols.action].map((h) => (
              <th key={h} className="px-2 py-1 font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {accounts.map((u) => {
            const guest = u.user_id === "guest";
            const block = u.status !== "gesperrt";
            return (
              <tr key={u.user_id} className="border-b border-wald-dunkel/10">
                <td className="px-2 py-1">{guest ? t.guests : (u.email ?? u.user_id)}</td>
                <td className={`px-2 py-1 ${u.status === "gesperrt" ? "font-semibold text-red-800" : ""}`}>{u.status ? t.accountStatus[u.status] : MISSING}</td>
                <td className="px-2 py-1">{u.created_at ? when(u.created_at, locale) : MISSING}</td>
                <td className="px-2 py-1">{u.last_sign_in_at ? when(u.last_sign_in_at, locale) : MISSING}</td>
                <td className="px-2 py-1">{u.searches}</td>
                <td className="px-2 py-1">
                  {guest ? null : asking === u.user_id ? (
                    <span className="flex flex-wrap items-center gap-2">
                      {block ? t.confirmBlock : t.confirmUnblock}
                      <button type="button" className={btn} disabled={busy === u.user_id} onClick={() => void act(u)}>{t.yes}</button>
                      <button type="button" className={btn} onClick={() => setAsking(null)}>{t.cancel}</button>
                    </span>
                  ) : (
                    <button type="button" className={btn} onClick={() => setAsking(u.user_id)}>{block ? t.block : t.unblock}</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
