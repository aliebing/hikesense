"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PageFrame from "../../components/PageFrame";
import { useT } from "../../i18n";
import { checkBlocked, reportBlocked, useSession } from "../../lib/auth";
import { loadPreferences, PREFERENCE_TAGS, SAVED_WEIGHTS, setPreference, type PreferenceError, type PreferenceTag, type SavedPreference } from "../../lib/preferences";

type Value = { mode: "prefer" | "avoid"; weight: number } | null;
const DEFAULT_WEIGHT = 2;

const pill = (active: boolean) =>
  `rounded-full border px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wald ${
    active ? "border-wald-dunkel bg-wald-dunkel text-papier" : "border-wald-dunkel/30 hover:bg-wald-dunkel/10"
  }`;

function Row({ tag, value, onChange, disabled }: { tag: PreferenceTag; value: Value; onChange: (v: Value) => void; disabled: boolean }) {
  const t = useT().prefs;
  const [label, explain] = t.tags[tag];
  const choices: { key: string; text: string; v: Value }[] = [
    { key: "none", text: t.none, v: null },
    { key: "prefer", text: t.prefer, v: { mode: "prefer", weight: value?.weight ?? DEFAULT_WEIGHT } },
    { key: "avoid", text: t.avoid, v: { mode: "avoid", weight: value?.weight ?? DEFAULT_WEIGHT } },
  ];
  const current = value?.mode ?? "none";
  return (
    <li className="flex flex-col gap-2 rounded-xl bg-papier/95 p-3 text-sm text-wald-dunkel shadow sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-0.5">
        <h2 className="font-serif text-base leading-snug">{label}</h2>
        <p className="text-xs text-wald-dunkel/80">{explain}</p>
      </div>
      <div className="flex flex-col items-start gap-1.5 sm:items-end">
        <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
          {choices.map((c) => (
            <button key={c.key} type="button" role="radio" aria-checked={current === c.key} disabled={disabled} onClick={() => onChange(c.v)} className={pill(current === c.key)}>
              {c.text}
            </button>
          ))}
        </div>
        {value && (
          <div role="radiogroup" aria-label={`${label}: ${t.weight}`} className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-wald-dunkel/80">{t.weight}:</span>
            {SAVED_WEIGHTS.map((w) => (
              <button key={w} type="button" role="radio" aria-checked={value.weight === w} disabled={disabled} onClick={() => onChange({ ...value, weight: w })} className={pill(value.weight === w)}>
                {t.weights[w]}
              </button>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

/** Standing preferences of the signed-in user: per feature tag egal / bevorzugen / meiden. */
export default function Vorlieben() {
  const { session, loading } = useSession();
  const t = useT();
  const p = t.prefs;
  const [values, setValues] = useState<Partial<Record<PreferenceTag, Value>> | null>(null);
  const [error, setError] = useState<PreferenceError | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const signedIn = !!session;

  useEffect(() => {
    if (!signedIn) {
      setValues(null);
      return;
    }
    let live = true;
    void loadPreferences().then((r) => {
      if (!live) return;
      setError(r.error);
      setValues(Object.fromEntries(r.prefs.map((x: SavedPreference) => [x.tag_id, { mode: x.mode, weight: x.weight }])));
    });
    return () => {
      live = false;
    };
  }, [signedIn]);

  const change = async (tag: PreferenceTag, v: Value) => {
    setBusy(true);
    setSaved(false);
    const r = await setPreference(tag, v);
    setBusy(false);
    if (r.error && (await checkBlocked())) return reportBlocked();
    setError(r.error);
    if (!r.error) {
      setValues((vs) => ({ ...vs, [tag]: v }));
      setSaved(true);
    }
  };

  return (
    <PageFrame back={{ href: "/", label: p.backChat }}>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">{p.title}</h1>
        <div className="flex w-full max-w-2xl flex-col gap-3">
          <p className="schrift-feld text-sm text-papier">{p.intro}</p>
          {!loading && !session && (
            <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
              {p.signInBefore}
              <Link href="/anmelden" className="underline">
                {p.signIn}
              </Link>
              .
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
              {t.errors.prefs[error]}
            </p>
          )}
          {values && (
            <>
              <ul className="flex flex-col gap-2">
                {PREFERENCE_TAGS.map((tag) => (
                  <Row key={tag} tag={tag} value={values[tag] ?? null} disabled={busy} onChange={(v) => void change(tag, v)} />
                ))}
              </ul>
              <p role="status" className="schrift-feld text-xs text-papier">
                {saved ? `${p.saved}. ` : ""}
                {p.applied}
              </p>
            </>
          )}
        </div>
      </main>
    </PageFrame>
  );
}
