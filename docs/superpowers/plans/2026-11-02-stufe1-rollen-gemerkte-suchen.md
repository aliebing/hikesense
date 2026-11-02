# Stufe 1: Rollen und gemerkte Ergebnisse – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Benutzer haben eine Rolle (`user`/`admin`) in einer Tabelle `profiles`, der Server kann Admins erkennen, und ein Benutzer kann sich das Ergebnis einer Suche merken und unter „Meine Pläne“ wieder genau so ansehen.

**Architecture:** Eine Supabase-Migration legt `profiles` an (Trigger beim Registrieren, Nachtrag für bestehende Konten, RLS) und erlaubt `kind = 'search'` in `saved_plans`. Das Backend bekommt `hikeall/roles.py` (Rolle lesen) und einen kleinen Router `/admin/me`, der Token **und** Rolle prüft – die Grundlage für Stufe 2. Im Web speichert ein Knopf „Ergebnis merken“ über das bestehende `lib/plans.ts` eine Momentaufnahme (Nachrichten, Antwort, Karten); „Meine Pläne“ zeigt sie in einem eigenen Abschnitt, `/gemerkt?id=` zeigt sie an.

**Tech Stack:** Supabase/Postgres (Migrationen, RLS), Python 3.12 + FastAPI + psycopg + pytest (`backend/`), Next.js + React + Vitest + Testing Library (`web/`).

**Spec:** `docs/superpowers/specs/2026-11-02-rollen-backend-regionen-wetter-design.md`, Abschnitt „Stufe 1“.

## Global Constraints

- Oberfläche und Fehlermeldungen auf Deutsch, Stil wie bestehende Meldungen in `web/src/lib/plans.ts`.
- Zwei Rollen, genau die Werte `user` und `admin`; Default `user`.
- Rolle wird **nie** vom Client geändert; keine Rollenverwaltung in der Oberfläche.
- Admin ist `admin@hikeall.local`; `make admin-user` setzt dessen Rolle auf `admin`.
- Gemerkte Suche = Momentaufnahme, wird **nicht** neu ausgeführt und nicht bearbeitet.
- Bestehendes „Merken“ (`day_hike`, `multiday`) bleibt unverändert.
- `enable_confirmations = false` bleibt.
- Voraussetzung: Branch `hintergrund-feinschliff` ist abgeschlossen und in `main`; Arbeit auf neuem Branch `stufe1-rollen` von `main`.

## Review Focus

1. **Benutzer, der sich selbst zum Admin macht** (`update profiles set role='admin'` mit eigenem JWT) → muss scheitern. Test in Task 1 (`test_user_cannot_change_own_role`).
2. **Konto, das vor der Migration existierte** (Ali, Smoke-Benutzer, Admin) → hat danach eine `profiles`-Zeile. Test in Task 1 (`test_backfill_creates_missing_profiles`).
3. **Gültiges Token, aber keine `profiles`-Zeile** (z. B. Zeile gelöscht) → Rolle gilt als `user`, `/admin/me` antwortet 403, nicht 500. Test in Task 2/3 (`test_role_defaults_to_user_without_profile`, `test_admin_me_forbidden_for_user`).
4. **Ergebnis mit genau einer Tour bzw. mit Ausweich-Hinweis** → wird ebenso gemerkt und mit Hinweis wieder angezeigt. Test in Task 4 (`savedSearchOf keeps fallback`) und Task 6 (`shows fallback note`).
5. **Gemerkte Suche eines anderen Benutzers per `/gemerkt?id=` aufrufen** → „nicht gefunden“, keine Daten (RLS). Test in Task 6 (`shows not found when the row is missing`); RLS selbst ist durch `test_saved_plans_rls.py` abgedeckt, Task 1 ergänzt `kind='search'`.

---

### Task 1: Migration `profiles` und `kind = 'search'`

**Files:**
- Create: `supabase/migrations/20261102000001_profiles.sql`
- Test: `backend/tests/test_profiles_rls.py` (Muster: `backend/tests/test_saved_plans_rls.py`, Marker `pytest.mark.db`, Helfer `_as`/`_user` dort abschauen)
- Modify: `backend/tests/test_saved_plans_rls.py` (ein Test für `kind='search'`)

**Interfaces:**
- Produces: Tabelle `public.profiles(user_id uuid pk → auth.users(id) on delete cascade, email text, role text not null default 'user' check (role in ('user','admin')), created_at timestamptz not null default now())`; Trigger `on_auth_user_created` (after insert on `auth.users`, `security definer`-Funktion `public.handle_new_user()`); `saved_plans.kind` erlaubt `'day_hike' | 'multiday' | 'search'`.

- [ ] **Step 1: Failing tests schreiben** in `test_profiles_rls.py`:
  - `test_signup_creates_user_profile`: nach `insert into auth.users (id, email)` gibt es genau eine Zeile in `profiles` mit `role = 'user'` und derselben E-Mail.
  - `test_user_reads_only_own_profile`: als `authenticated` mit `sub = a` liefert `select count(*) from profiles` genau 1 (die eigene), obwohl auch `b` existiert.
  - `test_user_cannot_change_own_role`: als `authenticated` (`sub = a`) wirft `update profiles set role='admin' where user_id = a` `InsufficientPrivilege` oder ändert 0 Zeilen; danach (`reset role`) ist `role` weiter `'user'`.
  - `test_anon_sees_no_profiles`: als `anon` wirft `select` `InsufficientPrivilege` oder liefert 0.
  - `test_backfill_creates_missing_profiles`: Zeile in `profiles` löschen, den Nachtrag-Befehl aus der Migration erneut ausführen (`insert into profiles (user_id, email) select id, email from auth.users on conflict do nothing`), Zeile ist wieder da.
  - In `test_saved_plans_rls.py`: `test_search_kind_allowed` – Insert mit `kind='search'` klappt für den Besitzer.
- [ ] **Step 2: Fehlschlag prüfen** – `cd backend && uv run pytest tests/test_profiles_rls.py tests/test_saved_plans_rls.py -q` → FAIL (`relation "profiles" does not exist`, Check-Constraint verletzt).
- [ ] **Step 3: Migration schreiben.** Inhalt: Tabelle wie oben; Funktion `handle_new_user()` (`security definer`, `set search_path = public`) fügt `(new.id, new.email)` ein, `on conflict do nothing`; Trigger; Nachtrag wie in Step 1; `alter table profiles enable row level security`; Policy `profiles_select` für `authenticated` mit `using (user_id = auth.uid())`; `revoke all on profiles from anon, authenticated; grant select on profiles to authenticated;` (kein Insert/Update/Delete für Clients – Grund siehe Grants-Kommentar in `20261030000006_saved_plans_grants.sql`). `saved_plans`: `alter table saved_plans drop constraint saved_plans_kind_check, add constraint saved_plans_kind_check check (kind in ('day_hike','multiday','search'));`. Kommentarzeilen auf Englisch wie in den bestehenden Migrationen.
- [ ] **Step 4: Migration anwenden und Tests laufen lassen** – `supabase migration up` (oder `supabase db reset`, wenn lokal üblich; README prüfen), dann `cd backend && uv run pytest tests/test_profiles_rls.py tests/test_saved_plans_rls.py tests/test_schema.py -q` → PASS.
- [ ] **Step 5: Commit** – `git add supabase/migrations/20261102000001_profiles.sql backend/tests/test_profiles_rls.py backend/tests/test_saved_plans_rls.py && git commit -m "feat: Tabelle profiles mit Rolle, gemerkte Suchen in saved_plans"`

### Task 2: Rolle lesen, Admin-Rolle setzen

**Files:**
- Create: `backend/src/hikeall/roles.py`
- Modify: `backend/src/hikeall/admin.py` (`ensure_admin`), `backend/src/hikeall/cli.py:530-545` (Ausgabe), `Makefile` (Kommentar bei `admin-user`)
- Test: `backend/tests/test_roles.py`, `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: Tabelle `profiles` (Task 1).
- Produces:
  - `Role = Literal["user", "admin"]`
  - `role_of(conn: psycopg.Connection, user_id: str) -> Role` – `'admin'` nur bei Zeile mit `role = 'admin'`, sonst (auch ohne Zeile oder bei ungültiger UUID) `'user'`.
  - `set_role(conn: psycopg.Connection, user_id: str, role: Role) -> None` – Upsert in `profiles` (mit E-Mail aus `auth.users`), commit.
  - `ensure_admin(...)` setzt nach Anlegen/Aktualisieren `set_role(conn, uid, "admin")`; Rückgabewerte `"angelegt"`/`"aktualisiert"` bleiben.

- [ ] **Step 1: Failing tests** (`pytest.mark.db`, `conn`-Fixture aus `conftest.py`, alles in zurückgerollter Transaktion wie in den RLS-Tests):
  - `test_role_defaults_to_user` – neuer `auth.users`-Eintrag → `role_of == "user"`.
  - `test_role_defaults_to_user_without_profile` – Profilzeile gelöscht → `"user"`; `role_of(conn, "not-a-uuid") == "user"`.
  - `test_set_role_admin` – `set_role(..., "admin")` → `role_of == "admin"`.
  - in `test_admin.py`: `test_ensure_admin_sets_admin_role` – nach `ensure_admin` ist die Rolle von `admin@hikeall.local` `"admin"`, auch beim zweiten Aufruf (`"aktualisiert"`). Achtung: `ensure_admin` committet; bestehende Tests in `test_admin.py` zeigen, wie dort aufgeräumt wird – genauso verfahren.
- [ ] **Step 2: Fehlschlag prüfen** – `cd backend && uv run pytest tests/test_roles.py tests/test_admin.py -q` → FAIL (`ModuleNotFoundError: hikeall.roles`).
- [ ] **Step 3: `roles.py` implementieren und `ensure_admin` erweitern.** `role_of` mit `select role from profiles where user_id = %s::uuid`; ungültige UUID abfangen (`psycopg.errors.InvalidTextRepresentation` → Rollback des Savepoints, `"user"`), dafür `conn.transaction()` als Savepoint nutzen.
- [ ] **Step 4: Tests laufen lassen** → PASS. Dann `make admin-user` lokal ausführen und mit `psql` prüfen: `select role from profiles where email = 'admin@hikeall.local'` → `admin`.
- [ ] **Step 5: Commit** – `git commit -m "feat: Rollen lesen, make admin-user setzt Rolle admin"`

### Task 3: Server prüft Admin – `GET /admin/me`

**Files:**
- Create: `backend/src/hikeall/api/admin.py`
- Modify: `backend/src/hikeall/api/app.py` (Router einhängen), `backend/src/hikeall/api/chat.py` (Token-Prüfung in eine gemeinsame Hilfsfunktion ziehen, siehe unten), `web/next.config.ts` (Rewrite `/api/admin/:path*` → `${API_INTERNAL_URL}/admin/:path*`)
- Test: `backend/tests/test_api_admin.py` (Muster: `bearer()`, `settings`-Fixture aus `backend/tests/test_api_chat.py`)

**Interfaces:**
- Consumes: `verify_token`, `AuthError`, `AUTH_MESSAGES` (bestehend), `role_of` (Task 2).
- Produces:
  - `authenticate(request: Request, settings: Settings) -> AuthUser | JSONResponse` in `api/admin.py` **oder** gemeinsam genutzt aus `chat.py` herausgezogen (gleiche 401/503-Antworten wie heute in `/chat`; `/chat` danach darüber).
  - `make_admin_router(settings: Settings, role_lookup: Callable[[str], Role]) -> APIRouter` mit `GET /admin/me` → `200 {"user_id": str, "role": "admin"}`; Nicht-Admin → `403 {"detail": "Kein Zugriff"}`; ohne/falsches Token → `401` wie `/chat`.
  - In `create_app`: `role_lookup` = Funktion, die eine Verbindung zu `settings.supabase_db_url` öffnet und `role_of` aufruft; `create_app` bekommt optionalen Parameter `role_lookup` für Tests.
  - Stufe 2 hängt weitere Admin-Endpunkte an diesen Router.

- [ ] **Step 1: Failing tests:**
  - `test_admin_me_requires_token` – ohne Header → 401.
  - `test_admin_me_forbidden_for_user` – `role_lookup=lambda uid: "user"` → 403, Body `{"detail": "Kein Zugriff"}`.
  - `test_admin_me_ok_for_admin` – `role_lookup=lambda uid: "admin"`, `bearer(sub="a1")` → 200 `{"user_id": "a1", "role": "admin"}`.
  - `test_admin_me_db_down` – `role_lookup` wirft `psycopg.OperationalError` → 503 mit deutscher Meldung (nicht 500).
  - Bestehende `tests/test_api_chat.py` muss nach dem Herausziehen der Token-Prüfung unverändert grün sein.
- [ ] **Step 2: Fehlschlag prüfen** – `cd backend && uv run pytest tests/test_api_admin.py -q` → FAIL (404).
- [ ] **Step 3: Router implementieren, in `create_app` einhängen, Rewrite in `next.config.ts` ergänzen.** `role_lookup` per `run_in_threadpool` aufrufen.
- [ ] **Step 4: Tests laufen lassen** – `cd backend && uv run pytest tests/test_api_admin.py tests/test_api_chat.py tests/test_api.py -q` → PASS.
- [ ] **Step 5: Commit** – `git commit -m "feat: /admin/me prüft Token und Rolle im Server"`

### Task 4: `lib/plans.ts` – gemerkte Suche als Momentaufnahme

**Files:**
- Modify: `web/src/lib/plans.ts`
- Test: `web/src/lib/plans.test.ts`

**Interfaces:**
- Consumes: `ChatState`, `LastResults` aus `web/src/lib/chatState.ts`; `ChatItem` aus `web/src/components/ChatMessages.tsx`.
- Produces:
  - `PlanKind = "day_hike" | "multiday" | "search"`
  - `type SavedSearch = { v: 1; messages: string[]; answer: string; results: LastResults }`
  - `savedSearchOf(state: ChatState): SavedSearch | null` – `null`, wenn `state.last` leer ist. `messages`: die Texte aller `user`-Items der Unterhaltung bis zum letzten `results`-Item (das zu `state.last` gehört), also inklusive Verfeinerungen; `answer`: Text des ersten `assistant`-Items nach diesem `results`-Item (leer, wenn keins).
  - `searchTitle(s: SavedSearch): string` – Nachrichten mit „ · “ verbunden, auf 80 Zeichen gekürzt mit „…“; leer → „Gemerkte Suche“.
  - `isSavedSearch(payload: unknown): payload is SavedSearch` – prüft `v === 1`, `messages` Array, `results.cards` Array.

- [ ] **Step 1: Failing tests:**
  - `savedSearchOf returns null without results`.
  - `savedSearchOf collects the messages including refinements` – Items: user „Feldberg 15 km“, results, assistant „…“, user „mit Einkehr“, results (2 Karten), assistant „Zwei Touren …“ → `messages == ["Feldberg 15 km", "mit Einkehr"]`, `answer == "Zwei Touren …"`, `results.cards.length == 2`.
  - `savedSearchOf ignores messages after the last result` – Items: user „Feldberg“, results, assistant „…“, user „Was ist der Schwarzwaldverein?“, assistant „…“ → `messages == ["Feldberg"]`, `answer` = Text des ersten assistant-Items.
  - `searchTitle joins messages` – `["Feldberg 15 km", "mit Einkehr"]` → „Feldberg 15 km · mit Einkehr“.
  - `savedSearchOf keeps fallback` – `state.last.fallback = "Keine Tour erfüllt alle Wünsche …"` landet unverändert in `results.fallback`.
  - `searchTitle truncates to 80 chars`, `searchTitle falls back to "Gemerkte Suche"`.
  - `isSavedSearch rejects day_hike payloads` (`{trail_id:"t1"}` → false).
  - `savePlan("search", …)` ruft `insert` mit `kind: "search"` (bestehender Mock).
- [ ] **Step 2: Fehlschlag prüfen** – `cd web && npx vitest run src/lib/plans.test.ts` → FAIL.
- [ ] **Step 3: Implementieren.**
- [ ] **Step 4: Tests laufen lassen** → PASS; `npx tsc --noEmit` ohne Fehler.
- [ ] **Step 5: Commit** – `git commit -m "feat: gemerkte Suche als Momentaufnahme (plans.ts)"`

### Task 5: Knopf „Ergebnis merken“ auf der Startseite

**Files:**
- Modify: `web/src/components/MerkenButton.tsx` (Beschriftung als Prop), `web/src/components/ResultsPane.tsx`
- Test: `web/src/components/ResultsPane.test.tsx`

**Interfaces:**
- Consumes: `savedSearchOf`, `searchTitle` (Task 4); `MerkenButton`.
- Produces: `MerkenButton` bekommt optionale Props `label = "Merken"` und `savedLabel = "Gemerkt"`; sonst unverändert (erscheint nur angemeldet).

- [ ] **Step 1: Failing tests** in `ResultsPane.test.tsx` (vorhandenes Setup für `useChat`/`useSession` nutzen):
  - `offers "Ergebnis merken" for a signed-in user with several tours` – Knopf sichtbar; Klick ruft `savePlan("search", <Titel>, <SavedSearch>)` mit `results.cards` = Karten aus `state.last`; danach Text „Gemerkt“.
  - `offers "Ergebnis merken" for a single tour` – auch bei `last.cards.length === 1`.
  - `hides "Ergebnis merken" when signed out`.
  - `hides "Ergebnis merken" for a multi-day plan` – bei `state.plan` (dort gibt es schon das Merken des Plans).
- [ ] **Step 2: Fehlschlag prüfen** – `cd web && npx vitest run src/components/ResultsPane.test.tsx` → FAIL.
- [ ] **Step 3: Implementieren.** Platz: rechts neben der Überschrift „N Touren gefunden“ bzw. über der Einzelvorschau; der Payload wird beim Klick aus dem aktuellen `state` gebildet. Nach einer neuen Suche (anderes `state.last`) springt der Knopf zurück auf „Ergebnis merken“ (`key` am Knopf aus der ersten `trail_id` + Kartenzahl).
- [ ] **Step 4: Tests laufen lassen** → PASS; `npx vitest run src/components` grün.
- [ ] **Step 5: Commit** – `git commit -m "feat: Ergebnis einer Suche merken"`

### Task 6: „Meine Pläne“ mit Abschnitt „Gemerkte Suchen“ und Seite `/gemerkt`

**Files:**
- Modify: `web/src/app/meine-plaene/page.tsx`
- Create: `web/src/app/gemerkt/page.tsx`
- Test: `web/src/app/meine-plaene/page.test.tsx` (neu, falls nicht vorhanden), `web/src/app/gemerkt/page.test.tsx`

**Interfaces:**
- Consumes: `listPlans`, `deletePlan`, `isSavedSearch`, `SavedSearch` (Task 4); `TourResultCard`, `TourPreview`, `PageFrame`, `useSession`; Lade-Muster von `web/src/app/plan/page.tsx:21-61` (`saved_plans` per `id`, `maybeSingle`, nur angemeldet, `Suspense` für `useSearchParams`).

- [ ] **Step 1: Failing tests:**
  - Meine Pläne: `lists saved searches in their own section` – Liste mit einem `search`- und einem `day_hike`-Eintrag → Überschrift „Gemerkte Suchen“ mit dem Suchtitel (Link auf `/gemerkt?id=<id>`), Überschrift „Touren und Pläne“ mit der Tour; Zeile zeigt „Suche · <Datum> · <N> Touren“.
  - Meine Pläne: `deletes a saved search` – Klick „Löschen: <Titel>“ entfernt die Zeile.
  - Meine Pläne: Leertext unverändert „Du hast noch keine Pläne gemerkt.“, wenn gar nichts gemerkt ist; ein Abschnitt ohne Einträge wird nicht angezeigt.
  - `/gemerkt`: `shows messages, answer and tiles` – Nachricht(en) als Zitat, Antworttext, Kacheln (`TourResultCard` je Karte, Link zur Tourseite `/t/<trail_id>`), Datum „Gemerkt am <Datum>“.
  - `/gemerkt`: `shows fallback note` – `results.fallback` erscheint als Hinweis wie in `ResultsPane`.
  - `/gemerkt`: `shows not found when the row is missing` – `maybeSingle` liefert `null` → „Diese gemerkte Suche gibt es nicht (mehr).“
  - `/gemerkt`: `asks to sign in when signed out`.
- [ ] **Step 2: Fehlschlag prüfen** – `cd web && npx vitest run src/app/meine-plaene src/app/gemerkt` → FAIL.
- [ ] **Step 3: Implementieren.** Abschnitte in `meine-plaene/page.tsx` nach `kind` trennen (`search` vs. Rest), Optik wie die bestehende Liste. `/gemerkt` mit `PageFrame back={{ href: "/meine-plaene", label: "← Meine Pläne" }}`; Kacheln im Raster wie `ResultsPane` (bei genau einer Karte `TourPreview`). Kein Neu-Suchen, keine Bearbeitung. Payloads, die `isSavedSearch` nicht bestehen, als „Diese gemerkte Suche lässt sich nicht anzeigen.“ melden.
- [ ] **Step 4: Tests laufen lassen** → PASS; dann `cd web && npm test` und `npx tsc --noEmit` komplett grün.
- [ ] **Step 5: Commit** – `git commit -m "feat: gemerkte Suchen unter Meine Pläne und /gemerkt"`

### Task 7: Abschluss – Doku und Gesamtprüfung

**Files:**
- Modify: `README.md` (Abschnitt zu Konten/Admin: Rollen, `profiles`, „Ergebnis merken“; Hinweis, dass `make admin-user` die Rolle setzt)

- [ ] **Step 1: README ergänzen.**
- [ ] **Step 2: Alles prüfen** – `make test` (Backend, mit laufender lokaler DB), `cd web && npm test && npx tsc --noEmit && npm run lint` → alles grün.
- [ ] **Step 3: Von Hand im Browser** (`make up`): neu registrieren → in `profiles` mit `role = user`; Suche „Rundtour Feldberg 15 km“ → „Ergebnis merken“ → „Meine Pläne“ zeigt sie unter „Gemerkte Suchen“ → `/gemerkt?id=…` zeigt Nachricht, Antwort, Kacheln; mit Admin-Konto anmelden und `curl -H "Authorization: Bearer <token>" localhost:8000/admin/me` → 200, mit normalem Konto → 403.
- [ ] **Step 4: Commit** – `git commit -m "docs: Rollen und gemerkte Suchen"`
