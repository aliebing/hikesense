"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PageFrame from "../../components/PageFrame";
import BackendLogin from "../../components/backend/BackendLogin";
import SearchDetail from "../../components/backend/SearchDetail";
import SearchTable from "../../components/backend/SearchTable";
import UserTable from "../../components/backend/UserTable";
import { useLocale, useT } from "../../i18n";
import { adminErrorText, backendGet, backendLogout, ms, usd, when, type BackendUser, type SearchDetail as Detail, type SearchPage } from "../../lib/backend";

const LIMIT = 50;
const ALL = "all";
const card = "rounded-xl bg-papier/95 p-4 text-wald-dunkel";
const notice = "max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel";

function Admin() {
  const { locale } = useLocale();
  const t = useT().admin;
  // failures are kept as HTTP status codes and translated at render time
  const [gate, setGate] = useState<"checking" | "login" | "ok" | { status: number }>("checking");
  const [attempt, setAttempt] = useState(0); // bumped after login/logout: re-check the session
  const [users, setUsers] = useState<BackendUser[]>([]);
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
    let live = true;
    void (async () => {
      const me = await backendGet<{ name: string }>("/me");
      if (!live) return;
      if (!me.ok) return setGate(me.status === 401 ? "login" : { status: me.status });
      setGate("ok");
      const u = await backendGet<{ users: BackendUser[] }>("/users");
      if (live && u.ok) setUsers(u.data.users);
      else if (live && !u.ok) setListError(u.status);
    })();
    return () => {
      live = false;
    };
  }, [attempt]);

  const query = (who: string, offset: number) => `/searches?${who === ALL ? "" : `user=${encodeURIComponent(who)}&`}offset=${offset}&limit=${LIMIT}`;

  const load = useCallback(async (who: string, offset: number) => {
    const n = ++seq.current;
    const r = await backendGet<SearchPage>(query(who, offset));
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
    void backendGet<Detail>(`/searches/${encodeURIComponent(selected)}`).then((r) => live && setDetail(r.ok ? r.data : { status: r.status }));
    return () => {
      live = false;
    };
  }, [gate, selected]);

  if (gate === "checking") return null;
  if (gate === "login") return <BackendLogin onSignedIn={() => setAttempt((n) => n + 1)} />;
  if (typeof gate === "object") return <p className={notice}>{adminErrorText(gate.status, locale)}</p>;

  const total = users.reduce((a, u) => a + u.searches, 0);
  const row = (active: boolean) => `block w-full rounded-lg px-2 py-1 text-left text-sm hover:bg-wald-dunkel/10 ${active ? "bg-wald-dunkel/15 font-bold" : ""}`;
  const list = page?.items.slice(0, LIMIT) ?? [];
  const label = owner === ALL ? t.allLower : owner === "guest" ? t.guests : (users.find((u) => u.user_id === owner)?.email ?? t.unknown);

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="schrift-feld font-serif text-3xl">Backend</h1>
        <button
          type="button"
          className="rounded-full border border-white/40 px-4 py-1 text-sm hover:bg-white/15"
          onClick={() => void backendLogout().finally(() => setAttempt((n) => n + 1))}
        >
          {t.signOut}
        </button>
      </div>
      {listError !== null && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {adminErrorText(listError, locale)}
        </p>
      )}
      <div className="grid grid-cols-[16rem_22rem_1fr] items-start gap-4">
        <section className={card}>
          <h2 className="mb-2 font-serif text-lg">{t.users}</h2>
          <button type="button" className={row(owner === ALL)} onClick={() => setOwner(ALL)}>{`${t.all} (${total})`}</button>
          {users.map((u) => (
            <button key={u.user_id} type="button" className={row(owner === u.user_id)} onClick={() => setOwner(u.user_id)}>
              {u.user_id === "unknown" ? `${t.unknown} (${u.searches})` : u.user_id === "guest" ? `${t.guests} (${u.searches})` : `${u.email ?? u.user_id} (${u.searches})`}
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="mb-2 font-serif text-lg">{t.recent(label)}</h2>
          {list.length === 0 && <p className="text-sm">{t.noSearches}</p>}
          {list.map((s) => (
            <button key={s.request_id} type="button" className={row(selected === s.request_id)} onClick={() => setSelected(s.request_id)}>
              <span className="block truncate">{s.message ?? t.olderSearch}</span>
              <span className="block text-xs font-normal text-wald-dunkel/70">{`${when(s.ts, locale)} · ${usd(s.cost_usd, locale)} · ${ms(s.duration_ms, locale)}`}</span>
            </button>
          ))}
        </section>
        <section className={card}>
          <h2 className="mb-2 font-serif text-lg">{t.details}</h2>
          {detail && "status" in detail ? <p className="text-sm text-red-900">{adminErrorText(detail.status, locale)}</p> : detail ? <SearchDetail d={detail} /> : selected ? <p className="text-sm">{t.loading}</p> : <p className="text-sm">{t.noneSelected}</p>}
        </section>
      </div>
      <section className={card}>
        <h2 className="mb-2 font-serif text-lg">{t.accounts}</h2>
        <UserTable users={users} />
      </section>
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
