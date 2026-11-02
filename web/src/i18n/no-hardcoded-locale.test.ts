import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return n === "i18n" ? [] : sources(p);
    return /\.(ts|tsx)$/.test(n) && !/\.test\.tsx?$/.test(n) ? [p] : [];
  });
}

it("no source file outside i18n/ hard-codes the German Intl locale", () => {
  const offenders = sources(join(process.cwd(), "src")).filter((f) => readFileSync(f, "utf8").includes('"de-DE"'));
  expect(offenders).toEqual([]);
});
