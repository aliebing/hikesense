"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import PageFrame from "../../components/PageFrame";
import SearchDetail from "../../components/admin/SearchDetail";
import SearchTable from "../../components/admin/SearchTable";
import { adminGet, ms, usd, when, type AdminUser, type SearchDetail as Detail, type SearchPage } from "../../lib/admin";
import { useSession } from "../../lib/auth";

const LIMIT = 50;
const ALL = "all";
const card = "rounded-xl bg-papier/95 p-4 text-wald-dunkel";
const notice = "max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel";

function Admin() {
  const { session, loading } = useSession();
  const signedIn = !!session;
  const [gate, setGate] = useState<"checking" | "ok" | { error: string }>("checking");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [owner, setOwner] = useState<string>(ALL);
  const [page, setPage] = useState<SearchPage | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | { error: string } | null>(null);
  const [listError, setListError] = useState<string | null>(null);
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
      if (!me.ok) return setGate({ error: me.status === 403 ? "Kein Zugriff" : me.message });
      setGate("ok");
      const u = await adminGet<{ users: AdminUser[] }>("/users");
      if (live && u.ok) setUsers(u.data.users);
      else if (live && !u.ok) setListError(u.message);
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
    if (!r.ok) return setListError(r.message);
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
    void adminGet<Detail>(`/searches/${encodeURIComponent(selected)}`).then((r) => live && setDetail(r.ok ? r.data : { error: r.message }));
    return () => {
      live = false;
    };
  }, [gate, selected]);

  if (loading) return null;
  if (!session)
    return (
      <p className={notice}>
        <Link href="/anmelden" className="underline">
          Bitte anmelden
        </Link>
      </p>
    );
  if (gate === "checking") return null;
  if (typeof gate === "object") return <p className={notice}>{gate.error}</p>;

  const total = users.reduce((a, u) => a + u.searches, 0);
  const row = (active: boolean) => `block w-full rounded-lg px-2 py-1 text-left text-sm hover:bg-wald-dunkel/10 ${active ? "bg-wald-dunkel/15 font-bold" : ""}`;
  const list = page?.items.slice(0, LIMIT) ?? [];
  const label = owner === ALL ? "alle" : (users.find((u) => u.user_id === owner)?.email ?? "Unbekannt");

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <h1 className="schrift-feld font-serif text-3xl">Backend</h1>
      {listError && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {listError}
        </p>
      )}
      <div className="grid grid-cols-[16rem_22rem_1fr] items-start gap-4">
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">Benutzer</h2>
          <button type="button" className={row(owner === ALL)} onClick={() => setOwner(ALL)}>{`Alle (${total})`}</button>
          {users.map((u) => (
            <button key={u.user_id} type="button" className={row(owner === u.user_id)} onClick={() => setOwner(u.user_id)}>
              {u.user_id === "unknown" ? `Unbekannt (${u.searches})` : `${u.email ?? u.user_id} (${u.searches})`}
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">{`Letzte Suchen · ${label}`}</h2>
          {list.length === 0 && <p className="text-sm">Keine Suchen.</p>}
          {list.map((s) => (
            <button key={s.request_id} type="button" className={row(selected === s.request_id)} onClick={() => setSelected(s.request_id)}>
              <span className="block truncate">{s.message ?? "(ältere Suche)"}</span>
              <span className="block text-xs font-normal text-wald-dunkel/70">{`${when(s.ts)} · ${usd(s.cost_usd)} · ${ms(s.duration_ms)}`}</span>
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="schrift-feld mb-2 font-serif text-lg">Details</h2>
          {detail && "error" in detail ? <p className="text-sm text-red-900">{detail.error}</p> : detail ? <SearchDetail d={detail} /> : selected ? <p className="text-sm">Lädt …</p> : <p className="text-sm">Keine Suche gewählt.</p>}
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
