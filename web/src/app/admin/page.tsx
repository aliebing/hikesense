"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import PageFrame from "../../components/PageFrame";
import SearchDetail from "../../components/admin/SearchDetail";
import SearchTable from "../../components/admin/SearchTable";
import { useLocale, useT } from "../../i18n";
import { adminErrorText, adminGet, ms, usd, when, type AdminUser, type SearchDetail as Detail, type SearchPage } from "../../lib/admin";
import { useSession } from "../../lib/auth";

const LIMIT = 50;
const ALL = "all";
const card = "rounded-xl bg-papier/95 p-4 text-wald-dunkel";
const notice = "max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel";

function Admin() {
  const { session, loading } = useSession();
  const signedIn = !!session;
  const { locale } = useLocale();
  const t = useT().admin;
  // failures are kept as HTTP status codes and translated at render time
  const [gate, setGate] = useState<"checking" | "ok" | { status: number }>("checking");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [owner, setOwner] = useState<string>(ALL);
  const [page, setPage] = useState<SearchPage | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | { status: number } | null>(null);
  const [listError, setListError] = useState<number | null>(null);
  const seq = useRef(0);
  const offsetRef = useRef(0);

  useEffect(() => {
    setGate("checking");
    setUsers([]);
    setPage(null);
    setSelected(null);
    if (!signedIn) return;
    let live = true;
    void (async () => {
      const me = await adminGet<{ role: string }>("/me");
      if (!live) return;
      if (!me.ok) return setGate({ status: me.status });
      setGate("ok");
      const u = await adminGet<{ users: AdminUser[] }>("/users");
      if (live && u.ok) setUsers(u.data.users);
      else if (live && !u.ok) setListError(u.status);
    })();
    return () => {
      live = false;
    };
  }, [signedIn]);

  const query = (who: string, offset: number) => `/searches?${who === ALL ? "" : `user=${encodeURIComponent(who)}&`}offset=${offset}&limit=${LIMIT}`;

  const load = useCallback(async (who: string, offset: number) => {
    const n = ++seq.current;
    const r = await adminGet<SearchPage>(query(who, offset));
    if (n !== seq.current) return;
    if (!r.ok) return setListError(r.status);
    setListError(null);
    offsetRef.current = offset;
    setPage((p) => (offset > 0 && p ? { ...r.data, items: [...p.items, ...r.data.items] } : r.data));
    if (offset === 0) setSelected(r.data.items[0]?.request_id ?? null);
  }, []);

  useEffect(() => {
    if (gate === "ok") void load(owner, 0);
  }, [gate, owner, load]);

  useEffect(() => {
    setDetail(null);
    if (gate !== "ok" || !selected) return;
    let live = true;
    void adminGet<Detail>(`/searches/${encodeURIComponent(selected)}`).then((r) => live && setDetail(r.ok ? r.data : { status: r.status }));
    return () => {
      live = false;
    };
  }, [gate, selected]);

  if (loading) return null;
  if (!session)
    return (
      <p className={notice}>
        <Link href="/anmelden" className="underline">
          {t.signInPlease}
        </Link>
      </p>
    );
  if (gate === "checking") return null;
  if (typeof gate === "object") return <p className={notice}>{adminErrorText(gate.status, locale)}</p>;

  const total = users.reduce((a, u) => a + u.searches, 0);
  const row = (active: boolean) => `block w-full rounded-lg px-2 py-1 text-left text-sm hover:bg-wald-dunkel/10 ${active ? "bg-wald-dunkel/15 font-bold" : ""}`;
  const list = page?.items.slice(0, LIMIT) ?? [];
  const label = owner === ALL ? t.allLower : (users.find((u) => u.user_id === owner)?.email ?? t.unknown);

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <h1 className="schrift-feld font-serif text-3xl">Backend</h1>
      {listError !== null && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {adminErrorText(listError, locale)}
        </p>
      )}
      <div className="grid grid-cols-[16rem_22rem_1fr] items-start gap-4">
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">{t.users}</h2>
          <button type="button" className={row(owner === ALL)} onClick={() => setOwner(ALL)}>{`${t.all} (${total})`}</button>
          {users.map((u) => (
            <button key={u.user_id} type="button" className={row(owner === u.user_id)} onClick={() => setOwner(u.user_id)}>
              {u.user_id === "unknown" ? `${t.unknown} (${u.searches})` : `${u.email ?? u.user_id} (${u.searches})`}
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">{t.recent(label)}</h2>
          {list.length === 0 && <p className="text-sm">{t.noSearches}</p>}
          {list.map((s) => (
            <button key={s.request_id} type="button" className={row(selected === s.request_id)} onClick={() => setSelected(s.request_id)}>
              <span className="block truncate">{s.message ?? t.olderSearch}</span>
              <span className="block text-xs font-normal text-wald-dunkel/70">{`${when(s.ts, locale)} · ${usd(s.cost_usd, locale)} · ${ms(s.duration_ms, locale)}`}</span>
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">{t.details}</h2>
          {detail && "status" in detail ? <p className="text-sm text-red-900">{adminErrorText(detail.status, locale)}</p> : detail ? <SearchDetail d={detail} /> : selected ? <p className="text-sm">{t.loading}</p> : <p className="text-sm">{t.noneSelected}</p>}
        </section>
      </div>
      {page && <SearchTable page={page} selected={selected} onSelect={setSelected} onMore={() => void load(owner, offsetRef.current + LIMIT)} />}
    </main>
  );
}

export default function AdminPage() {
  return (
    <PageFrame wide>
      <Admin />
    </PageFrame>
  );
}
