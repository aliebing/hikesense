import CreditsLine from "../components/CreditsLine";
import HomeStage from "../components/HomeStage";
import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";
import { getLandscapePool, getTrails, type Photo, type TrailSummary } from "../lib/data";
import { messagesFor } from "../i18n/locale";
import { getServerLocale } from "../i18n/server";
import { MissingConfigError } from "../lib/supabase";

export const dynamic = "force-dynamic";

export default async function Home() {
  const t = messagesFor(await getServerLocale()).home;
  let trails: TrailSummary[];
  try {
    trails = await getTrails();
  } catch (e) {
    console.error("getTrails failed:", e);
    return (
      <PageFrame>
        <Notice title={t.loadErrorTitle}>
          {e instanceof MissingConfigError ? (
            <p>{e.message}</p>
          ) : (
            <p>
              {t.dbDownBefore}
              <code>npx supabase start</code>
              {t.dbDownMiddle}
              <code>make up</code>.
            </p>
          )}
        </Notice>
        <HomeStage />
      </PageFrame>
    );
  }

  if (trails.length === 0) {
    return (
      <PageFrame>
        <Notice title={t.emptyTitle}>
          <p>
            {t.emptyBefore}
            <code>make import</code>.
          </p>
        </Notice>
        <HomeStage />
      </PageFrame>
    );
  }

  const longDistance = trails.filter((t) => t.kind === "long_distance");

  // the background pool for the results view; without it the view simply has no background photo
  const landscapes = await getLandscapePool().catch((e) => {
    console.error("getLandscapePool failed:", e);
    return [] as Photo[];
  });

  return (
    <PageFrame wide longDistance={longDistance.map(({ id, name }) => ({ id, name }))}>
      <HomeStage landscapes={landscapes.slice(0, 40)} />
      <CreditsLine />
    </PageFrame>
  );
}
